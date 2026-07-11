"""Aplikasi Penjaminan Mutu Internal (SPMI) berbasis siklus PPEPP.

PPEPP: Penetapan - Pelaksanaan - Evaluasi - Pengendalian - Peningkatan.
"""
from flask import Flask, render_template, request, redirect, url_for, flash

from db import get_db, init_db

app = Flask(__name__)
app.secret_key = "spmi-ppepp-dev-key"

KATEGORI_STANDAR = ["Pendidikan", "Penelitian", "Pengabdian", "Tambahan"]
STATUS_STANDAR = ["Draf", "Ditetapkan", "Dalam Peningkatan", "Tidak Berlaku"]
METODE_EVALUASI = ["Audit Mutu Internal", "Monitoring dan Evaluasi",
                   "Survei Kepuasan", "Rapat Tinjauan Manajemen"]
KESIMPULAN_EVALUASI = ["Melampaui Standar", "Mencapai Standar",
                       "Belum Mencapai Standar", "Menyimpang dari Standar"]
JENIS_TEMUAN = ["Sesuai", "Observasi", "KTS Minor", "KTS Mayor"]
STATUS_PENGENDALIAN = ["Terbuka", "Dalam Proses", "Selesai"]
JENIS_PENINGKATAN = ["Peningkatan Target", "Revisi Standar",
                     "Standar Baru", "Benchmarking"]
STATUS_PENINGKATAN = ["Diusulkan", "Dikaji", "Disetujui", "Diterapkan", "Ditolak"]


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
    conn.close()
    return render_template("standar/list.html", rows=rows,
                           kategori_aktif=kategori, kategori_list=KATEGORI_STANDAR)


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
    conn.close()
    return render_template("standar/detail.html", s=row, pelaksanaan=pelaksanaan,
                           evaluasi=evaluasi, pengendalian=pengendalian,
                           peningkatan=peningkatan)


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
    conn.close()
    return render_template("standar/form.html", s=row,
                           kategori_list=KATEGORI_STANDAR, status_list=STATUS_STANDAR)


@app.route("/standar/<int:id>/hapus", methods=["POST"])
def standar_hapus(id):
    conn = get_db()
    conn.execute("DELETE FROM standar WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Standar beserta seluruh riwayat siklusnya dihapus.", "sukses")
    return redirect(url_for("standar_list"))


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
    conn.close()
    return render_template("evaluasi/form.html", e=row, standar=standar,
                           metode_list=METODE_EVALUASI,
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


init_db()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
