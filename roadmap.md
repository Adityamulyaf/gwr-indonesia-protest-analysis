# Roadmap

Pemodelan Spasial Sebaran Aksi Protes di Indonesia Tahun 2024–2025:
Perbandingan Model Non-Spasial dan Model Spasial.

Kerjakan berurutan. Tahap 2 (literatur & variabel X) boleh berjalan paralel
dengan Tahap 1–3.

---

## Tahap 0 — Persiapan

- [x] Struktur repository
- [x] Git lokal
- [x] Ekstrak ACLED lokal dengan hash terverifikasi
- [x] Pasang Python 3.12 dan buat `venv`
- [ ] Pasang pustaka: `pandas`, `geopandas`, `statsmodels`, `libpysal`, `esda`, `mgwr`, `matplotlib`

## Tahap 1 — Audit data ACLED

Notebook: `notebooks/01_data_audit.ipynb`

- [x] Periksa jumlah kejadian (4.978 = 4.415 *Protests* + 563 *Riots*)
- [x] Periksa rentang tanggal, koordinat, dan nilai hilang
- [x] Tinjau `geo_precision` dan `sub_event_type`
- [ ] **Putuskan:** kategori ACLED dan ambang `geo_precision` (menunggu kesepakatan kelompok)
  - Usulan Y utama: *Protests* + *Violent demonstration* (tanpa *Mob violence*), presisi 1
  - Uji sensitivitas: *Protests* saja, presisi 1 (definisi pipeline spasial saat ini)
  - Alasan: *Violent demonstration* tetap aksi protes (kelompok *Demonstrations* di ACLED);
    74 dari 246 kejadiannya terjadi pada Agustus 2025. Presisi 3 hanya sampai tingkat
    provinsi sehingga tidak dapat dialokasikan ke kab/kota.
  - Jika disetujui, alokasi spasial Tahap 4 perlu dijalankan ulang dengan kategori tambahan.

Temuan penting: `admin2` ACLED tidak membedakan kabupaten vs kota bernama sama
(mis. Bandung) → Tahap 4 wajib memakai spatial join.

## Tahap 2 — Literatur dan variabel penjelas (X)

- [ ] Kumpulkan dan baca artikel rujukan (protes, GWR/GWPR)
- [ ] Susun daftar kandidat X beserta dasar teorinya
- [ ] Cek ketersediaan setiap X di level kab/kota untuk tahun yang sesuai
- [ ] **Putuskan:** daftar X final dan tahun datanya

## Tahap 3 — Data spasial dan penduduk

- [x] Validasi BIG September 2023 terhadap master BPS 2025 semester I untuk 514 kabupaten/kota di 38 provinsi (Milestone 2A)
- [ ] Ambil jumlah penduduk per kab/kota, simpan di `data/raw/indicators/`
- [ ] Pastikan kode wilayah konsisten di semua file (bukan berdasarkan nama)
- [x] Dokumentasikan wilayah Papua pascapemekaran dan karantina fitur BIG dengan identitas belum pasti

## Tahap 4 — Spatial join dan agregasi

- [x] Uji titik-dalam-poligon dan rekonsiliasi 4.415 ID *Protests* (Milestone 2B)
- [x] Pisahkan enam titik di luar poligon utama dan 18 kejadian Jakarta - Unspecified
- [x] Bentuk empat Y berversi dengan nol untuk wilayah tanpa rekaman teralokasi menurut kebijakannya (Milestone 2C)
- [x] Simpan tabel 514 wilayah, ledger, daftar tinjauan dan rekonsiliasi di `data/processed/spatial_allocation/v2/Protests/`
- [ ] Kelompok mengesahkan definisi penelitian. Y utama sementara menggunakan `enhanced`. [Bukti dan skenario sensitivitas](docs/spatial_allocation.md)

## Tahap 5 — Diagnostik Y dan pemilihan pendekatan

- [x] Hitung proporsi wilayah dengan Y utama sementara nol (114/514, sekitar 22,18%)
- [ ] Poisson dengan offset log(penduduk) → dispersi Pearson
- [ ] **Putuskan pendekatan:**

| Hasil | Pendekatan | Non-spasial | Spasial |
| --- | --- | --- | --- |
| Dispersi ringan (≈ 1–2) | Y = jumlah kejadian | Poisson | GWPR |
| Dispersi berat (≫ 2) | Y = log(laju + 1) | OLS | GWR |

## Tahap 6 — Kumpulkan X dan eksplorasi

- [ ] Unduh data X, gabungkan dengan Y berdasarkan kode wilayah
- [ ] Tangani nilai hilang dan outlier
- [ ] Cek multikolinearitas (korelasi, VIF)
- [ ] Peta sebaran Y dan X
- [ ] Moran's I global dan LISA untuk Y
- [ ] **Putuskan:** jenis matriks bobot spasial (Queen vs KNN; Indonesia negara kepulauan)

## Tahap 7 — Model non-spasial

- [ ] Estimasi model global (OLS atau Poisson/NegBin, sesuai Tahap 5)
- [ ] Uji asumsi dan signifikansi koefisien
- [ ] Moran's I pada residual → bukti perlu tidaknya model spasial

## Tahap 8 — Model spasial

- [ ] Pilih kernel dan bandwidth (adaptif, kriteria AICc)
- [ ] Estimasi GWR/GWPR
- [ ] Uji variabilitas spasial koefisien
- [ ] Peta koefisien lokal dan signifikansinya

## Tahap 9 — Perbandingan model

- [ ] Bandingkan AICc, R²/deviance, dan Moran's I residual
- [ ] Interpretasi: di wilayah mana pengaruh X berbeda dan mengapa
- [ ] Uji ketahanan dengan pendekatan alternatif dari Tahap 5 (lampiran)

## Tahap 10 — Penulisan dan finalisasi

- [ ] Tulis laporan: pendahuluan, metode, hasil, pembahasan, keterbatasan
- [ ] Pastikan notebook bisa dijalankan ulang dari awal
- [ ] Lengkapi README dan sumber data
- [ ] Pastikan data mentah ACLED tidak ikut ter-commit

---

## Keputusan penting

| Tahap | Keputusan | Status |
| --- | --- | --- |
| 1 | Kategori ACLED dan ambang `geo_precision` | terbuka; pipeline sementara memakai *Protests* presisi 1; usulan: *Protests* + *Violent demonstration* presisi 1 (sensitivitas: *Protests* saja) |
| 2 | Variabel X final dan tahun datanya | terbuka |
| 3 | Sumber batas wilayah dan sistem kode | BIG September 2023 dan master BPS 2025-I |
| 5 | Y = jumlah (GWPR) atau laju (GWR) | terbuka |
| 6 | Jenis matriks bobot spasial | terbuka |
