"""
entry_plan.py - Helper sederhana untuk membuat rencana entry trade.
"""


def _format_plan(entry, tp, sl):
    """Bulatkan semua angka plan ke 2 desimal."""
    return round(entry, 2), round(tp, 2), round(sl, 2)


def _print_plan(entry, tp, sl, mode):
    """Print hasil trade plan untuk debug."""
    print(f"[ENTRY PLAN - {mode.upper()}]")
    print(f"Entry       : {entry:.2f}")
    print(f"Take Profit : {tp:.2f}")
    print(f"Stop Loss   : {sl:.2f}")


def generate_simple_plan(price):
    """
    Hitung entry, take profit, dan stop loss berbasis persentase.

    Logic:
    - Entry = price
    - TP    = price * 1.02  (2%)
    - SL    = price * 0.985 (1.5%)

    Returns
    -------
    tuple[float, float, float]
        entry, tp, sl dalam format 2 desimal.
    """
    entry = price
    tp = price * 1.02
    sl = price * 0.985

    entry, tp, sl = _format_plan(entry, tp, sl)
    _print_plan(entry, tp, sl, mode="percent")

    return entry, tp, sl


def generate_trade_plan(price, high=None, low=None, mode="range"):
    """
    Hitung entry, take profit, dan stop loss berdasarkan harga saat ini.

    Mode:
    - "range"   : TP/SL dihitung dari range high-low.
    - "percent" : TP 2% dan SL 1.5% dari price.

    Returns
    -------
    tuple[float, float, float]
        entry, tp, sl dalam format 2 desimal.
    """
    mode = mode.lower()

    if mode == "percent":
        return generate_simple_plan(price)

    if mode != "range":
        raise ValueError("Mode harus 'range' atau 'percent'.")

    if high is None or low is None:
        raise ValueError("Mode 'range' membutuhkan high dan low.")

    price_range = high - low

    if price_range == 0:
        return generate_simple_plan(price)

    entry = price
    tp = entry + (price_range * 0.5)
    sl = entry - (price_range * 0.3)

    entry, tp, sl = _format_plan(entry, tp, sl)
    _print_plan(entry, tp, sl, mode="range")

    return entry, tp, sl
