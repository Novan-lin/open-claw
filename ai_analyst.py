import requests
import math
import json
import time

try:
    from config import GROQ_API_KEY
except ImportError:
    GROQ_API_KEY = ""

# Model Groq (untuk analisa fundamental — ultra cepat!)
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# ============================================================
# DATA FUNDAMENTAL PERUSAHAAN
# ============================================================
# Sumber: data publik IDX, laporan keuangan terbaru
FUNDAMENTAL_DATA = {
    "BBCA": {
        "nama": "Bank Central Asia Tbk",
        "sektor": "Keuangan / Perbankan",
        "market_cap": "~Rp 1.200 T",
        "per": "25-28x",
        "pbv": "4.5-5x",
        "roe": "~22%",
        "der": "~5.5x (wajar untuk bank)",
        "dividen_yield": "~1.5%",
        "catatan": "Bank swasta terbesar Indonesia. Pertumbuhan kredit stabil, NIM sehat, NPL rendah. Saham defensif blue-chip."
    },
    "BBRI": {
        "nama": "Bank Rakyat Indonesia Tbk",
        "sektor": "Keuangan / Perbankan",
        "market_cap": "~Rp 750 T",
        "per": "12-15x",
        "pbv": "2.5-3x",
        "roe": "~20%",
        "der": "~5x (wajar untuk bank)",
        "dividen_yield": "~4%",
        "catatan": "Bank BUMN terbesar, fokus mikro dan UMKM. Margin stabil, basis nasabah terluas di Indonesia."
    },
    "BMRI": {
        "nama": "Bank Mandiri Tbk",
        "sektor": "Keuangan / Perbankan",
        "market_cap": "~Rp 550 T",
        "per": "10-13x",
        "pbv": "2-2.5x",
        "roe": "~20%",
        "der": "~5x (wajar untuk bank)",
        "dividen_yield": "~4.5%",
        "catatan": "Bank BUMN terbesar kedua, korporasi & wholesale banking. Transformasi digital agresif."
    },
    "BBNI": {
        "nama": "Bank Negara Indonesia Tbk",
        "sektor": "Keuangan / Perbankan",
        "market_cap": "~Rp 170 T",
        "per": "8-10x",
        "pbv": "1.2-1.5x",
        "roe": "~15%",
        "der": "~5x (wajar untuk bank)",
        "dividen_yield": "~5%",
        "catatan": "Bank BUMN dengan valuasi murah dibanding peers. Fokus korporasi dan internasional."
    },
    "TLKM": {
        "nama": "Telkom Indonesia Tbk",
        "sektor": "Telekomunikasi",
        "market_cap": "~Rp 300 T",
        "per": "12-15x",
        "pbv": "2.5-3x",
        "roe": "~18%",
        "der": "~0.7x",
        "dividen_yield": "~4%",
        "catatan": "Perusahaan telko terbesar Indonesia, monopoli jaringan fixed-line. Anak usaha Telkomsel dominasi seluler."
    },
    "ASII": {
        "nama": "Astra International Tbk",
        "sektor": "Konglomerat / Otomotif",
        "market_cap": "~Rp 200 T",
        "per": "7-9x",
        "pbv": "1.2-1.5x",
        "roe": "~16%",
        "der": "~0.5x",
        "dividen_yield": "~5%",
        "catatan": "Konglomerat terbesar, dominasi otomotif (Toyota, Honda), juga di perbankan, tambang, infrastruktur."
    },
    "UNVR": {
        "nama": "Unilever Indonesia Tbk",
        "sektor": "Konsumer / FMCG",
        "market_cap": "~Rp 80 T",
        "per": "20-25x",
        "pbv": "30x+",
        "roe": "~100%+",
        "der": "~2x",
        "dividen_yield": "~3%",
        "catatan": "Consumer goods besar, margin tinggi tapi pertumbuhan melambat. PBV sangat tinggi karena ekuitas kecil."
    },
    "ICBP": {
        "nama": "Indofood CBP Sukses Makmur Tbk",
        "sektor": "Konsumer / FMCG",
        "market_cap": "~Rp 120 T",
        "per": "15-18x",
        "pbv": "3-4x",
        "roe": "~18%",
        "der": "~0.5x",
        "dividen_yield": "~2%",
        "catatan": "Produsen mie instan terbesar (Indomie). Bisnis defensif, ekspansi ke Timur Tengah dan Afrika."
    },
    "INDF": {
        "nama": "Indofood Sukses Makmur Tbk",
        "sektor": "Konsumer / FMCG",
        "market_cap": "~Rp 55 T",
        "per": "7-9x",
        "pbv": "1-1.3x",
        "roe": "~12%",
        "der": "~0.7x",
        "dividen_yield": "~4%",
        "catatan": "Holding Indofood Group (ICBP parent). Bisnis diversifikasi: mie, dairy, snack, agribisnis, distribusi."
    },
    "GOTO": {
        "nama": "GoTo Gojek Tokopedia Tbk",
        "sektor": "Teknologi",
        "market_cap": "~Rp 100 T",
        "per": "Belum profit",
        "pbv": "1.5-2x",
        "roe": "Negatif",
        "der": "~0.1x",
        "dividen_yield": "0%",
        "catatan": "Startup teknologi terbesar (Gojek + Tokopedia). Masih rugi, fokus pada efisiensi menuju profitabilitas."
    },
    "BRIS": {
        "nama": "Bank Syariah Indonesia Tbk",
        "sektor": "Keuangan / Perbankan Syariah",
        "market_cap": "~Rp 85 T",
        "per": "14-18x",
        "pbv": "2.5-3x",
        "roe": "~15%",
        "der": "~7x (wajar untuk bank)",
        "dividen_yield": "~1%",
        "catatan": "Bank syariah terbesar hasil merger. Pertumbuhan pembiayaan tinggi, didukung captive market BUMN."
    },
    "MDKA": {
        "nama": "Merdeka Copper Gold Tbk",
        "sektor": "Pertambangan / Emas & Tembaga",
        "market_cap": "~Rp 60 T",
        "per": "30-50x",
        "pbv": "3-4x",
        "roe": "~8%",
        "der": "~1x",
        "dividen_yield": "~0.5%",
        "catatan": "Produsen emas & tembaga. Proyek AIM (nikel HPAL) jadi katalis masa depan, tapi capex besar."
    },
    "INCO": {
        "nama": "Vale Indonesia Tbk",
        "sektor": "Pertambangan / Nikel",
        "market_cap": "~Rp 50 T",
        "per": "15-25x (fluktuatif mengikuti harga nikel)",
        "pbv": "1.5-2x",
        "roe": "~8-12%",
        "der": "~0.2x",
        "dividen_yield": "~2%",
        "catatan": "Produsen nikel terbesar di Indonesia (nikel matte). Sangat sensitif terhadap harga nikel global & permintaan EV."
    },
    "ANTM": {
        "nama": "Aneka Tambang Tbk",
        "sektor": "Pertambangan / Nikel & Emas",
        "market_cap": "~Rp 50 T",
        "per": "10-15x",
        "pbv": "1.5-2x",
        "roe": "~12%",
        "der": "~0.3x",
        "dividen_yield": "~2%",
        "catatan": "BUMN tambang (nikel, emas, bauksit). Harga komoditas jadi driver utama. Diversifikasi ke downstream."
    },
    "ADRO": {
        "nama": "Adaro Energy Indonesia Tbk",
        "sektor": "Pertambangan / Batubara",
        "market_cap": "~Rp 100 T",
        "per": "5-8x",
        "pbv": "1-1.5x",
        "roe": "~20%",
        "der": "~0.2x",
        "dividen_yield": "~6%",
        "catatan": "Produsen batubara terbesar kedua. Cash flow kuat, diversifikasi ke aluminium & energi hijau."
    },
    "PTBA": {
        "nama": "Bukit Asam Tbk",
        "sektor": "Pertambangan / Batubara",
        "market_cap": "~Rp 35 T",
        "per": "5-7x",
        "pbv": "1.5-2x",
        "roe": "~25%",
        "der": "~0.2x",
        "dividen_yield": "~8%",
        "catatan": "BUMN batubara dengan dividend yield tertinggi. Risiko ESG & transisi energi jangka panjang."
    },
    "CPIN": {
        "nama": "Charoen Pokphand Indonesia Tbk",
        "sektor": "Konsumer / Peternakan",
        "market_cap": "~Rp 70 T",
        "per": "20-25x",
        "pbv": "4-5x",
        "roe": "~18%",
        "der": "~0.4x",
        "dividen_yield": "~1.5%",
        "catatan": "Produsen pakan ternak & ayam broiler terbesar. Margin tergantung harga jagung & permintaan ayam."
    },
    "AMRT": {
        "nama": "Sumber Alfaria Trijaya Tbk",
        "sektor": "Ritel / Minimarket",
        "market_cap": "~Rp 100 T",
        "per": "40-50x",
        "pbv": "12-15x",
        "roe": "~25%",
        "der": "~1.5x",
        "dividen_yield": "~0.5%",
        "catatan": "Operator Alfamart, minimarket terbesar Indonesia. Ekspansi outlet agresif, pertumbuhan same-store stabil."
    },
    "ACES": {
        "nama": "Ace Hardware Indonesia Tbk",
        "sektor": "Ritel / Home Improvement",
        "market_cap": "~Rp 15 T",
        "per": "15-20x",
        "pbv": "3-4x",
        "roe": "~15%",
        "der": "~0.1x",
        "dividen_yield": "~3%",
        "catatan": "Ritel perlengkapan rumah terbesar. Balance sheet bersih, cash-rich, pertumbuhan stabil."
    },
    "EMTK": {
        "nama": "Elang Mahkota Teknologi Tbk",
        "sektor": "Media & Teknologi",
        "market_cap": "~Rp 30 T",
        "per": "Fluktuatif",
        "pbv": "1-1.5x",
        "roe": "~5%",
        "der": "~0.2x",
        "dividen_yield": "~0.5%",
        "catatan": "Holding media (SCMA) & teknologi (Bukalapak). Valuasi tertekan oleh kerugian segmen digital."
    },
    "KLBF": {
        "nama": "Kalbe Farma Tbk",
        "sektor": "Healthcare / Farmasi",
        "market_cap": "~Rp 70 T",
        "per": "20-25x",
        "pbv": "3-4x",
        "roe": "~15%",
        "der": "~0.15x",
        "dividen_yield": "~2.5%",
        "catatan": "Perusahaan farmasi terbesar Indonesia. Diversifikasi ke consumer health, nutrisi, distribusi."
    },
    "PGAS": {
        "nama": "Perusahaan Gas Negara Tbk",
        "sektor": "Energi / Gas",
        "market_cap": "~Rp 35 T",
        "per": "8-12x",
        "pbv": "1-1.3x",
        "roe": "~12%",
        "der": "~0.8x",
        "dividen_yield": "~5%",
        "catatan": "BUMN distribusi gas terbesar. Pendapatan tergantung volume gas & kebijakan harga pemerintah."
    },
    "SMGR": {
        "nama": "Semen Indonesia Tbk",
        "sektor": "Material / Semen",
        "market_cap": "~Rp 40 T",
        "per": "12-18x",
        "pbv": "1.3-1.8x",
        "roe": "~8%",
        "der": "~0.5x",
        "dividen_yield": "~3%",
        "catatan": "Produsen semen terbesar Indonesia (Semen Gresik, Semen Padang, Tonasa). Overcapacity jadi tantangan."
    },
    "INKP": {
        "nama": "Indah Kiat Pulp & Paper Tbk",
        "sektor": "Material / Pulp & Kertas",
        "market_cap": "~Rp 50 T",
        "per": "5-8x",
        "pbv": "0.5-0.8x",
        "roe": "~10%",
        "der": "~0.8x",
        "dividen_yield": "~2%",
        "catatan": "Produsen pulp & kertas terbesar (Sinar Mas Group). Sensitif terhadap harga pulp global & kurs USD."
    },
    "TOWR": {
        "nama": "Sarana Menara Nusantara Tbk",
        "sektor": "Infrastruktur / Menara Telekomunikasi",
        "market_cap": "~Rp 50 T",
        "per": "15-20x",
        "pbv": "4-5x",
        "roe": "~20%",
        "der": "~3x",
        "dividen_yield": "~2%",
        "catatan": "Operator menara telko terbesar. Pendapatan recurring, pertumbuhan stabil dari tenancy ratio."
    },
    "TBIG": {
        "nama": "Tower Bersama Infrastructure Tbk",
        "sektor": "Infrastruktur / Menara Telekomunikasi",
        "market_cap": "~Rp 35 T",
        "per": "18-22x",
        "pbv": "8-10x",
        "roe": "~35%",
        "der": "~5x",
        "dividen_yield": "~3%",
        "catatan": "Operator menara telko kedua terbesar. Recurring revenue tinggi tapi leverage juga tinggi."
    },
    "MAPI": {
        "nama": "Mitra Adiperkasa Tbk",
        "sektor": "Ritel / Fashion & Lifestyle",
        "market_cap": "~Rp 25 T",
        "per": "15-20x",
        "pbv": "3-4x",
        "roe": "~18%",
        "der": "~0.8x",
        "dividen_yield": "~1.5%",
        "catatan": "Ritel lifestyle terbesar (Zara, Starbucks, Sport Station). Sensitif terhadap consumer spending."
    },
    "UNTR": {
        "nama": "United Tractors Tbk",
        "sektor": "Konglomerat / Alat Berat & Pertambangan",
        "market_cap": "~Rp 100 T",
        "per": "5-7x",
        "pbv": "1-1.5x",
        "roe": "~20%",
        "der": "~0.3x",
        "dividen_yield": "~7%",
        "catatan": "Dealer Komatsu terbesar, tambang batubara (Pamapersada). Cash flow kuat, dividen tinggi. Anak usaha ASII."
    },
    "ESSA": {
        "nama": "Surya Esa Perkasa Tbk",
        "sektor": "Energi / Gas & LNG",
        "market_cap": "~Rp 20 T",
        "per": "8-12x",
        "pbv": "2-3x",
        "roe": "~15%",
        "der": "~0.5x",
        "dividen_yield": "~1%",
        "catatan": "Produsen LNG mini terbesar. Ekspansi ke green energy & ammonia jadi katalis. Volatil."
    },
    "ITMG": {
        "nama": "Indo Tambangraya Megah Tbk",
        "sektor": "Pertambangan / Batubara",
        "market_cap": "~Rp 30 T",
        "per": "4-6x",
        "pbv": "1.5-2x",
        "roe": "~30%",
        "der": "~0.1x",
        "dividen_yield": "~12%",
        "catatan": "Batubara premium (Banpu Group). Dividend payout sangat tinggi. Risiko harga batubara & ESG."
    },
    "BRPT": {
        "nama": "Barito Pacific Tbk",
        "sektor": "Petrokimia & Energi Terbarukan",
        "market_cap": "~Rp 40 T",
        "per": "Fluktuatif",
        "pbv": "1-2x",
        "roe": "~5%",
        "der": "~0.8x",
        "dividen_yield": "~0.5%",
        "catatan": "Holding petrokimia (Star Energy, Chandra Asri). Paparan ke geothermal & energi hijau."
    },
}


def _get_fundamental_block(ticker: str) -> str:
    """Mengambil blok teks fundamental untuk ticker tertentu."""
    clean = ticker.upper().split(".")[0]
    info = FUNDAMENTAL_DATA.get(clean)
    if not info:
        return "(Data fundamental tidak tersedia untuk saham ini)"

    return (
        f"  Nama         : {info['nama']}\n"
        f"  Sektor       : {info['sektor']}\n"
        f"  Market Cap   : {info['market_cap']}\n"
        f"  PER          : {info['per']}\n"
        f"  PBV          : {info['pbv']}\n"
        f"  ROE          : {info['roe']}\n"
        f"  DER          : {info['der']}\n"
        f"  Dividen Yield: {info['dividen_yield']}\n"
        f"  Catatan      : {info['catatan']}"
    )


def _get_company_name(ticker: str) -> str:
    """Mengambil nama perusahaan dari FUNDAMENTAL_DATA."""
    clean = ticker.upper().split(".")[0]
    info = FUNDAMENTAL_DATA.get(clean)
    if info:
        return info.get("nama", clean)
    return clean


def _call_groq(prompt: str, timeout: int = 60) -> str:
    """
    Memanggil Groq API (llama-3.3-70b) untuk generate analisa fundamental.
    Groq sangat cepat (< 2 detik biasanya).
    Return string hasil, atau None jika gagal (agar bisa fallback).
    """
    if not GROQ_API_KEY:
        print("[Groq] API key belum diisi, skip ke fallback...")
        return None

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}"
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 1500,
        "temperature": 0.5,
        "top_p": 0.9,
        "stream": False
    }

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=timeout)

            if response.status_code == 429 and attempt < max_retries:
                wait = 10 * (attempt + 1)
                print(f"[Groq] Rate limit, retry dalam {wait}s... (attempt {attempt+1})")
                time.sleep(wait)
                continue

            if response.status_code >= 400:
                print(f"[Groq] Error {response.status_code}: {response.text[:200]}")
                return None

            data = response.json()
            choices = data.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                content = message.get("content", "").strip()
                if content:
                    return content

            return None

        except requests.exceptions.Timeout:
            print(f"[Groq] Timeout (>{timeout}s)")
            return None
        except Exception as e:
            print(f"[Groq] Error: {e}")
            return None

    return None


def generate_ai_analysis(ticker, signal, rsi, ma20, ma50, harga,
                         entry=None, tp=None, sl=None,
                         score=0, alasan_scoring=None, smart_money=False,
                         volume_label="NORMAL", gap_up=False, gap_confidence="LOW",
                         mtf=None):
    """
    Meminta analisis teknikal & fundamental lengkap kepada AI lokal (Ollama - mistral).
    Mengembalikan string hasil analisis tanpa batasan panjang.
    """
    # Menyiapkan variabel yang tahan terhadap nilai NaN / Kosong
    ma20_str = f"{ma20:.2f}" if (ma20 is not None and not math.isnan(ma20)) else "N/A"
    ma50_str = f"{ma50:.2f}" if (ma50 is not None and not math.isnan(ma50)) else "N/A"
    rsi_str = f"{rsi:.2f}" if (rsi is not None and not math.isnan(rsi)) else "N/A"

    # Trend info
    trend = "N/A"
    if ma20 is not None and ma50 is not None and not math.isnan(ma20) and not math.isnan(ma50):
        trend = "UPTREND (MA20 > MA50)" if ma20 > ma50 else "DOWNTREND (MA20 < MA50)"

    harga_vs_ma20 = "N/A"
    if harga is not None and ma20 is not None and not math.isnan(ma20):
        harga_vs_ma20 = "DI ATAS MA20 (momentum positif)" if harga > ma20 else "DI BAWAH MA20 (momentum negatif, tekanan jual)"

    # RSI interpretation
    rsi_interpretation = "Data tidak tersedia"
    if rsi is not None and not math.isnan(rsi):
        if rsi > 70:
            rsi_interpretation = f"OVERBOUGHT ({rsi:.2f} > 70) — Harga sudah terlalu tinggi, potensi koreksi turun signifikan. Trader sebaiknya waspada dan pertimbangkan taking profit."
        elif rsi > 60:
            rsi_interpretation = f"MENDEKATI OVERBOUGHT ({rsi:.2f}) — Momentum bullish masih ada tapi mulai jenuh. Perlu perhatian jika mendekati 70."
        elif rsi < 30:
            rsi_interpretation = f"OVERSOLD ({rsi:.2f} < 30) — Harga sudah terlalu murah, potensi rebound/pembalikan arah naik."
        elif rsi < 40:
            rsi_interpretation = f"MENDEKATI OVERSOLD ({rsi:.2f}) — Tekanan jual cukup besar, belum sampai titik ekstrem."
        else:
            rsi_interpretation = f"NETRAL ({rsi:.2f}) — Berada di zona normal 40-60, belum ada sinyal ekstrem."

    # Susun baris entry plan jika tersedia
    if entry is not None and tp is not None and sl is not None:
        try:
            rr = (float(tp) - float(entry)) / (float(entry) - float(sl))
            entry_block = (
                f"* Entry : {entry:.2f}\n"
                f"* TP    : {tp:.2f}\n"
                f"* SL    : {sl:.2f}\n"
                f"* RR    : 1:{rr:.1f}\n"
            )
        except Exception:
            entry_block = "* Trade plan: Tidak tersedia\n"
    else:
        entry_block = "* Trade plan: Tidak ada (sinyal bukan BUY kuat)\n"

    # Alasan scoring
    alasan_text = "Tidak ada"
    if alasan_scoring:
        if isinstance(alasan_scoring, list):
            alasan_text = ", ".join(alasan_scoring)
        else:
            alasan_text = str(alasan_scoring)

    # Smart Money & Gap info
    sm_text = f"AKTIF ({volume_label})" if smart_money else f"TIDAK AKTIF ({volume_label})"
    gap_text = f"YA (confidence: {gap_confidence})" if gap_up else "TIDAK"

    # MTF info
    mtf_text = "Data tidak tersedia"
    if mtf and isinstance(mtf, dict) and mtf.get("confluence") != "NO_DATA":
        confluence = mtf.get("confluence", "N/A")
        mtf_parts = [f"Confluence: {confluence}"]
        for tf_key, tf_label in [("weekly", "Weekly"), ("daily", "Daily"), ("intraday", "1H")]:
            tf = mtf.get(tf_key)
            if tf and tf.get("status") == "ok":
                mtf_parts.append(f"{tf_label}: bias {tf.get('bias', 'N/A')}, RSI {tf.get('rsi', 'N/A')}")
        if mtf.get("summary"):
            mtf_parts.append(f"Summary: {mtf['summary']}")
        mtf_text = " | ".join(mtf_parts)

    # Fundamental
    fundamental_block = _get_fundamental_block(ticker)

    # ── STRATEGI: Mistral → teknikal, Gemini → fundamental, lalu gabung ──

    # === BAGIAN A: Analisa Fundamental via Gemini ===
    clean_ticker = ticker.upper().split(".")[0]
    gemini_fundamental_prompt = f"""Kamu analis fundamental saham Indonesia. Analisa singkat & padat saham **{clean_ticker}** ({_get_company_name(ticker)}).

Sinyal: **{signal}** (skor {score}/8) | Harga: {harga:.2f}

Data fundamental:
{fundamental_block}

Tulis dalam bahasa Indonesia, format ringkas:

**VALUASI**: PER, PBV — murah/wajar/mahal vs peers sektor? (2-3 kalimat)
**KEUANGAN**: ROE, margin, pertumbuhan revenue & laba, DER (2-3 kalimat)
**DIVIDEN**: Yield, konsistensi (1-2 kalimat)
**KATALIS & RISIKO**: Prospek utama dan risiko terbesar (2-3 kalimat)
**KESIMPULAN**: Layak {signal}? Rating: SANGAT BAGUS / BAGUS / NETRAL / KURANG BAGUS / BURUK (1-2 kalimat)

Jawab SINGKAT dan PADAT. Maksimal 5 paragraf pendek."""

    # Analisa fundamental via Groq (jika gagal → fallback ke Ollama Mistral)
    print(f"[AI] Menganalisa fundamental {clean_ticker} via Groq (llama-3.3-70b)...")
    gemini_fundamental = _call_groq(gemini_fundamental_prompt, timeout=30)
    fundamental_source = "Groq (Llama 3.3 70B)"

    # Fallback fundamental ke Ollama jika Groq gagal (token habis / rate limit)
    if not gemini_fundamental:
        print(f"[AI] Groq gagal. Fallback fundamental ke Ollama Mistral...")
        try:
            url = "http://localhost:11434/api/generate"
            payload = {
                "model": "mistral",
                "prompt": gemini_fundamental_prompt,
                "stream": False,
                "options": {
                    "num_predict": 1024,
                    "temperature": 0.5,
                    "top_p": 0.9,
                    "repeat_penalty": 1.1,
                }
            }
            resp = requests.post(url, json=payload, timeout=90)
            resp.raise_for_status()
            ollama_fund = resp.json().get("response", "").strip()
            if ollama_fund:
                gemini_fundamental = ollama_fund
                fundamental_source = "Ollama Mistral (fallback)"
                print(f"[AI] Fundamental via Ollama Mistral berhasil.")
        except Exception as e:
            print(f"[AI] Ollama fundamental juga gagal: {e}")

    # === BAGIAN B: Analisa Teknikal via Mistral (lokal) ===
    teknikal_prompt = f"""Kamu adalah analis saham teknikal profesional Indonesia yang sangat berpengalaman.

PENTING — ATURAN WAJIB:
1. Sinyal sistem untuk saham ini adalah: **{signal}** dengan skor {score}/8.
2. Analisa kamu HARUS KONSISTEN dengan sinyal sistem ({signal}). JANGAN memberikan rekomendasi yang bertentangan.
3. Jika sinyal SELL, jelaskan MENGAPA saham ini harus dijual/dihindari berdasarkan data teknikal.
4. Jika sinyal BUY, jelaskan MENGAPA saham ini layak dibeli.
5. Jika sinyal HOLD, jelaskan MENGAPA saham ini belum layak dibeli/dijual.

═══ DATA TEKNIKAL ═══
* Saham       : {ticker}
* Harga Close : {harga:.2f}
* RSI (14)    : {rsi_str} → {rsi_interpretation}
* MA20        : {ma20_str}
* MA50        : {ma50_str}
* Trend       : {trend}
* Harga vs MA : {harga_vs_ma20}
* Smart Money : {sm_text}
* Gap Up      : {gap_text}
* Sinyal      : {signal}
* Skor        : {score}/8
* Alasan Skor : {alasan_text}
{entry_block}
═══ MULTI-TIMEFRAME ═══
{mtf_text}

═══ TUGAS ═══
Buat analisa TEKNIKAL LENGKAP dalam bahasa Indonesia. JANGAN bahas fundamental.

**BAGIAN 1 — RINGKASAN SINYAL**
Jelaskan secara detail sinyal {signal} dan skor {score}/8.
Sebutkan setiap poin yang berkontribusi ke skor. Jelaskan arti skor ini untuk trader.

**BAGIAN 2 — ANALISA TEKNIKAL MENDALAM**
Bahas secara DETAIL dan PANJANG setiap poin berikut:
- RSI saat ini {rsi_str}: {rsi_interpretation}. Elaborasi apa implikasinya untuk arah harga saham ini dalam jangka pendek dan menengah.
- Harga {harga:.2f} saat ini {harga_vs_ma20}. Elaborasi apa artinya untuk momentum dan kekuatan tren saat ini.
- MA20 ({ma20_str}) vs MA50 ({ma50_str}): {trend}. Elaborasi apakah ini Golden Cross atau Death Cross, dan apa implikasinya.
- Smart Money: {sm_text}. Elaborasi apa arti aliran dana institusi/bandar untuk pergerakan harga ke depan.
- Gap Up: {gap_text}. Elaborasi apakah ada potensi gap di sesi berikutnya.
- Multi-timeframe: {mtf_text}. Elaborasi apakah semua timeframe (weekly, daily, intraday) selaras atau bertentangan.

**BAGIAN 3 — KESIMPULAN & REKOMENDASI TEKNIKAL**
- Berikan rekomendasi TEGAS yang KONSISTEN dengan sinyal {signal}
- Identifikasi level support dan resistance penting berdasarkan MA20 dan MA50
- Berikan risk/reward assessment
{f'- Komentari level entry ({entry:.2f}), TP ({tp:.2f}), dan SL ({sl:.2f}): apakah masuk akal? Apa risikonya?' if entry is not None and tp is not None and sl is not None else '- Jelaskan mengapa belum ada trade plan untuk saham ini'}
- Berikan skenario bullish dan bearish ke depan

INGAT: Tulis PANJANG dan DETAIL. Minimal 3 paragraf besar. Jangan pernah meringkas."""

    # Kirim ke Mistral
    teknikal_result = None
    try:
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": "mistral",
            "prompt": teknikal_prompt,
            "stream": False,
            "options": {
                "num_predict": 1024,
                "temperature": 0.7,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
            }
        }
        response = requests.post(url, json=payload, timeout=90)
        response.raise_for_status()
        data = response.json()
        teknikal_result = data.get("response", "").strip()
    except requests.exceptions.ConnectionError:
        teknikal_result = None
        print("[AI] Ollama tidak tersedia, skip analisis teknikal.")
    except requests.exceptions.Timeout:
        teknikal_result = None
        print("[AI] Ollama timeout (>90s), skip analisis teknikal.")
    except Exception as e:
        teknikal_result = None
        print(f"[AI] Ollama error: {e}, skip analisis teknikal.")

    # === GABUNGKAN HASIL ===
    parts = []

    # Teknikal dari Mistral
    if teknikal_result:
        parts.append("══════════════════════════════════════")
        parts.append("📊 ANALISA TEKNIKAL [Mistral AI]")
        parts.append("══════════════════════════════════════")
        parts.append(teknikal_result)

    # Fundamental dari Z.AI / Gemini
    if gemini_fundamental:
        parts.append("")
        parts.append("══════════════════════════════════════")
        parts.append(f"📈 ANALISA FUNDAMENTAL [{fundamental_source}]")
        parts.append("══════════════════════════════════════")
        parts.append(gemini_fundamental)
    else:
        # Fallback fundamental dari data hardcoded jika semua AI gagal
        parts.append("")
        parts.append("══════════════════════════════════════")
        parts.append("📈 ANALISA FUNDAMENTAL [Data Statis]")
        parts.append("══════════════════════════════════════")
        parts.append(fundamental_block)

    return "\n".join(parts)

def generate_market_outlook(daftar_saham_string):
    """
    Meminta Mistral membuat ringkasan market outlook (teknikal, bukan fundamental).
    """
    prompt = f"""Kamu adalah analis saham profesional Indonesia. Berikut saham dengan sinyal terbaik hari ini:\n{daftar_saham_string}\nBuat ringkasan market outlook dalam bahasa Indonesia, 2-3 kalimat padat."""

    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "mistral",
        "prompt": prompt,
        "stream": False
    }
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "Analisis gagal di-generate.").strip()
    except requests.exceptions.ConnectionError:
        return "Analisis Gagal: Tidak dapat menghubungi AI server."
    except Exception as e:
        return f"Analisis Error: {str(e)}"

if __name__ == "__main__":
    # Pengujian skrip mandiri
    print("Mempersiapkan data tes untuk dikirim ke Ollama Mistral...")
    
    # Simulasi kondisi Oversold
    hasil_analisis = generate_ai_analysis(
        ticker="BBCA.JK",
        signal="BUY",
        rsi=28.50,
        ma20=6200,
        ma50=6100,
        harga=5900.00
    )
    
    print("\n[+] Hasil Respons Analis AI:")
    print("-" * 50)
    print(hasil_analisis)
    print("-" * 50)
