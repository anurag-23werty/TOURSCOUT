# /// script
# requires-python = ">=3.12"
# ///
"""Download GeoNames cities15000 (CC BY 4.0) into data/raw/, which is git-ignored.

    uv run data/download_geonames.py
"""

from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path

URL = "https://download.geonames.org/export/dump/cities15000.zip"
OUT = Path(__file__).resolve().parent / "raw"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "cities15000.txt"
    if target.exists():
        print(f"already there: {target}")
        return
    print(f"downloading {URL} …")
    with urllib.request.urlopen(URL, timeout=60) as resp:
        archive = zipfile.ZipFile(io.BytesIO(resp.read()))
    archive.extract("cities15000.txt", OUT)
    rows = sum(1 for _ in target.open(encoding="utf-8"))
    print(f"saved {target} ({rows:,} cities). Data © GeoNames, CC BY 4.0.")


if __name__ == "__main__":
    main()
