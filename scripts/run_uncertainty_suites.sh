#!/usr/bin/env bash
# Bayesian/uncertainty suite, then the online (bandit) suite.
#
#   nohup bash scripts/run_uncertainty_suites.sh > reports/runs/chain2.log 2>&1 &
#
# NB: this is a script file rather than an inline `bash -c` on purpose. An
# inline waiter whose own command line contains the pattern it greps for
# matches itself and waits forever -- which is exactly what happened to the
# first version of this chain.
set -u
cd "$(dirname "$0")/.."

export OMP_NUM_THREADS=1
export LEADBENCH_NJOBS=1
PY=.venv/bin/python

log() { echo "[$(date -u +%H:%M:%S)] $*"; }

log "starting bayes suite (PyMC; slower, so fewer regimes and seeds)"
nice -n 5 $PY scripts/run_benchmark.py --suite bayes --seeds 4 \
  > reports/runs/bayes.log 2>&1
log "bayes done"

log "starting online suite (bandits vs frozen vs retrained)"
nice -n 5 $PY scripts/run_benchmark.py --suite online --seeds 4 \
  > reports/runs/online.log 2>&1
log "online done"
