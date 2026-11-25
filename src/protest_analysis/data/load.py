"""Read the ACLED export and fingerprint the exact bytes being audited."""
import hashlib
from pathlib import Path

import pandas as pd


def load_acled(path: Path) -> tuple[pd.DataFrame, str]:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
        stream.seek(0)
        # Preserve leading zeros in IDs and literal labels such as "NA".
        frame = pd.read_csv(stream, dtype="string", keep_default_na=False,
                            encoding="utf-8-sig", low_memory=False)
    return frame, digest
