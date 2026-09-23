#!/usr/bin/env bash
# Mutation tests for m9b_world_check.py -- the evidence behind F20.
#
# A metamorphic suite that has never failed on a real defect is an
# assertion, not evidence. Each mutation below is a plausible
# "optimisation" or shortcut a later reader might make in good faith; the
# harness must REFUSE every one. Two of them (M-c, M-d) were accepted
# 10/10 by the first version of the suite, which is why W3d exists.
#
# It edits the generator in the DISPOSABLE clone in place and restores it
# on exit (including on interrupt). Never point it at the reference clone.
#
#   bash marketing_experimentation/repro/recast/m9b_mutations.sh
#
# Expected: M-a exits the generator, M-b..M-e are REFUSED, restore passes.
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SP=${SP:-$(mktemp -d "${TMPDIR:-/tmp}/m9b_mut.XXXXXX")}
DONOR=${DONOR:-/home/user/donor-smoke}
GEN=$DONOR/src/R/generate_panels.R
PY=${PY:-$(cd "$HERE/../../.." && pwd)/.venv/bin/python}
CHK=$HERE/m9b_world_check.py
mkdir -p "$SP"

cp "$GEN" "$SP/gen.clean"
restore() { cp "$SP/gen.clean" "$GEN"; }
trap restore EXIT

run_check() {
  TMPDIR=$SP/mut $PY "$CHK" --donor "$DONOR" --skip-legacy 2>&1 \
    | grep -E "^\[ (PASS|FAIL)\]|REFUSED|checks pass|HARNESS FAILURE|generator exited" \
    | sed 's/^/    /'
}

echo "################ M-a: world sized to the request (tripwire left in) ####"
restore
python3 - "$GEN" <<'EOF'
import sys, re
p = sys.argv[1]; s = open(p).read()
s = s.replace("n_geos_world     <- n_treated + MAX_CONTROLS",
              "n_geos_world     <- n_treated + requested_n_control")
s = s.replace("total_days_world <- sc_pre_days + MAX_POST_DAYS",
              "total_days_world <- sc_pre_days + requested_post_days")
open(p,'w').write(s)
EOF
run_check

echo
echo "################ M-b: same, tripwire deleted ###########################"
restore
python3 - "$GEN" <<'EOF'
import sys
p = sys.argv[1]; s = open(p).read()
s = s.replace("n_geos_world     <- n_treated + MAX_CONTROLS",
              "n_geos_world     <- n_treated + requested_n_control")
s = s.replace("total_days_world <- sc_pre_days + MAX_POST_DAYS",
              "total_days_world <- sc_pre_days + requested_post_days")
start = s.index("        stopifnot(\n          n_geos_world")
end = s.index(")\n", s.index("MAX_POST_DAYS >= requested_post_days")) + 2
s = s[:start] + s[end:]
open(p,'w').write(s)
EOF
run_check

echo
echo "################ M-c: donors are the sorted-baseline prefix ############"
restore
python3 - "$GEN" <<'EOF'
import sys
p = sys.argv[1]; s = open(p).read()
s = s.replace("        donor_order <- control_idx[sample.int(length(control_idx))]",
              "        donor_order <- control_idx")
open(p,'w').write(s)
EOF
run_check

echo
echo "################ M-d: permutation drawn from the DGP noise stream ######"
restore
python3 - "$GEN" <<'EOF'
import sys
p = sys.argv[1]; s = open(p).read()
s = s.replace("        set.seed(panel_seed + M9B_PERM_SEED_OFFSET)",
              "        set.seed(panel_seed + 100000)")
open(p,'w').write(s)
EOF
run_check

echo
echo "################ M-e: treated geo chosen from the SLICE ################"
restore
python3 - "$GEN" <<'EOF'
import sys
p = sys.argv[1]; s = open(p).read()
s = s.replace("        sel <- select_treated(baselines, n_treated)",
              "        sel <- select_treated(baselines[seq_len(n_treated + requested_n_control)], n_treated)")
open(p,'w').write(s)
EOF
run_check

echo
echo "################ restore + confirm clean ###############################"
restore
run_check
