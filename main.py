import sys
import math
import json
import os
import time
from datetime import datetime, timezone, timedelta

# Import modul internal
from data import get_stock_data
from indicator import calculate_indicators
from ai_analyst import generate_ai_analysis, generate_market_outlook
from notifier import format_telegram_message, send_telegram_message
from scoring import calculate_score
from strategies import multi_strategy_confirmation
from volume_analysis import analyze_volume
from gap_detector import detect_gap
from stock_filter import is_stock_eligible
from stock_list import get_stock_list
from entry_plan import generate_trade_plan
from risk_management import calculate_position_size
from trade_logger import monitor_active_trades
from tuner import load_best_params, auto_tune, BEST_PARAMS_FILE

# Memuat signal.py secara dinamis 
import importlib.util
spec = importlib.util.spec_from_file_location("local_signal", "signal.py")
local_signal = importlib.util.module_from_spec(spec)
sys.modules["local_signal"] = local_signal
spec.loader.exec_module(local_signal)
generate_signal = local_signal.generate_signal

STATE_FILE = "last_signals.json"

def format_volume(vol):
    if vol >= 1_000_000_000:
        return f"{vol/1_000_000_000:.1f}B"
    elif vol >= 1_000_000:
        return f"{vol/1_000_000:.1f}M"
    elif vol >= 1_000:
        return f"{vol/1_000:.1f}K"
    else:
        return f"{vol:.0f}"

def is_market_open():
    """Mengecek apakah saat ini jam aktif bursa (WIB)."""
    wib_tz = timezone(timedelta(hours=7))
    now_wib = datetime.now(wib_tz)
    
    if now_wib.weekday() >= 5:
        return False, now_wib
        
    waktu_sekarang = now_wib.time()
    from datetime import time as dtime
    
    pagi_buka = dtime(9, 0)
    pagi_tutup = dtime(12, 0)
    siang_buka = dtime(13, 30)
    siang_tutup = dtime(16, 0)
    
    if (pagi_buka <= waktu_sekarang <= pagi_tutup) or (siang_buka <= waktu_sekarang <= siang_tutup):
        return True, now_wib
    return False, now_wib

def load_signals():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_signals(data):
    with open(STATE_FILE, "w") as f:
        json.dump(data, f, indent=4)

SIGNALS_FILE = "signals.json"

def get_env_float(name, default):
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        print(f"[CONFIG] {name} tidak valid. Pakai default: {default}")
        return float(default)

TRADE_CAPITAL = get_env_float("TRADE_CAPITAL", 10_000_000)
RISK_PERCENT = get_env_float("RISK_PERCENT", 1)

# Muat parameter terbaik dari best_params.json (fallback: RSI=14, MA 20/50)
_BEST_PARAMS = load_best_params()
print(f"[CONFIG] Parameter aktif: RSI={_BEST_PARAMS['rsi']} | "
      f"MA({_BEST_PARAMS['ma_short']},{_BEST_PARAMS['ma_long']})")

TUNE_INTERVAL_SECONDS = 7 * 24 * 3600  # 1x per minggu
TUNE_TICKER = "BBCA.JK"                 # Saham acuan untuk auto-tune

def save_signals_json(kumpulan_hasil: list):
    """
    Simpan hasil analisis ke signals.json dengan format bersih.
    Overwrite data lama setiap dipanggil.
    """
    wib_tz = timezone(timedelta(hours=7))
    output = []

    def safe_float(value):
        try:
            if value is None:
                return None
            number = float(value)
            if not math.isfinite(number):
                return None
            return round(number, 2)
        except (TypeError, ValueError):
            return None

    def safe_int(value):
        try:
            if value is None:
                return None
            number = float(value)
            if not math.isfinite(number):
                return None
            return int(number)
        except (TypeError, ValueError):
            return None

    for h in kumpulan_hasil:
        price = safe_float(h.get('harga'))

        output.append({
            "ticker":      h.get('ticker'),
            "price":       price,
            "signal":      h.get('signal'),
            "score":       h.get('score'),
            "smart_money": h.get('smart_money', False),
            "gap_up":      h.get('gap_up', False),
            "entry":       safe_float(h.get('entry')),
            "tp":          safe_float(h.get('tp')),
            "sl":          safe_float(h.get('sl')),
            "lot":         safe_int(h.get('lot')),
            "risk_amount": safe_float(h.get('risk_amount')),
            "ai":          h.get('ai_analysis', '-')
        })

    with open(SIGNALS_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    print(f">>> [signals.json] Tersimpan: {len(output)} saham | "
          f"{datetime.now(wib_tz).strftime('%H:%M:%S')} WIB")

def analyze_stock(ticker):
    """
    Memproses kalkulasi 1 saham. Hanya menarik data dan menghitung teknikal,
    tidak lagi mengirim notifikasi langsung secara individu / sendiri-sendiri.
    """
    clean_ticker = ticker.split('.')[0] if '.' in ticker else ticker
    
    print("\n" + "-"*30)
    print(f"[+] Analyze: {ticker}")
    print("-" * 30)
    
    try:
        df = get_stock_data(ticker)
        if df is None:
            print(f"-> [SKIP] Gagal mengambil data.")
            return None

        # Filter kelayakan: harga > 50 dan avg volume > 1 juta
        if not is_stock_eligible(df, ticker):
            return None

        # 2. Hitung indikator teknikal dengan parameter terbaik
        indicators = calculate_indicators(
            df,
            rsi_period=_BEST_PARAMS["rsi"],
            ma_short=_BEST_PARAMS["ma_short"],
            ma_long=_BEST_PARAMS["ma_long"],
        )
        if indicators is None:
            print(f"-> [SKIP] Gagal hitung teknikal.")
            return None

        rsi = indicators['rsi']
        ma20 = indicators['ma20']
        ma50 = indicators['ma50']
        harga = indicators['close_price']

        # Kalkulasi pergeseran Volume (Smart Money Tracker)
        volume_spike, avg_volume, current_volume, smart_money, volume_label, sm_confidence, sm_alasan = analyze_volume(df)

        price_today = df['Close'].iloc[-1]
        price_yesterday = df['Close'].iloc[-2] if len(df) > 1 else price_today
        gap_up, confidence = detect_gap(rsi, ma20, ma50, price_today, price_yesterday, smart_money)

        signal_status, alasan_teknis = generate_signal(
            rsi,
            ma20,
            ma50,
            harga,
            smart_money=smart_money,
            gap_up=gap_up,
            gap_confidence=confidence,
        )
        # Multi-strategy confirmation (bonus score jika 2+ strategi setuju)
        try:
            mc = multi_strategy_confirmation(df)
            mc_bonus  = mc["score_bonus"]
            mc_signal = mc["signal"]
        except Exception:
            mc_bonus  = 0
            mc_signal = "HOLD"

        score, alasan_skoring = calculate_score(
            rsi, ma20, ma50, harga, smart_money, volume_label, gap_up, confidence,
            multi_confirmation_bonus=mc_bonus,
        )

        entry = None
        tp = None
        sl = None
        lot = None
        risk_amount = None

        if signal_status == "BUY":
            high = float(df['High'].iloc[-1])
            low = float(df['Low'].iloc[-1])
            price = float(harga)
            entry, tp, sl = generate_trade_plan(price, high, low, mode="range")

            position = calculate_position_size(
                capital=TRADE_CAPITAL,
                risk_percent=RISK_PERCENT,
                entry=entry,
                stop_loss=sl,
            )
            if position is not None:
                lot, risk_amount = position
        
        rsi_display = f"{rsi:.2f}" if rsi is not None and not math.isnan(rsi) else "N/A"
        print(f"Harga: {harga:.2f} | RSI: {rsi_display}")
        print(f"Sinyal: {signal_status} | Skor: {score} | Multi-Conf: {mc_signal}")

        # Minta analisis AI (Ollama - Mistral)
        print(f"-> [AI] Menghasilkan analisis untuk {clean_ticker}...")
        ai_text = generate_ai_analysis(
            ticker=clean_ticker,
            signal=signal_status,
            rsi=rsi,
            ma20=ma20,
            ma50=ma50,
            harga=harga,
            entry=entry,
            tp=tp,
            sl=sl,
        )
        
        return {
            "ticker": clean_ticker,
            "harga": harga,
            "rsi": rsi,
            "ma20": ma20,
            "ma50": ma50,
            "signal": signal_status,
            "score": score,
            "multi_confirmation": mc_signal,
            "alasan": alasan_skoring,
            "current_volume": current_volume,
            "avg_volume": avg_volume,
            "volume_label": volume_label,
            "smart_money": smart_money,
            "sm_confidence": sm_confidence,
            "sm_alasan": sm_alasan,
            "gap_up": gap_up,
            "confidence": confidence,
            "entry": entry,
            "tp": tp,
            "sl": sl,
            "lot": lot,
            "risk_amount": risk_amount,
            "ai_analysis": ai_text
        }
            
    except Exception as e:
        print(f"\n[!] ERROR pada {ticker}: {str(e)}")
        return None

def check_single_instance():
    """Mencegah bot berjalan di lebih dari 1 terminal (Double Instance)."""
    try:
        import msvcrt
        global _lock_file_handle
        lock_filename = "bot_instance.lock"
        _lock_file_handle = open(lock_filename, 'w')
        msvcrt.locking(_lock_file_handle.fileno(), msvcrt.LK_NBLCK, 1)
    except IOError: 
        print("\n[!] Bot sudah berjalan")
        sys.exit(1)
    except ImportError:
        pass 

def main():
    check_single_instance()
    
    print("\n" + "*"*60)
    print("   MEMULAI BOT ANALISIS SAHAM BANYAK (REAL-TIME BATCH) ")
    print("   Siklus: Non-Stop 5 Menit | Dashboard tetap update saat bursa tutup")
    print("*"*60)
    
    print("\n>>> INFO: Mempersiapkan notifikasi startup...")
    startup_market_open, _ = is_market_open()
    if startup_market_open:
        send_telegram_message("🤖 Bot trading aktif dan berjalan")
    else:
        print(">>> Market tutup. Notifikasi startup Telegram dilewati.")
    
    daftar_saham = get_stock_list()   # 50 saham LQ45 + likuid tinggi
    wib_tz = timezone(timedelta(hours=7))
    total_saham = len(daftar_saham)

    print(f"\n>>> Daftar scanning: {total_saham} saham dimuat dari stock_list.py")
    
    while True:
        now_wib = datetime.now(wib_tz)
        print("\n\n" + "=" * 60)
        print(f"[*] SIKLUS EKSEKUSI BARU | TIMESTAMP: {now_wib.strftime('%H:%M:%S')} WIB")
        print("=" * 60)
        
        last_signals_state = load_signals()
        open_status, current_time = is_market_open()
        
        if not open_status:
            print("\n>>> INFO: Market tutup.")
            print(">>> Mode dashboard aktif: analisa tetap di-update, Telegram tidak dikirim.")
        else:
            print("\n>>> INFO: Market buka. Analisa dan Telegram aktif.")

        # --- AUTO-TUNE BERKALA (1x per minggu) ---
        try:
            _last_tuned = 0.0
            if os.path.exists(BEST_PARAMS_FILE):
                with open(BEST_PARAMS_FILE, "r", encoding="utf-8") as _f:
                    _last_tuned = float(json.load(_f).get("last_tuned", 0.0))
        except Exception:
            _last_tuned = 0.0

        if time.time() - _last_tuned >= TUNE_INTERVAL_SECONDS:
            print("\n" + "="*60)
            print("  Updating strategy parameters...")
            print("="*60)
            try:
                auto_tune(TUNE_TICKER, top_n=3)
                _BEST_PARAMS.update(load_best_params())
                print(f"  [AUTO-TUNE] Selesai. Parameter aktif sekarang: "
                      f"RSI={_BEST_PARAMS['rsi']} | "
                      f"MA({_BEST_PARAMS['ma_short']},{_BEST_PARAMS['ma_long']})")
            except Exception as _tune_err:
                print(f"  [AUTO-TUNE] Gagal: {_tune_err}")
            print("="*60)

        should_scan = True

        if should_scan:
            kumpulan_hasil = []
            skipped_list   = []
            error_list     = []

            # --- FASE 0: Monitoring Trade Aktif ---
            try:
                monitor_active_trades()
            except Exception as e:
                print(f"[!] Error saat memantau trade aktif: {e}")

            # --- FASE 1: Scanning Semua Saham ---
            print(f"\n{'='*60}")
            print(f"  FASE 1 — SCANNING {total_saham} SAHAM")
            print(f"{'='*60}")

            for idx, target_saham in enumerate(daftar_saham, 1):
                clean = target_saham.split('.')[0]
                print(f"\n[{idx:>2}/{total_saham}] Scanning {clean}...", flush=True)

                try:
                    hasil_saham = analyze_stock(target_saham)

                    if hasil_saham is None:
                        skipped_list.append(clean)
                        print(f"  -> [SKIP] {clean} tidak lolos filter atau data error.")
                    else:
                        kumpulan_hasil.append(hasil_saham)
                        sig   = hasil_saham.get('signal', '?')
                        score = hasil_saham.get('score', 0)
                        sm    = 'SM:YES' if hasil_saham.get('smart_money') else 'SM:NO'
                        gu    = 'GU:YES' if hasil_saham.get('gap_up') else 'GU:NO'
                        print(f"  -> [OK] {clean} | Signal:{sig} Score:{score} {sm} {gu}")

                except Exception as e:
                    error_list.append(clean)
                    print(f"  -> [ERROR] {clean}: {str(e)}")
                    continue

            # Ringkasan hasil scanning
            print(f"\n{'='*60}")
            print(f"  HASIL SCANNING SELESAI")
            print(f"  Total   : {total_saham} saham")
            print(f"  Berhasil: {len(kumpulan_hasil)} saham")
            print(f"  Skip    : {len(skipped_list)} saham" +
                  (f" ({', '.join(skipped_list)})" if skipped_list else ""))
            print(f"  Error   : {len(error_list)} saham" +
                  (f" ({', '.join(error_list)})" if error_list else ""))
            print(f"{'='*60}")
            
            # --- FASE 2: Perangkingan Top 5 ---
            if kumpulan_hasil:
                # Sort 3 kunci:
                #  1. score         DESC (semakin tinggi makin atas)
                #  2. smart_money   True didahulukan (True > False)
                #  3. gap_up        True didahulukan (True > False)
                kumpulan_hasil.sort(
                    key=lambda x: (
                        x.get("score", 0),
                        1 if x.get("smart_money") else 0,
                        1 if x.get("gap_up") else 0,
                    ),
                    reverse=True
                )

                top_5 = kumpulan_hasil[:5]

                # ── Print Ranking ──────────────────────────────────────
                RANK_MEDAL = {1: "[#1]", 2: "[#2]", 3: "[#3]", 4: "[#4]", 5: "[#5]"}
                SIG_TAG    = {"BUY": "BUY  ", "SELL": "SELL ", "HOLD": "HOLD "}

                print(f"\n{'='*60}")
                print(f"  FASE 2 -- RANKING TOP {len(top_5)} SAHAM TERBAIK")
                print(f"  Kriteria: Score DESC | Smart Money | Gap Up")
                print(f"{'='*60}")

                for rank, data in enumerate(top_5, 1):
                    medal      = RANK_MEDAL.get(rank, f"[#{rank}]")
                    ticker     = data.get('ticker', '?')
                    signal     = data.get('signal', 'HOLD')
                    sig_tag    = SIG_TAG.get(signal, signal)
                    score      = data.get('score', 0)
                    harga      = data.get('harga', 0)
                    sm         = data.get('smart_money', False)
                    sm_label   = data.get('volume_label', 'NORMAL')
                    gu         = data.get('gap_up', False)
                    gu_conf    = data.get('confidence', 'LOW')
                    rsi_val    = data.get('rsi')
                    rsi_str    = f"{rsi_val:.1f}" if rsi_val is not None and not math.isnan(rsi_val) else "N/A"
                    vol_c      = format_volume(data.get('current_volume', 0))
                    vol_a      = format_volume(data.get('avg_volume', 0))
                    alasan     = data.get('alasan', [])
                    sm_conf    = data.get('sm_confidence', 0.0)
                    entry      = data.get('entry')
                    tp         = data.get('tp')
                    sl         = data.get('sl')
                    lot        = data.get('lot')
                    risk_amt   = data.get('risk_amount')

                    sm_str  = f"YES ({sm_label}, {sm_conf:.0%})" if sm else "NO"
                    gu_str  = f"YES ({gu_conf})"                 if gu else "NO"

                    print(f"\n  {medal} {ticker:<6}  |  Signal: {sig_tag}  |  Score: {score}")
                    print(f"  {'-'*53}")
                    print(f"    Harga       : Rp {harga:>10,.2f}")
                    print(f"    RSI         : {rsi_str}")
                    print(f"    Volume      : {vol_c} (avg: {vol_a})")
                    print(f"    Smart Money : {sm_str}")
                    print(f"    Gap Up      : {gu_str}")
                    if entry is not None and tp is not None and sl is not None:
                        print(f"    Entry Plan  : Entry {entry:,.2f} | TP {tp:,.2f} | SL {sl:,.2f}")
                    if lot is not None and risk_amt is not None:
                        print(f"    Risk Mgmt   : {lot} lot | Risk Rp {risk_amt:,.0f}")
                    if alasan:
                        print(f"    Alasan      :")
                        for a in alasan:
                            print(f"      (+) {a}")
                    else:
                        print(f"    Alasan      : Kondisi netral")

                print(f"\n{'='*60}")

                # Untuk Telegram & signals.json: gunakan top_5 sebagai target
                target_notifikasi = top_5
                top_3 = top_5   # alias agar kode Fase 3 (Telegram) tetap kompatibel
                
                # --- FASE 3: Broadcast Telegram (Top 5 Digest) ---
                if target_notifikasi and open_status:
                    now_str = now_wib.strftime('%d/%m/%Y %H:%M WIB')

                    print(f"\n>>>> [FASE 3] Menyusun pesan Telegram Top {len(target_notifikasi)} saham...")

                    # ── Header pesan ─────────────────────────────────────
                    pesan_telegram  = "🔥 TOP SAHAM HARI INI 🔥\n"
                    pesan_telegram += f"🕒 {now_str}\n"
                    pesan_telegram += f"📊 Hasil scanning {len(kumpulan_hasil)} saham\n"
                    pesan_telegram += "━" * 30 + "\n\n"

                    # ── Baris per saham ───────────────────────────────────
                    ANGKA = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣"]

                    for i, s in enumerate(target_notifikasi):
                        nomor   = ANGKA[i] if i < len(ANGKA) else f"{i+1}."
                        ticker  = s.get('ticker', '?')
                        signal  = s.get('signal', 'HOLD')
                        score   = s.get('score', 0)
                        harga   = s.get('harga', 0)
                        sm      = s.get('smart_money', False)
                        sm_lbl  = s.get('volume_label', 'NORMAL')
                        sm_conf = s.get('sm_confidence', 0.0)
                        gu      = s.get('gap_up', False)
                        gu_conf = s.get('confidence', 'LOW')
                        rsi_val = s.get('rsi')
                        rsi_str = f"{rsi_val:.1f}" if rsi_val and not math.isnan(rsi_val) else "N/A"
                        alasan  = s.get('alasan', [])
                        entry   = s.get('entry')
                        tp      = s.get('tp')
                        sl      = s.get('sl')
                        lot     = s.get('lot')
                        risk_amt = s.get('risk_amount')

                        # Alasan ringkas (maks 2)
                        alasan_ringkas = " | ".join(alasan[:2]) if alasan else "Kondisi netral"
                        ai_text = s.get('ai_analysis') or alasan_ringkas

                        pesan_telegram += f"{nomor}\n"
                        pesan_telegram += format_telegram_message(
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
                        pesan_telegram += "\n\n"

                    pesan_telegram += "━" * 30 + "\n"

                    # ── Ringkasan AI dari semua Top 5 ─────────────────────
                    print(f"   [AI] Menyusun Market Outlook dari Top {len(top_5)} saham...")

                    def _fmt_rsi(val):
                        try:
                            return f"{float(val):.1f}" if val and not math.isnan(float(val)) else "N/A"
                        except Exception:
                            return "N/A"

                    lines = []
                    for s in top_5:
                        rsi_f = _fmt_rsi(s.get('rsi'))
                        sm_f  = 'YES' if s.get('smart_money') else 'NO'
                        gu_f  = 'YES' if s.get('gap_up') else 'NO'
                        lines.append(
                            f"- {s.get('ticker','?')} | Signal: {s.get('signal','?')} | "
                            f"RSI: {rsi_f} | Score: {s.get('score',0)} | "
                            f"SmartMoney: {sm_f} | GapUp: {gu_f}"
                        )
                    top5_summary = "\n".join(lines)
                    hasil_ai_market = generate_market_outlook(top5_summary)

                    pesan_telegram += f"\n🤖 Kesimpulan AI:\n{hasil_ai_market}\n"
                    pesan_telegram += "\n⚠️ Bukan saran investasi. Gunakan sebagai referensi saja."

                    # ── Kirim ke Telegram ─────────────────────────────────
                    print(f">>>> Mengirim pesan ke Telegram ({len(pesan_telegram)} karakter)...")
                    send_telegram_message(pesan_telegram)
                    print(">>>> Pesan berhasil dikirim.")

                elif target_notifikasi:
                    print(">>>> Market tutup. Telegram dilewati, analisa tetap tersimpan untuk dashboard.")
                else:
                    print(">>>> Tidak ada saham yang berhasil dianalisis. Pesan Telegram dibatalkan.")
                    
            # --- FASE 4: Update JSON Database ---
            # Catat semuanya termasuk yang gurem (tidak masuk top 3) agar anti-spam tetap update
            for h in kumpulan_hasil:
                last_signals_state[h['ticker'] + ".JK"] = h['signal']
            save_signals(last_signals_state)

            # --- FASE 5: Simpan ke signals.json (overwrite setiap loop) ---
            # Hanya timpa jika ada hasil — jaga data lama saat market tutup/scan gagal.
            if kumpulan_hasil:
                save_signals_json(kumpulan_hasil)
            else:
                print(">>> [signals.json] Scan kosong, data terakhir dipertahankan agar dashboard tetap tampil.")
            
        print("\n[TIDUR] Menunggu 5 Menit (300 detik) untuk siklus selanjutnya... (Ctrl+C manual stop)")
        try:
            time.sleep(300)
        except KeyboardInterrupt:
            print("\n\n[!] Eksekusi Shutdown Manual. Bot tidur selamanya.")
            sys.exit(0)

if __name__ == "__main__":
    main()
