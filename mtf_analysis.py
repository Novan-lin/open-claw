"""
mtf_analysis.py - Multi-Timeframe Analysis

Menganalisis saham di 3 timeframe (Weekly, Daily, 4H/1H) untuk mendapatkan
confluence. Prinsip MTF:
  - Higher TF menentukan ARAH (trend bias)
  - Lower TF menentukan TIMING (entry)
  - Jika semua TF setuju = sinyal kuat (confluence)
  - Jika TF bertentangan = waspada / hold

Timeframes:
  - Weekly (1wk)  : Trend utama — menentukan bias besar
  - Daily  (1d)   : Trend menengah — konfirmasi arah
  - Intraday (1h) : Momentum — timing entry/exit
"""

import math
import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator


# ─── CONFIG ───
TF_CONFIG = {
    "weekly":   {"period": "1y",  "interval": "1wk", "label": "Weekly"},
    "daily":    {"period": "4mo", "interval": "1d",   "label": "Daily"},
    "intraday": {"period": "1mo", "interval": "1h",   "label": "1 Hour"},
}

RSI_PERIOD = 14
MA_SHORT   = 20
MA_LONG    = 50


def _safe_val(v):
    """Return None jika NaN, else round ke 2 desimal."""
    if v is None:
        return None
    try:
        f = float(v)
        return None if not math.isfinite(f) else round(f, 2)
    except (TypeError, ValueError):
        return None


def _fetch_tf_data(ticker: str, period: str, interval: str) -> pd.DataFrame | None:
    """Ambil data yfinance untuk 1 timeframe."""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        if df is None or df.empty:
            return None
        df = df.dropna(subset=["Close"])
        return df if not df.empty else None
    except Exception:
        return None


def _analyze_single_tf(df: pd.DataFrame) -> dict:
    """
    Analisa teknikal untuk 1 timeframe.
    Return dict: rsi, ma20, ma50, close, trend, rsi_signal, ma_signal, bias
    """
    if df is None or len(df) < MA_SHORT:
        return {"status": "insufficient_data"}

    dfc = df.copy()

    # RSI
    rsi_ind = RSIIndicator(close=dfc["Close"], window=RSI_PERIOD)
    dfc["RSI"] = rsi_ind.rsi()

    # SMA
    dfc["MA20"] = SMAIndicator(close=dfc["Close"], window=MA_SHORT).sma_indicator()

    if len(dfc) >= MA_LONG:
        dfc["MA50"] = SMAIndicator(close=dfc["Close"], window=MA_LONG).sma_indicator()
    else:
        dfc["MA50"] = float("nan")

    latest = dfc.iloc[-1]
    rsi   = latest["RSI"]
    ma20  = latest["MA20"]
    ma50  = latest["MA50"] if "MA50" in latest.index else None
    close = latest["Close"]

    # RSI interpretation
    if pd.notna(rsi):
        if rsi > 70:
            rsi_signal = "OVERBOUGHT"
        elif rsi < 30:
            rsi_signal = "OVERSOLD"
        elif rsi > 55:
            rsi_signal = "BULLISH"
        elif rsi < 45:
            rsi_signal = "BEARISH"
        else:
            rsi_signal = "NEUTRAL"
    else:
        rsi_signal = "N/A"

    # MA trend
    ma_signal = "N/A"
    if pd.notna(ma20) and pd.notna(ma50):
        if ma20 > ma50:
            ma_signal = "BULLISH"
        elif ma20 < ma50:
            ma_signal = "BEARISH"
        else:
            ma_signal = "NEUTRAL"
    elif pd.notna(ma20):
        # Hanya MA20 tersedia — bandingkan harga vs MA20
        ma_signal = "BULLISH" if close > ma20 else "BEARISH"

    # Price vs MAs
    price_vs_ma20 = "ABOVE" if (pd.notna(ma20) and close > ma20) else ("BELOW" if pd.notna(ma20) else "N/A")

    # Overall bias
    bullish_pts = 0
    bearish_pts = 0

    if rsi_signal in ("OVERSOLD", "BULLISH"):
        bullish_pts += 1
    elif rsi_signal in ("OVERBOUGHT", "BEARISH"):
        bearish_pts += 1

    if ma_signal == "BULLISH":
        bullish_pts += 1
    elif ma_signal == "BEARISH":
        bearish_pts += 1

    if price_vs_ma20 == "ABOVE":
        bullish_pts += 1
    elif price_vs_ma20 == "BELOW":
        bearish_pts += 1

    if bullish_pts > bearish_pts:
        bias = "BULLISH"
    elif bearish_pts > bullish_pts:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    return {
        "status":        "ok",
        "close":         _safe_val(close),
        "rsi":           _safe_val(rsi),
        "ma20":          _safe_val(ma20),
        "ma50":          _safe_val(ma50),
        "rsi_signal":    rsi_signal,
        "ma_signal":     ma_signal,
        "price_vs_ma20": price_vs_ma20,
        "bias":          bias,
    }


def analyze_multi_timeframe(ticker: str) -> dict:
    """
    Jalankan analisis multi-timeframe (Weekly + Daily + 1H).

    Returns
    -------
    dict
        {
            "weekly":  { ... tf analysis ... },
            "daily":   { ... tf analysis ... },
            "intraday": { ... tf analysis ... },
            "confluence": "STRONG_BUY" | "BUY" | "NEUTRAL" | "SELL" | "STRONG_SELL" | "CONFLICT",
            "confluence_score": int (-3 to +3),
            "summary": str,
        }
    """
    results = {}
    for tf_key, cfg in TF_CONFIG.items():
        df = _fetch_tf_data(ticker, cfg["period"], cfg["interval"])
        analysis = _analyze_single_tf(df)
        analysis["label"] = cfg["label"]
        results[tf_key] = analysis

    # ─── Confluence scoring ───
    # Higher TF punya bobot lebih besar
    weights = {"weekly": 3, "daily": 2, "intraday": 1}
    score = 0
    valid_count = 0

    for tf_key, weight in weights.items():
        tf = results[tf_key]
        if tf.get("status") != "ok":
            continue
        valid_count += 1
        bias = tf["bias"]
        if bias == "BULLISH":
            score += weight
        elif bias == "BEARISH":
            score -= weight

    # Tentukan confluence
    # Max score = +6 (semua bullish), min = -6 (semua bearish)
    if valid_count == 0:
        confluence = "NO_DATA"
        summary = "Data tidak cukup untuk analisa multi-timeframe."
    else:
        # Cek apakah ada konflik arah
        biases = [results[k]["bias"] for k in weights if results[k].get("status") == "ok"]
        has_bull = "BULLISH" in biases
        has_bear = "BEARISH" in biases

        if score >= 5:
            confluence = "STRONG_BUY"
            summary = "Semua timeframe menunjukkan trend BULLISH kuat. Confluence tinggi untuk entry."
        elif score >= 3:
            confluence = "BUY"
            summary = "Mayoritas timeframe bullish. Sinyal cukup kuat, tapi perhatikan timeframe yang belum align."
        elif score <= -5:
            confluence = "STRONG_SELL"
            summary = "Semua timeframe menunjukkan trend BEARISH kuat. Hindari entry buy."
        elif score <= -3:
            confluence = "SELL"
            summary = "Mayoritas timeframe bearish. Waspada terhadap tekanan jual."
        elif has_bull and has_bear:
            confluence = "CONFLICT"
            # Cari detail konflik
            w_bias = results["weekly"].get("bias", "N/A") if results["weekly"].get("status") == "ok" else "N/A"
            d_bias = results["daily"].get("bias", "N/A") if results["daily"].get("status") == "ok" else "N/A"
            summary = f"KONFLIK antar timeframe! Weekly={w_bias}, Daily={d_bias}. Tunggu alignment sebelum entry."
        else:
            confluence = "NEUTRAL"
            summary = "Timeframe menunjukkan kondisi netral. Belum ada sinyal kuat untuk entry."

    return {
        "weekly":           results.get("weekly", {}),
        "daily":            results.get("daily", {}),
        "intraday":         results.get("intraday", {}),
        "confluence":       confluence,
        "confluence_score": score,
        "summary":          summary,
    }


if __name__ == "__main__":
    import json

    print("=" * 60)
    print("MULTI-TIMEFRAME ANALYSIS")
    print("=" * 60)

    ticker = "BBCA.JK"
    result = analyze_multi_timeframe(ticker)

    print(f"\nTicker: {ticker}")
    for tf in ["weekly", "daily", "intraday"]:
        r = result[tf]
        if r.get("status") != "ok":
            print(f"  [{TF_CONFIG[tf]['label']:>8}] Data tidak cukup")
            continue
        print(f"  [{TF_CONFIG[tf]['label']:>8}] "
              f"Close={r['close']}  RSI={r['rsi']} ({r['rsi_signal']})  "
              f"MA={r['ma_signal']}  Bias={r['bias']}")

    print(f"\nConfluence : {result['confluence']} (skor: {result['confluence_score']})")
    print(f"Summary    : {result['summary']}")
