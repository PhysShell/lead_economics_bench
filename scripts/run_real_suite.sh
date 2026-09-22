#!/usr/bin/env bash
# Real randomized-experiment suite (Hillstrom + Criteo-UPLIFT v2.1).
#
#   nohup bash scripts/run_real_suite.sh > reports/runs/real.log 2>&1 &
#
# Criteo runs on a deterministic subsample so every algorithm sees identical
# data within a runtime this box can finish. The full-data command is in
# docs/methodology.md.
set -u
cd "$(dirname "$0")/.."
export OMP_NUM_THREADS=1
export LEADBENCH_NJOBS=1
exec nice -n 5 .venv/bin/python scripts/run_benchmark.py \
  --suite real --seeds 3 --criteo-rows "${CRITEO_ROWS:-250000}"
