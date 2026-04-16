import os
import json
from datetime import datetime

FILE_NAME = "trades.json"

def _load_data():
    """Memuat data trades.json, buat baru jika belum ada."""
    if not os.path.exists(FILE_NAME):
        data = {
            "active": [],
            "closed": []
        }
        _save_data(data)
        return data
        
    try:
        with open(FILE_NAME, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, IOError):
        # Fallback jika file rusak
        return {"active": [], "closed": []}

def _save_data(data):
    """Menyimpan dictionary data ke dalam trades.json."""
    with open(FILE_NAME, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)

def add_trade(ticker, entry, tp, sl, date=None):
    """
    Menambahkan trade baru ke list active.
    Jika date kosong, gunakan waktu saat ini.
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
    data = _load_data()
    
    # Buat record baru
    new_trade = {
        "ticker": ticker,
        "entry": float(entry) if entry else None,
        "tp": float(tp) if tp else None,
        "sl": float(sl) if sl else None,
        "date_opened": date
    }
    
    # Opsional: Bisa ditambahkan perlindungan duplikasi jika ticker sudah aktif, 
    # namun untuk sekarang kita izinkan multiple entries
    data["active"].append(new_trade)
    _save_data(data)
    
    return True

def close_trade(ticker, exit_price, result):
    """
    Menutup trade yang sedang aktif berdasarkan ticker.
    Memindahkan data dari 'active' ke 'closed'.
    """
    data = _load_data()
    
    # Cari index trade aktif dengan ticker tersebut
    target_idx = None
    for i, trade in enumerate(data["active"]):
        if trade.get("ticker") == ticker:
            target_idx = i
            break
            
    if target_idx is not None:
        # Pindahkan trade ke daftar closed
        closed_trade = data["active"].pop(target_idx)
        closed_trade["exit_price"] = float(exit_price) if exit_price else None
        closed_trade["result"] = result
        closed_trade["date_closed"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        data["closed"].append(closed_trade)
        _save_data(data)
        return True
        
    # Jika tidak ada trade aktif dengan ticker tersebut
    return False

def monitor_active_trades():
    """
    Memantau seluruh trade aktif di trades.json.
    Jika harga >= TP -> close_trade(WIN)
    Jika harga <= SL -> close_trade(LOSS)
    """
    # Import secara dinamis agar terhindar dari permasalahan circular import
    from data import get_stock_data
    
    data = _load_data()
    active_trades = data.get("active", [])
    
    if not active_trades:
        return
        
    print("\n[MONITOR] Memeriksa status trade aktif...")
    
    for trade in list(active_trades):
        ticker = trade.get("ticker")
        tp = trade.get("tp")
        sl = trade.get("sl")
        
        if not ticker or tp is None or sl is None:
            continue
            
        query_ticker = ticker if ticker.endswith(".JK") else f"{ticker}.JK"
        df = get_stock_data(query_ticker)
        
        if df is None or df.empty:
            continue
            
        current_price = df['Close'].iloc[-1]
        print(f"  -> {ticker} | Harga: {current_price:.2f} | TP: {tp:.2f} | SL: {sl:.2f}")
        
        if current_price >= tp:
            print(f"  [WIN] Target Profit (TP) tercapai untuk {ticker}!")
            close_trade(ticker, current_price, "WIN")
        elif current_price <= sl:
            print(f"  [LOSS] Stop Loss (SL) tersentuh untuk {ticker}!")
            close_trade(ticker, current_price, "LOSS")

def calculate_performance():
    """
    Menghitung performa trading dari trades.json dan sekalian mencetaknya.
    """
    data = _load_data()
    closed_trades = data.get("closed", [])
    
    total_trade = len(closed_trades)
    
    if total_trade == 0:
        print("Performance:")
        print("Total Trade: 0")
        print("Winrate: 0%")
        print("Net Profit: 0%")
        return
        
    wins = 0
    total_profit_pct = 0.0
    total_loss_pct = 0.0
    
    for trade in closed_trades:
        result = trade.get("result", "")
        if result == "WIN":
            wins += 1
            
        entry = trade.get("entry")
        exit_price = trade.get("exit_price")
        
        if entry and exit_price and entry > 0:
            pnl_pct = ((exit_price - entry) / entry) * 100
            if pnl_pct > 0:
                total_profit_pct += pnl_pct
            else:
                total_loss_pct += pnl_pct
                
    winrate = (wins / total_trade) * 100
    net_profit_pct = total_profit_pct + total_loss_pct
    
    print("Performance:")
    print(f"Total Trade: {total_trade}")
    print(f"Winrate: {winrate:.0f}%")
    print(f"Net Profit: {net_profit_pct:.2f}%")
    
    return {
        "total_trade": total_trade,
        "winrate_pct": winrate,
        "total_profit_pct": total_profit_pct,
        "total_loss_pct": total_loss_pct,
        "net_profit_pct": net_profit_pct
    }

def send_daily_report():
    """
    Mengirim laporan performa (Daily Report) ke Telegram.
    """
    from notifier import send_telegram_message
    
    perf = calculate_performance()
    
    if perf is None:
        return False
        
    msg = "📊 DAILY REPORT\n\n"
    msg += f"Total Trade: {perf['total_trade']}\n"
    msg += f"Winrate: {perf['winrate_pct']:.0f}%\n"
    msg += f"Net Profit: {perf['net_profit_pct']:.2f}%\n\n"
    msg += "Keep disciplined 🔥"
    
    return send_telegram_message(msg)

if __name__ == "__main__":
    # Script untuk testing langsung
    print("Testing Trade Logger & Performance...")
    
    monitor_active_trades()
    print("-" * 30)
    calculate_performance()
    print("\nSilakan periksa file trades.json untuk melihat hasil strukturnya.")
