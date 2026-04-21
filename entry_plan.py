"""
entry_plan.py - Helper sederhana untuk membuat rencana entry trade.
"""

import math


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


def generate_trade_plan(price, high=None, low=None, mode="range", atr=None):
    """
    Hitung entry, take profit, dan stop loss berdasarkan harga saat ini.

    Mode:
    - "atr"     : TP/SL dihitung dari ATR. SL = entry - 1.5×ATR, TP = entry + 2×ATR.
    - "range"   : TP/SL dihitung dari range high-low.
    - "percent" : TP 2% dan SL 1.5% dari price.

    Jika atr tersedia dan mode="range", ATR digunakan sebagai fallback
    ketika range high-low = 0.

    Returns
    -------
    tuple[float, float, float]
        entry, tp, sl dalam format 2 desimal.
    """
    mode = mode.lower()

    if mode == "percent":
        return generate_simple_plan(price)

    # ── Mode ATR: stop loss & take profit berbasis volatilitas ──
    if mode == "atr":
        if atr is None or atr <= 0:
            raise ValueError("Mode 'atr' membutuhkan nilai ATR > 0.")
        entry = price
        sl = entry - (1.5 * atr)
        tp = entry + (2.0 * atr)
        entry, tp, sl = _format_plan(entry, tp, sl)
        _print_plan(entry, tp, sl, mode="atr")
        return entry, tp, sl

    if mode != "range":
        raise ValueError("Mode harus 'range', 'atr', atau 'percent'.")

    if high is None or low is None:
        raise ValueError("Mode 'range' membutuhkan high dan low.")

    price_range = high - low

    if price_range == 0:
        # Fallback ke ATR jika tersedia, otherwise percent
        if atr is not None and atr > 0:
            entry = price
            sl = entry - (1.5 * atr)
            tp = entry + (2.0 * atr)
            entry, tp, sl = _format_plan(entry, tp, sl)
            _print_plan(entry, tp, sl, mode="range→atr-fallback")
            return entry, tp, sl
        return generate_simple_plan(price)

    entry = price
    # Jika ATR tersedia, gunakan untuk SL yang lebih akurat
    if atr is not None and atr > 0:
        sl = entry - (1.5 * atr)
        tp = entry + (2.0 * atr)
    else:
        tp = entry + (price_range * 0.5)
        sl = entry - (price_range * 0.3)

    entry, tp, sl = _format_plan(entry, tp, sl)
    _print_plan(entry, tp, sl, mode="range" + ("+atr" if atr else ""))

    return entry, tp, sl


def validate_rrr(entry, support_20, resistance_20, min_rrr=1.5):
    """
    Validasi Risk-to-Reward Ratio berdasarkan Support/Resistance dinamis.

    Hitung:
        Potensi Profit = Resistance_20 - Entry
        Potensi Risk   = Entry - Support_20
        RRR            = Profit / Risk

    Jika RRR < min_rrr, flag 'BAD_RRR' dikembalikan.

    Args:
        entry          : float — Harga entry.
        support_20     : float — Support dinamis (Rolling Min 20).
        resistance_20  : float — Resistance dinamis (Rolling Max 20).
        min_rrr        : float — Batas minimum RRR. Default 1.5.

    Returns:
        dict:
            {
                "entry":          float,
                "support_20":     float,
                "resistance_20":  float,
                "potensi_profit": float,
                "potensi_risk":   float,
                "rrr":            float | None,
                "flag":           str — "GOOD_RRR" | "BAD_RRR" | "INVALID",
                "alasan":         str,
            }
    """
    result = {
        "entry": entry,
        "support_20": support_20,
        "resistance_20": resistance_20,
        "potensi_profit": None,
        "potensi_risk": None,
        "rrr": None,
        "flag": "INVALID",
        "alasan": "",
    }

    # Validasi input
    def _ok(v):
        return v is not None and math.isfinite(float(v))

    if not all(_ok(v) for v in [entry, support_20, resistance_20]):
        result["alasan"] = "Data Support/Resistance tidak tersedia."
        return result

    potensi_profit = resistance_20 - entry
    potensi_risk = entry - support_20

    result["potensi_profit"] = round(potensi_profit, 2)
    result["potensi_risk"] = round(potensi_risk, 2)

    if potensi_risk <= 0:
        result["flag"] = "INVALID"
        result["alasan"] = (
            f"Entry ({entry:.2f}) <= Support ({support_20:.2f}). "
            f"Risk tidak bisa dihitung."
        )
        print(f"[RRR] {result['alasan']}")
        return result

    if potensi_profit <= 0:
        result["flag"] = "BAD_RRR"
        result["rrr"] = 0.0
        result["alasan"] = (
            f"Entry ({entry:.2f}) >= Resistance ({resistance_20:.2f}). "
            f"Tidak ada ruang profit. RRR=0."
        )
        print(f"[RRR] {result['alasan']}")
        return result

    rrr = potensi_profit / potensi_risk
    result["rrr"] = round(rrr, 2)

    if rrr < min_rrr:
        result["flag"] = "BAD_RRR"
        result["alasan"] = (
            f"RRR {rrr:.2f} < {min_rrr} — ruang naik ({potensi_profit:.2f}) "
            f"lebih sempit dari ruang turun ({potensi_risk:.2f}). "
            f"Trade kurang menguntungkan."
        )
    else:
        result["flag"] = "GOOD_RRR"
        result["alasan"] = (
            f"RRR {rrr:.2f} >= {min_rrr} — Profit ({potensi_profit:.2f}) "
            f"vs Risk ({potensi_risk:.2f}). Trade layak."
        )

    print(f"[RRR] S20={support_20:.2f} | Entry={entry:.2f} | R20={resistance_20:.2f}")
    print(f"[RRR] Profit={potensi_profit:.2f} | Risk={potensi_risk:.2f} | RRR={rrr:.2f} | {result['flag']}")

    return result
