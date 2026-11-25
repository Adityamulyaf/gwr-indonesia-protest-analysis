# Persiapan batas kabupaten/kota

## Produk yang lulus validasi

Gunakan `data/spatial/big_sep2023/kabkota_analysis.gpkg`, layer `kabkota`. Setelah GeoPackage dibaca kembali, validator memberikan `passed=true`: 514 kode BPS unik, 38 provinsi, 42 kabupaten/kota di enam provinsi Papua, enam unit Jakarta, EPSG:4326, nol geometri invalid/kosong, dan nol irisan berluas positif antarkabupaten/kota. SHA-256 berkas yang diverifikasi adalah `c6ef08599472c254221b155e1cd2e00a992414107d624c9d6d6a98711c405ae4`.

Seluruh 548 FID sumber terwakili tepat sekali: kolom `source_fids` pada 514 baris utama mencakup 520 fitur, dan `source_fid` pada layer `unresolved_features` memuat 28 sisanya. Empat FID (107, 166, 329, 417) mempunyai geometri invalid pada sumber. Semua sumber mentah dipertahankan. Snapshot terdiri dari 69 batch, total 648.295.958 byte GeoJSON. Hash tiap batch ada di `manifest.json`, yang memiliki SHA-256 `64c4fd2990cd23582c293484d6e8ab15e57b20fa213245435b7b5ad3c35c2133`.

Untuk mereproduksi layer analisis, jalankan `python -m scripts.quarantine_big_slivers` setelah `scripts.prepare_big_sep2023` dengan interpreter proyek. Layer hasil perbaikan awal `kabkota_bps.gpkg` memiliki 127 pasangan irisan dengan total 0,015752 m². Skrip menyisihkan irisan poligonal dari kedua wilayah dengan margin 0,00000001 derajat. Pemeriksaan antara masih mendeteksi 42 pasangan residual. Khusus 72 wilayah yang terlibat, skrip menggunakan interior konservatif dengan jarak 0,00000001 derajat dari batas. Selisih jumlah luas sebelum dan sesudah tahap ini, dihitung atas dua layer di EPSG:6933, sekitar 0,05042 km². Angka tersebut merupakan perbedaan luas hasil pengukuran, bukan perubahan wilayah hukum. Jangan gunakan turunan ini untuk pengukuran luas resmi.

Layer `sliver_review` menyimpan masker lokal irisan. Daftar 72 wilayah yang batasnya dikontraksi ada dalam `analysis_validation.json`; masker lokal tidak meliputi seluruh pita interior tersebut. Untuk tahap selanjutnya, pertahankan titik di fitur tanpa identitas, masker, celah, atau garis batas sebagai kasus tinjauan. Periode geometri 2023 tetap menjadi keterbatasan untuk kejadian 2024–2025. Pemeriksaan ini tidak membuktikan kelengkapan seluruh garis pantai.

## Akuisisi fallback 25 November 2026

Metadata resmi [BIG](https://geoportal.big.go.id/sikambing/api/harvestings/identifier/TASWIL5000020230907KABKOTA) menunjuk distribusi poligon `BATASWILAYAH/Administrasi_AR_KabKota_50K/MapServer/0`. Edisi 7 September 2023 dipadankan ke identitas BPS 2025 semester I. Ini adalah geografi tetap untuk periode studi. Katalog data.go.id menandai akses Terbuka, tanpa judul lisensi redistribusi pada metadata. Arsip dan hasil geometri disimpan lokal. CRS, hak publikasi peta turunan, dan ketelitian pada batas yang berubah perlu dirujuk ke metadata produk; unduhan publik sendiri tidak menetapkan hak membagikan ulang geometri.

Satu Peta BIG dan distribusi BIG di katalog masing-masing mengembalikan 548 identifier. Pada distribusi katalog, kunci layanan adalah `FID`. Kueri atribut menunjukkan 520 fitur dengan satu kode PUM yang cocok, 27 tanpa kode yang dapat digunakan, dan satu berkode gabungan `71.05/71.10`. Lima kabupaten Sulawesi Tenggara memiliki beberapa fitur. Padanan 23 kode PUM dengan nol akhir diverifikasi terhadap nama resmi, termasuk pembedaan `11.01` dan `11.10`. Master asli dipertahankan.

Direktori lokal `data/spatial/big_sep2023/` memuat metadata, daftar ID, atribut, dan batch GeoJSON (`objectIds`, delapan per permintaan, `outSR=4326`, tanpa penyederhanaan). Manifest mencatat SHA-256 setiap berkas sumber. Untuk mereproduksi pemrosesan snapshot lengkap dari root repo:

```powershell
.\.venv\gwr-project\Scripts\python.exe -m scripts.prepare_big_sep2023
```

Program memeriksa hash, menghitung ulang himpunan FID, memakai komponen horizontal koordinat, mempertahankan wilayah dengan identitas ambigu dalam layer terpisah, dan menggabungkan bagian dengan identitas terverifikasi. Laporan mentah dan setelah standardisasi disimpan dalam `validation.json`. Pada penggunaan mendatang, setiap titik dalam fitur pengecualian atau irisan tetap memerlukan tinjauan, sekalipun juga termuat dalam satu poligon bernama. Peta garis pantai dan kecukupan cakupan historis tidak terbukti hanya dari jumlah kode.

**Pembanding komunitas.** [Wilayah Boundaries 2025](https://github.com/masmaksum/wilayah_boundaries-2025/tree/fec055fee4a0494a8f5cd168060f3135cbe12088) menyimpan 38 SQL tingkat kabupaten, diunduh tanpa menjalankan SQL. README menyebut penyederhanaan dan dasar pemutakhiran kode; datum dan sumber survei per geometri belum terkonfirmasi. Lisensi MIT tersedia. Pengujian menginterpretasikan pasangan lintang/bujur sebagai WGS 84. Terdapat 514 rekaman dengan 514 kode cocok; 124 geometri tidak valid sebelum make_valid. Setelah mengambil komponen poligonal hasil perbaikan, 935 pasangan masih beririsan (luas gabungan sekitar 1.191,34 km²). Arsip, hash per berkas, GeoPackage pemeriksaan, jejak 23 padanan, dan laporan tersedia di `data/spatial/wilayah_2025/`. [Alf-Anas](https://github.com/Alf-Anas/batas-administrasi-indonesia) menyebut pembaruan 13 Juni 2023 dan kode lama pada pemekaran Papua; lisensi penggunaan berkas tidak terkonfirmasi. Kedua sumber tidak menjadi pengganti geometri BIG.

## Data lokal per 25 November 2026

Master berasal dari [SIG BPS](https://sig.bps.go.id/kode-relasi). Pilih periode BPS 2025 semester I dan periode PUM 2025. Respons provinsi dan 38 respons kabupaten/kota disimpan di `data/spatial/bps_2025_1/`. API yang dipakai adalah `/api/v1/kode-relasi/provinces` dan `/api/v1/kode-relasi/regencies/{kode_provinsi}` dengan parameter `periode_bps=2025_1&periode_pum=2025`. Kolom `bps_provinsi` pada CSV diambil dari provinsi permintaan. Master gabungan memiliki 514 kode unik. SHA-256 `master.csv` adalah `6458a679c481766e63e0e5ccea1d3301d81c45839a5a2a420d450d36267ea48a`.

Pembanding [API SIPEDAS](https://sipedas.pertanian.go.id/api/wilayah/index) menggunakan `thn=2024`. Seluruh kode cocok, termasuk enam unit Jakarta dan 42 unit di enam provinsi Papua. Dua nama di Sumatera Selatan memiliki pemisah baris tambahan dalam SIPEDAS. Respons asli tersimpan di `data/spatial/sipedas_2024/`.

Metadata layanan [Prod_Air](https://geoservices.big.go.id/rbi/rest/services/Hosted/Prod_Air/FeatureServer) pernah menyebut April 2025. Saat akuisisi, permintaan metadata dan hitungan layer mengembalikan kesalahan aplikasi ArcGIS 500. Penelusuran [katalog BIG](https://geoportal.big.go.id/sikambing/api/harvestings/limit/title/0/50/KABKOTA) menemukan edisi 2023 dan 2026. Identifier, ukuran, lisensi dan SHA-256 paket poligon April 2025 belum dapat dikonfirmasi. Mintakan arsip area kabupaten/kota nasional beserta kamus atribut, CRS, edisi dan ketentuan pemakaian dari BIG.

[Layer 0 BIG Juni 2026](https://geoservices.big.go.id/rbi/rest/services/BATASWILAYAH/BATAS_KABKOTA_AR/MapServer/0) mendeklarasikan esriGeometryPolygon dan CRS horizontal 4326. Kueri count mengembalikan 541. Snapshot atribut tanpa geometri disimpan di `data/spatial/big_probe/`. Seluruh KDBBPS kosong setelah spasi dibuang. Normalisasi sederhana KDPKAB dan kode PUM master (hapus spasi tepi dan titik) menghasilkan 491 kode beririsan. Nilai ini tidak menunjukkan bahwa geometrinya sesuai untuk penelitian. Semua folder data mencakup provenance lokal berisi URL dan SHA-256. Lisensi redistribusi khusus belum terverifikasi.

## Menjalankan pemeriksaan

Di Windows, interpreter yang teruji adalah `.venv/gwr-project/Scripts/python.exe` dengan Python 3.12 dari environment Conda `gwr-project`. Dependensi GIS dicatat di `requirements-spatial.txt`. Jalankan dari root repo:

```powershell
.\.venv\gwr-project\Scripts\python.exe -m unittest discover -s tests -v
```

Setelah poligon yang tepat tersedia, baca master dengan `pandas.read_csv(..., dtype=str)`, periksa bahwa `kode_bps` unik, lalu bentuk pemetaan kode kabupaten ke provinsi. Jalankan `load_boundaries(path, layer=...)`, `standardize_boundaries(frame, district=..., province=...)`, dan `validate_boundaries(frame, master)`. Masukan kode kabupaten untuk standardisasi harus berupa kode BPS penuh empat digit. Jika produk hanya memiliki kode PUM, perlukan padanan beredisi jelas sebelum memanggil fungsi. Simpan urutan fitur sumber karena indeks pada laporan berbasis posisi mulai nol.

Validator membandingkan himpunan kode dan induknya, memeriksa tipe serta validitas geometri, mentransformasi extent ke WGS 84 sebagai pemeriksaan kewajaran, dan menguji irisan poligon kandidat dari indeks spasial. Luas irisan positif dilaporkan per pasangan dalam meter persegi menggunakan EPSG:6933. Sentuhan di garis batas mempunyai luas nol. Flag lulus bersifat konservatif terhadap irisan kecil; penelaahan sliver membutuhkan toleransi yang dibenarkan berdasarkan ketelitian sumber. Uji ini belum membuktikan kelengkapan garis pantai atau mendeteksi semua celah internal. Hasil Indonesia tercantum pada bagian akuisisi fallback.
