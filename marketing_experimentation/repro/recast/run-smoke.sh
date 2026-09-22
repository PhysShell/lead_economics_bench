#!/usr/bin/env bash
# G2: the donor's own end-to-end smoke test, in whichever lane is active.
#
# Acceptance is not "the package imports". It is that all four estimators --
# GeoLift, CausalImpact, CausalPy, Google Matched Markets -- complete one
# identical upstream run: R DGP -> panels -> four tools -> metrics -> tables
# -> figures -> the donor's own smoke validation.
set -euo pipefail
DONOR="${DONOR:-/home/user/getrecast/geolift-simulation-study}"
RSCRIPT="${RSCRIPT:-Rscript}"
PYTHON="${PYTHON:?set PYTHON to the 3.12.8 interpreter of the repro lane}"

cd "$DONOR"
echo "== lane =="
$RSCRIPT --version 2>&1 | head -1
$PYTHON --version
echo

make smoke RSCRIPT="$RSCRIPT" PYTHON="$PYTHON" VENV="$(dirname "$(dirname "$PYTHON")")"
