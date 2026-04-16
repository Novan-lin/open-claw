import requests
import math

def generate_ai_analysis(ticker, signal, rsi, ma20, ma50, harga,
                         entry=None, tp=None, sl=None):
    """
    Meminta analisis teknikal singkat kepada AI lokal (Ollama - mistral).
    Mengembalikan string hasil analisis.
    """
    # Menyiapkan variabel yang tahan terhadap nilai NaN / Kosong
    ma20_str = f"{ma20:.2f}" if (ma20 is not None and not math.isnan(ma20)) else "N/A"
    ma50_str = f"{ma50:.2f}" if (ma50 is not None and not math.isnan(ma50)) else "N/A"
    rsi_str = f"{rsi:.2f}" if (rsi is not None and not math.isnan(rsi)) else "N/A"

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
            entry_instruction = (
                "Komentari apakah level entry, TP, dan SL tersebut masuk akal "
                "berdasarkan kondisi teknikal di atas (1 kalimat)."
            )
        except Exception:
            entry_block = ""
            entry_instruction = ""
    else:
        entry_block = ""
        entry_instruction = ""

    prompt = f"""Kamu adalah analis saham profesional.

Data:
* Saham: {ticker}
* Harga: {harga:.2f}
* RSI: {rsi_str}
* MA20: {ma20_str}
* MA50: {ma50_str}
* Sinyal: {signal}
{entry_block}
Tugas:
Berikan analisa maksimal 2 kalimat, profesional.
{entry_instruction}"""

    # Set up request payload 
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "mistral",
        "prompt": prompt,
        "stream": False # Meminta respons penuh, bukan potongan stream bertahap
    }
    
    # Mengirimkan Request dan Error Handling
    try:
        # Timeout diset 60 detik karena AI lokal terkadang membutuhkan waktu untuk loading memori
        response = requests.post(url, json=payload, timeout=60)
        
        # Mengecek apakah ada HTTP Error dari endpoint (seperti 404 Model Not Found, dll)
        response.raise_for_status()
        
        data = response.json()
        return data.get("response", "Analisis gagal di-generate.").strip()

    except requests.exceptions.ConnectionError:
        return "Analisis Gagal: Tidak dapat menghubungi localhost:11434. Pastikan aplikasi Ollama berjalan."
        
    except requests.exceptions.Timeout:
        return "Analisis Gagal: Proses timeout (butuh lebih dari 60 detik). Periksa beban CPU/GPU saat ini."
        
    except requests.exceptions.HTTPError as e:
        # Jika Mistral belum selesai terdownload (seperti isu sebelumnya), Ollama akan melempar error HTTP ini
        return f"Analisis Gagal: Model bermasalah atau belum tersedia penuh di Ollama. ({e})"
        
    except Exception as e:
        return f"Analisis Error: {str(e)}"

def generate_market_outlook(daftar_saham_string):
    """
    Meminta Ollama membuat ringkasan komprehensif terkait market outlook dari semua top saham.
    """
    prompt = f"""Kamu adalah analis saham profesional. Berikut saham dengan sinyal terbaik hari ini:\n{daftar_saham_string}\nBuat ringkasan singkat market outlook dalam 2-3 kalimat."""

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
        return "Analisis Gagal: Tidak dapat menghubungi localhost:11434."
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
