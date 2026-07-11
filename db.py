"""Lapisan database aplikasi SPMI PPEPP (SQLite)."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "spmi.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS standar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kode TEXT NOT NULL UNIQUE,
    nama TEXT NOT NULL,
    kategori TEXT NOT NULL DEFAULT 'Pendidikan',
    pernyataan TEXT NOT NULL,
    indikator TEXT NOT NULL,
    target TEXT NOT NULL,
    penanggung_jawab TEXT,
    status TEXT NOT NULL DEFAULT 'Draf',
    tanggal_penetapan TEXT,
    dibuat_pada TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS pelaksanaan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    standar_id INTEGER NOT NULL REFERENCES standar(id) ON DELETE CASCADE,
    kegiatan TEXT NOT NULL,
    unit TEXT NOT NULL,
    periode TEXT NOT NULL,
    tanggal TEXT,
    capaian TEXT,
    bukti TEXT,
    catatan TEXT,
    dibuat_pada TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS evaluasi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    standar_id INTEGER NOT NULL REFERENCES standar(id) ON DELETE CASCADE,
    periode TEXT NOT NULL,
    metode TEXT NOT NULL DEFAULT 'Audit Mutu Internal',
    auditor TEXT,
    tanggal TEXT,
    capaian TEXT,
    kesimpulan TEXT NOT NULL DEFAULT 'Mencapai Standar',
    jenis_temuan TEXT NOT NULL DEFAULT 'Sesuai',
    temuan TEXT,
    dibuat_pada TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS pengendalian (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluasi_id INTEGER NOT NULL REFERENCES evaluasi(id) ON DELETE CASCADE,
    akar_masalah TEXT,
    tindakan TEXT NOT NULL,
    penanggung_jawab TEXT,
    batas_waktu TEXT,
    status TEXT NOT NULL DEFAULT 'Terbuka',
    hasil TEXT,
    dibuat_pada TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS pengaturan (
    kunci TEXT PRIMARY KEY,
    nilai TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS peningkatan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    standar_id INTEGER NOT NULL REFERENCES standar(id) ON DELETE CASCADE,
    jenis TEXT NOT NULL DEFAULT 'Peningkatan Target',
    usulan TEXT NOT NULL,
    dasar TEXT,
    target_baru TEXT,
    status TEXT NOT NULL DEFAULT 'Diusulkan',
    tanggal TEXT,
    dibuat_pada TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


PENGATURAN_BAWAAN = {
    "profil": "Pendidikan Tinggi",
    "nama_instansi": "",
    "kategori_standar": "Pendidikan\nPenelitian\nPengabdian\nTambahan",
    "metode_evaluasi": ("Audit Mutu Internal\nMonitoring dan Evaluasi\n"
                        "Survei Kepuasan\nRapat Tinjauan Manajemen"),
}


def init_db(seed=True):
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.executemany(
        "INSERT OR IGNORE INTO pengaturan (kunci, nilai) VALUES (?, ?)",
        PENGATURAN_BAWAAN.items())
    if seed and conn.execute("SELECT COUNT(*) FROM standar").fetchone()[0] == 0:
        _seed(conn)
    conn.commit()
    conn.close()


def _seed(conn):
    """Data contoh agar aplikasi langsung bisa dijelajahi."""
    standar = [
        ("STD-PDK-01", "Standar Kompetensi Lulusan", "Pendidikan",
         "Lulusan program studi memiliki capaian pembelajaran sesuai KKNI dan kebutuhan dunia kerja.",
         "Persentase lulusan bekerja/berwirausaha dalam 6 bulan setelah lulus",
         "≥ 80%", "Wakil Rektor I", "Ditetapkan", "2025-01-15"),
        ("STD-PDK-02", "Standar Proses Pembelajaran", "Pendidikan",
         "Proses pembelajaran dilaksanakan secara interaktif, holistik, dan berpusat pada mahasiswa.",
         "Persentase mata kuliah dengan RPS mutakhir dan terunggah di LMS",
         "100%", "Ketua Program Studi", "Ditetapkan", "2025-01-15"),
        ("STD-PNL-01", "Standar Hasil Penelitian", "Penelitian",
         "Dosen menghasilkan publikasi ilmiah pada jurnal nasional terakreditasi atau internasional bereputasi.",
         "Jumlah publikasi terindeks per dosen per tahun",
         "≥ 1 publikasi/dosen/tahun", "Kepala LPPM", "Ditetapkan", "2025-02-01"),
        ("STD-PKM-01", "Standar Pengabdian kepada Masyarakat", "Pengabdian",
         "Kegiatan PkM memberikan manfaat nyata dan terukur bagi masyarakat mitra.",
         "Jumlah kegiatan PkM dengan mitra aktif per prodi per tahun",
         "≥ 2 kegiatan/prodi/tahun", "Kepala LPPM", "Draf", None),
    ]
    conn.executemany(
        """INSERT INTO standar (kode, nama, kategori, pernyataan, indikator, target,
           penanggung_jawab, status, tanggal_penetapan) VALUES (?,?,?,?,?,?,?,?,?)""",
        standar)

    pelaksanaan = [
        (1, "Tracer study lulusan tahun 2025", "Career Center", "2025 Ganjil",
         "2025-10-20", "Respons 72% dari populasi lulusan; 78% bekerja dalam 6 bulan",
         "Laporan tracer study 2025", "Perlu peningkatan kerja sama industri"),
        (2, "Monitoring kelengkapan RPS semester ganjil", "Gugus Kendali Mutu", "2025 Ganjil",
         "2025-09-05", "92% RPS terunggah tepat waktu di LMS",
         "Rekap LMS per 5 September 2025", None),
        (3, "Pendampingan penulisan artikel jurnal", "LPPM", "2025 Ganjil",
         "2025-11-10", "0,8 publikasi/dosen/tahun berjalan",
         "Rekap SINTA institusi", "Klinik manuskrip berjalan bulanan"),
    ]
    conn.executemany(
        """INSERT INTO pelaksanaan (standar_id, kegiatan, unit, periode, tanggal,
           capaian, bukti, catatan) VALUES (?,?,?,?,?,?,?,?)""",
        pelaksanaan)

    evaluasi = [
        (1, "2025 Ganjil", "Audit Mutu Internal", "Tim Auditor AMI", "2025-12-10",
         "78% lulusan bekerja dalam 6 bulan (target ≥ 80%)",
         "Belum Mencapai Standar", "KTS Minor",
         "Capaian indikator 2% di bawah target; program magang belum merata di semua prodi."),
        (2, "2025 Ganjil", "Audit Mutu Internal", "Tim Auditor AMI", "2025-12-10",
         "92% RPS terunggah (target 100%)",
         "Belum Mencapai Standar", "Observasi",
         "8% mata kuliah belum mengunggah RPS; umumnya dosen tidak tetap baru."),
        (3, "2025 Ganjil", "Monitoring dan Evaluasi", "Kepala LPPM", "2025-12-15",
         "0,8 publikasi/dosen (target ≥ 1)",
         "Belum Mencapai Standar", "KTS Minor",
         "Sebaran publikasi tidak merata; 40% dosen belum memiliki publikasi tahun berjalan."),
    ]
    conn.executemany(
        """INSERT INTO evaluasi (standar_id, periode, metode, auditor, tanggal,
           capaian, kesimpulan, jenis_temuan, temuan) VALUES (?,?,?,?,?,?,?,?,?)""",
        evaluasi)

    pengendalian = [
        (1, "Kerja sama penempatan kerja dengan industri masih terbatas",
         "Menambah MoU penyaluran kerja dengan minimal 5 industri baru dan mewajibkan magang industri di semester 6",
         "Career Center", "2026-06-30", "Dalam Proses",
         "3 MoU baru telah ditandatangani per Juni 2026"),
        (2, "Dosen baru belum mendapat pelatihan LMS",
         "Pelatihan wajib LMS bagi seluruh dosen baru di awal semester dan reminder otomatis H-7 perkuliahan",
         "Gugus Kendali Mutu", "2026-02-28", "Selesai",
         "Semester genap: 100% RPS terunggah tepat waktu"),
        (3, "Beban mengajar tinggi menghambat waktu menulis",
         "Skema insentif publikasi dan pengurangan beban mengajar bagi dosen dengan target publikasi",
         "Kepala LPPM", "2026-08-31", "Terbuka", None),
    ]
    conn.executemany(
        """INSERT INTO pengendalian (evaluasi_id, akar_masalah, tindakan,
           penanggung_jawab, batas_waktu, status, hasil) VALUES (?,?,?,?,?,?,?)""",
        pengendalian)

    peningkatan = [
        (2, "Peningkatan Target",
         "Menaikkan standar: seluruh RPS wajib memuat komponen case-based/project-based learning",
         "Capaian 100% dua semester berturut-turut setelah tindakan pengendalian",
         "100% RPS dengan komponen CBL/PBL", "Disetujui", "2026-01-20"),
        (1, "Benchmarking",
         "Studi banding pengelolaan career center ke perguruan tinggi dengan serapan lulusan > 90%",
         "Hasil evaluasi AMI 2025 Ganjil", "≥ 85% lulusan bekerja dalam 6 bulan",
         "Diusulkan", "2026-02-01"),
    ]
    conn.executemany(
        """INSERT INTO peningkatan (standar_id, jenis, usulan, dasar, target_baru,
           status, tanggal) VALUES (?,?,?,?,?,?,?)""",
        peningkatan)


if __name__ == "__main__":
    init_db()
    print(f"Database siap: {DB_PATH}")
