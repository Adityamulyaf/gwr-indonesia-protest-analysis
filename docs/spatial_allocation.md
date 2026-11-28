# Alokasi spasial kejadian ACLED ke kabupaten/kota

## Produk Milestone 2C

Kebijakan utama sementara adalah `enhanced` dalam keluarga kebijakan `v2`. Kelompok masih perlu menyepakati definisi akhir. Setiap baris tabel regional mewakili satu kode dari master BPS. Untuk kebijakan *p*, hitungan di wilayah *i* adalah jumlah ID unik yang memperoleh kode *i* menurut kebijakan itu. Satu ID bisa dibandingkan di empat kolom skenario, tetapi hanya menyumbang satu kali dalam setiap kolom. Menjumlahkan keempat kolom akan menghitung ID yang sama berulang kali.

| Kebijakan v2 | Bukti yang diterima | Allocated | Review | Unallocated | Wilayah nol / 514 |
| --- | --- | ---: | ---: | ---: | ---: |
| `conservative` | Satu kode label provinsi dan kab/kota sesuai interior, presisi 1 | 3.165 | 1.226 | 24 | 163 |
| `ambiguity_resolved` | Tambahkan interior tunggal dalam himpunan kode label pada provinsi yang sama, presisi 1 | 3.953 | 438 | 24 | 115 |
| `enhanced` | Tambahkan alias terverifikasi di bawah dengan presisi 1 dan interior 3173 | 4.283 | 108 | 24 | 114 |
| `permissive` | Sertakan pula kandidat spasial tunggal dengan presisi atau label yang masih meragukan | 4.391 | 0 | 24 | 100 |

Seluruh skenario memeriksa himpunan interseksi dan interior sebelum serta sesudah karantina. Keduanya harus stabil, dengan persis satu kode di interior dan tanpa konflik batas, masker atau fitur pengecualian. Jakarta - Unspecified selalu memperoleh status unallocated. Untuk `outside`, titik tidak memiliki kandidat interseksi. Flag `label_disagreement` mensyaratkan dua kode yang dapat dibandingkan, yaitu satu kode label dan satu kode interior yang berbeda. Pada ekstrak ini ada enam outside dan enam konflik dua kode. Ledger 2B dahulu juga menandai lima titik outside sebagai konflik label.

### Alias dan konsentrasi geografis

Padanan khusus menggunakan admin1 sumber `Jakarta`, admin2 sumber `Central Jakarta`, dan kode BPS `3173`. Pembandingan menerima variasi kapitalisasi dan spasi tepi. Masa penerapan analitis mencakup tanggal kejadian 20 Oktober 2024 sampai 16 November 2025, inklusif. Kode dikonfirmasi dengan master BPS semester I 2025. Publikasi BPS menggunakan nama *Jakarta Pusat Municipality* dan *Central Jakarta City* pada katalog 1102001.3173. Referensi, label, kode, dan tanggal tersimpan bersama aturan dalam modul serta disalin ke JSON rekonsiliasi. [Publikasi BPS Jakarta Pusat](https://jakpuskota.bps.go.id/en/publication/2025/02/28/edbb1544aceef3f640647768/kota-jakarta-pusat-dalam-angka-2025.html)

Aturan lama mengecualikan 1.250 ID dari Y utama. Nama yang digunakan bersama oleh kabupaten dan kota membuat kejadian di wilayah tertentu lebih mudah terlewat. Sebanyak 788 ID dengan label ambigu dapat dipulihkan di 48 wilayah dengan mengecek apakah interior merupakan anggota himpunan kandidat dari provinsi yang sesuai. Alias menambah 330 ID hanya di Jakarta Pusat. Seluruhnya memakai satu pasangan koordinat tercatat. Nilai Y wilayah itu menjadi 0, 0, 330 dan 331 menurut urutan skenario di tabel. Koordinat dan presisi 1 mendukung penetapan wilayah, tetapi ketepatan lokasi tiap kejadian tetap mengandung ketidakpastian.

Selisih antara `ambiguity_resolved` dan `enhanced` mengisolasi pengaruh alias. Varians populasi Y antardaerah meningkat dari 192,74 menjadi 394,32, meskipun jumlah wilayah nol turun hanya satu. Simpan keempat skenario agar kelompok dapat menguji pengaruh ambiguitas nama, konsentrasi Jakarta Pusat dan ketidakpastian 108 kandidat tambahan secara terpisah. Hitungan nol berarti belum ada rekaman yang memenuhi aturan di wilayah itu. Batas BIG September 2023 mendahului kejadian 2024–2025. Karantina 28 fitur dengan identitas belum pasti dan koreksi irisan kecil juga membatasi cakupan, terutama dekat batas dan pantai. [Validasi geometri](boundaries.md)

### Reproduksi dan pembacaan keluaran

Jalankan dari root repo menggunakan ekstrak yang hash-nya tercatat pada audit Milestone 1, master lokal dan kedua GeoPackage Milestone 2A. Contoh berikut memakai lokasi ekstrak saat verifikasi.

```powershell
$csv = (Get-ChildItem ..\.. -Filter 'ACLED Data_2026-11-16_event_date_from_2024-10-20_event_date_to_2025-11-16.csv').FullName
.\.venv\gwr-project\Scripts\python.exe -m src.protest_analysis.spatial.allocate --input "$csv"
.\.venv\gwr-project\Scripts\python.exe -m unittest discover -s tests -v
```

Default adalah Protests. Untuk pilihan lain ulangi argumen `--event-type` satu kali per kategori. Angka di atas berlaku untuk Protests. Setiap pilihan menulis ke subfolder sendiri di `data/processed/spatial_allocation/v2/`. Proses ulang membandingkan keluaran dengan arsip versi tersebut dan berhenti jika isinya berbeda. Keluaran versi sebelumnya tetap di `data/processed/spatial_allocation/Protests/`.

- `regional_counts.csv` memuat identitas wilayah, empat kolom `y_<kebijakan>`, jumlah promosi ambiguitas, jumlah promosi alias, dan tambahan khusus kandidat. Pada v2, `protest_count` merujuk ke Y enhanced dan `candidate_count` ke Y permissive.
- `allocations.csv` menyimpan satu baris per ID, `policy_version`, `allocation_rule`, status dan kode setiap kebijakan, himpunan kandidat, bukti sebelum/sesudah dan flag asal dalam `reasons`. Flag ambigu atau label belum terverifikasi dipertahankan meski bukti lanjutan memenuhi aturan. Kode kosong berarti ID tidak masuk Y kebijakan tersebut. Kolom ringkas `status` dan `allocated_bps` merujuk ke enhanced.
- `review.csv` berisi 132 ID di luar Y enhanced, mencakup 108 review dan 24 unallocated. Ledger dan daftar tinjauan hanya disimpan lokal.
- `reconciliation.json` mencatat versi, alias, hash masukan, hitungan per aturan, status, wilayah nol, mean dan varians populasi tiap kebijakan. Jumlah ID pada setiap kebijakan harus sama dengan jumlah allocated, review dan unallocated. Frekuensi flag dapat beririsan.

## Arsip Milestone 2B

Bagian ini menjelaskan makna kolom pada produk lama dalam subfolder `Protests/`. Pada versi tersebut kebijakan utama memakai aturan konservatif.

Setiap ID unik mendapat satu titik (bujur, lintang), EPSG:4326. GeoPandas menghimpun seluruh poligon yang beririsan dengan titik serta seluruh poligon yang memuatnya di interior. Garis batas, beberapa kandidat, fitur tanpa identitas, masker irisan, dan perubahan kandidat/interior antara layer sebelum dan sesudah karantina menghalangi alokasi. Tidak ada snapping. Nilai kosong pada kolom daftar kandidat berarti tidak ada kecocokan.

Untuk Y utama, titik harus di satu interior tanpa tanda spasial, presisi 1, dan pasangan nama provinsi–kabupaten/kota harus menunjuk tepat satu kode master yang sama dengan kode poligon. Normalisasi deterministik menangani kapitalisasi, tanda baca, prefiks kabupaten/kota, beberapa nama provinsi dan terjemahan arah. Sebutan tanpa pembeda kota/kabupaten dapat menunjuk lebih dari satu kode. Daftar alias belum lengkap. Label yang tidak dapat dikonfirmasi tidak membuktikan koordinat salah.

`allocations.csv` mempertahankan seluruh ID, kandidat geometri, kandidat label, penanda, status, serta kode alokasi utama dan sensitivitas. `review.csv` mencakup seluruh baris di luar alokasi utama. Kategori review mensyaratkan satu kandidat spasial bersih; presisi rendah, label ambigu atau perbedaan label tetap terdokumentasi. Jakarta - Unspecified dan seluruh kasus spasial ambigu tidak menyumbang ke salah satu hitungan.

`regional_counts.csv` dibangun dari master lengkap. Kolom `protest_count` menghitung ID berstatus allocated. Kolom `candidate_count` menambahkan ID review satu kali dan sudah mencakup hitungan utama. Nol berarti tidak ada rekaman teralokasi menurut aturan kolom tersebut. `reconciliation.json` memuat hash, jumlah per status, alasan yang dapat bertumpang tindih, dan distribusi utama (varians populasi, pembagi 514). Batas BIG 2023 dan master BPS 2025-I digunakan sebagai geografi tetap untuk seluruh periode.
