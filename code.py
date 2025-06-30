# ==============================================================================
# === BLOK 1: IMPORT & KONFIGURASI GLOBAL ===
# ==============================================================================
# Tujuan: Mengimpor semua library yang diperlukan, melakukan setup awal untuk
# database, logger, dan hashing. Mendefinisikan konstanta dan path file.

import os
import re
import time
import uuid # Digunakan untuk menghasilkan ID unik
import datetime
from typing import List, Optional, Annotated # Digunakan untuk type hinting

# --- Import Library Eksternal Baru ---
# Pydantic untuk definisi model data, validasi, dan serialisasi
from pydantic import BaseModel, Field, EmailStr, ValidationError, ConfigDict, PlainSerializer, BeforeValidator
# TinyDB sebagai database NoSQL berbasis JSON
from tinydb import TinyDB, Query
# Passlib untuk hashing password dan PIN dengan aman (menggunakan bcrypt)
from passlib.context import CryptContext
# Loguru untuk manajemen logging yang lebih canggih dan terstruktur
from loguru import logger
# Moneyed untuk menangani mata uang dan perhitungan finansial secara akurat
from moneyed import Money, IDR # Mengimpor kelas Money dan mata uang IDR (Rupiah Indonesia)


# --- Konfigurasi Path Folder & File ---
# Menggunakan path penyimpanan yang Anda spesifikasikan
FOLDER_DATABASE = "/home/vivobook14/Source_code/Repository/Mart_Bank_Project/database"
FOLDER_LOG = "/home/vivobook14/Source_code/Repository/Mart_Bank_Project/logs"

# Pastikan folder penyimpanan ada; dibuat jika belum ada
os.makedirs(FOLDER_DATABASE, exist_ok=True)
os.makedirs(FOLDER_LOG, exist_ok=True)

# Nama file database utama dan log aktivitas
NAMA_FILE_DATABASE = "bear_mart_bank_data.json"
NAMA_FILE_LOG = "activity.log"

# Gabungkan path folder dengan nama file
PATH_DATABASE = os.path.join(FOLDER_DATABASE, NAMA_FILE_DATABASE)
PATH_LOG = os.path.join(FOLDER_LOG, NAMA_FILE_LOG)


# --- Setup Logging (Loguru) ---
# Menghapus handler default Loguru untuk mengatur handler kustom
logger.remove()
# Menambahkan handler file baru dengan konfigurasi yang diinginkan
logger.add(
    PATH_LOG,
    rotation="5 MB",      # Rotasi file log saat ukuran mencapai 5 MB
    retention="10 days",  # Hanya menyimpan log dari 10 hari terakhir
    level="INFO",         # Level log minimum yang akan dicatat (INFO, WARNING, ERROR, dll.)
    format="{time:YYYY-MM-DD HH:mm:ss} - {message}", # Format output log sesuai permintaan
    encoding='utf-8'      # Menggunakan encoding UTF-8 untuk mendukung karakter non-ASCII
)

# --- Setup Hashing Password dan PIN (Passlib) ---
# Membuat context untuk hashing; menggunakan algoritma bcrypt yang kuat
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Setup Database (TinyDB) ---
# Menginisialisasi objek TinyDB; akan membuat/membuka file JSON di PATH_DATABASE
db = TinyDB(PATH_DATABASE, indent=4, ensure_ascii=False)

# Mendefinisikan objek Query untuk setiap "tabel" di TinyDB
# Ini membuat sintaks kueri lebih terbaca (misalnya, PenggunaQuery.username == "admin")
PenggunaQuery = Query()
ProdukQuery = Query()
TransaksiQuery = Query()
PesananQuery = Query()
KonfigurasiQuery = Query() # Query spesifik untuk tabel konfigurasi sistem


# --- Konstanta & Konfigurasi Lainnya ---
PERAN_PELANGGAN = "PELANGGAN" # Konstanta untuk peran pengguna
PERAN_ADMIN = "ADMIN"       # Konstanta untuk peran admin

BATAS_PERCOBAAN_LOGIN = 3 # Batas maksimum percobaan login sebelum akun terkunci
DURASI_KUNCI_AKUN_MENIT = 5 # Durasi akun terkunci dalam menit

# Kredensial akun admin default; hanya digunakan saat inisialisasi database pertama kali
ADMIN_USERNAME_DEFAULT = "admin"
ADMIN_PASSWORD_DEFAULT = "AdminBearMart123!" # Kata sandi awal untuk admin
ADMIN_PIN_DEFAULT = "123456"             # PIN Bank awal untuk admin

# Kategori produk default yang akan ada saat database diinisialisasi pertama kali
KATEGORI_PRODUK_DEFAULT = ["Makanan Ringan", "Minuman", "Kebutuhan Pokok", "Perlengkapan Mandi", "Produk Segar", "Elektronik Rumah Tangga", "Lainnya"]

# >>> Perbaikan: Tambahkan ID Konstan untuk Dokumen Konfigurasi Sistem <<<
# Menggunakan ID yang tetap memastikan kita selalu bisa menemukan dan memperbarui
# dokumen konfigurasi utama di TinyDB, mengatasi potensi masalah saat startup.
SYSTEM_CONFIG_ID = "system_main_config" # ID unik yang akan selalu digunakan untuk dokumen konfigurasi utama
# >>> ------------------------------------------------------------- <<<

# === TAMBAHKAN FUNGSI INI ===
# Helper untuk Validator objek Money dengan Pydantic
def money_validator(v) -> Money:
    """Mengubah angka (int/float) menjadi objek Money saat data dimuat (validasi)."""
    if isinstance(v, Money):
        # Jika sudah merupakan objek Money, langsung kembalikan
        return v
    if isinstance(v, (int, float)):
        # Jika berupa angka, buat objek Money baru
        return Money(v, IDR)
    # Jika tipe datanya aneh, lemparkan error
    raise ValueError("Nilai untuk saldo harus berupa angka atau objek Money.")

# --- Helper untuk Serializer Objek Money dengan Pydantic ---
# Pydantic perlu tahu cara mengubah objek Money menjadi format yang bisa disimpan (JSON)
def money_serializer(m: Money) -> float:
    """Mengubah objek Money menjadi representasi float dari jumlahnya saat diserialisasi."""
    return float(m.amount)

# Membuat alias tipe kustom dua arah:
# - BeforeValidator: Mengubah angka -> Money (saat membaca/memvalidasi)
# - PlainSerializer: Mengubah Money -> float (saat menyimpan/output)
JsonSafeMoney = Annotated[
    Money,
    BeforeValidator(money_validator),
    PlainSerializer(money_serializer)
]


# ==============================================================================
# === BLOK 2: MODEL DATA DENGAN PYDANTIC ===
# ==============================================================================
# Tujuan: Mendefinisikan struktur data aplikasi menggunakan Pydantic BaseModel.
# Pydantic menyediakan validasi data, konversi tipe, dan serialisasi/deserialisasi otomatis.
# Menggantikan metode manual __init__, ke_dict, dan dari_dict di kelas data.

class ItemKeranjang(BaseModel):
    # Konfigurasi model untuk mengizinkan penggunaan tipe data kustom seperti Money
    model_config = ConfigDict(arbitrary_types_allowed=True)

    produk_id: str      # ID unik produk yang ada di keranjang
    nama_produk: str    # Nama produk (untuk memudahkan tampilan tanpa lookup produk asli)
    harga_satuan: JsonSafeMoney # Harga per unit produk (menggunakan objek Money)
    jumlah: int         # Jumlah unit produk di keranjang

    @property
    def subtotal(self) -> JsonSafeMoney:
        """Menghitung subtotal untuk item ini (harga per unit * jumlah)."""
        return self.harga_satuan * self.jumlah # Operasi perkalian antar objek Money

class TransaksiBank(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4())) # ID unik untuk setiap transaksi (otomatis dibuat)
    user_id_sumber: str     # ID pengguna yang memulai transaksi (pengirim dana, akun yang didebit)
    user_id_tujuan: Optional[str] = None # ID pengguna tujuan (penerima dana); Opsional untuk deposit/withdraw/pembayaran toko
    jenis_transaksi: str    # Jenis transaksi (misalnya, "Deposit", "Withdraw", "Transfer", "Pembayaran Toko")
    jumlah: JsonSafeMoney   # Jumlah uang yang ditransaksikan (menggunakan objek Money)
    keterangan: str         # Deskripsi singkat transaksi
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.now) # Waktu transaksi (otomatis dibuat)
    saldo_akhir_sumber: JsonSafeMoney # Saldo akun sumber SETELAH transaksi selesai
    saldo_akhir_tujuan: Optional[JsonSafeMoney] = None # Saldo akun tujuan SETELAH transaksi selesai (untuk transfer)

class PesananToko(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4())) # ID unik untuk setiap pesanan toko (otomatis dibuat)
    user_id: str            # ID pengguna yang membuat pesanan
    items_pesanan: List[ItemKeranjang] # Daftar item yang dibeli dalam pesanan ini (list objek ItemKeranjang Pydantic)
    total_harga: JsonSafeMoney # Total harga keseluruhan pesanan (menggunakan objek Money)
    metode_pembayaran: str = "Bank Bear Mart" # Metode pembayaran yang digunakan
    status_pesanan: str = "Selesai" # Status pesanan (default "Selesai" untuk simplifikasi)
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.now) # Waktu pesanan dibuat (otomatis dibuat)

class Pengguna(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4())) # ID unik untuk setiap pengguna (otomatis dibuat)
    username: str           # Nama pengguna (login)
    password_hash: str      # Hash dari password pengguna (menggunakan Passlib)
    pin_hash: Optional[str] = None # Hash dari PIN Bank pengguna; Opsional (admin default punya PIN)
    peran: str              # Peran pengguna ("PELANGGAN" atau "ADMIN")
    nama_lengkap: Optional[str] = "" # Nama lengkap pengguna; Opsional
    email: Optional[EmailStr] = None # Alamat email pengguna; Opsional (Pydantic memvalidasi format email)
    saldo_bank: JsonSafeMoney = Money(0, IDR) # Saldo bank pengguna (menggunakan objek Money, default 0 IDR)
    riwayat_transaksi_bank_ids: List[str] = [] # Daftar ID transaksi bank terkait pengguna ini
    riwayat_pesanan_toko_ids: List[str] = [] # Daftar ID pesanan toko terkait pengguna ini
    gagal_login_count: int = 0 # Hitungan percobaan login yang gagal (untuk fitur kunci akun)
    akun_terkunci_hingga: Optional[datetime.datetime] = None # Timestamp kapan akun terkunci akan berakhir; None jika tidak terkunci
    dibuat_pada: datetime.datetime = Field(default_factory=datetime.datetime.now) # Waktu akun dibuat (otomatis dibuat)

    # Metode untuk verifikasi password pengguna menggunakan Passlib
    def verifikasi_password(self, password: str) -> bool:
        return pwd_context.verify(password, self.password_hash)

    # Metode untuk verifikasi PIN Bank pengguna menggunakan Passlib
    def verifikasi_pin(self, pin: str) -> bool:
        return pwd_context.verify(pin, self.pin_hash) if self.pin_hash else False # Hanya verifikasi jika pin_hash ada

    # Metode untuk mengatur atau mengubah PIN Bank pengguna (menggunakan Passlib)
    def set_pin(self, pin_baru: str):
        self.pin_hash = pwd_context.hash(pin_baru) # Membuat hash PIN baru dan menyimpannya

class Produk(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4())) # ID unik untuk setiap produk (otomatis dibuat)
    nama: str           # Nama produk
    harga: JsonSafeMoney # Harga produk per unit (menggunakan objek Money)
    stok: int           # Jumlah stok produk yang tersedia
    kategori: str       # Kategori produk
    deskripsi: str = "" # Deskripsi produk; Opsional
    dibuat_pada: datetime.datetime = Field(default_factory=datetime.datetime.now) # Waktu produk dibuat
    diperbarui_pada: datetime.datetime = Field(default_factory=datetime.datetime.now) # Waktu produk terakhir diperbarui

# Kelas Keranjang Belanja (tetap berbasis memori selama sesi pengguna login)
# Item di dalamnya sekarang adalah instance dari model Pydantic ItemKeranjang
class KeranjangBelanja:
    def __init__(self):
        # Menggunakan dictionary produk_id -> Pydantic ItemKeranjang
        self.items: dict[str, ItemKeranjang] = {}

    def tambah_item(self, produk: Produk, jumlah: int):
        """Menambahkan jumlah produk ke keranjang atau menambah item baru."""
        if jumlah <= 0:
            return # Tidak melakukan apa-apa jika jumlah non-positif

        # Cari item yang sudah ada di keranjang berdasarkan produk ID
        item_yang_ada = self.items.get(produk.id)

        if item_yang_ada:
            # Jika produk sudah ada di keranjang, tambahkan jumlahnya
            item_yang_ada.jumlah += jumlah
        else:
            # Jika produk belum ada, buat objek ItemKeranjang baru dan tambahkan ke dictionary items
            item_baru = ItemKeranjang(
                produk_id=produk.id,
                nama_produk=produk.nama,
                harga_satuan=produk.harga, # Ini adalah objek Money dari objek Produk
                jumlah=jumlah
            )
            self.items[produk.id] = item_baru # Tambahkan item baru ke keranjang

    def hapus_item(self, produk_id: str) -> bool:
        """Menghapus item dari keranjang berdasarkan ID produk."""
        if produk_id in self.items:
            del self.items[produk_id] # Hapus item dari dictionary
            return True # Berhasil menghapus
        return False # Produk ID tidak ditemukan di keranjang

    def ubah_jumlah_item(self, produk_id: str, jumlah_baru: int) -> bool:
        """Mengubah jumlah item di keranjang berdasarkan ID produk."""
        if produk_id in self.items:
            if jumlah_baru > 0:
                self.items[produk_id].jumlah = jumlah_baru # Ubah jumlah jika jumlah baru positif
            elif jumlah_baru == 0:
                self.hapus_item(produk_id) # Hapus item jika jumlah baru 0
            else:
                # Jika jumlah baru negatif, cetak pesan error dan tidak melakukan apa-apa
                print("Jumlah tidak boleh negatif.")
                return False # Gagal karena jumlah negatif
            return True # Berhasil mengubah atau menghapus
        return False # Produk ID tidak ditemukan di keranjang

    @property
    def total_belanja(self) -> JsonSafeMoney:
        """Menghitung total harga dari semua item di keranjang."""
        # Total belanja dihitung dengan menjumlahkan subtotal setiap item
        total = Money(0, IDR) # Mulai dengan 0 IDR (objek Money)
        for item in self.items.values():
            total += item.subtotal # Penjumlahan objek Money
        return total

    def kosongkan_keranjang(self):
        """Menghapus semua item dari keranjang belanja."""
        self.items.clear()

    def dapatkan_semua_item_dict(self) -> List[dict]:
        """Mengembalikan list dictionary dari semua item di keranjang."""
        # Digunakan saat menyimpan pesanan ke database (items_pesanan disimpan sebagai list dictionary)
        return [item.model_dump(mode='json') for item in self.items.values()]


# ==============================================================================
# === BLOK 3: FUNGSI AKSES DATA DENGAN TINYDB ===
# ==============================================================================
# Tujuan: Menyediakan fungsi-fungsi untuk berinteraksi dengan TinyDB.
# Menggantikan interaksi langsung dengan dictionary global data_global.
# Fungsi-fungsi ini mengambil/menyimpan objek Pydantic atau dictionary.

def dapatkan_pengguna_by_id(user_id: str) -> Optional[Pengguna]:
    """Mengambil data pengguna dari TinyDB berdasarkan ID unik."""
    # Menggunakan Query pada field 'id'
    hasil = db.table('pengguna').get(PenggunaQuery.id == user_id)
    # Jika data ditemukan (hasil bukan None), buat objek Pengguna dari dictionary yang didapat
    return Pengguna(**hasil) if hasil else None

def dapatkan_pengguna_by_username(username: str) -> Optional[Pengguna]:
    """Mengambil data pengguna dari TinyDB berdasarkan username (case-insensitive)."""
    # --- LOGIKA BARU YANG LEBIH KUAT DAN EKSPLISIT ---
    # Menggunakan metode .test() dengan fungsi lambda. Ini adalah cara
    # paling 'failsafe' untuk melakukan perbandingan kustom dan menghindari
    # masalah interpretasi pada .lower().
    # Fungsi lambda ini akan dijalankan untuk setiap field 'username' di database.
    # 'db_val' adalah nilai username yang tersimpan di database.
    # Kita juga menambahkan 'isinstance(db_val, str)' untuk keamanan,
    # memastikan kita tidak mencoba .lower() pada sesuatu yang bukan string.
    hasil = db.table('pengguna').get(
        PenggunaQuery.username.test(lambda db_val: isinstance(db_val, str) and db_val.lower() == username.lower())
    )
    # Baris di bawah ini sudah benar dan tidak perlu diubah.
    # Ia akan membuat objek Pengguna jika 'hasil' adalah dictionary, atau mengembalikan None jika tidak ada hasil.
    return Pengguna(**hasil) if hasil else None

def simpan_pengguna(pengguna: Pengguna):
    """Menyimpan atau memperbarui data pengguna di TinyDB."""
    # Mengubah objek Pengguna Pydantic menjadi dictionary yang siap disimpan ke JSON
    data_dict = pengguna.model_dump(mode='json')
    # Menggunakan upsert: jika ada dokumen dengan ID yang sama, perbarui; jika tidak, masukkan baru
    db.table('pengguna').upsert(data_dict, PenggunaQuery.id == pengguna.id)


def dapatkan_produk_by_id(produk_id: str) -> Optional[Produk]:
    """Mengambil data produk dari TinyDB berdasarkan ID unik."""
    hasil = db.table('produk').get(ProdukQuery.id == produk_id)
    # Jika data ditemukan, buat objek Produk dari dictionary
    return Produk(**hasil) if hasil else None

def dapatkan_semua_produk() -> List[Produk]:
    """Mengambil semua data produk dari TinyDB."""
    # Mengambil semua entry dari tabel 'produk' dan mengubah setiap dictionary menjadi objek Produk
    return [Produk(**p) for p in db.table('produk').all()]

def simpan_produk(produk: Produk):
    """Menyimpan atau memperbarui data produk di TinyDB."""
    produk.diperbarui_pada = datetime.datetime.now() # Update timestamp terakhir diperbarui
    data_dict = produk.model_dump(mode='json')
    db.table('produk').upsert(data_dict, ProdukQuery.id == produk.id)

def hapus_produk_by_id(produk_id: str) -> bool:
    """Menghapus produk dari TinyDB berdasarkan ID unik."""
    # Menghapus dokumen dari tabel 'produk' berdasarkan ID
    hapus_count = db.table('produk').remove(ProdukQuery.id == produk_id)
    return hapus_count > 0 # Mengembalikan True jika setidaknya satu dokumen terhapus


def simpan_transaksi_bank(transaksi: TransaksiBank):
    """Menyimpan transaksi bank baru ke TinyDB."""
    data_dict = transaksi.model_dump(mode='json')
    # Memasukkan dokumen baru ke tabel 'transaksi_bank'. TinyDB akan memberi doc_id internal.
    # ID unik transaksi (dari Pydantic Model) disimpan sebagai field 'id'.
    db.table('transaksi_bank').insert(data_dict)

def dapatkan_transaksi_bank_by_id(transaksi_id: str) -> Optional[TransaksiBank]:
    """Mengambil transaksi bank dari TinyDB berdasarkan ID unik."""
    hasil = db.table('transaksi_bank').get(TransaksiQuery.id == transaksi_id)
    return TransaksiBank(**hasil) if hasil else None

def dapatkan_semua_transaksi_bank() -> List[TransaksiBank]:
     """Mengambil semua transaksi bank dari TinyDB."""
     return [TransaksiBank(**t) for t in db.table('transaksi_bank').all()]


def simpan_pesanan_toko(pesanan: PesananToko):
    """Menyimpan pesanan toko baru ke TinyDB."""
    data_dict = pesanan.model_dump(mode='json')
    # Memasukkan dokumen baru ke tabel 'pesanan_toko'. TinyDB akan memberi doc_id internal.
    # ID unik pesanan (dari Pydantic Model) disimpan sebagai field 'id'.
    db.table('pesanan_toko').insert(data_dict)

def dapatkan_pesanan_toko_by_id(pesanan_id: str) -> Optional[PesananToko]:
    """Mengambil pesanan toko dari TinyDB berdasarkan ID unik."""
    hasil = db.table('pesanan_toko').get(PesananQuery.id == pesanan_id)
    return PesananToko(**hasil) if hasil else None

def dapatkan_semua_pesanan_toko() -> List[PesananToko]:
    """Mengambil semua pesanan toko dari TinyDB."""
    return [PesananToko(**p) for p in db.table('pesanan_toko').all()]

# >>> Perbaikan: Fungsi untuk mengelola konfigurasi sistem <<<
# Fungsi ini lebih tangguh saat startup database kosong atau tidak konsisten.
def dapatkan_konfigurasi() -> dict:
    """Mengambil konfigurasi sistem dari TinyDB. Mengembalikan struktur default jika belum ada dan menginsertnya."""
    # Perbaikan: Coba ambil SEMUA dokumen dari tabel konfigurasi terlebih dahulu.
    # Pada startup, ini akan mengembalikan list kosong ([]) jika tabel 'konfigurasi' belum ada atau kosong,
    # dan ini adalah operasi yang lebih stabil daripada menggunakan Query.
    try:
        config_docs = db.table('konfigurasi').all()
    except Exception as e:
        # Tangani potensi error jika membaca tabel .all() saja bermasalah (sangat jarang tapi bisa terjadi)
        logger.error(f"Error reading config table using .all(): {e}. Initializing default config structure.")
        config_docs = [] # Paksa list kosong untuk memicu proses inisialisasi default

    if not config_docs:
        # Jika list dokumen kosong (tabel 'konfigurasi' benar-benar kosong atau tidak dapat dibaca)
        logger.info(f"System configuration table is empty or corrupt. Creating and inserting default document (ID: {SYSTEM_CONFIG_ID}).")
        default_config = {
           "id": SYSTEM_CONFIG_ID, # <<< WAJIB: Tetapkan ID konstan untuk dokumen konfigurasi utama
           "nama_toko": "Bear Mart",
           "kategori_produk": KATEGORI_PRODUK_DEFAULT.copy(),
           "admin_dibuat": False,
           "setup_selesai": False # Flag ini akan menjadi True setelah inisialisasi penuh selesai
        }
        try:
             # Langsung masukkan dokumen konfigurasi default ke dalam tabel.
             # Gunakan truncate() sebelum insert sebagai safety jika ada data invalid di awal akibat error sebelumnya.
             db.table('konfigurasi').truncate() # Kosongkan tabel konfigurasi (jika ada data invalid)
             db.table('konfigurasi').insert(default_config.copy()) # Masukkan salinan dari dictionary default
             logger.info("Default configuration inserted into DB.")
        except Exception as e:
             # Tangani error jika proses insert awal gagal (misalnya masalah izin file)
             logger.error(f"Error inserting default config document after table was empty: {e}")
        return default_config # Kembalikan struktur default yang sudah dibuat dan diinsert

    else:
        # Jika list dokumen tidak kosong, asumsikan dokumen pertama adalah konfigurasi utama.
        # Ambil dokumen pertama dari list hasil .all(). Ini adalah dictionary Python.
        config_data = config_docs[0]

        # Merge data yang didapat dari DB dengan struktur default untuk memastikan
        # semua field ada, bahkan jika field baru ditambahkan di versi kode mendatang.
        merged_config = {
            "id": SYSTEM_CONFIG_ID, # Pastikan ID-nya benar, bahkan jika data DB corrupt
            "nama_toko": "Bear Mart", # Nilai default fallback jika field 'nama_toko' hilang di DB
            "kategori_produk": KATEGORI_PRODUK_DEFAULT.copy(), # Nilai default fallback
            "admin_dibuat": False, # Nilai default fallback
            "setup_selesai": False # Nilai default fallback
        }
        # Perbarui dictionary merged_config dengan data yang ditemukan di DB
        merged_config.update(config_data)
        # Pastikan ID-nya tetap benar (mengganti jika entah bagaimana berbeda di data DB)
        merged_config["id"] = SYSTEM_CONFIG_ID
        return merged_config # Kembalikan data konfigurasi yang sudah ada (mungkin sudah dimodifikasi)


def simpan_konfigurasi(config_data: dict):
    """Menyimpan atau memperbarui konfigurasi sistem di TinyDB menggunakan upsert pada ID konstan."""
    # Perbaikan: Gunakan upsert berdasarkan ID konstan SYSTEM_CONFIG_ID.
    # Pastikan dictionary yang akan disimpan memiliki field 'id' dengan nilai SYSTEM_CONFIG_ID.
    if "id" not in config_data or config_data["id"] != SYSTEM_CONFIG_ID:
        # Jika ID hilang atau salah, tambahkan/perbaiki sebelum menyimpan
        config_data["id"] = SYSTEM_CONFIG_ID
        logger.warning(f"Configuration data missing or incorrect ID ({config_data.get('id', 'None')}) before saving. Assigned {SYSTEM_CONFIG_ID}.")

    try:
        # Menggunakan upsert: perbarui dokumen yang memiliki 'id' sama dengan SYSTEM_CONFIG_ID jika ada,
        # atau masukkan sebagai dokumen baru jika tidak ada. Ini menjamin hanya ada satu dokumen konfigurasi utama.
        db.table('konfigurasi').upsert(config_data, KonfigurasiQuery.id == SYSTEM_CONFIG_ID)
        # logger.debug("Configuration saved successfully.") # Log ini terlalu sering, nonaktifkan
    except Exception as e:
        # Tangani error saat menyimpan konfigurasi
        logger.error(f"Error saving configuration using upsert: {e}")
# >>> Akhir Perbaikan Fungsi Konfigurasi Sistem <<<


# ==============================================================================
# === BLOK 4: INISIALISASI DATA AWAL ===
# ==============================================================================
# Tujuan: Memastikan database memiliki data dasar (admin, produk contoh, config)
# saat pertama kali dijalankan. Ini termasuk pembuatan akun admin default
# dan produk contoh jika database masih kosong atau belum diinisialisasi.

# >>> Perbaikan: Pindahkan definisi buat_admin_default_jika_perlu DI SINI <<<
# Definisi fungsi buat_admin_default_jika_perlu harus berada SEBELUM
# fungsi inisialisasi_database_jika_perlu karena dipanggil di dalamnya.
def buat_admin_default_jika_perlu(konfigurasi: dict): # Menerima dictionary konfigurasi sebagai argumen
    """Membuat akun admin default jika belum ada di database pengguna."""
    # Cek apakah ada pengguna dengan username admin default dan peran ADMIN di tabel 'pengguna'
    # Menggunakan kueri kombinasi dengan objek Query
    # Di dalam fungsi buat_admin_default_jika_perlu:

    # Cek apakah ada pengguna dengan username admin default DAN peran ADMIN di tabel 'pengguna'

    # === LOGIKA BARU YANG LEBIH KUAT ===
    # 1. Cari pengguna berdasarkan username terlebih dahulu.
    #    Fungsi ini akan mengembalikan objek Pengguna atau None.
    calon_admin = dapatkan_pengguna_by_username(ADMIN_USERNAME_DEFAULT)

    # 2. Periksa hasilnya.
    #    Jika calon_admin ditemukan (bukan None) DAN perannya adalah ADMIN,
    #    maka admin_exists kita anggap True. Jika tidak, maka False.
    if calon_admin and calon_admin.peran == PERAN_ADMIN:
        admin_exists = True
    else:
        admin_exists = False
    # ======================================

    # Jika admin default tidak ditemukan di database
    if not admin_exists:
        logger.info(f"Akun admin default '{ADMIN_USERNAME_DEFAULT}' not found in DB. Creating new account.")
        try:
            # Membuat hash password dan PIN menggunakan Passlib untuk keamanan
            admin_password_hash = pwd_context.hash(ADMIN_PASSWORD_DEFAULT)
            admin_pin_hash = pwd_context.hash(ADMIN_PIN_DEFAULT)

            # Membuat objek Pengguna baru menggunakan Pydantic Model
            # ID unik akan di-generate otomatis oleh default_factory di model Pengguna
            admin_baru = Pengguna(
                username=ADMIN_USERNAME_DEFAULT,
                password_hash=admin_password_hash,
                pin_hash=admin_pin_hash,
                peran=PERAN_ADMIN, # Menggunakan konstanta peran admin
                nama_lengkap="Administrator Utama",
                email="admin@bearmart.system",
                saldo_bank=Money(0, IDR) # Memberikan saldo awal 0 dengan objek Money
            )
            simpan_pengguna(admin_baru) # Menyimpan objek pengguna admin baru ke TinyDB
            konfigurasi["admin_dibuat"] = True # Memperbarui flag 'admin_dibuat' di dictionary konfigurasi yang dilewatkan
            logger.info(f"Akun admin default '{ADMIN_USERNAME_DEFAULT}' berhasil dibuat.")
        except ValidationError as e:
            # Menangani error jika data admin default tidak valid menurut Pydantic Model
            logger.error(f"Gagal membuat model admin default karena validasi Pydantic: {e}")
        except Exception as e:
             # Menangani error tak terduga lainnya selama proses pembuatan admin
             logger.error(f"Error tak terduga saat membuat admin default: {e}")
    else:
         # Jika admin default sudah ada, pastikan flag 'admin_dibuat' di dictionary konfigurasi adalah True
         konfigurasi["admin_dibuat"] = True
         logger.info(f"Akun admin default '{ADMIN_USERNAME_DEFAULT}' already exists.")
    # Perbaikan: TIDAK PANGGIL simpan_konfigurasi() di sini.
    # Penyimpanan perubahan pada dictionary 'konfigurasi' (termasuk flag 'admin_dibuat')
    # akan dilakukan oleh fungsi pemanggil (inisialisasi_database_jika_perlu)
    # setelah semua langkah inisialisasi pada dictionary konfigurasi selesai.


# >>> DEFINISI inisialisasi_database_jika_perlu DITEMPATKAN SETELAH buat_admin_default_jika_perlu <<<
def inisialisasi_database_jika_perlu():
    """Memeriksa apakah database perlu diinisialisasi dan menjalankan setup awal.
    Termasuk memastikan konfigurasi sistem, admin, dan produk contoh ada."""
    # Perbaikan: Ambil konfigurasi sistem saat ini. Fungsi dapatkan_konfigurasi() sekarang
    #           menjamin adanya dokumen konfigurasi di TinyDB (akan membuatnya jika tidak ada).
    konfigurasi = dapatkan_konfigurasi() # Mengambil dictionary konfigurasi

    # Periksa flag 'setup_selesai' dari dictionary konfigurasi yang didapat
    if konfigurasi.get("setup_selesai", False):
        logger.info("Database already initialized (setup_selesai flag is True).")
        # Perbaikan: Masih panggil buat_admin_default_jika_perlu sebagai langkah pengamanan
        #           jika data admin terhapus meskipun flag setup_selesai True.
        # Ini akan update dictionary 'konfigurasi' jika admin baru dibuat.
        buat_admin_default_jika_perlu(konfigurasi)
        # Perbaikan: Simpan konfigurasi terakhir kalinya setelah cek/buat admin jika ada perubahan.
        # Ini penting jika admin baru dibuat di sini (buat_admin_default_jika_perlu tidak menyimpan config).
        simpan_konfigurasi(konfigurasi) # Menyimpan dictionary konfigurasi (termasuk flag admin_dibuat yang mungkin berubah)
        return # Keluar dari fungsi inisialisasi karena setup sudah selesai

    # Jika flag 'setup_selesai' adalah False (berarti ini adalah inisialisasi pertama atau proses sebelumnya terganggu)
    logger.info("Performing initial database setup (setup_selesai is False).")

    # Buat Akun Admin Default jika belum ada.
    # Fungsi ini akan memperbarui dictionary 'konfigurasi' yang dilewatkan
    # jika admin baru dibuat. Admin akan disimpan oleh simpan_pengguna() di dalamnya.
    buat_admin_default_jika_perlu(konfigurasi)

    # Buat Produk Contoh jika tabel 'produk' masih kosong.
    # Menggunakan count() tanpa argumen untuk memeriksa jumlah dokumen, yang seharusnya aman setelah perbaikan penanganan konfigurasi.
    if len(db.table('produk').all()) == 0:
        logger.info("Adding example products.")
        produk_contoh = [
            {"nama": "Susu UHT Full Cream 1L", "harga": 18500, "stok": 150, "kategori": "Minuman", "deskripsi": "Susu UHT segar berkualitas."},
            {"nama": "Keripik Kentang Original 100g", "harga": 12000, "stok": 80, "kategori": "Makanan Ringan", "deskripsi": "Rennyah dan gurih."},
            {"nama": "Shampoo Anti Ketombe 250ml", "harga": 28000, "stok": 60, "kategori": "Perlengkapan Mandi", "deskripsi": "Membersihkan ketombe secara efektif."},
            {"nama": "Beras Pandan Wangi 5kg", "harga": 75000, "stok": 40, "kategori": "Kebutuhan Pokok", "deskripsi": "Beras premium dengan aroma pandan."},
            {"nama": "Apel Fuji per kg", "harga": 35000, "stok": 25, "kategori": "Produk Segar", "deskripsi": "Apel segar, manis dan renyah."},
            {"nama": "Lampu LED 10W", "harga": 22000, "stok": 50, "kategori": "Elektronik Rumah Tangga", "deskripsi": "Lampu hemat energi."},
        ]
        for p_data in produk_contoh:
            try:
                # Membuat objek Produk menggunakan Pydantic Model
                # ID akan dibuat otomatis oleh Field(default_factory)
                produk_baru = Produk(
                    nama=p_data['nama'],
                    harga=Money(p_data['harga'], IDR), # Menggunakan objek Money
                    stok=p_data['stok'],
                    kategori=p_data['kategori'],
                    deskripsi=p_data['deskripsi']
                )
                simpan_produk(produk_baru) # Menyimpan objek produk baru ke TinyDB (menggunakan upsert)
            except ValidationError as e:
                logger.error(f"Gagal membuat model produk contoh '{p_data['nama']}' karena validasi Pydantic: {e}")
            except Exception as e:
                logger.error(f"Error tak terduga saat menambahkan produk contoh '{p_data['nama']}': {e}")


        # Simpan kategori produk default ke dalam konfigurasi jika belum ada atau kosong.
        if not konfigurasi.get("kategori_produk"):
            konfigurasi["kategori_produk"] = KATEGORI_PRODUK_DEFAULT.copy()
            logger.info("Adding default product categories to config.")

        # Tandai bahwa proses setup awal telah selesai di dictionary konfigurasi
        konfigurasi["setup_selesai"] = True
        # Perbaikan: Simpan dictionary konfigurasi yang sudah lengkap dan final (termasuk flag setup_selesai=True) ke TinyDB
        simpan_konfigurasi(konfigurasi) # Menggunakan fungsi simpan_konfigurasi yang sudah diperbaiki
        logger.info("Database initialization complete.")

# ==============================================================================
# === BLOK 5: FUNGSI UTILITAS UMUM ===
# ==============================================================================
# Fungsi-fungsi bantu yang lebih umum dan tidak spesifik ke satu modul (Bank/Toko)
# atau interaksi database langsung.

def bersihkan_layar():
    """Membersihkan layar konsol."""
    # Menggunakan perintah sistem 'cls' untuk Windows dan 'clear' untuk sistem Unix-like (Linux/macOS)
    os.system('cls' if os.name == 'nt' else 'clear')

def format_rupiah(angka_atau_money) -> str:
    """Mengubah angka (float/int) atau objek Money menjadi format mata uang Rupiah."""
    amount = None # Inisialisasi nilai jumlah uang
    if isinstance(angka_atau_money, Money):
        amount = angka_atau_money.amount # Ambil jumlah dari objek Money
    elif isinstance(angka_atau_money, (int, float)):
        amount = angka_atau_money # Gunakan angka langsung jika tipe int atau float
    else:
        return "Rp0" # Kembalikan "Rp0" jika tipe data tidak valid

    if amount is None: return "Rp0" # Safety check jika amount entah bagaimana None

    # Format angka dengan separator ribuan dan tanpa desimal, lalu ganti koma dengan titik (format umum ID)
    # f"Rp{int(amount):,.0f}" -> mengonversi ke int, format dengan koma untuk ribuan, 0 desimal
    # .replace(",", ".") -> mengganti koma (separator bawaan Python locale) dengan titik
    return f"Rp{int(amount):,.0f}".replace(",", ".")


def generate_id_unik() -> str:
    """Menghasilkan ID unik menggunakan UUID4."""
    # Digunakan untuk menghasilkan ID di luar Pydantic Fields jika diperlukan
    return str(uuid.uuid4())

# Fungsi input_valid dan input_pilihan_menu sangat berguna untuk interaksi pengguna di konsol.
def input_valid(prompt, tipe_data=str, validasi_regex=None, pesan_error_regex=None, sembunyikan_input=False, opsional=False, default_value=None):
    """Meminta input dari pengguna dengan validasi tipe data, regex, dan opsi tambahan (sembunyi input, opsional, default)."""
    while True: # Loop sampai input valid diterima
        try:
            # Menangani input yang disembunyikan (untuk password/PIN)
            if sembunyikan_input:
                import getpass
                # Menggunakan getpass untuk input tanpa echo
                try:
                    nilai_input_str = getpass.getpass(prompt)
                except Exception as e:
                    # Fallback ke input biasa jika getpass gagal (misal di beberapa IDE)
                    logger.warning(f"Gagal menggunakan getpass: {e}. Menggunakan input biasa (tidak disembunyikan).")
                    nilai_input_str = input(prompt) # Fallback
            else:
                # Input biasa
                nilai_input_str = input(prompt)

            # Menangani input opsional
            if opsional and not nilai_input_str.strip(): # Jika input kosong atau hanya spasi
                return default_value # Kembalikan nilai default atau None jika tidak ada default

            # Mencoba konversi tipe data
            if tipe_data == int:
                nilai_konversi = int(nilai_input_str)
            elif tipe_data == float:
                nilai_konversi = float(nilai_input_str)
            else: # Untuk tipe data string atau lainnya
                nilai_konversi = nilai_input_str

            # Validasi menggunakan Regular Expression (Regex) jika disediakan
            if validasi_regex:
                # Lakukan regex match pada representasi string dari nilai yang sudah dikonversi
                # re.fullmatch memastikan SELURUH string sesuai dengan regex, bukan hanya sebagian
                if not re.fullmatch(validasi_regex, str(nilai_konversi)):
                    # Cetak pesan error jika regex tidak cocok
                    print(pesan_error_regex or "Format input tidak valid.")
                    continue # Minta input ulang dari awal loop

            return nilai_konversi # Jika semua validasi (tipe & regex) lolos, kembalikan nilai yang sudah dikonversi
        except ValueError:
            # Tangani kesalahan konversi tipe (misalnya, user memasukkan teks saat diminta angka)
            print(f"Input tidak valid. Harap masukkan tipe data {tipe_data.__name__}.")
        except Exception as e:
            # Tangani kesalahan lain yang mungkin terjadi selama input
            logger.error(f"Terjadi kesalahan tak terduga saat input_valid dengan prompt '{prompt}': {e}")
            print(f"Terjadi kesalahan saat menerima input: {e}")


def input_pilihan_menu(maks_pilihan: int, min_pilihan: int = 1, prompt_pesan: str = "Masukkan pilihan Anda: ") -> int:
    """Meminta input pilihan menu dari pengguna dan memastikan bahwa pilihan tersebut berada dalam rentang yang valid."""
    while True: # Loop sampai pilihan valid diterima
        try:
            # Meminta input dan mencoba mengonversinya menjadi integer
            pilihan_str = input(prompt_pesan)
            pilihan = int(pilihan_str)

            # Memeriksa apakah pilihan berada dalam rentang yang diizinkan (min_pilihan sampai maks_pilihan)
            if min_pilihan <= pilihan <= maks_pilihan:
                return pilihan # Jika valid, kembalikan nilai integer pilihan
            else:
                # Jika pilihan di luar rentang, cetak pesan error dan ulangi loop
                print(f"Pilihan tidak valid. Harap masukkan angka antara {min_pilihan} dan {maks_pilihan}.")
        except ValueError:
            # Menangani error jika input bukan angka
            print("Input tidak valid. Harap masukkan angka.")
        except Exception as e:
            # Menangani error tak terduga lainnya
            logger.error(f"Terjadi kesalahan tak terduga saat input_pilihan_menu: {e}")
            print(f"Terjadi kesalahan saat memproses pilihan: {e}")


def print_header(judul: str, panjang_total: int = 70):
    """Mencetak header bergaris di konsol untuk judul menu/bagian."""
    print("=" * panjang_total) # Garis atas
    print(judul.center(panjang_total)) # Judul di tengah
    print("=" * panjang_total) # Garis bawah

def print_separator_line(panjang: int = 70, char: str = "-"):
    """Mencetak garis pemisah horizontal di konsol."""
    print(char * panjang)

def input_enter_lanjut():
    """Menunggu pengguna menekan tombol Enter untuk melanjutkan eksekusi program."""
    input("\nTekan Enter untuk melanjutkan...")


# ==============================================================================
# === BLOK 6: FUNGSI AUTENTIKASI & MANAJEMEN AKUN ===
# ==============================================================================
# Fungsi-fungsi untuk registrasi, login, logout pengguna, serta manajemen PIN.
# Menggunakan Passlib untuk hashing dan Pydantic untuk model Pengguna.

# Variabel state aplikasi: menyimpan objek Pengguna yang sedang login
pengguna_login_saat_ini: Optional[Pengguna] = None
# Variabel state aplikasi: objek KeranjangBelanja yang aktif selama sesi pengguna login
keranjang_belanja_global = KeranjangBelanja()


def registrasi_pengguna_baru():
    """Mendaftarkan pengguna baru ke dalam sistem."""
    bersihkan_layar(); print_header("Registrasi Akun Baru Bear Mart & Bank")

    # Meminta dan memvalidasi username
    username = input_valid("Username baru (3-20 karakter, alfanumerik & underscore): ",
                        validasi_regex=r"^[a-zA-Z0-9_]{3,20}$", # Regex untuk format username
                        pesan_error_regex="Username tidak valid. Harus 3-20 karakter alfanumerik atau underscore.")
    # Memeriksa apakah username sudah digunakan
    if dapatkan_pengguna_by_username(username):
        print(f"Username '{username}' sudah digunakan. Harap pilih username lain."); input_enter_lanjut(); return

    # Meminta dan memvalidasi password
    password_regex = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&_])[A-Za-z\d@$!%*?&_]{8,30}$" # Regex untuk kekuatan password
    password_msg = "Password (min 8 karakter, harus mengandung huruf besar, kecil, angka, dan simbol @$!%*?&_):"
    password = input_valid(password_msg, sembunyikan_input=True, validasi_regex=password_regex,
                            pesan_error_regex="Password tidak memenuhi syarat keamanan.")
    # Meminta konfirmasi password
    if password != input_valid("Konfirmasi password: ", sembunyikan_input=True):
        print("Password tidak cocok. Registrasi dibatalkan."); input_enter_lanjut(); return

    # Meminta dan memvalidasi PIN Bank (6 digit angka)
    pin_bank = input_valid("Buat 6 digit PIN Bank: ", sembunyikan_input=True, validasi_regex=r"^\d{6}$", pesan_error_regex="PIN Bank harus terdiri dari 6 digit angka.")
    # Meminta konfirmasi PIN
    if pin_bank != input_valid("Konfirmasi PIN Bank: ", sembunyikan_input=True):
        print("PIN Bank tidak cocok. Registrasi dibatalkan."); input_enter_lanjut(); return

    # Meminta data opsional (nama lengkap dan email)
    nama_lengkap = input_valid("Nama lengkap (opsional): ", opsional=True, default_value="")
    # Meminta email; validasi format email hanya jika input tidak kosong setelah strip()
    email_input_str = input_valid("Email (opsional, format: user@domain.com): ", opsional=True, default_value="")
    email = email_input_str if email_input_str.strip() else None # Set None jika input kosong/spasi
    # Validasi format email jika email_baru bukan None
    if email and not re.fullmatch(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        print("Format email tidak valid. Email tidak disimpan."); email = None # Buang email jika format salah

    try:
        # Membuat hash password dan PIN menggunakan Passlib
        password_hash = pwd_context.hash(password)
        pin_hash = pwd_context.hash(pin_bank)

        # Membuat objek Pengguna baru menggunakan Pydantic Model
        # ID unik pengguna akan di-generate otomatis oleh Field(default_factory) di model Pengguna
        pengguna_baru = Pengguna(
            username=username,
            password_hash=password_hash,
            pin_hash=pin_hash,
            peran=PERAN_PELANGGAN, # Menetapkan peran sebagai PELANGGAN
            nama_lengkap=nama_lengkap,
            email=email,
            saldo_bank=Money(0, IDR) # Memberikan saldo awal 0 dengan objek Money
        )

        # Menyimpan objek pengguna baru ke TinyDB
        simpan_pengguna(pengguna_baru)

        logger.info(f"Pengguna baru '{username}' (ID: {pengguna_baru.id}) berhasil diregistrasi.")
        print(f"\nRegistrasi berhasil! Akun '{username}' telah dibuat. Silakan login.");
    except ValidationError as e:
        # Menangani error jika data yang dimasukkan tidak sesuai dengan skema Pydantic Model
        logger.error(f"Gagal membuat objek Pengguna karena validasi Pydantic: {e}")
        print(f"Gagal membuat akun karena data tidak valid: {e}")
    except Exception as e:
        # Menangani error tak terduga lainnya selama proses registrasi
        logger.error(f"Error tak terduga saat registrasi pengguna: {e}")
        print(f"Terjadi kesalahan saat registrasi: {e}")

    input_enter_lanjut()


def login_pengguna():
    """Memproses login pengguna dengan verifikasi kredensial dan cek status akun terkunci."""
    global pengguna_login_saat_ini # Mengizinkan fungsi ini mengubah variabel global
    bersihkan_layar(); print_header("Login Bear Mart & Bank")

    username = input_valid("Username: ")
    password = input_valid("Password: ", sembunyikan_input=True)

    # Mencari pengguna berdasarkan username di database
    pengguna = dapatkan_pengguna_by_username(username)

    if pengguna: # Jika pengguna ditemukan di database
        # Cek apakah akun terkunci
        if pengguna.akun_terkunci_hingga and pengguna.akun_terkunci_hingga > datetime.datetime.now():
            sisa_waktu = pengguna.akun_terkunci_hingga - datetime.datetime.now()
            # Format sisa waktu tanpa milidetik untuk tampilan yang lebih bersih
            sisa_waktu_str = str(sisa_waktu).split('.')[0]
            print(f"Akun terkunci. Silakan coba lagi dalam {sisa_waktu_str}.")
            logger.warning(f"Percobaan login ke akun terkunci: {username}")
            input_enter_lanjut(); return # Keluar dari fungsi login

        # Verifikasi password menggunakan Passlib
        if pengguna.verifikasi_password(password):
            # Jika password benar:
            pengguna_login_saat_ini = pengguna # Menetapkan objek pengguna yang login ke variabel global
            pengguna.gagal_login_count = 0 # Mereset hitungan gagal login
            pengguna.akun_terkunci_hingga = None # Memastikan status akun tidak terkunci
            simpan_pengguna(pengguna) # Menyimpan perubahan status kunci ke database

            logger.info(f"Pengguna '{username}' (Peran: {pengguna.peran}) berhasil login.")
            print(f"\nLogin berhasil! Selamat datang, {pengguna.nama_lengkap or pengguna.username}!") # Menyapa pengguna
        else:
            # Jika password salah:
            pengguna.gagal_login_count += 1 # Menambah hitungan gagal login
            if pengguna.gagal_login_count >= BATAS_PERCOBAAN_LOGIN:
                # Jika hitungan gagal login mencapai batas, kunci akun
                pengguna.akun_terkunci_hingga = datetime.datetime.now() + datetime.timedelta(minutes=DURASI_KUNCI_AKUN_MENIT) # Menetapkan waktu kunci
                logger.warning(f"Akun '{username}' terkunci karena gagal login {BATAS_PERCOBAAN_LOGIN} kali.")
                print(f"Password salah. Akun Anda terkunci selama {DURASI_KUNCI_AKUN_MENIT} menit.")
            else:
                # Jika belum mencapai batas, beri tahu sisa percobaan
                print(f"Password salah. Sisa percobaan: {BATAS_PERCOBAAN_LOGIN - pengguna.gagal_login_count}.")
            simpan_pengguna(pengguna) # Menyimpan perubahan hitungan gagal login/status kunci

    else:
        # Jika username tidak ditemukan di database
        print("Username tidak ditemukan.")
        logger.warning(f"Gagal login: Username '{username}' tidak ditemukan.")

    input_enter_lanjut()


def logout_pengguna():
    """Memproses logout pengguna yang sedang login."""
    global pengguna_login_saat_ini, keranjang_belanja_global # Mengizinkan fungsi ini mengubah variabel global

    if pengguna_login_saat_ini: # Jika ada pengguna yang sedang login
        logger.info(f"Pengguna '{pengguna_login_saat_ini.username}' logout.")
        print(f"Anda telah logout, {pengguna_login_saat_ini.username}. Sampai jumpa!")
        pengguna_login_saat_ini = None # Mereset variabel pengguna yang login menjadi None
        keranjang_belanja_global.kosongkan_keranjang() # Mengosongkan keranjang belanja
    else:
        print("Tidak ada pengguna yang sedang login.") # Jika tidak ada pengguna yang login saat fungsi dipanggil

    input_enter_lanjut()


def minta_pin_transaksi(pengguna_obj: Pengguna, keterangan_aksi: str = "untuk transaksi ini") -> bool:
    """Meminta input PIN Bank dan memverifikasinya terhadap PIN yang tersimpan."""
    # Mengecek apakah pengguna memiliki PIN Bank yang diatur
    if not pengguna_obj.pin_hash:
        print("PIN Bank belum diatur untuk akun ini. Silakan atur PIN di menu Pengaturan Akun."); return False # Batal jika PIN belum diatur

    for i in range(3): # Memberikan batas maksimum 3 kali percobaan memasukkan PIN
        pin_input = input_valid(f"Masukkan 6 digit PIN Bank Anda {keterangan_aksi} (percobaan {i+1}/3): ",
                                sembunyikan_input=True, # Input disembunyikan untuk keamanan
                                validasi_regex=r"^\d{6}$", # Memastikan input berupa 6 digit angka
                                pesan_error_regex="PIN Bank harus 6 digit angka.")
        # Memverifikasi PIN yang dimasukkan dengan hash PIN yang tersimpan menggunakan Passlib
        if pengguna_obj.verifikasi_pin(pin_input):
            return True # PIN benar, otorisasi berhasil
        else:
            print("PIN salah.") # PIN salah, ulangi loop

    # Jika 3 kali percobaan gagal
    print("Terlalu banyak percobaan PIN salah. Aksi dibatalkan.")
    logger.warning(f"Gagal verifikasi PIN untuk '{pengguna_obj.username}' setelah 3 kali percobaan {keterangan_aksi}.")
    return False # PIN salah setelah 3 percobaan, otorisasi gagal


# ==============================================================================
# === BLOK 7: FUNGSI MODUL BANK ===
# ==============================================================================
# Fungsi-fungsi untuk layanan perbankan (lihat saldo, deposit, withdraw, transfer, riwayat).
# Menggunakan objek Money untuk perhitungan uang, Pydantic TransaksiBank untuk pencatatan,
# dan TinyDB untuk penyimpanan data transaksi.

def lihat_saldo_bank():
    """Menampilkan saldo bank pengguna yang sedang login."""
    bersihkan_layar(); print_header("Informasi Saldo Bank")
    # Menampilkan saldo saat ini dari objek pengguna_login_saat_ini (yang merupakan objek Money)
    print(f"Saldo Anda saat ini: {format_rupiah(pengguna_login_saat_ini.saldo_bank)}") # Menggunakan format_rupiah untuk tampilan mata uang
    input_enter_lanjut()


def deposit_bank():
    """Memproses deposit saldo ke akun bank pengguna yang sedang login."""
    global pengguna_login_saat_ini # Mengizinkan fungsi ini mengubah objek pengguna yang login

    bersihkan_layar(); print_header("Deposit Saldo Bank")

    try:
        # Meminta jumlah deposit dari pengguna sebagai float
        jumlah_float = input_valid("Jumlah deposit: Rp", tipe_data=float)
        if jumlah_float <= 0:
            print("Jumlah deposit harus lebih besar dari 0."); input_enter_lanjut(); return # Batal jika jumlah non-positif

        # Mengonversi jumlah float menjadi objek Money dengan mata uang IDR
        jumlah_deposit = Money(jumlah_float, IDR)

        # === Melakukan perubahan saldo di memori (pada objek pengguna yang sedang login) ===
        saldo_awal = pengguna_login_saat_ini.saldo_bank # Menyimpan saldo awal sebelum perubahan
        pengguna_login_saat_ini.saldo_bank += jumlah_deposit # Menambahkan jumlah deposit ke saldo (operasi objek Money)

        # Membuat objek TransaksiBank untuk mencatat deposit ini
        # ID transaksi akan di-generate otomatis oleh Field(default_factory) di model TransaksiBank
        transaksi = TransaksiBank(
            user_id_sumber=pengguna_login_saat_ini.id, # ID pengguna yang melakukan deposit
            jenis_transaksi="Deposit",                 # Jenis transaksi
            jumlah=jumlah_deposit,                     # Jumlah deposit (objek Money)
            keterangan="Setoran ke akun",              # Keterangan transaksi
            saldo_akhir_sumber=pengguna_login_saat_ini.saldo_bank # Saldo akhir pengguna setelah deposit
        )

        # Memperbarui riwayat transaksi pada objek pengguna di memori dengan ID transaksi yang baru
        pengguna_login_saat_ini.riwayat_transaksi_bank_ids.append(transaksi.id)

        # === Menyimpan semua perubahan ke database (TinyDB) ===
        simpan_transaksi_bank(transaksi) # Menyimpan objek transaksi baru ke tabel transaksi
        simpan_pengguna(pengguna_login_saat_ini) # Menyimpan objek pengguna dengan saldo dan riwayat transaksi terbaru

        # Mencatat aktivitas deposit ke log
        logger.info(f"Pengguna '{pengguna_login_saat_ini.username}' deposit {format_rupiah(jumlah_deposit)}. Saldo awal: {format_rupiah(saldo_awal)}, Saldo akhir: {format_rupiah(pengguna_login_saat_ini.saldo_bank)}")

        # Memberikan umpan balik kepada pengguna
        print(f"\nDeposit {format_rupiah(jumlah_deposit)} berhasil. Saldo baru Anda: {format_rupiah(pengguna_login_saat_ini.saldo_bank)}");

    except ValueError:
        print("Input jumlah tidak valid. Harap masukkan angka.");
    except Exception as e:
        # Menangani error tak terduga selama proses deposit
        logger.error(f"Error saat deposit bank untuk pengguna '{pengguna_login_saat_ini.username}': {e}")
        print(f"Terjadi kesalahan saat deposit: {e}");

    input_enter_lanjut()


def withdraw_bank():
    """Memproses penarikan saldo dari akun bank pengguna yang sedang login."""
    global pengguna_login_saat_ini # Mengizinkan fungsi ini mengubah objek pengguna yang login

    bersihkan_layar(); print_header("Penarikan Saldo Bank")

    try:
        # Meminta jumlah penarikan sebagai float
        jumlah_float = input_valid("Jumlah penarikan: Rp", tipe_data=float)
        if jumlah_float <= 0:
            print("Jumlah harus lebih besar dari 0."); input_enter_lanjut(); return # Batal jika jumlah non-positif

        # Mengonversi jumlah float menjadi objek Money
        jumlah_tarik = Money(jumlah_float, IDR)

        # Mengecek apakah saldo pengguna mencukupi untuk penarikan (operasi objek Money)
        if jumlah_tarik > pengguna_login_saat_ini.saldo_bank:
            print("Saldo tidak cukup untuk penarikan ini."); input_enter_lanjut(); return # Batal jika saldo tidak cukup

        # Meminta verifikasi PIN transaksi sebelum melanjutkan penarikan
        if not minta_pin_transaksi(pengguna_login_saat_ini, "untuk penarikan"):
            input_enter_lanjut(); return # Batal jika verifikasi PIN gagal

        # === Melakukan perubahan saldo di memori ===
        saldo_awal = pengguna_login_saat_ini.saldo_bank # Menyimpan saldo awal
        pengguna_login_saat_ini.saldo_bank -= jumlah_tarik # Mengurangi saldo (operasi objek Money)

        # Membuat objek TransaksiBank untuk mencatat penarikan ini
        # ID transaksi akan di-generate otomatis
        transaksi = TransaksiBank(
            user_id_sumber=pengguna_login_saat_ini.id, # ID pengguna yang melakukan penarikan
            jenis_transaksi="Withdraw",                # Jenis transaksi
            jumlah=jumlah_tarik,                       # Jumlah penarikan (objek Money)
            keterangan="Penarikan dari akun",          # Keterangan transaksi
            saldo_akhir_sumber=pengguna_login_saat_ini.saldo_bank # Saldo akhir pengguna setelah penarikan
        )

        # Memperbarui riwayat transaksi pada objek pengguna di memori
        pengguna_login_saat_ini.riwayat_transaksi_bank_ids.append(transaksi.id)

        # === Menyimpan semua perubahan ke database (TinyDB) ===
        simpan_transaksi_bank(transaksi) # Menyimpan objek transaksi baru
        simpan_pengguna(pengguna_login_saat_ini) # Menyimpan objek pengguna dengan saldo dan riwayat terbaru

        # Mencatat aktivitas penarikan ke log
        logger.info(f"Pengguna '{pengguna_login_saat_ini.username}' tarik {format_rupiah(jumlah_tarik)}. Saldo awal: {format_rupiah(saldo_awal)}, Saldo akhir: {format_rupiah(pengguna_login_saat_ini.saldo_bank)}")

        # Memberikan umpan balik kepada pengguna
        print(f"\nPenarikan {format_rupiah(jumlah_tarik)} berhasil. Saldo baru Anda: {format_rupiah(pengguna_login_saat_ini.saldo_bank)}");

    except ValueError:
        print("Input jumlah tidak valid. Harap masukkan angka.");
    except Exception as e:
        # Menangani error tak terduga selama proses penarikan
        logger.error(f"Error saat withdraw bank untuk pengguna '{pengguna_login_saat_ini.username}': {e}")
        print(f"Terjadi kesalahan saat penarikan: {e}");

    input_enter_lanjut()


def transfer_dana_bank():
    """Memproses transfer dana antar pengguna bank."""
    global pengguna_login_saat_ini # Mengizinkan fungsi ini mengubah objek pengguna yang login

    bersihkan_layar(); print_header("Transfer Dana")

    try:
        # === BAGIAN 1: PERSIAPAN DAN VALIDASI INPUT ===
        # Meminta username penerima dana
        username_tujuan = input_valid("Username penerima: ")

        # Validasi 1: Pengguna tidak bisa mentransfer ke dirinya sendiri
        if username_tujuan.lower() == pengguna_login_saat_ini.username.lower():
            print("Tidak bisa mentransfer dana ke akun Anda sendiri."); input_enter_lanjut(); return # Batal jika transfer ke diri sendiri

        # Validasi 2: Mencari pengguna tujuan di database
        pengguna_tujuan = dapatkan_pengguna_by_username(username_tujuan)
        if not pengguna_tujuan:
            print(f"Pengguna dengan username '{username_tujuan}' tidak ditemukan."); input_enter_lanjut(); return # Batal jika pengguna tujuan tidak ada

        # Menampilkan informasi pengguna tujuan untuk konfirmasi
        print(f"Anda akan mentransfer dana ke: {pengguna_tujuan.nama_lengkap or pengguna_tujuan.username} ({pengguna_tujuan.username})")

        # Meminta jumlah dana yang akan ditransfer sebagai float
        jumlah_float = input_valid("Jumlah transfer: Rp", tipe_data=float)
        if jumlah_float <= 0:
            print("Jumlah transfer harus lebih besar dari 0."); input_enter_lanjut(); return # Batal jika jumlah non-positif

        # Mengonversi jumlah float menjadi objek Money
        jumlah_transfer = Money(jumlah_float, IDR)

        # Validasi 4: Mengecek apakah saldo pengirim mencukupi (operasi objek Money)
        if jumlah_transfer > pengguna_login_saat_ini.saldo_bank:
            print("Saldo Anda tidak cukup untuk melakukan transfer ini."); input_enter_lanjut(); return # Batal jika saldo tidak cukup

        # Validasi 5: Meminta verifikasi PIN transaksi dari pengirim
        if not minta_pin_transaksi(pengguna_login_saat_ini, f"untuk transfer ke {pengguna_tujuan.username}"):
            input_enter_lanjut(); return # Batal jika verifikasi PIN gagal

        # === BAGIAN 2: INTI PROSES TRANSFER (Melakukan perubahan di memori) ===
        print("\nMemproses transaksi transfer...")
        time.sleep(2) # Memberikan jeda simulasi proses transfer

        saldo_awal_sumber = pengguna_login_saat_ini.saldo_bank # Menyimpan saldo awal pengirim
        saldo_awal_tujuan = pengguna_tujuan.saldo_bank       # Menyimpan saldo awal penerima

        # Mengurangi saldo pengirim dan menambahkan saldo penerima (operasi objek Money)
        pengguna_login_saat_ini.saldo_bank -= jumlah_transfer
        pengguna_tujuan.saldo_bank += jumlah_transfer

        # Membuat objek TransaksiBank tunggal untuk mencatat transaksi transfer ini
        # ID transaksi akan di-generate otomatis
        transaksi = TransaksiBank(
            user_id_sumber=pengguna_login_saat_ini.id, # ID pengirim
            user_id_tujuan=pengguna_tujuan.id,         # ID penerima
            jenis_transaksi="Transfer",                # Jenis transaksi
            jumlah=jumlah_transfer,                    # Jumlah transfer (objek Money)
            keterangan=f"Transfer ke {pengguna_tujuan.username}", # Keterangan
            saldo_akhir_sumber=pengguna_login_saat_ini.saldo_bank, # Saldo akhir pengirim
            saldo_akhir_tujuan=pengguna_tujuan.saldo_bank        # Saldo akhir penerima
        )

        # Menambahkan ID transaksi yang sama ke riwayat transaksi kedua pengguna (pengirim dan penerima) di memori
        pengguna_login_saat_ini.riwayat_transaksi_bank_ids.append(transaksi.id)
        pengguna_tujuan.riwayat_transaksi_bank_ids.append(transaksi.id)

        # === BAGIAN 3: Menyimpan SEMUA perubahan yang dilakukan di memori ke database (TinyDB) ===
        simpan_transaksi_bank(transaksi)          # Menyimpan objek transaksi baru
        simpan_pengguna(pengguna_login_saat_ini)  # Menyimpan objek pengirim dengan saldo & riwayat terbaru
        simpan_pengguna(pengguna_tujuan)          # Menyimpan objek penerima dengan saldo & riwayat terbaru

        # === BAGIAN 4: Memberikan umpan balik kepada pengguna ===
        logger.info(f"Pengguna '{pengguna_login_saat_ini.username}' transfer {format_rupiah(jumlah_transfer)} ke '{pengguna_tujuan.username}'. Saldo sumber awal: {format_rupiah(saldo_awal_sumber)}, akhir: {format_rupiah(pengguna_login_saat_ini.saldo_bank)}. Saldo tujuan awal: {format_rupiah(saldo_awal_tujuan)}, akhir: {format_rupiah(pengguna_tujuan.saldo_bank)}")

        print(f"\nTransfer {format_rupiah(jumlah_transfer)} ke {pengguna_tujuan.username} berhasil.")
        print(f"Saldo baru Anda: {format_rupiah(pengguna_login_saat_ini.saldo_bank)}") # Menampilkan saldo pengirim setelah transfer

    except ValueError:
         print("Input jumlah tidak valid. Harap masukkan angka.");
    except Exception as e:
        # Menangani error tak terduga selama proses transfer
        logger.error(f"Error saat transfer dana dari '{pengguna_login_saat_ini.username}': {e}")
        print(f"Terjadi kesalahan saat transfer: {e}");

    input_enter_lanjut()


def lihat_riwayat_transaksi_bank():
    """Menampilkan riwayat transaksi bank untuk pengguna yang sedang login."""
    bersihkan_layar(); print_header(f"Riwayat Transaksi Bank - {pengguna_login_saat_ini.username}")

    # Mengambil daftar objek transaksi berdasarkan ID yang ada di riwayat pengguna yang login
    # Menggunakan list comprehension dan memastikan transaksi benar-benar ada di database
    list_transaksi_obj = [dapatkan_transaksi_bank_by_id(trx_id)
                          for trx_id in pengguna_login_saat_ini.riwayat_transaksi_bank_ids
                          if dapatkan_transaksi_bank_by_id(trx_id) is not None] # Filter out None results

    if not list_transaksi_obj: # Jika list riwayat transaksi kosong
        print("Belum ada riwayat transaksi."); input_enter_lanjut(); return # Keluar dari fungsi

    # Mengurutkan daftar transaksi berdasarkan timestamp, dari yang paling baru ke yang paling lama (descending)
    list_transaksi_obj.sort(key=lambda t: t.timestamp, reverse=True)

    # Menampilkan header tabel riwayat transaksi
    print_separator_line(150)
    print(f"{'Tanggal':<26} | {'Jenis':<18} | {'Keterangan':<35} | {'Jumlah':<20} | {'Saldo Akhir':<20}")
    print_separator_line(150)

    # Melakukan iterasi melalui setiap objek transaksi dan menampilkannya dalam format tabel
    for trx in list_transaksi_obj:
        jumlah_rp = ""          # Variabel untuk menampilkan jumlah (dengan tanda + atau -)
        saldo_akhir_rp = ""     # Variabel untuk menampilkan saldo akhir yang relevan
        keterangan_tampil = trx.keterangan # Keterangan transaksi
        jenis = trx.jenis_transaksi     # Jenis transaksi

        # Menentukan bagaimana menampilkan data berdasarkan jenis transaksi
        if trx.jenis_transaksi == "Transfer":
            # Jika ini adalah transaksi transfer, tentukan apakah pengguna yang login adalah sumber (pengirim) atau tujuan (penerima)
            if trx.user_id_sumber == pengguna_login_saat_ini.id:
                # Jika pengguna adalah pengirim
                jenis = "Transfer Keluar" # Tampilkan jenis sebagai "Transfer Keluar"
                jumlah_rp = f"- {format_rupiah(trx.jumlah)}" # Tampilkan jumlah dengan tanda minus (pengeluaran)
                saldo_akhir_rp = format_rupiah(trx.saldo_akhir_sumber) # Tampilkan saldo akhir pengirim
                # Mendapatkan username penerima untuk keterangan
                penerima = dapatkan_pengguna_by_id(trx.user_id_tujuan)
                keterangan_tampil = f"Ke: {penerima.username if penerima else 'N/A'}" # Menampilkan username penerima

            else: # Jika pengguna adalah tujuan (penerima)
                jenis = "Transfer Masuk" # Tampilkan jenis sebagai "Transfer Masuk"
                jumlah_rp = f"+ {format_rupiah(trx.jumlah)}" # Tampilkan jumlah dengan tanda plus (pemasukan)
                saldo_akhir_rp = format_rupiah(trx.saldo_akhir_tujuan) # Tampilkan saldo akhir penerima
                # Mendapatkan username pengirim untuk keterangan
                pengirim = dapatkan_pengguna_by_id(trx.user_id_sumber)
                keterangan_tampil = f"Dari: {pengirim.username if pengirim else 'N/A'}" # Menampilkan username pengirim

        else:
            # Jika jenis transaksi bukan Transfer (misalnya Deposit, Withdraw, Pembayaran Toko)
            if jenis == "Deposit":
                jumlah_rp = f"+ {format_rupiah(trx.jumlah)}" # Deposit adalah pemasukan
            else: # Withdraw, Pembayaran Toko adalah pengeluaran
                jumlah_rp = f"- {format_rupiah(trx.jumlah)}"

            # Untuk jenis transaksi ini, saldo akhir yang relevan selalu saldo sumber
            saldo_akhir_rp = format_rupiah(trx.saldo_akhir_sumber)
            # Keterangan bisa tetap menggunakan keterangan dari objek transaksi

        # Mencetak satu baris transaksi ke konsol dengan format yang sudah ditentukan
        print(f"{trx.timestamp.strftime('%Y-%m-%d %H:%M:%S'):<26} | {jenis:<18} | {keterangan_tampil[:35]:<35} | {jumlah_rp:<20} | {saldo_akhir_rp:<20}") # Format timestamp untuk tampilan

    # Menampilkan garis penutup tabel
    print_separator_line(150)
    input_enter_lanjut() # Menunggu pengguna menekan Enter sebelum kembali


# ==============================================================================
# === BLOK 8: FUNGSI MODUL TOKO ===
# ==============================================================================
# Fungsi-fungsi untuk fitur toko (lihat produk, kelola keranjang, checkout, riwayat pembelian).
# Menggunakan Pydantic Models untuk Produk, ItemKeranjang, PesananToko,
# dan TinyDB untuk penyimpanan data produk dan pesanan.

def tampilkan_daftar_produk_toko(filter_kategori: Optional[str] = None, keyword_pencarian: Optional[str] = None, tampilkan_deskripsi: bool = False) -> List[Produk]:
    """Mengambil data produk dari database dan menampilkannya di konsol,
    dengan opsi filter berdasarkan kategori atau pencarian berdasarkan nama."""

    # Mengambil semua objek Produk dari database
    semua_produk_obj = dapatkan_semua_produk()
    produk_tampil = [] # List untuk menyimpan produk yang akan ditampilkan setelah filtering

    # Jika tidak ada produk di database
    if not semua_produk_obj:
        # Bersihkan layar dan header mungkin dipanggil di luar fungsi ini
        print("Belum ada produk di toko."); return produk_tampil # Mengembalikan list kosong

    # Melakukan filtering dan pencarian produk
    for produk in semua_produk_obj:
        lolos = True # Asumsikan produk lolos filter awalnya

        # Filter berdasarkan kategori jika filter_kategori disediakan
        if filter_kategori and produk.kategori.lower() != filter_kategori.lower():
            lolos = False # Produk tidak lolos filter kategori

        # Pencarian berdasarkan nama produk jika keyword_pencarian disediakan
        if keyword_pencarian and keyword_pencarian.lower() not in produk.nama.lower():
            lolos = False # Produk tidak lolos filter pencarian

        # Jika produk lolos semua filter (lolos tetap True)
        if lolos:
            produk_tampil.append(produk) # Tambahkan produk ke list yang akan ditampilkan

    # Jika tidak ada produk yang lolos filter/pencarian
    if not produk_tampil:
        print("Tidak ada produk sesuai filter/pencarian."); return produk_tampil # Mengembalikan list kosong

    # Menentukan lebar kolom deskripsi jika ditampilkan
    kolom_deskripsi_width = 30 # Lebar standar kolom deskripsi
    lebar_total = 110 + (kolom_deskripsi_width + 3 if tampilkan_deskripsi else 0) # Hitung lebar total tabel (+3 untuk " | ")

    # Menampilkan header tabel produk
    print_separator_line(lebar_total)
    header_str = f"{'No.':<5} | {'ID Produk':<37} | {'Nama Produk':<30} | {'Harga':<15} | {'Stok':<7} | {'Kategori':<20}"
    if tampilkan_deskripsi:
        header_str += f" | {'Deskripsi':<{kolom_deskripsi_width}}" # Tambahkan kolom deskripsi jika diminta
    print(header_str)
    print_separator_line(lebar_total)

    # Menampilkan setiap produk yang lolos filter dalam format tabel
    for i, produk in enumerate(produk_tampil):
        row_str = f"{i+1:<5} | {produk.id:<37} | {produk.nama[:30]:<30} | {format_rupiah(produk.harga):<15} | {str(produk.stok):<7} | {produk.kategori[:20]:<20}"
        if tampilkan_deskripsi:
             # Potong dan padding deskripsi agar sesuai lebar kolom
            row_str += f" | {produk.deskripsi[:kolom_deskripsi_width]:<{kolom_deskripsi_width}}"
        print(row_str)

    # Menampilkan garis penutup tabel
    print_separator_line(lebar_total)
    return produk_tampil # Mengembalikan list objek Produk yang ditampilkan


def pilih_produk_dari_daftar(list_produk_ditampilkan: List[Produk]) -> Optional[Produk]:
    """Meminta pengguna memilih produk dari daftar yang sebelumnya telah ditampilkan
    dan mengembalikan objek Produk yang dipilih."""

    # Jika daftar produk kosong, tidak ada yang bisa dipilih
    if not list_produk_ditampilkan:
        print("Daftar produk untuk dipilih kosong.") # Tambahkan pesan ini untuk kejelasan
        return None # Mengembalikan None jika list kosong

    while True: # Loop sampai pilihan valid diterima atau dibatalkan
        try:
            # Meminta nomor produk yang dipilih dari pengguna
            pilihan_no = input_valid("\nNo. produk yang dipilih (0 untuk batal): ", tipe_data=int)

            # Jika pengguna memilih 0, batalkan pemilihan
            if pilihan_no == 0:
                return None # Mengembalikan None untuk menandakan pembatalan

            # Memeriksa apakah nomor pilihan valid (berada dalam rentang nomor produk yang ditampilkan)
            if 1 <= pilihan_no <= len(list_produk_ditampilkan):
                # Mengembalikan objek Produk yang sesuai dengan nomor yang dipilih
                return list_produk_ditampilkan[pilihan_no - 1] # pihan_no 1-based, list index 0-based
            else:
                # Jika nomor pilihan tidak valid, cetak pesan error dan ulangi loop
                print(f"Nomor produk tidak valid. Harap pilih nomor antara 1 dan {len(list_produk_ditampilkan)}, atau 0 untuk batal.")
        except ValueError:
             # Menangani error jika input bukan angka
             print("Input tidak valid. Harap masukkan nomor produk.")
        except Exception as e:
             # Menangani error tak terduga lainnya
             logger.error(f"Terjadi kesalahan tak terduga saat memilih produk dari daftar: {e}")
             print(f"Terjadi kesalahan saat memproses pilihan produk: {e}")


def tambah_produk_ke_keranjang_toko():
    """Memungkinkan pengguna mencari/memfilter produk dan menambahkannya ke keranjang belanja."""
    global keranjang_belanja_global # Mengizinkan fungsi ini mengakses dan mengubah keranjang global

    while True: # Loop utama untuk menambah lebih dari satu produk
        bersihkan_layar(); print_header("Tambah Produk ke Keranjang")
        print("Pilih cara mencari produk yang ingin dibeli:")
        print("1. Tampilkan Semua Produk")
        print("2. Cari Produk berdasarkan Nama")
        print("3. Filter Produk berdasarkan Kategori")
        print("4. Kembali ke Menu Toko")
        print_separator_line()

        aksi = input_pilihan_menu(4) # Meminta pilihan aksi dari pengguna

        produk_ditampilkan: List[Produk] = [] # List untuk menyimpan produk yang ditampilkan berdasarkan aksi
        if aksi == 1:
            bersihkan_layar(); print_header("Semua Produk");
            # Menampilkan semua produk dengan deskripsi lengkap
            produk_ditampilkan = tampilkan_daftar_produk_toko(tampilkan_deskripsi=True)
        elif aksi == 2:
            bersihkan_layar(); print_header("Cari Produk");
            keyword = input_valid("Masukkan kata kunci nama produk yang dicari: ")
            # Menampilkan produk yang sesuai dengan keyword pencarian
            produk_ditampilkan = tampilkan_daftar_produk_toko(keyword_pencarian=keyword, tampilkan_deskripsi=True)
        elif aksi == 3:
            bersihkan_layar(); print_header("Filter Produk");
            # Mendapatkan daftar kategori produk yang tersedia dari konfigurasi sistem
            konfigurasi = dapatkan_konfigurasi()
            kategori_tersedia = konfigurasi.get("kategori_produk", [])

            if not kategori_tersedia:
                print("Belum ada kategori produk yang tersedia."); input_enter_lanjut(); continue # Kembali ke awal loop aksi jika tidak ada kategori

            print("\nKategori Tersedia:");
            [print(f"{i+1}. {kat}") for i, kat in enumerate(kategori_tersedia)]
            print_separator_line()

            try:
                 # Meminta pengguna memilih nomor kategori
                 pilihan_kat_idx = input_pilihan_menu(len(kategori_tersedia), prompt_pesan="Pilih nomor kategori untuk filter: ") - 1 # Input 1-based, index 0-based
                 filter_kat = kategori_tersedia[pilihan_kat_idx] # Mendapatkan nama kategori yang dipilih
                 bersihkan_layar(); print_header(f"Produk Kategori: {filter_kat}");
                 # Menampilkan produk yang sesuai dengan kategori yang dipilih
                 produk_ditampilkan = tampilkan_daftar_produk_toko(filter_kategori=filter_kat, tampilkan_deskripsi=True)
            except IndexError: # Menangani error jika nomor kategori tidak valid (seharusnya sudah ditangani input_pilihan_menu)
                 print("Nomor kategori tidak valid."); input_enter_lanjut(); continue
            except Exception as e:
                 logger.error(f"Error saat memfilter produk berdasarkan kategori: {e}")
                 print(f"Terjadi kesalahan saat memfilter produk: {e}"); input_enter_lanjut(); continue

        elif aksi == 4:
            return # Kembali ke menu toko utama

        # Jika tidak ada produk yang ditampilkan setelah aksi pencarian/filter
        if not produk_ditampilkan:
             # Pesan "Tidak ada produk" sudah ditangani di dalam tampilkan_daftar_produk_toko
             input_enter_lanjut(); continue # Kembali ke awal loop aksi

        # Memilih produk dari daftar produk yang baru saja ditampilkan
        produk_dipilih = pilih_produk_dari_daftar(produk_ditampilkan)
        if not produk_dipilih:
            # Jika pengguna batal memilih produk, tanya apakah mau cari produk lain atau kembali
            if input_valid("Cari produk lain? (y/n): ", opsional=True, default_value='n').lower() == 'y':
                continue # Kembali ke awal loop utama (memilih aksi cari/filter lagi)
            else:
                break # Keluar dari loop utama penambahan produk

        # === Proses Penambahan Item ke Keranjang setelah Produk dipilih ===
        print(f"\nAnda memilih: {produk_dipilih.nama} | Harga: {format_rupiah(produk_dipilih.harga)} | Stok: {produk_dipilih.stok}")
        if produk_dipilih.stok == 0:
            print("Maaf, stok produk ini sedang habis. Tidak bisa ditambahkan ke keranjang."); input_enter_lanjut(); continue # Lanjut ke loop utama untuk pilih produk lain

        try:
            # Meminta jumlah unit produk yang akan dibeli
            jumlah_beli = input_valid(f"Masukkan jumlah '{produk_dipilih.nama}' yang ingin dibeli: ", tipe_data=int)

            if jumlah_beli <= 0:
                print("Jumlah harus lebih dari 0.")
            elif jumlah_beli > produk_dipilih.stok:
                print(f"Stok tidak cukup (tersedia: {produk_dipilih.stok} unit).")
            else:
                # Menambahkan item ke keranjang belanja global
                keranjang_belanja_global.tambah_item(produk_dipilih, jumlah_beli)
                logger.info(f"Pengguna '{pengguna_login_saat_ini.username}' menambah {jumlah_beli}x '{produk_dipilih.nama}' (ID: {produk_dipilih.id}) ke keranjang.")
                print(f"{jumlah_beli} x '{produk_dipilih.nama}' berhasil ditambahkan ke keranjang.")
        except ValueError:
            print("Input jumlah tidak valid. Harap masukkan angka.")
        except Exception as e:
            logger.error(f"Error saat menambah produk ke keranjang: {e}")
            print(f"Terjadi kesalahan saat menambah produk ke keranjang: {e}")

        input_enter_lanjut()
        # Setelah berhasil menambah item (atau jika ada validasi jumlah gagal), tanya apakah mau menambah produk lain
        if input_valid("Tambah produk lain? (y/n): ", opsional=True, default_value='n').lower() != 'y':
            break # Keluar dari loop utama penambahan produk


def lihat_keranjang_toko():
    """Menampilkan isi keranjang belanja pengguna yang sedang login."""
    bersihkan_layar(); print_header("Isi Keranjang Belanja Anda")

    # Memeriksa apakah keranjang belanja kosong
    if not keranjang_belanja_global.items:
        print("Keranjang belanja Anda kosong."); input_enter_lanjut(); return # Keluar jika keranjang kosong

    # Menampilkan item-item di keranjang dalam format tabel
    print_separator_line(110)
    print(f"{'No.':<5} | {'ID Produk':<37} | {'Nama Produk':<30} | {'Jml':<5} | {'Harga Satuan':<15} | {'Subtotal':<15}")
    print_separator_line(110)

    items_list = list(keranjang_belanja_global.items.values()) # Mengambil item keranjang sebagai list objek ItemKeranjang
    for i, item in enumerate(items_list):
        # Menampilkan detail setiap item
        print(f"{i+1:<5} | {item.produk_id:<37} | {item.nama_produk[:30]:<30} | {str(item.jumlah):<5} | {format_rupiah(item.harga_satuan):<15} | {format_rupiah(item.subtotal):<15}") # Menggunakan format_rupiah

    # Menampilkan total belanja
    print_separator_line(110)
    print(f"{'Total Belanja:':<95} {format_rupiah(keranjang_belanja_global.total_belanja):<15}") # Menggunakan format_rupiah untuk total
    print_separator_line(110)

    input_enter_lanjut() # Menunggu pengguna menekan Enter


def ubah_item_keranjang_toko():
    """Memungkinkan pengguna mengubah jumlah unit atau menghapus item di keranjang belanja."""
    global keranjang_belanja_global # Mengizinkan fungsi ini mengubah keranjang global

    bersihkan_layar(); print_header("Ubah Item Keranjang")

    # Memeriksa apakah keranjang belanja kosong
    if not keranjang_belanja_global.items:
        print("Keranjang belanja Anda kosong. Tidak ada item untuk diubah."); input_enter_lanjut(); return # Keluar jika keranjang kosong

    # Menampilkan item-item di keranjang dengan nomor untuk dipilih
    print(f"{'No.':<5} | {'Nama Produk':<30} | {'Jml':<5}"); print_separator_line(45)
    items_list = list(keranjang_belanja_global.items.values()) # Mengambil item keranjang sebagai list objek ItemKeranjang
    for i, item in enumerate(items_list):
        print(f"{i+1:<5} | {item.nama_produk[:30]:<30} | {str(item.jumlah):<5}")
    print_separator_line(45)

    # Meminta nomor item yang akan diubah (0 untuk batal)
    pilihan_no = input_valid("No. produk di keranjang yang akan diubah (0 untuk batal): ", tipe_data=int)
    if pilihan_no == 0:
        print("Perubahan keranjang dibatalkan."); return # Batal jika pilihan 0

    # Memeriksa apakah nomor pilihan valid
    if 1 <= pilihan_no <= len(items_list):
        item_dipilih = items_list[pilihan_no - 1] # Mendapatkan objek ItemKeranjang yang dipilih

        print(f"\nItem yang dipilih: {item_dipilih.nama_produk} (Jumlah saat ini: {item_dipilih.jumlah})")

        try:
            # Meminta jumlah unit yang baru (0 untuk menghapus item)
            jumlah_baru = input_valid("Masukkan jumlah baru (0 untuk menghapus item): ", tipe_data=int)

            # Mendapatkan objek produk asli dari database untuk memeriksa stok yang tersedia
            produk_asli = dapatkan_produk_by_id(item_dipilih.produk_id)
            if not produk_asli:
                # Jika produk asli tidak ditemukan di DB (misalnya sudah dihapus oleh admin)
                logger.error(f"Produk ID {item_dipilih.produk_id} tidak ditemukan di DB saat mencoba mengubah item di keranjang.")
                print("Error: Produk asli tidak ditemukan di database. Tidak bisa mengubah item ini."); input_enter_lanjut(); return

            # Validasi jumlah baru terhadap stok yang tersedia (jika jumlah baru > 0)
            if jumlah_baru < 0:
                 print("Jumlah tidak boleh negatif.")
            elif jumlah_baru > 0 and jumlah_baru > produk_asli.stok:
                print(f"Stok produk '{produk_asli.nama}' tidak cukup (tersedia: {produk_asli.stok}).")
            else:
                # Memanggil metode ubah_jumlah_item di objek keranjang belanja global
                if keranjang_belanja_global.ubah_jumlah_item(item_dipilih.produk_id, jumlah_baru):
                     # Memberikan umpan balik sesuai aksi yang dilakukan (ubah atau hapus)
                     if jumlah_baru == 0:
                         logger.info(f"Pengguna '{pengguna_login_saat_ini.username}' menghapus item '{item_dipilih.nama_produk}' (ID: {item_dipilih.produk_id}) dari keranjang.")
                         print(f"Item '{item_dipilih.nama_produk}' telah dihapus dari keranjang.")
                     else:
                         logger.info(f"Pengguna '{pengguna_login_saat_ini.username}' mengubah jumlah item '{item_dipilih.nama_produk}' (ID: {item_dipilih.produk_id}) di keranjang menjadi {jumlah_baru}.")
                         print(f"Jumlah item '{item_dipilih.nama_produk}' telah diubah menjadi {jumlah_baru}.")
                else:
                    # Ini seharusnya tidak tercapai jika produk_id ada di keranjang dan jumlah >= 0
                    print("Gagal mengubah item di keranjang.")
        except ValueError:
            print("Input jumlah tidak valid. Harap masukkan angka.")
        except Exception as e:
            # Menangani error tak terduga selama proses mengubah item keranjang
            logger.error(f"Error saat mengubah item keranjang: {e}")
            print(f"Terjadi kesalahan saat mengubah item keranjang: {e}")
    else:
        print("Nomor item tidak valid. Harap masukkan nomor dari daftar.")

    input_enter_lanjut() # Menunggu pengguna menekan Enter


def proses_pembayaran_toko():
    """Memproses pembayaran pesanan yang ada di keranjang belanja menggunakan saldo bank pengguna."""
    global keranjang_belanja_global, pengguna_login_saat_ini # Mengizinkan akses dan perubahan pada variabel global

    bersihkan_layar(); print_header("Proses Pembayaran Bear Mart")

    # Memeriksa apakah keranjang belanja kosong
    if not keranjang_belanja_global.items:
        print("Keranjang belanja Anda kosong. Tidak ada yang bisa dibayar."); input_enter_lanjut(); return # Keluar jika keranjang kosong

    # Menampilkan rincian belanja dan total yang harus dibayar (menggunakan objek Money)
    total_bayar = keranjang_belanja_global.total_belanja # Mengambil total belanja dari keranjang (objek Money)
    print("--- Rincian Belanja ---")
    for item in keranjang_belanja_global.items.values(): # Iterasi melalui item di keranjang
        print(f"- {item.nama_produk} x{item.jumlah} = {format_rupiah(item.subtotal)}") # Menampilkan detail item dengan subtotal
    print_separator_line()
    print(f"Total yang harus dibayar: {format_rupiah(total_bayar)}") # Menampilkan total bayar
    print_separator_line()
    # Menampilkan informasi saldo pengguna saat ini
    print(f"Akun Bank Anda: {pengguna_login_saat_ini.username}, Saldo saat ini: {format_rupiah(pengguna_login_saat_ini.saldo_bank)}")

    # Validasi saldo: Mengecek apakah saldo pengguna mencukupi untuk total pembayaran (operasi objek Money)
    if pengguna_login_saat_ini.saldo_bank < total_bayar:
        print("\nSaldo bank Anda tidak cukup untuk pembayaran ini."); input_enter_lanjut(); return # Batal jika saldo tidak cukup

    # Meminta konfirmasi dari pengguna untuk melanjutkan pembayaran
    if input_valid("\nLanjutkan proses pembayaran? (y/n): ", opsional=True, default_value='n').lower() == 'y':
        # Meminta verifikasi PIN transaksi sebelum melakukan pembayaran
        if not minta_pin_transaksi(pengguna_login_saat_ini, "untuk pembayaran ini"):
            print("Pembayaran dibatalkan karena verifikasi PIN gagal."); input_enter_lanjut(); return # Batal jika verifikasi PIN gagal

        # === VALIDASI STOK AKHIR (PENTING) ===
        # Melakukan pengecekan stok terakhir kali sebelum memproses transaksi
        # untuk menghindari pembelian melebihi stok yang tersisa.
        produk_yang_diubah: List[Produk] = [] # List untuk menyimpan objek Produk yang stoknya akan diubah
        stok_cukup = True # Flag untuk menandai apakah semua stok item cukup
        for item_keranjang in keranjang_belanja_global.items.values(): # Iterasi melalui setiap item di keranjang
            produk_db = dapatkan_produk_by_id(item_keranjang.produk_id) # Mendapatkan objek Produk dari database

            # Jika produk tidak ditemukan di DB atau stok yang tersedia kurang dari jumlah di keranjang
            if not produk_db or produk_db.stok < item_keranjang.jumlah:
                # Mencatat peringatan ke log
                logger.warning(f"Checkout dibatalkan untuk '{pengguna_login_saat_ini.username}': Stok produk '{item_keranjang.nama_produk}' (ID: {item_keranjang.produk_id}) tidak cukup ({produk_db.stok if produk_db else 0} tersedia < {item_keranjang.jumlah} diminta).")
                print(f"Error: Stok produk '{item_keranjang.nama_produk}' tidak cukup saat checkout. Pembayaran dibatalkan.");
                stok_cukup = False # Menetapkan flag stok_cukup menjadi False
                break # Menghentikan pengecekan stok karena sudah ada satu item yang bermasalah

            # Jika stok cukup, tambahkan objek Produk dari DB ke list produk_yang_diubah
            # Kita akan memodifikasi objek ini di memori, lalu menyimpannya nanti
            produk_yang_diubah.append(produk_db)

        # Jika stok tidak mencukupi untuk setidaknya satu item, batalkan pembayaran
        if not stok_cukup:
             input_enter_lanjut(); return # Keluar dari fungsi

        # === INTI PROSES PEMBAYARAN (Melakukan perubahan di memori terlebih dahulu) ===
        print("\nMemproses pembayaran...")
        time.sleep(2) # Menambahkan jeda simulasi proses

        saldo_awal_pengguna = pengguna_login_saat_ini.saldo_bank # Menyimpan saldo awal pengguna

        # Mengurangi stok produk di memori
        for item_keranjang in keranjang_belanja_global.items.values(): # Iterasi melalui item di keranjang
             # Mencari objek Produk yang sesuai di list produk_yang_diubah (yang diambil dari DB)
            for produk_obj in produk_yang_diubah:
                 if produk_obj.id == item_keranjang.produk_id:
                     produk_obj.stok -= item_keranjang.jumlah # Mengurangi stok pada objek di memori
                     produk_obj.diperbarui_pada = datetime.datetime.now() # Memperbarui timestamp diperbarui
                     break # Keluar dari inner loop dan lanjut ke item keranjang berikutnya

        # Mengurangi saldo pengguna yang login (operasi objek Money)
        pengguna_login_saat_ini.saldo_bank -= total_bayar

        # Membuat objek TransaksiBank untuk mencatat pembayaran ini
        # ID transaksi akan di-generate otomatis
        transaksi_pembayaran = TransaksiBank(
            user_id_sumber=pengguna_login_saat_ini.id, # ID pengguna yang membayar
            jenis_transaksi="Pembayaran Toko",         # Jenis transaksi
            jumlah=total_bayar,                       # Jumlah pembayaran (total belanja sebagai objek Money)
            keterangan="Pembelian di Bear Mart",      # Keterangan transaksi
            saldo_akhir_sumber=pengguna_login_saat_ini.saldo_bank # Saldo akhir pengguna setelah pembayaran
        )

        # Membuat objek PesananToko untuk mencatat pesanan ini
        # ID pesanan akan di-generate otomatis
        items_pesanan_dict = keranjang_belanja_global.dapatkan_semua_item_dict() # Mengambil item keranjang dalam format list dictionary
        pesanan_baru = PesananToko(
            user_id=pengguna_login_saat_ini.id, # ID pengguna yang membuat pesanan
            items_pesanan=items_pesanan_dict,   # Item yang dibeli (list dictionary)
            total_harga=total_bayar             # Total harga pesanan (objek Money)
        )

        # Menambahkan ID transaksi dan pesanan ke riwayat pengguna di memori
        pengguna_login_saat_ini.riwayat_transaksi_bank_ids.append(transaksi_pembayaran.id)
        pengguna_login_saat_ini.riwayat_pesanan_toko_ids.append(pesanan_baru.id)

        # === Menyimpan SEMUA perubahan yang dilakukan di memori ke database (TinyDB) secara serentak ===
        # Simpan transaksi pembayaran baru
        simpan_transaksi_bank(transaksi_pembayaran)
        # Simpan pesanan toko baru
        simpan_pesanan_toko(pesanan_baru)
        # Simpan objek pengguna yang login (saldo & riwayat terbaru)
        simpan_pengguna(pengguna_login_saat_ini)

        # Simpan semua objek Produk yang stoknya sudah diubah
        for prod in produk_yang_diubah:
             simpan_produk(prod) # simpan_produk menggunakan upsert pada ID produk


        # Mengosongkan keranjang belanja setelah pembayaran berhasil dan data tersimpan
        keranjang_belanja_global.kosongkan_keranjang()

        # Mencatat aktivitas pembayaran yang berhasil ke log
        logger.info(f"Pengguna '{pengguna_login_saat_ini.username}' bayar {format_rupiah(total_bayar)} di Bear Mart. Saldo awal: {format_rupiah(saldo_awal_pengguna)}, Saldo akhir: {format_rupiah(pengguna_login_saat_ini.saldo_bank)}. Pesanan ID: {pesanan_baru.id}")

        # Menampilkan struk pembayaran kepada pengguna
        print("\n--- Struk Pembayaran Bear Mart ---")
        print(f"ID Pesanan: {pesanan_baru.id}")
        print(f"Tanggal: {pesanan_baru.timestamp.strftime('%Y-%m-%d %H:%M:%S')}") # Format timestamp pesanan
        print(f"Akun: {pengguna_login_saat_ini.username}")
        print(f"Total: {format_rupiah(total_bayar)}")
        print("\nPembayaran berhasil! Terima kasih telah berbelanja.")
        print(f"Sisa saldo: {format_rupiah(pengguna_login_saat_ini.saldo_bank)}") # Menampilkan sisa saldo

    else:
        # Jika pengguna membatalkan pembayaran
        print("Pembayaran dibatalkan oleh pengguna.")

    input_enter_lanjut() # Menunggu pengguna menekan Enter


def lihat_riwayat_pembelian_toko():
    """Menampilkan riwayat pembelian toko untuk pengguna yang sedang login."""
    bersihkan_layar(); print_header(f"Riwayat Pembelian Toko - {pengguna_login_saat_ini.username}")

    # Mengambil daftar ID pesanan dari riwayat pengguna yang login
    ids_pesanan_user = pengguna_login_saat_ini.riwayat_pesanan_toko_ids
    # Mengambil objek PesananToko dari database berdasarkan ID
    list_pesanan_obj = [dapatkan_pesanan_toko_by_id(pid)
                        for pid in ids_pesanan_user
                        if dapatkan_pesanan_toko_by_id(pid) is not None] # Memastikan pesanan benar-benar ada di database

    if not list_pesanan_obj: # Jika tidak ada riwayat pembelian
        print("Belum ada riwayat pembelian di toko."); input_enter_lanjut(); return # Keluar dari fungsi

    # Mengurutkan daftar pesanan berdasarkan timestamp, dari yang paling baru ke yang paling lama
    list_pesanan_obj.sort(key=lambda p: p.timestamp, reverse=True)

    # Menampilkan setiap pesanan dalam riwayat
    for i, pesanan in enumerate(list_pesanan_obj):
        print_separator_line() # Garis pemisah antar pesanan
        print(f"Pesanan Ke-{i+1} (ID: {pesanan.id})")
        print(f"Tanggal: {pesanan.timestamp.strftime('%Y-%m-%d %H:%M:%S')}") # Format timestamp pesanan
        print(f"Total: {format_rupiah(pesanan.total_harga)}") # Menampilkan total harga pesanan dengan format Rupiah
        print("Item:")
        # Menampilkan item-item di dalam pesanan
        for item_dict in pesanan.items_pesanan: # Iterasi melalui list dictionary item yang disimpan di pesanan
             try:
                 # Mengonversi dictionary item kembali menjadi objek ItemKeranjang untuk akses properti (nama, jumlah, harga)
                 item_obj = ItemKeranjang(**item_dict)
                 # Menampilkan detail setiap item dalam pesanan
                 print(f"  - {item_obj.nama_produk} x{item_obj.jumlah} @ {format_rupiah(item_obj.harga_satuan)} = {format_rupiah(item_obj.subtotal)}") # Menggunakan format_rupiah
             except ValidationError as e:
                 # Menangani error jika data item dalam riwayat pesanan tidak valid (misalnya format JSON corrupt)
                 logger.error(f"Error validasi Pydantic saat memproses item pesanan {pesanan.id}: {item_dict} - {e}")
                 print(f"  - Error menampilkan item (format data tidak valid): {item_dict.get('nama_produk', 'N/A')}")
             except Exception as e:
                 # Menangani error tak terduga lainnya saat memproses item pesanan
                 logger.error(f"Error tak terduga saat memproses item pesanan {pesanan.id}: {item_dict} - {e}")
                 print(f"  - Error tak terduga saat menampilkan item: {item_dict.get('nama_produk', 'N/A')}")

    print_separator_line(); input_enter_lanjut() # Garis penutup dan menunggu input


# ==============================================================================
# === BLOK 9: FUNGSI PANEL ADMIN ===
# ==============================================================================
# Fungsi-fungsi untuk fitur administrasi sistem (manajemen produk, laporan, kelola kategori, lihat data).
# Menggunakan TinyDB dan Pydantic Models untuk interaksi data.

def admin_tambah_produk():
    """Admin: Menambahkan produk baru ke dalam daftar produk toko."""
    bersihkan_layar(); print_header("Admin - Tambah Produk Baru")

    nama = input_valid("Masukkan Nama Produk Baru: ") # Meminta nama produk

    # Meminta dan memvalidasi harga produk (float)
    try:
        harga_float = input_valid("Masukkan Harga Produk Baru: Rp", tipe_data=float)
        if harga_float < 0: raise ValueError("Harga tidak boleh negatif.")
        harga = Money(harga_float, IDR) # Mengonversi float ke objek Money
    except ValueError as e:
        print(f"Input harga tidak valid: {e}. Penambahan produk dibatalkan."); input_enter_lanjut(); return

    # Meminta dan memvalidasi stok awal produk (integer)
    try:
        stok = input_valid("Masukkan Stok Awal Produk: ", tipe_data=int)
        if stok < 0: raise ValueError("Stok tidak boleh negatif.")
    except ValueError as e:
        print(f"Input stok tidak valid: {e}. Penambahan produk dibatalkan."); input_enter_lanjut(); return

    # Meminta deskripsi produk (opsional)
    deskripsi = input_valid("Masukkan Deskripsi Produk (opsional): ", opsional=True, default_value="")

    # Memilih atau menambahkan kategori produk
    konfigurasi = dapatkan_konfigurasi() # Mengambil konfigurasi sistem
    kategori_tersedia = konfigurasi.get("kategori_produk", []) # Mendapatkan list kategori yang ada

    print("\nPilih Kategori Produk:");
    # Menampilkan kategori yang sudah ada dengan nomor
    if not kategori_tersedia: print("(Belum ada kategori. Pilihan akan menggunakan 'Lainnya' atau kategori baru.)")
    else: [print(f"{i+1}. {kat}") for i, kat in enumerate(kategori_tersedia)]
    print(f"{len(kategori_tersedia)+1}. Tambah Kategori Baru") # Opsi untuk menambah kategori baru

    # Meminta pilihan nomor kategori
    # Jika tidak ada kategori tersedia, min_pilihan adalah 1 (untuk Tambah Baru)
    pilihan_kat = input_pilihan_menu(len(kategori_tersedia) + 1, prompt_pesan="Nomor Kategori: ")

    kategori = "" # Variabel untuk menyimpan nama kategori yang dipilih/dibuat

    # Memproses pilihan kategori
    if pilihan_kat == len(kategori_tersedia) + 1: # Jika memilih opsi "Tambah Kategori Baru"
        kategori_baru = input_valid("Masukkan Nama Kategori Baru: ").strip() # Meminta nama kategori baru
        if kategori_baru and kategori_baru not in kategori_tersedia:
            # Jika nama kategori baru valid dan belum ada, tambahkan ke konfigurasi
            konfigurasi["kategori_produk"].append(kategori_baru) # Tambahkan ke list di dictionary konfigurasi (di memori)
            simpan_konfigurasi(konfigurasi) # Menyimpan perubahan konfigurasi ke TinyDB
            kategori = kategori_baru # Menggunakan kategori baru
            logger.info(f"ADMIN: Menambah kategori baru '{kategori_baru}'. Oleh {pengguna_login_saat_ini.username}.")
            print(f"Kategori '{kategori_baru}' berhasil ditambah dan dipilih.")
        elif kategori_baru in kategori_tersedia:
            # Jika nama kategori baru sudah ada, gunakan yang sudah ada
            kategori = kategori_baru
            print(f"Kategori '{kategori_baru}' sudah ada, dipilih.")
        else:
            # Jika nama kategori baru tidak valid atau kosong, fallback
            # Mencoba menggunakan "Lainnya" jika ada di default, atau kategori pertama jika ada, atau "Default"
            kategori = "Lainnya" if "Lainnya" in KATEGORI_PRODUK_DEFAULT else (kategori_tersedia[0] if kategori_tersedia else "Default")
            logger.warning(f"ADMIN: Nama kategori baru tidak valid. Menggunakan kategori default '{kategori}'. Oleh {pengguna_login_saat_ini.username}.")
            print(f"Nama kategori baru tidak valid atau kosong. Menggunakan kategori '{kategori}'.")

    else: # Jika memilih kategori dari daftar yang sudah ada
        kategori = kategori_tersedia[pilihan_kat - 1] # Mendapatkan nama kategori dari list berdasarkan nomor pilihan (1-based)

    try:
        # Membuat objek Produk baru menggunakan Pydantic Model
        # ID produk akan di-generate otomatis oleh Field(default_factory)
        produk_baru = Produk(
            nama=nama,
            harga=harga,
            stok=stok,
            kategori=kategori,
            deskripsi=deskripsi
        )

        # Menyimpan objek produk baru ke TinyDB
        simpan_produk(produk_baru) # Menggunakan fungsi simpan_produk yang menggunakan upsert

        # Mencatat aktivitas penambahan produk ke log
        logger.info(f"ADMIN: Produk '{nama}' (ID: {produk_baru.id}, Kategori: {kategori}) ditambah oleh {pengguna_login_saat_ini.username}.")

        # Memberikan umpan balik kepada pengguna
        print(f"\nProduk '{nama}' berhasil ditambahkan dengan ID: {produk_baru.id}");
    except ValidationError as e:
         # Menangani error validasi Pydantic jika data produk tidak valid
         logger.error(f"Gagal membuat model produk baru karena validasi Pydantic: {e}")
         print(f"Gagal menambah produk: Validasi Error - {e}")
    except Exception as e:
        # Menangani error tak terduga lainnya
        logger.error(f"Error tak terduga saat menambah produk: {e}")
        print(f"Terjadi kesalahan saat menambah produk: {e}");

    input_enter_lanjut() # Menunggu pengguna menekan Enter


def admin_ubah_produk():
    """Admin: Mengubah data produk yang sudah ada di toko."""
    bersihkan_layar(); print_header("Admin - Ubah Data Produk")

    # Menampilkan daftar produk agar admin dapat memilih mana yang akan diubah
    produk_ditampilkan = tampilkan_daftar_produk_toko(tampilkan_deskripsi=True) # Tampilkan deskripsi untuk info lebih lengkap
    if not produk_ditampilkan:
        print("Tidak ada produk untuk diubah."); input_enter_lanjut(); return # Keluar jika tidak ada produk

    # Meminta admin memilih produk dari daftar yang ditampilkan
    produk_dipilih = pilih_produk_dari_daftar(produk_ditampilkan)
    if not produk_dipilih:
        print("Pengubahan produk dibatalkan."); return # Keluar jika admin batal memilih

    print(f"\nMengubah produk: {produk_dipilih.nama} (ID: {produk_dipilih.id})")
    # Menampilkan informasi produk saat ini
    print(f"Info saat ini: Kategori: {produk_dipilih.kategori}, Harga: {format_rupiah(produk_dipilih.harga)}, Stok: {produk_dipilih.stok}, Deskripsi: {produk_dipilih.deskripsi or '-'}")

    # Meminta input untuk data baru, menggunakan nilai saat ini sebagai default
    nama_baru = input_valid(f"Nama baru [{produk_dipilih.nama}]: ", opsional=True, default_value=produk_dipilih.nama)

    # Meminta dan memvalidasi harga baru (float), menggunakan harga saat ini sebagai default opsional
    harga_baru = produk_dipilih.harga # Default awal adalah harga produk saat ini (objek Money)
    while True: # Loop untuk validasi input harga
        # Meminta input harga baru, menampilkan harga saat ini dalam format tanpa Rp
        harga_input_str = input_valid(f"Harga baru [{produk_dipilih.harga.amount:.0f}] (Kosongkan jika tidak diubah): Rp", opsional=True, default_value=str(produk_dipilih.harga.amount)) # Default berupa string
        if not harga_input_str:
             print("Harga tidak diubah.")
             break # Keluar dari loop harga jika input kosong (opsional default)
        try:
            harga_float_baru = float(harga_input_str) # Konversi input string ke float
            if harga_float_baru < 0: raise ValueError("Harga tidak boleh negatif.") # Validasi nilai negatif
            harga_baru = Money(harga_float_baru, IDR) # Konversi float ke objek Money
            break # Keluar dari loop harga jika input valid dan dikonversi
        except ValueError as e:
             # Menangani error jika input bukan angka atau negatif
             print(f"Input harga tidak valid: {e}. Harap masukkan angka positif.")

    # Meminta dan memvalidasi stok baru (integer), menggunakan stok saat ini sebagai default opsional
    stok_baru = produk_dipilih.stok # Default awal adalah stok produk saat ini
    while True: # Loop untuk validasi input stok
        # Meminta input stok baru, menampilkan stok saat ini
        stok_input_str = input_valid(f"Stok baru [{produk_dipilih.stok}] (Kosongkan jika tidak diubah): ", opsional=True, default_value=str(produk_dipilih.stok)) # Default berupa string
        if not stok_input_str:
             print("Stok tidak diubah.")
             break # Keluar dari loop stok jika input kosong (opsional default)
        try:
            stok_int_baru = int(stok_input_str) # Konversi input string ke integer
            if stok_int_baru < 0: raise ValueError("Stok tidak boleh negatif.") # Validasi nilai negatif
            stok_baru = stok_int_baru
            break # Keluar dari loop stok jika input valid dan dikonversi
        except ValueError as e:
             # Menangani error jika input bukan angka atau negatif
             print(f"Input stok tidak valid: {e}. Harap masukkan angka non-negatif.")


    # Meminta input deskripsi baru (opsional), menggunakan deskripsi saat ini sebagai default
    deskripsi_baru = input_valid(f"Deskripsi baru [{produk_dipilih.deskripsi or '-'}]: ", opsional=True, default_value=produk_dipilih.deskripsi)

    # Memilih kategori baru atau menambah kategori baru
    konfigurasi = dapatkan_konfigurasi() # Mengambil konfigurasi sistem
    kategori_tersedia = konfigurasi.get("kategori_produk", []) # Mendapatkan list kategori yang ada

    print("\nPilih Kategori Baru untuk Produk ini:");
    # Menampilkan kategori yang sudah ada
    if not kategori_tersedia: print("(Belum ada kategori. Pilihan akan menggunakan 'Lainnya' atau kategori baru.)")
    else: [print(f"{i+1}. {kat}") for i, kat in enumerate(kategori_tersedia)]
    print(f"{len(kategori_tersedia)+1}. Tambah Kategori Baru") # Opsi tambah kategori baru
    print(f"0. Tidak Ubah Kategori (Saat ini: {produk_dipilih.kategori})") # Opsi untuk tidak mengubah kategori

    # Meminta pilihan nomor kategori baru (termasuk opsi 0)
    pilihan_kat = input_pilihan_menu(len(kategori_tersedia) + 1, min_pilihan=0, prompt_pesan="Nomor Kategori Baru: ")

    kategori_baru = produk_dipilih.kategori # Default awal adalah kategori produk saat ini

    # Memproses pilihan kategori
    if pilihan_kat != 0 : # Jika tidak memilih opsi "Tidak Ubah Kategori"
        if pilihan_kat == len(kategori_tersedia) + 1: # Jika memilih opsi "Tambah Kategori Baru"
            kategori_input = input_valid("Masukkan Nama Kategori Baru: ").strip() # Meminta nama kategori baru
            if kategori_input and kategori_input not in kategori_tersedia:
                 # Jika nama kategori baru valid dan belum ada, tambahkan ke konfigurasi dan simpan
                 konfigurasi["kategori_produk"].append(kategori_input)
                 simpan_konfigurasi(konfigurasi) # Menyimpan perubahan konfigurasi ke TinyDB
                 kategori_baru = kategori_input # Menggunakan kategori baru
                 logger.info(f"ADMIN: Menambah kategori baru '{kategori_input}' saat ubah produk ID {produk_dipilih.id}. Oleh {pengguna_login_saat_ini.username}.")
                 print(f"Kategori '{kategori_input}' berhasil ditambah dan dipilih.")
            elif kategori_input in kategori_tersedia:
                 # Jika nama kategori baru sudah ada, gunakan yang sudah ada
                 kategori_baru = kategori_input
                 print(f"Kategori '{kategori_input}' sudah ada, dipilih.")
            else:
                 # Jika nama kategori baru tidak valid/kosong, beri tahu pengguna dan kategori tidak berubah
                 print("Nama kategori baru tidak valid atau kosong. Kategori tidak diubah.")
                 # kategori_baru tetap pada nilai default (kategori produk saat ini)
        else: # Jika memilih kategori dari daftar yang sudah ada
            kategori_baru = kategori_tersedia[pilihan_kat - 1] # Mendapatkan nama kategori dari list (1-based input)

    # Memperbarui objek produk di memori dengan nilai-nilai baru yang didapat dari input
    produk_dipilih.nama = nama_baru
    produk_dipilih.harga = harga_baru # Ini adalah objek Money
    produk_dipilih.stok = stok_baru
    produk_dipilih.deskripsi = deskripsi_baru
    produk_dipilih.kategori = kategori_baru # Memperbarui kategori jika dipilih atau ditambahkan

    try:
        # Menyimpan objek produk yang sudah diperbarui ke TinyDB
        simpan_produk(produk_dipilih) # Menggunakan fungsi simpan_produk yang menggunakan upsert

        # Mencatat aktivitas pengubahan produk ke log
        logger.info(f"ADMIN: Produk '{produk_dipilih.nama}' (ID: {produk_dipilih.id}) diubah oleh {pengguna_login_saat_ini.username}.")

        # Memberikan umpan balik kepada pengguna
        print(f"\nData produk '{produk_dipilih.nama}' berhasil diperbarui.");
    except ValidationError as e:
         # Menangani error validasi Pydantic jika data produk yang diperbarui tidak valid
         logger.error(f"Gagal memperbarui model produk karena validasi Pydantic: {e}")
         print(f"Gagal mengubah produk: Validasi Error - {e}")
    except Exception as e:
         # Menangani error tak terduga lainnya
         logger.error(f"Error tak terduga saat mengubah produk: {e}")
         print(f"Terjadi kesalahan saat mengubah produk: {e}");

    input_enter_lanjut() # Menunggu pengguna menekan Enter


def admin_hapus_produk():
    """Admin: Menghapus produk dari daftar produk toko."""
    bersihkan_layar(); print_header("Admin - Hapus Produk")

    # Menampilkan daftar produk agar admin dapat memilih mana yang akan dihapus
    produk_ditampilkan = tampilkan_daftar_produk_toko()
    if not produk_ditampilkan:
        print("Tidak ada produk untuk dihapus."); input_enter_lanjut(); return # Keluar jika tidak ada produk

    # Meminta admin memilih produk dari daftar yang ditampilkan
    produk_dipilih = pilih_produk_dari_daftar(produk_ditampilkan)
    if not produk_dipilih:
        print("Penghapusan produk dibatalkan."); return # Keluar jika admin batal memilih

    # Meminta konfirmasi penghapusan dari admin
    if input_valid(f"Yakin ingin menghapus produk '{produk_dipilih.nama}' (ID: {produk_dipilih.id})? (y/n): ", opsional=True, default_value='n').lower() == 'y':
        try:
            # Menghapus produk dari TinyDB berdasarkan ID
            if hapus_produk_by_id(produk_dipilih.id):
                # Mencatat aktivitas penghapusan produk ke log
                logger.info(f"ADMIN: Produk '{produk_dipilih.nama}' (ID: {produk_dipilih.id}) dihapus oleh {pengguna_login_saat_ini.username}.")
                # Memberikan umpan balik kepada pengguna
                print(f"Produk '{produk_dipilih.nama}' berhasil dihapus.")
            else:
                # Kasus jika produk tidak ditemukan di database saat mencoba menghapus (misalnya sudah dihapus sebelumnya)
                logger.warning(f"ADMIN: Gagal menghapus produk ID {produk_dipilih.id}, mungkin sudah dihapus?. Oleh {pengguna_login_saat_ini.username}.")
                print("Gagal menghapus produk. Produk tidak ditemukan di database saat ini.")
        except Exception as e:
             # Menangani error tak terduga selama proses penghapusan
             logger.error(f"Error tak terduga saat menghapus produk ID {produk_dipilih.id}: {e}")
             print(f"Terjadi kesalahan saat menghapus produk: {e}");
    else:
        # Jika admin membatalkan konfirmasi
        print("Penghapusan produk dibatalkan.")

    input_enter_lanjut() # Menunggu pengguna menekan Enter


def admin_lihat_laporan_penjualan():
    """Admin: Menampilkan laporan ringkasan penjualan toko."""
    bersihkan_layar(); print_header("Admin - Laporan Penjualan Toko")

    # Mengambil semua data pesanan dari TinyDB
    semua_pesanan = dapatkan_semua_pesanan_toko()

    # Jika tidak ada data pesanan
    if not semua_pesanan:
        print("Belum ada data penjualan."); input_enter_lanjut(); return # Keluar dari fungsi

    # Menghitung total pendapatan dari semua pesanan
    # Menggunakan sum() dengan nilai awal Money(0, IDR) untuk menjumlahkan objek Money
    total_pendapatan = sum((p.total_harga for p in semua_pesanan), Money(0, IDR))

    # Menampilkan ringkasan penjualan
    print(f"Total Transaksi Penjualan: {len(semua_pesanan)}")
    print(f"Total Pendapatan Bruto: {format_rupiah(total_pendapatan)}") # Menampilkan total pendapatan dalam format Rupiah
    print_separator_line()

    # Menghitung jumlah unit terjual per produk untuk mengetahui produk terlaris
    produk_terjual_count: dict[str, int] = {} # Dictionary: nama_produk -> jumlah_unit
    for pesanan in semua_pesanan: # Iterasi melalui setiap pesanan
        for item_dict in pesanan.items_pesanan: # Iterasi melalui setiap item dalam pesanan (dalam format dictionary)
             # Mengambil nama produk dan jumlah unit dari dictionary item
             nama_produk = item_dict.get('nama_produk', 'Produk Tidak Dikenal') # Fallback jika kunci hilang
             jumlah_unit = item_dict.get('jumlah', 0) # Fallback jika kunci hilang
             if jumlah_unit > 0:
                 # Menambahkan jumlah unit terjual untuk produk ini ke dictionary hitungan
                 produk_terjual_count[nama_produk] = produk_terjual_count.get(nama_produk, 0) + jumlah_unit

    # Menampilkan daftar produk terlaris (berdasarkan unit terjual)
    if produk_terjual_count: # Jika ada data produk terjual
        print("Produk Terlaris (berdasarkan unit terjual):")
        # Mengurutkan dictionary berdasarkan jumlah unit terjual (nilai), dari terbesar ke terkecil
        sorted_produk = sorted(produk_terjual_count.items(), key=lambda item: item[1], reverse=True)
        # Menampilkan 10 produk teratas (atau kurang jika total produk terjual kurang dari 10)
        for i, (nama, jumlah) in enumerate(sorted_produk[:10]):
            print(f"  {i+1}. {nama}: {jumlah} unit")
    else:
        print("Belum ada item produk terjual.")

    print_separator_line(); input_enter_lanjut() # Garis penutup dan menunggu input


def admin_kelola_kategori():
    """Admin: Menambah atau menghapus kategori produk yang tersedia di sistem."""
    while True: # Loop untuk tetap di menu kelola kategori sampai admin memilih kembali
        bersihkan_layar(); print_header("Admin - Kelola Kategori Produk")

        konfigurasi = dapatkan_konfigurasi() # Mengambil konfigurasi sistem (termasuk list kategori)
        kategori_tersedia = konfigurasi.get("kategori_produk", []) # Mendapatkan list kategori yang ada

        print("Kategori Produk Saat Ini:");
        # Menampilkan kategori yang sudah ada dengan nomor
        if not kategori_tersedia: print("(Belum ada kategori.)")
        else: [print(f"{i+1}. {kat}") for i, kat in enumerate(kategori_tersedia)]
        print_separator_line()

        # Menampilkan opsi menu kelola kategori
        print("1. Tambah Kategori Baru")
        print("2. Hapus Kategori")
        print("3. Kembali ke Menu Admin")
        print_separator_line()

        pilihan = input_pilihan_menu(3) # Meminta pilihan dari admin

        if pilihan == 1: # Memilih opsi "Tambah Kategori Baru"
            nama_baru = input_valid("Masukkan Nama Kategori Baru: ").strip() # Meminta nama kategori baru
            if nama_baru and nama_baru not in kategori_tersedia:
                # Jika nama kategori valid dan belum ada, tambahkan ke list di konfigurasi (memori)
                konfigurasi["kategori_produk"].append(nama_baru)
                simpan_konfigurasi(konfigurasi) # Menyimpan perubahan konfigurasi ke TinyDB
                logger.info(f"ADMIN: Kategori '{nama_baru}' added by {pengguna_login_saat_ini.username}.")
                print(f"Kategori '{nama_baru}' berhasil ditambahkan.")
            elif nama_baru in kategori_tersedia:
                 # Jika nama kategori sudah ada
                 print("Kategori dengan nama tersebut sudah ada.")
            else:
                 # Jika nama kategori tidak valid (kosong atau hanya spasi)
                 print("Nama kategori tidak valid atau kosong.")

        elif pilihan == 2: # Memilih opsi "Hapus Kategori"
            if not kategori_tersedia: # Jika tidak ada kategori untuk dihapus
                print("Tidak ada kategori untuk dihapus."); input_enter_lanjut(); continue # Kembali ke awal loop menu kelola kategori

            print("\nPilih nomor kategori yang akan dihapus:")
            # Menampilkan kategori yang bisa dihapus dengan nomor
            [print(f"{i+1}. {kat}") for i, kat in enumerate(kategori_tersedia)]
            print("0. Batal") # Opsi batal
            print_separator_line()

            # Meminta nomor kategori yang akan dihapus
            pilihan_hapus = input_pilihan_menu(len(kategori_tersedia), min_pilihan=0)
            if pilihan_hapus == 0:
                print("Penghapusan kategori dibatalkan."); continue # Batal jika pilihan 0

            idx_hapus = pilihan_hapus - 1 # Menghitung index dari nomor pilihan (1-based)
            kategori_dihapus = kategori_tersedia[idx_hapus] # Mendapatkan nama kategori yang akan dihapus

            # Mengecek apakah kategori yang akan dihapus masih digunakan oleh produk
            semua_produk = dapatkan_semua_produk() # Mengambil semua produk
            digunakan = any(prod.kategori == kategori_dihapus for prod in semua_produk) # Memeriksa apakah ada produk dengan kategori ini

            if digunakan:
                # Jika kategori masih digunakan oleh produk
                print(f"Kategori '{kategori_dihapus}' masih digunakan oleh beberapa produk. Tidak bisa dihapus.");
                logger.warning(f"ADMIN: Failed to delete category '{kategori_dihapus}', still in use by products. By {pengguna_login_saat_ini.username}.")
            else:
                # Jika kategori tidak digunakan, minta konfirmasi penghapusan
                if input_valid(f"Yakin ingin menghapus kategori '{kategori_dihapus}'? (y/n): ", opsional=True, default_value='n').lower() == 'y':
                    # Menghapus kategori dari list di konfigurasi (memori)
                    konfigurasi["kategori_produk"].pop(idx_hapus)
                    simpan_konfigurasi(konfigurasi) # Menyimpan perubahan konfigurasi ke TinyDB
                    logger.info(f"ADMIN: Kategori '{kategori_dihapus}' deleted by {pengguna_login_saat_ini.username}.")
                    print(f"Kategori '{kategori_dihapus}' berhasil dihapus.")
                else:
                    print("Penghapusan kategori dibatalkan.")

        elif pilihan == 3:
            break # Keluar dari loop menu kelola kategori dan kembali ke menu admin

        input_enter_lanjut() # Menunggu pengguna menekan Enter sebelum mengulangi loop menu kelola kategori


def admin_lihat_semua_akun_bank():
    """Admin: Menampilkan daftar semua akun pengguna (termasuk admin) di sistem."""
    bersihkan_layar(); print_header("Admin - Daftar Semua Akun Bank")

    # Mengambil semua dokumen pengguna dari tabel 'pengguna' dan mengubahnya menjadi objek Pengguna
    semua_pengguna_obj = [Pengguna(**u) for u in db.table('pengguna').all()]

    # Jika tidak ada akun pengguna (selain admin default, jika belum dibuat)
    if not semua_pengguna_obj:
        print("Belum ada akun pengguna di sistem."); input_enter_lanjut(); return # Keluar dari fungsi

    # Menampilkan header tabel daftar akun pengguna
    print_separator_line(120)
    print(f"{'ID':<37} | {'Username':<20} | {'Nama':<25} | {'Peran':<10} | {'Saldo':<15} | {'Kunci?':<7}")
    print_separator_line(120)

    # Menampilkan setiap akun pengguna dalam format tabel
    for p in semua_pengguna_obj:
        # Mengecek status akun terkunci
        kunci = "Ya" if p.akun_terkunci_hingga and p.akun_terkunci_hingga > datetime.datetime.now() else "Tidak"
        # Memformat saldo bank (menggunakan objek Money)
        saldo_formatted = format_rupiah(p.saldo_bank)

        # Mencetak satu baris informasi akun
        print(f"{p.id:<37} | {p.username:<20} | {(p.nama_lengkap or '-'):<25} | {p.peran:<10} | {saldo_formatted:<15} | {kunci:<7}")

    # Menampilkan garis penutup tabel
    print_separator_line(120); input_enter_lanjut() # Menunggu pengguna menekan Enter


def admin_lihat_semua_transaksi_bank():
    """Admin: Menampilkan daftar semua transaksi bank yang pernah terjadi dalam sistem."""
    bersihkan_layar(); print_header("Admin - Semua Transaksi Bank Sistem")

    # Mengambil semua dokumen transaksi dari tabel 'transaksi_bank' dan mengubahnya menjadi objek TransaksiBank
    semua_trx = dapatkan_semua_transaksi_bank()

    # Jika tidak ada data transaksi
    if not semua_trx:
        print("Belum ada data transaksi bank."); input_enter_lanjut(); return # Keluar dari fungsi

    # Mengurutkan daftar transaksi berdasarkan timestamp, dari yang paling baru ke yang paling lama
    semua_trx.sort(key=lambda t: t.timestamp, reverse=True)

    # Menampilkan header tabel transaksi
    print_separator_line(160)
    # Kolom saldo akhir tidak ditampilkan di laporan admin untuk ringkasan
    print(f"{'ID Trx':<37} | {'Timestamp':<26} | {'User Sumber':<15} | {'User Tujuan':<15} | {'Jenis':<18} | {'Jumlah':<15} | {'Ket.':<25}")
    print_separator_line(160)

    # Menampilkan setiap transaksi dalam format tabel
    for trx in semua_trx:
        # Mendapatkan username pengguna sumber dari ID
        u_sumber_obj = dapatkan_pengguna_by_id(trx.user_id_sumber)
        u_sumber = u_sumber_obj.username if u_sumber_obj else "N/A" # Menampilkan username atau "N/A"

        # Mendapatkan username pengguna tujuan dari ID (jika ada)
        u_tujuan = "-" # Default tampilan jika tidak ada pengguna tujuan
        if trx.user_id_tujuan: # Jika field user_id_tujuan tidak kosong
             u_tujuan_obj = dapatkan_pengguna_by_id(trx.user_id_tujuan)
             u_tujuan = u_tujuan_obj.username if u_tujuan_obj else "N/A" # Menampilkan username atau "N/A"

        # Memformat jumlah transaksi (menggunakan objek Money)
        jumlah_formatted = format_rupiah(trx.jumlah)

        # Mencetak satu baris transaksi
        print(f"{trx.timestamp.strftime('%Y-%m-%d %H:%M:%S'):<26} | {trx.jenis_transaksi:<18} | {trx.keterangan[:25]:<25} | {jumlah_formatted:<15} | {u_sumber:<15} | {u_tujuan:<15}")
        # Kolom diubah urutannya agar user sumber dan tujuan di akhir, lebih sesuai dengan keterangan
        # print(f"{trx.id:<37} | {trx.timestamp.strftime('%Y-%m-%d %H:%M:%S'):<26} | {u_sumber:<15} | {u_tujuan:<15} | {trx.jenis_transaksi:<18} | {jumlah_formatted:<15} | {trx.keterangan[:25]:<25}") # Format asli

    # Menampilkan garis penutup tabel
    print_separator_line(160); input_enter_lanjut() # Menunggu pengguna menekan Enter


# ==============================================================================
# === BLOK 10: FUNGSI PENGATURAN AKUN ===
# ==============================================================================
# Fungsi-fungsi untuk memungkinkan pengguna mengubah detail akun mereka (nama, email, password, PIN).
# Menggunakan Pydantic Model Pengguna dan Passlib untuk keamanan kredensial.

def menu_pengaturan_akun(is_admin_self_setting: bool = False):
    """Menu pengaturan akun untuk pengguna yang sedang login."""
    # Target pengaturan adalah objek pengguna yang sedang login
    target_pengguna = pengguna_login_saat_ini

    # Tambahkan validasi pengamanan: memastikan ada pengguna yang sedang login
    if not target_pengguna:
        logger.error("Attempted to access account settings menu without a logged-in user.")
        print("Error: Tidak ada pengguna yang sedang login. Silakan login terlebih dahulu."); input_enter_lanjut(); return # Keluar jika tidak ada pengguna login

    while True: # Loop menu pengaturan akun
        bersihkan_layar(); print_header(f"Pengaturan Akun - {target_pengguna.username}")
        # Menampilkan informasi akun saat ini
        print(f"Nama Lengkap: {target_pengguna.nama_lengkap or '(Belum diatur)'}")
        print(f"Email: {target_pengguna.email or '(Belum diatur)'}")
        print_separator_line()

        # Menampilkan opsi pengaturan
        print("1. Ubah Nama Lengkap")
        print("2. Ubah Email")
        print("3. Ubah Password")
        print("4. Ubah PIN Bank")
        print("5. Kembali")
        print_separator_line()

        pilihan = input_pilihan_menu(5) # Meminta pilihan dari pengguna

        if pilihan == 1: # Mengubah Nama Lengkap
            nama_lengkap_baru = input_valid("Masukkan Nama Lengkap Baru: ", opsional=True, default_value=target_pengguna.nama_lengkap) # Meminta input baru
            if nama_lengkap_baru != target_pengguna.nama_lengkap: # Hanya proses jika ada perubahan nilai
                target_pengguna.nama_lengkap = nama_lengkap_baru # Memperbarui nama lengkap di objek pengguna (memori)
                simpan_pengguna(target_pengguna) # Menyimpan perubahan ke database
                logger.info(f"Pengguna '{target_pengguna.username}' ubah nama lengkap menjadi '{nama_lengkap_baru}'.")
                print("Nama lengkap berhasil diperbarui.");
            else:
                 print("Nama lengkap tidak diubah.") # Memberi tahu jika tidak ada perubahan


        elif pilihan == 2: # Mengubah Email
            # Meminta input email baru (opsional), menggunakan email saat ini sebagai default (string kosong jika None)
            email_input_str = input_valid(f"Masukkan Email Baru [{target_pengguna.email or '-'}]: ", opsional=True, default_value=target_pengguna.email or "")
            # Mengonversi input string menjadi None jika kosong setelah strip(), jika tidak, gunakan nilai string
            email_baru = email_input_str if email_input_str.strip() else None

            # Mengecek validasi format email jika email_baru bukan None
            if email_baru and not re.fullmatch(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email_baru):
                 print("Format email tidak valid. Email tidak diubah.");
                 email_baru = target_pengguna.email # Mengembalikan nilai email ke nilai lama jika format salah

            # Hanya proses jika ada perubahan nilai email (termasuk dari/ke None)
            if email_baru != target_pengguna.email:
                target_pengguna.email = email_baru # Memperbarui email di objek pengguna (memori)
                simpan_pengguna(target_pengguna) # Menyimpan perubahan ke database
                logger.info(f"Pengguna '{target_pengguna.username}' ubah email menjadi '{email_baru}'.")
                print("Email berhasil diperbarui.");
            else:
                 print("Email tidak diubah.") # Memberi tahu jika tidak ada perubahan


        elif pilihan == 3: # Mengubah Password
            # Meminta verifikasi PIN sebagai otorisasi untuk mengubah password (jika PIN sudah diatur)
            if target_pengguna.pin_hash: # Hanya minta PIN jika pin_hash ada
                 if not minta_pin_transaksi(target_pengguna, "untuk otorisasi ubah password"):
                     input_enter_lanjut(); continue # Batal jika verifikasi PIN gagal

            # Meminta password lama dan memverifikasinya
            password_lama_input = input_valid("Masukkan Password Lama: ", sembunyikan_input=True)
            if not target_pengguna.verifikasi_password(password_lama_input): # Menggunakan metode verifikasi Passlib di objek Pengguna
                print("Password lama salah. Pengubahan password dibatalkan."); input_enter_lanjut(); continue # Batal jika password lama salah

            # Meminta dan memvalidasi password baru
            password_regex = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&_])[A-Za-z\d@$!%*?&_]{8,30}$" # Regex untuk kekuatan password
            password_baru = input_valid("Masukkan Password Baru: ", sembunyikan_input=True, validasi_regex=password_regex, pesan_error_regex="Password baru tidak memenuhi syarat keamanan.")
            # Meminta konfirmasi password baru
            if password_baru != input_valid("Konfirmasi Password Baru: ", sembunyikan_input=True):
                print("Password baru tidak cocok. Pengubahan password dibatalkan."); input_enter_lanjut(); continue # Batal jika password baru tidak cocok

            # Membuat hash password baru menggunakan Passlib dan menyimpannya di objek pengguna
            target_pengguna.password_hash = pwd_context.hash(password_baru)
            simpan_pengguna(target_pengguna) # Menyimpan perubahan password ke database

            logger.info(f"Pengguna '{target_pengguna.username}' ubah password.")
            print("Password berhasil diubah."); # Memberikan umpan balik


        elif pilihan == 4: # Mengubah PIN Bank
            # Meminta verifikasi PIN lama sebagai otorisasi (jika PIN sudah diatur)
            if target_pengguna.pin_hash: # Hanya minta PIN lama jika pin_hash ada
                 if not minta_pin_transaksi(target_pengguna, "untuk otorisasi ubah PIN"):
                     input_enter_lanjut(); continue # Batal jika verifikasi PIN gagal
            else:
                 print("Anda belum memiliki PIN Bank yang terdaftar. Silakan buat PIN baru.")


            # Meminta dan memvalidasi PIN baru (6 digit angka)
            pin_baru = input_valid("Masukkan PIN Bank Baru (6 digit angka): ", sembunyikan_input=True, validasi_regex=r"^\d{6}$", pesan_error_regex="PIN Bank harus terdiri dari 6 digit angka.")
            # Meminta konfirmasi PIN baru
            if pin_baru != input_valid("Konfirmasi PIN Bank Baru: ", sembunyikan_input=True):
                print("PIN Bank baru tidak cocok. Pengubahan PIN dibatalkan."); input_enter_lanjut(); continue # Batal jika PIN baru tidak cocok

            # Mengatur PIN baru di objek pengguna menggunakan metode set_pin (ini akan membuat hash PIN baru)
            target_pengguna.set_pin(pin_baru)
            simpan_pengguna(target_pengguna) # Menyimpan perubahan PIN ke database

            logger.info(f"Pengguna '{target_pengguna.username}' ubah/buat PIN Bank.")
            print("PIN Bank berhasil diubah/dibuat."); # Memberikan umpan balik


        elif pilihan == 5: # Kembali ke menu sebelumnya
            break # Keluar dari loop menu pengaturan akun

        input_enter_lanjut() # Menunggu pengguna menekan Enter sebelum mengulangi loop menu pengaturan akun


# ==============================================================================
# === BLOK 11: FUNGSI TAMPILAN MENU ===
# ==============================================================================
# Fungsi-fungsi untuk menampilkan struktur menu utama dan menu sub-modul
# (Toko dan Bank) sesuai dengan peran pengguna yang sedang login.

def menu_utama_non_login():
    """Menampilkan menu utama saat tidak ada pengguna yang sedang login."""
    # Mengambil nama toko dari konfigurasi sistem untuk ditampilkan di header
    konfigurasi = dapatkan_konfigurasi() # Menggunakan fungsi yang sudah diperbaiki
    nama_toko = konfigurasi.get("nama_toko", "Bear Mart") # Mengambil nama toko, default "Bear Mart"

    bersihkan_layar(); print_header(f"Selamat Datang di {nama_toko} & Bank") # Menampilkan header

    print("Status: Belum Login") # Menunjukkan status login
    print_separator_line() # Garis pemisah

    # Opsi menu untuk pengguna yang belum login
    print("1. Login")
    print("2. Registrasi Akun Baru")
    print("3. Lihat Produk Toko (Guest Mode)") # Memungkinkan tamu melihat daftar produk
    print("4. Keluar Program") # Opsi keluar dari program
    print_separator_line() # Garis pemisah bawah

    # Meminta dan mengembalikan pilihan menu dari pengguna
    return input_pilihan_menu(4) # Mengembalikan integer pilihan


def menu_utama_pelanggan():
    """Menampilkan menu utama untuk pengguna dengan peran PELANGGAN."""
    # Mengambil nama toko dari konfigurasi sistem
    konfigurasi = dapatkan_konfigurasi() # Menggunakan fungsi yang sudah diperbaiki
    nama_toko = konfigurasi.get("nama_toko", "Bear Mart") # Mengambil nama toko

    # Membersihkan layar dan menampilkan header dengan username pengguna yang login
    bersihkan_layar(); print_header(f"Menu Utama - {pengguna_login_saat_ini.username}")

    # Menampilkan saldo bank pengguna (menggunakan format_rupiah)
    # Menambahkan validasi pengamanan jika entah bagaimana pengguna_login_saat_ini None
    if pengguna_login_saat_ini:
        print(f"Saldo Bank Anda: {format_rupiah(pengguna_login_saat_ini.saldo_bank)}")
    else:
        print("Informasi Saldo: Tidak tersedia (Objek pengguna hilang?)") # Safety message

    print_separator_line() # Garis pemisah

    # Opsi menu untuk pengguna PELANGGAN
    print(f"1. {nama_toko} (Modul Toko)") # Masuk ke modul toko
    print("2. Bear Bank (Modul Perbankan)") # Masuk ke modul bank
    print("3. Pengaturan Akun") # Mengubah detail akun
    print("4. Logout") # Keluar dari sesi login
    print_separator_line() # Garis pemisah bawah

    # Meminta dan mengembalikan pilihan menu dari pengguna
    return input_pilihan_menu(4) # Mengembalikan integer pilihan


def menu_utama_admin():
    """Menampilkan menu utama (Panel Admin) untuk pengguna dengan peran ADMIN."""
    # Membersihkan layar dan menampilkan header Panel Admin dengan username admin yang login
    bersihkan_layar(); print_header(f"Panel Admin - {pengguna_login_saat_ini.username}")

    print("--- Manajemen Toko ---") # Bagian menu terkait manajemen toko
    print("1. Tambah Produk Baru") # Opsi menambah produk
    print("2. Ubah Data Produk")   # Opsi mengubah data produk yang sudah ada
    print("3. Hapus Produk")      # Opsi menghapus produk
    print("4. Lihat Laporan Penjualan") # Opsi melihat laporan penjualan
    print("5. Kelola Kategori Produk") # Opsi menambah/menghapus kategori
    print_separator_line() # Garis pemisah

    print("--- Manajemen Bank & Pengguna ---") # Bagian menu terkait bank dan pengguna
    print("6. Lihat Semua Akun Bank")       # Opsi melihat daftar semua akun pengguna
    print("7. Lihat Semua Transaksi Bank Sistem") # Opsi melihat riwayat semua transaksi bank
    print("8. Pengaturan Akun Admin") # Opsi mengatur akun admin yang sedang login
    print_separator_line() # Garis pemisah

    print("9. Logout") # Opsi logout
    print_separator_line() # Garis pemisah bawah

    # Meminta dan mengembalikan pilihan menu dari admin
    return input_pilihan_menu(9) # Mengembalikan integer pilihan


def menu_toko_pelanggan():
    """Menampilkan menu spesifik untuk modul Toko Bear Mart bagi pengguna PELANGGAN."""
    global keranjang_belanja_global # Mengizinkan akses ke keranjang belanja global

    while True: # Loop untuk tetap di menu toko sampai pengguna memilih kembali
        # Mengambil nama toko dari konfigurasi sistem
        konfigurasi = dapatkan_konfigurasi() # Menggunakan fungsi yang sudah diperbaiki
        nama_toko = konfigurasi.get("nama_toko", "Bear Mart") # Mengambil nama toko

        bersihkan_layar(); print_header(f"{nama_toko} - Modul Toko") # Menampilkan header modul toko

        # Menampilkan ringkasan isi keranjang belanja saat ini
        # Menggunakan len() pada dictionary items untuk jumlah item, dan format_rupiah untuk total belanja
        print(f"Keranjang Belanja Anda: {len(keranjang_belanja_global.items)} item | Total: {format_rupiah(keranjang_belanja_global.total_belanja)}")
        print_separator_line() # Garis pemisah

        # Opsi menu modul toko
        print("1. Tampilkan/Cari Produk & Tambah ke Keranjang") # Opsi untuk melihat produk dan menambahkannya
        print("2. Lihat Isi Keranjang Belanja") # Opsi untuk melihat detail item di keranjang
        print("3. Ubah Jumlah Item di Keranjang") # Opsi untuk mengubah jumlah atau menghapus item
        print("4. Proses Pembayaran (Checkout)") # Opsi untuk melanjutkan ke proses pembayaran
        print("5. Lihat Riwayat Pembelian Anda") # Opsi untuk melihat riwayat pesanan toko
        print("6. Kembali ke Menu Utama") # Opsi untuk kembali

        pilihan = input_pilihan_menu(6) # Meminta pilihan dari pengguna

        # Memproses pilihan menu
        if pilihan == 1:
            # Fungsi tambah_produk_ke_keranjang_toko sudah memiliki alur internal
            # untuk menampilkan/mencari/memfilter dan memilih produk.
            tambah_produk_ke_keranjang_toko()
        elif pilihan == 2:
            lihat_keranjang_toko()
        elif pilihan == 3:
            ubah_item_keranjang_toko()
        elif pilihan == 4:
            proses_pembayaran_toko() # Memulai proses pembayaran
        elif pilihan == 5:
            lihat_riwayat_pembelian_toko()
        elif pilihan == 6:
            break # Keluar dari loop menu toko dan kembali ke menu utama pelanggan


def menu_bank_pelanggan():
    """Menampilkan menu spesifik untuk modul Bank Bear Mart bagi pengguna PELANGGAN."""
    while True: # Loop untuk tetap di menu bank sampai pengguna memilih kembali
        bersihkan_layar(); print_header("Bear Bank - Modul Perbankan") # Menampilkan header modul bank

        # Menampilkan saldo bank pengguna yang sedang login (menggunakan format_rupiah)
        # Menambahkan validasi pengamanan jika entah bagaimana pengguna_login_saat_ini None
        if pengguna_login_saat_ini:
             print(f"Saldo Anda Saat Ini: {format_rupiah(pengguna_login_saat_ini.saldo_bank)}")
        else:
             print("Informasi Saldo: Tidak tersedia") # Safety message

        print_separator_line() # Garis pemisah

        # Opsi menu modul bank
        print("1. Lihat Saldo Rekening") # Opsi melihat saldo
        print("2. Deposit Saldo")        # Opsi menambahkan saldo
        print("3. Withdraw Saldo")       # Opsi menarik saldo
        print("4. Transfer Dana ke Pengguna Lain") # Opsi mentransfer dana
        print("5. Lihat Riwayat Transaksi Bank") # Opsi melihat riwayat transaksi
        print("6. Kembali ke Menu Utama") # Opsi untuk kembali

        pilihan = input_pilihan_menu(6) # Meminta pilihan dari pengguna

        # Menambahkan validasi pengamanan: memastikan ada pengguna yang login sebelum akses fungsi bank
        if not pengguna_login_saat_ini:
             logger.error("Accessed bank menu option without logged-in user object.")
             print("Error: Anda harus login untuk mengakses fungsi Bank."); input_enter_lanjut(); continue # Kembali ke awal loop menu bank

        # Memproses pilihan menu
        if pilihan == 1:
            lihat_saldo_bank()
        elif pilihan == 2:
            deposit_bank()
        elif pilihan == 3:
            withdraw_bank()
        elif pilihan == 4:
            transfer_dana_bank()
        elif pilihan == 5:
            lihat_riwayat_transaksi_bank()
        elif pilihan == 6:
            break # Keluar dari loop menu bank dan kembali ke menu utama pelanggan

# ==============================================================================
# === BLOK 12: LOOP UTAMA PROGRAM ===
# ==============================================================================
# Mengatur alur utama eksekusi program. Ini adalah loop yang terus berjalan
# sampai pengguna memilih opsi untuk keluar. Memanggil fungsi-fungsi menu
# berdasarkan status login dan peran pengguna.

def jalankan_program():
    """Fungsi utama untuk menjalankan aplikasi Bear Mart & Bank."""

    # >>> PERUBAHAN: Panggil fungsi inisialisasi_database_jika_perlu di awal program <<<
    # Fungsi ini akan memastikan database dan data dasar (config, admin, produk contoh)
    # ada saat program dimulai. Ini harus dipanggil hanya sekali.
    inisialisasi_database_jika_perlu()
    # >>> ------------------------------------------------------------------- <<<

    # Loop utama program yang terus berjalan
    while True:
        # Mengecek apakah ada objek pengguna yang tersimpan di variabel global pengguna_login_saat_ini
        if pengguna_login_saat_ini:
            # Jika ada pengguna login, cek perannya
            if pengguna_login_saat_ini.peran == PERAN_PELANGGAN:
                # Jika peran adalah PELANGGAN, tampilkan menu utama pelanggan
                pilihan = menu_utama_pelanggan()
                # Memproses pilihan menu pelanggan
                if pilihan == 1:
                    menu_toko_pelanggan() # Masuk ke modul toko
                elif pilihan == 2:
                    menu_bank_pelanggan() # Masuk ke modul bank
                elif pilihan == 3:
                    menu_pengaturan_akun() # Masuk ke pengaturan akun pengguna
                elif pilihan == 4:
                    logout_pengguna() # Melakukan logout

            elif pengguna_login_saat_ini.peran == PERAN_ADMIN:
                # Jika peran adalah ADMIN, tampilkan menu utama admin (Panel Admin)
                pilihan = menu_utama_admin()
                # Memproses pilihan menu admin
                if pilihan == 1:
                    admin_tambah_produk() # Admin: Tambah produk baru
                elif pilihan == 2:
                    admin_ubah_produk() # Admin: Ubah data produk
                elif pilihan == 3:
                    admin_hapus_produk() # Admin: Hapus produk
                elif pilihan == 4:
                    admin_lihat_laporan_penjualan() # Admin: Lihat laporan penjualan
                elif pilihan == 5:
                    admin_kelola_kategori() # Admin: Kelola kategori produk
                elif pilihan == 6:
                    admin_lihat_semua_akun_bank() # Admin: Lihat semua akun pengguna
                elif pilihan == 7:
                    admin_lihat_semua_transaksi_bank() # Admin: Lihat semua transaksi bank sistem
                elif pilihan == 8:
                    # Admin mengatur akunnya sendiri (menggunakan menu pengaturan akun dengan flag)
                    menu_pengaturan_akun(is_admin_self_setting=True)
                elif pilihan == 9:
                    logout_pengguna() # Melakukan logout admin

        else: # Jika tidak ada pengguna yang sedang login (pengguna_login_saat_ini adalah None)
            # Tampilkan menu utama untuk status belum login
            pilihan = menu_utama_non_login()
            # Memproses pilihan menu non-login
            if pilihan == 1:
                login_pengguna() # Melakukan proses login
            elif pilihan == 2:
                registrasi_pengguna_baru() # Melakukan proses registrasi
            elif pilihan == 3:
                # Memungkinkan pengguna tamu melihat daftar produk toko
                bersihkan_layar(); print_header("Produk Bear Mart (Guest Mode)")
                # Mengambil nama toko dari konfigurasi untuk header guest mode
                konfigurasi = dapatkan_konfigurasi() # Menggunakan fungsi yang sudah diperbaiki
                nama_toko = konfigurasi.get("nama_toko", "Bear Mart")
                bersihkan_layar(); print_header(f"Produk {nama_toko} (Guest Mode)")
                # Menampilkan daftar produk tanpa opsi pembelian
                tampilkan_daftar_produk_toko(tampilkan_deskripsi=True)
                print("\nSilakan login atau registrasi untuk berbelanja."); input_enter_lanjut()
            elif pilihan == 4:
                # Memilih opsi keluar dari program
                print("Terima kasih telah menggunakan layanan Bear Mart & Bank. Sampai jumpa!")
                logger.info("Program dihentikan oleh pengguna."); # Mencatat di log
                time.sleep(1); # Memberikan jeda singkat sebelum keluar
                bersihkan_layar(); # Membersihkan layar sebelum program berakhir
                break # Menghentikan loop utama, sehingga program berakhir


# ==============================================================================
# === BLOK 13: EKSEKUSI PROGRAM UTAMA ===
# ==============================================================================
# Blok ini adalah titik masuk utama program ketika file skrip dijalankan.
# Memastikan bahwa fungsi jalankan_program() hanya dipanggil saat skrip dieksekusi langsung.

if __name__ == "__main__":
    # Mencatat awal eksekusi program ke log
    logger.info("=== Program Bear Mart & Bank (Powerfull Version) dimulai ===")
    try:
        # Memulai eksekusi loop utama program
        jalankan_program()
    except KeyboardInterrupt: # Menangani interupsi dari keyboard (misalnya, menekan Ctrl+C)
        print("\nProgram dihentikan paksa oleh pengguna (KeyboardInterrupt).")
        logger.warning("Program dihentikan paksa (KeyboardInterrupt).")
    except Exception as e: # Menangani kesalahan tak terduga lainnya yang terjadi selama eksekusi
        print(f"\nTerjadi kesalahan tak terduga: {e}")
        logger.error(f"FATAL ERROR: Terjadi kesalahan tak terduga: {e} - Program berhenti.")
        # Secara opsional, Anda bisa mencatat traceback lengkap ke log untuk debugging
        import traceback
        logger.error(f"Traceback lengkap:\n{traceback.format_exc()}")
    finally:
        # Mencatat akhir eksekusi program ke log, terlepas dari apakah terjadi error atau keluar normal
        logger.info("=== Program Bear Mart & Bank (Powerfull Version) selesai ===")