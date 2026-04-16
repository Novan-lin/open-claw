"""
stock_filter.py - Filter Kelayakan Saham Sebelum Analisis
==========================================================
Menyaring saham berdasarkan kriteria minimum agar hanya
saham yang liquid dan bermakna yang dianalisis lebih lanjut.

Kriteria Default:
    1. Harga (Close) terakhir > Rp 50
    2. Volume rata-rata 5 hari terakhir > 1.000.000

Fungsi:
    is_stock_eligible(df, ticker)  -> bool
    filter_dataframe_list(df_map)  -> dict (yang lolos)
"""

import sys
import math
import pandas as pd

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ============================================================
# KONFIGURASI THRESHOLD (ubah di sini jika ingin sesuaikan)
# ============================================================
MIN_PRICE        = 50          # Harga minimum (Rp)
MIN_AVG_VOLUME   = 1_000_000   # Volume rata-rata minimum (5 hari)
VOLUME_WINDOW    = 5           # Jumlah hari untuk hitung avg volume


# ============================================================
# FUNGSI UTAMA
# ============================================================

def is_stock_eligible(df: pd.DataFrame, ticker: str = "UNKNOWN") -> bool:
    """
    Cek apakah saham memenuhi kriteria minimum untuk dianalisis.

    Kriteria:
        1. Close terakhir > MIN_PRICE  (default: Rp 50)
        2. Avg Volume (5 hari) > MIN_AVG_VOLUME (default: 1.000.000)

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame OHLCV saham. Harus memiliki kolom 'Close' dan 'Volume'.
    ticker : str, optional
        Kode saham untuk keperluan debug print.

    Returns
    -------
    bool
        True  -> saham LOLOS filter, lanjut ke analisis
        False -> saham DI-SKIP, tidak memenuhi kriteria
    """
    print(f"\n[FILTER] Memeriksa kelayakan: {ticker}")
    print("-" * 45)

    # ── Guard: DataFrame kosong atau kolom tidak lengkap ───────
    if df is None or df.empty:
        print(f"  [SKIP] DataFrame kosong atau None.")
        print("-" * 45)
        return False

    required = ['Close', 'Volume']
    missing  = [c for c in required if c not in df.columns]
    if missing:
        print(f"  [SKIP] Kolom hilang: {missing}")
        print("-" * 45)
        return False

    if len(df) < 1:
        print(f"  [SKIP] Data kurang dari 1 baris.")
        print("-" * 45)
        return False

    # ── Ambil nilai ───────────────────────────────────────────
    close_last  = df['Close'].iloc[-1]
    window      = min(VOLUME_WINDOW, len(df))
    avg_volume  = df['Volume'].tail(window).mean()

    # Tangkap NaN
    if math.isnan(float(close_last)):
        print(f"  [SKIP] Harga terakhir adalah NaN.")
        print("-" * 45)
        return False
    if math.isnan(float(avg_volume)):
        print(f"  [SKIP] Avg volume adalah NaN.")
        print("-" * 45)
        return False

    close_last = float(close_last)
    avg_volume = float(avg_volume)

    # ── Evaluasi kriteria ─────────────────────────────────────
    passed_price  = close_last > MIN_PRICE
    passed_volume = avg_volume  > MIN_AVG_VOLUME
    eligible      = passed_price and passed_volume

    # ── Debug print ───────────────────────────────────────────
    price_icon  = "OK" if passed_price  else "FAIL"
    volume_icon = "OK" if passed_volume else "FAIL"

    print(f"  [{price_icon }] Harga Terakhir : Rp {close_last:>12,.2f}  "
          f"(min: Rp {MIN_PRICE:,})")
    print(f"  [{volume_icon}] Avg Vol {window}D   : {avg_volume:>15,.0f}  "
          f"(min: {MIN_AVG_VOLUME:,})")

    if eligible:
        print(f"  => LOLOS  — {ticker} akan dianalisis.")
    else:
        reasons = []
        if not passed_price:
            reasons.append(f"Harga terlalu rendah (Rp {close_last:.2f} <= {MIN_PRICE})")
        if not passed_volume:
            reasons.append(f"Volume terlalu kecil ({avg_volume:,.0f} <= {MIN_AVG_VOLUME:,})")
        print(f"  => SKIP   — Alasan: {'; '.join(reasons)}")

    print("-" * 45)
    return eligible


def filter_dataframe_list(df_map: dict) -> dict:
    """
    Filter sekumpulan DataFrame saham sekaligus.

    Parameters
    ----------
    df_map : dict
        Dictionary {ticker: DataFrame}.

    Returns
    -------
    dict
        Hanya berisi saham yang LOLOS filter.

    Contoh::

        df_map = {
            'BBCA.JK': df_bbca,
            'GOTO.JK': df_goto,
        }
        lolos = filter_dataframe_list(df_map)
    """
    lolos = {}
    skip  = []

    for ticker, df in df_map.items():
        if is_stock_eligible(df, ticker):
            lolos[ticker] = df
        else:
            skip.append(ticker)

    print(f"\n[FILTER SUMMARY] Lolos: {len(lolos)} | Skip: {len(skip)}")
    if skip:
        print(f"  Skip list: {', '.join(skip)}")
    return lolos


# ============================================================
# SELF-TEST
# ============================================================
if __name__ == "__main__":

    def make_test_df(price, volume, rows=10):
        """Buat DataFrame test sederhana."""
        return pd.DataFrame({
            'Open':   [price * 0.99] * rows,
            'High':   [price * 1.02] * rows,
            'Low':    [price * 0.98] * rows,
            'Close':  [price]        * rows,
            'Volume': [volume]       * rows,
        })

    print("=" * 55)
    print("  STOCK FILTER — Self Test")
    print("=" * 55)

    # Test 1: Lolos semua kriteria
    print("\n[TEST 1] Harga OK + Volume OK -> Harus LOLOS")
    df1 = make_test_df(price=9_500, volume=5_000_000)
    r1  = is_stock_eligible(df1, "BBCA.JK")
    print(f"  Hasil: {'LOLOS' if r1 else 'SKIP'}\n")

    # Test 2: Harga terlalu rendah
    print("[TEST 2] Harga < 50 -> Harus SKIP")
    df2 = make_test_df(price=45, volume=5_000_000)
    r2  = is_stock_eligible(df2, "GORENGAN.JK")
    print(f"  Hasil: {'LOLOS' if r2 else 'SKIP'}\n")

    # Test 3: Volume terlalu kecil
    print("[TEST 3] Volume < 1 Juta -> Harus SKIP")
    df3 = make_test_df(price=6_000, volume=500_000)
    r3  = is_stock_eligible(df3, "ILLIQUID.JK")
    print(f"  Hasil: {'LOLOS' if r3 else 'SKIP'}\n")

    # Test 4: Dua-duanya gagal
    print("[TEST 4] Harga < 50 DAN Volume kecil -> Harus SKIP")
    df4 = make_test_df(price=30, volume=10_000)
    r4  = is_stock_eligible(df4, "PENNY.JK")
    print(f"  Hasil: {'LOLOS' if r4 else 'SKIP'}\n")

    # Test 5: DataFrame kosong
    print("[TEST 5] DataFrame kosong -> Harus SKIP")
    df5 = pd.DataFrame()
    r5  = is_stock_eligible(df5, "EMPTY.JK")
    print(f"  Hasil: {'LOLOS' if r5 else 'SKIP'}\n")

    # Test 6: filter_dataframe_list batch
    print("[TEST 6] Batch filter 3 saham")
    batch = {
        "BBCA.JK":     make_test_df(9_500, 10_000_000),
        "PENNY.JK":    make_test_df(20,    100_000),
        "MIDLIQ.JK":   make_test_df(1_500, 800_000),
    }
    hasil = filter_dataframe_list(batch)
    print(f"\n  Saham lolos batch: {list(hasil.keys())}")

    print("\n" + "=" * 55)
    print("  Self-test selesai.")
    print("=" * 55)
