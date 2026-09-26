#!/usr/bin/env python
"""Closure attestation: a statement ABOUT a frozen subject set, never inside it.

The defect this replaces
------------------------
M9-B's closure record hashed a document and then that document was appended
to, in the same turn, so it shipped certifying a state that had already
moved. The record was checking that digests were RECORDED, not that they
DESCRIBED the current artifacts — the same surrogate-for-property substitution
as F20/F21/F22, arrived at the meta level of the closure process itself.

An extra check would not fix the class. The fix is structural, and it is the
one in-toto and SLSA already use: **separate the subject artifacts,
identified by digest, from the attestation made about them.** The subject set
is finalised first and then frozen; the attestation is a separate object that
points at it.

    finalize artifacts -> commit -> compute digests -> attest -> immutable tag

Two rules fall out, and this script enforces both:

1. **The attestation is not a subject of itself.** Nothing can contain an
   accurate digest of the sealed envelope it is sealed inside. That is
   solvable with more layers and there is no reason to volunteer for it.
2. **Digests are computed as the final act, against a clean tree.** If the
   working tree is dirty, the subject set is still moving and there is
   nothing to attest to. The script refuses.

What it does not claim
----------------------
This is not a supply-chain attestation and makes no authenticity claim. It
is provenance for a research milestone: which artifacts, at which digests,
under which commit, with which verification results. Signing and an
immutable release are the operator's step, deliberately outside this script —
see `--print-release-plan`.

    python marketing_experimentation/repro/recast/closure_attest.py \
        --milestone M9-C --out docs/m9c-closure.json --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TRACK = REPO / "marketing_experimentation"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def git(*a: str) -> str:
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True,
                          text=True).stdout.strip()


def build(milestone: str, subjects: list[str], out: Path,
          verification: dict, notes: dict) -> dict:
    """Attestation about `subjects`. `out` is excluded from its own subjects."""
    out_rel = str(out.relative_to(TRACK)) if out.is_relative_to(TRACK) else str(out)
    subject_set = sorted(s for s in subjects if s != out_rel)
    dropped = [s for s in subjects if s == out_rel]
    return {
        "_type": "leadbench-mx closure attestation v1",
        "_shape": "modelled on in-toto/SLSA: SUBJECTS identified by digest, "
                  "and a separate STATEMENT about them. The attestation is "
                  "deliberately not a subject of itself.",
        "milestone": milestone,
        "attested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subject": [{"name": s, "digest": {"sha256": sha256(TRACK / s)}}
                    for s in subject_set],
        "self_excluded_from_subjects": dropped or None,
        "materials": {
            "commit": git("rev-parse", "HEAD"),
            "commit_subject": git("log", "-1", "--format=%s"),
            "tree_clean_at_attestation": git("status", "--porcelain") == "",
        },
        "verification": verification,
        "notes": notes,
        "reopening": "A change to any subject is a NEW milestone with a new "
                     "attestation, not an edit to this one. Corrections that "
                     "move no subject are recorded in `amendments`, carrying "
                     "the superseded digests.",
        "amendments": [],
    }


RELEASE_PLAN = """\
Immutable-release plan (operator step, not performed by this script)

  1. finalize every subject; make no further edits
  2. commit; confirm `git status --porcelain` is empty
  3. run this script -- it refuses on a dirty tree and computes digests last
  4. commit the attestation
  5. create a DRAFT GitHub release; attach the attestation
  6. publish. With immutable releases enabled the tag cannot move and assets
     cannot be changed or deleted afterwards, and GitHub emits its own
     release attestation carrying tag, commit SHA and asset digests.

  Draft -> attach everything -> publish, in that order, so nothing has to be
  corrected after freezing.

  CONSTRAINT FOR THIS TRACK: donor-derived numeric output is PRIVATE
  (docs/artifact-manifest.json, D5). A release may carry the attestation and
  the provenance records. It must NOT carry the cells, the panels or any
  other donor-derived payload. The attestation names their digests; the
  payload stays out of any public artifact store.
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--subject", action="append", default=[],
                    help="repeatable; paths relative to marketing_experimentation/")
    ap.add_argument("--verification", default="{}",
                    help="JSON object of gate results")
    ap.add_argument("--note", action="append", default=[],
                    help="repeatable key=value")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--print-release-plan", action="store_true")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="escape hatch. Using it means the subject set is "
                         "still moving and the attestation describes nothing.")
    a = ap.parse_args()

    if a.print_release_plan:
        print(RELEASE_PLAN)
        return 0

    dirty = git("status", "--porcelain")
    if dirty and not a.allow_dirty:
        print("REFUSED: the working tree is dirty, so the subject set is "
              "still moving.\nFinalize and commit first; digests are the "
              "final act, not an early one.\n")
        print(dirty[:1500])
        return 2

    missing = [s for s in a.subject if not (TRACK / s).exists()]
    if missing:
        print(f"REFUSED: subjects do not exist: {missing}")
        return 2

    notes = dict(n.split("=", 1) for n in a.note if "=" in n)
    att = build(a.milestone, a.subject, Path(a.out).resolve(),
                json.loads(a.verification), notes)

    print(f"milestone      {att['milestone']}")
    print(f"subjects       {len(att['subject'])}")
    if att["self_excluded_from_subjects"]:
        print(f"self-excluded  {att['self_excluded_from_subjects']}")
    print(f"commit         {att['materials']['commit'][:12]}")
    print(f"tree clean     {att['materials']['tree_clean_at_attestation']}")
    if a.dry_run:
        print("\n[dry run] nothing written")
        return 0
    Path(a.out).write_text(json.dumps(att, indent=2) + "\n")
    print(f"\nwrote {a.out}")
    print("\nNext: commit this attestation, then follow --print-release-plan.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
