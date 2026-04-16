"""
send_now.py
────────────────────────────────────────────────────────────
Kirim data analisa top saham ke Telegram sekarang juga,
TANPA cek jam bursa. Baca dari signals.json yang sudah ada.
Jalankan: python send_now.py
"""

import json
import math
import os
import sys
from datetime import datetime, timezone, timedelta

from notifier import format_telegram_message, send_telegram_message

SIGNALS_FILE = "signals.json"


def fmt_rsi(val):
    try:
        return f"{float(val):.1f}" if val is not None and not math.isnan(float(val)) else "N/A"
    except Exception:
        return "N/A"


def load_signals():
    if not os.path.exists(SIGNALS_FILE):
        print(f"[!] {SIGNALS_FILE} tidak ditemukan.")
        print("    Pastikan main.py sudah pernah dijalankan minimal sekali.")
        sys.exit(1)

    with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not data:
        print("[!] signals.json kosong. Tidak ada data untuk dikirim.")
        sys.exit(1)

    return data


def sort_signals(signals):
    return sorted(
        signals,
        key=lambda x: (
            x.get("score", 0),
            1 if x.get("smart_money") else 0,
            1 if x.get("gap_up") else 0,
        ),
        reverse=True,
    )


def build_message(top5, total_scanned):
    wib_tz = timezone(timedelta(hours=7))
    now_str = datetime.now(wib_tz).strftime("%d/%m/%Y %H:%M WIB")

    ANGKA = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

    pesan  = "🔔 DATA ANALISA SAHAM (Manual Kirim)\n"
    pesan += f"🕒 {now_str}\n"
    pesan += f"📊 Dari {total_scanned} saham yang dianalisis\n"
    pesan += "━" * 30 + "\n\n"

    for i, s in enumerate(top5):
        nomor    = ANGKA[i] if i < len(ANGKA) else f"{i+1}."
        ticker   = s.get("ticker") or s.get("ticker", "?")
        signal   = s.get("signal", "HOLD")
        harga    = s.get("harga") or s.get("price")
        sm       = s.get("smart_money", False)
        gu       = s.get("gap_up", False)
        entry    = s.get("entry")
        tp       = s.get("tp")
        sl       = s.get("sl")
        lot      = s.get("lot")
        risk_amt = s.get("risk_amount")
        ai_text  = s.get("ai") or s.get("ai_analysis") or "-"

        pesan += f"{nomor}\n"
        pesan += format_telegram_message(
            ticker=ticker,
            signal=signal,
            harga=harga,
            ai_text=ai_text,
            entry=entry,
            tp=tp,
            sl=sl,
            lot=lot,
            risk_amount=risk_amt,
            smart_money=sm,
            gap_up=gu,
        )
        pesan += "\n\n"

    pesan += "━" * 30 + "\n"
    pesan += "\n⚠️ Bukan saran investasi. Gunakan sebagai referensi saja."
    return pesan


def main():
    print("\n" + "=" * 55)
    print("   SEND NOW — Kirim analisa ke Telegram (tanpa cek bursa)")
    print("=" * 55)

    signals = load_signals()
    sorted_signals = sort_signals(signals)
    top5 = sorted_signals[:5]
    total = len(signals)

    print(f"\n[+] Loaded {total} saham dari {SIGNALS_FILE}")
    print(f"[+] Menyusun pesan Top {len(top5)} saham...\n")

    for i, s in enumerate(top5, 1):
        ticker = s.get("ticker", "?")
        signal = s.get("signal", "HOLD")
        score  = s.get("score", 0)
        sm     = "YES" if s.get("smart_money") else "NO"
        gu     = "YES" if s.get("gap_up") else "NO"
        print(f"  #{i} {ticker:<6} | {signal:<4} | Score:{score} | SM:{sm} | GU:{gu}")

    pesan = build_message(top5, total)
    print(f"\n[+] Pesan siap ({len(pesan)} karakter). Mengirim ke Telegram...")

    ok = send_telegram_message(pesan)
    if ok:
        print("\n[✓] Pesan berhasil dikirim ke Telegram!")
    else:
        print("\n[✗] Gagal mengirim. Cek token/chat ID di config.py")


if __name__ == "__main__":
    main()
