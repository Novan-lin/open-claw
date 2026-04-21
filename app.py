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
from scoring import calculate_score, smart_trade_decision
from strategies import multi_strategy_confirmation
from volume_analysis import analyze_volume
from gap_detector import detect_gap
from stock_filter import is_stock_eligible
from stock_list import get_lq45
from entry_plan import generate_trade_plan, validate_rrr
from risk_management import calculate_position_size
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
HISTORY_DIR  = "history"            # folder penyimpanan history harian
DEFAULT_DASHBOARD_LIMIT = 5
CACHE_RELOAD_INTERVAL       = 30    # detik — reload cache dari disk tiap 30 detik
BACKGROUND_SCAN_LIMIT       = 20    # jumlah saham yang di-scan saat /rescan
FULL_RESCAN_COOLDOWN        = 28800 # detik (8 jam) — cooldown untuk rescan manual

# In-memory cache — agar data TIDAK hilang meskipun file write sedang berjalan
_signals_cache: list = []           # hasil scan terakhir yang berhasil
_cache_lock = threading.Lock()      # lock untuk thread-safe read/write cache

# Pastikan folder history ada
os.makedirs(HISTORY_DIR, exist_ok=True)

# ============================================================
# FUNGSI HELPER
# ============================================================

def _is_market_open() -> bool:
    """Selalu return True — dashboard & scan aktif 24/7 tanpa batasan jam bursa."""
    return True


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

    raw_score = item.get("score", 0) or 0
    capped_score = max(-10, min(10, int(raw_score)))

    return {
        "ticker":      item.get("ticker"),
        "harga":       safe_float(harga, 2),
        "signal":      item.get("signal", "HOLD"),
        "score":       capped_score,
        "multi_confirmation": item.get("multi_confirmation", "N/A"),
        "smart_money": item.get("smart_money", False),
        "gap_up":      item.get("gap_up", False),
        "entry":       safe_float(item.get("entry"), 2),
        "tp":          safe_float(item.get("tp"), 2),
        "sl":          safe_float(item.get("sl"), 2),
        "lot":         item.get("lot"),
        "risk_amount": safe_float(item.get("risk_amount"), 2),
        "ai_analysis": item.get("ai") or item.get("ai_analysis", "-"),
        "scanned_at":  item.get("scanned_at", ""),
        "rrr":         item.get("rrr"),
        "_meta":       item.get("_meta", {}),
    }


def _get_signal_age(ticker: str) -> float | None:
    """Kembalikan umur data (detik) untuk ticker tertentu, atau None jika belum ada."""
    with _cache_lock:
        cached = list(_signals_cache)
    for s in cached:
        if (s.get("ticker") or "").upper() == ticker.upper().split(".")[0]:
            scanned_at = s.get("scanned_at", "")
            if not scanned_at:
                return None
            try:
                wib_tz = timezone(timedelta(hours=7))
                ts = datetime.fromisoformat(scanned_at)
                return (datetime.now(wib_tz) - ts).total_seconds()
            except Exception:
                return None
    return None


# ============================================================
# HISTORY MANAGEMENT
# ============================================================

def _history_filename() -> str:
    """Nama file history berdasarkan tanggal WIB hari ini."""
    wib_tz = timezone(timedelta(hours=7))
    today = datetime.now(wib_tz).strftime("%Y-%m-%d")
    return os.path.join(HISTORY_DIR, f"signals_{today}.json")


def save_history(signals: list[dict]):
    """Simpan hasil scan ke file history harian (merge dengan data sebelumnya hari ini)."""
    hist_file = _history_filename()
    wib_tz = timezone(timedelta(hours=7))
    ts = datetime.now(wib_tz).isoformat()

    existing = []
    if os.path.exists(hist_file):
        try:
            with open(hist_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                existing = data.get("signals", []) if isinstance(data, dict) else data
        except Exception:
            # File rusak — backup dulu sebelum lanjut
            backup = hist_file + ".bak"
            try:
                import shutil
                shutil.copy2(hist_file, backup)
                print(f"[HISTORY] File rusak, backup disimpan: {backup}")
            except Exception:
                pass
            existing = []

    # Merge: data baru menimpa ticker yang sama HANYA jika data baru valid
    merged = {s.get("ticker"): s for s in existing}
    for s in signals:
        tk = s.get("ticker")
        if not tk:
            continue
        old = merged.get(tk)
        if old and not _is_valid_result(s) and _is_valid_result(old):
            # Data baru null tapi data lama valid → pertahankan data lama
            continue
        merged[tk] = s
    merged_list = list(merged.values())

    history_data = {
        "date": datetime.now(wib_tz).strftime("%Y-%m-%d"),
        "last_updated": ts,
        "total": len(merged_list),
        "signals": merged_list,
    }

    tmp = hist_file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(history_data, f, indent=4, ensure_ascii=False)
    os.replace(tmp, hist_file)
    print(f"[HISTORY] Tersimpan: {len(merged_list)} sinyal → {hist_file}")


def load_latest_history() -> list[dict]:
    """Muat history terbaru yang memiliki data VALID (bukan null semua)."""
    if not os.path.isdir(HISTORY_DIR):
        return []
    files = sorted(
        [f for f in os.listdir(HISTORY_DIR) if f.startswith("signals_") and f.endswith(".json")],
        reverse=True,
    )
    for fname in files:
        fpath = os.path.join(HISTORY_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            signals = data.get("signals", []) if isinstance(data, dict) else data
            if not signals:
                continue
            normalized = [normalize_signal_item(s) for s in signals]
            valid_count = sum(1 for s in normalized if _is_valid_result(s))
            if valid_count == 0:
                date_label = data.get("date", fname) if isinstance(data, dict) else fname
                print(f"[HISTORY] Skip {date_label}: {len(signals)} sinyal tapi 0 valid (semua null).")
                continue
            date_label = data.get("date", fname) if isinstance(data, dict) else fname
            print(f"[HISTORY] Dimuat {len(normalized)} sinyal dari history {date_label} ({valid_count} valid)")
            return normalized
        except Exception:
            continue
    return []


def merge_with_history(new_signals: list[dict]) -> list[dict]:
    """Gabungkan sinyal baru dengan history terakhir (data baru menang jika ticker sama)."""
    history = load_latest_history()
    if not history:
        return new_signals
    merged = {s.get("ticker"): s for s in history}
    for s in new_signals:
        merged[s.get("ticker")] = s
    return list(merged.values())


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
        atr   = indicators.get("atr")
        support_20    = indicators.get("support_20")
        resistance_20 = indicators.get("resistance_20")

        # 3. Deteksi volume & Smart Money
        volume_spike, avg_volume, current_volume, smart_money, volume_label, sm_confidence, sm_alasan = analyze_volume(df)

        # 4. Deteksi potensi Gap Up
        price_today     = df["Close"].iloc[-1]
        price_yesterday = df["Close"].iloc[-2] if len(df) > 1 else price_today
        gap_up, confidence = detect_gap(rsi, ma20, ma50, price_today, price_yesterday, smart_money)

        # 5. Multi-strategy confirmation (raw votes) + scoring sebagai Signal Engine
        try:
            mc = multi_strategy_confirmation(
                df,
                smart_money=smart_money,
                gap_up=gap_up,
                gap_confidence=confidence,
            )
        except Exception:
            mc = None

        # RRR validation sebelum scoring
        rrr_data = validate_rrr(float(harga), support_20, resistance_20)

        signal_status, score, alasan_skoring = calculate_score(
            rsi, ma20, ma50, harga,
            volume_label=volume_label,
            mc_data=mc,
            mode="STRICT",
            atr=atr,
            rrr_data=rrr_data,
            macd_hist=indicators.get('macd_hist'),
        )

        entry = None
        tp = None
        sl = None
        lot = None
        risk_amount = None

        gate_result = None
        if signal_status == "BUY":
            high = float(df["High"].iloc[-1])
            low = float(df["Low"].iloc[-1])
            price = float(harga)
            entry, tp, sl = generate_trade_plan(price, high, low, mode="range", atr=atr)

            # ── FINAL GATE: cek RRR, volume, entry zone ──
            gate_result = smart_trade_decision(
                signal=signal_status,
                rrr_data=rrr_data,
                smart_money=smart_money,
                volume_label=volume_label,
                entry=entry,
                tp=tp,
                sl=sl,
            )

            if gate_result["decision"] == "EXECUTE":
                position = calculate_position_size(
                    capital=10_000_000,
                    risk_percent=1,
                    entry=entry,
                    stop_loss=sl,
                )
                if position is not None:
                    lot, risk_amount = position
            else:
                # Gate menolak — override sinyal ke HOLD
                alasan_skoring.extend(gate_result["alasan"])
                signal_status = "HOLD"
                entry = tp = sl = None

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
            "multi_confirmation": f"BUY:{mc['total_buy_votes']} SELL:{mc['total_sell_votes']}" if mc else "N/A",
            "smart_money": smart_money,
            "gap_up":      gap_up,
            "entry":       safe_float(entry, 2),
            "tp":          safe_float(tp, 2),
            "sl":          safe_float(sl, 2),
            "lot":         lot,
            "risk_amount": safe_float(risk_amount, 2),
            "ai_analysis": ai_analysis,
            "rrr":   rrr_data,
            "gate":  gate_result,
            "_meta": {
                "rsi":              safe_float(rsi, 2),
                "ma20":             safe_float(ma20, 2),
                "ma50":             safe_float(ma50, 2),
                "atr":              safe_float(atr, 2),
                "support_20":       safe_float(support_20, 2),
                "resistance_20":    safe_float(resistance_20, 2),
                "gap_confidence":   confidence,
                "volume_label":     volume_label,
                "sm_confidence":    round(sm_confidence, 2),
                "sm_alasan":        sm_alasan,
                "alasan":           alasan_skoring,
                "mtf":              mtf,
                "macd":             safe_float(indicators.get('macd'), 4),
                "macd_hist":        safe_float(indicators.get('macd_hist'), 4),
                "macd_signal_line": safe_float(indicators.get('macd_signal'), 4),
                "strategy_details": mc.get('details') if mc else None,
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


def _reload_signals_from_disk():
    """Reload signals.json dari disk ke cache (menangkap update dari main.py)."""
    global _signals_cache
    if not os.path.exists(SIGNALS_FILE):
        return
    try:
        with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
            disk_data = json.load(f)
        if disk_data:
            normalized = sort_signals([normalize_signal_item(i) for i in disk_data])
            with _cache_lock:
                # Merge: data dari disk + data di cache (disk menang jika ticker sama & lebih baru)
                merged = {s.get("ticker"): s for s in _signals_cache}
                for s in normalized:
                    tk = s.get("ticker")
                    if tk:
                        existing = merged.get(tk)
                        # Data dari disk menang jika lebih baru atau belum ada di cache
                        if not existing:
                            merged[tk] = s
                        else:
                            disk_ts = s.get("scanned_at", "")
                            cache_ts = existing.get("scanned_at", "")
                            if disk_ts >= cache_ts:
                                merged[tk] = s
                _signals_cache = sort_signals(list(merged.values()))
            print(f"[RELOAD] Cache di-refresh dari disk: {len(_signals_cache)} sinyal.")
    except Exception as e:
        print(f"[RELOAD] Gagal baca signals.json: {e}")


def _background_cache_worker():
    """
    Thread daemon: reload cache dari disk secara berkala.
    TIDAK melakukan scan sendiri — scanning dilakukan oleh main.py.
    Tugas thread ini hanya memastikan cache selalu sinkron dengan signals.json.
    """
    global _signals_cache

    # Load cache dari file yang sudah ada saat startup
    if os.path.exists(SIGNALS_FILE):
        try:
            with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if existing:
                normalized = sort_signals([normalize_signal_item(i) for i in existing])
                valid_count = _count_valid(normalized)
                with _cache_lock:
                    _signals_cache = normalized
                print(f"[CACHE] Startup: {len(normalized)} sinyal dimuat dari signals.json ({valid_count} valid).")
        except Exception:
            pass

    # Jika signals.json kosong/tidak ada ATAU data kebanyakan null → muat dari history
    with _cache_lock:
        has_valid_data = _count_valid(_signals_cache) > 0

    if not has_valid_data:
        print("[CACHE] Data di signals.json kosong/null. Mencari history yang valid...")
        history_signals = load_latest_history()
        if history_signals and _count_valid(history_signals) > 0:
            history_signals = sort_signals(history_signals)
            with _cache_lock:
                _signals_cache = history_signals
            try:
                with open(SIGNALS_FILE, "w", encoding="utf-8") as f:
                    json.dump(history_signals, f, indent=4, ensure_ascii=False)
            except Exception:
                pass
            print(f"[CACHE] Startup: {len(history_signals)} sinyal dimuat dari history.")

    with _cache_lock:
        has_data = bool(_signals_cache)
    if has_data:
        print(f"[CACHE] Dashboard siap. Reload otomatis tiap {CACHE_RELOAD_INTERVAL}s dari disk.")
    else:
        print("[CACHE] Belum ada data. Jalankan main.py untuk scan saham, atau gunakan /rescan.")

    # Loop: hanya reload dari disk, tidak scan
    while True:
        time.sleep(CACHE_RELOAD_INTERVAL)
        _reload_signals_from_disk()


# Jalankan thread cache-reload saat modul di-load (daemon → otomatis mati saat server stop)
_bg_cache_thread = threading.Thread(target=_background_cache_worker, daemon=True, name="bg-cache")
_bg_cache_thread.start()


# ============================================================
# ENDPOINT FLASK
# ============================================================

def _is_valid_result(item: dict) -> bool:
    """Cek apakah hasil scan punya data esensial (bukan null semua)."""
    harga = item.get("harga") or item.get("price")
    meta = item.get("_meta") or {}
    rsi = meta.get("rsi") or item.get("rsi")
    if harga is None and rsi is None:
        return False
    return True


def _count_valid(signals: list) -> int:
    """Hitung berapa sinyal yang punya data valid (harga/RSI tidak null)."""
    return sum(1 for s in signals if _is_valid_result(s))


@app.route("/rescan", methods=["POST"])
def force_rescan():
    """
    POST /rescan
    Paksa scan ulang semua saham tanpa cooldown.
    Merge hasil dengan data yang sudah ada (tidak menghapus data lama).
    Berguna saat ada perubahan kode (misal: penambahan field baru di _meta).
    """
    global _is_scanning, _signals_cache
    if _is_scanning:
        return jsonify({"status": "busy", "message": "Scan sedang berjalan, tunggu selesai."}), 409

    def _rescan_worker():
        global _is_scanning, _signals_cache
        _is_scanning = True
        try:
            wib_tz = timezone(timedelta(hours=7))
            wib_now = datetime.now(wib_tz).isoformat()
            tickers = get_lq45()[:BACKGROUND_SCAN_LIMIT]
            results = []
            for ticker in tickers:
                result = analyze_stock(ticker)
                if result and not result.get("skipped") and not result.get("error"):
                    item = normalize_signal_item(result)
                    item["scanned_at"] = wib_now
                    results.append(item)
                    print(f"  [RESCAN] {item.get('ticker')} selesai ({len(results)}/{len(tickers)})")
            if results:
                # Merge dengan data existing (jangan hapus saham lain)
                existing = []
                if os.path.exists(SIGNALS_FILE):
                    try:
                        with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
                            existing = json.load(f)
                    except Exception:
                        existing = []
                merged = {s.get("ticker"): s for s in existing}
                for s in results:
                    tk = s.get("ticker")
                    old = merged.get(tk)
                    # Jangan timpa data lama yang valid dengan data baru yang null
                    if old and not _is_valid_result(s) and _is_valid_result(old):
                        print(f"  [PROTECT] {tk}: data baru null, data lama dipertahankan.")
                        continue
                    merged[tk] = s
                all_data = sort_signals([normalize_signal_item(s) for s in merged.values()])

                with _cache_lock:
                    _signals_cache = all_data
                tmp_file = SIGNALS_FILE + ".tmp"
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(all_data, f, indent=4, ensure_ascii=False)
                os.replace(tmp_file, SIGNALS_FILE)
                save_history(all_data)
                print(f"[RESCAN] Selesai. {len(all_data)} sinyal tersimpan ({len(results)} di-rescan).")
        finally:
            _is_scanning = False

    threading.Thread(target=_rescan_worker, daemon=True, name="force-rescan").start()
    return jsonify({"status": "started", "message": "Rescan dimulai. Refresh dashboard dalam beberapa menit."})


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

    # Selalu reload dari disk terlebih dahulu agar update dari main.py tertangkap
    _reload_signals_from_disk()

    # Prioritas 1: in-memory cache (sudah di-refresh dari disk di atas)
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

    # Prioritas 3: baca dari history harian terakhir
    history_results = load_latest_history()
    if history_results:
        history_sorted = sort_signals(history_results)
        with _cache_lock:
            _signals_cache = history_sorted
        return jsonify({
            "status":      "success",
            "timestamp":   timestamp,
            "market_open": market_open,
            "scanning":    _is_scanning,
            "source":      "history",
            "total":       len(history_sorted),
            "signals":     history_sorted,
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


@app.route("/history", methods=["GET"])
def get_history_list():
    """
    GET /history
    Daftar file history yang tersedia, urut dari terbaru.
    Query params: ?limit=10 (default 30)
    """
    limit = request.args.get("limit", 30, type=int)
    if not os.path.isdir(HISTORY_DIR):
        return jsonify({"status": "empty", "dates": []})
    files = sorted(
        [f for f in os.listdir(HISTORY_DIR) if f.startswith("signals_") and f.endswith(".json")],
        reverse=True,
    )[:limit]
    dates = []
    for fname in files:
        fpath = os.path.join(HISTORY_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            dates.append({
                "date": data.get("date", fname.replace("signals_", "").replace(".json", "")),
                "last_updated": data.get("last_updated", ""),
                "total": data.get("total", 0),
                "file": fname,
            })
        except Exception:
            dates.append({"date": fname.replace("signals_", "").replace(".json", ""), "file": fname, "total": 0})
    return jsonify({"status": "success", "total": len(dates), "dates": dates})


@app.route("/history/<date>", methods=["GET"])
def get_history_detail(date):
    """
    GET /history/2026-04-17
    Data sinyal history untuk tanggal tertentu.
    """
    # Sanitize: hanya izinkan format tanggal YYYY-MM-DD
    import re
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        return jsonify({"status": "error", "message": "Format tanggal tidak valid (YYYY-MM-DD)"}), 400
    fname = f"signals_{date}.json"
    fpath = os.path.join(HISTORY_DIR, fname)
    if not os.path.exists(fpath):
        return jsonify({"status": "not_found", "message": f"History {date} tidak ditemukan."}), 404
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        signals = data.get("signals", []) if isinstance(data, dict) else data
        signals = sort_signals([normalize_signal_item(s) for s in signals])
        return jsonify({
            "status": "success",
            "date": data.get("date", date) if isinstance(data, dict) else date,
            "last_updated": data.get("last_updated", "") if isinstance(data, dict) else "",
            "total": len(signals),
            "signals": signals,
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/performance", methods=["GET"])
def get_performance():
    """
    GET /performance
    Hitung performa trading dari trades.csv.
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
    Reload dari disk dulu agar update dari main.py tertangkap.
    """
    ticker = ticker.upper().split(".")[0]

    # Reload dari disk agar data terbaru dari main.py tertangkap
    _reload_signals_from_disk()

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
