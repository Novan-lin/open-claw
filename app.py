"""
app.py - Flask API Server untuk Stock Analyzer Bot
====================================================
Endpoint:
    GET /signals  ->  Kembalikan data sinyal saham real-time dalam format JSON rapi.

Cara menjalankan:
    python app.py

Server berjalan di: http://localhost:5000
"""

import sys
import math
import json
import os
import csv
import time
import threading
from datetime import datetime, timezone, timedelta

from flask import Flask, jsonify, send_from_directory, request

# ============================================================
# IMPORT MODUL INTERNAL BOT
# ============================================================
from data import get_stock_data
from indicator import calculate_indicators
from ai_analyst import generate_ai_analysis
from scoring import calculate_score
from strategies import multi_strategy_confirmation
from volume_analysis import analyze_volume
from gap_detector import detect_gap
from stock_filter import is_stock_eligible
from stock_list import get_lq45
from entry_plan import generate_trade_plan
from risk_management import calculate_position_size
from signal_generator import generate_signal
from mtf_analysis import analyze_multi_timeframe
from tuner import load_best_params

# Muat parameter terbaik (fallback ke RSI=14, MA 20/50 jika file belum ada)
_BEST_PARAMS = load_best_params()

# ============================================================
# INISIALISASI FLASK
# ============================================================
app = Flask(__name__)

SIGNALS_FILE = "signals.json"
TRADES_CSV   = "trades.csv"
DEFAULT_DASHBOARD_LIMIT = 5
BACKGROUND_REFRESH_INTERVAL = 300   # detik — refresh tiap 5 menit tanpa cek jam bursa
BACKGROUND_SCAN_LIMIT       = 20    # jumlah saham yang di-scan tiap siklus background

# In-memory cache — agar data TIDAK hilang meskipun file write sedang berjalan
_signals_cache: list = []           # hasil scan terakhir yang berhasil
_cache_lock = threading.Lock()      # lock untuk thread-safe read/write cache

# ============================================================
# FUNGSI HELPER
# ============================================================

def _is_market_open() -> bool:
    """Cek apakah saat ini jam aktif bursa IDX (WIB)."""
    from datetime import time as dtime
    wib_tz = timezone(timedelta(hours=7))
    now = datetime.now(wib_tz)
    if now.weekday() >= 5:          # Sabtu / Minggu
        return False
    t = now.time()
    return (dtime(9, 0) <= t <= dtime(12, 0)) or (dtime(13, 30) <= t <= dtime(16, 0))


def safe_float(value, decimals=2):
    """Konversi nilai ke float aman; kembalikan None jika NaN atau None."""
    if value is None:
        return None
    try:
        f = float(value)
        return None if not math.isfinite(f) else round(f, decimals)
    except (TypeError, ValueError):
        return None


def normalize_signal_item(item: dict) -> dict:
    """Samakan bentuk data dari signals.json dan hasil analisa langsung Flask."""
    harga = item.get("price") if item.get("price") is not None else item.get("harga")

    return {
        "ticker":      item.get("ticker"),
        "harga":       safe_float(harga, 2),
        "signal":      item.get("signal", "HOLD"),
        "score":       item.get("score", 0),
        "smart_money": item.get("smart_money", False),
        "gap_up":      item.get("gap_up", False),
        "entry":       safe_float(item.get("entry"), 2),
        "tp":          safe_float(item.get("tp"), 2),
        "sl":          safe_float(item.get("sl"), 2),
        "lot":         item.get("lot"),
        "risk_amount": safe_float(item.get("risk_amount"), 2),
        "ai_analysis": item.get("ai") or item.get("ai_analysis", "-"),
        "_meta":       item.get("_meta", {}),
    }


def sort_signals(results: list[dict]) -> list[dict]:
    """Urutkan sinyal sesuai prioritas dashboard."""
    results.sort(
        key=lambda x: (
            x.get("score", 0),
            1 if x.get("smart_money") else 0,
            1 if x.get("gap_up") else 0,
        ),
        reverse=True
    )
    return results


def analyze_dashboard_signals(limit: int = DEFAULT_DASHBOARD_LIMIT) -> list[dict]:
    """
    Buat analisa langsung dari Flask agar localhost:5000 tetap punya data
    walaupun main.py belum berjalan.
    """
    tickers = get_lq45()[:limit]
    results = []

    print(f"\n[Dashboard] signals.json belum tersedia. Generate analisa {len(tickers)} saham...")

    for idx, ticker in enumerate(tickers, 1):
        clean = ticker.split(".")[0]
        print(f"[Dashboard] [{idx}/{len(tickers)}] Analyze {clean}...")

        result = analyze_stock(ticker)
        if not result or result.get("skipped") or result.get("error"):
            reason = (result.get("reason") or result.get("error")) if result else "Data kosong"
            print(f"[Dashboard] Skip {clean}: {reason}")
            continue

        results.append(normalize_signal_item(result))

    results = sort_signals(results)

    if results:
        with open(SIGNALS_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4, ensure_ascii=False)
        print(f"[Dashboard] {len(results)} analisa tersimpan ke {SIGNALS_FILE}")

    return results


def analyze_stock(ticker: str) -> dict | None:
    """
    Analisis satu saham dan kembalikan dictionary hasil lengkap.
    Mengembalikan None jika analisis gagal.
    """
    clean_ticker = ticker.split(".")[0] if "." in ticker else ticker

    try:
        # 1. Ambil data historis
        df = get_stock_data(ticker)
        if df is None:
            return None

        # Filter kelayakan: harga > 50 dan avg volume > 1 juta
        if not is_stock_eligible(df, clean_ticker):
            return {
                "ticker":  clean_ticker,
                "skipped": True,
                "reason":  "Tidak memenuhi filter minimum (harga/volume)"
            }

        # 2. Hitung indikator teknikal dengan parameter terbaik
        indicators = calculate_indicators(
            df,
            rsi_period=_BEST_PARAMS["rsi"],
            ma_short=_BEST_PARAMS["ma_short"],
            ma_long=_BEST_PARAMS["ma_long"],
        )
        if indicators is None:
            return None

        rsi   = indicators["rsi"]
        ma20  = indicators["ma20"]
        ma50  = indicators["ma50"]
        harga = indicators["close_price"]

        # 3. Deteksi volume & Smart Money
        volume_spike, avg_volume, current_volume, smart_money, volume_label, sm_confidence, sm_alasan = analyze_volume(df)

        # 4. Deteksi potensi Gap Up
        price_today     = df["Close"].iloc[-1]
        price_yesterday = df["Close"].iloc[-2] if len(df) > 1 else price_today
        gap_up, confidence = detect_gap(rsi, ma20, ma50, price_today, price_yesterday, smart_money)

        # 5. Generate sinyal trading
        signal_status, alasan_teknis = generate_signal(
            rsi,
            ma20,
            ma50,
            harga,
            smart_money=smart_money,
            gap_up=gap_up,
            gap_confidence=confidence,
        )

        # 6. Hitung skor + multi-strategy confirmation bonus
        try:
            mc = multi_strategy_confirmation(df)
            mc_bonus  = mc["score_bonus"]
            mc_signal = mc["signal"]
        except Exception:
            mc_bonus  = 0
            mc_signal = "HOLD"

        score, alasan_skoring = calculate_score(
            rsi, ma20, ma50, harga, smart_money, volume_label, gap_up, confidence,
            multi_confirmation_bonus=mc_bonus,
        )

        entry = None
        tp = None
        sl = None
        lot = None
        risk_amount = None

        if signal_status == "BUY" and smart_money:
            high = float(df["High"].iloc[-1])
            low = float(df["Low"].iloc[-1])
            price = float(harga)
            entry, tp, sl = generate_trade_plan(price, high, low, mode="range")

            position = calculate_position_size(
                capital=10_000_000,
                risk_percent=1,
                entry=entry,
                stop_loss=sl,
            )
            if position is not None:
                lot, risk_amount = position

        # 7. Multi-Timeframe Analysis
        print(f"-> [MTF] Analisa multi-timeframe {clean_ticker}...")
        try:
            mtf = analyze_multi_timeframe(ticker)
        except Exception as e_mtf:
            print(f"-> [MTF] Gagal: {e_mtf}")
            mtf = None

        # 8. Minta analisis AI (Ollama - Mistral) — lengkap dengan semua data
        ai_analysis = generate_ai_analysis(
            ticker=clean_ticker,
            signal=signal_status,
            rsi=rsi,
            ma20=ma20,
            ma50=ma50,
            harga=harga,
            entry=entry,
            tp=tp,
            sl=sl,
            score=score,
            alasan_scoring=alasan_skoring,
            smart_money=smart_money,
            volume_label=volume_label,
            gap_up=gap_up,
            gap_confidence=confidence,
            mtf=mtf,
        )

        return {
            "ticker":      clean_ticker,
            "harga":       safe_float(harga, 2),
            "signal":      signal_status,
            "score":       score,
            "multi_confirmation": mc_signal,
            "smart_money": smart_money,
            "gap_up":      gap_up,
            "entry":       safe_float(entry, 2),
            "tp":          safe_float(tp, 2),
            "sl":          safe_float(sl, 2),
            "lot":         lot,
            "risk_amount": safe_float(risk_amount, 2),
            "ai_analysis": ai_analysis,
            "_meta": {
                "rsi":            safe_float(rsi, 2),
                "ma20":           safe_float(ma20, 2),
                "ma50":           safe_float(ma50, 2),
                "gap_confidence": confidence,
                "volume_label":   volume_label,
                "sm_confidence":  round(sm_confidence, 2),
                "sm_alasan":      sm_alasan,
                "alasan":         alasan_skoring,
                "mtf":            mtf,
            },
        }

    except Exception as e:
        return {
            "ticker": clean_ticker,
            "error":  str(e),
        }


# ============================================================
# BACKGROUND AUTO-REFRESH (tanpa cek jam bursa)
# ============================================================

_is_scanning = False   # flag global: True saat scan sedang berjalan


def _do_scan():
    """Lakukan satu siklus scan dan simpan hasilnya. Return jumlah hasil."""
    global _is_scanning, _signals_cache
    _is_scanning = True
    try:
        wib_tz = timezone(timedelta(hours=7))
        ts = datetime.now(wib_tz).strftime('%H:%M:%S WIB')
        print(f"\n[AUTO-REFRESH] Mulai scan otomatis @ {ts} ...")

        tickers = get_lq45()[:BACKGROUND_SCAN_LIMIT]
        results = []
        for ticker in tickers:
            result = analyze_stock(ticker)
            if result and not result.get("skipped") and not result.get("error"):
                results.append(normalize_signal_item(result))

                # Update cache inkremental — dashboard langsung bisa lihat hasil
                sorted_so_far = sort_signals(list(results))
                with _cache_lock:
                    _signals_cache = sorted_so_far
                print(f"  [CACHE] {len(results)} saham tersedia di dashboard ({ticker} selesai)")

        if results:
            results = sort_signals(results)

            # Final update cache
            with _cache_lock:
                _signals_cache = results

            # Atomic write: tulis ke file temp dulu baru rename
            tmp_file = SIGNALS_FILE + ".tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=4, ensure_ascii=False)
            os.replace(tmp_file, SIGNALS_FILE)   # atomic di OS level

            print(f"[AUTO-REFRESH] Selesai. {len(results)} sinyal tersimpan.")
        else:
            print("[AUTO-REFRESH] Scan kosong. Cache & sinyal lama dipertahankan.")

        return len(results)
    except Exception as exc:
        print(f"[AUTO-REFRESH] Error: {exc}")
        return 0
    finally:
        _is_scanning = False


def _background_refresh_worker():
    """
    Thread daemon: scan saham secara berkala.
    - Jika signals.json kosong/tidak ada → langsung scan tanpa menunggu.
    - Setelah ada data → tunggu BACKGROUND_REFRESH_INTERVAL sebelum scan berikutnya.
    """
    global _signals_cache

    # Load cache dari file yang sudah ada saat startup
    if os.path.exists(SIGNALS_FILE):
        try:
            with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if existing:
                with _cache_lock:
                    _signals_cache = sort_signals([normalize_signal_item(i) for i in existing])
                print(f"[AUTO-REFRESH] Cache diisi dari file: {len(_signals_cache)} sinyal.")
        except Exception:
            pass

    # Cek apakah perlu scan segera
    with _cache_lock:
        has_data = bool(_signals_cache)

    if not has_data:
        print("[AUTO-REFRESH] Tidak ada data — scan pertama dimulai segera...")
        _do_scan()
    else:
        print(f"[AUTO-REFRESH] Ada {len(_signals_cache)} sinyal di cache. Scan berikutnya dalam {BACKGROUND_REFRESH_INTERVAL}s.")

    while True:
        time.sleep(BACKGROUND_REFRESH_INTERVAL)
        _do_scan()


# Jalankan thread background saat modul di-load (daemon → otomatis mati saat server stop)
_bg_refresh_thread = threading.Thread(target=_background_refresh_worker, daemon=True, name="bg-refresh")
_bg_refresh_thread.start()


# ============================================================
# ENDPOINT FLASK
# ============================================================

@app.route("/signals", methods=["GET"])
def get_signals():
    """
    GET /signals
    Baca hasil analisis dari signals.json yang ditulis oleh main.py.
    Jauh lebih cepat daripada re-analisis, dan data konsisten dengan Telegram.

    Response JSON:
    {
        "status":      "success" | "empty" | "error",
        "timestamp":   "2026-04-16T15:00:00+07:00",
        "total":       50,
        "signals":     [ ... ]
    }
    """
    global _signals_cache
    wib_tz = timezone(timedelta(hours=7))
    timestamp = datetime.now(wib_tz).isoformat()
    market_open = _is_market_open()

    # Prioritas 1: in-memory cache (paling cepat, tidak terpengaruh race condition file)
    with _cache_lock:
        cached = list(_signals_cache)

    if cached:
        return jsonify({
            "status":      "success",
            "timestamp":   timestamp,
            "market_open": market_open,
            "scanning":    _is_scanning,
            "source":      "cache",
            "total":       len(cached),
            "signals":     cached,
        })

    # Prioritas 2: baca dari signals.json (fallback saat server baru restart)
    has_file = os.path.exists(SIGNALS_FILE)
    raw_signals = []

    if has_file:
        try:
            with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
                raw_signals = json.load(f)
        except Exception:
            raw_signals = []   # file mungkin sedang ditulis / corrupt

    results = sort_signals([normalize_signal_item(item) for item in raw_signals])

    if results:
        # Isi cache dari file agar request berikutnya langsung dari cache
        with _cache_lock:
            _signals_cache = results
        return jsonify({
            "status":      "success",
            "timestamp":   timestamp,
            "market_open": market_open,
            "scanning":    _is_scanning,
            "source":      "file",
            "total":       len(results),
            "signals":     results,
        })

    # Tidak ada data sama sekali
    return jsonify({
        "status":      "scanning" if _is_scanning else "empty",
        "timestamp":   timestamp,
        "market_open": market_open,
        "scanning":    _is_scanning,
        "message":     (
            "Sedang melakukan scan saham, mohon tunggu beberapa menit..."
            if _is_scanning else
            "Belum ada data. Pastikan koneksi internet aktif dan coba restart app.py."
        ),
        "total":       0,
        "signals":     []
    })


@app.route("/performance", methods=["GET"])
def get_performance():
    """
    GET /performance
    Hitung performa trading dari trades.csv.

    Response JSON:
    {
        "total_trade": 10,
        "winrate": 60.0,
        "total_profit": 5.3
    }
    """
    if not os.path.exists(TRADES_CSV):
        return jsonify({"total_trade": 0, "winrate": 0.0, "total_profit": 0.0})

    try:
        total = 0
        wins  = 0
        total_profit = 0.0

        with open(TRADES_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total += 1
                try:
                    pct = float(row.get("profit_pct", 0) or 0)
                except (ValueError, TypeError):
                    pct = 0.0
                total_profit += pct
                if pct > 0:
                    wins += 1

        winrate = round((wins / total) * 100, 1) if total > 0 else 0.0

        return jsonify({
            "total_trade":  total,
            "winrate":      winrate,
            "total_profit": round(total_profit, 2),
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
def index():
    """Sajikan dashboard HTML dari root directory."""
    return send_from_directory(".", "index.html")


@app.route("/analysis/<ticker>", methods=["GET"])
def analysis_page(ticker):
    """Sajikan halaman analisa lengkap untuk satu saham."""
    return send_from_directory(".", "analysis.html")


@app.route("/api/stock/<ticker>", methods=["GET"])
def get_stock_detail(ticker):
    """
    GET /api/stock/<TICKER>
    Kembalikan data analisa lengkap satu saham dari cache.
    """
    ticker = ticker.upper().split(".")[0]

    with _cache_lock:
        cached = list(_signals_cache)

    # Cari di cache
    for s in cached:
        if (s.get("ticker") or "").upper().split(".")[0] == ticker:
            return jsonify({"status": "success", "data": s})

    # Fallback: cari di file
    if os.path.exists(SIGNALS_FILE):
        try:
            with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for item in raw:
                normalized = normalize_signal_item(item)
                if (normalized.get("ticker") or "").upper().split(".")[0] == ticker:
                    return jsonify({"status": "success", "data": normalized})
        except Exception:
            pass

    return jsonify({"status": "not_found", "message": f"Data untuk {ticker} tidak ditemukan."}), 404


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("   STOCK ANALYZER - FLASK API SERVER")
    print("=" * 55)
    print("  Dashboard: http://localhost:5000")
    print("  Endpoint : http://localhost:5000/signals")
    print("=" * 55 + "\n")

    # CATATAN: use_reloader=False wajib diset karena proyek ini memiliki file
    # 'signal.py' yang menimpa (shadowing) modul bawaan Python 'signal'.
    # Werkzeug reloader membutuhkan signal.signal(SIGTERM), yang akan gagal
    # jika modul 'signal' yang dimuat adalah file lokal kita.
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        use_reloader=False
    )
