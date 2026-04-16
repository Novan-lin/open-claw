import time
import yfinance as yf
import pandas as pd

# Periode data: 4 bulan agar MA20 dan MA50 punya cukup data (~80 hari trading)
DATA_PERIOD   = "4mo"
DATA_INTERVAL = "1d"
MAX_RETRIES   = 3
RETRY_DELAY   = 5   # detik antar retry

def get_stock_data(ticker):
    """
    Mengambil data saham menggunakan yfinance.
    - Periode: 4 bulan (cukup untuk MA20 & MA50)
    - Interval: harian (1d)
    - Retry: otomatis hingga 3x jika Yahoo Finance gagal/timeout
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if attempt > 1:
                print(f"  [RETRY {attempt}/{MAX_RETRIES}] Mengambil ulang data {ticker}...")
            else:
                print(f"Mengambil data saham untuk {ticker}...")

            stock = yf.Ticker(ticker)
            df = stock.history(period=DATA_PERIOD, interval=DATA_INTERVAL)

            # Error handling jika data kosong
            if df is None or df.empty:
                print(f"Peringatan: Data untuk ticker '{ticker}' kosong atau tidak ditemukan.")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                    continue
                return None

            # Buang baris yang harga Close-nya NaN
            # (yfinance kadang menambah baris hari ini tanpa harga saat market belum/sudah tutup)
            df = df.dropna(subset=["Close"])

            if df.empty:
                print(f"Peringatan: Semua data Close NaN untuk '{ticker}'.")
                return None

            # Print 3 data terakhir
            print(f"\n[+] 3 Data Terakhir untuk {ticker} ({len(df)} baris):")
            print(df.tail(3))
            print("-" * 50)

            return df

        except Exception as e:
            print(f"  [ERROR attempt {attempt}] {ticker}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    print(f"[GAGAL] Tidak bisa ambil data {ticker} setelah {MAX_RETRIES}x percobaan.")
    return None

if __name__ == "__main__":
    # Contoh penggunaan
    df_bbca = get_stock_data("BBCA.JK")

    if df_bbca is not None:
        print("Data berhasil diambil, total baris:", len(df_bbca))
