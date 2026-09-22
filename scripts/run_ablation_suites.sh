#!/usr/bin/env bash
# Ablations, then the focused RQ4 run. Waits for the main lead sweep so the
# box is not oversubscribed.
set -u
cd "$(dirname "$0")/.."
export OMP_NUM_THREADS=1
export LEADBENCH_NJOBS=1
PY=.venv/bin/python
log() { echo "[$(date -u +%H:%M:%S)] $*"; }

log "waiting for the lead sweep"
while pgrep -f "venv/bin/python scripts/run_benchmark.py --suite lead --seeds 8" > /dev/null; do sleep 30; done

log "starting ablation"
nice -n 5 $PY scripts/run_benchmark.py --suite ablation --seeds 6 --n-leads 30000 \
  > reports/runs/ablation.log 2>&1
log "ablation done"

log "starting RQ4 focused run (campaign-level handle-time heterogeneity)"
nice -n 5 $PY scripts/run_benchmark.py --suite lead --seeds 6 --n-leads 30000 \
  --regimes campaign_effort_heterogeneity --out-name rq4 > reports/runs/rq4.log 2>&1
log "done"
