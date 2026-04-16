"""
signal_generator.py (sebelumnya signal.py) - Modul Sinyal Trading Sederhana.

Modul ini berisi fungsi clean dan sederhana untuk generate sinyal trading
(BUY/SELL/HOLD) dengan kriteria:
 - BUY  jika RSI < 30 dan Harga > MA20
 - SELL jika RSI > 70

Catatan: File ini dinamai `signal_generator.py` untuk menghindari bentrokan
dengan modul bawaan Python yang bernama "signal".
"""

import math
from typing import Tuple

def generate_signal(
    rsi,
    ma20,
    ma50,
    harga,
    smart_money=False,
    gap_up=False,
    gap_confidence="LOW",
) -> Tuple[str, str]:
    """
    Menghasilkan sinyal trading sederhana berdasarkan input nilai indikator teknikal.

    Parameters
    ----------
    rsi : float
        Nilai RSI terkini.
    ma20 : float
        Nilai Moving Average short (20).
    ma50 : float
        Nilai Moving Average long (50).
    harga : float
        Harga close terakhir.
    smart_money : bool
        Apakah ada indikasi smart money.
    gap_up : bool
        Apakah terjadi gap up.
    gap_confidence : str
        Tingkat confidence gap (LOW/MEDIUM/HIGH).

    Returns
    -------
    Tuple[str, str]
        (Sinyal [BUY/SELL/HOLD], Alasan sinyal)
    """
    signal = 'HOLD'
    alasan = 'Kriteria BUY ketat belum terpenuhi. Sinyal ditahan untuk mengurangi false signal.'

    if rsi is None or math.isnan(rsi):
        alasan = 'Data RSI belum terbentuk karena rentang hari kurang dari 14 hari.'
        return signal, alasan

    if rsi > 70:
        signal = 'SELL'
        alasan = f'RSI berada di level Overbought ({rsi:.2f} > 70), indikasi harga saham sudah terlalu mahal (potensi koreksi turun).'
    else:
        valid_ma = (
            ma20 is not None and ma50 is not None
            and not math.isnan(ma20) and not math.isnan(ma50)
        )
        uptrend = valid_ma and ma20 > ma50
        rsi_in_buy_zone = 35 <= rsi <= 60
        gap_ok = str(gap_confidence).upper() in {"MEDIUM", "HIGH"}

        if rsi_in_buy_zone and uptrend and smart_money and gap_ok:
            signal = 'BUY'
            alasan = (
                f'BUY ketat valid: RSI {rsi:.2f} berada di 35-60, '
                f'MA20 ({ma20:.2f}) > MA50 ({ma50:.2f}), Smart Money aktif, '
                f'dan Gap Up confidence {str(gap_confidence).upper()}.'
            )
        else:
            gagal = []
            if not rsi_in_buy_zone:
                gagal.append(f"RSI {rsi:.2f} di luar zona 35-60")
            if not uptrend:
                gagal.append("MA20 belum di atas MA50")
            if not smart_money:
                gagal.append("Smart Money belum aktif")
            if not gap_ok:
                gagal.append(f"Gap Up confidence masih {str(gap_confidence).upper()}")
            alasan = "HOLD: " + "; ".join(gagal) + "."

    return signal, alasan


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
