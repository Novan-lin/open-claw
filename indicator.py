import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator

def calculate_indicators(df, rsi_period: int = 14, ma_short: int = 20, ma_long: int = 50):
    """
    Menghitung indikator teknikal (RSI, MA short, MA long) dari target DataFrame.
    Hanya mengembalikan row terakhir dalam bentuk dictionary.

    Args:
        df         : DataFrame harga saham.
        rsi_period : Periode RSI. Default 14.
        ma_short   : Periode MA cepat. Default 20.
        ma_long    : Periode MA lambat. Default 50.
    """
    if df is None or df.empty:
        print("Error: DataFrame kosong atau tidak valid.")
        return None
        
    # Gunakan copy() untuk menghindari SettingWithCopyWarning
    df_copy = df.copy()
    
    try:
        # Menghitung RSI
        rsi_indicator = RSIIndicator(close=df_copy['Close'], window=rsi_period)
        df_copy['RSI'] = rsi_indicator.rsi()
        
        # Menghitung Simple Moving Average (MA short)
        ma20_indicator = SMAIndicator(close=df_copy['Close'], window=ma_short)
        df_copy['MA20'] = ma20_indicator.sma_indicator()
        
        # Menghitung Simple Moving Average (MA long)
        ma50_indicator = SMAIndicator(close=df_copy['Close'], window=ma_long)
        df_copy['MA50'] = ma50_indicator.sma_indicator()
        
        # Ambil data hari terakhir
        latest_data = df_copy.iloc[-1]
        
        # Susun dictionary untuk return
        result = {
            'rsi': latest_data['RSI'],
            'ma20': latest_data['MA20'],
            'ma50': latest_data['MA50'],
            'close_price': latest_data['Close']
        }
        
        # Print hasil sesuai kriteria
        print("\n[+] Hasil Kalkulasi Indikator Analisis Teknikal:")
        print(f"Harga Open (Terakhir)   : {latest_data['Open']:.2f}")
        print(f"Harga Close (Terakhir)  : {result['close_price']:.2f}")
        
        # Cek apakah bernilai NaN karena rentang waktu data yang kurang
        rsi_str  = f"{result['rsi']:.2f}"  if pd.notna(result['rsi'])  else f"Data tidak cukup (butuh > {rsi_period} hari)"
        ma20_str = f"{result['ma20']:.2f}" if pd.notna(result['ma20']) else f"Data tidak cukup (butuh > {ma_short} hari)"
        ma50_str = f"{result['ma50']:.2f}" if pd.notna(result['ma50']) else f"Data tidak cukup (butuh > {ma_long} hari)"
        
        print(f"RSI ({rsi_period})                : {rsi_str}")
        print(f"MA ({ma_short})                 : {ma20_str}")
        print(f"MA ({ma_long})                 : {ma50_str}")
        print("-" * 50)
        
        return result
        
    except Exception as e:
        print(f"Error saat menghitung indikator: {e}")
        return None

if __name__ == "__main__":
    # Contoh penggunaan dengan modul data.py
    try:
        from data import get_stock_data
        
        print("1. Menarik data untuk simulasi...")
        # Di data.py, secara bawaan mengambil "1mo" (sekitar 20-22 hari bursa). 
        # Oleh karena itu, MA50 pasti akan menampilkan "Data tidak cukup". 
        df_bbca = get_stock_data("BBCA.JK")
        
        if df_bbca is not None:
            hasil_indikator = calculate_indicators(df_bbca)
            if hasil_indikator:
                print(f"Output Dictionary:\n{hasil_indikator}")
                
    except ImportError:
        print("Modul data.py tidak ditemukan di direktori yang sama.")
