# Pemodelan Spasial Sebaran Aksi Protes di Indonesia Tahun 2024–2025

Proyek ini memodelkan sebaran aksi protes di kabupaten/kota di Indonesia
dan membandingkan **model non-spasial** dengan **model spasial** (kemungkinan
GWR) untuk melihat apakah hubungan antara aksi protes dan faktor-faktor
wilayah berbeda antar daerah.

- **Data kejadian:** ACLED, periode 20 Oktober 2024 – 16 November 2025
- **Unit analisis:** kabupaten/kota
- **Status:** preprocessing spasial Milestone 2A–2C menghasilkan tabel 514 kabupaten/kota. Y utama sementara (`y_enhanced`, versi `v2`) menghitung 4.283 dari 4.415 *Protests*. Sebanyak 108 kejadian berstatus review dan 24 unallocated. Definisi akhir menunggu persetujuan kelompok.

> Data mentah ACLED tidak disertakan di repository ini.

## Mereproduksi tabel regional

Dari root repo, gunakan interpreter proyek dan ekstrak yang lolos pemeriksaan SHA-256 Milestone 1. Batas BIG September 2023, master BPS 2025 semester I, serta laporan validasi lokal diperlukan. Petunjuk dan sumber tersedia di [persiapan batas](docs/boundaries.md).

```powershell
$csv = 'data/raw/acled/ACLED Data_2026-11-16_event_date_from_2024-10-20_event_date_to_2025-11-16.csv'
.\.venv\gwr-project\Scripts\python.exe -m src.protest_analysis.spatial.allocate --input "$csv"
.\.venv\gwr-project\Scripts\python.exe -m unittest discover -s tests -v
```

Sesuaikan `$csv` dengan lokasi ekstrak. Tabel `data/processed/spatial_allocation/v2/Protests/regional_counts.csv` menyandingkan empat definisi Y. Gunakan ledger lokal dan ringkasan JSON untuk menelusuri setiap perbedaan. [Aturan, hasil, dan keterbatasan alokasi](docs/spatial_allocation.md)

## Menjalankan audit Milestone 1

Gunakan Python 3.11+ dengan pandas 2.0+ dari root repository. Roadmap menargetkan Python 3.12.
Taruh ekstrak UTF-8 CSV di `data/raw/acled/`. Perintah PowerShell untuk ekstrak yang disebut paket awal adalah

```powershell
$csv = 'data/raw/acled/ACLED Data_2026-11-16_event_date_from_2024-10-20_event_date_to_2025-11-16.csv'
python -m src.protest_analysis.data.audit_acled --input "$csv" --reference "../gwr_acled_milestone1/output/audit_summary.json"
python -m unittest discover -s tests -v
```

Sesuaikan nama CSV dengan berkas lokal. Argumen `--reference` bersifat opsional dan membaca JSON
dari paket awal. Kode keluar 0 berarti audit berhasil dan, jika dibandingkan, SHA-256 serta
tujuh ukuran referensi cocok. Kode 1 berarti audit gagal. Kode 2 ketika membandingkan hasil
berarti file atau metrik berbeda. Hasil audit aktual tetap tersedia untuk menelusuri selisih.

### Alur dan keluaran

1. `data/load.py` di bawah `src/protest_analysis/` memuat CSV sebagai teks dan mencatat SHA-256.
2. `data/validate.py` memeriksa sepuluh kolom wajib dari skrip awal, ID, negara, tanggal, kategori,
   koordinat, label administrasi, serta distribusi presisi. Spasi tepi dibersihkan dalam memori.
   Tanggal numerik non-ISO memakai urutan hari/bulan/tahun. Baris di luar periode dan kategori
   selain Protests tetap masuk ringkasan. Koordinat wajib numerik dengan lintang di [-90, 90]
   dan bujur di [-180, 180].
3. `data/preprocess.py` menghitung baris Protests untuk setiap pasangan label dengan admin2 terisi.
   Admin1 kosong dipertahankan sebagai kelompok tersendiri dan ditandai. Daftar tinjauan memakai
   gabungan kondisi admin2 kosong, presisi selain 1 (termasuk kosong), admin1 kosong, atau koordinat
   tidak valid. Dua kondisi terakhir memperluas pemeriksaan paket awal. Satu baris dapat memiliki
   beberapa tanda dan muncul sekali dalam daftar. Sebagian baris tinjauan juga masuk rekap.
4. `data/audit_acled.py` menulis `audit_summary.json`, `AUDIT_README.md`,
   `provisional_acled_admin2_counts_NOT_MODEL_READY.csv`, dan `protest_location_review.csv`
   di `data/interim/acled_audit/`. Masukan dan keluaran default diabaikan oleh Git. Untuk menyimpan
   beberapa pelaksanaan, gunakan direktori berbeda di bawah `data/interim/` dengan `--output`.

### Membaca angka audit

Satu baris merupakan satu rekaman kejadian. ID teks `event_id_cnty` digunakan untuk memeriksa
keunikan. Dua baris dengan ID sama menghasilkan dua baris terdampak duplikasi. ID kosong
dilaporkan tersendiri. Audit tidak membuang baris duplikat secara otomatis.

Untuk pasangan label wilayah, hitungan sementara adalah jumlah baris berkategori Protests yang
memiliki pasangan itu. Jumlah seluruh hitungan ditambah Protests tanpa admin2 harus sama dengan
jumlah seluruh baris Protests. Rekap ini hanya mencakup label yang muncul dalam ekstrak.
Milestone 2A–2C menggunakan daftar induk BPS dan spatial join untuk menghitung Y,
termasuk wilayah dengan nol rekaman teralokasi.

Paket awal melaporkan 4.978 rekaman (4.415 Protests dan 563 Riots), nol baris dengan ID kosong
atau duplikat, 18 admin2 kosong, 77 Protests berpresisi 2/3, dan 95 Protests dalam daftar tinjauan.
Angka ini merupakan **referensi untuk ekstrak dengan hash yang tercatat di paket**.
Gunakan hasil pelaksanaan lokal untuk menyatakan bahwa angka tersebut telah direproduksi.
