#!/usr/bin/env python
"""Fetch the real randomized-experiment datasets.

    python scripts/download_datasets.py --all
    python scripts/download_datasets.py --dataset hillstrom

Datasets are NOT committed to this repository. Criteo-UPLIFT is CC BY-NC-SA
4.0 (non-commercial use only) and is ~300 MB compressed; Hillstrom is a
third-party public release. SHA256 digests are pinned in
``src/leadbench/data/real.py`` and verified after download.
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leadbench.data.real import DATASETS, DATA_DIR, _sha256  # noqa: E402

LICENCE_NOTICE = {
    "criteo": (
        "Criteo-UPLIFT v2.1 is released under CC BY-NC-SA 4.0: NON-COMMERCIAL "
        "use only, attribution required, share-alike. Cite Diemert, Betlei, "
        "Renaudin & Amini, 'A Large Scale Benchmark for Uplift Modeling', "
        "AdKDD 2018."
    ),
    "hillstrom": (
        "Hillstrom / MineThatData E-Mail Analytics And Data Mining Challenge "
        "(2008), released publicly by Kevin Hillstrom. Credit the source."
    ),
}


def _progress(done: int, total: int) -> None:
    if total <= 0:
        return
    pct = 100.0 * done / total
    sys.stdout.write(f"\r  {done / 1e6:7.1f} / {total / 1e6:7.1f} MB ({pct:5.1f}%)")
    sys.stdout.flush()


def download(name: str, data_dir: Path, force: bool = False) -> Path:
    spec = DATASETS[name]
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / spec["filename"]

    print(f"\n[{name}] {LICENCE_NOTICE.get(name, '')}")
    if path.exists() and not force:
        digest = _sha256(path)
        if spec["sha256"] and digest == spec["sha256"]:
            print(f"[{name}] already present and verified: {path}")
            return path
        print(f"[{name}] present but checksum differs; re-downloading")

    print(f"[{name}] downloading {spec['url']}")
    with urllib.request.urlopen(spec["url"], timeout=120) as r:
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        with open(path, "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                _progress(done, total)
    print()

    digest = _sha256(path)
    if spec["sha256"] and digest != spec["sha256"]:
        raise SystemExit(
            f"[{name}] CHECKSUM MISMATCH\n  expected {spec['sha256']}\n  got      {digest}\n"
            "Refusing to proceed: the upstream file changed, or the download was truncated."
        )
    print(f"[{name}] ok  sha256={digest}  bytes={path.stat().st_size}")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", choices=sorted(DATASETS))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--data-dir", default=str(DATA_DIR))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if not args.all and not args.dataset:
        ap.error("pass --all or --dataset NAME")

    names = sorted(DATASETS) if args.all else [args.dataset]
    for n in names:
        download(n, Path(args.data_dir), force=args.force)
    print("\nDone. These files are gitignored and must not be committed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
