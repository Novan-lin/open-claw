import math


def calculate_score(rsi, ma20, ma50, price, smart_money=False, label="NORMAL", gap_up=False, confidence="LOW",
                    multi_confirmation_bonus=0):
    """
    Menghitung besaran skor berdasarkan kekuatan sinyal teknikal dan perilaku aliran dana.

    Args:
        multi_confirmation_bonus : Bonus poin dari multi_strategy_confirmation().
                                   +2 untuk STRONG BUY/SELL, +1 untuk WEAK BUY/SELL.
    """
    score = 0
    alasan = []
    
    # --- 1. Logika RSI -> Memiliki bobot tinggi (+2)
    if rsi is not None and not math.isnan(rsi):
        if rsi < 30:
            score += 2
            alasan.append("RSI oversold")
        elif rsi > 70:
            score += 2
            alasan.append("RSI overbought")
            
    # --- 2. Logika Harga berbanding MA20 -> Bobot tren jangka pendek (+1)
    if price is not None and ma20 is not None and not math.isnan(ma20):
        if price > ma20:
            score += 1
            alasan.append("Harga di atas MA20 (Uptrend Jangka Pendek)")
            
    # --- 3. Logika MA20 berbanding MA50 -> Bobot tren jangka menengah (+1)
    if ma20 is not None and not math.isnan(ma20) and ma50 is not None and not math.isnan(ma50):
        if ma20 > ma50:
            score += 1
            alasan.append("MA20 di atas MA50 (Golden Cross / Uptrend Kuat)")

    # --- 4. Logika Smart Money (Pendeteksi Bandar) ---
    if smart_money:
        score += 2
        alasan.append("Smart money (volume spike + harga naik)")
    elif label == "DISTRIBUSI":
        # Tidak menambah poin skor, tapi memberi peringatan kewaspadaan
        alasan.append("[WARNING] Distribusi Murni (Volume spike saat harga turun)")

    # --- 5. Logika Potensi Gap Up ---
    if gap_up:
        score += 2
        alasan.append("Potensi gap up")
        if confidence == "HIGH":
            score += 1
            alasan.append("Gap Up tingkat keyakinan TINGGI")

    # --- 6. Multi-Strategy Confirmation Bonus ---
    if multi_confirmation_bonus > 0:
        score += multi_confirmation_bonus
        label_bonus = "STRONG" if multi_confirmation_bonus >= 2 else "WEAK"
        alasan.append(f"Multi-Strategy {label_bonus} confirmation (+{multi_confirmation_bonus})")

    # --- Print hasil untuk debugging ---
    print("\n--- DEBUG SCORING ---")
    
    f_rsi = f"{rsi:.2f}" if (rsi is not None and not math.isnan(rsi)) else "NaN"
    f_ma20 = f"{ma20:.2f}" if (ma20 is not None and not math.isnan(ma20)) else "NaN"
    f_ma50 = f"{ma50:.2f}" if (ma50 is not None and not math.isnan(ma50)) else "NaN"
    
    print(f"Input   : RSI={f_rsi}, MA20={f_ma20}, MA50={f_ma50}, Price={price:.2f}")
    print(f"Volume  : Smart Money={smart_money}, Label={label}")
    print(f"Momentum: Gap Up={gap_up}, Confidence={confidence}")
    print(f"Multi-Conf Bonus: +{multi_confirmation_bonus}")
    print(f"Skor Final: {score}")
    print("Detail Poin:")
    if alasan:
        for item in alasan:
            print(f" [+] {item}")
    else:
        print(" [-] Tidak ada kriteria yang mencetak skor.")
    print("---------------------\n")
    
    return score, alasan

if __name__ == "__main__":
    # ------ UJI COBA (DEBUG TEST) ------
    
    print("[TEST 1] Sideways tapi ada Akumulasi Diam-diam")
    s, a = calculate_score(rsi=50, ma20=5100, ma50=5200, price=5050, smart_money=True, label="AKUMULASI")
    
    print("[TEST 2] Market Jatuh Terjun Bebas dengan Volume Raksasa (Guyuran)")
    s, a = calculate_score(rsi=28, ma20=5200, ma50=5300, price=4500, smart_money=False, label="DISTRIBUSI")
