"""
strategies.py — Kumpulan Strategi Trading Teknikal
====================================================
Berisi empat strategi siap pakai:
    1. rsi_strategy        — RSI Reversal (oversold/overbought + konfirmasi arah)
    2. bollinger_strategy  — Bollinger Bands squeeze & price touch
    3. rsi_ma_strategy     — Kombinasi RSI + Moving Average (konfirmasi ganda)
    4. macd_strategy       — MACD Histogram Momentum

Setiap fungsi:
    Input  : DataFrame pandas dengan kolom OHLCV standar (Open, High, Low, Close, Volume)
    Output : tuple (signal: str, alasan: str)
             signal -> "BUY" | "SELL" | "HOLD"
"""

import math
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator, MACD
from ta.volatility import BollingerBands


# ─────────────────────────────────────────────────────────────
# HELPERS INTERNAL
# ─────────────────────────────────────────────────────────────

def _validate_df(df, min_rows, name):
    if df is None or not isinstance(df, pd.DataFrame):
        raise ValueError(f"[{name}] Input harus berupa pandas DataFrame.")
    if "Close" not in df.columns:
        raise ValueError(f"[{name}] DataFrame harus memiliki kolom 'Close'.")
    if len(df) < min_rows:
        raise ValueError(
            f"[{name}] Data tidak cukup: butuh minimal {min_rows} baris, "
            f"tersedia {len(df)} baris."
        )


def _valid(value):
    if value is None:
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


# ─────────────────────────────────────────────────────────────
# EVALUASI TREN → BATAS RSI DINAMIS
# ─────────────────────────────────────────────────────────────

def _evaluate_trend_rsi_bounds(df, ma_fast=20, ma_slow=50,
                                oversold_uptrend=45.0, oversold_downtrend=30.0,
                                overbought_default=70.0):
    """
    Menentukan batas oversold RSI secara dinamis berdasarkan tren MA.

    - Uptrend  (MA20 > MA50): oversold dinaikkan ke 45 → lebih mudah BUY.
    - Downtrend (MA20 < MA50): oversold tetap 30 → lebih konservatif.

    Returns:
        (oversold, overbought, trend_label)
    """
    close = df["Close"]
    fast = SMAIndicator(close=close, window=ma_fast).sma_indicator()
    slow = SMAIndicator(close=close, window=ma_slow).sma_indicator()

    fast_now = fast.iloc[-1]
    slow_now = slow.iloc[-1]

    if _valid(fast_now) and _valid(slow_now) and fast_now > slow_now:
        return oversold_uptrend, overbought_default, "UPTREND"
    else:
        return oversold_downtrend, overbought_default, "DOWNTREND"


# ─────────────────────────────────────────────────────────────
# 1. RSI REVERSAL STRATEGY  (batas dinamis berdasarkan tren)
# ─────────────────────────────────────────────────────────────

def rsi_strategy(df, period=14, oversold=None, overbought=None):
    """
    Strategi RSI Reversal dengan batas oversold/overbought DINAMIS.

    Batas oversold disesuaikan otomatis berdasarkan tren Moving Average:
        - Uptrend  (MA20 > MA50): oversold = 45 → lebih mudah BUY saat tren naik.
        - Downtrend (MA20 < MA50): oversold = 30 → standar konservatif.

    Jika oversold/overbought diberikan secara eksplisit, evaluasi tren dilewati.

    Logika:
        BUY  - RSI < oversold DAN rsi[-1] > rsi[-2]  (momentum berbalik naik)
        SELL - RSI > overbought DAN rsi[-1] < rsi[-2] (momentum berbalik turun)
        HOLD - RSI di zona netral atau belum ada konfirmasi pembalikan.

    Args:
        df         : DataFrame OHLCV.
        period     : Periode RSI. Default 14.
        oversold   : Batas bawah zona oversold. None = dinamis berdasarkan tren.
        overbought : Batas atas zona overbought. None = dinamis (default 70).

    Returns:
        (signal, alasan)
    """
    _validate_df(df, min_rows=max(period, 50) + 2, name="RSI Reversal")

    # ── Tentukan batas RSI dinamis berdasarkan tren ───────────
    if oversold is None or overbought is None:
        dyn_oversold, dyn_overbought, trend = _evaluate_trend_rsi_bounds(df)
        if oversold is None:
            oversold = dyn_oversold
        if overbought is None:
            overbought = dyn_overbought
    else:
        trend = "CUSTOM"

    rsi_series = RSIIndicator(close=df["Close"], window=period).rsi()
    rsi_now  = rsi_series.iloc[-1]
    rsi_prev = rsi_series.iloc[-2]

    if not _valid(rsi_now) or not _valid(rsi_prev):
        return "HOLD", (
            f"RSI-{period} belum terbentuk — data terlalu pendek "
            f"(butuh minimal {period + 1} baris)."
        )

    trend_info = f" [Tren: {trend}, Oversold={oversold}, Overbought={overbought}]"

    if rsi_now < oversold:
        if rsi_now > rsi_prev:
            return "BUY", (
                f"RSI Reversal BUY: RSI-{period} ({rsi_now:.2f}) di zona "
                f"oversold (< {oversold}) dan berbalik naik dari {rsi_prev:.2f}. "
                f"Potensi reversal ke atas.{trend_info}"
            )
        return "HOLD", (
            f"RSI-{period} ({rsi_now:.2f}) di zona oversold tetapi masih turun "
            f"dari {rsi_prev:.2f}. Tunggu konfirmasi pembalikan.{trend_info}"
        )

    if rsi_now > overbought:
        if rsi_now < rsi_prev:
            return "SELL", (
                f"RSI Reversal SELL: RSI-{period} ({rsi_now:.2f}) di zona "
                f"overbought (> {overbought}) dan berbalik turun dari {rsi_prev:.2f}. "
                f"Potensi koreksi ke bawah.{trend_info}"
            )
        return "HOLD", (
            f"RSI-{period} ({rsi_now:.2f}) di zona overbought tetapi masih naik "
            f"dari {rsi_prev:.2f}. Tunggu konfirmasi puncak.{trend_info}"
        )

    return "HOLD", (
        f"RSI-{period} ({rsi_now:.2f}) berada di zona netral "
        f"({oversold}–{overbought}). Tidak ada sinyal reversal saat ini.{trend_info}"
    )


# ─────────────────────────────────────────────────────────────
# 2. BOLLINGER BANDS STRATEGY
# ─────────────────────────────────────────────────────────────

def bollinger_strategy(df, period=20, std_dev=2.0):
    """
    Strategi Bollinger Bands.

    Logika:
        BUY  - Harga menyentuh Lower Band pada candle sebelumnya, lalu
               menutup kembali di atas Lower Band (bounce dari batas bawah).
        SELL - Harga menyentuh Upper Band pada candle sebelumnya, lalu
               menutup kembali di bawah Upper Band (rejection dari batas atas).
        HOLD - Harga bergerak di dalam band atau kondisi tidak terpenuhi.

    Args:
        df      : DataFrame OHLCV.
        period  : Periode Bollinger Bands. Default 20.
        std_dev : Multiplier standar deviasi. Default 2.0.

    Returns:
        (signal, alasan)
    """
    _validate_df(df, min_rows=period + 2, name="Bollinger Bands")

    close = df["Close"]
    bb = BollingerBands(close=close, window=period, window_dev=std_dev)

    upper      = bb.bollinger_hband().iloc[-1]
    lower      = bb.bollinger_lband().iloc[-1]
    middle     = bb.bollinger_mavg().iloc[-1]
    upper_prev = bb.bollinger_hband().iloc[-2]
    lower_prev = bb.bollinger_lband().iloc[-2]

    close_now  = float(close.iloc[-1])
    close_prev = float(close.iloc[-2])

    if not all(_valid(v) for v in [upper, lower, middle]):
        return "HOLD", f"Bollinger Bands belum terbentuk (butuh minimal {period} baris)."

    bandwidth = ((upper - lower) / middle * 100) if (middle and middle > 0) else 0.0
    squeeze   = bandwidth < 5.0

    # BUY: harga sentuh lower band lalu bounced kembali ke atas
    if close_prev <= float(lower_prev) and close_now > float(lower):
        return "BUY", (
            f"Bollinger BUY: Harga menyentuh Lower Band ({lower:.2f}) "
            f"dan menutup kembali di atas ({close_now:.2f}). "
            f"Bandwidth {bandwidth:.1f}%"
            + (" — squeeze aktif, potensi ekspansi volatilitas." if squeeze else ".")
        )

    # SELL: harga sentuh upper band lalu rejected kembali ke bawah
    if close_prev >= float(upper_prev) and close_now < float(upper):
        return "SELL", (
            f"Bollinger SELL: Harga menyentuh Upper Band ({upper:.2f}) "
            f"dan menutup kembali di bawah ({close_now:.2f}). "
            f"Bandwidth {bandwidth:.1f}%"
            + (" — squeeze aktif, potensi ekspansi volatilitas." if squeeze else ".")
        )

    # HOLD: harga di dalam band
    pct_b = ((close_now - lower) / (upper - lower) * 100) if (upper - lower) > 0 else 50.0
    return "HOLD", (
        f"Harga ({close_now:.2f}) di dalam Bollinger Band "
        f"[Lower: {lower:.2f} | Middle: {middle:.2f} | Upper: {upper:.2f}]. "
        f"%B: {pct_b:.1f}% | Bandwidth: {bandwidth:.1f}%"
        + (" — squeeze aktif." if squeeze else ".")
    )


# ─────────────────────────────────────────────────────────────
# 3. RSI + MOVING AVERAGE STRATEGY
# ─────────────────────────────────────────────────────────────

def rsi_ma_strategy(df, rsi_period=14, ma_fast=20, ma_slow=50, oversold=None, overbought=None):
    """
    Strategi kombinasi RSI + Moving Average (konfirmasi ganda).

    Batas oversold/overbought disesuaikan otomatis berdasarkan tren:
        - Uptrend  (MA20 > MA50): oversold = 45, overbought = 70
        - Downtrend (MA20 < MA50): oversold = 30, overbought = 60

    Logika:
        BUY  - RSI < oversold (harga relatif murah) DAN
               MA-cepat > MA-lambat (tren jangka pendek naik).
        SELL - RSI > overbought (harga relatif mahal) DAN
               MA-cepat < MA-lambat (tren jangka pendek turun).
        HOLD - Salah satu atau kedua kondisi tidak terpenuhi.

    Args:
        df          : DataFrame OHLCV.
        rsi_period  : Periode RSI. Default 14.
        ma_fast     : Periode MA cepat. Default 20.
        ma_slow     : Periode MA lambat. Default 50.
        oversold    : Batas RSI untuk sinyal BUY. None = dinamis.
        overbought  : Batas RSI untuk sinyal SELL. None = dinamis.

    Returns:
        (signal, alasan)
    """
    min_rows = max(rsi_period, ma_slow) + 2
    _validate_df(df, min_rows=min_rows, name="RSI+MA")

    close = df["Close"]

    rsi_series  = RSIIndicator(close=close, window=rsi_period).rsi()
    fast_series = SMAIndicator(close=close, window=ma_fast).sma_indicator()
    slow_series = SMAIndicator(close=close, window=ma_slow).sma_indicator()

    rsi_now  = rsi_series.iloc[-1]
    fast_now = fast_series.iloc[-1]
    slow_now = slow_series.iloc[-1]

    if not _valid(rsi_now):
        return "HOLD", f"RSI-{rsi_period} belum terbentuk (data kurang)."
    if not _valid(fast_now) or not _valid(slow_now):
        return "HOLD", f"MA{ma_fast} atau MA{ma_slow} belum terbentuk (data kurang)."

    uptrend   = fast_now > slow_now
    downtrend = fast_now < slow_now

    # ── Batas RSI dinamis berdasarkan tren ────────────────────
    if oversold is None:
        oversold = 45.0 if uptrend else 30.0
    if overbought is None:
        overbought = 70.0 if uptrend else 60.0
    trend_label = "UPTREND" if uptrend else "DOWNTREND"

    # BUY: RSI murah + tren naik
    if rsi_now < oversold and uptrend:
        return "BUY", (
            f"RSI+MA BUY: RSI-{rsi_period} ({rsi_now:.2f}) < {oversold} "
            f"(harga relatif murah) DAN MA{ma_fast} ({fast_now:.2f}) > "
            f"MA{ma_slow} ({slow_now:.2f}) (tren naik). "
            f"Konfirmasi ganda terpenuhi."
        )

    # SELL: RSI mahal + tren turun
    if rsi_now > overbought and downtrend:
        return "SELL", (
            f"RSI+MA SELL: RSI-{rsi_period} ({rsi_now:.2f}) > {overbought} "
            f"(harga relatif mahal) DAN MA{ma_fast} ({fast_now:.2f}) < "
            f"MA{ma_slow} ({slow_now:.2f}) (tren turun). "
            f"Konfirmasi ganda terpenuhi."
        )

    # HOLD: konfirmasi tidak lengkap
    reasons = []
    if rsi_now < oversold:
        reasons.append(f"RSI ({rsi_now:.2f}) oversold tapi tren turun")
    elif rsi_now > overbought:
        reasons.append(f"RSI ({rsi_now:.2f}) overbought tapi tren naik")
    else:
        reasons.append(f"RSI ({rsi_now:.2f}) di zona netral ({oversold}–{overbought})")

    trend_str = (
        f"MA{ma_fast} ({fast_now:.2f}) > MA{ma_slow} ({slow_now:.2f}) — tren naik"
        if uptrend else
        f"MA{ma_fast} ({fast_now:.2f}) < MA{ma_slow} ({slow_now:.2f}) — tren turun"
    )
    reasons.append(trend_str)
    return "HOLD", "RSI+MA HOLD: " + " | ".join(reasons) + "."


# ─────────────────────────────────────────────────────────────
# 4. MACD STRATEGY
# ─────────────────────────────────────────────────────────────

def macd_strategy(df, fast=12, slow=26, signal=9):
    """
    Strategi MACD Histogram Momentum.

    Logika:
        BUY  - Histogram hari ini > Histogram kemarin DAN
               Histogram kemarin < 0 (pelemahan tren turun mereda,
               momentum mulai berbalik naik).
        SELL - Histogram hari ini < Histogram kemarin DAN
               Histogram kemarin > 0 (momentum bullish melemah).
        HOLD - Kondisi tidak terpenuhi.

    Args:
        df     : DataFrame OHLCV.
        fast   : Periode EMA cepat. Default 12.
        slow   : Periode EMA lambat. Default 26.
        signal : Periode signal line. Default 9.

    Returns:
        (signal_str, alasan)
    """
    _validate_df(df, min_rows=slow + signal + 1, name="MACD")

    macd_ind = MACD(
        close=df["Close"], window_slow=slow, window_fast=fast, window_sign=signal
    )
    hist = macd_ind.macd_diff()

    hist_now  = hist.iloc[-1]
    hist_prev = hist.iloc[-2]

    if not _valid(hist_now) or not _valid(hist_prev):
        return "HOLD", (
            f"MACD Histogram belum terbentuk — data terlalu pendek "
            f"(butuh minimal {slow + signal} baris)."
        )

    # BUY: histogram naik dari bawah nol
    if hist_now > hist_prev and hist_prev < 0:
        return "BUY", (
            f"MACD BUY: Histogram naik ({hist_prev:.4f} → {hist_now:.4f}), "
            f"momentum bearish mereda. Potensi reversal bullish."
        )

    # SELL: histogram turun dari atas nol
    if hist_now < hist_prev and hist_prev > 0:
        return "SELL", (
            f"MACD SELL: Histogram turun ({hist_prev:.4f} → {hist_now:.4f}), "
            f"momentum bullish melemah. Potensi koreksi."
        )

    # HOLD
    direction = "naik" if hist_now > hist_prev else "turun" if hist_now < hist_prev else "flat"
    zone = "positif" if hist_now > 0 else "negatif" if hist_now < 0 else "nol"
    return "HOLD", (
        f"MACD HOLD: Histogram {direction} ({hist_prev:.4f} → {hist_now:.4f}), "
        f"zona {zone}. Belum ada konfirmasi sinyal."
    )


# ─────────────────────────────────────────────────────────────
# JALANKAN SEMUA STRATEGI SEKALIGUS
# ─────────────────────────────────────────────────────────────

def run_all_strategies(df):
    """
    Jalankan semua strategi sekaligus.

    Returns:
        {
            "rsi":       {"signal": ..., "alasan": ...},
            "bollinger": {"signal": ..., "alasan": ...},
            "rsi_ma":    {"signal": ..., "alasan": ...},
            "macd":      {"signal": ..., "alasan": ...},
        }
    """
    results = {}
    for key, func in [
        ("rsi",       rsi_strategy),
        ("bollinger", bollinger_strategy),
        ("rsi_ma",    rsi_ma_strategy),
        ("macd",      macd_strategy),
    ]:
        try:
            signal, alasan = func(df)
            results[key] = {"signal": signal, "alasan": alasan}
        except ValueError as e:
            results[key] = {"signal": "HOLD", "alasan": str(e)}
    return results


# ─────────────────────────────────────────────────────────────
# MULTI-STRATEGY CONFIRMATION
# ─────────────────────────────────────────────────────────────

def multi_strategy_confirmation(df, smart_money=False, gap_up=False, gap_confidence="LOW"):
    """
    Jalankan semua strategi, gabungkan dengan status Smart Money dan Gap Up,
    lalu hitung total votes BUY/SELL.

    File ini hanya mengeluarkan data mentah (votes dan status) —
    penentuan sinyal akhir (BUY/SELL) dilakukan di tahap scoring.

    Args:
        df             : DataFrame OHLCV.
        smart_money    : bool — apakah ada indikasi smart money.
        gap_up         : bool — apakah terjadi gap up.
        gap_confidence : str  — tingkat confidence gap (LOW/MEDIUM/HIGH).

    Returns:
        {
            "total_buy_votes":    int,
            "total_sell_votes":   int,
            "smart_money_status": bool,
            "gap_up_status":      {"detected": bool, "confidence": str},
            "details":            dict,  # hasil per strategi teknikal
        }
    """
    details = run_all_strategies(df)

    buy_count  = sum(1 for v in details.values() if v["signal"] == "BUY")
    sell_count = sum(1 for v in details.values() if v["signal"] == "SELL")

    # Smart Money sebagai voter tambahan untuk BUY
    if smart_money:
        buy_count += 1

    # Gap Up sebagai voter tambahan (hanya jika confidence MEDIUM/HIGH)
    gap_conf_upper = str(gap_confidence).upper()
    gap_ok = gap_conf_upper in {"MEDIUM", "HIGH"}
    if gap_up and gap_ok:
        buy_count += 1

    return {
        "total_buy_votes":    buy_count,
        "total_sell_votes":   sell_count,
        "smart_money_status": smart_money,
        "gap_up_status":      {"detected": gap_up, "confidence": gap_conf_upper},
        "details":            details,
    }


# ─────────────────────────────────────────────────────────────
# DEMO  (python strategies.py)
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        from data import get_stock_data

        ticker = "BBCA.JK"
        print(f"\n{'='*55}")
        print(f"  DEMO strategies.py — {ticker}")
        print(f"{'='*55}")

        df = get_stock_data(ticker)
        if df is None:
            print("[!] Gagal mengambil data.")
        else:
            print(f"[+] Data loaded: {len(df)} baris\n")

            # ── Detail per strategi ───────────────────────────────
            results = run_all_strategies(df)
            labels = {
                "rsi":       "RSI Reversal",
                "bollinger": "Bollinger Bands",
                "rsi_ma":    "RSI + Moving Average",
            }
            for key, label in labels.items():
                r = results[key]
                print(f"  {'─'*50}")
                print(f"  Strategi : {label}")
                print(f"  Signal   : {r['signal']}")
                print(f"  Alasan   : {r['alasan']}")

            # ── Multi-Strategy Confirmation ───────────────────────
            conf = multi_strategy_confirmation(df)
            print(f"\n  {'═'*50}")
            print(f"  MULTI-STRATEGY CONFIRMATION (Raw Data)")
            print(f"  {'═'*50}")
            print(f"  Total BUY votes  : {conf['total_buy_votes']}")
            print(f"  Total SELL votes  : {conf['total_sell_votes']}")
            print(f"  Smart Money       : {conf['smart_money_status']}")
            print(f"  Gap Up            : {conf['gap_up_status']}")
            print(f"\n{'='*55}\n")

    except ImportError:
        print("[!] Modul data.py tidak ditemukan.")
