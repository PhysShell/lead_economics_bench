#!/usr/bin/env bash
# Assemble everything into reports/latest once the suites have run.
#
#   bash scripts/finalize.sh
#
# 1. score the incumbent (replay of the logged policy) on every lead cell
# 2. build leaderboards, comparisons, kill criteria, Pareto and figures
# 3. answer each preregistered research question from the data
set -euo pipefail
cd "$(dirname "$0")/.."

export PYTHONPATH=src
export OMP_NUM_THREADS=1
PY=.venv/bin/python

echo "==> incumbent policy replay"
$PY scripts/add_incumbent_baseline.py --runs reports/runs/lead || true
$PY scripts/add_incumbent_baseline.py --runs reports/runs/rq4 || true

echo "==> report artefacts"
$PY scripts/build_report.py --runs reports/runs --out reports/latest

echo "==> research-question answers"
$PY scripts/answer_research_questions.py --runs reports/runs \
  --out reports/latest/rq_answers.md > reports/latest/rq_answers.txt

echo
echo "==> kill criteria"
$PY - <<'PY'
import pandas as pd
from pathlib import Path
p = Path("reports/latest/kill_criteria.csv")
if p.exists():
    print(pd.read_csv(p).round(2).to_string(index=False))
PY

echo
echo "==> rows per suite"
for d in reports/runs/*/; do
  f="$d/results.csv"
  [ -f "$f" ] && printf "  %-28s %6d rows\n" "$(basename "$d")" "$(($(wc -l < "$f") - 1))"
done
echo
echo "artefacts in reports/latest/"
