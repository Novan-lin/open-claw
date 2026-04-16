"""
signal_generator.py (sebelumnya signal.py) - Modul Sinyal Trading Sederhana.

Modul ini berisi fungsi clean dan sederhana untuk generate sinyal trading
(BUY/SELL/HOLD) dengan kriteria:
 - BUY  jika RSI < 30 dan Harga > MA20
 - SELL jika RSI > 70

Catatan: File ini dinamai `signal_generator.py` untuk menghindari bentrokan
dengan modul bawaan Python yang bernama "signal".
"""

import pandas as pd
from typing import Tuple

def generate_signal(df: pd.DataFrame) -> Tuple[str, str]:
    """
    Menghasilkan sinyal trading sederhana berdasarkan data terakhir.

    Kriteria:
    - BUY  : RSI < 30 DAN Harga (Close) di atas MA20
    - SELL : RSI > 70
    - HOLD : Kondisi lainnya

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame saham dengan indikator teknikal: 'Close', 'RSI_14', 'MA_20'.

    Returns
    -------
    Tuple[str, str]
        (Sinyal [BUY/SELL/HOLD], Alasan sinyal)
    """
    if df.empty:
        return "HOLD", "Data kosong"

    # Ambil baris data terakhir saja
    latest = df.iloc[-1]

    # Validasi keberadaan kolom indikator
    required_cols = ["Close", "RSI_14", "MA_20"]
    for col in required_cols:
        if col not in df.columns or pd.isna(latest[col]):
            return "HOLD", f"Indikator '{col}' belum siap/tidak tersedia"

    close_price = latest["Close"]
    rsi = latest["RSI_14"]
    ma20 = latest["MA_20"]

    # Logika BUY / SELL / HOLD
    if rsi < 30 and close_price > ma20:
        reason = f"RSI oversold ({rsi:.2f}) dan harga di atas MA20 ({close_price:.2f} > {ma20:.2f})"
        return "BUY", reason
    
    elif rsi > 70:
        reason = f"RSI overbought ({rsi:.2f})"
        return "SELL", reason
    
    else:
        reason = f"RSI netral ({rsi:.2f}) dan belum memenuhi kondisi masuk"
        return "HOLD", reason


if __name__ == "__main__":
    from data import fetch_stock_data
    from indicator import add_indicators

    print("=" * 60)
    print("CONTOH: Sinyal Trading Sederhana")
    print("=" * 60)

    try:
        # 1. Ambil data
        df = fetch_stock_data("BBCA.JK", period="3mo")
        print("\nData awal berhasil diambil.")

        # 2. Hitung indikator
        df = add_indicators(df)
        print("Indikator ditambahkan.\n")

        # 3. Generate Sinyal
        sinyal, alasan = generate_signal(df)

        print("-" * 40)
        print(f"Sinyal Akhir : {sinyal}")
        print(f"Alasan       : {alasan}")
        print("-" * 40)

    except Exception as e:
        print(f"Error: {e}")
