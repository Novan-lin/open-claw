import math

def generate_signal(
    rsi,
    ma20,
    ma50,
    harga,
    smart_money=False,
    gap_up=False,
    gap_confidence="LOW",
):
    """
    Menghasilkan rekomendasi sinyal trading (BUY/SELL/HOLD) 
    berdasarkan input nilai indikator teknikal.
    """
    # Nilai default
    signal = 'HOLD'
    alasan = 'Kriteria BUY ketat belum terpenuhi. Sinyal ditahan untuk mengurangi false signal.'
    
    # Validasi jika nilai RSI tidak ada / NaN karena data kurang panjang
    if rsi is None or math.isnan(rsi):
        alasan = 'Data RSI belum terbentuk karena rentang hari kurang dari 14 hari.'
        print(f"\n[!] Sinyal: {signal} | Alasan: {alasan}")
        return signal, alasan
        
    # SELL tetap sederhana: RSI overbought.
    if rsi > 70:
        signal = 'SELL'
        alasan = f'RSI berada di level Overbought ({rsi:.2f} > 70), indikasi harga saham sudah terlalu mahal (potensi koreksi turun).'
    else:
        valid_ma = (
            ma20 is not None and ma50 is not None
            and not math.isnan(ma20) and not math.isnan(ma50)
        )
        uptrend = valid_ma and ma20 > ma50
        rsi_in_buy_zone = 35 <= rsi <= 60
        gap_ok = str(gap_confidence).upper() in {"MEDIUM", "HIGH"}

        if rsi_in_buy_zone and uptrend and smart_money and gap_ok:
            signal = 'BUY'
            alasan = (
                f'BUY ketat valid: RSI {rsi:.2f} berada di 35-60, '
                f'MA20 ({ma20:.2f}) > MA50 ({ma50:.2f}), Smart Money aktif, '
                f'dan Gap Up confidence {str(gap_confidence).upper()}.'
            )
        else:
            gagal = []
            if not rsi_in_buy_zone:
                gagal.append(f"RSI {rsi:.2f} di luar zona 35-60")
            if not uptrend:
                gagal.append("MA20 belum di atas MA50")
            if not smart_money:
                gagal.append("Smart Money belum aktif")
            if not gap_ok:
                gagal.append(f"Gap Up confidence masih {str(gap_confidence).upper()}")
            alasan = "HOLD: " + "; ".join(gagal) + "."
        
    # Menampilkan hasil menggunakan print
    print("\n[+] Rekomendasi Sinyal Trading:")
    print(f"Harga Terakhir : {harga:.2f}")
    
    # Format MA supaya rapi jika ada nilai NaN
    ma20_str = f"{ma20:.2f}" if (ma20 is not None and not math.isnan(ma20)) else "NaN"
    ma50_str = f"{ma50:.2f}" if (ma50 is not None and not math.isnan(ma50)) else "NaN"
    
    print(f"MA20           : {ma20_str}")
    print(f"MA50           : {ma50_str}")
    print(f"Smart Money    : {'YES' if smart_money else 'NO'}")
    print(f"Gap Up Conf.   : {str(gap_confidence).upper()}")
    print(f"Sinyal         : ** {signal} **")
    print(f"Alasan         : {alasan}")
    print("-" * 50)
    
    return signal, alasan

if __name__ == "__main__":
    # Contoh penggunaan fungsi dengan data manual (dummy data)
    print("\n\n=== UJI COBA BUY KETAT ===")
    generate_signal(
        rsi=48.5,
        ma20=6200,
        ma50=6100,
        harga=6250,
        smart_money=True,
        gap_confidence="MEDIUM",
    )
    
    print("=== UJI COBA KONDISI OVERBOUGHT (RSI > 70) ===")
    generate_signal(rsi=76.2, ma20=6500, ma50=6400, harga=6800)
    
    print("=== UJI COBA KONDISI NETRAL (HOLD) ===")
    generate_signal(rsi=50.0, ma20=6400, ma50=6500, harga=6600)
