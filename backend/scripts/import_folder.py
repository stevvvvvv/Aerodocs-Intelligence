"""Importe des PDF réels (EASA...) décrits dans un manifeste JSON, via l'API.

Exemple de manifeste (data/raw/manifest.json) :
[
  {"file": "EAR_Continuing_Airworthiness_2024-07.pdf", "family": "EAR Continuing Airworthiness",
   "version_label": "Rev. July 2024", "effective_date": "2024-07-18"},
  {"file": "EAR_Continuing_Airworthiness_2025-09.pdf", "family": "EAR Continuing Airworthiness",
   "version_label": "Rev. September 2025", "effective_date": "2025-09-01"}
]

Usage : python scripts/import_folder.py ../data/raw --api http://localhost:8000
Les dates d'effet ci-dessus sont des exemples : reprendre celles indiquées par EASA.
"""
import argparse
import json
import sys
from pathlib import Path

import httpx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--api", default="http://localhost:8000")
    args = ap.parse_args()

    manifest = json.loads((args.folder / "manifest.json").read_text())
    errors = 0
    for m in manifest:
        path = args.folder / m["file"]
        print(f"→ {m['file']} ({path.stat().st_size / 1e6:.1f} Mo)…", flush=True)
        with path.open("rb") as f:
            r = httpx.post(
                f"{args.api}/api/documents",
                files={"file": (path.name, f, "application/pdf")},
                data={k: v for k, v in m.items() if k != "file" and v},
                timeout=None,  # un EAR de 1 000+ pages prend plusieurs minutes à encoder sur CPU
            )
        if r.status_code == 201:
            d = r.json()
            print(f"  importé : {d['page_count']} pages, {d['chunk_count']} passages")
        elif r.status_code == 409:
            print("  déjà importé")
        else:
            errors += 1
            print(f"  ERREUR {r.status_code} : {r.text[:300]}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
