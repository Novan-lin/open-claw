import math
from typing import Tuple, List


def calculate_score(
    rsi,
    ma20,
    ma50,
    price,
    volume_label="NORMAL",
    mc_data=None,
    mode="STRICT",
    atr=None,
    rrr_data=None,
    macd_hist=None,
) -> Tuple[str, int, List[str]]:
    """
    Signal Engine — satu-satunya penentu sinyal akhir BUY / SELL / HOLD.

    Menerima data mentah dari indikator teknikal dan dictionary hasil
    multi_strategy_confirmation(), lalu menghitung skor total dengan
    pembobotan dinamis.

    Skor dibatasi maksimal 10 dan minimal -10.

    Komponen skor (max natural ~12 → dikap 10):
        +2  RSI oversold (< 30 atau dinamis)
        +1  Harga > MA20 (uptrend jangka pendek)
        +1  MA20 > MA50 (uptrend jangka menengah / golden cross)
        +2  Smart Money aktif (volume spike + harga naik)
        +1  Gap Up terdeteksi
        +1  Gap Up HIGH confidence (bonus)
        +2  Multi-Strategy BUY votes (maks 2 vote, +1 per vote)
        +1  MACD histogram momentum bullish (naik dari zona negatif)
        +1  RRR Excellent (> 2.0)
        ─────────────────────────────────────────────────
        -1  per SELL vote (penalti)
        -2  BAD_RRR (RRR < 1.5, penalti tetap)

    Args:
        rsi          : float — Nilai RSI terkini.
        ma20         : float — Moving Average 20.
        ma50         : float — Moving Average 50.
        price        : float — Harga close terakhir.
        volume_label : str   — Label volume (NORMAL / AKUMULASI / DISTRIBUSI).
        mc_data      : dict  — Dictionary dari multi_strategy_confirmation().
        mode         : str   — "STRICT" (BUY jika score >= 6) atau
                               "AGGRESSIVE" (BUY jika score >= 4).
        atr          : float — Average True Range periode 14.
        rrr_data     : dict  — Hasil dari validate_rrr().
        macd_hist    : float — MACD Histogram value terkini (dari calculate_indicators).

    Returns:
        (Final_Signal, Total_Score, Alasan_Lengkap)
    """
    if mc_data is None:
        mc_data = {
            "total_buy_votes": 0,
            "total_sell_votes": 0,
            "smart_money_status": False,
            "gap_up_status": {"detected": False, "confidence": "LOW"},
            "details": {},
        }

    score = 0
    alasan = []

    # --- Ekstrak data dari mc_data ---
    buy_votes    = mc_data.get("total_buy_votes", 0)
    sell_votes   = mc_data.get("total_sell_votes", 0)
    smart_money  = mc_data.get("smart_money_status", False)
    gap_status   = mc_data.get("gap_up_status", {})
    gap_up       = gap_status.get("detected", False)
    gap_conf     = gap_status.get("confidence", "LOW")

    # ─────────────────────────────────────────────────────────
    # 1. RSI oversold  (+2)
    #    Hanya RSI oversold yang memberi poin BUY.
    #    RSI overbought (>70) ditangani di logika SELL di bawah.
    # ─────────────────────────────────────────────────────────
    rsi_valid = rsi is not None and not math.isnan(rsi)
    if rsi_valid and rsi < 30:
        score += 2
        alasan.append(f"RSI oversold ({rsi:.2f} < 30) — potensi reversal bullish (+2)")

    # ─────────────────────────────────────────────────────────
    # 2. Harga vs MA20 — tren jangka pendek  (+1)
    # ─────────────────────────────────────────────────────────
    if price is not None and ma20 is not None and not math.isnan(ma20):
        if price > ma20:
            score += 1
            alasan.append("Harga di atas MA20 — Uptrend Jangka Pendek (+1)")

    # ─────────────────────────────────────────────────────────
    # 3. MA20 vs MA50 — tren jangka menengah  (+1)
    # ─────────────────────────────────────────────────────────
    if (ma20 is not None and not math.isnan(ma20)
            and ma50 is not None and not math.isnan(ma50)):
        if ma20 > ma50:
            score += 1
            alasan.append("MA20 > MA50 — Golden Cross / Uptrend Menengah (+1)")

    # ─────────────────────────────────────────────────────────
    # 4. Smart Money  (+2)
    # ─────────────────────────────────────────────────────────
    if smart_money:
        score += 2
        alasan.append("Smart Money aktif — volume spike + harga naik (+2)")
    elif volume_label == "DISTRIBUSI":
        alasan.append("[WARNING] Distribusi Murni — volume spike saat harga turun")

    # ─────────────────────────────────────────────────────────
    # 5. Gap Up  (+1, +1 extra jika HIGH)
    # ─────────────────────────────────────────────────────────
    if gap_up:
        score += 1
        alasan.append("Gap Up terdeteksi (+1)")
        if gap_conf == "HIGH":
            score += 1
            alasan.append("Gap Up confidence TINGGI (+1)")

    # ─────────────────────────────────────────────────────────
    # 6. Multi-Strategy Votes  (+1 per vote, maks +2)
    #    Smart Money & Gap Up sudah dihitung sendiri di atas,
    #    sehingga vote bonus dibatasi 2 agar tidak terjadi
    #    double-counting.
    # ─────────────────────────────────────────────────────────
    if buy_votes > 0:
        vote_bonus = min(buy_votes, 2)
        score += vote_bonus
        alasan.append(f"Multi-Strategy BUY votes: {buy_votes} (+{vote_bonus})")

    # ─────────────────────────────────────────────────────────
    # 7. MACD Histogram Momentum  (+1)
    #    Histogram naik dari zona negatif → momentum bearish
    #    melemah, bullish reversal mulai terbentuk.
    # ─────────────────────────────────────────────────────────
    macd_valid = macd_hist is not None and not math.isnan(float(macd_hist)) if macd_hist is not None else False
    if macd_valid:
        macd_hist_f = float(macd_hist)
        details = mc_data.get("details", {})
        macd_detail = details.get("macd", {})
        # Ambil sinyal MACD dari multi-strategy confirmation jika tersedia,
        # atau gunakan nilai histogram saja
        if macd_detail.get("signal") == "BUY":
            score += 1
            alasan.append(f"MACD Histogram bullish — momentum bearish mereda (+1)")
        elif macd_hist_f > 0:
            # Histogram positif tapi belum BUY signal → tidak ada bonus
            pass

    # ─────────────────────────────────────────────────────────
    # 8a. SELL penalti — sell votes mendominasi
    # ─────────────────────────────────────────────────────────
    if sell_votes >= 1:
        penalty = sell_votes * 1
        score -= penalty
        alasan.append(f"Multi-Strategy SELL votes: {sell_votes} (-{penalty})")

    # ─────────────────────────────────────────────────────────
    # 8b. RRR — Risk to Reward Ratio
    # ─────────────────────────────────────────────────────────
    if rrr_data is not None:
        rrr_flag = rrr_data.get("flag", "")
        rrr_val = rrr_data.get("rrr")
        if rrr_flag == "BAD_RRR":
            score -= 2
            rrr_display = f"{rrr_val:.2f}" if rrr_val is not None else "0"
            alasan.append(
                f"BAD_RRR: RRR {rrr_display} < 1.5 — ruang profit terbatas (-2)"
            )
        elif rrr_flag == "GOOD_RRR" and rrr_val is not None:
            if rrr_val > 2.0:
                score += 1
                alasan.append(
                    f"RRR Excellent: {rrr_val:.2f} > 2.0 — potensi upside besar (+1)"
                )
            else:
                alasan.append(f"RRR OK: {rrr_val:.2f} (tidak ada penalti/bonus)")

    # ─────────────────────────────────────────────────────────
    # 9. CAP SKOR: maksimal 10, minimal -10
    # ─────────────────────────────────────────────────────────
    score = max(-10, min(10, score))

    # ─────────────────────────────────────────────────────────
    # 10. TENTUKAN SINYAL AKHIR berdasarkan mode
    # ─────────────────────────────────────────────────────────
    mode = mode.upper()
    buy_threshold = 6 if mode == "STRICT" else 4

    # Cek apakah harga masih di atas MA20 (uptrend)
    ma20_valid = ma20 is not None and not math.isnan(ma20)
    price_above_ma20 = ma20_valid and price is not None and price > ma20

    if rsi_valid and rsi > 70 and sell_votes >= 1:
        if price_above_ma20:
            # RSI overbought tapi harga masih di atas MA20 → uptrend kuat, jangan SELL
            final_signal = "HOLD"
            alasan.append(
                f"HOLD: RSI overbought ({rsi:.2f}) tapi harga ({price:.2f}) "
                f"masih di atas MA20 ({ma20:.2f}). "
                f"Uptrend masih kuat, hold dengan trailing stop"
            )
        else:
            # RSI overbought DAN harga sudah di bawah MA20 → konfirmasi SELL
            final_signal = "SELL"
            alasan.append(
                f"SELL: RSI overbought ({rsi:.2f}) + harga ({price:.2f}) "
                f"di bawah MA20 ({ma20:.2f}) + {sell_votes} strategi SELL"
            )
    elif rsi_valid and rsi > 70 and not price_above_ma20:
        # RSI overbought + harga di bawah MA20, meskipun sell_votes == 0
        final_signal = "SELL"
        alasan.append(
            f"SELL: RSI overbought ({rsi:.2f}) + harga ({price:.2f}) "
            f"di bawah MA20 ({ma20:.2f if ma20_valid else 'N/A'})"
        )
    elif rsi_valid and rsi > 70 and price_above_ma20:
        # RSI overbought tapi harga masih di atas MA20
        final_signal = "HOLD"
        alasan.append(
            f"HOLD: RSI overbought ({rsi:.2f}) tapi harga ({price:.2f}) "
            f"masih di atas MA20 ({ma20:.2f}). "
            f"Uptrend masih kuat, hold dengan trailing stop"
        )
    elif score >= buy_threshold:
        final_signal = "BUY"
        alasan.append(
            f"BUY: Skor {score} >= threshold {buy_threshold} (mode {mode})"
        )
    else:
        final_signal = "HOLD"
        alasan.append(
            f"HOLD: Skor {score} < threshold {buy_threshold} (mode {mode})"
        )

    # ─────────────────────────────────────────────────────────
    # DEBUG
    # ─────────────────────────────────────────────────────────
    print("\n--- DEBUG SCORING ---")
    f_rsi  = f"{rsi:.2f}" if rsi_valid else "NaN"
    f_ma20 = f"{ma20:.2f}" if (ma20 is not None and not math.isnan(ma20)) else "NaN"
    f_ma50 = f"{ma50:.2f}" if (ma50 is not None and not math.isnan(ma50)) else "NaN"
    f_price = f"{price:.2f}" if price is not None else "NaN"
    f_atr  = f"{atr:.2f}" if (atr is not None and not math.isnan(atr)) else "NaN"
    f_macd_h = f"{float(macd_hist):.4f}" if macd_valid else "NaN"
    print(f"Input   : RSI={f_rsi}, MA20={f_ma20}, MA50={f_ma50}, Price={f_price}, ATR={f_atr}")
    print(f"MACD    : Histogram={f_macd_h}")
    print(f"Volume  : Smart Money={smart_money}, Label={volume_label}")
    print(f"Gap     : Detected={gap_up}, Confidence={gap_conf}")
    print(f"Votes   : BUY={buy_votes}, SELL={sell_votes}")

    # RRR / Support / Resistance debug
    if rrr_data is not None:
        _s20 = rrr_data.get("support_20")
        _r20 = rrr_data.get("resistance_20")
        _rrr = rrr_data.get("rrr")
        _flg = rrr_data.get("flag", "N/A")
        f_s20 = f"{_s20:.2f}" if _s20 is not None else "N/A"
        f_r20 = f"{_r20:.2f}" if _r20 is not None else "N/A"
        f_rrr = f"{_rrr:.2f}" if _rrr is not None else "N/A"
        print(f"S/R     : Support={f_s20}, Resistance={f_r20}")
        print(f"RRR     : {f_rrr} ({_flg})")
    else:
        print("S/R     : N/A")
        print("RRR     : N/A")

    print(f"Mode    : {mode} (threshold={buy_threshold})")
    print(f"Skor    : {score}/10")
    print(f"Signal  : {final_signal}")
    print("Detail Poin:")
    if alasan:
        for item in alasan:
            print(f"  [+] {item}")
    else:
        print("  [-] Tidak ada kriteria yang mencetak skor.")
    print("---------------------\n")

    return final_signal, score, alasan


# ═════════════════════════════════════════════════════════════
# FINAL GATE — smart_trade_decision
# Dipanggil SETELAH calculate_score() dan generate_trade_plan().
# Menjadi gerbang terakhir sebelum sinyal BUY dieksekusi.
# ═════════════════════════════════════════════════════════════

def smart_trade_decision(
    signal,
    rrr_data=None,
    smart_money=False,
    volume_label="NORMAL",
    entry=None,
    tp=None,
    sl=None,
):
    """
    Final gate sebelum eksekusi trade.

    Tiga pengecekan keras:
      1. RRR >= 1.5   → HARD GATE (BAD_RRR / INVALID = SKIP)
      2. Volume        → HARD GATE (tanpa smart money DAN volume normal = WAIT)
      3. Entry zone    → HARD GATE (entry terlalu dekat TP = SKIP, anti-chasing)

    Args:
        signal       : str   — Sinyal dari calculate_score ("BUY"/"SELL"/"HOLD").
        rrr_data     : dict  — Hasil dari validate_rrr().
        smart_money  : bool  — Apakah Smart Money aktif.
        volume_label : str   — "NORMAL" / "AKUMULASI" / "DISTRIBUSI" / etc.
        entry        : float — Harga entry (dari generate_trade_plan).
        tp           : float — Take Profit.
        sl           : float — Stop Loss.

    Returns:
        dict:
            {
                "decision":        "EXECUTE" | "WAIT" | "SKIP",
                "original_signal": str,
                "alasan":          [str],
            }
    """
    result = {
        "decision": "EXECUTE",
        "original_signal": signal,
        "alasan": [],
    }

    # Hanya berlaku untuk sinyal BUY
    if signal != "BUY":
        result["decision"] = signal  # HOLD / SELL tetap apa adanya
        return result

    blockers = []   # blocker → SKIP
    warnings = []   # warning → jika ≥ 2, WAIT

    # ── Gate 1: RRR Hard Check ─────────────────────────────
    if rrr_data is not None:
        rrr_flag = rrr_data.get("flag", "")
        rrr_val = rrr_data.get("rrr")
        if rrr_flag == "BAD_RRR":
            rrr_display = f"{rrr_val:.2f}" if rrr_val is not None else "0"
            blockers.append(
                f"BLOCK RRR: RRR {rrr_display} < 1.5 — "
                f"risiko terlalu besar vs potensi profit"
            )
        elif rrr_flag == "INVALID":
            blockers.append(
                "BLOCK RRR: Data Support/Resistance tidak valid — "
                "tidak bisa hitung risk/reward"
            )
    else:
        # Tidak ada data RRR sama sekali
        warnings.append("WARNING RRR: Data RRR tidak tersedia")

    # ── Gate 2: Volume Confirmation ────────────────────────
    if not smart_money and volume_label in ("NORMAL", None, ""):
        warnings.append(
            "WARNING Volume: Volume lemah — tidak ada konfirmasi "
            "Smart Money atau volume di atas rata-rata"
        )
    if volume_label == "DISTRIBUSI":
        blockers.append(
            "BLOCK Volume: Distribusi terdeteksi — volume tinggi "
            "tapi harga turun (bandar jualan)"
        )

    # ── Gate 3: Entry Zone — Anti Chasing ──────────────────
    if entry is not None and tp is not None and sl is not None:
        total_range = tp - sl
        upside = tp - entry
        if total_range > 0:
            # entry_ratio: 1.0 = di SL (bagus, upside penuh)
            #              0.0 = di TP (buruk, tidak ada upside)
            entry_ratio = upside / total_range
            if entry_ratio < 0.15:
                blockers.append(
                    f"BLOCK Entry: Sudah terlalu dekat TP — "
                    f"upside hanya {upside:.2f} "
                    f"({entry_ratio * 100:.0f}% dari range). "
                    f"Jangan chasing!"
                )
            elif entry_ratio < 0.30:
                warnings.append(
                    f"WARNING Entry: Entry agak dekat TP — "
                    f"upside {upside:.2f} "
                    f"({entry_ratio * 100:.0f}% dari range)"
                )

    # ── Keputusan Akhir ────────────────────────────────────
    if blockers:
        result["decision"] = "SKIP"
        result["alasan"] = blockers + warnings
    elif len(warnings) >= 2:
        result["decision"] = "WAIT"
        result["alasan"] = warnings
    else:
        result["decision"] = "EXECUTE"
        if warnings:
            result["alasan"] = warnings
        else:
            result["alasan"] = ["✓ Semua gate terpenuhi — trade layak dieksekusi"]

    # ── Debug output ───────────────────────────────────────
    print("\n--- FINAL GATE ---")
    print(f"Signal masuk : {signal}")
    print(f"Keputusan    : {result['decision']}")
    for a in result["alasan"]:
        tag = "[X]" if a.startswith("BLOCK") else "[!]" if a.startswith("WARNING") else "[✓]"
        print(f"  {tag} {a}")
    print("------------------\n")

    return result


if __name__ == "__main__":
    print("[TEST 1] STRICT mode — Smart Money aktif + 2 BUY votes")
    sig, sc, al = calculate_score(
        rsi=45, ma20=5100, ma50=5000, price=5150,
        volume_label="AKUMULASI",
        mc_data={
            "total_buy_votes": 2,
            "total_sell_votes": 0,
            "smart_money_status": True,
            "gap_up_status": {"detected": True, "confidence": "HIGH"},
            "details": {},
        },
        mode="STRICT",
    )
    print(f"=> {sig} | Score: {sc}\n")

    print("[TEST 2] AGGRESSIVE mode — tanpa Smart Money")
    sig, sc, al = calculate_score(
        rsi=28, ma20=5200, ma50=5300, price=4500,
        volume_label="DISTRIBUSI",
        mc_data={
            "total_buy_votes": 1,
            "total_sell_votes": 0,
            "smart_money_status": False,
            "gap_up_status": {"detected": False, "confidence": "LOW"},
            "details": {},
        },
        mode="AGGRESSIVE",
    )
    print(f"=> {sig} | Score: {sc}\n")

    print("[TEST 3] RSI overbought tapi harga MASIH di atas MA20 → harus HOLD")
    sig, sc, al = calculate_score(
        rsi=75, ma20=5000, ma50=5100, price=5200,
        volume_label="NORMAL",
        mc_data={
            "total_buy_votes": 0,
            "total_sell_votes": 2,
            "smart_money_status": False,
            "gap_up_status": {"detected": False, "confidence": "LOW"},
            "details": {},
        },
        mode="STRICT",
        atr=85.0,
    )
    print(f"=> {sig} | Score: {sc}\n")

    print("[TEST 4] RSI overbought DAN harga DI BAWAH MA20 → baru SELL")
    sig, sc, al = calculate_score(
        rsi=75, ma20=5200, ma50=5100, price=5000,
        volume_label="NORMAL",
        mc_data={
            "total_buy_votes": 0,
            "total_sell_votes": 2,
            "smart_money_status": False,
            "gap_up_status": {"detected": False, "confidence": "LOW"},
            "details": {},
        },
        mode="STRICT",
        atr=90.0,
    )
    print(f"=> {sig} | Score: {sc}")
