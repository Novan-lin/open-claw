"""
backtest.py - Mesin Backtest Sinyal Trading
============================================
Mensimulasi sinyal BUY dari indikator teknikal (RSI, MA20, MA50),
Smart Money Detection, dan Gap Up Detector pada data historis 6 bulan.

Logika Trade:
    - Entry  : BELI di harga Close hari sinyal BUY
    - Exit   : JUAL di harga Open hari BERIKUTNYA
    - P&L    : ((open_besok - close_hari_ini) / close_hari_ini) * 100

Cara pakai:
    python backtest.py BBCA.JK
    python backtest.py BBCA BBRI TLKM
    python backtest.py --lq45
    python backtest.py --all
    python backtest.py            (uji dengan daftar bawaan)
"""

import sys
import math
import importlib.util
from datetime import datetime, timezone, timedelta

import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator

# ── Muat signal.py secara dinamis (hindari konflik dengan modul bawaan) ──
spec = importlib.util.spec_from_file_location("local_signal", "signal.py")
local_signal = importlib.util.module_from_spec(spec)
sys.modules["local_signal"] = local_signal
spec.loader.exec_module(local_signal)
generate_signal_raw = local_signal.generate_signal

from volume_analysis import analyze_volume
from gap_detector import detect_gap


# ════════════════════════════════════════════════════════════
# HELPER: HITUNG INDIKATOR PER BARIS (tanpa print noise)
# ════════════════════════════════════════════════════════════
def _calc_indicators_silent(
    df_slice: pd.DataFrame,
    rsi_period: int = 14,
    ma_short: int = 20,
    ma_long: int = 50,
) -> dict | None:
    """
    Hitung RSI, MA-short, dan MA-long dari slice DataFrame.
    Parameter periode bisa dikustomisasi.
    Kembalikan dict atau None jika data tidak mencukupi.
    """
    min_rows = max(rsi_period, ma_long) + 1
    if df_slice is None or len(df_slice) < min_rows:
        return None
    try:
        close = df_slice["Close"]
        rsi      = RSIIndicator(close=close, window=rsi_period).rsi().iloc[-1]
        ma_s_val = SMAIndicator(close=close, window=ma_short).sma_indicator().iloc[-1]
        ma_l_val = SMAIndicator(close=close, window=ma_long).sma_indicator().iloc[-1]
        return {
            "rsi":         float(rsi)      if pd.notna(rsi)      else float("nan"),
            "ma20":        float(ma_s_val) if pd.notna(ma_s_val) else float("nan"),
            "ma50":        float(ma_l_val) if pd.notna(ma_l_val) else float("nan"),
            "close_price": float(close.iloc[-1]),
        }
    except Exception:
        return None


def _generate_signal_silent(
    rsi, ma_short_val, ma_long_val, harga,
    smart_money=False, gap_confidence="LOW",
) -> str:
    """
    Tentukan sinyal BUY/SELL/HOLD tanpa print ke terminal.
    Menggunakan logika yang sama dengan signal.py.
    """
    if rsi is None or math.isnan(rsi):
        return "HOLD"
    if rsi > 70:
        return "SELL"

    valid_ma = (
        ma_short_val is not None and ma_long_val is not None
        and not math.isnan(ma_short_val) and not math.isnan(ma_long_val)
    )
    gap_ok = str(gap_confidence).upper() in {"MEDIUM", "HIGH"}
    if 35 <= rsi <= 60 and valid_ma and ma_short_val > ma_long_val and smart_money and gap_ok:
        return "BUY"

    return "HOLD"


def _analyze_volume_silent(df_slice: pd.DataFrame):
    """
    Wrapper analyze_volume yang membuang output print.
    Kembalikan tuple yang sama dengan analyze_volume().
    """
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = analyze_volume(df_slice)
    return result


def _detect_gap_silent(rsi, ma20, ma50, price_today, price_yesterday, smart_money):
    """
    Wrapper detect_gap tanpa print ke terminal.
    """
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = detect_gap(rsi, ma20, ma50, price_today, price_yesterday, smart_money)
    return result


# ════════════════════════════════════════════════════════════
# FUNGSI UTAMA: run_backtest
# ════════════════════════════════════════════════════════════
def run_backtest(
    ticker: str,
    rsi_period: int = 14,
    ma_short: int = 20,
    ma_long: int = 50,
) -> list[dict]:
    """
    Jalankan backtest sinyal BUY untuk satu ticker dengan parameter dinamis.

    Parameters
    ----------
    ticker     : str   — Kode saham, contoh "BBCA.JK"
    rsi_period : int   — Periode RSI. Default 14.
    ma_short   : int   — Periode MA cepat. Default 20.
    ma_long    : int   — Periode MA lambat. Default 50.

    Returns
    -------
    list[dict]
        Daftar setiap trade dengan detail:
        {
            "ticker"       : str,
            "tanggal_beli" : str  (YYYY-MM-DD),
            "harga_beli"   : float  (Close hari sinyal),
            "tanggal_jual" : str  (YYYY-MM-DD),
            "harga_jual"   : float  (Open hari berikutnya),
            "pl_pct"       : float  (profit/loss dalam %),
            "profit"       : bool,
            "rsi"          : float,
            "ma20"         : float,
            "ma50"         : float,
            "smart_money"  : bool,
            "gap_up"       : bool,
        }
    """
    clean = ticker.split(".")[0]
    print(f"\n{'='*60}")
    print(f"  BACKTEST: {ticker}")
    print(f"{'='*60}")

    # ── 1. Ambil data 6 bulan ──────────────────────────────────
    print(f"  [1] Mengunduh data historis 6 bulan untuk {ticker}...")
    try:
        df = yf.download(ticker, period="6mo", interval="1d",
                         auto_adjust=True, progress=False)
    except Exception as e:
        print(f"  [!] Gagal download: {e}")
        return []

    # Flatten MultiIndex jika ada (yfinance kadang hasilkan MultiIndex)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    if df is None or df.empty:
        print(f"  [!] Data kosong untuk {ticker}")
        return []

    df = df.reset_index()          # buat kolom 'Date'
    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    print(f"  [OK] {len(df)} hari data tersedia ({df['Date'].iloc[0]} → {df['Date'].iloc[-1]})")

    # ── 2. Loop mulai dari hari yang cukup untuk semua indikator ──
    trades     = []
    total_days = len(df)
    START_IDX  = max(rsi_period, ma_long) + 1

    print(f"\n  [2] Scanning sinyal BUY dari hari ke-{START_IDX+1} hingga {total_days-1}...")
    print(f"      RSI={rsi_period} | MA_short={ma_short} | MA_long={ma_long}")
    print(f"      (Hari terakhir tidak masuk karena tidak ada Open besok)\n")

    for i in range(START_IDX, total_days - 1):
        # Slice data s/d hari i (inklusif) — simulasi "tidak tahu masa depan"
        df_slice = df.iloc[: i + 1].copy()
        df_slice = df_slice.set_index("Date")

        # ── Hitung indikator dengan parameter dinamis ──
        ind = _calc_indicators_silent(df_slice, rsi_period=rsi_period,
                                      ma_short=ma_short, ma_long=ma_long)
        if ind is None:
            continue

        rsi   = ind["rsi"]
        ma20  = ind["ma20"]
        ma50  = ind["ma50"]
        harga = ind["close_price"]

        # ── Hitung Smart Money ──
        vs, avg_vol, cur_vol, smart_money, vol_label, sm_conf, sm_alasan = \
            _analyze_volume_silent(df_slice)

        # ── Hitung Gap Up ──
        price_today     = float(df_slice["Close"].iloc[-1])
        price_yesterday = float(df_slice["Close"].iloc[-2]) if len(df_slice) > 1 else price_today
        gap_up, gap_conf = _detect_gap_silent(rsi, ma20, ma50,
                                              price_today, price_yesterday,
                                              smart_money)

        # ── Tentukan sinyal ──
        signal = _generate_signal_silent(rsi, ma20, ma50, harga, smart_money, gap_conf)

        # ── Eksekusi trade jika BUY ──
        if signal == "BUY":
            tanggal_beli = df.iloc[i]["Date"]
            harga_beli   = float(df.iloc[i]["Close"])

            tanggal_jual = df.iloc[i + 1]["Date"]
            harga_jual   = float(df.iloc[i + 1]["Open"])

            pl_pct = ((harga_jual - harga_beli) / harga_beli) * 100

            trade = {
                "ticker":        clean,
                "tanggal_beli":  str(tanggal_beli),
                "harga_beli":    round(harga_beli, 2),
                "tanggal_jual":  str(tanggal_jual),
                "harga_jual":    round(harga_jual, 2),
                "pl_pct":        round(pl_pct, 2),
                "profit":        pl_pct > 0,
                "rsi":           round(rsi, 2) if not math.isnan(rsi) else None,
                "ma20":          round(ma20, 2) if not math.isnan(ma20) else None,
                "ma50":          round(ma50, 2) if not math.isnan(ma50) else None,
                "smart_money":   smart_money,
                "gap_up":        gap_up,
                "params": {
                    "rsi_period": rsi_period,
                    "ma_short":   ma_short,
                    "ma_long":    ma_long,
                },
            }
            trades.append(trade)

    return trades


# ════════════════════════════════════════════════════════════
# KALKULASI PERFORMA
# ════════════════════════════════════════════════════════════
def calculate_performance(trades: list[dict]) -> dict:
    """
    Hitung metrik performa dari daftar trade.

    Metrik:
        total_trade   - jumlah trade
        win           - jumlah trade profit
        loss          - jumlah trade rugi
        win_rate      - % trade yang profit
        avg_profit    - rata-rata P&L seluruh trade (%)
        avg_win       - rata-rata P&L trade profit (%)
        avg_loss      - rata-rata P&L trade rugi (%)
        total_return  - akumulasi return (dihitung compound, %)
        max_drawdown  - penurunan maksimum dari puncak ekuitas (%)
        profit_factor - gross profit / gross loss (rasio)
        best_trade    - P&L trade terbaik (%)
        worst_trade   - P&L trade terburuk (%)
    """
    if not trades:
        return {}

    wins   = [t for t in trades if t["profit"]]
    losses = [t for t in trades if not t["profit"]]

    # ── Total Return (compound) ──────────────────────────────
    # Simulasi ekuitas: mulai dari 100, setiap trade berlipat
    equity    = 100.0
    peak      = 100.0
    max_dd    = 0.0
    equity_curve = [equity]

    for t in trades:
        equity *= (1 + t["pl_pct"] / 100)
        equity_curve.append(equity)
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100
        if dd > max_dd:
            max_dd = dd

    total_return = equity - 100.0   # dalam %

    # ── Profit Factor ────────────────────────────────────────
    gross_profit = sum(t["pl_pct"] for t in wins)   if wins   else 0.0
    gross_loss   = abs(sum(t["pl_pct"] for t in losses)) if losses else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

    pl_list = [t["pl_pct"] for t in trades]

    return {
        "total_trade":   len(trades),
        "win":           len(wins),
        "loss":          len(losses),
        "win_rate":      (len(wins) / len(trades)) * 100,
        "avg_profit":    sum(pl_list) / len(pl_list),
        "avg_win":       sum(t["pl_pct"] for t in wins)   / len(wins)   if wins   else 0.0,
        "avg_loss":      sum(t["pl_pct"] for t in losses) / len(losses) if losses else 0.0,
        "total_return":  round(total_return, 2),
        "max_drawdown":  round(max_dd, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "∞",
        "best_trade":    max(pl_list),
        "worst_trade":   min(pl_list),
        "equity_curve":  equity_curve,
    }


# ════════════════════════════════════════════════════════════
# BACKTEST DENGAN PARAMETER DINAMIS
# ════════════════════════════════════════════════════════════
def run_backtest_with_params(
    ticker: str,
    rsi_period: int = 14,
    ma_short: int = 20,
    ma_long: int = 50,
) -> dict:
    """
    Jalankan backtest dengan parameter dinamis dan kembalikan ringkasan performa.

    Args:
        ticker     : Kode saham, contoh "BBCA.JK"
        rsi_period : Periode RSI. Default 14.
        ma_short   : Periode MA cepat. Default 20.
        ma_long    : Periode MA lambat. Default 50.

    Returns:
        {
            "ticker":       str,
            "params":       {"rsi_period": int, "ma_short": int, "ma_long": int},
            "total_trade":  int,
            "winrate":      float,   # dalam %
            "total_return": float,   # dalam %
            "trades":       list[dict],
        }

    Raises:
        ValueError: Jika ma_short >= ma_long.
    """
    if ma_short >= ma_long:
        raise ValueError(
            f"ma_short ({ma_short}) harus lebih kecil dari ma_long ({ma_long})."
        )

    trades = run_backtest(ticker, rsi_period=rsi_period,
                          ma_short=ma_short, ma_long=ma_long)

    if not trades:
        return {
            "ticker":       ticker.split(".")[0],
            "params":       {"rsi_period": rsi_period, "ma_short": ma_short, "ma_long": ma_long},
            "total_trade":  0,
            "winrate":      0.0,
            "total_return": 0.0,
            "trades":       [],
        }

    perf = calculate_performance(trades)

    return {
        "ticker":       ticker.split(".")[0],
        "params":       {"rsi_period": rsi_period, "ma_short": ma_short, "ma_long": ma_long},
        "total_trade":  perf["total_trade"],
        "winrate":      round(perf["win_rate"], 2),
        "total_return": round(perf["total_return"], 2),
        "trades":       trades,
    }


# ════════════════════════════════════════════════════════════
# CETAK RINGKASAN HASIL
# ════════════════════════════════════════════════════════════
def normalize_tickers(tickers: list[str]) -> list[str]:
    """
    Normalisasi input list saham.

    Menerima format ["BBCA", "BBRI.JK"] atau ["BBCA,BBRI"] dan
    mengembalikan list unik dalam format Yahoo Finance, contoh "BBCA.JK".
    """
    normalized = []
    seen = set()

    for raw in tickers:
        if raw is None:
            continue

        for item in str(raw).split(","):
            ticker = item.strip().upper()
            if not ticker:
                continue
            if "." not in ticker:
                ticker += ".JK"
            if ticker in seen:
                continue

            seen.add(ticker)
            normalized.append(ticker)

    return normalized


def flatten_trade_results(all_results: dict[str, list[dict]]) -> list[dict]:
    """
    Gabungkan trade dari semua saham menjadi satu list kronologis.
    """
    all_trades = []

    for ticker, trades in all_results.items():
        clean = ticker.split(".")[0]
        for trade in trades:
            row = dict(trade)
            row.setdefault("ticker", clean)
            all_trades.append(row)

    return sorted(
        all_trades,
        key=lambda t: (
            t.get("tanggal_beli", ""),
            t.get("tanggal_jual", ""),
            t.get("ticker", ""),
        ),
    )


def build_profitability_ranking(all_results: dict[str, list[dict]]) -> list[dict]:
    """
    Buat ranking saham dari paling profitable berdasarkan total return.
    """
    rows = []

    for ticker, trades in all_results.items():
        clean = ticker.split(".")[0]

        if not trades:
            rows.append({
                "ticker":        clean,
                "total_trade":   0,
                "win_rate":      0.0,
                "avg_profit":    0.0,
                "total_return":  None,
                "max_drawdown":  0.0,
                "profit_factor": 0.0,
                "no_trade":      True,
                "_sort_return":  -float("inf"),
            })
            continue

        perf = calculate_performance(trades)
        rows.append({
            "ticker":        clean,
            "total_trade":   perf["total_trade"],
            "win_rate":      perf["win_rate"],
            "avg_profit":    perf["avg_profit"],
            "total_return":  perf["total_return"],
            "max_drawdown":  perf["max_drawdown"],
            "profit_factor": perf["profit_factor"] if isinstance(perf["profit_factor"], float) else float("inf"),
            "no_trade":      False,
            "_sort_return":  perf["total_return"],
        })

    rows.sort(
        key=lambda r: (r["_sort_return"], r["win_rate"], r["avg_profit"]),
        reverse=True,
    )

    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
        row.pop("_sort_return", None)

    return rows


def calculate_combined_performance(all_results: dict[str, list[dict]]) -> dict:
    """
    Hitung total performa gabungan dari semua trade lintas saham.
    """
    all_trades = flatten_trade_results(all_results)
    saham_total = len(all_results)
    saham_aktif = sum(1 for trades in all_results.values() if trades)

    return {
        "saham_total":    saham_total,
        "saham_aktif":    saham_aktif,
        "saham_no_trade": saham_total - saham_aktif,
        "all_trades":     all_trades,
        "performance":    calculate_performance(all_trades) if all_trades else {},
    }


def run_backtest_batch(tickers: list[str]) -> dict:
    """
    Jalankan backtest banyak saham dan kembalikan hasil siap pakai.
    """
    per_stock = run_multi_backtest(tickers)

    return {
        "per_stock":  per_stock,
        "all_trades": flatten_trade_results(per_stock),
        "ranking":    build_profitability_ranking(per_stock),
        "combined":   calculate_combined_performance(per_stock),
    }


def print_summary(ticker: str, trades: list[dict]):
    """Cetak laporan backtest lengkap dengan format standar dan analisa performa."""
    clean = ticker.split(".")[0]
    W     = 60
    SEP   = "─" * W
    DBL   = "═" * W

    print(f"\n\n{DBL}")
    print(f"  📊 BACKTEST RESULT: {clean}")
    print(DBL)

    if not trades:
        print("  ⚠  Tidak ada sinyal BUY yang terdeteksi dalam periode ini.")
        print(DBL)
        return

    perf = calculate_performance(trades)

    # ── ① FORMAT UTAMA (sesuai permintaan) ───────────────────
    total_return_sign = "+" if perf["total_return"] >= 0 else ""
    avg_profit_sign   = "+" if perf["avg_profit"]   >= 0 else ""

    print()
    print(f"  Backtest Result:")
    print(f"  Total Trade  : {perf['total_trade']}")
    print(f"  Winrate      : {perf['win_rate']:.1f}%")
    print(f"  Avg Profit   : {avg_profit_sign}{perf['avg_profit']:.2f}%")
    print(f"  Total Return : {total_return_sign}{perf['total_return']:.2f}%")

    # ── ② ANALISA PERFORMA LENGKAP ────────────────────────────
    print(f"\n  {SEP}")
    print(f"  📈 ANALISA PERFORMA LENGKAP")
    print(f"  {SEP}")

    print(f"  {'Win / Loss':<22}: {perf['win']} ✅  /  {perf['loss']} ❌")
    print(f"  {'Avg Win (trade profit)':<22}: +{perf['avg_win']:.2f}%")
    print(f"  {'Avg Loss (trade rugi)':<22}: {perf['avg_loss']:+.2f}%")
    print(f"  {'Best Trade':<22}: {perf['best_trade']:+.2f}%")
    print(f"  {'Worst Trade':<22}: {perf['worst_trade']:+.2f}%")
    print(f"  {'Max Drawdown':<22}: -{perf['max_drawdown']:.2f}%")
    print(f"  {'Profit Factor':<22}: {perf['profit_factor']}")

    # Penilaian kualitatif
    print(f"\n  {SEP}")
    print(f"  📋 PENILAIAN SINYAL")
    print(f"  {SEP}")

    wr   = perf["win_rate"]
    mdd  = perf["max_drawdown"]
    pf   = perf["profit_factor"] if isinstance(perf["profit_factor"], float) else 999
    tr   = perf["total_return"]

    # Win Rate
    if wr >= 60:
        wr_label = "✅ BAIK  (≥60%)"
    elif wr >= 40:
        wr_label = "⚠️  SEDANG (40-60%)"
    else:
        wr_label = "❌ RENDAH (<40%)"

    # Max Drawdown
    if mdd <= 5:
        mdd_label = "✅ AMAN  (≤5%)"
    elif mdd <= 15:
        mdd_label = "⚠️  MODERAT (5-15%)"
    else:
        mdd_label = "❌ TINGGI (>15%), risiko besar"

    # Profit Factor
    if pf >= 1.5:
        pf_label = "✅ BAGUS  (≥1.5)"
    elif pf >= 1.0:
        pf_label = "⚠️  BREAK-EVEN (1.0-1.5)"
    else:
        pf_label = "❌ MERUGI (<1.0)"

    # Total Return
    if tr >= 10:
        tr_label = "✅ POSITIF BAIK"
    elif tr >= 0:
        tr_label = "⚠️  TIPIS POSITIF"
    else:
        tr_label = "❌ NEGATIF"

    print(f"  Win Rate      : {wr_label}")
    print(f"  Max Drawdown  : {mdd_label}")
    print(f"  Profit Factor : {pf_label}")
    print(f"  Total Return  : {tr_label}")

    # ── ③ TABEL TRADE ─────────────────────────────────────────
    print(f"\n  {SEP}")
    print(f"  DETAIL TRADE")
    print(f"  {SEP}")
    print(f"  {'No':<4} {'Beli':^12} {'Jual':^12} {'Beli Rp':>9} {'Jual Rp':>9}  {'P&L%':>7}  RSI    SM  GU")
    print(f"  {SEP}")

    for idx, t in enumerate(trades, 1):
        icon = "✅" if t["profit"] else "❌"
        sm   = "✔" if t["smart_money"] else "-"
        gu   = "✔" if t["gap_up"]      else "-"
        rsi_s = f"{t['rsi']:.1f}" if t["rsi"] is not None else "N/A"
        print(
            f"  {idx:<4} {t['tanggal_beli']:^12} {t['tanggal_jual']:^12} "
            f"{t['harga_beli']:>9,.0f} {t['harga_jual']:>9,.0f}  "
            f"{t['pl_pct']:>+6.2f}% {icon}  {rsi_s:>5}  {sm:^3} {gu:^3}"
        )

    print(f"  {SEP}")
    print(f"  Keterangan: SM = Smart Money  |  GU = Gap Up Detected")
    print(DBL + "\n")


# ════════════════════════════════════════════════════════════
# PRINT 5 TRADE TERAKHIR
# ════════════════════════════════════════════════════════════
def print_last_trades(trades: list[dict], n: int = 5):
    """
    Cetak N trade terakhir dari daftar trade.
    Hanya menampilkan kolom utama: tanggal, harga, profit (%).
    """
    if not trades:
        return

    last_n = trades[-n:]   # ambil N terakhir
    ticker = last_n[0]["ticker"]
    SEP    = "─" * 60

    print(f"\n  {SEP}")
    print(f"  ⏳ {n} TRADE TERAKHIR  —  {ticker}")
    print(f"  {SEP}")
    print(f"  {'No':<4} {'Tgl Beli':^12} {'Tgl Jual':^12}  "
          f"{'Harga Beli':>10} {'Harga Jual':>10}  {'Profit (%)':>10}")
    print(f"  {SEP}")

    for i, t in enumerate(last_n, 1):
        icon = "✅" if t["profit"] else "❌"
        print(
            f"  {i:<4} {t['tanggal_beli']:^12} {t['tanggal_jual']:^12}  "
            f"{t['harga_beli']:>10,.0f} {t['harga_jual']:>10,.0f}  "
            f"{t['pl_pct']:>+9.2f}% {icon}"
        )

    print(f"  {SEP}\n")


# ════════════════════════════════════════════════════════════
# SIMPAN TRADE LOG KE CSV
# ════════════════════════════════════════════════════════════
def save_trades_csv(all_trades: dict[str, list[dict]], filepath: str = "trades.csv"):
    """
    Simpan semua trade dari semua ticker ke satu file CSV.

    Kolom CSV:
        ticker | tanggal_beli | tanggal_jual | harga_beli | harga_jual
        | profit_pct | profit | rsi | ma20 | ma50 | smart_money | gap_up

    Parameters
    ----------
    all_trades : dict  { "BBCA.JK": [trade, ...], ... }
    filepath   : str   path file CSV output (default: trades.csv)
    """
    import csv
    from datetime import datetime

    rows = []
    for t in flatten_trade_results(all_trades):
        rows.append({
            "ticker":       t.get("ticker"),
            "tanggal_beli": t.get("tanggal_beli"),
            "tanggal_jual": t.get("tanggal_jual"),
            "harga_beli":   t.get("harga_beli"),
            "harga_jual":   t.get("harga_jual"),
            "profit_pct":   t.get("pl_pct"),
            "profit":       "YES" if t.get("profit") else "NO",
            "rsi":          t.get("rsi"),
            "ma20":         t.get("ma20"),
            "ma50":         t.get("ma50"),
            "smart_money":  "YES" if t.get("smart_money") else "NO",
            "gap_up":       "YES" if t.get("gap_up") else "NO",
        })

    if not rows:
        print("  [CSV] Tidak ada trade untuk disimpan.")
        return

    fieldnames = [
        "ticker", "tanggal_beli", "tanggal_jual",
        "harga_beli", "harga_jual", "profit_pct", "profit",
        "rsi", "ma20", "ma50", "smart_money", "gap_up",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  ✔ [CSV] {len(rows)} baris disimpan ke '{filepath}'  |  {ts}")


# ════════════════════════════════════════════════════════════
# MULTI-STOCK BACKTEST ENGINE
# ════════════════════════════════════════════════════════════
def run_multi_backtest(tickers: list[str]) -> dict[str, list[dict]]:
    """
    Jalankan backtest untuk banyak saham sekaligus.

    Parameters
    ----------
    tickers : list[str]
        Daftar kode saham, contoh ["BBCA.JK", "BBRI.JK", ...]

    Returns
    -------
    dict[str, list[dict]]
        { "BBCA.JK": [trade, ...], "BBRI.JK": [trade, ...], ... }
    """
    tickers = normalize_tickers(tickers)
    total   = len(tickers)
    results = {}

    print(f"\n{'═'*70}")
    print(f"  🚀 MULTI-STOCK BACKTEST — {total} SAHAM")
    print(f"{'═'*70}")

    for idx, ticker in enumerate(tickers, 1):
        clean = ticker.split(".")[0]
        print(f"\n  [{idx:>2}/{total}] ▶ Scanning {clean}...", flush=True)
        trades = run_backtest(ticker)
        results[ticker] = trades
        n = len(trades)
        if n:
            perf = calculate_performance(trades)
            print(f"         ✔ {n} trade  |  Win: {perf['win_rate']:.0f}%  |  "
                  f"Return: {perf['total_return']:+.2f}%  |  "
                  f"MaxDD: -{perf['max_drawdown']:.2f}%")
        else:
            print(f"         — Tidak ada sinyal BUY")

    return results


# ════════════════════════════════════════════════════════════
# RANKING SAHAM PALING PROFITABLE
# ════════════════════════════════════════════════════════════
def print_ranking(all_results: dict[str, list[dict]]):
    """
    Cetak ranking saham dari yang paling profitable ke paling tidak.
    Kriteria utama: Total Return (compound), lalu Win Rate, lalu Avg Profit.
    """
    DBL = "═" * 72
    SEP = "─" * 72

    # Hitung performa semua saham
    rows = []
    for ticker, trades in all_results.items():
        clean = ticker.split(".")[0]
        if not trades:
            rows.append({
                "ticker":       clean,
                "total_trade":  0,
                "win_rate":     0.0,
                "avg_profit":   0.0,
                "total_return": -999.0,   # paling bawah ranking
                "max_drawdown": 0.0,
                "profit_factor": 0.0,
                "no_trade":     True,
            })
        else:
            perf = calculate_performance(trades)
            rows.append({
                "ticker":        clean,
                "total_trade":   perf["total_trade"],
                "win_rate":      perf["win_rate"],
                "avg_profit":    perf["avg_profit"],
                "total_return":  perf["total_return"],
                "max_drawdown":  perf["max_drawdown"],
                "profit_factor": perf["profit_factor"] if isinstance(perf["profit_factor"], float) else 999.0,
                "no_trade":      False,
            })

    # Sort: total_return DESC → win_rate DESC → avg_profit DESC
    rows.sort(key=lambda r: (r["total_return"], r["win_rate"], r["avg_profit"]), reverse=True)
    rows = build_profitability_ranking(all_results)

    MEDAL = {1: "🥇", 2: "🥈", 3: "🥉"}

    print(f"\n\n{DBL}")
    print(f"  🏆 RANKING SAHAM — PALING PROFITABLE")
    print(DBL)
    print(f"  {'Rank':<5} {'Ticker':<8} {'Trade':>5}  {'Win%':>6}  "
          f"{'Avg P&L':>8}  {'Total Return':>13}  {'Max DD':>8}  {'PF':>6}")
    print(f"  {SEP}")

    for rank, r in enumerate(rows, 1):
        medal  = MEDAL.get(rank, f"#{rank:>2}")
        ticker = r["ticker"]

        if r["no_trade"]:
            print(f"  {medal:<5} {ticker:<8} {'0':>5}  {'—':>6}  "
                  f"{'—':>8}  {'Tidak ada BUY':>13}  {'—':>8}  {'—':>6}")
            continue

        tr_sign = "+" if r["total_return"] >= 0 else ""
        ap_sign = "+" if r["avg_profit"]   >= 0 else ""
        pf_value = r["profit_factor"]
        pf_disp = "inf" if pf_value == float("inf") else f"{pf_value:.2f}"

        # Warna teks via prefix
        status = "✅" if r["total_return"] > 0 else ("⚠️ " if r["total_return"] == 0 else "❌")

        print(
            f"  {medal:<5} {ticker:<8} {r['total_trade']:>5}  "
            f"{r['win_rate']:>5.1f}%  "
            f"{ap_sign}{r['avg_profit']:>7.2f}%  "
            f"{tr_sign}{r['total_return']:>12.2f}%  "
            f"-{r['max_drawdown']:>7.2f}%  "
            f"{pf_disp:>6}  {status}"
        )

    print(f"  {SEP}")
    print(f"  Keterangan: PF = Profit Factor  |  Max DD = Max Drawdown")
    print(DBL)


# ════════════════════════════════════════════════════════════
# TOTAL PERFORMA GABUNGAN
# ════════════════════════════════════════════════════════════
def print_combined_performance(all_results: dict[str, list[dict]]):
    """
    Cetak statistik performa gabungan dari semua saham.
    Menggabungkan SEMUA trade dari semua ticker menjadi satu pool.
    """
    DBL = "═" * 60

    # Gabungkan semua trade
    all_trades = []
    for trades in all_results.values():
        all_trades.extend(trades)

    saham_total    = len(all_results)
    saham_aktif    = sum(1 for t in all_results.values() if t)
    saham_no_trade = saham_total - saham_aktif
    combined = calculate_combined_performance(all_results)
    all_trades = combined["all_trades"]
    saham_total = combined["saham_total"]
    saham_aktif = combined["saham_aktif"]
    saham_no_trade = combined["saham_no_trade"]

    print(f"\n{DBL}")
    print(f"  📊 TOTAL PERFORMA GABUNGAN")
    print(DBL)
    print(f"  Saham di-scan     : {saham_total}")
    print(f"  Saham ada sinyal  : {saham_aktif}")
    print(f"  Saham tanpa BUY   : {saham_no_trade}")

    if not all_trades:
        print(f"  Tidak ada trade sama sekali dalam periode ini.")
        print(DBL)
        return

    perf = combined["performance"]

    tr_sign = "+" if perf["total_return"] >= 0 else ""
    ap_sign = "+" if perf["avg_profit"]   >= 0 else ""

    print(f"\n  {'─'*48}")
    print(f"  Gabungan Semua Trade:")
    print(f"  {'─'*48}")
    print(f"  Total Trade       : {perf['total_trade']}")
    print(f"  Win / Loss        : {perf['win']} ✅  /  {perf['loss']} ❌")
    print(f"  Win Rate          : {perf['win_rate']:.1f}%")
    print(f"  Avg Profit/Trade  : {ap_sign}{perf['avg_profit']:.2f}%")
    print(f"  Total Return      : {tr_sign}{perf['total_return']:.2f}%")
    print(f"  Max Drawdown      : -{perf['max_drawdown']:.2f}%")
    print(f"  Profit Factor     : {perf['profit_factor']}")
    print(f"  Best Trade        : {perf['best_trade']:+.2f}%")
    print(f"  Worst Trade       : {perf['worst_trade']:+.2f}%")

    # Penilaian
    wr  = perf["win_rate"]
    tr  = perf["total_return"]
    mdd = perf["max_drawdown"]
    pf  = perf["profit_factor"] if isinstance(perf["profit_factor"], float) else 999

    verdict = []
    verdict.append("✅ Win Rate BAIK" if wr >= 50 else "❌ Win Rate RENDAH")
    verdict.append("✅ Profit POSITIF" if tr > 0 else "❌ Total Return NEGATIF")
    verdict.append("✅ Drawdown AMAN" if mdd <= 10 else "⚠️  Drawdown TINGGI")
    verdict.append("✅ Profit Factor BAGUS" if pf >= 1.5 else "❌ Profit Factor LEMAH")

    print(f"\n  {'─'*48}")
    print(f"  Verdict:")
    for v in verdict:
        print(f"    {v}")
    print(DBL + "\n")


# ════════════════════════════════════════════════════════════
# VISUALISASI HASIL BACKTEST
# ════════════════════════════════════════════════════════════
def plot_backtest_results(all_results: dict[str, list[dict]]):
    """
    Tampilkan visualisasi hasil backtest gabungan.

    Membuat dua figure terpisah:
    1. Equity curve pertumbuhan modal.
    2. Profit/loss per trade.
    """
    combined = calculate_combined_performance(all_results)
    all_trades = combined["all_trades"]

    if not all_trades:
        print("  [PLOT] Tidak ada trade untuk divisualisasikan.")
        return

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("  [PLOT] matplotlib belum terpasang. Jalankan: pip install matplotlib")
        return

    perf = combined["performance"]
    equity_curve = perf["equity_curve"]
    trade_numbers = list(range(1, len(all_trades) + 1))
    profit_per_trade = [t["pl_pct"] for t in all_trades]
    labels = [
        f"{t.get('ticker', '?')} {t.get('tanggal_beli', '')}"
        for t in all_trades
    ]

    plt.figure()
    plt.plot(range(len(equity_curve)), equity_curve, marker="o")
    plt.title("Equity Curve Backtest Gabungan")
    plt.xlabel("Trade ke-")
    plt.ylabel("Modal")
    plt.grid(True)
    plt.tight_layout()

    plt.figure()
    plt.bar(trade_numbers, profit_per_trade)
    plt.axhline(0, linewidth=1)
    plt.title("Profit per Trade")
    plt.xlabel("Trade")
    plt.ylabel("Profit / Loss (%)")
    plt.xticks(trade_numbers, labels, rotation=45, ha="right")
    plt.grid(True, axis="y")
    plt.tight_layout()

    plt.show()


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# ENTRY POINT
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
if __name__ == "__main__":
    from stock_list import get_stock_list, get_lq45

    # ── Parse argumen CLI ─────────────────────────────────────────
    # Cara pakai:
    #   python backtest.py                   → 5 saham default
    #   python backtest.py BBCA              → 1 saham spesifik
    #   python backtest.py BBCA BBRI TLKM   → beberapa saham
    #   python backtest.py --lq45            → 25 saham LQ45 core
    #   python backtest.py --all             → 50 saham lengkap

    args = [a.upper() for a in sys.argv[1:]]

    if "--ALL" in args:
        tickers = get_stock_list()
        mode    = f"FULL LIST ({len(tickers)} saham)"
    elif "--LQ45" in args:
        tickers = get_lq45()
        mode    = f"LQ45 CORE ({len(tickers)} saham)"
    elif args:
        tickers = normalize_tickers(args)
        mode = f"CUSTOM ({len(tickers)} saham)"
    else:
        tickers = ["BBCA.JK", "BBRI.JK", "TLKM.JK", "ASII.JK", "GOTO.JK"]
        mode    = f"DEFAULT ({len(tickers)} saham)"

    print(f"\n{'═'*70}")
    print(f"  📈 BACKTEST MULTI-SAHAM — Mode: {mode}")
    print(f"  Saham: {', '.join(t.split('.')[0] for t in tickers)}")
    print(f"{'═'*70}")

    # ── Jalankan multi backtest ───────────────────────────────────
    all_results = run_multi_backtest(tickers)

    # ── Print detail per saham (hanya jika ≤ 10 saham) ───────────
    if len(tickers) <= 10:
        for ticker, trades in all_results.items():
            print_summary(ticker, trades)
            print_last_trades(trades, n=5)

    # ── Simpan CSV ────────────────────────────────────────────────
    save_trades_csv(all_results, filepath="trades.csv")

    # ── Ranking & Combined Performance ───────────────────────────
    print_ranking(all_results)
    print_combined_performance(all_results)
    plot_backtest_results(all_results)
