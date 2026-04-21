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
from scoring import calculate_score, smart_trade_decision
from strategies import multi_strategy_confirmation
from volume_analysis import analyze_volume
from gap_detector import detect_gap
from stock_filter import is_stock_eligible
from stock_list import get_stock_list
from entry_plan import generate_trade_plan, validate_rrr
from risk_management import calculate_position_size
from trade_logger import monitor_active_trades
from mtf_analysis import analyze_multi_timeframe
from tuner import load_best_params, auto_tune, BEST_PARAMS_FILE

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
    """
    Cek apakah sekarang jam bursa IDX (Senin-Jumat, 09:00-15:30 WIB).
    Return (True/False, datetime_wib)
    """
    wib_tz = timezone(timedelta(hours=7))
    now_wib = datetime.now(wib_tz)

    # Sabtu=5, Minggu=6
    if now_wib.weekday() >= 5:
        return False, now_wib

    market_open = now_wib.replace(hour=9, minute=0, second=0, microsecond=0)
    market_close = now_wib.replace(hour=15, minute=30, second=0, microsecond=0)

    is_open = market_open <= now_wib <= market_close
    return is_open, now_wib

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
HISTORY_DIR  = "history"            # folder penyimpanan history harian
os.makedirs(HISTORY_DIR, exist_ok=True)

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
SCAN_COOLDOWN = 1800                     # detik (30 menit) — rescan saat market buka
SCAN_COOLDOWN_SHORT = 1800               # detik (30 menit) — cooldown minimum antar scan saham yang sama

# Tracker waktu scan terakhir per ticker (in-memory, reset saat restart)
_last_scanned: dict = {}  # {"BBCA": datetime, ...}

def _get_existing_tickers() -> set:
    """Ambil set ticker yang sudah punya data di signals.json."""
    if not os.path.exists(SIGNALS_FILE):
        return set()
    try:
        with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {s.get("ticker", "").upper() for s in data if s.get("ticker")}
    except Exception:
        return set()


def _prioritize_stocks(daftar_saham: list, last_scanned: dict, force_all=False) -> list:
    """
    Urutkan saham berdasarkan prioritas scanning:
    1. Saham yang belum pernah di-scan (belum ada di signals.json)
    2. Saham yang sudah expired (> SCAN_COOLDOWN sejak terakhir scan)
    3. Saham yang masih fresh (skip)
    
    force_all=True → bypass cooldown, scan semua (untuk first run / uji coba)
    
    Return: list of (ticker, priority_label)
    """
    if force_all:
        return [(t, "FORCE - scan semua") for t in daftar_saham], []

    wib_tz = timezone(timedelta(hours=7))
    now = datetime.now(wib_tz)
    existing = _get_existing_tickers()
    
    unscanned = []   # belum ada di signals.json sama sekali
    expired = []     # sudah ada tapi data sudah > SCAN_COOLDOWN
    fresh = []       # masih dalam cooldown
    
    for ticker in daftar_saham:
        clean = ticker.split('.')[0].upper()
        
        # Cek apakah sudah punya data di signals.json
        has_data = clean in existing
        
        # Cek cooldown dari in-memory tracker
        last_ts = last_scanned.get(clean)
        if last_ts:
            age = (now - last_ts).total_seconds()
            if age < SCAN_COOLDOWN_SHORT:
                fresh.append((ticker, f"fresh ({int(age//60)}m ago)"))
                continue
            elif age < SCAN_COOLDOWN and has_data:
                fresh.append((ticker, f"cooldown ({int(age//3600)}h ago)"))
                continue
        
        if not has_data:
            unscanned.append((ticker, "BARU - belum ada data"))
        else:
            expired.append((ticker, f"expired ({int(age//3600) if last_ts else '?'}h ago)" if last_ts else "no timestamp"))
    
    # Prioritas: unscanned dulu, lalu expired
    return unscanned + expired, fresh


def _is_valid_result(hasil: dict) -> bool:
    """Cek apakah hasil scan punya data esensial (harga tidak null)."""
    harga = hasil.get("harga") or hasil.get("price")
    if harga is None:
        return False
    return True


def _save_incremental(hasil_saham: dict):
    """
    Simpan satu hasil scan langsung ke signals.json (merge).
    Dashboard langsung update tanpa menunggu seluruh siklus selesai.
    TIDAK menimpa data lama jika data baru tidak valid (null semua).
    """
    wib_tz = timezone(timedelta(hours=7))

    # Baca data existing
    existing = []
    if os.path.exists(SIGNALS_FILE):
        try:
            with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = []

    # Merge: ticker baru menimpa yang lama
    merged = {}
    for s in existing:
        tk = s.get("ticker") or s.get("ticker", "")
        if tk:
            merged[tk] = s

    tk = hasil_saham.get("ticker", "")
    if tk:
        # Jangan timpa data lama yang valid dengan data baru yang null
        old = merged.get(tk)
        if old and not _is_valid_result(hasil_saham):
            old_price = old.get("price") or old.get("harga")
            old_rsi = (old.get("_meta") or {}).get("rsi") or old.get("rsi")
            if old_price is not None or old_rsi is not None:
                print(f"  -> [PROTECT] {tk}: data baru null, data lama tetap dipertahankan.")
                return
        merged[tk] = hasil_saham

    # Simpan
    save_signals_json(list(merged.values()))
    print(f"  -> [SAVED] {tk} langsung tersimpan ke signals.json ({len(merged)} total)")


def save_signals_json(kumpulan_hasil: list):
    """
    Simpan hasil analisis ke signals.json dengan format bersih.
    Overwrite data lama setiap dipanggil.
    Juga menyimpan salinan ke folder history harian.
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
        # Support both raw format (from analyze_stock) and serialized format (from signals.json)
        meta = h.get('_meta') or {}

        def pick(raw_key, meta_key=None):
            """Ambil nilai dari raw key, fallback ke _meta, fallback ke serialized top-level key."""
            v = h.get(raw_key)
            if v is not None:
                return v
            mk = meta_key or raw_key
            return meta.get(mk)

        price = safe_float(h.get('harga') or h.get('price'))

        output.append({
            "ticker":      h.get('ticker'),
            "price":       price,
            "signal":      h.get('signal'),
            "score":       h.get('score'),
            "multi_confirmation": h.get('multi_confirmation', 'N/A'),
            "smart_money": h.get('smart_money', False),
            "gap_up":      h.get('gap_up', False),
            "entry":       safe_float(pick('entry')),
            "tp":          safe_float(pick('tp')),
            "sl":          safe_float(pick('sl')),
            "lot":         safe_int(pick('lot')),
            "risk_amount": safe_float(pick('risk_amount')),
            "ai":          h.get('ai_analysis') or h.get('ai') or '-',
            "scanned_at":  h.get('scanned_at') or datetime.now(wib_tz).isoformat(),
            "_meta": {
                "rsi":              pick('rsi'),
                "ma20":             pick('ma20'),
                "ma50":             pick('ma50'),
                "atr":              pick('atr'),
                "support_20":       pick('support_20'),
                "resistance_20":    pick('resistance_20'),
                "volume_label":     pick('volume_label'),
                "sm_confidence":    pick('sm_confidence'),
                "sm_alasan":        pick('sm_alasan'),
                "alasan":           pick('alasan'),
                "gap_confidence":   h.get('confidence') or meta.get('gap_confidence'),
                "mtf":              pick('mtf'),
                "macd":             pick('macd'),
                "macd_hist":        pick('macd_hist'),
                "macd_signal_line": pick('macd_signal_line'),
                "strategy_details": pick('strategy_details'),
            },
            "rrr": h.get('rrr'),
            "gate": h.get('gate'),
        })

    tmp_file = SIGNALS_FILE + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)
    os.replace(tmp_file, SIGNALS_FILE)

    # Simpan ke history harian
    _save_history(output)

    print(f">>> [signals.json] Tersimpan: {len(output)} saham | "
          f"{datetime.now(wib_tz).strftime('%H:%M:%S')} WIB")


def _save_history(signals: list):
    """Simpan salinan ke folder history (merge dengan data hari ini jika ada)."""
    wib_tz = timezone(timedelta(hours=7))
    today = datetime.now(wib_tz).strftime("%Y-%m-%d")
    hist_file = os.path.join(HISTORY_DIR, f"signals_{today}.json")
    ts = datetime.now(wib_tz).isoformat()

    existing = []
    if os.path.exists(hist_file):
        try:
            with open(hist_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                existing = data.get("signals", []) if isinstance(data, dict) else data
        except Exception:
            # File rusak — backup dulu
            backup = hist_file + ".bak"
            try:
                import shutil
                shutil.copy2(hist_file, backup)
                print(f">>> [HISTORY] File rusak, backup: {backup}")
            except Exception:
                pass
            existing = []

    # Merge: data baru menimpa ticker yang sama
    merged = {s.get("ticker"): s for s in existing}
    for s in signals:
        merged[s.get("ticker")] = s
    merged_list = list(merged.values())

    history_data = {
        "date": today,
        "last_updated": ts,
        "total": len(merged_list),
        "signals": merged_list,
    }

    tmp = hist_file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(history_data, f, indent=4, ensure_ascii=False)
    os.replace(tmp, hist_file)
    print(f">>> [HISTORY] Tersimpan: {len(merged_list)} sinyal → {hist_file}")

def _get_previous_signal(ticker_clean):
    """Ambil sinyal & AI analysis terakhir dari signals.json untuk ticker ini."""
    if not os.path.exists(SIGNALS_FILE):
        return None, None
    try:
        with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for s in data:
            tk = s.get("ticker", "").upper()
            if tk == ticker_clean.upper():
                sig = s.get("signal")
                ai = s.get("ai_analysis") or s.get("ai_summary")
                return sig, ai
    except Exception:
        pass
    return None, None


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
        atr = indicators.get('atr')
        support_20 = indicators.get('support_20')
        resistance_20 = indicators.get('resistance_20')

        # Kalkulasi pergeseran Volume (Smart Money Tracker)
        volume_spike, avg_volume, current_volume, smart_money, volume_label, sm_confidence, sm_alasan = analyze_volume(df)

        price_today = df['Close'].iloc[-1]
        price_yesterday = df['Close'].iloc[-2] if len(df) > 1 else price_today
        gap_up, confidence = detect_gap(rsi, ma20, ma50, price_today, price_yesterday, smart_money)

        # Multi-strategy confirmation (raw votes termasuk Smart Money & Gap Up)
        try:
            mc = multi_strategy_confirmation(
                df,
                smart_money=smart_money,
                gap_up=gap_up,
                gap_confidence=confidence,
            )
        except Exception:
            mc = None

        # RRR validation sebelum scoring
        rrr_data = validate_rrr(float(harga), support_20, resistance_20)

        signal_status, score, alasan_skoring = calculate_score(
            rsi, ma20, ma50, harga,
            volume_label=volume_label,
            mc_data=mc,
            mode="STRICT",
            atr=atr,
            rrr_data=rrr_data,
            macd_hist=indicators.get('macd_hist'),
        )

        entry = None
        tp = None
        sl = None
        lot = None
        risk_amount = None

        gate_result = None
        if signal_status == "BUY":
            high = float(df['High'].iloc[-1])
            low = float(df['Low'].iloc[-1])
            price = float(harga)
            entry, tp, sl = generate_trade_plan(price, high, low, mode="range", atr=atr)

            # ── FINAL GATE: cek RRR, volume, entry zone ──
            gate_result = smart_trade_decision(
                signal=signal_status,
                rrr_data=rrr_data,
                smart_money=smart_money,
                volume_label=volume_label,
                entry=entry,
                tp=tp,
                sl=sl,
            )

            if gate_result["decision"] == "EXECUTE":
                position = calculate_position_size(
                    capital=TRADE_CAPITAL,
                    risk_percent=RISK_PERCENT,
                    entry=entry,
                    stop_loss=sl,
                )
                if position is not None:
                    lot, risk_amount = position
            else:
                # Gate menolak — override sinyal ke HOLD
                alasan_skoring.extend(gate_result["alasan"])
                signal_status = "HOLD"
                entry = tp = sl = None
        
        rsi_display = f"{rsi:.2f}" if rsi is not None and not math.isnan(rsi) else "N/A"
        mc_summary = f"BUY:{mc['total_buy_votes']} SELL:{mc['total_sell_votes']}" if mc else "N/A"
        print(f"Harga: {harga:.2f} | RSI: {rsi_display}")
        print(f"Sinyal: {signal_status} | Skor: {score} | Multi-Conf: {mc_summary}")

        # 7. Multi-Timeframe Analysis
        print(f"-> [MTF] Analisa multi-timeframe {clean_ticker}...")
        try:
            mtf = analyze_multi_timeframe(ticker)
        except Exception as e_mtf:
            print(f"-> [MTF] Gagal: {e_mtf}")
            mtf = None

        # Minta analisis AI — skip jika sinyal sama dengan scan sebelumnya
        prev_signal, prev_ai = _get_previous_signal(clean_ticker)
        if prev_signal == signal_status and prev_ai:
            print(f"-> [AI] Skip — sinyal masih {signal_status}, pakai AI analysis sebelumnya")
            ai_text = prev_ai
        else:
            if prev_signal and prev_signal != signal_status:
                print(f"-> [AI] Sinyal berubah {prev_signal} → {signal_status}, regenerate AI...")
            else:
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
                score=score,
                alasan_scoring=alasan_skoring,
                smart_money=smart_money,
                volume_label=volume_label,
                gap_up=gap_up,
                gap_confidence=confidence,
                mtf=mtf,
            )
        
        return {
            "ticker": clean_ticker,
            "harga": harga,
            "rsi": rsi,
            "ma20": ma20,
            "ma50": ma50,
            "atr": atr,
            "support_20": support_20,
            "resistance_20": resistance_20,
            "macd": indicators.get('macd'),
            "macd_hist": indicators.get('macd_hist'),
            "macd_signal_line": indicators.get('macd_signal'),
            "strategy_details": mc.get('details') if mc else None,
            "signal": signal_status,
            "score": score,
            "multi_confirmation": mc_summary,
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
            "rrr": rrr_data,
            "mtf": mtf,
            "ai_analysis": ai_text,
            "gate": gate_result,
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

def load_persistent_cooldown() -> dict:
    """Muat data cooldown dari signals.json agar bot tidak scan ulang semua saham saat restart."""
    cooldown = {}
    if not os.path.exists(SIGNALS_FILE):
        return cooldown
    try:
        with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return cooldown
        for item in data:
            ticker = item.get("ticker")
            scanned_at = item.get("scanned_at", "")
            if ticker and scanned_at:
                try:
                    ts = datetime.fromisoformat(scanned_at)
                    cooldown[ticker] = ts
                except (ValueError, TypeError):
                    continue
    except (json.JSONDecodeError, OSError):
        pass
    if cooldown:
        print(f">>> [COOLDOWN] Dimuat {len(cooldown)} ticker dari signals.json")
    return cooldown


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

    global _last_scanned
    _last_scanned = load_persistent_cooldown()

    _first_run = True   # Siklus pertama selalu scan (untuk testing/startup)

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

        should_scan = open_status or _first_run

        if _first_run and not open_status:
            print("\n>>> [FIRST RUN] Market tutup, tapi siklus pertama tetap scan untuk uji coba.")
        elif not should_scan:
            print("\n>>> [SKIP] Market tutup — scan dilewati untuk hemat resource.")
            print(">>> Dashboard tetap menampilkan data terakhir dari signals.json.")

        if should_scan:
            kumpulan_hasil = []
            skipped_list   = []
            error_list     = []

            # --- FASE 0: Monitoring Trade Aktif ---
            try:
                monitor_active_trades()
            except Exception as e:
                print(f"[!] Error saat memantau trade aktif: {e}")

            # --- FASE 1: Scanning Saham (Prioritas: belum ada data → expired) ---
            print(f"\n{'='*60}")
            print(f"  FASE 1 — SCANNING (SMART PRIORITY)")
            print(f"{'='*60}")

            to_scan, skipped_fresh = _prioritize_stocks(daftar_saham, _last_scanned, force_all=_first_run)

            if skipped_fresh:
                print(f"\n  [INFO] {len(skipped_fresh)} saham di-skip (data masih fresh):")
                for ticker, reason in skipped_fresh[:5]:
                    print(f"    - {ticker.split('.')[0]}: {reason}")
                if len(skipped_fresh) > 5:
                    print(f"    ... dan {len(skipped_fresh) - 5} lainnya")

            if not to_scan:
                print(f"\n  [INFO] Semua {total_saham} saham sudah di-scan dan masih dalam cooldown.")
                print(f"  [INFO] Rescan penuh berikutnya dalam ~{SCAN_COOLDOWN//3600} jam.")
            else:
                scan_total = len(to_scan)
                print(f"\n  [QUEUE] {scan_total} saham perlu di-scan:")
                for i, (ticker, reason) in enumerate(to_scan[:10]):
                    print(f"    {i+1}. {ticker.split('.')[0]} — {reason}")
                if scan_total > 10:
                    print(f"    ... dan {scan_total - 10} lainnya")

            for idx, (target_saham, priority_label) in enumerate(to_scan, 1):
                clean = target_saham.split('.')[0]
                print(f"\n[{idx:>2}/{len(to_scan)}] Scanning {clean} ({priority_label})...", flush=True)

                try:
                    hasil_saham = analyze_stock(target_saham)

                    if hasil_saham is None:
                        skipped_list.append(clean)
                        print(f"  -> [SKIP] {clean} tidak lolos filter atau data error.")
                    else:
                        kumpulan_hasil.append(hasil_saham)
                        _last_scanned[clean] = datetime.now(wib_tz)  # Catat waktu scan
                        sig   = hasil_saham.get('signal', '?')
                        score = hasil_saham.get('score', 0)
                        sm    = 'SM:YES' if hasil_saham.get('smart_money') else 'SM:NO'
                        gu    = 'GU:YES' if hasil_saham.get('gap_up') else 'GU:NO'
                        print(f"  -> [OK] {clean} | Signal:{sig} Score:{score} {sm} {gu}")

                        # Simpan langsung ke signals.json agar dashboard update real-time
                        try:
                            _save_incremental(hasil_saham)
                        except Exception as e_inc:
                            print(f"  -> [WARN] Gagal simpan inkremental: {e_inc}")

                except Exception as e:
                    error_list.append(clean)
                    print(f"  -> [ERROR] {clean}: {str(e)}")
                    continue

            # Ringkasan hasil scanning
            print(f"\n{'='*60}")
            print(f"  HASIL SCANNING SELESAI")
            print(f"  Total list : {total_saham} saham")
            print(f"  Di-scan    : {len(to_scan)} saham")
            print(f"  Berhasil   : {len(kumpulan_hasil)} saham")
            print(f"  Skip(fresh): {len(skipped_fresh)} saham")
            print(f"  Skip(fail) : {len(skipped_list)} saham" +
                  (f" ({', '.join(skipped_list)})" if skipped_list else ""))
            print(f"  Error      : {len(error_list)} saham" +
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

            # --- FASE 5: Simpan ke signals.json (merge dengan data yang sudah ada) ---
            if kumpulan_hasil:
                # Muat data lama dari signals.json dan gabungkan
                existing_signals = []
                if os.path.exists(SIGNALS_FILE):
                    try:
                        with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
                            existing_signals = json.load(f)
                    except Exception:
                        existing_signals = []
                
                # Merge: data baru menimpa ticker yang sama HANYA jika valid
                merged = {}
                for s in existing_signals:
                    tk = s.get("ticker") or s.get("ticker", "")
                    if tk:
                        merged[tk] = s
                for h in kumpulan_hasil:
                    tk = h.get("ticker", "")
                    if tk:
                        old = merged.get(tk)
                        if old and not _is_valid_result(h):
                            # Data baru null, pertahankan data lama
                            old_price = old.get("price") or old.get("harga")
                            if old_price is not None:
                                print(f"  -> [PROTECT] {tk}: data baru null di FASE 5, data lama dipertahankan.")
                                continue
                        merged[tk] = h
                
                # Simpan semua (merged), bukan hanya hasil siklus ini
                save_signals_json(list(merged.values()))
            else:
                print(">>> [signals.json] Scan kosong, data terakhir dipertahankan agar dashboard tetap tampil.")
            
        _first_run = False  # Siklus pertama selesai, selanjutnya ikuti aturan market

        # Tidur: 5 menit saat market buka, 30 menit saat market tutup
        if open_status:
            sleep_sec = 300
            sleep_label = "5 menit"
        else:
            sleep_sec = 1800
            sleep_label = "30 menit (market tutup)"
        print(f"\n[TIDUR] Menunggu {sleep_label} ({sleep_sec} detik) untuk siklus selanjutnya... (Ctrl+C manual stop)")
        try:
            time.sleep(sleep_sec)
        except KeyboardInterrupt:
            print("\n\n[!] Eksekusi Shutdown Manual. Bot tidur selamanya.")
            sys.exit(0)

if __name__ == "__main__":
    main()
