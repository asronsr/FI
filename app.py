"""Aplikasi Penjaminan Mutu Internal (SPMI) berbasis siklus PPEPP.

PPEPP: Penetapan - Pelaksanaan - Evaluasi - Pengendalian - Peningkatan.
"""
import uuid
from pathlib import Path

from flask import (Flask, render_template, request, redirect, url_for, flash,
                   send_from_directory)
from werkzeug.utils import secure_filename

from db import get_db, init_db

app = Flask(__name__)
app.secret_key = "spmi-ppepp-dev-key"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # batas unggahan 16 MB

UPLOAD_DIR = Path(__file__).parent / "unggahan"
UPLOAD_DIR.mkdir(exist_ok=True)
EKSTENSI_DIIZINKAN = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
                      "jpg", "jpeg", "png"}

STATUS_STANDAR = ["Draf", "Ditetapkan", "Dalam Peningkatan", "Tidak Berlaku"]
KESIMPULAN_EVALUASI = ["Melampaui Standar", "Mencapai Standar",
                       "Belum Mencapai Standar", "Menyimpang dari Standar"]
JENIS_TEMUAN = ["Sesuai", "Observasi", "KTS Minor", "KTS Mayor"]
STATUS_PENGENDALIAN = ["Terbuka", "Dalam Proses", "Selesai"]
JENIS_PENINGKATAN = ["Peningkatan Target", "Revisi Standar",
                     "Standar Baru", "Benchmarking"]
JENIS_DOKUMEN = ["SK", "Kebijakan", "Peraturan", "SOP", "Manual Mutu",
                 "Formulir", "Lainnya"]
STATUS_PENINGKATAN = ["Diusulkan", "Dikaji", "Disetujui", "Diterapkan", "Ditolak"]

# Profil siap pakai: mengisi daftar kategori standar dan metode evaluasi
# sesuai domain organisasi. Daftar tetap dapat disunting manual di Pengaturan.
PROFIL = {
    "Pendidikan Tinggi": {
        "kategori_standar": ["Pendidikan", "Penelitian", "Pengabdian", "Tambahan"],
        "metode_evaluasi": ["Audit Mutu Internal", "Monitoring dan Evaluasi",
                            "Survei Kepuasan", "Rapat Tinjauan Manajemen"],
    },
    "Manufaktur": {
        "kategori_standar": ["Proses Produksi", "Bahan Baku", "Produk Jadi",
                             "K3 & Lingkungan", "Pendukung"],
        "metode_evaluasi": ["Audit Mutu Internal", "Inspeksi QC",
                            "Statistical Process Control",
                            "Audit Eksternal / Sertifikasi",
                            "Rapat Tinjauan Manajemen"],
    },
}


def get_konfig(conn):
    """Konfigurasi aktif dari tabel pengaturan, dengan daftar terurai per baris."""
    k = {r["kunci"]: r["nilai"] for r in
         conn.execute("SELECT kunci, nilai FROM pengaturan").fetchall()}

    def daftar(kunci, cadangan):
        baris = [b.strip() for b in k.get(kunci, "").splitlines() if b.strip()]
        return baris or cadangan

    return {
        "profil": k.get("profil", "Pendidikan Tinggi"),
        "nama_instansi": k.get("nama_instansi", ""),
        "kategori_standar": daftar("kategori_standar",
                                   PROFIL["Pendidikan Tinggi"]["kategori_standar"]),
        "metode_evaluasi": daftar("metode_evaluasi",
                                  PROFIL["Pendidikan Tinggi"]["metode_evaluasi"]),
    }


def simpan_pengaturan(conn, data):
    conn.executemany(
        """INSERT INTO pengaturan (kunci, nilai) VALUES (?, ?)
           ON CONFLICT(kunci) DO UPDATE SET nilai = excluded.nilai""",
        data.items())


@app.context_processor
def sisipkan_konfig():
    conn = get_db()
    konfig = get_konfig(conn)
    conn.close()
    return {"konfig": konfig}


@app.template_filter("badge")
def badge_class(value):
    """Pemetaan nilai status/temuan ke kelas warna badge."""
    hijau = {"Ditetapkan", "Selesai", "Sesuai", "Mencapai Standar",
             "Melampaui Standar", "Disetujui", "Diterapkan"}
    kuning = {"Draf", "Dalam Proses", "Observasi", "KTS Minor",
              "Belum Mencapai Standar", "Dikaji", "Diusulkan", "Dalam Peningkatan"}
    merah = {"KTS Mayor", "Menyimpang dari Standar", "Terbuka",
             "Ditolak", "Tidak Berlaku"}
    if value in hijau:
        return "badge-hijau"
    if value in kuning:
        return "badge-kuning"
    if value in merah:
        return "badge-merah"
    return "badge-abu"


def daftar_standar(conn):
    return conn.execute("SELECT id, kode, nama FROM standar ORDER BY kode").fetchall()


def daftar_evaluasi(conn):
    return conn.execute(
        """SELECT e.id, e.periode, e.jenis_temuan, s.kode
           FROM evaluasi e JOIN standar s ON s.id = e.standar_id
           ORDER BY e.tanggal DESC"""
    ).fetchall()


# ---------------------------------------------------------------- Dashboard

@app.route("/")
def dashboard():
    conn = get_db()
    stat = {
        "standar": conn.execute("SELECT COUNT(*) FROM standar").fetchone()[0],
        "standar_ditetapkan": conn.execute(
            "SELECT COUNT(*) FROM standar WHERE status = 'Ditetapkan'").fetchone()[0],
        "pelaksanaan": conn.execute("SELECT COUNT(*) FROM pelaksanaan").fetchone()[0],
        "evaluasi": conn.execute("SELECT COUNT(*) FROM evaluasi").fetchone()[0],
        "temuan": conn.execute(
            "SELECT COUNT(*) FROM evaluasi WHERE jenis_temuan != 'Sesuai'").fetchone()[0],
        "pengendalian_terbuka": conn.execute(
            "SELECT COUNT(*) FROM pengendalian WHERE status != 'Selesai'").fetchone()[0],
        "peningkatan": conn.execute("SELECT COUNT(*) FROM peningkatan").fetchone()[0],
    }
    temuan_per_jenis = conn.execute(
        """SELECT jenis_temuan, COUNT(*) AS jumlah FROM evaluasi
           GROUP BY jenis_temuan ORDER BY jumlah DESC""").fetchall()
    tindak_lanjut = conn.execute(
        """SELECT p.*, e.periode, s.id AS standar_id, s.kode, s.nama AS nama_standar
           FROM pengendalian p
           JOIN evaluasi e ON e.id = p.evaluasi_id
           JOIN standar s ON s.id = e.standar_id
           WHERE p.status != 'Selesai'
           ORDER BY p.batas_waktu""").fetchall()
    evaluasi_terbaru = conn.execute(
        """SELECT e.*, s.kode, s.nama AS nama_standar
           FROM evaluasi e JOIN standar s ON s.id = e.standar_id
           ORDER BY e.tanggal DESC LIMIT 5""").fetchall()
    conn.close()
    return render_template("dashboard.html", stat=stat,
                           temuan_per_jenis=temuan_per_jenis,
                           tindak_lanjut=tindak_lanjut,
                           evaluasi_terbaru=evaluasi_terbaru)


# ------------------------------------------------------- 1. Penetapan (Standar)

@app.route("/standar")
def standar_list():
    conn = get_db()
    kategori = request.args.get("kategori", "")
    if kategori:
        rows = conn.execute(
            "SELECT * FROM standar WHERE kategori = ? ORDER BY kode", (kategori,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM standar ORDER BY kode").fetchall()
    kategori_list = get_konfig(conn)["kategori_standar"]
    conn.close()
    return render_template("standar/list.html", rows=rows,
                           kategori_aktif=kategori, kategori_list=kategori_list)


@app.route("/standar/<int:id>")
def standar_detail(id):
    conn = get_db()
    row = conn.execute("SELECT * FROM standar WHERE id = ?", (id,)).fetchone()
    if row is None:
        conn.close()
        flash("Standar tidak ditemukan.", "error")
        return redirect(url_for("standar_list"))
    pelaksanaan = conn.execute(
        "SELECT * FROM pelaksanaan WHERE standar_id = ? ORDER BY tanggal DESC", (id,)).fetchall()
    evaluasi = conn.execute(
        "SELECT * FROM evaluasi WHERE standar_id = ? ORDER BY tanggal DESC", (id,)).fetchall()
    pengendalian = conn.execute(
        """SELECT p.*, e.periode FROM pengendalian p
           JOIN evaluasi e ON e.id = p.evaluasi_id
           WHERE e.standar_id = ? ORDER BY p.batas_waktu""", (id,)).fetchall()
    peningkatan = conn.execute(
        "SELECT * FROM peningkatan WHERE standar_id = ? ORDER BY tanggal DESC", (id,)).fetchall()
    dokumen = conn.execute(
        "SELECT * FROM dokumen WHERE standar_id = ? ORDER BY dibuat_pada DESC", (id,)).fetchall()
    conn.close()
    return render_template("standar/detail.html", s=row, pelaksanaan=pelaksanaan,
                           evaluasi=evaluasi, pengendalian=pengendalian,
                           peningkatan=peningkatan, dokumen=dokumen,
                           jenis_dokumen=JENIS_DOKUMEN)


@app.route("/standar/tambah", methods=["GET", "POST"])
@app.route("/standar/<int:id>/edit", methods=["GET", "POST"])
def standar_form(id=None):
    conn = get_db()
    row = None
    if id is not None:
        row = conn.execute("SELECT * FROM standar WHERE id = ?", (id,)).fetchone()
        if row is None:
            conn.close()
            flash("Standar tidak ditemukan.", "error")
            return redirect(url_for("standar_list"))
    if request.method == "POST":
        f = request.form
        data = (f["kode"].strip(), f["nama"].strip(), f["kategori"],
                f["pernyataan"].strip(), f["indikator"].strip(), f["target"].strip(),
                f.get("penanggung_jawab", "").strip(), f["status"],
                f.get("tanggal_penetapan") or None)
        try:
            if id is None:
                conn.execute(
                    """INSERT INTO standar (kode, nama, kategori, pernyataan, indikator,
                       target, penanggung_jawab, status, tanggal_penetapan)
                       VALUES (?,?,?,?,?,?,?,?,?)""", data)
                flash("Standar berhasil ditetapkan.", "sukses")
            else:
                conn.execute(
                    """UPDATE standar SET kode=?, nama=?, kategori=?, pernyataan=?,
                       indikator=?, target=?, penanggung_jawab=?, status=?,
                       tanggal_penetapan=? WHERE id=?""", data + (id,))
                flash("Standar berhasil diperbarui.", "sukses")
            conn.commit()
            conn.close()
            return redirect(url_for("standar_list"))
        except Exception as e:  # kode duplikat dan sejenisnya
            conn.rollback()
            flash(f"Gagal menyimpan: {e}", "error")
    kategori_list = get_konfig(conn)["kategori_standar"]
    conn.close()
    return render_template("standar/form.html", s=row,
                           kategori_list=kategori_list, status_list=STATUS_STANDAR)


@app.route("/standar/<int:id>/hapus", methods=["POST"])
def standar_hapus(id):
    conn = get_db()
    for d in conn.execute("SELECT nama_file FROM dokumen WHERE standar_id = ?", (id,)):
        (UPLOAD_DIR / d["nama_file"]).unlink(missing_ok=True)
    conn.execute("DELETE FROM standar WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Standar beserta seluruh riwayat siklusnya dihapus.", "sukses")
    return redirect(url_for("standar_list"))


# ------------------------------------------------- Dokumen penetapan standar

@app.route("/standar/<int:id>/cetak")
def standar_cetak(id):
    """Generate dokumen standar siap cetak dari data yang diinput."""
    conn = get_db()
    row = conn.execute("SELECT * FROM standar WHERE id = ?", (id,)).fetchone()
    konfig = get_konfig(conn)
    conn.close()
    if row is None:
        flash("Standar tidak ditemukan.", "error")
        return redirect(url_for("standar_list"))
    return render_template("standar/cetak.html", s=row, konfig=konfig)


@app.route("/standar/<int:id>/dokumen/unggah", methods=["POST"])
def dokumen_unggah(id):
    conn = get_db()
    row = conn.execute("SELECT id FROM standar WHERE id = ?", (id,)).fetchone()
    if row is None:
        conn.close()
        flash("Standar tidak ditemukan.", "error")
        return redirect(url_for("standar_list"))
    berkas = request.files.get("berkas")
    if berkas is None or berkas.filename == "":
        conn.close()
        flash("Pilih berkas yang akan diunggah.", "error")
        return redirect(url_for("standar_detail", id=id))
    nama_asli = secure_filename(berkas.filename)
    ekstensi = nama_asli.rsplit(".", 1)[-1].lower() if "." in nama_asli else ""
    if ekstensi not in EKSTENSI_DIIZINKAN:
        conn.close()
        flash("Jenis berkas tidak diizinkan. Gunakan: "
              + ", ".join(sorted(EKSTENSI_DIIZINKAN)) + ".", "error")
        return redirect(url_for("standar_detail", id=id))
    nama_file = f"{id}-{uuid.uuid4().hex}.{ekstensi}"
    berkas.save(UPLOAD_DIR / nama_file)
    judul = request.form.get("judul", "").strip() or nama_asli.rsplit(".", 1)[0]
    conn.execute(
        """INSERT INTO dokumen (standar_id, jenis, judul, nomor, tanggal,
           nama_file, nama_asli) VALUES (?,?,?,?,?,?,?)""",
        (id, request.form.get("jenis", "Lainnya"), judul,
         request.form.get("nomor", "").strip(),
         request.form.get("tanggal") or None, nama_file, nama_asli))
    conn.commit()
    conn.close()
    flash("Dokumen berhasil diunggah.", "sukses")
    return redirect(url_for("standar_detail", id=id))


@app.route("/dokumen/<int:id>/unduh")
def dokumen_unduh(id):
    conn = get_db()
    d = conn.execute("SELECT * FROM dokumen WHERE id = ?", (id,)).fetchone()
    conn.close()
    if d is None:
        flash("Dokumen tidak ditemukan.", "error")
        return redirect(url_for("standar_list"))
    return send_from_directory(UPLOAD_DIR, d["nama_file"], as_attachment=True,
                               download_name=d["nama_asli"])


@app.route("/dokumen/<int:id>/hapus", methods=["POST"])
def dokumen_hapus(id):
    conn = get_db()
    d = conn.execute("SELECT * FROM dokumen WHERE id = ?", (id,)).fetchone()
    if d is not None:
        (UPLOAD_DIR / d["nama_file"]).unlink(missing_ok=True)
        conn.execute("DELETE FROM dokumen WHERE id = ?", (id,))
        conn.commit()
        flash("Dokumen dihapus.", "sukses")
    conn.close()
    return redirect(url_for("standar_detail", id=d["standar_id"])
                    if d else url_for("standar_list"))


# ------------------------------------------------------------ 2. Pelaksanaan

@app.route("/pelaksanaan")
def pelaksanaan_list():
    conn = get_db()
    rows = conn.execute(
        """SELECT p.*, s.kode, s.nama AS nama_standar
           FROM pelaksanaan p JOIN standar s ON s.id = p.standar_id
           ORDER BY p.tanggal DESC""").fetchall()
    conn.close()
    return render_template("pelaksanaan/list.html", rows=rows)


@app.route("/pelaksanaan/tambah", methods=["GET", "POST"])
@app.route("/pelaksanaan/<int:id>/edit", methods=["GET", "POST"])
def pelaksanaan_form(id=None):
    conn = get_db()
    row = None
    if id is not None:
        row = conn.execute("SELECT * FROM pelaksanaan WHERE id = ?", (id,)).fetchone()
        if row is None:
            conn.close()
            flash("Catatan pelaksanaan tidak ditemukan.", "error")
            return redirect(url_for("pelaksanaan_list"))
    if request.method == "POST":
        f = request.form
        data = (f["standar_id"], f["kegiatan"].strip(), f["unit"].strip(),
                f["periode"].strip(), f.get("tanggal") or None,
                f.get("capaian", "").strip(), f.get("bukti", "").strip(),
                f.get("catatan", "").strip())
        if id is None:
            conn.execute(
                """INSERT INTO pelaksanaan (standar_id, kegiatan, unit, periode,
                   tanggal, capaian, bukti, catatan) VALUES (?,?,?,?,?,?,?,?)""", data)
            flash("Catatan pelaksanaan ditambahkan.", "sukses")
        else:
            conn.execute(
                """UPDATE pelaksanaan SET standar_id=?, kegiatan=?, unit=?, periode=?,
                   tanggal=?, capaian=?, bukti=?, catatan=? WHERE id=?""", data + (id,))
            flash("Catatan pelaksanaan diperbarui.", "sukses")
        conn.commit()
        conn.close()
        return redirect(url_for("pelaksanaan_list"))
    standar = daftar_standar(conn)
    conn.close()
    return render_template("pelaksanaan/form.html", p=row, standar=standar)


@app.route("/pelaksanaan/<int:id>/hapus", methods=["POST"])
def pelaksanaan_hapus(id):
    conn = get_db()
    conn.execute("DELETE FROM pelaksanaan WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Catatan pelaksanaan dihapus.", "sukses")
    return redirect(url_for("pelaksanaan_list"))


# --------------------------------------------------------------- 3. Evaluasi

@app.route("/evaluasi")
def evaluasi_list():
    conn = get_db()
    rows = conn.execute(
        """SELECT e.*, s.kode, s.nama AS nama_standar
           FROM evaluasi e JOIN standar s ON s.id = e.standar_id
           ORDER BY e.tanggal DESC""").fetchall()
    conn.close()
    return render_template("evaluasi/list.html", rows=rows)


@app.route("/evaluasi/tambah", methods=["GET", "POST"])
@app.route("/evaluasi/<int:id>/edit", methods=["GET", "POST"])
def evaluasi_form(id=None):
    conn = get_db()
    row = None
    if id is not None:
        row = conn.execute("SELECT * FROM evaluasi WHERE id = ?", (id,)).fetchone()
        if row is None:
            conn.close()
            flash("Evaluasi tidak ditemukan.", "error")
            return redirect(url_for("evaluasi_list"))
    if request.method == "POST":
        f = request.form
        data = (f["standar_id"], f["periode"].strip(), f["metode"],
                f.get("auditor", "").strip(), f.get("tanggal") or None,
                f.get("capaian", "").strip(), f["kesimpulan"], f["jenis_temuan"],
                f.get("temuan", "").strip())
        if id is None:
            conn.execute(
                """INSERT INTO evaluasi (standar_id, periode, metode, auditor, tanggal,
                   capaian, kesimpulan, jenis_temuan, temuan) VALUES (?,?,?,?,?,?,?,?,?)""",
                data)
            flash("Hasil evaluasi dicatat.", "sukses")
        else:
            conn.execute(
                """UPDATE evaluasi SET standar_id=?, periode=?, metode=?, auditor=?,
                   tanggal=?, capaian=?, kesimpulan=?, jenis_temuan=?, temuan=?
                   WHERE id=?""", data + (id,))
            flash("Hasil evaluasi diperbarui.", "sukses")
        conn.commit()
        conn.close()
        return redirect(url_for("evaluasi_list"))
    standar = daftar_standar(conn)
    metode_list = get_konfig(conn)["metode_evaluasi"]
    conn.close()
    return render_template("evaluasi/form.html", e=row, standar=standar,
                           metode_list=metode_list,
                           kesimpulan_list=KESIMPULAN_EVALUASI,
                           temuan_list=JENIS_TEMUAN)


@app.route("/evaluasi/<int:id>/hapus", methods=["POST"])
def evaluasi_hapus(id):
    conn = get_db()
    conn.execute("DELETE FROM evaluasi WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Evaluasi dihapus.", "sukses")
    return redirect(url_for("evaluasi_list"))


# ----------------------------------------------------------- 4. Pengendalian

@app.route("/pengendalian")
def pengendalian_list():
    conn = get_db()
    rows = conn.execute(
        """SELECT p.*, e.periode, e.jenis_temuan, s.kode, s.nama AS nama_standar
           FROM pengendalian p
           JOIN evaluasi e ON e.id = p.evaluasi_id
           JOIN standar s ON s.id = e.standar_id
           ORDER BY CASE p.status WHEN 'Terbuka' THEN 0
                    WHEN 'Dalam Proses' THEN 1 ELSE 2 END, p.batas_waktu""").fetchall()
    conn.close()
    return render_template("pengendalian/list.html", rows=rows)


@app.route("/pengendalian/tambah", methods=["GET", "POST"])
@app.route("/pengendalian/<int:id>/edit", methods=["GET", "POST"])
def pengendalian_form(id=None):
    conn = get_db()
    row = None
    if id is not None:
        row = conn.execute("SELECT * FROM pengendalian WHERE id = ?", (id,)).fetchone()
        if row is None:
            conn.close()
            flash("Tindakan pengendalian tidak ditemukan.", "error")
            return redirect(url_for("pengendalian_list"))
    if request.method == "POST":
        f = request.form
        data = (f["evaluasi_id"], f.get("akar_masalah", "").strip(),
                f["tindakan"].strip(), f.get("penanggung_jawab", "").strip(),
                f.get("batas_waktu") or None, f["status"], f.get("hasil", "").strip())
        if id is None:
            conn.execute(
                """INSERT INTO pengendalian (evaluasi_id, akar_masalah, tindakan,
                   penanggung_jawab, batas_waktu, status, hasil) VALUES (?,?,?,?,?,?,?)""",
                data)
            flash("Tindakan pengendalian ditambahkan.", "sukses")
        else:
            conn.execute(
                """UPDATE pengendalian SET evaluasi_id=?, akar_masalah=?, tindakan=?,
                   penanggung_jawab=?, batas_waktu=?, status=?, hasil=? WHERE id=?""",
                data + (id,))
            flash("Tindakan pengendalian diperbarui.", "sukses")
        conn.commit()
        conn.close()
        return redirect(url_for("pengendalian_list"))
    evaluasi = daftar_evaluasi(conn)
    conn.close()
    return render_template("pengendalian/form.html", p=row, evaluasi=evaluasi,
                           status_list=STATUS_PENGENDALIAN)


@app.route("/pengendalian/<int:id>/hapus", methods=["POST"])
def pengendalian_hapus(id):
    conn = get_db()
    conn.execute("DELETE FROM pengendalian WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Tindakan pengendalian dihapus.", "sukses")
    return redirect(url_for("pengendalian_list"))


# ------------------------------------------------------------ 5. Peningkatan

@app.route("/peningkatan")
def peningkatan_list():
    conn = get_db()
    rows = conn.execute(
        """SELECT p.*, s.kode, s.nama AS nama_standar
           FROM peningkatan p JOIN standar s ON s.id = p.standar_id
           ORDER BY p.tanggal DESC""").fetchall()
    conn.close()
    return render_template("peningkatan/list.html", rows=rows)


@app.route("/peningkatan/tambah", methods=["GET", "POST"])
@app.route("/peningkatan/<int:id>/edit", methods=["GET", "POST"])
def peningkatan_form(id=None):
    conn = get_db()
    row = None
    if id is not None:
        row = conn.execute("SELECT * FROM peningkatan WHERE id = ?", (id,)).fetchone()
        if row is None:
            conn.close()
            flash("Usulan peningkatan tidak ditemukan.", "error")
            return redirect(url_for("peningkatan_list"))
    if request.method == "POST":
        f = request.form
        data = (f["standar_id"], f["jenis"], f["usulan"].strip(),
                f.get("dasar", "").strip(), f.get("target_baru", "").strip(),
                f["status"], f.get("tanggal") or None)
        if id is None:
            conn.execute(
                """INSERT INTO peningkatan (standar_id, jenis, usulan, dasar,
                   target_baru, status, tanggal) VALUES (?,?,?,?,?,?,?)""", data)
            flash("Usulan peningkatan ditambahkan.", "sukses")
        else:
            conn.execute(
                """UPDATE peningkatan SET standar_id=?, jenis=?, usulan=?, dasar=?,
                   target_baru=?, status=?, tanggal=? WHERE id=?""", data + (id,))
            flash("Usulan peningkatan diperbarui.", "sukses")
        conn.commit()
        conn.close()
        return redirect(url_for("peningkatan_list"))
    standar = daftar_standar(conn)
    conn.close()
    return render_template("peningkatan/form.html", p=row, standar=standar,
                           jenis_list=JENIS_PENINGKATAN, status_list=STATUS_PENINGKATAN)


@app.route("/peningkatan/<int:id>/hapus", methods=["POST"])
def peningkatan_hapus(id):
    conn = get_db()
    conn.execute("DELETE FROM peningkatan WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Usulan peningkatan dihapus.", "sukses")
    return redirect(url_for("peningkatan_list"))


# --------------------------------------------------------------- Pengaturan

@app.route("/pengaturan", methods=["GET", "POST"])
def pengaturan():
    conn = get_db()
    if request.method == "POST":
        aksi = request.form.get("aksi")
        if aksi == "profil":
            nama_profil = request.form.get("profil", "")
            preset = PROFIL.get(nama_profil)
            if preset:
                simpan_pengaturan(conn, {
                    "profil": nama_profil,
                    "kategori_standar": "\n".join(preset["kategori_standar"]),
                    "metode_evaluasi": "\n".join(preset["metode_evaluasi"]),
                })
                conn.commit()
                flash(f"Profil «{nama_profil}» diterapkan.", "sukses")
            else:
                flash("Profil tidak dikenal.", "error")
        else:
            simpan_pengaturan(conn, {
                "profil": "Kustom",
                "nama_instansi": request.form.get("nama_instansi", "").strip(),
                "kategori_standar": request.form.get("kategori_standar", "").strip(),
                "metode_evaluasi": request.form.get("metode_evaluasi", "").strip(),
            })
            conn.commit()
            flash("Pengaturan disimpan.", "sukses")
        conn.close()
        return redirect(url_for("pengaturan"))
    k = {r["kunci"]: r["nilai"] for r in
         conn.execute("SELECT kunci, nilai FROM pengaturan").fetchall()}
    conn.close()
    return render_template("pengaturan.html", k=k, profil_list=list(PROFIL))


init_db()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
