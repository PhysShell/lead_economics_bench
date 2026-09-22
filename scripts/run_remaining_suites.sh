#!/usr/bin/env bash
# Run the remaining benchmark suites in sequence.
#
#   nohup bash scripts/run_remaining_suites.sh > reports/runs/chain.log 2>&1 &
#
# Sizes are chosen to finish on a 4-core container. Commands for the full
# sweeps are in docs/methodology.md.
#
# NB: this is a script file rather than an inline `bash -c` on purpose. An
# inline waiter whose own command line contains the pattern it greps for
# matches itself and waits forever.
set -u
cd "$(dirname "$0")/.."

export OMP_NUM_THREADS=1
export LEADBENCH_NJOBS=1
PY=.venv/bin/python

wait_for() {
  while pgrep -f "$1" > /dev/null; do sleep 30; done
}

log() { echo "[$(date -u +%H:%M:%S)] $*"; }

log "starting real (Hillstrom + Criteo 500k deterministic subsample)"
nice -n 5 $PY scripts/run_benchmark.py --suite real --seeds 3 --criteo-rows 500000 \
  > reports/runs/real.log 2>&1
log "real done"

log "waiting for the lead sweep before ablation, to avoid oversubscribing"
wait_for "run_benchmark.py --suite lead"

log "starting ablation"
nice -n 5 $PY scripts/run_benchmark.py --suite ablation --seeds 6 --n-leads 30000 \
  > reports/runs/ablation.log 2>&1
log "ablation done"

log "starting RQ4 focused run on campaign-level handle-time heterogeneity"
nice -n 5 $PY scripts/run_benchmark.py --suite lead --seeds 6 --n-leads 30000 \
  --regimes campaign_effort_heterogeneity --out-name rq4 > reports/runs/rq4.log 2>&1
log "all remaining suites complete"
