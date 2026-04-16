"""
tuner.py — Parameter Grid Generator & Auto-Tuner
==================================================
Menghasilkan semua kombinasi parameter untuk RSI dan Moving Average
dan menjalankan backtest otomatis untuk menemukan parameter terbaik.

Cara pakai:
    from tuner import get_parameter_grid, auto_tune

    # Hanya grid
    for params in get_parameter_grid():
        print(params)

    # Auto-tune + cetak top 3
    results = auto_tune("BBCA.JK", top_n=3)

Atau jalankan langsung:
    python tuner.py
"""

import json
import os
import time
from itertools import product

# ─────────────────────────────────────────────────────────────
# KONSTANTA
# ─────────────────────────────────────────────────────────────

BEST_PARAMS_FILE = "best_params.json"

# ─────────────────────────────────────────────────────────────
# PARAMETER GRID
# ─────────────────────────────────────────────────────────────

RSI_PERIODS = [7, 14, 21]

MA_PAIRS = [
    (10, 20),
    (20, 50),
    (50, 100),
]


# ─────────────────────────────────────────────────────────────
# FUNGSI UTAMA
# ─────────────────────────────────────────────────────────────

def get_parameter_grid(
    rsi_periods: list = None,
    ma_pairs: list = None,
) -> list[dict]:
    """
    Hasilkan semua kombinasi parameter RSI × MA.

    Args:
        rsi_periods : List periode RSI. Default: [7, 14, 21].
        ma_pairs    : List tuple (ma_short, ma_long). Default: [(10,20), (20,50), (50,100)].

    Returns:
        List of dict, masing-masing berisi:
            {"rsi": int, "ma_short": int, "ma_long": int}

    Raises:
        ValueError: Jika ma_short >= ma_long pada salah satu pasangan.
    """
    if rsi_periods is None:
        rsi_periods = RSI_PERIODS
    if ma_pairs is None:
        ma_pairs = MA_PAIRS

    # Validasi: ma_short harus lebih kecil dari ma_long
    for ma_short, ma_long in ma_pairs:
        if ma_short >= ma_long:
            raise ValueError(
                f"MA pair tidak valid: ma_short ({ma_short}) harus < ma_long ({ma_long})."
            )

    grid = [
        {"rsi": rsi, "ma_short": ma_short, "ma_long": ma_long}
        for rsi, (ma_short, ma_long) in product(rsi_periods, ma_pairs)
    ]

    return grid


# ─────────────────────────────────────────────────────────────
# AUTO-TUNE
# ─────────────────────────────────────────────────────────────

def auto_tune(
    ticker: str,
    rsi_periods: list = None,
    ma_pairs: list = None,
    top_n: int = 3,
) -> list[dict]:
    """
    Jalankan backtest untuk semua kombinasi parameter dan kembalikan
    parameter terbaik berdasarkan profit tertinggi.

    Args:
        ticker      : Kode saham, contoh "BBCA.JK".
        rsi_periods : List periode RSI. Default: [7, 14, 21].
        ma_pairs    : List tuple (ma_short, ma_long). Default grid.
        top_n       : Jumlah kombinasi terbaik yang dikembalikan. Default 3.

    Returns:
        List of dict (urutan profit tertinggi), masing-masing berisi:
            {
                "rank":         int,
                "params":       {"rsi_period": int, "ma_short": int, "ma_long": int},
                "total_trade":  int,
                "winrate":      float,   # dalam %
                "total_return": float,   # dalam %
            }
    """
    from backtest import run_backtest_with_params  # import di sini agar tidak circular

    grid = get_parameter_grid(rsi_periods=rsi_periods, ma_pairs=ma_pairs)
    total = len(grid)

    print(f"\n{'='*55}")
    print(f"  AUTO-TUNE: {ticker.split('.')[0]}  |  {total} kombinasi parameter")
    print(f"{'='*55}")

    results = []
    for i, p in enumerate(grid, 1):
        print(f"  [{i:>2}/{total}] RSI={p['rsi']:>2} | MA({p['ma_short']:>3},{p['ma_long']:>3}) ... ", end="", flush=True)
        try:
            r = run_backtest_with_params(
                ticker,
                rsi_period=p["rsi"],
                ma_short=p["ma_short"],
                ma_long=p["ma_long"],
            )
            results.append({
                "params": {
                    "rsi_period": p["rsi"],
                    "ma_short":   p["ma_short"],
                    "ma_long":    p["ma_long"],
                },
                "total_trade":  r["total_trade"],
                "winrate":      r["winrate"],
                "total_return": r["total_return"],
            })
            print(f"trade={r['total_trade']} | winrate={r['winrate']:.1f}% | return={r['total_return']:.2f}%")
        except Exception as exc:
            print(f"ERROR: {exc}")

    # Urutkan: profit (total_return) tertinggi → winrate tertinggi → jumlah trade terbanyak
    results.sort(key=lambda x: (x["total_return"], x["winrate"], x["total_trade"]), reverse=True)

    # Tambahkan rank
    top = []
    for rank, entry in enumerate(results[:top_n], 1):
        top.append({"rank": rank, **entry})

    # Cetak ringkasan top N
    print(f"\n{'='*55}")
    print(f"  TOP {top_n} PARAMETER TERBAIK — {ticker.split('.')[0]}")
    print(f"{'='*55}")
    for entry in top:
        p = entry["params"]
        print(
            f"  #{entry['rank']}  RSI={p['rsi_period']:>2} | MA({p['ma_short']:>3},{p['ma_long']:>3})"
            f"  |  Trade={entry['total_trade']:>2}"
            f"  |  Winrate={entry['winrate']:>6.1f}%"
            f"  |  Return={entry['total_return']:>7.2f}%"
        )
    print(f"{'='*55}\n")

    # Simpan parameter #1 ke best_params.json
    if top:
        best = top[0]["params"]
        save_data = {
            "rsi":          best["rsi_period"],
            "ma_short":     best["ma_short"],
            "ma_long":      best["ma_long"],
            "source_ticker": ticker.split(".")[0],
            "winrate":      top[0]["winrate"],
            "total_return": top[0]["total_return"],
            "last_tuned":   time.time(),
        }
        with open(BEST_PARAMS_FILE, "w", encoding="utf-8") as fj:
            json.dump(save_data, fj, indent=4)
        print(f"  [✓] Parameter terbaik disimpan ke {BEST_PARAMS_FILE}")
        print(f"      RSI={save_data['rsi']} | MA({save_data['ma_short']},{save_data['ma_long']})")
        print(f"      Winrate={save_data['winrate']}% | Return={save_data['total_return']}%\n")

    return top


# ─────────────────────────────────────────────────────────────
# LOAD PARAMETER TERBAIK
# ─────────────────────────────────────────────────────────────

# Nilai default fallback jika best_params.json belum ada
_DEFAULT_PARAMS = {"rsi": 14, "ma_short": 20, "ma_long": 50}


def load_best_params() -> dict:
    """
    Muat parameter terbaik dari best_params.json.
    Jika file belum ada, kembalikan default (RSI=14, MA20/50).

    Returns:
        dict dengan key: rsi, ma_short, ma_long
    """
    if not os.path.exists(BEST_PARAMS_FILE):
        return dict(_DEFAULT_PARAMS)

    try:
        with open(BEST_PARAMS_FILE, "r", encoding="utf-8") as fj:
            data = json.load(fj)
        rsi      = int(data.get("rsi",      _DEFAULT_PARAMS["rsi"]))
        ma_short = int(data.get("ma_short", _DEFAULT_PARAMS["ma_short"]))
        ma_long  = int(data.get("ma_long",  _DEFAULT_PARAMS["ma_long"]))
        if ma_short >= ma_long:
            raise ValueError("ma_short >= ma_long")
        return {"rsi": rsi, "ma_short": ma_short, "ma_long": ma_long}
    except Exception as exc:
        print(f"[tuner] Gagal membaca {BEST_PARAMS_FILE}: {exc} — pakai default.")
        return dict(_DEFAULT_PARAMS)


# ─────────────────────────────────────────────────────────────
# DEMO  (python tuner.py)
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    ticker = sys.argv[1] if len(sys.argv) > 1 else "BBCA.JK"

    # Tampilkan grid
    grid = get_parameter_grid()
    print(f"\n{'='*45}")
    print(f"  PARAMETER GRID — {len(grid)} kombinasi")
    print(f"{'='*45}")
    print(f"  RSI periods : {RSI_PERIODS}")
    print(f"  MA pairs    : {MA_PAIRS}")
    print(f"{'='*45}\n")
    for i, params in enumerate(grid, 1):
        print(
            f"  [{i:>2}] RSI: {params['rsi']:>2} | "
            f"MA Short: {params['ma_short']:>3} | "
            f"MA Long: {params['ma_long']:>3}"
        )

    # Jalankan auto-tune
    auto_tune(ticker, top_n=3)
