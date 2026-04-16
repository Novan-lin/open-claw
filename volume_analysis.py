"""
volume_analysis.py - Smart Money Detection System (Upgraded v2.0)
==================================================================
Menganalisis pergerakan volume dan price action untuk mendeteksi
aktivitas Smart Money (institutional buying/selling).

Kriteria:
    1. Volume Spike   : volume > 1.5x rata-rata 20 hari
    2. Price Action   : close hari ini > close kemarin
    3. Strong Close   : (close - low) / (high - low) > 0.7
    4. Breakout       : close > high tertinggi 5 hari sebelumnya

Label Output:
    - "SMART MONEY STRONG 🔥" : semua 4 kriteria terpenuhi
    - "SMART MONEY WEAK"      : sebagian kriteria (2-3)
    - "NORMAL"                : kurang dari 2 kriteria
"""

import pandas as pd
import math
import sys

# Pastikan terminal Windows bisa menampilkan karakter Unicode (emoji, arrow, dsb)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def analyze_volume(df: pd.DataFrame):
    """
    Deteksi Smart Money berdasarkan 4 kriteria: Volume Spike,
    Price Action, Strong Close, dan Breakout.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame OHLCV dengan kolom: 'Open', 'High', 'Low', 'Close', 'Volume'.

    Returns
    -------
    tuple:
        volume_spike  (bool)   - Apakah terjadi lonjakan volume
        avg_volume    (float)  - Rata-rata volume 20 hari
        current_volume(float)  - Volume hari ini
        smart_money   (bool)   - True jika label STRONG atau WEAK
        label         (str)    - Label hasil analisis
        confidence    (float)  - Skor kepercayaan 0.0–1.0
        alasan        (list)   - Daftar alasan/kondisi yang terpenuhi
    """

    # ── Defensive check ──────────────────────────────────────────
    required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    if df is None or df.empty:
        return False, 0.0, 0.0, False, "NORMAL", 0.0, []

    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"[!] Kolom hilang di DataFrame: {missing}")
        return False, 0.0, 0.0, False, "NORMAL", 0.0, []

    # Butuh minimal 6 hari: 1 hari kemarin + 5 hari untuk breakout window
    if len(df) < 6:
        print(f"[!] Data terlalu sedikit ({len(df)} hari, minimal 6)")
        return False, 0.0, 0.0, False, "NORMAL", 0.0, []

    # ── Ambil nilai hari ini dan window ──────────────────────────
    today       = df.iloc[-1]
    yesterday   = df.iloc[-2]
    prev_5_days = df.iloc[-6:-1]   # 5 hari SEBELUM hari ini

    close_today     = float(today['Close'])
    close_yesterday = float(yesterday['Close'])
    high_today      = float(today['High'])
    low_today       = float(today['Low'])
    vol_today       = float(today['Volume'])

    # Rata-rata volume 20 hari (gunakan semua data jika kurang dari 20)
    avg_vol_series = df['Volume'].rolling(window=20).mean()
    avg_volume = float(avg_vol_series.iloc[-1])
    if math.isnan(avg_volume):
        avg_volume = float(df['Volume'].mean())

    high_5d = float(prev_5_days['High'].max())  # high tertinggi 5 hari sebelumnya

    # ═══════════════════════════════════════════════════════════
    # KRITERIA 1: Volume Spike  (volume > 1.5x rata-rata 20 hari)
    # ═══════════════════════════════════════════════════════════
    vol_ratio     = vol_today / avg_volume if avg_volume > 0 else 0.0
    volume_spike  = vol_ratio > 1.5
    vol_detail    = f"{vol_ratio:.2f}x avg"

    # ═══════════════════════════════════════════════════════════
    # KRITERIA 2: Price Action  (close hari ini > close kemarin)
    # ═══════════════════════════════════════════════════════════
    price_up      = close_today > close_yesterday
    price_change  = ((close_today - close_yesterday) / close_yesterday * 100) if close_yesterday else 0.0

    # ═══════════════════════════════════════════════════════════
    # KRITERIA 3: Strong Close  ((close - low) / (high - low) > 0.7)
    # ═══════════════════════════════════════════════════════════
    candle_range  = high_today - low_today
    if candle_range > 0:
        strong_close_ratio = (close_today - low_today) / candle_range
    else:
        strong_close_ratio = 0.5   # neutral jika doji (no range)
    strong_close = strong_close_ratio > 0.7

    # ═══════════════════════════════════════════════════════════
    # KRITERIA 4: Breakout  (close > high 5 hari terakhir)
    # ═══════════════════════════════════════════════════════════
    breakout = close_today > high_5d

    # ═══════════════════════════════════════════════════════════
    # SCORING & LABELING
    # ═══════════════════════════════════════════════════════════
    met_criteria  = 0
    alasan        = []

    if volume_spike:
        met_criteria += 1
        alasan.append(f"✅ Volume Spike: {vol_today:,.0f} ({vol_detail})")
    else:
        alasan.append(f"❌ Volume Normal: {vol_today:,.0f} ({vol_detail})")

    if price_up:
        met_criteria += 1
        alasan.append(f"✅ Harga Naik: +{price_change:.2f}% ({close_yesterday:.0f} → {close_today:.0f})")
    else:
        alasan.append(f"❌ Harga Tidak Naik: {price_change:.2f}% ({close_yesterday:.0f} → {close_today:.0f})")

    if strong_close:
        met_criteria += 1
        alasan.append(f"✅ Strong Close: ratio {strong_close_ratio:.2f} (> 0.70)")
    else:
        alasan.append(f"❌ Weak Close: ratio {strong_close_ratio:.2f} (≤ 0.70)")

    if breakout:
        met_criteria += 1
        alasan.append(f"✅ Breakout: Close {close_today:.0f} > High 5D {high_5d:.0f}")
    else:
        alasan.append(f"❌ No Breakout: Close {close_today:.0f} ≤ High 5D {high_5d:.0f}")

    # Confidence = proporsi kriteria terpenuhi (0.0 – 1.0)
    confidence  = met_criteria / 4.0

    # Label final
    if met_criteria == 4:
        label       = "SMART MONEY STRONG 🔥"
        smart_money = True
    elif met_criteria >= 2:
        label       = "SMART MONEY WEAK"
        smart_money = True
    else:
        label       = "NORMAL"
        smart_money = False

    # ═══════════════════════════════════════════════════════════
    # DEBUG PRINT
    # ═══════════════════════════════════════════════════════════
    print("\n" + "═" * 52)
    print("  📊 SMART MONEY DETECTION v2.0")
    print("═" * 52)
    print(f"  Volume Hari Ini   : {vol_today:>15,.0f}")
    print(f"  Avg Volume 20D    : {avg_volume:>15,.0f}")
    print(f"  Rasio Volume      : {vol_ratio:>14.2f}x")
    print(f"  Price Yesterday   : {close_yesterday:>15.2f}")
    print(f"  Price Today       : {close_today:>15.2f}")
    print(f"  High Hari Ini     : {high_today:>15.2f}")
    print(f"  Low Hari Ini      : {low_today:>15.2f}")
    print(f"  Strong Close Ratio: {strong_close_ratio:>14.2f}")
    print(f"  High 5D           : {high_5d:>15.2f}")
    print(f"  Kriteria Terpenuhi: {met_criteria}/4")
    print()
    print("  Detail Kriteria:")
    for a in alasan:
        print(f"    {a}")
    print()
    print(f"  ► LABEL      : {label}")
    print(f"  ► CONFIDENCE : {confidence:.0%} ({met_criteria}/4 kriteria)")
    print(f"  ► SMART MONEY: {'YES' if smart_money else 'NO'}")
    print("═" * 52 + "\n")

    return volume_spike, avg_volume, vol_today, smart_money, label, confidence, alasan


# ════════════════════════════════════════════════════════════
# SELF-TEST (jalankan: python volume_analysis.py)
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":

    def make_df(vol_list, close_list, high_list=None, low_list=None):
        """Helper buat DataFrame test OHLCV."""
        n = len(close_list)
        if high_list is None:
            high_list  = [c * 1.02 for c in close_list]
        if low_list is None:
            low_list   = [c * 0.98 for c in close_list]
        return pd.DataFrame({
            'Open':   [c * 0.99 for c in close_list],
            'High':   high_list,
            'Low':    low_list,
            'Close':  close_list,
            'Volume': vol_list,
        })

    # ── TEST 1: Semua terpenuhi → SMART MONEY STRONG ────────────
    print("=" * 60)
    print("[TEST 1] Semua kriteria terpenuhi → SMART MONEY STRONG 🔥")
    print("=" * 60)
    closes = [5000] * 5 + [5000] * 14 + [5300]   # breakout & price up
    highs  = [5050] * 5 + [5100] * 14 + [5350]   # high hari ini
    lows   = [4950] * 5 + [4900] * 14 + [5250]   # low → strong close ratio tinggi
    vols   = [100_000] * 19 + [250_000]           # volume spike 2.5x
    analyze_volume(make_df(vols, closes, highs, lows))

    # ── TEST 2: Sebagian → SMART MONEY WEAK ─────────────────────
    print("=" * 60)
    print("[TEST 2] Kriteria sebagian (volume + price up) → SMART MONEY WEAK")
    print("=" * 60)
    closes2 = [5000] * 19 + [5050]   # price up tapi kecil
    highs2  = [5100] * 19 + [5200]   # high 5d = 5100, tidak breakout
    lows2   = [4900] * 19 + [4980]   # strong close ratio ~0.47, lemah
    vols2   = [100_000] * 19 + [200_000]   # spike 2x
    analyze_volume(make_df(vols2, closes2, highs2, lows2))

    # ── TEST 3: Tidak ada → NORMAL ───────────────────────────────
    print("=" * 60)
    print("[TEST 3] Tidak ada kriteria terpenuhi → NORMAL")
    print("=" * 60)
    closes3 = [5000] * 19 + [4950]   # harga turun
    highs3  = [5100] * 19 + [5000]
    lows3   = [4900] * 19 + [4920]   # strong close ratio ~0.43
    vols3   = [100_000] * 19 + [90_000]   # volume malah turun
    analyze_volume(make_df(vols3, closes3, highs3, lows3))
