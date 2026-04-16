import yfinance as yf
import pandas as pd

def get_stock_data(ticker):
    """
    Mengambil data saham menggunakan yfinance.
    - Periode: 1 bulan terakhir
    - Interval: harian (1d)
    """
    try:
        print(f"Mengambil data saham untuk {ticker}...")
        
        # Mengambil data saham menggunakan Ticker history untuk hasil DataFrame yang rapi
        stock = yf.Ticker(ticker)
        df = stock.history(period="1mo", interval="1d")
        
        # Error handling jika data kosong
        if df is None or df.empty:
            print(f"Peringatan: Data untuk ticker '{ticker}' kosong atau tidak ditemukan.")
            return None
            
        # Print 3 data terakhir
        print(f"\n[+] 3 Data Terakhir untuk {ticker}:")
        print(df.tail(3))
        print("-" * 50)
        
        return df
        
    except Exception as e:
        print(f"Error saat mengambil data untuk {ticker}: {e}")
        return None

if __name__ == "__main__":
    # Contoh penggunaan
    df_bbca = get_stock_data("BBCA.JK")
    
    if df_bbca is not None:
        print("Data berhasil diambil, total baris:", len(df_bbca))
