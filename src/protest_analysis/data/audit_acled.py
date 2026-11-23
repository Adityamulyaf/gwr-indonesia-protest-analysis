"""Audit kualitas CSV ACLED tanpa mengubah sumbernya."""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .load import load_acled
from .preprocess import protest_tables
from .validate import clean_fields, inspect_records


COUNTS_FILE = "provisional_acled_admin2_counts_NOT_MODEL_READY.csv"
REVIEW_FILE = "protest_location_review.csv"
OUTPUT_FILES = (COUNTS_FILE, REVIEW_FILE, "AUDIT_README.md", "audit_summary.json")
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "interim" / "acled_audit"


def report(s: dict) -> str:
    return f"""# Audit kualitas data ACLED

Berkas `{s['input_filename']}` memiliki SHA-256 `{s['sha256']}`.
Terdapat {s['records']} baris dan {s['columns']} kolom. Rentang tanggal terbaca
{s['min_date']} sampai {s['max_date']}. Tanggal kosong/gagal dibaca
{s['unparseable_dates']}, tanggal terbaca di luar periode proyek {s['dates_outside_project_period']}.

| Pemeriksaan | Hasil |
|---|---|
| Negara | {s['country_counts']} |
| Kategori kejadian | {s['event_type_counts']} |
| Baris ber-ID duplikat / ID kosong | {s['duplicated_event_id_rows']} / {s['missing_event_id_rows']} |
| Baris dengan koordinat tidak valid | {s['invalid_coordinate_rows']} |
| Admin1 / admin2 kosong, semua kategori | {s['missing_admin1']} / {s['missing_admin2_all_types']} |
| Admin2 kosong pada Protests | {s['missing_admin2_protests']} |
| Presisi lokasi, semua kategori | {s['geo_precision_all']} |
| Presisi lokasi, Protests | {s['geo_precision_protests']} |
| Protests dengan presisi 2 atau 3 | {s['protests_geo_precision_2_or_3']} |
| Baris Protests untuk tinjauan lokasi | {s['protest_location_review_rows']} |

`{COUNTS_FILE}` menghitung {s['protest_counts_mapped_by_labels_provisionally']}
baris Protests pada {s['distinct_protest_admin1_admin2_pairs_with_admin2']} pasangan label
dengan admin2 terisi. Rekap mempertahankan baris yang ditandai, termasuk duplikat.
Jumlah kejadian unik memerlukan penyelesaian masalah ID terlebih dahulu.

`{REVIEW_FILE}` berisi satu baris per baris Protests yang memenuhi setidaknya satu
kriteria di kolom penanda. Aturan paket awal (admin2 kosong atau presisi selain 1,
termasuk kosong) menandai {s['protest_location_review_original_rules']} baris.
Audit ini juga memeriksa koordinat tidak valid dan admin1 kosong. Baris tinjauan
dengan admin2 terisi tetap termasuk dalam rekap sementara.

`audit_summary.json` menyimpan hitungan terstruktur. Audit menghitung seluruh
baris input, termasuk Riots. Label ACLED belum dipadankan dengan kode wilayah resmi.
Koordinat dalam rentang global belum membuktikan kecocokan kabupaten/kota.
Daftar induk dan pemeriksaan cakupan diperlukan sebelum menetapkan wilayah nol.
"""


def audit(input_path: Path, output_dir: Path) -> dict:
    input_path = input_path.resolve(strict=True)
    output_dir = output_dir.resolve()
    for name in OUTPUT_FILES:
        target = output_dir / name
        if target.resolve() == input_path or (target.exists() and target.samefile(input_path)):
            raise ValueError("Tujuan keluaran bertabrakan dengan berkas input.")
        if target.is_dir():
            raise ValueError(f"Tujuan keluaran berupa direktori: {name}")
    frame, digest = load_acled(input_path)
    data = clean_fields(frame)
    quality, invalid_coords = inspect_records(data)
    provisional, review, protest_summary = protest_tables(data, invalid_coords)
    summary = {"input_filename": input_path.name, "sha256": digest, "columns": len(frame.columns),
               **quality, **protest_summary}

    output_dir.mkdir(parents=True, exist_ok=True)
    # Finish serializing the full run before publishing its files; publish JSON last.
    with TemporaryDirectory(dir=output_dir) as staging:
        stage = Path(staging)
        provisional.to_csv(stage / COUNTS_FILE, index=False)
        review.to_csv(stage / REVIEW_FILE, index=False)
        (stage / "AUDIT_README.md").write_text(report(summary), encoding="utf-8")
        (stage / "audit_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        for name in OUTPUT_FILES:
            (stage / name).replace(output_dir / name)
    return summary


def reference_metrics(summary: dict) -> dict:
    types = summary["event_type_counts"]
    precision = summary["geo_precision_protests"]
    return {
        "Jumlah baris": summary["records"],
        "Protests": types.get("Protests", 0),
        "Riots": types.get("Riots", 0),
        # The original package reports a combined count. Zero proves both are zero.
        "Baris ber-ID kosong atau duplikat": summary["missing_or_duplicated_event_ids_rows"],
        "Admin2 kosong": summary["missing_admin2_all_types"],
        "Protests dengan presisi 2 atau 3": precision.get("2", 0) + precision.get("3", 0),
        "Protests untuk tinjauan lokasi": summary["protest_location_review_rows"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Berkas CSV ACLED")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Direktori keluaran lokal")
    parser.add_argument("--reference", type=Path, help="audit_summary.json dari paket pembanding")
    args = parser.parse_args()
    try:
        if args.reference:
            if args.reference.resolve() in {(args.output / name).resolve() for name in OUTPUT_FILES}:
                raise ValueError("Gunakan direktori keluaran terpisah dari ringkasan pembanding.")
            baseline = json.loads(args.reference.read_text(encoding="utf-8-sig"))
            expected = reference_metrics(baseline)
            reference_hash = baseline["sha256"]
        result = audit(args.input, args.output)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Audit gagal: {error}\n")
    print(f"{result['records']} baris diperiksa. Ringkasan: {args.output / 'audit_summary.json'}")
    if args.reference:
        same_hash = result["sha256"] == reference_hash
        print("SHA-256 identik." if same_hash else "SHA-256 berbeda. Periksa versi ekspor.")
        actual = reference_metrics(result)
        for metric, count in actual.items():
            print(f"{metric}: {count} (referensi {expected[metric]})")
        if not same_hash or actual != expected:
            parser.exit(2, "Verifikasi berbeda. Periksa metadata, filter, dan penanda tinjauan.\n")


if __name__ == "__main__":
    main()
