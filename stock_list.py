"""
stock_list.py - Daftar Saham Indonesia Aktif & Likuid
======================================================
Berisi daftar saham pilihan dari indeks LQ45 dan saham
dengan likuiditas tinggi di Bursa Efek Indonesia (BEI).

Semua kode saham menggunakan suffix '.JK' (Yahoo Finance format).

Fungsi:
    get_stock_list()             -> list lengkap (50 saham)
    get_stock_list_by_sector()   -> dict kelompok per sektor
    get_lq45()                   -> list LQ45 core
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


# ============================================================
# DAFTAR SAHAM LQ45 + LIKUID TINGGI (50 SAHAM)
# ============================================================
# Dikelompokkan per sektor untuk kemudahan referensi

_PERBANKAN = [
    "BBCA.JK",   # Bank Central Asia
    "BBRI.JK",   # Bank Rakyat Indonesia
    "BMRI.JK",   # Bank Mandiri
    "BBNI.JK",   # Bank Negara Indonesia
    "BRIS.JK",   # Bank Syariah Indonesia
    "ARTO.JK",   # Bank Jago (digital bank growth)
    "BTPS.JK",   # Bank BTPN Syariah
]

_TELEKOMUNIKASI = [
    "TLKM.JK",   # Telkom Indonesia
    "EXCL.JK",   # XL Axiata
    "ISAT.JK",   # Indosat Ooredoo Hutchison
]

_ENERGI_TAMBANG = [
    "ADRO.JK",   # Adaro Energy
    "PTBA.JK",   # Bukit Asam (batubara)
    "ITMG.JK",   # Indo Tambangraya Megah
    "INCO.JK",   # Vale Indonesia (nikel)
    "ANTM.JK",   # Aneka Tambang (emas & nikel)
    "MDKA.JK",   # Merdeka Copper Gold
    "PTPP.JK",   # PP (Pembangunan Perumahan)
    "MEDC.JK",   # Medco Energi Internasional
]

_CONSUMER_GOODS = [
    "ICBP.JK",   # Indofood CBP Sukses Makmur
    "INDF.JK",   # Indofood Sukses Makmur
    "UNVR.JK",   # Unilever Indonesia
    "MYOR.JK",   # Mayora Indah
    "SIDO.JK",   # Industri Jamu & Farmasi Sido Muncul
    "ULTJ.JK",   # Ultra Jaya Milk Industry
    "KLBF.JK",   # Kalbe Farma
    "MAPA.JK",   # MAP Aktif Adiperkasa (retail fashion)
]

_INDUSTRI_INFRASTRUKTUR = [
    "ASII.JK",   # Astra International
    "GGRM.JK",   # Gudang Garam
    "HMSP.JK",   # HM Sampoerna
    "SRIL.JK",   # Sri Rejeki Isman (tekstil)
    "WTON.JK",   # Wijaya Karya Beton
    "WIKA.JK",   # Wijaya Karya
    "WSKT.JK",   # Waskita Karya
    "JSMR.JK",   # Jasa Marga (tol)
]

_PROPERTI_REITS = [
    "BSDE.JK",   # Bumi Serpong Damai
    "PWON.JK",   # Pakuwon Jati
    "CTRA.JK",   # Ciputra Development
    "SMRA.JK",   # Summarecon Agung
    "LPKR.JK",   # Lippo Karawaci
]

_TEKNOLOGI_DIGITAL = [
    "EMTK.JK",   # Elang Mahkota Teknologi
    "GOTO.JK",   # GoTo Gojek Tokopedia
    "BUKA.JK",   # Bukalapak
    "DMMX.JK",   # Digital Mediatama Maxima
]

_KEUANGAN_NON_BANK = [
    "BMTR.JK",   # Global Mediacom
    "PANS.JK",   # Panin Sekuritas
    "MFIN.JK",   # Mandala Multifinance
    "BBLD.JK",   # Buana Finance
]

_AGRIKULTUR = [
    "AALI.JK",   # Astra Agro Lestari (CPO)
    "SIMP.JK",   # Salim Ivomas Pratama (CPO)
    "SSMS.JK",   # Sawit Sumbermas Sarana
]

# ============================================================
# DAFTAR GABUNGAN LENGKAP (50 saham)
# ============================================================
_ALL_STOCKS = (
    _PERBANKAN
    + _TELEKOMUNIKASI
    + _ENERGI_TAMBANG
    + _CONSUMER_GOODS
    + _INDUSTRI_INFRASTRUKTUR
    + _PROPERTI_REITS
    + _TEKNOLOGI_DIGITAL
    + _KEUANGAN_NON_BANK
    + _AGRIKULTUR
)

# ============================================================
# CORE LQ45 (25 saham paling liquid & paling sering di LQ45)
# ============================================================
_LQ45_CORE = [
    "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "BRIS.JK",
    "TLKM.JK", "ASII.JK",
    "ADRO.JK", "PTBA.JK", "ANTM.JK", "INCO.JK",
    "ICBP.JK", "INDF.JK", "KLBF.JK", "UNVR.JK",
    "BSDE.JK", "CTRA.JK", "PWON.JK",
    "JSMR.JK", "WIKA.JK",
    "AALI.JK",
    "GOTO.JK", "EMTK.JK",
    "MEDC.JK", "MDKA.JK",
]


# ============================================================
# PUBLIC API
# ============================================================

def get_stock_list() -> list[str]:
    """
    Kembalikan list lengkap 50 saham Indonesia aktif & likuid tinggi.

    Returns
    -------
    list[str]
        Daftar kode saham dengan suffix '.JK' (format Yahoo Finance).

    Contoh::

        from stock_list import get_stock_list

        saham = get_stock_list()
        # ['BBCA.JK', 'BBRI.JK', 'BMRI.JK', ...]
    """
    return list(_ALL_STOCKS)


def get_lq45() -> list[str]:
    """
    Kembalikan list 25 saham core LQ45 paling likuid.

    Returns
    -------
    list[str]
        Daftar kode saham LQ45 core.
    """
    return list(_LQ45_CORE)


def get_stock_list_by_sector() -> dict[str, list[str]]:
    """
    Kembalikan dictionary saham dikelompokkan per sektor.

    Returns
    -------
    dict[str, list[str]]
        Key = nama sektor, Value = list kode saham.

    Contoh::

        from stock_list import get_stock_list_by_sector

        sektoral = get_stock_list_by_sector()
        print(sektoral['Perbankan'])
        # ['BBCA.JK', 'BBRI.JK', ...]
    """
    return {
        "Perbankan":              _PERBANKAN,
        "Telekomunikasi":         _TELEKOMUNIKASI,
        "Energi & Pertambangan":  _ENERGI_TAMBANG,
        "Consumer Goods":         _CONSUMER_GOODS,
        "Industri & Infrastruktur": _INDUSTRI_INFRASTRUKTUR,
        "Properti & REITs":       _PROPERTI_REITS,
        "Teknologi & Digital":    _TEKNOLOGI_DIGITAL,
        "Keuangan Non-Bank":      _KEUANGAN_NON_BANK,
        "Agrikultur":             _AGRIKULTUR,
    }


# ============================================================
# SELF-TEST
# ============================================================
if __name__ == "__main__":
    semua   = get_stock_list()
    lq45    = get_lq45()
    sektoral = get_stock_list_by_sector()

    print("=" * 55)
    print("  STOCK LIST - Indonesia Active & Liquid Stocks")
    print("=" * 55)
    print(f"  Total saham  : {len(semua)}")
    print(f"  LQ45 Core    : {len(lq45)}")
    print(f"  Sektor       : {len(sektoral)}")
    print()

    print("-" * 55)
    print("  DAFTAR PER SEKTOR:")
    print("-" * 55)
    for sektor, daftar in sektoral.items():
        tickers = ", ".join(t.replace(".JK", "") for t in daftar)
        print(f"  [{sektor}]")
        print(f"    {tickers}")
        print()

    print("-" * 55)
    print(f"  LQ45 CORE ({len(lq45)} saham):")
    print("-" * 55)
    lq45_str = ", ".join(t.replace(".JK", "") for t in lq45)
    print(f"  {lq45_str}")
    print()

    print("-" * 55)
    print(f"  FULL LIST ({len(semua)} saham):")
    print("-" * 55)
    print(f"  {semua}")
    print("=" * 55)
