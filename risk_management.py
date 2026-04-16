"""
risk_management.py - Helper sizing posisi berdasarkan risiko per trade.
"""

import math


def calculate_position_size(capital, risk_percent, entry, stop_loss):
    """
    Hitung jumlah lot berdasarkan modal, risiko, entry, dan stop loss.

    Logic:
    - risk_amount = capital * (risk_percent / 100)
    - risk_per_share = entry - stop_loss
    - position_size = risk_amount / risk_per_share
    - lot = floor(position_size / 100)

    Returns
    -------
    tuple[int, float]
        lot, risk_amount
    """
    try:
        capital = float(capital)
        risk_percent = float(risk_percent)
        entry = float(entry)
        stop_loss = float(stop_loss)
    except (TypeError, ValueError):
        print("[RISK MANAGEMENT ERROR] Input harus berupa angka.")
        return None

    if not all(math.isfinite(v) for v in [capital, risk_percent, entry, stop_loss]):
        print("[RISK MANAGEMENT ERROR] Input tidak boleh NaN atau infinity.")
        return None

    if capital <= 0:
        print("[RISK MANAGEMENT ERROR] Capital harus lebih besar dari 0.")
        return None

    if risk_percent <= 0:
        print("[RISK MANAGEMENT ERROR] Risk percent harus lebih besar dari 0.")
        return None

    if entry <= stop_loss:
        print("[RISK MANAGEMENT ERROR] Entry harus lebih besar dari stop loss.")
        return None

    risk_amount = capital * (risk_percent / 100)
    risk_per_share = entry - stop_loss

    if risk_per_share <= 0:
        print("[RISK MANAGEMENT ERROR] Risk per share tidak valid.")
        return None

    position_size = risk_amount / risk_per_share
    lot = math.floor(position_size / 100)
    lot = max(lot, 1)

    print("[RISK MANAGEMENT]")
    print(f"Capital        : {capital:.2f}")
    print(f"Risk Percent   : {risk_percent:.2f}%")
    print(f"Risk Amount    : {risk_amount:.2f}")
    print(f"Entry          : {entry:.2f}")
    print(f"Stop Loss      : {stop_loss:.2f}")
    print(f"Risk / Share   : {risk_per_share:.2f}")
    print(f"Position Size  : {position_size:.2f} saham")
    print(f"Lot            : {lot}")

    return lot, round(risk_amount, 2)
