@echo off
:: Mengarahkan ke lokasi spesifik hasil instalasi Python 3.12 dari pip/winget sebelumnya
set "PYTHON_PATH=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
set PYTHONIOENCODING=utf-8

:: Ganti warna teks konsol agar lebih rapi (opsional)
color 0A

:: Cari tahu jika parameter diberikan argumen dari user ke bat
if exist "%PYTHON_PATH%" (
    echo ----------------------------------------------------
    echo Menjalankan Stock Analyzer...
    echo Menggunakan Python: "%PYTHON_PATH%"
    echo ----------------------------------------------------
    
    :: Meneruskan argumen apa pun ke main.py (misal AAPL --notify)
    :: Jika tidak ada argumen, otomatis uji notifier.py terlebih dahulu
    if "%~1"=="" (
        echo Menjalankan Test Notifier.py karena tidak ada perintah tiket saham...
        "%PYTHON_PATH%" notifier.py
    ) else (
        "%PYTHON_PATH%" main.py %*
    )
    
) else (
    echo [ERROR] Eksekusi Langsung Gagal!
    echo Python 3.12 tidak ditemukan di %PYTHON_PATH%.
    echo Mencoba jalan manual...
    python main.py %*
)

echo.
pause
