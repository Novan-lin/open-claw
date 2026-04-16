import math

def detect_gap(rsi, ma20, ma50, price_today, price_yesterday, smart_money):
    """
    Mendeteksi anomali Gap-Up (peluang loncatan harga drastis saat pembukaan)
    berdasarkan konfirmasi filter teknikal dan rekam tapak institusi.
    """
    jumlah_kondisi_terpenuhi = 0
    kriteria_list = []
    
    # Kriteria 1: Momentum mulai aktif memanas (Bukan downtrend parah)
    if rsi is not None and not math.isnan(rsi) and rsi > 40:
        jumlah_kondisi_terpenuhi += 1
        kriteria_list.append("[+] RSI stabil di atas 40")
    else:
        kriteria_list.append("[-] RSI lemah (< 40)")
        
    # Kriteria 2: Penutupan saat ini melampaui resisten dinamis MA20
    if price_today is not None and ma20 is not None and not math.isnan(ma20) and price_today > ma20:
        jumlah_kondisi_terpenuhi += 1
        kriteria_list.append("[+] Harga melampaui MA20")
    else:
        kriteria_list.append("[-] Harga masih tersendat di MA20")
        
    # Kriteria 3: Status Bandar masuk barang (Akumulasi Aktif)
    if smart_money == True:
        jumlah_kondisi_terpenuhi += 1
        kriteria_list.append("[+] Konfirmasi Smart Money masuk")
    else:
        kriteria_list.append("[-] Tidak ada dominasi logikal uang besar")
        
    # Kriteria 4: Penutupan Hijau dari hari kemarin
    if price_today is not None and price_yesterday is not None and price_today > price_yesterday:
        jumlah_kondisi_terpenuhi += 1
        kriteria_list.append("[+] Close hari ini lebih tinggi")
    else:
        kriteria_list.append("[-] Close turun/stagnan")

    # --- Penetapan Keputusan Gap Up ---
    gap_up = (jumlah_kondisi_terpenuhi == 4)

    # --- Penetapan Keputusan Nilai Keyakinan (Confidence Level) ---
    if jumlah_kondisi_terpenuhi == 4:
        confidence = "HIGH"
    elif jumlah_kondisi_terpenuhi in [2, 3]:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"
        
    # --- SISTEM CETAK TERMINAL (DEBUG) ---
    print("\n--- DEBUG GAP DETECTOR ---")
    for cek in kriteria_list:
        print(f" {cek}")
        
    print(f"\nSkor Kondisi      : {jumlah_kondisi_terpenuhi} dari 4")
    print(f"Confidence Level  : {confidence}")
    print(f"Status GAP UP Aktif : {gap_up}")
    print("--------------------------\n")
    
    return gap_up, confidence

if __name__ == "__main__":
    # --- MODUL PENGUJIAN SKRIP INTERNAL (MOCK TEST) ---
    
    print("[TEST 1] Kondisi Sempurna (4/4 Kriteria Lolos) = HIGH")
    detect_gap(rsi=50, ma20=5000, ma50=5100, price_today=5200, price_yesterday=4900, smart_money=True)
    
    print("[TEST 2] Kondisi Sedang (Hanya Lolos 2 Kriteria) = MEDIUM")
    # Lolos: RSI > 40 & Harga Naik. Gagal: Dibawah MA20 & Smart money False
    detect_gap(rsi=45, ma20=5300, ma50=5100, price_today=5200, price_yesterday=5100, smart_money=False)
    
    print("[TEST 3] Kondisi Lemah Total/Bearish (0/4 Kriteria) = LOW")
    detect_gap(rsi=28, ma20=5500, ma50=5100, price_today=4800, price_yesterday=4900, smart_money=False)
