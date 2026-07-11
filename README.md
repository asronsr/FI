# SPMI PPEPP — Aplikasi Penjaminan Mutu Internal

Aplikasi web untuk mengelola Sistem Penjaminan Mutu Internal (SPMI) berdasarkan siklus
**PPEPP**. Dirancang untuk perguruan tinggi (sesuai SPM Dikti) namun **dapat dikonfigurasi**
untuk domain lain seperti industri manufaktur — siklus PPEPP setara dengan siklus
PDCA/kaizen pada ISO 9001.

| Tahap | Modul | Fungsi |
|---|---|---|
| **P**enetapan | Standar Mutu | Menetapkan standar (pernyataan, indikator, target, penanggung jawab, status penetapan) |
| **P**elaksanaan | Pelaksanaan | Mencatat kegiatan pemenuhan standar beserta unit pelaksana, capaian, dan bukti |
| **E**valuasi | Evaluasi | Mencatat hasil AMI / monev / survei: capaian vs target, kesimpulan, dan jenis temuan (Sesuai, Observasi, KTS Minor, KTS Mayor) |
| **P**engendalian | Pengendalian | Tindakan korektif atas temuan: akar masalah, RTL, penanggung jawab, batas waktu, status |
| **P**eningkatan | Peningkatan | Usulan peningkatan standar berkelanjutan (kaizen): kenaikan target, revisi standar, standar baru, benchmarking |

Dashboard menampilkan ringkasan siklus: jumlah standar, temuan, tindak lanjut yang belum
selesai, evaluasi terbaru, dan sebaran jenis temuan. Halaman detail setiap standar
menampilkan jejak lengkap siklus PPEPP untuk standar tersebut.

## Konfigurasi Domain

Menu **⚙️ Pengaturan** memungkinkan aplikasi dipakai lintas domain:

- **Profil siap pakai** — satu klik untuk mengisi kategori standar dan metode evaluasi:
  - *Pendidikan Tinggi*: kategori Pendidikan/Penelitian/Pengabdian/Tambahan; metode
    AMI, monev, survei kepuasan, RTM.
  - *Manufaktur*: kategori Proses Produksi/Bahan Baku/Produk Jadi/K3 & Lingkungan/Pendukung;
    metode AMI, inspeksi QC, SPC, audit eksternal/sertifikasi, RTM.
- **Sunting manual** — nama instansi/perusahaan serta daftar kategori dan metode bebas
  diubah (satu nilai per baris); profil tercatat sebagai *Kustom*.

Pengaturan disimpan di basis data, sehingga bertahan saat aplikasi dimulai ulang. Data
yang sudah tercatat dengan kategori/metode lama tetap tersimpan dan tampil di daftar.

## Teknologi

- Python 3 + [Flask](https://flask.palletsprojects.com/)
- SQLite (tanpa server basis data terpisah; berkas `spmi.db` dibuat otomatis)
- Tanpa dependensi frontend — HTML + CSS murni

## Menjalankan

```bash
pip install -r requirements.txt
python app.py
```

Buka http://localhost:5000. Saat pertama dijalankan, basis data dibuat otomatis dan
diisi data contoh agar seluruh alur PPEPP langsung dapat dijelajahi. Hapus berkas
`spmi.db` untuk memulai dari kosong kembali (data contoh akan diisikan ulang; ubah
`init_db(seed=False)` di `app.py` bila ingin benar-benar kosong).

## Struktur

```
app.py            # Rute Flask untuk kelima modul PPEPP + dashboard
db.py             # Skema SQLite + data contoh
templates/        # Tampilan Jinja2 per modul
static/style.css  # Gaya tampilan
```

## Catatan Pengembangan Lanjutan

Aplikasi ini belum memiliki autentikasi/otorisasi pengguna dan unggah berkas bukti —
kolom bukti saat ini berupa teks/tautan. Keduanya merupakan kandidat pengembangan
berikutnya bila akan dipakai multi-pengguna di lingkungan produksi.
