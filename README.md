# 📈 Stock Analyzer v2.0 (Automated Batching & AI)

Sistem analisis saham otomatis (_Real-Time Batching_) berbasis AI yang dirancang untuk beroperasi secara mandiri selama jam bursa aktif. Sistem akan mengambil data, menghitung skor momentum, melacak pergerakan bandar (Smart Money), mendeteksi probabilitas Gap Up, meminta opini intelijen Mistral (Ollama), dan mengirimkan Top 3 Rekomendasi bersih secara langsung ke Telegram Anda.

## 📁 Struktur Project

```
stock-analyzer/
├── main.py              # Entry point bot analisis (siklus 5 menit)
├── app.py               # Flask API server + serve dashboard
├── index.html           # Dashboard web (TradingView + signal cards)
├── data.py              # Mengambil data saham dari Yahoo Finance
├── indicator.py         # Menghitung indikator teknikal
├── signal.py            # Menghasilkan sinyal Buy/Sell/Hold
├── ai_analyst.py        # Analisis AI via Ollama (Mistral)
├── notifier.py          # Mengirim notifikasi ke Telegram
├── volume_analysis.py   # Sistem deteksi Smart Money (Akumulasi/Distribusi)
├── gap_detector.py      # Modul kalkulator probabilitas Gap-Up
├── scoring.py           # Sistem agregasi skor multifaktor
├── config.py            # Konfigurasi (API key, dsb)
├── signals.json         # Output analisis per siklus (auto-generated)
├── last_signals.json    # State anti-spam Telegram (auto-generated)
├── requirements.txt     # Daftar dependensi
└── README.md            # Dokumentasi
```

## 🌟 Update Fitur Terbaru (Hari Ini)

*   **Automated Infinite Loop**: Bot berjalan otomatis setiap 5 menit dan menggunakan sistem *Smart Delay*.
*   **Market Hours Filter**: Bot hanya memproses data pada hari kerja dan jam bursa lokal aktif (Sesi 1: 09.00-12.00, Sesi 2: 13.30-16.00 WIB) untuk menghemat daya komputasi PC.
*   **Smart Money Tracker**: Dilengkapi modul pendeteksi pergerakan Bandar/Whale (Volume Spike vs Price Action) untuk mencap saham ke fase *AKUMULASI* atau *DISTRIBUSI*.
*   **Gap Up Predictor**: Memiliki kriteria berlapis (RSI, Breakout MA20, Uang Masuk) untuk mengukur tingkat _Confidence_ (HIGH/MED/LOW) sebuah saham melonjak di pembukaan hari esok.
*   **AI Mistral Market Outlook**: Tidak lagi memanggil bot AI per-saham. Ia mengamati 3 daftar juara sekaligus lalu menyimpulkannya sebagai _Market Digest Outlook_ di ujung notifikasi Telegram Anda untuk menghemat limit API lokal.
*   **Multi-Condition Sorting**: Klasemen TOP 3 tidak sembarangan diacak. Prioritas dinilai dari: Skor Tertinggi -> Kondisi Gap Up True -> Confidence HIGH -> dan yang memiliki Smart Money.
*   **State Persistence & Anti-Spam**: Ditanamkan filter `last_signals.json`. Jika tak ada pergerakan sinyal baru di daftar elit saham, bot akan bungkam dan menolak melakukan _Spam_ ke Telegram Anda.
*   **Anti-Double Instance Lock**: Mencegah terminal bertabrakan atau terksekusi ganda menggunakan pengunci OS *msvcrt*.

## 🚀 Cara Menjalankan

### 1. Persiapan Sistem

```bash
# Install semua dependensi (Pandas, TA, Flask, dll)
pip install -r requirements.txt

# Pastikan Ollama CLI telah berjalan di latar belakang PC
ollama pull mistral
```

### 2. Jalankan Bot Analisis (Terminal 1)

Bot ini mengambil data saham, menghitung indikator teknikal, dan menyimpan hasilnya ke `signals.json` setiap 5 menit.

```bash
python main.py
```

> **Catatan:** Bot hanya memproses data saat jam bursa aktif (09:00-12:00 & 13:30-16:00 WIB). Di luar jam tersebut bot akan idle.

### 3. Jalankan Dashboard API (Terminal 2)

Buka terminal **baru** (terpisah dari bot), lalu jalankan Flask:

```bash
python app.py
```

Output yang diharapkan:

```
=======================================================
   STOCK ANALYZER - FLASK API SERVER
=======================================================
  Dashboard: http://localhost:5000
  Endpoint : http://localhost:5000/signals
=======================================================

 * Serving Flask app 'app'
 * Running on http://127.0.0.1:5000
```

### 4. Buka Dashboard di Browser

```
http://localhost:5000
```

Dashboard akan menampilkan:

| Komponen | Deskripsi |
|----------|-----------|
| **Stats Bar** | Ringkasan: Total saham, sinyal BUY/SELL, Smart Money, Gap Up |
| **TradingView Chart** | Chart candlestick real-time dengan indikator RSI & MA |
| **Signal Cards** | Kartu per saham: ticker, harga, sinyal, skor, analisa AI |
| **Auto-Refresh** | Data diperbarui otomatis setiap 10 detik |

---

## 🛠️ Troubleshooting & Debug

### ❌ Dashboard kosong / API tidak muncul

**Gejala:** Halaman `http://localhost:5000` menampilkan pesan error atau kartu sinyal tidak muncul.

**Langkah debug:**

1. **Cek apakah Flask berjalan:**
   ```bash
   # Pastikan terminal Flask menampilkan "Running on http://127.0.0.1:5000"
   python app.py
   ```

2. **Test API secara langsung:**
   Buka di browser:
   ```
   http://localhost:5000/signals
   ```
   Jika muncul JSON → API berjalan normal, masalah ada di frontend.
   Jika error → lihat pesan error di terminal Flask.

3. **Cek Ollama berjalan:**
   ```bash
   # Ollama harus aktif agar AI analysis bisa bekerja
   ollama list
   ```
   Jika `mistral` tidak ada di daftar:
   ```bash
   ollama pull mistral
   ```

4. **Cek koneksi internet:**
   - TradingView chart **membutuhkan internet** (widget dimuat dari server TradingView)
   - Data saham diambil dari Yahoo Finance (butuh internet)

5. **Port 5000 sudah dipakai:**
   ```bash
   # Windows - cek proses yang menggunakan port 5000
   netstat -ano | findstr :5000
   ```
   Jika ada proses lain, matikan atau ganti port di `app.py`.

### ❌ Data sinyal tidak update

**Gejala:** Signal cards menampilkan data lama.

**Penyebab:** Bot (`main.py`) belum dijalankan atau sedang di luar jam bursa.

**Solusi:** Pastikan `main.py` berjalan di terminal terpisah dan saat ini adalah jam bursa aktif.

---

## 📄 Cara Cek File JSON Output

Bot menyimpan 2 file JSON yang bisa diperiksa kapan saja:

### `signals.json` — Hasil Analisis Lengkap

File ini di-overwrite setiap siklus bot (5 menit). Berisi data bersih untuk dashboard:

```bash
# Lihat isi file
type signals.json
```

Format isi:
```json
[
  {
    "ticker": "BBCA",
    "price": 9500.0,
    "signal": "BUY",
    "score": 5,
    "smart_money": true,
    "gap_up": true,
    "ai": "Saham BBCA menunjukkan momentum bullish..."
  },
  ...
]
```

### `last_signals.json` — State Anti-Spam

File ini menyimpan sinyal terakhir setiap saham untuk mencegah notifikasi Telegram berulang:

```bash
type last_signals.json
```

Format isi:
```json
{
  "BBCA.JK": "HOLD",
  "BBRI.JK": "BUY",
  "TLKM.JK": "HOLD",
  "ASII.JK": "SELL"
}
```

### Tips Cek JSON dengan Python

```bash
# Format JSON rapi di terminal
python -c "import json; print(json.dumps(json.load(open('signals.json')), indent=2, ensure_ascii=False))"
```

## 📊 Indikator Teknikal yang Tersedia

| Indikator | Deskripsi |
|-----------|-----------|
| **SMA** (20, 50) | Simple Moving Average |
| **EMA** (20, 50) | Exponential Moving Average |
| **RSI** (14) | Relative Strength Index |
| **MACD** (12, 26, 9) | Moving Average Convergence Divergence |
| **Bollinger Bands** (20, 2) | Upper, Middle, Lower Band + Width |
| **Stochastic** (14, 3) | Stochastic Oscillator (%K, %D) |
| **ATR** (14) | Average True Range |

## 🎯 Strategi Sinyal

| Strategi | Kondisi BUY | Kondisi SELL |
|----------|-------------|-------------|
| **RSI** | RSI < 30 (oversold) | RSI > 70 (overbought) |
| **MACD** | MACD cross di atas Signal | MACD cross di bawah Signal |
| **MA Cross** | Golden Cross (SMA20 > SMA50) | Death Cross (SMA20 < SMA50) |
| **Bollinger** | Harga ≤ Lower Band | Harga ≥ Upper Band |
| **Stochastic** | %K < 20 (oversold) | %K > 80 (overbought) |

Setiap sinyal memiliki **confidence score** dan hasil akhir ditentukan menggunakan **weighted scoring**.

## 📱 Setup Notifikasi Telegram

1. Buka Telegram, cari **@BotFather**
2. Kirim `/newbot` dan ikuti instruksi untuk membuat bot
3. Salin **Bot Token** yang diberikan
4. Kirim pesan ke bot yang baru dibuat
5. Buka browser: `https://api.telegram.org/bot<TOKEN>/getUpdates`
6. Cari `"chat":{"id": <CHAT_ID>}` untuk mendapatkan **Chat ID**
7. Masukkan token dan chat ID di `notifier.py` atau gunakan parameter `--token` dan `--chat`

## 📝 Contoh Output

```
╔══════════════════════════════════════════════════╗
║        📈 STOCK ANALYZER v1.0                   ║
║        Sistem Analisis Saham Sederhana           ║
╚══════════════════════════════════════════════════╝

══════════════════════════════════════════════════
📈 ANALISIS SAHAM: BBCA.JK
💰 Harga Terakhir: 9875.00
══════════════════════════════════════════════════

── Detail Sinyal ──
  ⚪ HOLD [RSI]
    └─ RSI=55.3 — Netral
       Confidence: ███░░░░░░░ 30%

  🟡 BUY [MACD]
    └─ MACD di atas Signal (bullish momentum)
       Confidence: █████░░░░░ 50%

  🟡 BUY [MA Cross]
    └─ Harga(9875.00) > SMA20(9750.00) > SMA50(9500.00) — Uptrend
       Confidence: ██████░░░░ 60%
...

══════════════════════════════════════════════════
🎯 REKOMENDASI: 🟡 BUY
📊 Skor Agregat: 0.65
══════════════════════════════════════════════════
```

## 🔧 Kode Saham Populer

### Indonesia (BEI) — tambahkan `.JK`
- `BBCA.JK` — Bank Central Asia
- `BBRI.JK` — Bank Rakyat Indonesia
- `TLKM.JK` — Telkom Indonesia
- `UNVR.JK` — Unilever Indonesia
- `ASII.JK` — Astra International

### US
- `AAPL` — Apple
- `GOOGL` — Alphabet (Google)
- `MSFT` — Microsoft
- `AMZN` — Amazon
- `TSLA` — Tesla

## ⚠️ Disclaimer

Project ini dibuat untuk **tujuan edukasi** saja. Sinyal yang dihasilkan bukan merupakan saran investasi. Selalu lakukan riset mandiri sebelum mengambil keputusan investasi.
