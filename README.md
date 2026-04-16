# 📈 Stock Analyzer v3.0

Sistem analisis saham otomatis berbasis AI untuk saham Indonesia (BEI/LQ45). Bot berjalan non-stop setiap 5 menit, menghitung indikator teknikal, mendeteksi Smart Money, menjalankan multi-strategy confirmation, mengirim rekomendasi Top 5 ke Telegram, dan secara otomatis mengoptimalkan parameter setiap minggu.

---

## 📁 Struktur Project

```
stock-analyzer/
├── main.py              # Entry point bot — siklus 5 menit non-stop
├── app.py               # Flask API server + dashboard web
├── index.html           # Dashboard UI (signal cards + trading performance)
├── data.py              # Ambil data saham dari Yahoo Finance
├── indicator.py         # Hitung RSI, MA — mendukung parameter dinamis
├── signal.py            # Generate sinyal BUY/SELL/HOLD
├── scoring.py           # Sistem skor multi-faktor
├── strategies.py        # 3 strategi teknikal + multi-strategy confirmation
├── ai_analyst.py        # Analisis AI via Ollama (Mistral) + komentar entry plan
├── notifier.py          # Kirim notifikasi ke Telegram
├── volume_analysis.py   # Deteksi Smart Money (Akumulasi/Distribusi)
├── gap_detector.py      # Kalkulator probabilitas Gap-Up
├── entry_plan.py        # Hitung entry, TP, SL, RR
├── risk_management.py   # Hitung lot & jumlah risiko per trade
├── trade_logger.py      # Monitoring posisi aktif
├── backtest.py          # Backtest engine — parameter dinamis RSI & MA
├── tuner.py             # Auto-tune parameter + simpan best_params.json
├── stock_filter.py      # Filter kelayakan saham (harga & volume minimum)
├── stock_list.py        # Daftar saham LQ45 + likuid
├── config.py            # Konfigurasi Telegram Bot Token & Chat ID
├── send_now.py          # Kirim analisis ke Telegram saat ini (bypass jam bursa)
├── signals.json         # Output analisis per siklus (auto-generated)
├── last_signals.json    # State anti-spam Telegram (auto-generated)
├── best_params.json     # Parameter terbaik hasil auto-tune (auto-generated)
├── trades.csv           # Riwayat trade historis
├── trades.json          # Posisi aktif & tertutup
└── requirements.txt     # Daftar dependensi Python
```

---

## 🌟 Fitur Lengkap

### 🤖 Bot Utama (`main.py`)
- **Loop otomatis 5 menit** — non-stop, market buka maupun tutup
- **Market hours filter** — Telegram hanya dikirim saat jam bursa aktif (Sesi 1: 09:00–12:00, Sesi 2: 13:30–16:00 WIB)
- **Dashboard tetap update** di luar jam bursa untuk keperluan monitoring
- **Anti-double instance** — mencegah bot berjalan ganda via OS lock (`msvcrt`)
- **Scanning 50+ saham LQ45** setiap siklus

### 📊 Analisis Teknikal
- **RSI** — Relative Strength Index (periode dinamis)
- **SMA** — Simple Moving Average (MA short & MA long, dinamis)
- **Smart Money Tracker** — deteksi volume spike vs price action (fase AKUMULASI/DISTRIBUSI)
- **Gap Up Predictor** — confidence level HIGH/MEDIUM/LOW berdasarkan RSI, MA breakout, dan volume

### 🎯 Multi-Strategy Confirmation (`strategies.py`)
Tiga strategi berjalan bersamaan dan memberikan bonus skor:

| Strategi | Kondisi BUY | Kondisi SELL |
|---|---|---|
| **RSI Reversal** | RSI < 30 & berbalik naik | RSI > 70 & berbalik turun |
| **Bollinger Bands** | Harga memantul dari lower band | Harga ditolak di upper band |
| **RSI + MA** | RSI < 40 & MA fast > MA slow | RSI > 60 & MA fast < MA slow |

| Hasil Voting | Bonus Skor |
|---|---|
| ≥ 2 BUY → **STRONG BUY** | +2 |
| 1 BUY → **WEAK BUY** | +1 |
| ≥ 2 SELL → **STRONG SELL** | +2 |
| 1 SELL → **WEAK SELL** | +1 |
| Tidak ada → **HOLD** | 0 |

### 🧠 AI Analyst (`ai_analyst.py`)
- Analisis per saham via **Ollama Mistral** (lokal, gratis)
- Prompt menyertakan data: harga, RSI, MA, sinyal, entry, TP, SL, dan RR
- AI memberikan **komentar entry plan** — apakah level entry/TP/SL masuk akal
- **Market Outlook** dari ringkasan Top 5 saham dikirim di akhir pesan Telegram

### 📐 Entry Plan & Risk Management
- **Entry, TP, SL** dihitung otomatis dari range High-Low hari ini
- **Risk/Reward Ratio** dihitung dan ditampilkan di Telegram
- **Lot sizing** berdasarkan modal dan persentase risiko yang dikonfigurasi
- Entry plan hanya dihasilkan untuk sinyal **BUY**

### 🔁 Backtest Engine (`backtest.py`)
- Simulasi sinyal BUY pada data historis 6 bulan
- Mendukung **parameter dinamis**: `rsi_period`, `ma_short`, `ma_long`
- Output: winrate, total return, jumlah trade, equity curve
- Fungsi `run_backtest_with_params()` untuk integrasi mudah

### 🔧 Auto-Tune Parameter (`tuner.py`)
- **Grid search** 9 kombinasi parameter (RSI x MA pairs)
- Backtest otomatis semua kombinasi, urutkan berdasarkan profit tertinggi
- Cetak **Top 3 parameter terbaik**
- Simpan parameter #1 ke `best_params.json` (dengan timestamp `last_tuned`)
- `load_best_params()` — baca parameter dari file, fallback ke default jika belum ada

### ⏰ Auto-Tune Berkala
- Bot menjalankan auto-tune **1x per minggu** secara otomatis
- Log: `Updating strategy parameters...`
- Setelah selesai, parameter langsung diperbarui — analisa live memakai parameter baru tanpa restart

### 📱 Notifikasi Telegram
- **Top 5 saham terbaik** dikirim setiap siklus saat market buka
- Format per saham: ticker, sinyal, entry/TP/SL, RR, lot, risiko, smart money, gap up, analisa AI
- Market Outlook di bagian bawah pesan
- **Anti-spam** — tidak kirim ulang jika sinyal tidak berubah

### 📊 Dashboard Web (`app.py` + `index.html`)
- Berjalan di `http://localhost:5000`
- **Signal cards** — satu kartu per saham dengan data lengkap
- **Stats bar** — total saham, jumlah BUY/SELL, smart money, gap up
- **Trading Performance** — total trade, winrate, total profit dari `trades.csv`
- **Auto-refresh** setiap 10 detik
- Endpoint: `GET /signals`, `GET /performance`

### 📤 Send Now (`send_now.py`)
- Kirim analisis Top 5 ke Telegram **bypass jam bursa**
- Berguna untuk testing atau kirim manual kapan saja

---

## 🚀 Cara Menjalankan

### 1. Install Dependensi

```bash
pip install -r requirements.txt
```

### 2. Konfigurasi Telegram

Edit `config.py`:
```python
TELEGRAM_BOT_TOKEN = "token_bot_anda"
TELEGRAM_CHAT_ID   = "chat_id_anda"
```

Cara dapat token & chat ID:
1. Buka Telegram → cari **@BotFather** → `/newbot`
2. Salin token yang diberikan
3. Kirim pesan ke bot baru, buka: `https://api.telegram.org/bot<TOKEN>/getUpdates`
4. Cari `"chat":{"id": ...}` untuk Chat ID

### 3. Jalankan Bot (Terminal 1)

```bash
python main.py
```

### 4. Jalankan Dashboard (Terminal 2)

```bash
python app.py
```

Buka browser: `http://localhost:5000`

### 5. (Opsional) Auto-Tune Parameter

```bash
python tuner.py BBCA.JK
```

### 6. (Opsional) Kirim Analisis Sekarang

```bash
python send_now.py
```

---

## 🔁 Alur Kerja Sistem

```
Bot start
  └── baca best_params.json → set parameter aktif (RSI, MA)

Loop tiap 5 menit:
  ├── Cek 7 hari sejak tune terakhir?
  │     └── "Updating strategy parameters..."
  │         auto_tune() → simpan best_params.json → reload parameter
  ├── FASE 0: Monitor posisi aktif
  ├── FASE 1: Scan semua saham
  │     ├── calculate_indicators(rsi_period, ma_short, ma_long)
  │     ├── analyze_volume() → Smart Money
  │     ├── detect_gap() → Gap Up confidence
  │     ├── generate_signal()
  │     ├── multi_strategy_confirmation() → bonus skor
  │     ├── calculate_score()
  │     ├── generate_trade_plan() → entry/TP/SL (BUY only)
  │     └── generate_ai_analysis() → analisa + komentar entry
  ├── FASE 2: Ranking Top 5
  ├── FASE 3: Broadcast Telegram (jika market buka)
  ├── FASE 4: Update last_signals.json (anti-spam)
  └── FASE 5: Simpan signals.json (untuk dashboard)
```

---

## ⚙️ Konfigurasi

### Modal & Risiko (environment variable atau edit `main.py`)

```python
TRADE_CAPITAL = 10_000_000  # Modal total (Rp)
RISK_PERCENT  = 1           # Persentase risiko per trade (%)
```

### Parameter Grid Auto-Tune (edit `tuner.py`)

```python
RSI_PERIODS = [7, 14, 21]
MA_PAIRS    = [(10, 20), (20, 50), (50, 100)]
```

### Saham Acuan Auto-Tune (edit `main.py`)

```python
TUNE_TICKER = "BBCA.JK"
```

---

## 📄 File Output

| File | Isi | Update |
|---|---|---|
| `signals.json` | Hasil analisis semua saham | Tiap 5 menit |
| `last_signals.json` | State sinyal terakhir (anti-spam) | Tiap 5 menit |
| `best_params.json` | Parameter terbaik + timestamp | Tiap minggu (auto-tune) |
| `trades.csv` | Riwayat trade historis | Manual / trade_logger |
| `trades.json` | Posisi aktif & tertutup | Manual / trade_logger |

### Contoh `best_params.json`

```json
{
    "rsi": 7,
    "ma_short": 20,
    "ma_long": 50,
    "source_ticker": "BBCA",
    "winrate": 33.33,
    "total_return": 1.85,
    "last_tuned": 1744800000.0
}
```

---

## 🛠️ Troubleshooting

| Masalah | Penyebab | Solusi |
|---|---|---|
| Dashboard kosong | `signals.json` belum ada | Jalankan `main.py` minimal 1 siklus |
| Sinyal tidak update | `main.py` tidak berjalan | Jalankan di terminal terpisah |
| AI error | Ollama tidak aktif | `ollama pull mistral`, jalankan Ollama |
| Entry plan tidak muncul | Sinyal bukan BUY | Normal — entry hanya untuk BUY |
| Port 5000 dipakai | Proses lain | `netstat -ano | findstr :5000` |
| Auto-tune gagal | Koneksi Yahoo Finance | Cek koneksi internet |

---

## ⚠️ Disclaimer

Project ini dibuat untuk **tujuan edukasi**. Sinyal yang dihasilkan bukan saran investasi. Selalu lakukan riset mandiri sebelum mengambil keputusan investasi.
