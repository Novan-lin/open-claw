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
import importlib.util
from datetime import datetime, timezone, timedelta

from flask import Flask, jsonify, send_from_directory

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
from tuner import load_best_params

# Muat signal.py secara dinamis (menghindari konflik dengan modul bawaan Python)
spec = importlib.util.spec_from_file_location("local_signal", "signal.py")
local_signal = importlib.util.module_from_spec(spec)
sys.modules["local_signal"] = local_signal
spec.loader.exec_module(local_signal)
generate_signal = local_signal.generate_signal

# Muat parameter terbaik (fallback ke RSI=14, MA 20/50 jika file belum ada)
_BEST_PARAMS = load_best_params()

# ============================================================
# INISIALISASI FLASK
# ============================================================
app = Flask(__name__)

SIGNALS_FILE = "signals.json"
TRADES_CSV   = "trades.csv"
DEFAULT_DASHBOARD_LIMIT = 5

# ============================================================
# FUNGSI HELPER
# ============================================================

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

        if signal_status == "BUY" and smart_money:
            high = float(df["High"].iloc[-1])
            low = float(df["Low"].iloc[-1])
            price = float(harga)
            entry, tp, sl = generate_trade_plan(price, high, low, mode="range")

        # 7. Minta analisis AI (Ollama - Mistral)
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
            },
        }

    except Exception as e:
        return {
            "ticker": clean_ticker,
            "error":  str(e),
        }


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
    wib_tz = timezone(timedelta(hours=7))
    timestamp = datetime.now(wib_tz).isoformat()

    # Coba baca signals.json yang ditulis main.py
    if os.path.exists(SIGNALS_FILE):
        try:
            with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)

            results = sort_signals([normalize_signal_item(item) for item in raw])
            if not results:
                results = analyze_dashboard_signals()

            return jsonify({
                "status":    "success",
                "timestamp": timestamp,
                "total":     len(results),
                "signals":   results,
            })

        except Exception as e:
            return jsonify({
                "status":  "error",
                "message": f"Gagal membaca signals.json: {str(e)}",
                "signals": []
            }), 500

    # signals.json belum ada -> generate analisa langsung dari Flask.
    results = analyze_dashboard_signals()
    if results:
        return jsonify({
            "status":    "success",
            "source":    "flask-live-analysis",
            "timestamp": timestamp,
            "total":     len(results),
            "signals":   results,
        })

    return jsonify({
        "status":    "empty",
        "timestamp": timestamp,
        "message":   "Belum ada analisa yang berhasil dibuat. Cek koneksi internet, Yahoo Finance, dan Ollama.",
        "total":     0,
        "signals":   []
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
