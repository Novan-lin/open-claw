import requests

# Mengambil pengaturan rahasia dari config.py
try:
    import config
    BOT_TOKEN = config.TELEGRAM_BOT_TOKEN
    CHAT_ID = config.TELEGRAM_CHAT_ID
except ImportError:
    BOT_TOKEN = None
    CHAT_ID = None
except AttributeError:
    BOT_TOKEN = None
    CHAT_ID = None

def _format_number(value):
    """Format angka ke bilangan bulat rapi untuk Telegram."""
    if value is None:
        return "-"

    try:
        return f"{float(value):.0f}"
    except (TypeError, ValueError):
        return "-"


def _format_rupiah(value):
    """Format angka risiko dengan separator ribuan Indonesia."""
    if value is None:
        return "-"

    try:
        return f"{float(value):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "-"


def format_telegram_message(
    ticker,
    signal,
    harga,
    ai_text,
    entry=None,
    tp=None,
    sl=None,
    lot=None,
    risk_amount=None,
    smart_money=False,
    gap_up=False,
):
    """
    Menyusun teks sesuai format pesan yang diinginkan sebelum dikirim.
    """
    # Bersihkan ".JK" agar lebih rapi dibaca di Telegram
    clean_ticker = ticker.split('.')[0] if '.' in ticker else ticker
    
    msg = f"Saham: {clean_ticker}\n"
    msg += f"Sinyal: {signal}\n\n"

    if entry is not None or tp is not None or sl is not None:
        msg += f"Entry: {_format_number(entry)}\n"
        msg += f"TP: {_format_number(tp)}\n"
        msg += f"SL: {_format_number(sl)}\n"
        
        if entry is not None and tp is not None and sl is not None and entry != sl:
            try:
                rr = (float(tp) - float(entry)) / (float(entry) - float(sl))
                msg += f"RR: 1 : {rr:.1f}\n\n"
            except Exception:
                msg += "\n"
        else:
            msg += "\n"
    else:
        msg += f"Harga: {_format_number(harga)}\n\n"

    if lot is not None or risk_amount is not None:
        msg += f"Lot: {_format_number(lot)}\n"
        msg += f"⚠️ Risk: Rp {_format_rupiah(risk_amount)}\n\n"

    msg += f"Smart Money: {'🔥' if smart_money else '-'}\n"
    msg += f"Gap Up: {'🚀' if gap_up else '-'}\n\n"
    msg += f"Analisa AI:\n{ai_text}"
    
    return msg

def send_telegram_message(message_string):
    """
    Menerima input "message string" lalu mengirimkannya ke API Telegram.
    Dilengkapi error-handling menyeluruh dan print status.
    """
    # Mengecek apakah config sudah diubah oleh user atau masih bentukan dasar
    if not BOT_TOKEN or BOT_TOKEN == "GANTI_DENGAN_TOKEN_BOT_ANDA":
        print("\n[-] FAILED (Telegram): Token Bot belum diisi di 'config.py'. Pesan tidak dikirim.")
        return False
        
    if not CHAT_ID or CHAT_ID == "GANTI_DENGAN_CHAT_ID_ANDA":
        print("\n[-] FAILED (Telegram): Chat ID belum diisi di 'config.py'. Pesan tidak dikirim.")
        return False

    # Endpoint Resmi Telegram Bot API
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    # Payload
    payload = {
        "chat_id": str(CHAT_ID),
        "text": message_string
    }
    
    print(f"\n[*] Mengirim notifikasi telegram...")
    try:
        response = requests.post(url, json=payload, timeout=20)
        
        # raise_for_status() akan trigger HTTPError jika respon API tidak 200 OK (gagal)
        response.raise_for_status() 
        
        # Jika berhasil melewati baris di atas, berarti sukses
        print("[+] SUCCESS: Pesan notifikasi berhasil terkirim ke Telegram!")
        return True
        
    except requests.exceptions.HTTPError as e:
        print(f"[-] FAILED: Server Telegram menolak request. (Kemungkinan Token/Chat ID salah). Detail: {e}")
        return False
    except requests.exceptions.ConnectionError:
        print("[-] FAILED: Gagal terkoneksi dengan API Telegram. Pastikan internet aktif didukung.")
        return False
    except requests.exceptions.Timeout:
        print("[-] FAILED: Proses pengiriman memakan waktu terlalu lama (Timeout).")
        return False
    except Exception as e:
        print(f"[-] FAILED: Error sistem saat mengirim Telegram: {e}")
        return False

if __name__ == "__main__":
    # Blok ini hanya berjalan jika file notifier.py dijalankan langsung untuk testing
    print("Test: Membentuk Pesan...")
    contoh_pesan = format_telegram_message(
        ticker="BBCA.JK",
        signal="BUY",
        harga=5800.00,
        ai_text="BBCA berada di zona Oversold dengan RSI rendah, potensial untuk swing trade jangka menengah.",
        entry=5800,
        tp=5916,
        sl=5713,
        lot=6,
        risk_amount=100000,
        smart_money=True,
        gap_up=True,
    )
    
    print("\nDraft Pesan:")
    print("---------------------------------")
    print(contoh_pesan)
    print("---------------------------------")
    
    # Coba kirim
    send_telegram_message(contoh_pesan)
