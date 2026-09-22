#!/usr/bin/env bash
# The one experiment the completed study left open (RQ5 follow-up).
#
#   setsid nohup bash scripts/run_pooling_suite.sh > reports/runs/pooling.log 2>&1 &
#
# Two questions in one suite:
#   1. can partial pooling be had without MCMC? (K1 fired, but removing the
#      hierarchy costs 3.2%, so the pooling itself is doing real work)
#   2. does shrinking the per-lead value model toward its mean help? (the
#      ablation found that removing it entirely *improved* one regime)
#
# n=5,000 and the four bayes regimes so the pooling numbers sit directly
# alongside bayes_hierarchical, plus the two value-heterogeneity regimes.
set -u
cd "$(dirname "$0")/.."
export OMP_NUM_THREADS=1
export LEADBENCH_NJOBS=1
exec nice -n 5 .venv/bin/python scripts/run_benchmark.py \
  --suite pooling --seeds 6 --bayes-sizes 5000
