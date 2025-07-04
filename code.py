# ==============================================================================
# === BLOK 1: IMPORT & KONFIGURASI GLOBAL ===
# ==============================================================================
# Tujuan: Mengimpor semua library yang diperlukan, melakukan setup awal untuk
# database, logger, dan hashing. Mendefinisikan konstanta dan path file.

import os
import re
import time
import sys
import uuid # Digunakan untuk menghasilkan ID unik
import datetime
import contextlib
from typing import List, Optional, Annotated # Digunakan untuk type hinting

# --- Import Library Eksternal ---
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
FOLDER_DATABASE = "/home/vivobook14/Source_code/Repository/Mart_Bank_Project/database"
FOLDER_LOG = "/home/vivobook14/Source_code/Repository/Mart_Bank_Project/logs"

# Pastikan folder penyimpanan ada; dibuat jika belum ada
os.makedirs(FOLDER_DATABASE, exist_ok=True)
os.makedirs(FOLDER_LOG, exist_ok=True)

# Nama file database utama dan log aktivitas
NAMA_FILE_DATABASE = "Novi_mart_bank_data.json"
NAMA_FILE_LOG = "activity.log"

# Gabungkan path folder dengan nama file
PATH_DATABASE = os.path.join(FOLDER_DATABASE, NAMA_FILE_DATABASE)
PATH_LOG = os.path.join(FOLDER_LOG, NAMA_FILE_LOG)


# --- Setup Logging (Loguru) ---
logger.remove()
logger.add(
    PATH_LOG,
    rotation="5 MB",      # Rotasi file log saat ukuran mencapai 5 MB
    retention="10 days",  # Hanya menyimpan log dari 10 hari terakhir
    level="INFO",         # Level log minimum yang akan dicatat
    format="{time:YYYY-MM-DD HH:mm:ss} - {message}", # Format output log
    encoding='utf-8'
)

# --- Setup Hashing Password dan PIN (Passlib) ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Setup Database (TinyDB) ---
db = TinyDB(PATH_DATABASE, indent=4, ensure_ascii=False)

# Mendefinisikan objek Query untuk setiap "tabel" di TinyDB
PenggunaQuery = Query()
ProdukQuery = Query()
TransaksiQuery = Query()
PesananQuery = Query()
KonfigurasiQuery = Query()


# --- Konstanta & Konfigurasi Lainnya ---

# =========================================================
# === SAKLAR MODE PENGEMBANGAN (DEVELOPMENT MODE) ===
# Atur ke username (misal, "admin") untuk melewati login.
# Atur ke None untuk menjalankan program secara normal.
DEVELOPMENT_AUTO_LOGIN_AS = ""
DEVELOPMENT_TIMEOUT_SECONS = 5
# =========================================================

PERAN_PELANGGAN = "PELANGGAN"
PERAN_ADMIN = "ADMIN"
PERAN_ADMIN_UTAMA = "ADMIN_UTAMA"

ADMIN_USERNAME_DEFAULT = "admin"
ADMIN_PASSWORD_DEFAULT = "Adminpinter123!"
ADMIN_PIN_DEFAULT = "123456"

BATAS_PERCOBAAN_LOGIN = 3
DURASI_KUNCI_AKUN_MENIT = 5

# ---KONSTANTA PRODUK---
KATEGORI_PRODUK_DEFAULT = ["Makanan Ringan", "Minuman", "Kebutuhan Pokok", "Perlengkapan Mandi", "Produk Segar", "Elektronik Rumah Tangga", "Lainnya"]
PRODUK_DEFAULT = [
    {"nama": "Keripik Kentang Original 100g", "harga": 12000, "stok": 80, "kategori": "Makanan Ringan", "deskripsi": "Rennyah dan gurih."},
    {"nama": "Shampoo Anti Ketombe 250ml", "harga": 28000, "stok": 60, "kategori": "Perlengkapan Mandi", "deskripsi": "Membersihkan ketombe secara efektif."},
    {"nama": "Susu UHT Full Cream 1L", "harga": 18500, "stok": 150, "kategori": "Minuman", "deskripsi": "Susu UHT segar berkualitas."},
    {"nama": "Beras Pandan Wangi 5kg", "harga": 75000, "stok": 40, "kategori": "Kebutuhan Pokok", "deskripsi": "Beras premium dengan aroma pandan."},
    {"nama": "Apel Fuji per kg", "harga": 35000, "stok": 25, "kategori": "Produk Segar", "deskripsi": "Apel segar, manis dan renyah."},
    {"nama": "Lampu LED 10W", "harga": 22000, "stok": 50, "kategori": "Elektronik Rumah Tangga", "deskripsi": "Lampu hemat energi."},
]

# ID Konstan untuk Dokumen Konfigurasi Sistem.
# Menggunakan ID yang tetap memastikan kita selalu bisa menemukan dan memperbarui dokumen konfigurasi.
SYSTEM_CONFIG_ID = "system_main_config"


# --- Helper untuk Serializer & Validator Objek Money dengan Pydantic ---

def money_validator(v) -> Money:
    """Mengubah angka (int/float) menjadi objek Money saat data dimuat (validasi)."""
    if isinstance(v, Money):
        return v
    if isinstance(v, (int, float)):
        return Money(v, IDR)
    raise ValueError("Nilai untuk saldo harus berupa angka atau objek Money.")

def money_serializer(m: Money) -> float:
    """Mengubah objek Money menjadi representasi float saat diserialisasi."""
    return float(m.amount)

def datetime_serializer(dt: datetime.datetime) -> str:
    """Mengubah objek datetime menjadi string format 'YYYY-MM-DD HH:MM:SS'."""
    return dt.strftime('%Y-%m-%d %H:%M:%S')



# Membuat alias tipe kustom dua arah untuk Pydantic:
# - BeforeValidator: Mengubah angka dari JSON -> objek Money (saat membaca).
# - PlainSerializer: Mengubah objek Money -> float untuk disimpan ke JSON (saat menulis).
JsonSafeMoney = Annotated[
    Money,
    BeforeValidator(money_validator),
    PlainSerializer(money_serializer)
]

JsonSafeDatetime = Annotated[
    datetime.datetime, PlainSerializer(datetime_serializer)
]

# ==============================================================================
# === BLOK 2: MODEL DATA DENGAN PYDANTIC ===
# ==============================================================================
# Tujuan: Mendefinisikan struktur data aplikasi menggunakan Pydantic BaseModel.
# Pydantic menyediakan validasi data, konversi tipe, dan serialisasi/deserialisasi otomatis.

class ItemKeranjang(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    produk_id: str
    nama_produk: str
    harga_satuan: JsonSafeMoney
    jumlah: int

    @property
    def subtotal(self) -> JsonSafeMoney:
        """Menghitung subtotal untuk item ini (harga * jumlah)."""
        return self.harga_satuan * self.jumlah

class TransaksiBank(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id_sumber: str
    user_id_tujuan: Optional[str] = None
    jenis_transaksi: str
    jumlah: JsonSafeMoney
    keterangan: str
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.now)
    saldo_akhir_sumber: JsonSafeMoney
    saldo_akhir_tujuan: Optional[JsonSafeMoney] = None

class PesananToko(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    items_pesanan: List[ItemKeranjang]
    total_harga: JsonSafeMoney
    metode_pembayaran: str = "Bank Novi Mart"
    status_pesanan: str = "Selesai"
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.now)

class Pengguna(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    password_hash: str
    pin_hash: Optional[str] = None
    peran: str
    nama_lengkap: Optional[str] = ""
    email: Optional[EmailStr] = None
    saldo_bank: JsonSafeMoney = Money(0, IDR)
    riwayat_transaksi_bank_ids: List[str] = []
    riwayat_pesanan_toko_ids: List[str] = []
    gagal_login_count: int = 0
    akun_terkunci_hingga: Optional[datetime.datetime] = None
    dibuat_pada: JsonSafeDatetime = Field(default_factory=datetime.datetime.now)

    def verifikasi_password(self, password: str) -> bool:
        """Memverifikasi password menggunakan Passlib."""
        return pwd_context.verify(password, self.password_hash)

    def verifikasi_pin(self, pin: str) -> bool:
        """Memverifikasi PIN Bank menggunakan Passlib."""
        return pwd_context.verify(pin, self.pin_hash) if self.pin_hash else False

    def set_pin(self, pin_baru: str):
        """Mengatur atau mengubah PIN Bank (membuat hash baru)."""
        self.pin_hash = pwd_context.hash(pin_baru)

class Produk(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    nama: str
    harga: JsonSafeMoney
    stok: int
    kategori: str
    deskripsi: str = ""
    dibuat_pada: JsonSafeDatetime = Field(default_factory=datetime.datetime.now)
    diperbarui_pada: JsonSafeDatetime = Field(default_factory=datetime.datetime.now)

# Kelas Keranjang Belanja (berbasis memori selama sesi pengguna login)
class KeranjangBelanja:
    def __init__(self):
        self.items: dict[str, ItemKeranjang] = {}

    def tambah_item(self, produk: Produk, jumlah: int):
        """Menambahkan jumlah produk ke keranjang atau menambah item baru."""
        if jumlah <= 0: return

        item_yang_ada = self.items.get(produk.id)
        if item_yang_ada:
            item_yang_ada.jumlah += jumlah
        else:
            item_baru = ItemKeranjang(
                produk_id=produk.id,
                nama_produk=produk.nama,
                harga_satuan=produk.harga,
                jumlah=jumlah
            )
            self.items[produk.id] = item_baru

    def hapus_item(self, produk_id: str) -> bool:
        """Menghapus item dari keranjang berdasarkan ID produk."""
        if produk_id in self.items:
            del self.items[produk_id]
            return True
        return False

    def ubah_jumlah_item(self, produk_id: str, jumlah_baru: int) -> bool:
        """Mengubah jumlah item di keranjang berdasarkan ID produk."""
        if produk_id in self.items:
            if jumlah_baru > 0:
                self.items[produk_id].jumlah = jumlah_baru
            elif jumlah_baru == 0:
                self.hapus_item(produk_id)
            else:
                print("Jumlah tidak boleh negatif.")
                return False
            return True
        return False

    @property
    def total_belanja(self) -> JsonSafeMoney:
        """Menghitung total harga dari semua item di keranjang."""
        total = Money(0, IDR)
        for item in self.items.values():
            total += item.subtotal
        return total

    def kosongkan_keranjang(self):
        """Menghapus semua item dari keranjang belanja."""
        self.items.clear()

    def dapatkan_semua_item_dict(self) -> List[dict]:
        """Mengembalikan list dictionary dari semua item di keranjang untuk disimpan ke database."""
        return [item.model_dump(mode='json') for item in self.items.values()]


# ==============================================================================
# === BLOK 3: FUNGSI AKSES DATA DENGAN TINYDB ===
# ==============================================================================
# Tujuan: Menyediakan fungsi-fungsi untuk berinteraksi dengan TinyDB.
# Fungsi-fungsi ini mengambil/menyimpan objek Pydantic atau dictionary.

def dapatkan_pengguna_by_id(user_id: str) -> Optional[Pengguna]:
    """Mengambil data pengguna dari TinyDB berdasarkan ID unik."""
    hasil = db.table('pengguna').get(PenggunaQuery.id == user_id)
    return Pengguna(**hasil) if hasil else None

def dapatkan_pengguna_by_username(username: str) -> Optional[Pengguna]:
    """Mengambil data pengguna dari TinyDB berdasarkan username (case-insensitive)."""
    # Menggunakan metode .test() yang eksplisit untuk perbandingan kustom yang aman.
    # Ini mencegah error interpretasi dan aman terhadap data non-string.
    hasil = db.table('pengguna').get(
        PenggunaQuery.username.test(lambda db_val: isinstance(db_val, str) and db_val.lower() == username.lower())
    )
    # Membuat objek Pengguna jika hasil ditemukan, jika tidak mengembalikan None.
    return Pengguna(**hasil) if hasil else None

def simpan_pengguna(pengguna: Pengguna):
    """Menyimpan atau memperbarui data pengguna di TinyDB."""
    data_dict = pengguna.model_dump(mode='json')
    db.table('pengguna').upsert(data_dict, PenggunaQuery.id == pengguna.id)


def dapatkan_produk_by_id(produk_id: str) -> Optional[Produk]:
    """Mengambil data produk dari TinyDB berdasarkan ID unik."""
    hasil = db.table('produk').get(ProdukQuery.id == produk_id)
    return Produk(**hasil) if hasil else None

def dapatkan_semua_produk() -> List[Produk]:
    """Mengambil semua data produk dari TinyDB."""
    return [Produk(**p) for p in db.table('produk').all()]

def simpan_produk(produk: Produk):
    """Menyimpan atau memperbarui data produk di TinyDB."""
    produk.diperbarui_pada = datetime.datetime.now()
    data_dict = produk.model_dump(mode='json')
    db.table('produk').upsert(data_dict, ProdukQuery.id == produk.id)

def hapus_produk_by_id(produk_id: str) -> bool:
    """Menghapus produk dari TinyDB berdasarkan ID unik."""
    hapus_count = db.table('produk').remove(ProdukQuery.id == produk_id)
    return hapus_count > 0


def simpan_transaksi_bank(transaksi: TransaksiBank):
    """Menyimpan transaksi bank baru ke TinyDB."""
    data_dict = transaksi.model_dump(mode='json')
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
    db.table('pesanan_toko').insert(data_dict)

def dapatkan_pesanan_toko_by_id(pesanan_id: str) -> Optional[PesananToko]:
    """Mengambil pesanan toko dari TinyDB berdasarkan ID unik."""
    hasil = db.table('pesanan_toko').get(PesananQuery.id == pesanan_id)
    return PesananToko(**hasil) if hasil else None

def dapatkan_semua_pesanan_toko() -> List[PesananToko]:
    """Mengambil semua pesanan toko dari TinyDB."""
    return [PesananToko(**p) for p in db.table('pesanan_toko').all()]


def dapatkan_konfigurasi() -> dict:
    """Mengambil konfigurasi sistem dari TinyDB. Mengembalikan struktur default jika belum ada dan menyimpannya."""
    try:
        config_docs = db.table('konfigurasi').all()
    except Exception as e:
        logger.error(f"Error reading config table: {e}. Initializing default config.")
        config_docs = []

    if not config_docs:
        logger.info(f"System configuration not found. Creating default (ID: {SYSTEM_CONFIG_ID}).")
        default_config = {
            "id": SYSTEM_CONFIG_ID,
            "nama_toko": "Novi Mart",
            "kategori_produk": KATEGORI_PRODUK_DEFAULT.copy(),
            "admin_dibuat": False,
            "setup_selesai": False,
            "maintenance_aktif": False,
            "maintenance_berakhir_pada": None
        }
        try:
            db.table('konfigurasi').truncate()
            db.table('konfigurasi').insert(default_config.copy())
            logger.info("Default configuration inserted into DB.")
        except Exception as e:
            logger.error(f"Failed to insert default config document: {e}")
        return default_config

    else:
        config_data = config_docs[0]
        # Gabungkan data dari DB dengan struktur default untuk memastikan semua field ada.
        merged_config = {
            "id": SYSTEM_CONFIG_ID,
            "nama_toko": "Novi Mart",
            "kategori_produk": KATEGORI_PRODUK_DEFAULT.copy(),
            "admin_dibuat": False,
            "setup_selesai": False,
            "maintenance_aktif": False,
            "maintenance_berakhir_pada": None
        }
        merged_config.update(config_data)
        merged_config["id"] = SYSTEM_CONFIG_ID # Pastikan ID-nya tetap benar.
        return merged_config


def simpan_konfigurasi(config_data: dict):
    """Menyimpan atau memperbarui konfigurasi sistem di TinyDB."""
    # Pastikan ID konstan ada di data sebelum disimpan.
    if "id" not in config_data or config_data["id"] != SYSTEM_CONFIG_ID:
        config_data["id"] = SYSTEM_CONFIG_ID
        logger.warning(f"Configuration data missing or incorrect ID. Assigned {SYSTEM_CONFIG_ID}.")

    try:
        # Gunakan upsert untuk memperbarui atau memasukkan dokumen konfigurasi utama.
        db.table('konfigurasi').upsert(config_data, KonfigurasiQuery.id == SYSTEM_CONFIG_ID)
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")


# ==============================================================================
# === BLOK 4: INISIALISASI DATA AWAL ===
# ==============================================================================
# Tujuan: Memastikan database memiliki data dasar (admin, produk, config) saat pertama kali dijalankan.

def buat_admin_default_jika_perlu(konfigurasi: dict):
    """Membuat akun admin default jika belum ada di database pengguna."""
    # Lakukan pengecekan admin dengan pendekatan dua langkah yang aman.
    # 1. Cari pengguna berdasarkan username.
    calon_admin = dapatkan_pengguna_by_username(ADMIN_USERNAME_DEFAULT)
    # 2. Periksa apakah pengguna ditemukan DAN perannya adalah ADMIN.
    if calon_admin and calon_admin.peran == PERAN_ADMIN_UTAMA:
        admin_exists = True
    else:
        admin_exists = False

    if not admin_exists:
        logger.info(f"Akun admin default '{ADMIN_USERNAME_DEFAULT}' tidak ditemukan. Membuat akun baru.")
        try:
            admin_password_hash = pwd_context.hash(ADMIN_PASSWORD_DEFAULT)
            admin_pin_hash = pwd_context.hash(ADMIN_PIN_DEFAULT)
            admin_baru = Pengguna(
                username=ADMIN_USERNAME_DEFAULT,
                password_hash=admin_password_hash,
                pin_hash=admin_pin_hash,
                peran=PERAN_ADMIN_UTAMA,
                nama_lengkap="Administrator Utama",
                email="admin@Novimart.system",
                saldo_bank=Money(0, IDR)
            )
            simpan_pengguna(admin_baru)
            konfigurasi["admin_dibuat"] = True
            logger.info(f"Akun admin default '{ADMIN_USERNAME_DEFAULT}' berhasil dibuat.")
        except ValidationError as e:
            logger.error(f"Gagal membuat model admin default karena validasi Pydantic: {e}")
        except Exception as e:
            logger.error(f"Error tak terduga saat membuat admin default: {e}")
    else:
        konfigurasi["admin_dibuat"] = True
        logger.info(f"Akun admin default '{ADMIN_USERNAME_DEFAULT}' sudah ada.")
    # Perubahan pada `konfigurasi` akan disimpan oleh fungsi pemanggil.


def inisialisasi_database_jika_perlu():
    """Memeriksa apakah database perlu diinisialisasi dan menjalankan setup awal."""
    konfigurasi = dapatkan_konfigurasi()
    if konfigurasi.get("setup_selesai", False):
        logger.info("Database sudah diinisialisasi. Melewatkan setup.")
        buat_admin_default_jika_perlu(konfigurasi)
        simpan_konfigurasi(konfigurasi)
        return

    logger.info("Melakukan inisialisasi awal database.")

    buat_admin_default_jika_perlu(konfigurasi)

    # Buat Produk Contoh jika tabel 'produk' masih kosong.
    # DIUBAH: Menggunakan len(db.table('produk')) untuk efisiensi
    if len(db.table('produk')) == 0:
        logger.info("Menambahkan produk default dari konstanta global.")
        
        # DIUBAH: Tidak ada lagi definisi list di sini.
        # Loop sekarang menggunakan konstanta global 'PRODUK_DEFAULT'.
        for p_data in PRODUK_DEFAULT:
            try:
                # Logika di dalam loop tetap sama persis
                produk_baru = Produk(
                    nama=p_data['nama'],
                    harga=Money(p_data['harga'], IDR), # Perhatikan: Pydantic akan menangani ini jika Anda menggunakan Produk(**p_data)
                    stok=p_data['stok'],
                    kategori=p_data['kategori'],
                    deskripsi=p_data['deskripsi']
                )
                simpan_produk(produk_baru)
            except ValidationError as e:
                logger.error(f"Gagal membuat model produk default '{p_data['nama']}': {e}")
            except Exception as e:
                logger.error(f"Error saat menambahkan produk default '{p_data['nama']}': {e}")

        # Simpan kategori produk default ke dalam konfigurasi.
        if not konfigurasi.get("kategori_produk"):
            konfigurasi["kategori_produk"] = KATEGORI_PRODUK_DEFAULT.copy()
            logger.info("Menambahkan kategori produk default ke konfigurasi.")

    # Tandai bahwa proses setup awal telah selesai.
    konfigurasi["setup_selesai"] = True
    simpan_konfigurasi(konfigurasi)
    logger.info("Inisialisasi database selesai.")

# ==============================================================================
# === BLOK 5: FUNGSI UTILITAS UMUM ===
# ==============================================================================
# Fungsi-fungsi bantu umum yang digunakan di seluruh program.

def countdown_with_cancel(duration: int, prompt_message: str) -> bool:
    """
    Menampilkan hitung mundur (countdown) dan menunggu input pembatalan ('n') secara non-blocking.

    Args:
        duration (int): Durasi hitung mundur dalam detik.
        prompt_message (str): Pesan yang ditampilkan di atas countdown.

    Returns:
        bool: True jika countdown selesai, False jika dibatalkan oleh pengguna.
    """
    
    print(prompt_message)
    print("Tekan (n) untuk membatalkan...")

    # --- Logika untuk Windows ---
    if os.name == 'nt':
        import msvcrt
        for i in range(duration, 0, -1):
            # \r (carriage return) akan memindahkan kursor ke awal baris
            # end='' mencegah print membuat baris baru
            print(f"\rMelanjutkan otomatis dalam {i} detik...  ", end='')
            
            # Cek input selama 1 detik tanpa memblokir total
            start_time = time.time()
            while time.time() - start_time < 1:
                if msvcrt.kbhit(): # Apakah ada tombol yang ditekan?
                    char = msvcrt.getch().decode(errors='ignore').lower()
                    if char == 'n':
                        print("\n\nAuto-login dibatalkan oleh pengguna.")
                        return False # Dibatalkan
                time.sleep(0.1) # Jeda singkat agar CPU tidak bekerja terlalu keras

        print("\rMelanjutkan proses auto-login...             ") # Timpa pesan countdown terakhir
        return True # Selesai tanpa pembatalan

    # --- Logika untuk Linux/macOS ---
    elif os.name == 'posix':
        import tty
        import termios
        import select

        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setcbreak(sys.stdin.fileno()) # Ubah mode terminal
            for i in range(duration, 0, -1):
                print(f"\rMelanjutkan otomatis dalam {i} detik...  ", end='')
                sys.stdout.flush() # Pastikan pesan langsung tampil
                
                # Menunggu input selama 1 detik
                # Jika ada input, r akan berisi [sys.stdin]
                r, _, _ = select.select([sys.stdin], [], [], 1)
                
                if r:
                    char = sys.stdin.read(1).lower()
                    if char == 'n':
                        print("\n\nAuto-login dibatalkan oleh pengguna.")
                        return False # Dibatalkan

            print("\rMelanjutkan proses auto-login...             ")
            return True # Selesai tanpa pembatalan
        finally:
            # SANGAT PENTING: Kembalikan terminal ke pengaturan semula
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    # --- Logika Fallback (Cadangan) untuk OS lain ---
    else:
        print("Pembatalan interaktif tidak didukung di OS ini.")
        for i in range(duration, 0, -1):
            print(f"\rMelanjutkan otomatis dalam {i} detik...  ", end='')
            time.sleep(1)
        print("\rMelanjutkan proses auto-login...             ")
        return True

def bersihkan_layar():
    """Membersihkan layar konsol."""
    os.system('cls' if os.name == 'nt' else 'clear')

def format_rupiah(angka_atau_money) -> str:
    """Mengubah angka (int/float) atau objek Money menjadi format mata uang Rupiah."""
    if isinstance(angka_atau_money, Money):
        amount = angka_atau_money.amount
    elif isinstance(angka_atau_money, (int, float)):
        amount = angka_atau_money
    else:
        return "Rp0"

    # Format angka dengan separator ribuan (titik) dan tanpa desimal.
    return f"Rp{int(amount):,.0f}".replace(",", ".")

def generate_id_unik() -> str:
    """Menghasilkan ID unik menggunakan UUID4."""
    return str(uuid.uuid4())

@contextlib.contextmanager
def sembunyikan_stderr():
    """Context manager untuk membungkam aliran stderr sementara."""
    original_stderr = sys.stderr
    # Mengarahkan stderr ke "null device" (lubang hitam sistem operasi)
    devnull = open(os.devnull, 'w')
    sys.stderr = devnull
    try:
        yield
    finally:
        # Selalu pastikan aliran stderr dikembalikan seperti semula
        sys.stderr = original_stderr
        devnull.close()

def cek_maintenance_dan_tampilkan_pesan():
    """
    Memeriksa apakah mode maintenance aktif. Jika ya, tampilkan pesan blokade.
    Mengembalikan True jika maintenance aktif (blokir aksi), False jika tidak.
    """
    konfigurasi = dapatkan_konfigurasi()
    if konfigurasi.get("maintenance_aktif", False):
        berakhir_str = konfigurasi.get("maintenance_berakhir_pada")
        if isinstance(berakhir_str, str):
            try:
                berakhir_dt = datetime.datetime.strptime(berakhir_str, '%Y-%m-%d %H:%M:%S')
                if datetime.datetime.now() < berakhir_dt:
                    # Maintenance aktif dan belum kedaluwarsa
                    bersihkan_layar()
                    print_header("Sistem Dalam Perbaikan")
                    print("Mohon maaf, sistem sedang dalam proses maintenance.")
                    print(f"Silakan coba lagi setelah pukul: {berakhir_dt.strftime('%H:%M:%S')}")
                    input_enter_lanjut()
                    return True # <-- Penting: Mengindikasikan untuk memblokir
            except ValueError:
                return False # Format tanggal salah, anggap tidak aktif
    return False # <-- Maintenance tidak aktif

def input_valid(prompt, tipe_data=str, validasi_regex=None, pesan_error_regex=None, sembunyikan_input=False, opsional=False, default_value=None):
    """Meminta input dari pengguna dengan validasi tipe data, regex, dan opsi tambahan."""
    while True:
        try:
            if sembunyikan_input:
                import getpass
                try:
                    nilai_input_str = getpass.getpass(prompt)
                except Exception as e:
                    logger.warning(f"Gagal menggunakan getpass: {e}. Menggunakan input biasa (tidak disembunyikan).")
                    nilai_input_str = input(prompt)
            else:
                nilai_input_str = input(prompt)

            if opsional and not nilai_input_str.strip():
                return default_value

            if tipe_data == int:
                nilai_konversi = int(nilai_input_str)
            elif tipe_data == float:
                nilai_konversi = float(nilai_input_str)
            else:
                nilai_konversi = nilai_input_str

            if validasi_regex:
                if not re.fullmatch(validasi_regex, str(nilai_konversi)):
                    print(pesan_error_regex or "Format input tidak valid.")
                    continue

            return nilai_konversi
        except ValueError:
            print(f"Input tidak valid. Harap masukkan tipe data {tipe_data.__name__}.")
        except Exception as e:
            logger.error(f"Kesalahan tak terduga saat input_valid: {e}")
            print(f"Terjadi kesalahan saat menerima input: {e}")


def input_pilihan_menu(maks_pilihan: int, min_pilihan: int = 1, prompt_pesan: str = "Masukkan pilihan Anda: ") -> int:
    """Meminta input pilihan menu dari pengguna dan memastikan pilihan berada dalam rentang yang valid."""
    while True:
        try:
            pilihan = int(input(prompt_pesan))
            if min_pilihan <= pilihan <= maks_pilihan:
                return pilihan
            else:
                print(f"Pilihan tidak valid. Harap masukkan angka antara {min_pilihan} dan {maks_pilihan}.")
        except ValueError:
            print("Input tidak valid. Harap masukkan angka.")
        except Exception as e:
            logger.error(f"Kesalahan tak terduga saat input_pilihan_menu: {e}")
            print(f"Terjadi kesalahan saat memproses pilihan: {e}")


def print_header(judul: str, panjang_total: int = 70):
    """Mencetak header bergaris, dengan notifikasi maintenance real-time untuk admin."""
    print("=" * panjang_total)
    print(judul.center(panjang_total))

    # --- Logika Notifikasi Maintenance Real-time untuk Admin ---
    # Cek hanya jika ada pengguna yang login dan perannya adalah ADMIN
    if pengguna_login_saat_ini and pengguna_login_saat_ini.peran == PERAN_ADMIN:
        konfigurasi = dapatkan_konfigurasi()
        
        # Cek jika flag maintenance di konfigurasi aktif
        if konfigurasi.get("maintenance_aktif", False):
            berakhir_str = konfigurasi.get("maintenance_berakhir_pada")
            if isinstance(berakhir_str, str):
                try:
                    berakhir_dt = datetime.datetime.strptime(berakhir_str, '%Y-%m-%d %H:%M:%S')
                    sisa_waktu = berakhir_dt - datetime.datetime.now()
                    
                    # Hanya tampilkan notifikasi jika waktu maintenance belum habis
                    if sisa_waktu.total_seconds() > 0:
                        # Hitung sisa menit, bulatkan ke atas agar lebih intuitif
                        menit_sisa = int(sisa_waktu.total_seconds() // 60) + 1 
                        
                        pesan_notif = f"MAINTENANCE AKTIF (Berakhir dalam ~{menit_sisa} menit)"
                        print(pesan_notif.center(panjang_total))
                        
                except ValueError:
                    # Jika format tanggal di DB salah, abaikan saja notifikasi
                    pass 
    # --------------------------------------------------------
    print("=" * panjang_total)

def print_separator_line(panjang: int = 70, char: str = "-"):
    """Mencetak garis pemisah horizontal di konsol."""
    print(char * panjang)

def input_enter_lanjut():
    """Menunggu pengguna menekan tombol Enter untuk melanjutkan."""
    input("\nTekan Enter untuk melanjutkan...")


# ==============================================================================
# === BLOK 6: FUNGSI AUTENTIKASI & MANAJEMEN AKUN ===
# ==============================================================================
# Fungsi-fungsi untuk registrasi, login, logout pengguna, serta manajemen PIN.

pengguna_login_saat_ini: Optional[Pengguna] = None
keranjang_belanja_global = KeranjangBelanja()


def registrasi_pengguna_baru():
    """Mendaftarkan pengguna baru ke dalam sistem."""
    #  --- BLOKADE MAINTENANCE ---
    if cek_maintenance_dan_tampilkan_pesan():
        return  #---> Langsung keluar dari fungsi, batalkan registrasi
    # <<<<---------->>>>
    bersihkan_layar(); print_header("Registrasi Akun Baru Novi Mart & Bank")

    username = input_valid("Username baru (3-20 karakter, alfanumerik & underscore): ",
                        validasi_regex=r"^[a-zA-Z0-9_]{3,20}$",
                        pesan_error_regex="Username tidak valid. Harus 3-20 karakter alfanumerik atau underscore.")
    if dapatkan_pengguna_by_username(username):
        print(f"Username '{username}' sudah digunakan. Harap pilih username lain."); input_enter_lanjut(); return

    password_regex = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&_])[A-Za-z\d@$!%*?&_]{8,30}$"
    password_msg = "Password (min 8, huruf besar, kecil, angka, simbol @$!%*?&_):"
    password = input_valid(password_msg, sembunyikan_input=True, validasi_regex=password_regex,
                            pesan_error_regex="Password tidak memenuhi syarat keamanan.")
    if password != input_valid("Konfirmasi password: ", sembunyikan_input=True):
        print("Password tidak cocok. Registrasi dibatalkan."); input_enter_lanjut(); return

    pin_bank = input_valid("Buat 6 digit PIN Bank: ", sembunyikan_input=True, validasi_regex=r"^\d{6}$", pesan_error_regex="PIN Bank harus 6 digit angka.")
    if pin_bank != input_valid("Konfirmasi PIN Bank: ", sembunyikan_input=True):
        print("PIN Bank tidak cocok. Registrasi dibatalkan."); input_enter_lanjut(); return

    nama_lengkap = input_valid("Nama lengkap (opsional): ", opsional=True, default_value="")
    email_input_str = input_valid("Email (opsional): ", opsional=True, default_value="")
    email = email_input_str if email_input_str.strip() else None
    if email and not re.fullmatch(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        print("Format email tidak valid. Email tidak disimpan."); email = None

    try:
        pengguna_baru = Pengguna(
            username=username,
            password_hash=pwd_context.hash(password),
            pin_hash=pwd_context.hash(pin_bank),
            peran=PERAN_PELANGGAN,
            nama_lengkap=nama_lengkap,
            email=email,
            saldo_bank=Money(0, IDR)
        )
        simpan_pengguna(pengguna_baru)
        logger.info(f"Pengguna baru '{username}' (ID: {pengguna_baru.id}) berhasil diregistrasi.")
        print(f"\nRegistrasi berhasil! Akun '{username}' telah dibuat. Silakan login.");
    except ValidationError as e:
        logger.error(f"Gagal membuat objek Pengguna karena validasi Pydantic: {e}")
        print(f"Gagal membuat akun karena data tidak valid: {e}")
    except Exception as e:
        logger.error(f"Error tak terduga saat registrasi pengguna: {e}")
        print(f"Terjadi kesalahan saat registrasi: {e}")

    input_enter_lanjut()


def login_pengguna():
    """Memproses login pengguna, verifikasi kredensial, dan cek status kunci akun."""
    global pengguna_login_saat_ini
    bersihkan_layar(); print_header("Login Novi Mart & Bank")

    username = input_valid("Username: ")
    password = input_valid("Password: ", sembunyikan_input=True)

    pengguna = dapatkan_pengguna_by_username(username)

    if pengguna:
        #  ----BLOKADE MAINTENANCE----
        # Cek maintenance HANYA jika pengguna yang mencoba login adalah PELANGGAN
        if pengguna.peran == PERAN_PELANGGAN and cek_maintenance_dan_tampilkan_pesan():
            return # Keluar dari fungsi, batalkan login untuk pelanggan
        #  ----<<<<>>>>>------
        if pengguna.akun_terkunci_hingga and pengguna.akun_terkunci_hingga > datetime.datetime.now():
            sisa_waktu = pengguna.akun_terkunci_hingga - datetime.datetime.now()
            sisa_waktu_str = str(sisa_waktu).split('.')[0]
            print(f"Akun terkunci. Silakan coba lagi dalam {sisa_waktu_str}.")
            logger.warning(f"Percobaan login ke akun terkunci: {username}")
            input_enter_lanjut(); return
        
                # Verifikasi password menggunakan Passlib, dengan membungkam stderr
        with sembunyikan_stderr():
            verifikasi_berhasil = pengguna.verifikasi_password(password)

        if verifikasi_berhasil:
            # Jika password benar:
            pengguna_login_saat_ini = pengguna
            pengguna.gagal_login_count = 0
            pengguna.akun_terkunci_hingga = None
            simpan_pengguna(pengguna)
            logger.info(f"Pengguna '{username}' (Peran: {pengguna.peran}) berhasil login.")
            print(f"\nLogin berhasil! Selamat datang, {pengguna.nama_lengkap or pengguna.username}!")
        else:
            pengguna.gagal_login_count += 1
            if pengguna.gagal_login_count >= BATAS_PERCOBAAN_LOGIN:
                pengguna.akun_terkunci_hingga = datetime.datetime.now() + datetime.timedelta(minutes=DURASI_KUNCI_AKUN_MENIT)
                logger.warning(f"Akun '{username}' terkunci karena gagal login {BATAS_PERCOBAAN_LOGIN} kali.")
                print(f"Password salah. Akun Anda terkunci selama {DURASI_KUNCI_AKUN_MENIT} menit.")
            else:
                sisa_percobaan = BATAS_PERCOBAAN_LOGIN - pengguna.gagal_login_count
                print(f"Password salah. Sisa percobaan: {sisa_percobaan}.")
            simpan_pengguna(pengguna)
    else:
        print("Username tidak ditemukan.")
        logger.warning(f"Gagal login: Username '{username}' tidak ditemukan.")

    input_enter_lanjut()


def logout_pengguna():
    """Memproses logout pengguna yang sedang login."""
    print_separator_line()
    global pengguna_login_saat_ini, keranjang_belanja_global

    if pengguna_login_saat_ini:
        logger.info(f"Pengguna '{pengguna_login_saat_ini.username}' logout.")
        print(f"Anda telah logout, {pengguna_login_saat_ini.username}. Sampai jumpa!")
        pengguna_login_saat_ini = None
        keranjang_belanja_global.kosongkan_keranjang()
    else:
        print("Tidak ada pengguna yang sedang login.")
    print_separator_line()
    input_enter_lanjut()


def minta_pin_transaksi(pengguna_obj: Pengguna, keterangan_aksi: str = "untuk transaksi ini") -> bool:
    """Meminta dan memverifikasi PIN Bank untuk otorisasi aksi."""
    if not pengguna_obj.pin_hash:
        print("PIN Bank belum diatur untuk akun ini. Silakan atur di menu Pengaturan Akun."); return False

    for i in range(3):
        pin_input = input_valid(f"Masukkan 6 digit PIN Bank {keterangan_aksi} (coba {i+1}/3): ",
                                sembunyikan_input=True,
                                validasi_regex=r"^\d{6}$",
                                pesan_error_regex="PIN Bank harus 6 digit angka.")
        if pengguna_obj.verifikasi_pin(pin_input):
            return True
        else:
            print("PIN salah.")

    print("Terlalu banyak percobaan PIN salah. Aksi dibatalkan.")
    logger.warning(f"Gagal verifikasi PIN untuk '{pengguna_obj.username}' setelah 3 kali percobaan.")
    return False


# ==============================================================================
# === BLOK 7: FUNGSI MODUL BANK ===
# ==============================================================================
# Fungsi-fungsi untuk layanan perbankan: lihat saldo, deposit, withdraw, transfer, riwayat.

def lihat_saldo_bank():
    """Menampilkan saldo bank pengguna yang sedang login."""
    bersihkan_layar(); print_header("Informasi Saldo Bank")
    print(f"Saldo Anda saat ini: {format_rupiah(pengguna_login_saat_ini.saldo_bank)}")
    input_enter_lanjut()


def deposit_bank():
    """Memproses deposit saldo ke akun bank pengguna."""
    global pengguna_login_saat_ini
    bersihkan_layar(); print_header("Deposit Saldo Bank")

    try:
        jumlah_float = input_valid("Jumlah deposit: Rp", tipe_data=float)
        if jumlah_float <= 0:
            print("Jumlah deposit harus lebih besar dari 0."); input_enter_lanjut(); return

        jumlah_deposit = Money(jumlah_float, IDR)
        saldo_awal = pengguna_login_saat_ini.saldo_bank
        pengguna_login_saat_ini.saldo_bank += jumlah_deposit

        transaksi = TransaksiBank(
            user_id_sumber=pengguna_login_saat_ini.id,
            jenis_transaksi="Deposit",
            jumlah=jumlah_deposit,
            keterangan="Setoran ke akun",
            saldo_akhir_sumber=pengguna_login_saat_ini.saldo_bank
        )

        pengguna_login_saat_ini.riwayat_transaksi_bank_ids.append(transaksi.id)
        simpan_transaksi_bank(transaksi)
        simpan_pengguna(pengguna_login_saat_ini)

        logger.info(f"Pengguna '{pengguna_login_saat_ini.username}' deposit {format_rupiah(jumlah_deposit)}. Saldo: {format_rupiah(saldo_awal)} -> {format_rupiah(pengguna_login_saat_ini.saldo_bank)}")
        print(f"\nDeposit {format_rupiah(jumlah_deposit)} berhasil. Saldo baru Anda: {format_rupiah(pengguna_login_saat_ini.saldo_bank)}");
    except ValueError:
        print("Input jumlah tidak valid. Harap masukkan angka.");
    except Exception as e:
        logger.error(f"Error saat deposit untuk '{pengguna_login_saat_ini.username}': {e}")
        print(f"Terjadi kesalahan saat deposit: {e}");

    input_enter_lanjut()


def withdraw_bank():
    """Memproses penarikan saldo dari akun bank pengguna."""
    global pengguna_login_saat_ini
    bersihkan_layar(); print_header("Penarikan Saldo Bank")

    try:
        jumlah_float = input_valid("Jumlah penarikan: Rp", tipe_data=float)
        if jumlah_float <= 0:
            print("Jumlah harus lebih besar dari 0."); input_enter_lanjut(); return

        jumlah_tarik = Money(jumlah_float, IDR)

        if jumlah_tarik > pengguna_login_saat_ini.saldo_bank:
            print("Saldo tidak cukup untuk penarikan ini."); input_enter_lanjut(); return

        if not minta_pin_transaksi(pengguna_login_saat_ini, "untuk penarikan"):
            input_enter_lanjut(); return

        saldo_awal = pengguna_login_saat_ini.saldo_bank
        pengguna_login_saat_ini.saldo_bank -= jumlah_tarik

        transaksi = TransaksiBank(
            user_id_sumber=pengguna_login_saat_ini.id,
            jenis_transaksi="Withdraw",
            jumlah=jumlah_tarik,
            keterangan="Penarikan dari akun",
            saldo_akhir_sumber=pengguna_login_saat_ini.saldo_bank
        )

        pengguna_login_saat_ini.riwayat_transaksi_bank_ids.append(transaksi.id)
        simpan_transaksi_bank(transaksi)
        simpan_pengguna(pengguna_login_saat_ini)

        logger.info(f"Pengguna '{pengguna_login_saat_ini.username}' tarik {format_rupiah(jumlah_tarik)}. Saldo: {format_rupiah(saldo_awal)} -> {format_rupiah(pengguna_login_saat_ini.saldo_bank)}")
        print(f"\nPenarikan {format_rupiah(jumlah_tarik)} berhasil. Saldo baru Anda: {format_rupiah(pengguna_login_saat_ini.saldo_bank)}");
    except ValueError:
        print("Input jumlah tidak valid. Harap masukkan angka.");
    except Exception as e:
        logger.error(f"Error saat withdraw untuk '{pengguna_login_saat_ini.username}': {e}")
        print(f"Terjadi kesalahan saat penarikan: {e}");

    input_enter_lanjut()


def transfer_dana_bank():
    """Memproses transfer dana antar pengguna bank."""
    global pengguna_login_saat_ini
    bersihkan_layar(); print_header("Transfer Dana")

    try:
        username_tujuan = input_valid("Username penerima: ")
        if username_tujuan.lower() == pengguna_login_saat_ini.username.lower():
            print("Tidak bisa mentransfer dana ke akun Anda sendiri."); input_enter_lanjut(); return

        pengguna_tujuan = dapatkan_pengguna_by_username(username_tujuan)
        if not pengguna_tujuan:
            print(f"Pengguna '{username_tujuan}' tidak ditemukan."); input_enter_lanjut(); return

        print(f"Anda akan mentransfer ke: {pengguna_tujuan.nama_lengkap or pengguna_tujuan.username} ({pengguna_tujuan.username})")

        jumlah_float = input_valid("Jumlah transfer: Rp", tipe_data=float)
        if jumlah_float <= 0:
            print("Jumlah transfer harus lebih besar dari 0."); input_enter_lanjut(); return

        jumlah_transfer = Money(jumlah_float, IDR)
        if jumlah_transfer > pengguna_login_saat_ini.saldo_bank:
            print("Saldo Anda tidak cukup untuk transfer ini."); input_enter_lanjut(); return

        if not minta_pin_transaksi(pengguna_login_saat_ini, f"untuk transfer ke {pengguna_tujuan.username}"):
            input_enter_lanjut(); return

        print("\nMemproses transfer...")
        time.sleep(2)

        saldo_awal_sumber = pengguna_login_saat_ini.saldo_bank
        saldo_awal_tujuan = pengguna_tujuan.saldo_bank

        pengguna_login_saat_ini.saldo_bank -= jumlah_transfer
        pengguna_tujuan.saldo_bank += jumlah_transfer

        transaksi = TransaksiBank(
            user_id_sumber=pengguna_login_saat_ini.id,
            user_id_tujuan=pengguna_tujuan.id,
            jenis_transaksi="Transfer",
            jumlah=jumlah_transfer,
            keterangan=f"Transfer ke {pengguna_tujuan.username}",
            saldo_akhir_sumber=pengguna_login_saat_ini.saldo_bank,
            saldo_akhir_tujuan=pengguna_tujuan.saldo_bank
        )

        pengguna_login_saat_ini.riwayat_transaksi_bank_ids.append(transaksi.id)
        pengguna_tujuan.riwayat_transaksi_bank_ids.append(transaksi.id)

        simpan_transaksi_bank(transaksi)
        simpan_pengguna(pengguna_login_saat_ini)
        simpan_pengguna(pengguna_tujuan)

        logger.info(f"Transfer {format_rupiah(jumlah_transfer)} dari '{pengguna_login_saat_ini.username}' ke '{pengguna_tujuan.username}'.")
        print(f"\nTransfer {format_rupiah(jumlah_transfer)} ke {pengguna_tujuan.username} berhasil.")
        print(f"Saldo baru Anda: {format_rupiah(pengguna_login_saat_ini.saldo_bank)}")
    except ValueError:
        print("Input jumlah tidak valid. Harap masukkan angka.");
    except Exception as e:
        logger.error(f"Error saat transfer dari '{pengguna_login_saat_ini.username}': {e}")
        print(f"Terjadi kesalahan saat transfer: {e}");

    input_enter_lanjut()


def lihat_riwayat_transaksi_bank():
    """Menampilkan riwayat transaksi bank untuk pengguna yang sedang login."""
    bersihkan_layar(); print_header(f"Riwayat Transaksi Bank - {pengguna_login_saat_ini.username}")

    list_transaksi_obj = [dapatkan_transaksi_bank_by_id(trx_id)
                        for trx_id in pengguna_login_saat_ini.riwayat_transaksi_bank_ids
                        if dapatkan_transaksi_bank_by_id(trx_id) is not None]

    if not list_transaksi_obj:
        print("Belum ada riwayat transaksi."); input_enter_lanjut(); return

    list_transaksi_obj.sort(key=lambda t: t.timestamp, reverse=True)

    print_separator_line(120)
    print(f"{'Tanggal':<26} | {'Jenis':<18} | {'Keterangan':<35} | {'Jumlah':<20} | {'Saldo Akhir':<20}")
    print_separator_line(120)

    for trx in list_transaksi_obj:
        jenis_tampil = trx.jenis_transaksi
        keterangan_tampil = trx.keterangan

        if trx.jenis_transaksi == "Transfer":
            if trx.user_id_sumber == pengguna_login_saat_ini.id:
                jenis_tampil = "Transfer Keluar"
                jumlah_rp = f"- {format_rupiah(trx.jumlah)}"
                saldo_akhir_rp = format_rupiah(trx.saldo_akhir_sumber)
                penerima = dapatkan_pengguna_by_id(trx.user_id_tujuan)
                keterangan_tampil = f"Ke: {penerima.username if penerima else 'N/A'}"
            else:
                jenis_tampil = "Transfer Masuk"
                jumlah_rp = f"+ {format_rupiah(trx.jumlah)}"
                saldo_akhir_rp = format_rupiah(trx.saldo_akhir_tujuan)
                pengirim = dapatkan_pengguna_by_id(trx.user_id_sumber)
                keterangan_tampil = f"Dari: {pengirim.username if pengirim else 'N/A'}"
        else:
            jumlah_rp = f"+ {format_rupiah(trx.jumlah)}" if jenis_tampil == "Deposit" else f"- {format_rupiah(trx.jumlah)}"
            saldo_akhir_rp = format_rupiah(trx.saldo_akhir_sumber)

        print(f"{trx.timestamp.strftime('%Y-%m-%d %H:%M:%S'):<26} | {jenis_tampil:<18} | {keterangan_tampil[:35]:<35} | {jumlah_rp:<20} | {saldo_akhir_rp:<20}")

    print_separator_line(120)
    input_enter_lanjut()


# ==============================================================================
# === BLOK 8: FUNGSI MODUL TOKO ===
# ==============================================================================
# Fungsi-fungsi untuk fitur toko: lihat produk, kelola keranjang, checkout, riwayat pembelian.

def tampilkan_daftar_produk_toko(filter_kategori: Optional[str] = None, keyword_pencarian: Optional[str] = None, tampilkan_deskripsi: bool = False) -> List[Produk]:
    """Mengambil dan menampilkan produk dari database, dengan opsi filter dan pencarian."""
    semua_produk_obj = dapatkan_semua_produk()
    produk_tampil = []

    if not semua_produk_obj:
        print("Belum ada produk di toko."); return produk_tampil

    for produk in semua_produk_obj:
        lolos = True
        if filter_kategori and produk.kategori.lower() != filter_kategori.lower():
            lolos = False
        if keyword_pencarian and keyword_pencarian.lower() not in produk.nama.lower():
            lolos = False
        if lolos:
            produk_tampil.append(produk)

    if not produk_tampil:
        print("Tidak ada produk sesuai filter/pencarian."); return produk_tampil

    kolom_deskripsi_width = 30
    lebar_total = 110 + (kolom_deskripsi_width + 3 if tampilkan_deskripsi else 0)

    print_separator_line(lebar_total)
    header_str = f"{'No.':<5} | {'ID Produk':<37} | {'Nama Produk':<30} | {'Harga':<15} | {'Stok':<7} | {'Kategori':<20}"
    if tampilkan_deskripsi:
        header_str += f" | {'Deskripsi':<{kolom_deskripsi_width}}"
    print(header_str)
    print_separator_line(lebar_total)

    for i, produk in enumerate(produk_tampil):
        row_str = f"{i+1:<5} | {produk.id:<37} | {produk.nama[:30]:<30} | {format_rupiah(produk.harga):<15} | {str(produk.stok):<7} | {produk.kategori[:20]:<20}"
        if tampilkan_deskripsi:
            row_str += f" | {produk.deskripsi[:kolom_deskripsi_width]:<{kolom_deskripsi_width}}"
        print(row_str)

    print_separator_line(lebar_total)
    return produk_tampil


def pilih_produk_dari_daftar(list_produk_ditampilkan: List[Produk]) -> Optional[Produk]:
    """Meminta pengguna memilih produk dari daftar yang ditampilkan."""
    if not list_produk_ditampilkan:
        return None

    while True:
        try:
            pilihan_no = input_valid("\nNo. produk yang dipilih (0 untuk batal): ", tipe_data=int)
            if pilihan_no == 0:
                return None
            if 1 <= pilihan_no <= len(list_produk_ditampilkan):
                return list_produk_ditampilkan[pilihan_no - 1]
            else:
                print(f"Nomor tidak valid. Harap pilih antara 1 dan {len(list_produk_ditampilkan)}, atau 0.")
        except ValueError:
            print("Input tidak valid. Harap masukkan nomor produk.")
        except Exception as e:
            logger.error(f"Error saat memilih produk: {e}")
            print(f"Terjadi kesalahan saat memproses pilihan: {e}")


def tambah_produk_ke_keranjang_toko():
    """Memungkinkan pengguna mencari/memfilter produk dan menambahkannya ke keranjang."""
    global keranjang_belanja_global

    while True:
        bersihkan_layar(); print_header("Tambah Produk ke Keranjang")
        print("Pilih cara mencari produk:")
        print("1. Tampilkan Semua Produk")
        print("2. Cari Produk berdasarkan Nama")
        print("3. Filter Produk berdasarkan Kategori")
        print("4. Kembali ke Menu Toko")
        print_separator_line()

        aksi = input_pilihan_menu(4)
        produk_ditampilkan: List[Produk] = []

        if aksi == 1:
            bersihkan_layar(); print_header("Semua Produk")
            produk_ditampilkan = tampilkan_daftar_produk_toko(tampilkan_deskripsi=True)
        elif aksi == 2:
            bersihkan_layar(); print_header("Cari Produk")
            keyword = input_valid("Masukkan kata kunci nama produk: ")
            produk_ditampilkan = tampilkan_daftar_produk_toko(keyword_pencarian=keyword, tampilkan_deskripsi=True)
        elif aksi == 3:
            bersihkan_layar(); print_header("Filter Produk")
            kategori_tersedia = dapatkan_konfigurasi().get("kategori_produk", [])
            if not kategori_tersedia:
                print("Belum ada kategori produk."); input_enter_lanjut(); continue

            print("\nKategori Tersedia:");
            [print(f"{i+1}. {kat}") for i, kat in enumerate(kategori_tersedia)]
            print_separator_line()
            try:
                pilihan_kat_idx = input_pilihan_menu(len(kategori_tersedia), prompt_pesan="Pilih nomor kategori: ") - 1
                filter_kat = kategori_tersedia[pilihan_kat_idx]
                bersihkan_layar(); print_header(f"Produk Kategori: {filter_kat}")
                produk_ditampilkan = tampilkan_daftar_produk_toko(filter_kategori=filter_kat, tampilkan_deskripsi=True)
            except (IndexError, Exception) as e:
                logger.error(f"Error saat filter produk: {e}")
                print(f"Terjadi kesalahan saat memfilter produk: {e}"); input_enter_lanjut(); continue
        elif aksi == 4:
            return

        if not produk_ditampilkan:
            input_enter_lanjut(); continue

        produk_dipilih = pilih_produk_dari_daftar(produk_ditampilkan)
        if not produk_dipilih:
            if input_valid("Cari produk lain? (y/n): ", opsional=True, default_value='n').lower() != 'y':
                break
            else:
                continue

        print(f"\nAnda memilih: {produk_dipilih.nama} | Harga: {format_rupiah(produk_dipilih.harga)} | Stok: {produk_dipilih.stok}")
        if produk_dipilih.stok == 0:
            print("Maaf, stok produk ini habis."); input_enter_lanjut(); continue

        try:
            jumlah_beli = input_valid(f"Masukkan jumlah '{produk_dipilih.nama}' yang ingin dibeli: ", tipe_data=int)
            if jumlah_beli <= 0:
                print("Jumlah harus lebih dari 0.")
            elif jumlah_beli > produk_dipilih.stok:
                print(f"Stok tidak cukup (tersedia: {produk_dipilih.stok}).")
            else:
                keranjang_belanja_global.tambah_item(produk_dipilih, jumlah_beli)
                logger.info(f"User '{pengguna_login_saat_ini.username}' menambah {jumlah_beli}x '{produk_dipilih.nama}' ke keranjang.")
                print(f"{jumlah_beli} x '{produk_dipilih.nama}' berhasil ditambahkan ke keranjang.")
        except ValueError:
            print("Input jumlah tidak valid. Harap masukkan angka.")
        except Exception as e:
            logger.error(f"Error saat menambah produk ke keranjang: {e}")
            print(f"Terjadi kesalahan: {e}")

        input_enter_lanjut()
        if input_valid("Tambah produk lain? (y/n): ", opsional=True, default_value='n').lower() != 'y':
            break


def lihat_keranjang_toko():
    """Menampilkan isi keranjang belanja pengguna."""
    bersihkan_layar(); print_header("Isi Keranjang Belanja Anda")

    if not keranjang_belanja_global.items:
        print("Keranjang belanja Anda kosong."); input_enter_lanjut(); return

    print_separator_line(110)
    print(f"{'No.':<5} | {'ID Produk':<37} | {'Nama Produk':<30} | {'Jml':<5} | {'Harga Satuan':<15} | {'Subtotal':<15}")
    print_separator_line(110)

    items_list = list(keranjang_belanja_global.items.values())
    for i, item in enumerate(items_list):
        print(f"{i+1:<5} | {item.produk_id:<37} | {item.nama_produk[:30]:<30} | {str(item.jumlah):<5} | {format_rupiah(item.harga_satuan):<15} | {format_rupiah(item.subtotal):<15}")

    print_separator_line(110)
    print(f"{'Total Belanja:':<95} {format_rupiah(keranjang_belanja_global.total_belanja):<15}")
    print_separator_line(110)
    input_enter_lanjut()


def ubah_item_keranjang_toko():
    """Memungkinkan pengguna mengubah jumlah atau menghapus item di keranjang."""
    global keranjang_belanja_global
    bersihkan_layar(); print_header("Ubah Item Keranjang")

    if not keranjang_belanja_global.items:
        print("Keranjang belanja Anda kosong."); input_enter_lanjut(); return

    print(f"{'No.':<5} | {'Nama Produk':<30} | {'Jml':<5}"); print_separator_line(45)
    items_list = list(keranjang_belanja_global.items.values())
    for i, item in enumerate(items_list):
        print(f"{i+1:<5} | {item.nama_produk[:30]:<30} | {str(item.jumlah):<5}")
    print_separator_line(45)

    pilihan_no = input_valid("No. produk yang akan diubah (0 untuk batal): ", tipe_data=int)
    if pilihan_no == 0:
        return

    if 1 <= pilihan_no <= len(items_list):
        item_dipilih = items_list[pilihan_no - 1]
        print(f"\nItem: {item_dipilih.nama_produk} (Jumlah: {item_dipilih.jumlah})")

        try:
            jumlah_baru = input_valid("Masukkan jumlah baru (0 untuk hapus): ", tipe_data=int)
            produk_asli = dapatkan_produk_by_id(item_dipilih.produk_id)
            if not produk_asli:
                logger.error(f"Produk ID {item_dipilih.produk_id} tidak ditemukan saat ubah keranjang.")
                print("Error: Produk asli tidak ditemukan."); input_enter_lanjut(); return

            if jumlah_baru < 0:
                print("Jumlah tidak boleh negatif.")
            elif jumlah_baru > 0 and jumlah_baru > produk_asli.stok:
                print(f"Stok produk tidak cukup (tersedia: {produk_asli.stok}).")
            else:
                if keranjang_belanja_global.ubah_jumlah_item(item_dipilih.produk_id, jumlah_baru):
                    if jumlah_baru == 0:
                        logger.info(f"User '{pengguna_login_saat_ini.username}' menghapus item '{item_dipilih.nama_produk}' dari keranjang.")
                        print(f"Item '{item_dipilih.nama_produk}' telah dihapus.")
                    else:
                        logger.info(f"User '{pengguna_login_saat_ini.username}' mengubah jml item '{item_dipilih.nama_produk}' menjadi {jumlah_baru}.")
                        print(f"Jumlah '{item_dipilih.nama_produk}' telah diubah menjadi {jumlah_baru}.")
        except ValueError:
            print("Input jumlah tidak valid.")
        except Exception as e:
            logger.error(f"Error saat mengubah item keranjang: {e}")
            print(f"Terjadi kesalahan: {e}")
    else:
        print("Nomor item tidak valid.")
    input_enter_lanjut()


def proses_pembayaran_toko():
    """Memproses pembayaran pesanan di keranjang menggunakan saldo bank."""
    global keranjang_belanja_global, pengguna_login_saat_ini
    bersihkan_layar(); print_header("Proses Pembayaran Novi Mart")

    if not keranjang_belanja_global.items:
        print("Keranjang belanja kosong."); input_enter_lanjut(); return

    total_bayar = keranjang_belanja_global.total_belanja
    print("--- Rincian Belanja ---")
    for item in keranjang_belanja_global.items.values():
        print(f"- {item.nama_produk} x{item.jumlah} = {format_rupiah(item.subtotal)}")
    print_separator_line()
    print(f"Total yang harus dibayar: {format_rupiah(total_bayar)}")
    print(f"Saldo Anda saat ini: {format_rupiah(pengguna_login_saat_ini.saldo_bank)}")
    print_separator_line()

    if pengguna_login_saat_ini.saldo_bank < total_bayar:
        print("\nSaldo bank Anda tidak cukup."); input_enter_lanjut(); return

    if input_valid("\nLanjutkan pembayaran? (y/n): ", opsional=True, default_value='n').lower() == 'y':
        if not minta_pin_transaksi(pengguna_login_saat_ini, "untuk pembayaran ini"):
            print("Pembayaran dibatalkan karena verifikasi PIN gagal."); input_enter_lanjut(); return

        # Validasi stok terakhir kali sebelum transaksi
        produk_yang_diubah: List[Produk] = []
        stok_cukup = True
        for item_keranjang in keranjang_belanja_global.items.values():
            produk_db = dapatkan_produk_by_id(item_keranjang.produk_id)
            if not produk_db or produk_db.stok < item_keranjang.jumlah:
                logger.warning(f"Checkout dibatalkan: Stok '{item_keranjang.nama_produk}' tidak cukup.")
                print(f"Error: Stok produk '{item_keranjang.nama_produk}' tidak cukup. Pembayaran dibatalkan.");
                stok_cukup = False; break
            produk_yang_diubah.append(produk_db)

        if not stok_cukup:
            input_enter_lanjut(); return

        print("\nMemproses pembayaran...")
        time.sleep(2)

        saldo_awal_pengguna = pengguna_login_saat_ini.saldo_bank

        # Kurangi stok produk
        for item_keranjang in keranjang_belanja_global.items.values():
            for produk_obj in produk_yang_diubah:
                if produk_obj.id == item_keranjang.produk_id:
                    produk_obj.stok -= item_keranjang.jumlah
                    break

        # Kurangi saldo pengguna
        pengguna_login_saat_ini.saldo_bank -= total_bayar

        # Buat catatan transaksi dan pesanan
        transaksi_pembayaran = TransaksiBank(
            user_id_sumber=pengguna_login_saat_ini.id,
            jenis_transaksi="Pembayaran Toko",
            jumlah=total_bayar,
            keterangan="Pembelian di Novi Mart",
            saldo_akhir_sumber=pengguna_login_saat_ini.saldo_bank
        )
        pesanan_baru = PesananToko(
            user_id=pengguna_login_saat_ini.id,
            items_pesanan=keranjang_belanja_global.dapatkan_semua_item_dict(),
            total_harga=total_bayar
        )

        pengguna_login_saat_ini.riwayat_transaksi_bank_ids.append(transaksi_pembayaran.id)
        pengguna_login_saat_ini.riwayat_pesanan_toko_ids.append(pesanan_baru.id)

        # Simpan semua perubahan ke database
        simpan_transaksi_bank(transaksi_pembayaran)
        simpan_pesanan_toko(pesanan_baru)
        simpan_pengguna(pengguna_login_saat_ini)
        for prod in produk_yang_diubah:
            simpan_produk(prod)

        keranjang_belanja_global.kosongkan_keranjang()
        logger.info(f"User '{pengguna_login_saat_ini.username}' bayar {format_rupiah(total_bayar)}. Saldo: {format_rupiah(saldo_awal_pengguna)} -> {format_rupiah(pengguna_login_saat_ini.saldo_bank)}. Pesanan ID: {pesanan_baru.id}")

        print("\n--- Struk Pembayaran Novi Mart ---")
        print(f"ID Pesanan: {pesanan_baru.id}")
        print(f"Tanggal: {pesanan_baru.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total: {format_rupiah(total_bayar)}")
        print("\nPembayaran berhasil! Terima kasih telah berbelanja.")
        print(f"Sisa saldo: {format_rupiah(pengguna_login_saat_ini.saldo_bank)}")
    else:
        print("Pembayaran dibatalkan oleh pengguna.")

    input_enter_lanjut()


def lihat_riwayat_pembelian_toko():
    """Menampilkan riwayat pembelian toko untuk pengguna yang sedang login."""
    bersihkan_layar(); print_header(f"Riwayat Pembelian Toko - {pengguna_login_saat_ini.username}")

    list_pesanan_obj = [dapatkan_pesanan_toko_by_id(pid)
                        for pid in pengguna_login_saat_ini.riwayat_pesanan_toko_ids
                        if dapatkan_pesanan_toko_by_id(pid) is not None]

    if not list_pesanan_obj:
        print("Belum ada riwayat pembelian."); input_enter_lanjut(); return

    list_pesanan_obj.sort(key=lambda p: p.timestamp, reverse=True)

    for i, pesanan in enumerate(list_pesanan_obj):
        print_separator_line()
        print(f"Pesanan Ke-{i+1} (ID: {pesanan.id})")
        print(f"Tanggal: {pesanan.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total: {format_rupiah(pesanan.total_harga)}")
        print("Item:")
        for item_dict in pesanan.items_pesanan:
            try:
                item_obj = ItemKeranjang(**item_dict)
                print(f"  - {item_obj.nama_produk} x{item_obj.jumlah} @ {format_rupiah(item_obj.harga_satuan)} = {format_rupiah(item_obj.subtotal)}")
            except ValidationError as e:
                logger.error(f"Error validasi data item pesanan {pesanan.id}: {item_dict} - {e}")
                print(f"  - Error menampilkan item: {item_dict.get('nama_produk', 'N/A')}")

    print_separator_line(); input_enter_lanjut()


# ==============================================================================
# === BLOK 9: FUNGSI PANEL ADMIN ===
# ==============================================================================
# Fungsi-fungsi untuk fitur administrasi sistem.

def admin_tambah_produk():
    """Admin: Menambahkan produk baru ke dalam daftar produk toko."""
    bersihkan_layar(); print_header("Admin - Tambah Produk Baru")

    nama = input_valid("Masukkan Nama Produk: ")
    try:
        harga_float = input_valid("Masukkan Harga Produk: Rp", tipe_data=float)
        if harga_float < 0: raise ValueError("Harga tidak boleh negatif.")
        harga = Money(harga_float, IDR)
    except ValueError as e:
        print(f"Input harga tidak valid: {e}."); input_enter_lanjut(); return

    try:
        stok = input_valid("Masukkan Stok Awal: ", tipe_data=int)
        if stok < 0: raise ValueError("Stok tidak boleh negatif.")
    except ValueError as e:
        print(f"Input stok tidak valid: {e}."); input_enter_lanjut(); return

    deskripsi = input_valid("Masukkan Deskripsi (opsional): ", opsional=True, default_value="")

    konfigurasi = dapatkan_konfigurasi()
    kategori_tersedia = konfigurasi.get("kategori_produk", [])
    print("\nPilih Kategori Produk:");
    [print(f"{i+1}. {kat}") for i, kat in enumerate(kategori_tersedia)]
    print(f"{len(kategori_tersedia)+1}. Tambah Kategori Baru")

    pilihan_kat = input_pilihan_menu(len(kategori_tersedia) + 1, prompt_pesan="Nomor Kategori: ")
    kategori = ""

    if pilihan_kat == len(kategori_tersedia) + 1:
        kategori_baru = input_valid("Masukkan Nama Kategori Baru: ").strip()
        if kategori_baru and kategori_baru not in kategori_tersedia:
            konfigurasi["kategori_produk"].append(kategori_baru)
            simpan_konfigurasi(konfigurasi)
            kategori = kategori_baru
            logger.info(f"ADMIN: Menambah kategori baru '{kategori_baru}'.")
            print(f"Kategori '{kategori_baru}' berhasil ditambah dan dipilih.")
        elif kategori_baru in kategori_tersedia:
            kategori = kategori_baru
            print(f"Kategori '{kategori_baru}' sudah ada, dipilih.")
        else:
            kategori = "Lainnya"
            logger.warning(f"Nama kategori baru tidak valid. Menggunakan '{kategori}'.")
            print(f"Nama kategori baru tidak valid. Menggunakan kategori '{kategori}'.")
    else:
        kategori = kategori_tersedia[pilihan_kat - 1]

    try:
        produk_baru = Produk(nama=nama, harga=harga, stok=stok, kategori=kategori, deskripsi=deskripsi)
        simpan_produk(produk_baru)
        logger.info(f"ADMIN: Produk '{nama}' (ID: {produk_baru.id}) ditambah oleh {pengguna_login_saat_ini.username}.")
        print(f"\nProduk '{nama}' berhasil ditambahkan.");
    except ValidationError as e:
        logger.error(f"Gagal membuat model produk baru: {e}")
        print(f"Gagal menambah produk: {e}")
    except Exception as e:
        logger.error(f"Error tak terduga saat menambah produk: {e}")
        print(f"Terjadi kesalahan: {e}");

    input_enter_lanjut()


def admin_ubah_produk():
    """Admin: Mengubah data produk yang sudah ada di toko."""
    bersihkan_layar(); print_header("Admin - Ubah Data Produk")

    produk_ditampilkan = tampilkan_daftar_produk_toko(tampilkan_deskripsi=True)
    if not produk_ditampilkan:
        input_enter_lanjut(); return

    produk_dipilih = pilih_produk_dari_daftar(produk_ditampilkan)
    if not produk_dipilih:
        return

    print(f"\nMengubah produk: {produk_dipilih.nama} (ID: {produk_dipilih.id})")
    print(f"Info saat ini: Kategori: {produk_dipilih.kategori}, Harga: {format_rupiah(produk_dipilih.harga)}, Stok: {produk_dipilih.stok}")

    nama_baru = input_valid(f"Nama baru [{produk_dipilih.nama}]: ", opsional=True, default_value=produk_dipilih.nama)

    harga_baru_str = input_valid(f"Harga baru [{int(produk_dipilih.harga.amount)}] (kosongkan jika tidak diubah): Rp", opsional=True)
    harga_baru = Money(float(harga_baru_str), IDR) if harga_baru_str else produk_dipilih.harga

    stok_baru_str = input_valid(f"Stok baru [{produk_dipilih.stok}] (kosongkan jika tidak diubah): ", opsional=True)
    stok_baru = int(stok_baru_str) if stok_baru_str else produk_dipilih.stok

    deskripsi_baru = input_valid(f"Deskripsi baru [{produk_dipilih.deskripsi or '-'}]: ", opsional=True, default_value=produk_dipilih.deskripsi)

    kategori_tersedia = dapatkan_konfigurasi().get("kategori_produk", [])
    print("\nPilih Kategori Baru:");
    [print(f"{i+1}. {kat}") for i, kat in enumerate(kategori_tersedia)]
    print(f"{len(kategori_tersedia)+1}. Tambah Kategori Baru")
    print(f"0. Tidak Ubah Kategori (Saat ini: {produk_dipilih.kategori})")
    pilihan_kat = input_pilihan_menu(len(kategori_tersedia) + 1, min_pilihan=0, prompt_pesan="Nomor Kategori Baru: ")
    kategori_baru = produk_dipilih.kategori

    if pilihan_kat > 0 :
        if pilihan_kat == len(kategori_tersedia) + 1:
            kategori_input = input_valid("Masukkan Nama Kategori Baru: ").strip()
            if kategori_input and kategori_input not in kategori_tersedia:
                konfigurasi = dapatkan_konfigurasi()
                konfigurasi["kategori_produk"].append(kategori_input)
                simpan_konfigurasi(konfigurasi)
                kategori_baru = kategori_input
                logger.info(f"ADMIN: Menambah kategori baru '{kategori_input}'.")
            elif kategori_input:
                kategori_baru = kategori_input
        else:
            kategori_baru = kategori_tersedia[pilihan_kat - 1]

    produk_dipilih.nama = nama_baru
    produk_dipilih.harga = harga_baru
    produk_dipilih.stok = stok_baru
    produk_dipilih.deskripsi = deskripsi_baru
    produk_dipilih.kategori = kategori_baru

    try:
        simpan_produk(produk_dipilih)
        logger.info(f"ADMIN: Produk '{produk_dipilih.nama}' (ID: {produk_dipilih.id}) diubah oleh {pengguna_login_saat_ini.username}.")
        print(f"\nData produk '{produk_dipilih.nama}' berhasil diperbarui.");
    except Exception as e:
        logger.error(f"Error saat mengubah produk: {e}")
        print(f"Terjadi kesalahan saat mengubah produk: {e}");

    input_enter_lanjut()


def admin_hapus_produk():
    """Admin: Menghapus produk dari daftar produk toko."""
    bersihkan_layar(); print_header("Admin - Hapus Produk")

    produk_ditampilkan = tampilkan_daftar_produk_toko()
    if not produk_ditampilkan:
        input_enter_lanjut(); return

    produk_dipilih = pilih_produk_dari_daftar(produk_ditampilkan)
    if not produk_dipilih:
        return

    konfirmasi = f"Yakin ingin menghapus '{produk_dipilih.nama}' (ID: {produk_dipilih.id})? (y/n): "
    if input_valid(konfirmasi, opsional=True, default_value='n').lower() == 'y':
        try:
            if hapus_produk_by_id(produk_dipilih.id):
                logger.info(f"ADMIN: Produk '{produk_dipilih.nama}' (ID: {produk_dipilih.id}) dihapus oleh {pengguna_login_saat_ini.username}.")
                print(f"Produk '{produk_dipilih.nama}' berhasil dihapus.")
            else:
                logger.warning(f"ADMIN: Gagal menghapus produk ID {produk_dipilih.id}, mungkin sudah dihapus.")
                print("Gagal menghapus produk. Mungkin sudah dihapus sebelumnya.")
        except Exception as e:
            logger.error(f"Error tak terduga saat menghapus produk ID {produk_dipilih.id}: {e}")
            print(f"Terjadi kesalahan: {e}");
    else:
        print("Penghapusan produk dibatalkan.")

    input_enter_lanjut()


def admin_lihat_laporan_penjualan():
    """Admin: Menampilkan laporan ringkasan penjualan toko."""
    bersihkan_layar(); print_header("Admin - Laporan Penjualan Toko")

    semua_pesanan = dapatkan_semua_pesanan_toko()
    if not semua_pesanan:
        print("Belum ada data penjualan."); input_enter_lanjut(); return

    total_pendapatan = sum((p.total_harga for p in semua_pesanan), Money(0, IDR))

    print(f"Total Transaksi Penjualan: {len(semua_pesanan)}")
    print(f"Total Pendapatan Bruto: {format_rupiah(total_pendapatan)}")
    print_separator_line()

    produk_terjual_count: dict[str, int] = {}
    for pesanan in semua_pesanan:
        for item_dict in pesanan.items_pesanan:
            nama_produk = item_dict.get('nama_produk', 'Produk Tidak Dikenal')
            jumlah_unit = item_dict.get('jumlah', 0)
            if jumlah_unit > 0:
                produk_terjual_count[nama_produk] = produk_terjual_count.get(nama_produk, 0) + jumlah_unit

    if produk_terjual_count:
        print("Produk Terlaris (berdasarkan unit terjual):")
        sorted_produk = sorted(produk_terjual_count.items(), key=lambda item: item[1], reverse=True)
        for i, (nama, jumlah) in enumerate(sorted_produk[:10]):
            print(f"  {i+1}. {nama}: {jumlah} unit")
    else:
        print("Belum ada item produk terjual.")

    print_separator_line(); input_enter_lanjut()


def admin_kelola_kategori():
    """Admin: Menambah atau menghapus kategori produk."""
    while True:
        bersihkan_layar(); print_header("Admin - Kelola Kategori Produk")
        konfigurasi = dapatkan_konfigurasi()
        kategori_tersedia = konfigurasi.get("kategori_produk", [])

        print("Kategori Produk Saat Ini:");
        if not kategori_tersedia: print("(Belum ada kategori.)")
        else: [print(f"{i+1}. {kat}") for i, kat in enumerate(kategori_tersedia)]
        print_separator_line()

        print("1. Tambah Kategori Baru")
        print("2. Hapus Kategori")
        print("3. Kembali ke Menu Admin")
        print_separator_line()

        pilihan = input_pilihan_menu(3)

        if pilihan == 1:
            nama_baru = input_valid("Masukkan Nama Kategori Baru: ").strip()
            if nama_baru and nama_baru not in kategori_tersedia:
                konfigurasi["kategori_produk"].append(nama_baru)
                simpan_konfigurasi(konfigurasi)
                logger.info(f"ADMIN: Kategori '{nama_baru}' ditambah oleh {pengguna_login_saat_ini.username}.")
                print(f"Kategori '{nama_baru}' berhasil ditambahkan.")
            elif nama_baru in kategori_tersedia:
                print("Kategori tersebut sudah ada.")
            else:
                print("Nama kategori tidak valid.")

        elif pilihan == 2:
            if not kategori_tersedia:
                print("Tidak ada kategori untuk dihapus."); input_enter_lanjut(); continue

            print("\nPilih nomor kategori yang akan dihapus (0 untuk batal):")
            pilihan_hapus = input_pilihan_menu(len(kategori_tersedia), min_pilihan=0)
            if pilihan_hapus == 0: continue

            idx_hapus = pilihan_hapus - 1
            kategori_dihapus = kategori_tersedia[idx_hapus]
            digunakan = any(prod.kategori == kategori_dihapus for prod in dapatkan_semua_produk())

            if digunakan:
                print(f"Kategori '{kategori_dihapus}' masih digunakan oleh produk dan tidak bisa dihapus.");
                logger.warning(f"ADMIN: Gagal hapus kategori '{kategori_dihapus}', masih digunakan.")
            else:
                konfirmasi = f"Yakin ingin menghapus kategori '{kategori_dihapus}'? (y/n): "
                if input_valid(konfirmasi, opsional=True, default_value='n').lower() == 'y':
                    konfigurasi["kategori_produk"].pop(idx_hapus)
                    simpan_konfigurasi(konfigurasi)
                    logger.info(f"ADMIN: Kategori '{kategori_dihapus}' dihapus oleh {pengguna_login_saat_ini.username}.")
                    print(f"Kategori '{kategori_dihapus}' berhasil dihapus.")
                else:
                    print("Penghapusan dibatalkan.")

        elif pilihan == 3:
            break

        input_enter_lanjut()


def admin_lihat_semua_akun_bank():
    """Admin: Menampilkan daftar semua akun pengguna di sistem."""
    bersihkan_layar(); print_header("Admin - Daftar Semua Akun Bank")
    semua_pengguna_obj = [Pengguna(**u) for u in db.table('pengguna').all()]

    if not semua_pengguna_obj:
        print("Belum ada akun pengguna di sistem."); input_enter_lanjut(); return

    print_separator_line(120)
    print(f"{'ID':<37} | {'Username':<20} | {'Nama':<25} | {'Peran':<10} | {'Saldo':<15} | {'Kunci?':<7}")
    print_separator_line(120)

    for p in semua_pengguna_obj:
        kunci = "Ya" if p.akun_terkunci_hingga and p.akun_terkunci_hingga > datetime.datetime.now() else "Tidak"
        print(f"{p.id:<37} | {p.username:<20} | {(p.nama_lengkap or '-'):<25} | {p.peran:<10} | {format_rupiah(p.saldo_bank):<15} | {kunci:<7}")

    print_separator_line(120); input_enter_lanjut()


def admin_lihat_semua_transaksi_bank():
    """Admin: Menampilkan daftar semua transaksi bank dalam sistem."""
    bersihkan_layar(); print_header("Admin - Semua Transaksi Bank Sistem")
    semua_trx = dapatkan_semua_transaksi_bank()

    if not semua_trx:
        print("Belum ada data transaksi bank."); input_enter_lanjut(); return

    semua_trx.sort(key=lambda t: t.timestamp, reverse=True)

    print_separator_line(150)
    print(f"{'Timestamp':<26} | {'Jenis':<18} | {'Jumlah':<20} | {'User Sumber':<20} | {'User Tujuan':<20} | {'Ket.':<30}")
    print_separator_line(150)

    for trx in semua_trx:
        u_sumber_obj = dapatkan_pengguna_by_id(trx.user_id_sumber)
        u_sumber = u_sumber_obj.username if u_sumber_obj else "N/A"
        u_tujuan = "-"
        if trx.user_id_tujuan:
            u_tujuan_obj = dapatkan_pengguna_by_id(trx.user_id_tujuan)
            u_tujuan = u_tujuan_obj.username if u_tujuan_obj else "N/A"

        print(f"{trx.timestamp.strftime('%Y-%m-%d %H:%M:%S'):<26} | {trx.jenis_transaksi:<18} | {format_rupiah(trx.jumlah):<20} | {u_sumber:<20} | {u_tujuan:<20} | {trx.keterangan[:30]:<30}")
    print_separator_line(150)

def admin_kelola_maintenance():
    """Admin: Mengaktifkan atau menonaktifkan mode maintenance sistem."""
    bersihkan_layar()
    print_header("Admin - Kelola Mode Maintenance")

    konfigurasi = dapatkan_konfigurasi()
    maintenance_aktif = konfigurasi.get("maintenance_aktif", False)
    berakhir_pada_str = konfigurasi.get("maintenance_berakhir_pada")
    berakhir_pada_dt = None

    # Ubah string dari database kembali menjadi objek datetime jika ada
    if isinstance(berakhir_pada_str, str):
        try:
            # Gunakan format yang sama dengan serializer kita
            berakhir_pada_dt = datetime.datetime.strptime(berakhir_pada_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            logger.warning(f"Format datetime tidak valid di 'maintenance_berakhir_pada': {berakhir_pada_str}")
            maintenance_aktif = False # Anggap tidak aktif jika format salah

    # Periksa apakah maintenance aktif dan sudah kedaluwarsa
    if maintenance_aktif and berakhir_pada_dt and datetime.datetime.now() > berakhir_pada_dt:
        print("Mode maintenance terdeteksi sudah berakhir. Menonaktifkan secara otomatis.")
        logger.info("ADMIN: Mode maintenance dinonaktifkan secara otomatis karena waktu telah berakhir.")
        konfigurasi["maintenance_aktif"] = False
        konfigurasi["maintenance_berakhir_pada"] = None
        simpan_konfigurasi(konfigurasi)
        maintenance_aktif = False # Perbarui status lokal untuk sisa fungsi
        input_enter_lanjut()
        # Panggil fungsi lagi agar menampilkan status yang benar setelah dinonaktifkan
        admin_kelola_maintenance() 
        return

    # --- Logika Utama ---
    if maintenance_aktif:
        # Jika maintenance sedang AKTIF
        print("Status Sistem: MODE MAINTENANCE AKTIF")
        print(f"Akses non-admin akan dibatasi hingga: {berakhir_pada_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print_separator_line()
        
        if input_valid("Nonaktifkan mode maintenance sekarang? (y/n): ", default_value='n').lower() == 'y':
            konfigurasi["maintenance_aktif"] = False
            konfigurasi["maintenance_berakhir_pada"] = None
            simpan_konfigurasi(konfigurasi)
            logger.info(f"ADMIN: Mode maintenance dinonaktifkan secara manual oleh {pengguna_login_saat_ini.username}.")
            print("\nMode maintenance telah dinonaktifkan. Sistem kembali normal.")
        else:
            print("\nTidak ada perubahan. Sistem tetap dalam mode maintenance.")

    else:
        # Jika maintenance sedang TIDAK AKTIF
        print("Status Sistem: NORMAL")
        print("Semua pengguna dapat mengakses sistem.")
        print_separator_line()

        if input_valid("Aktifkan mode maintenance? (y/n): ", default_value='n').lower() == 'y':
            try:
                durasi_menit = input_valid("Masukkan durasi maintenance (menit): ", tipe_data=int)
                if durasi_menit <= 0:
                    print("Durasi harus lebih dari 0 menit.")
                else:
                    waktu_berakhir = datetime.datetime.now() + datetime.timedelta(minutes=durasi_menit)
                    
                    konfigurasi["maintenance_aktif"] = True
                    # Kita simpan dalam format string yang sudah kita tentukan
                    konfigurasi["maintenance_berakhir_pada"] = waktu_berakhir.strftime('%Y-%m-%d %H:%M:%S')
                    
                    simpan_konfigurasi(konfigurasi)
                    logger.info(f"ADMIN: Mode maintenance DIAKTIFKAN oleh {pengguna_login_saat_ini.username} selama {durasi_menit} menit.")
                    print(f"\nMode maintenance berhasil diaktifkan selama {durasi_menit} menit.")
                    print(f"Sistem akan kembali normal sekitar pukul: {waktu_berakhir.strftime('%H:%M:%S')}")

            except ValueError:
                print("Input durasi tidak valid. Harap masukkan angka.")
        else:
            print("\nTidak ada perubahan. Sistem tetap dalam mode normal.")
            
    input_enter_lanjut()

# ==============================================================================
# === BLOK 10: FUNGSI PENGATURAN AKUN ===
# ==============================================================================
# Fungsi-fungsi untuk memungkinkan pengguna mengubah detail akun mereka.

def menu_pengaturan_akun():
    """Menu pengaturan akun untuk pengguna yang sedang login."""
    target_pengguna = pengguna_login_saat_ini
    if not target_pengguna:
        logger.error("Akses menu pengaturan gagal: tidak ada pengguna login.")
        print("Error: Tidak ada pengguna yang login."); input_enter_lanjut(); return

    while True:
        bersihkan_layar(); print_header(f"Pengaturan Akun - {target_pengguna.username}")
        print(f"Nama Lengkap: {target_pengguna.nama_lengkap or '(Belum diatur)'}")
        print(f"Email: {target_pengguna.email or '(Belum diatur)'}")
        print_separator_line()

        print("1. Ubah Nama Lengkap")
        print("2. Ubah Email")
        print("3. Ubah Password")
        print("4. Ubah PIN Bank")
        print("5. Kembali")
        print_separator_line()

        pilihan = input_pilihan_menu(5)

        if pilihan == 1:
            nama_lengkap_baru = input_valid("Masukkan Nama Lengkap Baru: ", opsional=True, default_value=target_pengguna.nama_lengkap)
            if nama_lengkap_baru != target_pengguna.nama_lengkap:
                target_pengguna.nama_lengkap = nama_lengkap_baru
                simpan_pengguna(target_pengguna)
                logger.info(f"Pengguna '{target_pengguna.username}' ubah nama menjadi '{nama_lengkap_baru}'.")
                print("Nama lengkap berhasil diperbarui.");
            else:
                print("Nama lengkap tidak diubah.")

        elif pilihan == 2:
            email_input_str = input_valid(f"Masukkan Email Baru [{target_pengguna.email or '-'}]: ", opsional=True, default_value=target_pengguna.email or "")
            email_baru = email_input_str.strip() or None
            if email_baru and not re.fullmatch(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email_baru):
                print("Format email tidak valid. Email tidak diubah.");
                email_baru = target_pengguna.email

            if email_baru != target_pengguna.email:
                target_pengguna.email = email_baru
                simpan_pengguna(target_pengguna)
                logger.info(f"Pengguna '{target_pengguna.username}' ubah email menjadi '{email_baru}'.")
                print("Email berhasil diperbarui.");
            else:
                print("Email tidak diubah.")

        elif pilihan == 3:
            if target_pengguna.pin_hash and not minta_pin_transaksi(target_pengguna, "untuk ubah password"):
                input_enter_lanjut(); continue

            password_lama = input_valid("Masukkan Password Lama: ", sembunyikan_input=True)
            if not target_pengguna.verifikasi_password(password_lama):
                print("Password lama salah. Perubahan dibatalkan."); input_enter_lanjut(); continue

            password_regex = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&_])[A-Za-z\d@$!%*?&_]{8,30}$"
            password_baru = input_valid("Masukkan Password Baru: ", sembunyikan_input=True, validasi_regex=password_regex, pesan_error_regex="Password baru tidak memenuhi syarat keamanan.")
            if password_baru != input_valid("Konfirmasi Password Baru: ", sembunyikan_input=True):
                print("Password baru tidak cocok. Perubahan dibatalkan."); input_enter_lanjut(); continue

            target_pengguna.password_hash = pwd_context.hash(password_baru)
            simpan_pengguna(target_pengguna)
            logger.info(f"Pengguna '{target_pengguna.username}' berhasil ubah password.")
            print("Password berhasil diubah.");

        elif pilihan == 4:
            if target_pengguna.pin_hash:
                if not minta_pin_transaksi(target_pengguna, "untuk ubah PIN"):
                    input_enter_lanjut(); continue
            else:
                print("Anda belum memiliki PIN. Silakan buat PIN baru.")

            pin_baru = input_valid("Masukkan PIN Bank Baru (6 digit): ", sembunyikan_input=True, validasi_regex=r"^\d{6}$", pesan_error_regex="PIN harus 6 digit angka.")
            if pin_baru != input_valid("Konfirmasi PIN Bank Baru: ", sembunyikan_input=True):
                print("PIN baru tidak cocok. Perubahan dibatalkan."); input_enter_lanjut(); continue

            target_pengguna.set_pin(pin_baru)
            simpan_pengguna(target_pengguna)
            logger.info(f"Pengguna '{target_pengguna.username}' berhasil ubah PIN Bank.")
            print("PIN Bank berhasil diubah/dibuat.");

        elif pilihan == 5:
            break

        input_enter_lanjut()


# ==============================================================================
# === BLOK 11: FUNGSI TAMPILAN MENU ===
# ==============================================================================
# Fungsi-fungsi untuk menampilkan menu utama dan sub-modul (Toko dan Bank).

def menu_utama_non_login():
    """Menampilkan menu utama saat tidak ada pengguna yang login."""
    nama_toko = dapatkan_konfigurasi().get("nama_toko", "Novi Mart")
    bersihkan_layar(); print_header(f"Selamat Datang di {nama_toko} & Bank")

    # --- TAMBAHKAN LOGIKA NOTIFIKASI INI ---
    konfigurasi = dapatkan_konfigurasi()
    if konfigurasi.get("maintenance_aktif", False):
        berakhir_str = konfigurasi.get("maintenance_berakhir_pada")
        if isinstance(berakhir_str, str):
            try:
                berakhir_dt = datetime.datetime.strptime(berakhir_str, '%Y-%m-%d %H:%M:%S')
                if datetime.datetime.now() < berakhir_dt:
                    # Tampilkan pesan besar jika maintenance aktif
                    print_separator_line(char="!")
                    print("!!! SISTEM DALAM MODE MAINTENANCE !!!".center(70))
                    print(f"Layanan login & registrasi tidak tersedia.".center(70))
                    print(f"Sistem akan kembali normal sekitar pukul {berakhir_dt.strftime('%H:%M:%S')}.".center(70))
                    print_separator_line(char="!")
            except ValueError:
                pass # Abaikan jika format tanggal salah
    # ----------------------------------------
    
    print("\nStatus: Belum Login")
    print("1. Login")
    print("2. Registrasi Akun Baru")
    print("3. Lihat Produk Toko (Guest Mode)")
    print("4. Keluar Program")
    print_separator_line()
    return input_pilihan_menu(4)


def menu_utama_pelanggan():
    """Menampilkan menu utama untuk pengguna dengan peran PELANGGAN."""
    nama_toko = dapatkan_konfigurasi().get("nama_toko", "Novi Mart")
    bersihkan_layar(); print_header(f"Menu Utama - {pengguna_login_saat_ini.username}")
    print(f"Saldo Bank Anda: {format_rupiah(pengguna_login_saat_ini.saldo_bank)}")
    print_separator_line()
    print(f"1. {nama_toko} (Modul Toko)")
    print("2. Novi Bank (Modul Perbankan)")
    print("3. Pengaturan Akun")
    print("4. Logout")
    print_separator_line()
    return input_pilihan_menu(4)


def menu_utama_admin():
    """Menampilkan menu 'gerbang' utama untuk admin."""
    bersihkan_layar(); print_header(f"Gerbang Panel untuk admin - {pengguna_login_saat_ini.username}")
    print(f"Saldo Akun Anda= {format_rupiah(pengguna_login_saat_ini.saldo_bank)}")
    print_separator_line()
    print("-> Anda login sebagai Admin - Pilih Mode yang ingin di akses:")
    print("1. Akses Panel Admin (Manajemen Sistem)")
    print("2. Akses Menu Pelanggan (Toko & Bank)")
    print_separator_line()
    print("3. Logout")
    print_separator_line()
    return input_pilihan_menu(3)

def menu_panel_admin():
    """Menampilkan menu utama (Panel Admin) untuk pengguna dengan peran ADMIN."""
    bersihkan_layar(); print_header(f"Panel Admin - {pengguna_login_saat_ini.username}")
    print("--- Manajemen Toko ---")
    print("1. Tambah Produk Baru")
    print("2. Ubah Data Produk")
    print("3. Hapus Produk")
    print("4. Lihat Laporan Penjualan")
    print("5. Kelola Kategori Produk")
    print_separator_line()
    print("--- Manajemen Bank & Pengguna ---")
    print("6. Lihat Semua Akun Bank")
    print("7. Lihat Semua Transaksi Bank Sistem")
    print("8. Kelola Mode Maintenance")
    print("9. Pengaturan Akun Admin")
    print_separator_line()
    print("10. Kembali")
    print_separator_line()
    return input_pilihan_menu(10)


def menu_toko_pelanggan():
    """Menampilkan menu spesifik untuk modul Toko Novi Mart."""
    while True:
        nama_toko = dapatkan_konfigurasi().get("nama_toko", "Novi Mart")
        bersihkan_layar(); print_header(f"{nama_toko} - Modul Toko")
        print(f"Keranjang Belanja: {len(keranjang_belanja_global.items)} item | Total: {format_rupiah(keranjang_belanja_global.total_belanja)}")
        print_separator_line()
        print("1. Tampilkan/Cari Produk & Tambah ke Keranjang")
        print("2. Lihat Isi Keranjang Belanja")
        print("3. Ubah Jumlah Item di Keranjang")
        print("4. Proses Pembayaran (Checkout)")
        print("5. Lihat Riwayat Pembelian Anda")
        print("6. Kembali ke Menu Utama")

        pilihan = input_pilihan_menu(6)
        if pilihan == 1: tambah_produk_ke_keranjang_toko()
        elif pilihan == 2: lihat_keranjang_toko()
        elif pilihan == 3: ubah_item_keranjang_toko()
        elif pilihan == 4: proses_pembayaran_toko()
        elif pilihan == 5: lihat_riwayat_pembelian_toko()
        elif pilihan == 6: break


def menu_bank_pelanggan():
    """Menampilkan menu spesifik untuk modul Bank Novi Mart."""
    while True:
        bersihkan_layar(); print_header("Novi Bank - Modul Perbankan")
        if pengguna_login_saat_ini:
            print(f"Saldo Anda Saat Ini: {format_rupiah(pengguna_login_saat_ini.saldo_bank)}")
        else:
            print("Informasi Saldo: Tidak tersedia")
        print_separator_line()
        print("1. Lihat Saldo Rekening")
        print("2. Deposit Saldo")
        print("3. Withdraw Saldo")
        print("4. Transfer Dana")
        print("5. Lihat Riwayat Transaksi Bank")
        print("6. Kembali ke Menu Utama")

        pilihan = input_pilihan_menu(6)
        if not pengguna_login_saat_ini:
            logger.error("Akses fungsi bank gagal: tidak ada pengguna login.")
            print("Error: Anda harus login untuk mengakses fungsi Bank."); input_enter_lanjut(); continue

        if pilihan == 1: lihat_saldo_bank()
        elif pilihan == 2: deposit_bank()
        elif pilihan == 3: withdraw_bank()
        elif pilihan == 4: transfer_dana_bank()
        elif pilihan == 5: lihat_riwayat_transaksi_bank()
        elif pilihan == 6: break

# ==============================================================================
# === BLOK 12: LOOP UTAMA PROGRAM ===
# ==============================================================================
# Mengatur alur utama eksekusi program berdasarkan status login dan peran pengguna.

# KODE PERBAIKAN UNTUK jalankan_program()
def jalankan_program():
    """Fungsi utama untuk menjalankan aplikasi Novi Mart & Bank."""
    inisialisasi_database_jika_perlu()

    while True:
        if pengguna_login_saat_ini:
            # --- JALUR A: PENGGUNA SUDAH LOGIN ---
            
            if pengguna_login_saat_ini.peran == PERAN_PELANGGAN:
                # Logika untuk Pelanggan (Sudah Benar)
                pilihan = menu_utama_pelanggan()
                if pilihan == 1: menu_toko_pelanggan()
                elif pilihan == 2: menu_bank_pelanggan()
                elif pilihan == 3: menu_pengaturan_akun()
                elif pilihan == 4: logout_pengguna()

            elif pengguna_login_saat_ini.peran == PERAN_ADMIN_UTAMA:
                # --- LOGIKA BARU UNTUK ADMIN UTAMA ---
                while pengguna_login_saat_ini: # Mulai sub-loop khusus admin
                    pilihan_gerbang = menu_utama_admin() # Panggil menu gerbang

                    if pilihan_gerbang == 1:
                        # --- Masuk ke Mode Panel Admin ---
                        while True: # Loop untuk panel admin
                            pilihan_panel = menu_panel_admin()
                            if pilihan_panel == 1: admin_tambah_produk()
                            elif pilihan_panel == 2: admin_ubah_produk()
                            elif pilihan_panel == 3: admin_hapus_produk()
                            elif pilihan_panel == 4: admin_lihat_laporan_penjualan()
                            elif pilihan_panel == 5: admin_kelola_kategori()
                            elif pilihan_panel == 6: admin_lihat_semua_akun_bank()
                            elif pilihan_panel == 7: admin_lihat_semua_transaksi_bank()
                            elif pilihan_panel == 8: admin_kelola_maintenance()
                            elif pilihan_panel == 9: menu_pengaturan_akun()
                            elif pilihan_panel == 10:
                                break # Keluar dari loop panel admin, kembali ke menu gerbang
                        # Setelah break, sub-loop admin akan berputar dan menampilkan menu gerbang lagi.

                    elif pilihan_gerbang == 2:
                        # --- Masuk ke Mode Pelanggan ---
                        pilihan_pelanggan = menu_utama_pelanggan()
                        if pilihan_pelanggan == 1: menu_toko_pelanggan()
                        elif pilihan_pelanggan == 2: menu_bank_pelanggan()
                        elif pilihan_pelanggan == 3: menu_pengaturan_akun()
                        # Opsi logout di sini akan kembali ke menu gerbang admin
                        elif pilihan_pelanggan == 4: pass 

                    elif pilihan_gerbang == 3:
                        # Logout dari menu gerbang
                        logout_pengguna()
                        # break # Keluar dari sub-loop admin
            
        else:
            # --- JALUR B: PENGGUNA BELUM LOGIN--- (Sudah Benar)
            pilihan = menu_utama_non_login()
            if pilihan == 1: login_pengguna()
            elif pilihan == 2: registrasi_pengguna_baru()
            elif pilihan == 3:
                nama_toko = dapatkan_konfigurasi().get("nama_toko", "Novi Mart")
                bersihkan_layar(); print_header(f"Produk {nama_toko} (Guest Mode)")
                tampilkan_daftar_produk_toko(tampilkan_deskripsi=True)
                print("\nSilakan login atau registrasi untuk berbelanja."); input_enter_lanjut()
            elif pilihan == 4:
                print("Terima kasih telah menggunakan layanan Novi Mart & Bank. Sampai jumpa!")
                logger.info("Program dihentikan oleh pengguna.");
                time.sleep(1); bersihkan_layar()
                break


# ==============================================================================
# === BLOK 13: EKSEKUSI PROGRAM UTAMA ===
# ==============================================================================
# Titik masuk utama program saat file skrip dijalankan.

if __name__ == "__main__":
    # --- LOGIKA AUTO-LOGIN UNTUK DEVELOPMENT MODE ---
    if DEVELOPMENT_AUTO_LOGIN_AS:
        # Siapkan pesan yang akan ditampilkan di atas countdown
        prompt_pesan = (
            f"\n{'='*70}\n"
            f"{'!!! WARNING: DEVELOPMENT MODE IS ACTIVE !!!'.center(70)}\n"
            f"{f'--- Akan auto-login sebagai: \'{DEVELOPMENT_AUTO_LOGIN_AS}\' ---'.center(70)}\n"
            f"{'='*70}"
        )
        
        # Panggil fungsi helper kita dengan durasi dari konstanta
        # dan periksa hasilnya (True jika lanjut, False jika batal)
        if countdown_with_cancel(DEVELOPMENT_TIMEOUT_SECONS, prompt_pesan):
            # Jika countdown selesai (tidak dibatalkan), maka lanjutkan proses login
            user_to_login = dapatkan_pengguna_by_username(DEVELOPMENT_AUTO_LOGIN_AS)

            if user_to_login:
                pengguna_login_saat_ini = user_to_login
                logger.info(f"[DEV MODE] Auto-login berhasil sebagai '{DEVELOPMENT_AUTO_LOGIN_AS}'.")
                # Bersihkan layar setelah login berhasil untuk tampilan yang rapi
                time.sleep(1)
                bersihkan_layar() 
            else:
                logger.warning(f"[DEV MODE] Gagal auto-login: Pengguna '{DEVELOPMENT_AUTO_LOGIN_AS}' tidak ditemukan.")
                print(f"Pengguna '{DEVELOPMENT_AUTO_LOGIN_AS}' tidak ditemukan. Memulai program secara normal.")
                input_enter_lanjut()
        else:
            # Jika dibatalkan (fungsi mengembalikan False), catat di log dan mulai normal
            logger.info("[DEV MODE] Auto-login dibatalkan oleh pengguna. Memulai program secara normal.")
            # Tidak perlu melakukan apa-apa lagi, program akan lanjut ke `try...except` di bawah
    # -----------------------------------------------

    try:
        jalankan_program()
    except KeyboardInterrupt:
        print("\nProgram dihentikan paksa oleh pengguna (KeyboardInterrupt).")
        logger.warning("Program dihentikan paksa (KeyboardInterrupt).")
    except Exception as e:
        print(f"\nTerjadi kesalahan fatal yang tidak terduga: {e}")
        logger.error(f"FATAL ERROR: {e} - Program berhenti.")
        import traceback
        logger.error(f"Traceback lengkap:\n{traceback.format_exc()}")
    finally:
        logger.info("=== Program Novi Mart & Bank (Powerfull Version) selesai ===")