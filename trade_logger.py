import os
import json
import math
from datetime import datetime, timezone, timedelta

FILE_NAME = "trades.json"
WIB = timezone(timedelta(hours=7))


# ─────────────────────────────────────────────────────────────
# I/O HELPERS
# ─────────────────────────────────────────────────────────────

def _load_data() -> dict:
    if not os.path.exists(FILE_NAME):
        data = {"active": [], "closed": []}
        _save_data(data)
        return data
    try:
        with open(FILE_NAME, "r", encoding="utf-8") as f:
            d = json.load(f)
            if not isinstance(d, dict):
                return {"active": [], "closed": []}
            d.setdefault("active", [])
            d.setdefault("closed", [])
            return d
    except (json.JSONDecodeError, IOError):
        return {"active": [], "closed": []}


def _save_data(data: dict):
    tmp = FILE_NAME + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    os.replace(tmp, FILE_NAME)


def _now_str() -> str:
    return datetime.now(WIB).strftime("%Y-%m-%d %H:%M:%S")


# ─────────────────────────────────────────────────────────────
# PAPER TRADING — AUTO-LOGGER
# ─────────────────────────────────────────────────────────────

def add_if_not_active(
    ticker: str,
    entry: float,
    tp: float,
    sl: float,
    score: int = None,
    rsi: float = None,
    smart_money: bool = False,
    signal_reason: list = None,
) -> bool:
    """
    Tambahkan trade ke paper book HANYA jika ticker belum ada di active.
    Return True jika berhasil ditambahkan, False jika sudah ada.
    """
    data = _load_data()
    active_tickers = {t.get("ticker", "").upper() for t in data["active"]}
    clean = ticker.split(".")[0].upper()

    if clean in active_tickers:
        return False

    data["active"].append({
        "ticker":        clean,
        "entry":         round(float(entry), 2),
        "tp":            round(float(tp), 2),
        "sl":            round(float(sl), 2),
        "score":         score,
        "rsi":           round(float(rsi), 2) if rsi and not math.isnan(float(rsi)) else None,
        "smart_money":   smart_money,
        "signal_reason": signal_reason or [],
        "peak_price":    round(float(entry), 2),
        "date_opened":   _now_str(),
    })
    _save_data(data)
    print(f"  [PAPER] 📋 Trade baru: {clean} | Entry {entry:.0f} | TP {tp:.0f} | SL {sl:.0f}")
    return True


def check_and_close(ticker: str, current_price: float) -> str:
    """
    Periksa apakah active trade untuk ticker hit TP atau SL.
    Returns: "WIN" | "LOSS" | "ACTIVE" | "NOT_FOUND"
    """
    data = _load_data()
    clean = ticker.split(".")[0].upper()

    for i, trade in enumerate(data["active"]):
        if trade.get("ticker", "").upper() != clean:
            continue

        tp = trade.get("tp")
        sl = trade.get("sl")
        entry = trade.get("entry", current_price)

        # Update peak price
        if current_price > trade.get("peak_price", 0):
            data["active"][i]["peak_price"] = round(current_price, 2)

        if tp is not None and current_price >= tp:
            outcome = "WIN"
        elif sl is not None and current_price <= sl:
            outcome = "LOSS"
        else:
            _save_data(data)
            return "ACTIVE"

        # Close trade
        pl_pct = round(((current_price - entry) / entry) * 100, 2)
        closed = data["active"].pop(i)
        closed["exit_price"]  = round(current_price, 2)
        closed["result"]      = outcome
        closed["pl_pct"]      = pl_pct
        closed["date_closed"] = _now_str()
        data["closed"].append(closed)
        _save_data(data)

        icon = "✅ WIN" if outcome == "WIN" else "❌ LOSS"
        print(f"  [PAPER] {icon}: {clean} ditutup @ {current_price:.0f} | P&L: {pl_pct:+.2f}%")
        return outcome

    return "NOT_FOUND"


def force_close(ticker: str, current_price: float, reason: str = "MANUAL") -> bool:
    """Tutup paksa trade aktif (misalnya sinyal berubah ke SELL)."""
    data = _load_data()
    clean = ticker.split(".")[0].upper()

    for i, trade in enumerate(data["active"]):
        if trade.get("ticker", "").upper() != clean:
            continue

        entry = trade.get("entry", current_price)
        pl_pct = round(((current_price - entry) / entry) * 100, 2)
        outcome = "WIN" if pl_pct > 0 else "LOSS"

        closed = data["active"].pop(i)
        closed["exit_price"]  = round(current_price, 2)
        closed["result"]      = outcome
        closed["pl_pct"]      = pl_pct
        closed["close_reason"] = reason
        closed["date_closed"] = _now_str()
        data["closed"].append(closed)
        _save_data(data)
        print(f"  [PAPER] Force close: {clean} @ {current_price:.0f} ({reason}) | P&L: {pl_pct:+.2f}%")
        return True

    return False


# ─────────────────────────────────────────────────────────────
# STATISTIK & PERFORMA
# ─────────────────────────────────────────────────────────────

def get_stats() -> dict:
    """
    Hitung statistik lengkap paper trading dari trades.json.
    Returns dict siap pakai untuk API/dashboard.
    """
    data = _load_data()
    closed = data.get("closed", [])
    active = data.get("active", [])

    if not closed:
        return {
            "total_closed":  0,
            "total_active":  len(active),
            "wins":          0,
            "losses":        0,
            "winrate":       0.0,
            "avg_pl":        0.0,
            "avg_win":       0.0,
            "avg_loss":      0.0,
            "total_return":  0.0,
            "max_drawdown":  0.0,
            "profit_factor": 0.0,
            "best_trade":    None,
            "worst_trade":   None,
            "active_trades": active,
            "closed_trades": [],
            "equity_curve":  [100.0],
            "by_ticker":     {},
        }

    wins   = [t for t in closed if t.get("result") == "WIN"]
    losses = [t for t in closed if t.get("result") == "LOSS"]

    # Ambil pl_pct — hitung ulang jika tidak ada
    for t in closed:
        if "pl_pct" not in t:
            e = t.get("entry", 0)
            x = t.get("exit_price", 0)
            t["pl_pct"] = round(((x - e) / e) * 100, 2) if e > 0 else 0.0

    pl_list = [t["pl_pct"] for t in closed]

    # Equity curve (mulai dari 100)
    equity = 100.0
    peak   = 100.0
    max_dd = 0.0
    curve  = [round(equity, 2)]
    for t in sorted(closed, key=lambda x: x.get("date_closed", "")):
        equity *= (1 + t["pl_pct"] / 100)
        curve.append(round(equity, 2))
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100
        if dd > max_dd:
            max_dd = dd

    gross_profit = sum(t["pl_pct"] for t in wins) if wins else 0.0
    gross_loss   = abs(sum(t["pl_pct"] for t in losses)) if losses else 0.0
    pf = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None

    # Per-ticker breakdown
    by_ticker: dict = {}
    for t in closed:
        tk = t.get("ticker", "?")
        if tk not in by_ticker:
            by_ticker[tk] = {"wins": 0, "losses": 0, "pl_pcts": []}
        by_ticker[tk]["pl_pcts"].append(t["pl_pct"])
        if t.get("result") == "WIN":
            by_ticker[tk]["wins"] += 1
        else:
            by_ticker[tk]["losses"] += 1

    ticker_stats = {}
    for tk, d in by_ticker.items():
        total = d["wins"] + d["losses"]
        ticker_stats[tk] = {
            "total":    total,
            "wins":     d["wins"],
            "losses":   d["losses"],
            "winrate":  round(d["wins"] / total * 100, 1) if total else 0.0,
            "avg_pl":   round(sum(d["pl_pcts"]) / len(d["pl_pcts"]), 2) if d["pl_pcts"] else 0.0,
        }

    return {
        "total_closed":  len(closed),
        "total_active":  len(active),
        "wins":          len(wins),
        "losses":        len(losses),
        "winrate":       round(len(wins) / len(closed) * 100, 1),
        "avg_pl":        round(sum(pl_list) / len(pl_list), 2),
        "avg_win":       round(sum(t["pl_pct"] for t in wins)   / len(wins),   2) if wins   else 0.0,
        "avg_loss":      round(sum(t["pl_pct"] for t in losses) / len(losses), 2) if losses else 0.0,
        "total_return":  round(equity - 100.0, 2),
        "max_drawdown":  round(max_dd, 2),
        "profit_factor": pf,
        "best_trade":    max(pl_list),
        "worst_trade":   min(pl_list),
        "active_trades": active,
        "closed_trades": sorted(closed, key=lambda x: x.get("date_closed", ""), reverse=True),
        "equity_curve":  curve,
        "by_ticker":     ticker_stats,
    }


# ─────────────────────────────────────────────────────────────
# LEGACY COMPAT (dipertahankan agar tidak break kode lain)
# ─────────────────────────────────────────────────────────────

def add_trade(ticker, entry, tp, sl, date=None):
    data = _load_data()
    data["active"].append({
        "ticker":      ticker.split(".")[0].upper(),
        "entry":       float(entry) if entry else None,
        "tp":          float(tp) if tp else None,
        "sl":          float(sl) if sl else None,
        "date_opened": date or _now_str(),
    })
    _save_data(data)
    return True


def close_trade(ticker, exit_price, result):
    data = _load_data()
    clean = ticker.split(".")[0].upper()
    for i, trade in enumerate(data["active"]):
        if trade.get("ticker", "").upper() == clean:
            closed = data["active"].pop(i)
            closed["exit_price"]  = float(exit_price) if exit_price else None
            closed["result"]      = result
            closed["date_closed"] = _now_str()
            data["closed"].append(closed)
            _save_data(data)
            return True
    return False


def calculate_performance():
    stats = get_stats()
    total = stats["total_closed"]
    print(f"Performance:")
    print(f"Total Trade  : {total}")
    print(f"Winrate      : {stats['winrate']:.1f}%")
    print(f"Total Return : {stats['total_return']:+.2f}%")
    print(f"Max Drawdown : -{stats['max_drawdown']:.2f}%")
    print(f"Profit Factor: {stats['profit_factor'] or 'N/A'}")


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
