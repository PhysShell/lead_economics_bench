#!/usr/bin/env bash
# Bayesian / uncertainty suite at a single dataset size.
#
#   nohup bash scripts/run_bayes_suite.sh > reports/runs/bayes.log 2>&1 &
#
# Four regimes at n=5,000 rather than one regime at two sizes: at n=20,000 a
# single PyMC scenario takes longer than the rest of the benchmark combined on
# a 4-core box, and regime coverage is worth more than size coverage for RQ5
# and RQ6.
set -u
cd "$(dirname "$0")/.."
export OMP_NUM_THREADS=1
export LEADBENCH_NJOBS=1
exec nice -n 5 .venv/bin/python scripts/run_benchmark.py \
  --suite bayes --seeds 4 --bayes-sizes 5000
