#!/usr/bin/env python
"""The plan gate: expensive work requires a surviving necessary condition (C16).

What it is for
--------------
A research plan is easy to write after the result. The one field that cannot
be written afterwards without self-deception is KILL — the specific outcome
that closes the direction. Left blank, a human will explain after *any*
outcome why the thing is actually very interesting and deserves a little
more looking, which is a reliable way to turn research into a hobby.

So the gate is narrow and mostly about KILL:

    every field present and non-empty
    KILL names a concrete observation, not a sentiment
    BUDGET is a quantity with a unit
    if CONSTRUCTION says the bad state cannot be made unrepresentable,
      WITNESS must say what counterexample is rejected instead (C12/C15)

Honest about its own strength
-----------------------------
This is a CHECK, not a construction, so by C15 it is the weaker form. It
also remains HEURISTIC in the place that matters: it reads KILL as natural
language and infers whether that text terminates a direction. Inferring a
property from prose is itself a proxy, and this gate has already made that
mistake once — see the WEASEL comment below.

**The known limit, and the deferred fix.** If `plan_gate.py` ever becomes a
hard gate in front of an expensive runner, its critical properties should be
expressed STRUCTURALLY rather than guessed from prose:

    kill:
      observation: "rho(att_pct, theta) not materially above rho(verdict, ...)"
      action: stop_direction

`action: stop_direction` *is* a termination by construction; the human
sentence stays alongside as explanation rather than as the thing being
parsed. That is C15 applied to the defect this gate actually hit.

**It is deliberately NOT built now.** No expensive runner consumes a plan
file yet. Designing v2 of a validator for a consumer that does not exist
would be a close-to-caricature violation of the protocol this gate enforces:
introducing a rule against speculative work and immediately doing some. The
note exists so the fix is obvious when a consumer appears, and so nobody
mistakes the current heuristic for a decided design.

    python marketing_experimentation/repro/recast/plan_gate.py PLAN.md
    python marketing_experimentation/repro/recast/plan_gate.py --self-test
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

FIELDS = [
    ("CLAIM", "what are we trying to establish?"),
    ("NECESSARY CONDITION", "what must be true for this to be worth pursuing?"),
    ("CHEAPEST FALSIFIER", "the smallest thing that could show it is not"),
    ("KILL", "the specific result that closes this direction"),
    ("SURVIVE", "the minimum permitted next step if it survives"),
    ("BUDGET", "max time / compute / money before the next decision"),
    ("INVARIANT", "a mathematical or structural property that MUST hold"),
    ("CONSTRUCTION", "can the violation be made unrepresentable? (C15)"),
    ("WITNESS", "if not, what proxy-preserving counterexample is rejected? (C12)"),
]

#: Deferral PHRASES that turn KILL into a decoration. Not exhaustive; the
#: point is to catch the reflexive ones.
#:
#: These were single words in the first version, and the gate promptly
#: rejected its own good example: "GeoLift is not INVESTIGATEd further" is a
#: perfectly concrete termination, and the substring `investigate` flagged
#: it. That is this project's own recurring defect in miniature -- matching a
#: cheap proxy (a word appears) for the property (does KILL name a result
#: that ENDS the direction). Phrases, with boundaries, and only ones that
#: actually defer a decision.
WEASEL = [r"worth (a )?look", r"look (in)?to (it|this)", r"look further",
          r"more data", r"needs? more", r"worth exploring", r"we can (then )?look",
          r"\btbd\b", r"\bn/a\b", r"see above", r"unclear", r"might be",
          r"probably (worth|interesting)", r"revisit later", r"keep an eye"]


def parse(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    cur = None
    for line in text.splitlines():
        m = re.match(r"^##\s+([A-Z][A-Z ]+?)\s*$", line)
        if m:
            cur = m.group(1).strip()
            out[cur] = ""
        elif cur:
            out[cur] += line + "\n"
    return {k: v.strip() for k, v in out.items()}


def validate(text: str) -> list[str]:
    p = parse(text)
    bad = []
    for name, why in FIELDS:
        if name not in p:
            bad.append(f"{name}: missing — {why}")
        elif not p[name]:
            bad.append(f"{name}: empty — {why}")

    kill = p.get("KILL", "").lower()
    if kill:
        if len(kill) < 25:
            bad.append("KILL: too short to name a concrete observation")
        hits = [w for w in WEASEL if re.search(w, kill)]
        if hits:
            bad.append(f"KILL: reads as a sentiment, not an observation "
                       f"({', '.join(hits)}). It must name the result that "
                       f"ENDS the direction.")
    budget = p.get("BUDGET", "")
    if budget and not re.search(r"\d", budget):
        bad.append("BUDGET: no quantity — a budget without a number is a wish")

    con = p.get("CONSTRUCTION", "").lower()
    wit = p.get("WITNESS", "").strip()
    if con and re.search(r"\bno\b|cannot|not possible|impossible", con):
        if not wit or wit.lower() in ("none", "n/a", "-"):
            bad.append("WITNESS: CONSTRUCTION says the violation cannot be "
                       "designed out, so C12 requires a proxy-preserving "
                       "counterexample the gate must reject")
    return bad


GOOD = """## CLAIM
GeoLift's thresholded VERDICT discards decision-relevant directional info.
## NECESSARY CONDITION
GeoLift's raw point estimate must track true theta at all.
## CHEAPEST FALSIFIER
Spearman rho of att_pct against true_att_pct on the 25,600 cached rows.
## KILL
If rho(att_pct, theta) is not materially above rho(verdict, theta) and not
comparable to the other tools', the interface hypothesis is dead and GeoLift
is not investigated further.
## SURVIVE
One nested-channel EVSI gate on the same cached rows. No new simulation.
## BUDGET
2 hours of analyst time, 0 new CPU-hours.
## INVARIANT
Blackwell: a refinement cannot be worth less than its garbling.
## CONSTRUCTION
Yes — derive every coarse prior from the fine prior through the aggregation
map, so incompatible priors cannot be expressed.
## WITNESS
n/a, the violation is unconstructible.
"""

BAD = """## CLAIM
Something is wrong with GeoLift.
## NECESSARY CONDITION
It should be informative.
## CHEAPEST FALSIFIER
Run more simulations and see.
## KILL
If it turns out not to be that interesting we can look further.
## SURVIVE
Scale up.
## BUDGET
as needed
## INVARIANT
## CONSTRUCTION
No, cannot be designed out.
## WITNESS
none
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("plan", nargs="?")
    ap.add_argument("--self-test", action="store_true",
                    help="C12 applied to this gate: a plan that looks "
                         "complete must still be rejected on KILL")
    a = ap.parse_args()

    if a.self_test:
        ok = True
        g, b = validate(GOOD), validate(BAD)
        print("self-test (the gate's own adversarial witness)\n")
        print(f"  a real plan (GeoLift gate 1)      "
              f"{'ACCEPTED' if not g else 'REJECTED — ' + str(g)}")
        ok &= not g
        print(f"  a plan with every field FILLED    "
              f"{'REJECTED' if b else 'ACCEPTED — GATE IS BROKEN'}")
        ok &= bool(b)
        for x in b:
            print(f"      - {x}")
        print(f"\n  the witness preserves the cheap proxy (all nine headings "
              f"present\n  and non-empty except INVARIANT) and violates the "
              f"invariant (KILL\n  names no observation). {'3/3' if ok else 'FAILED'}")
        return 0 if ok else 1

    if not a.plan:
        ap.error("give a plan file, or --self-test")
    bad = validate(Path(a.plan).read_text())
    if bad:
        print(f"REFUSED: {a.plan} is not a plan.\n")
        for x in bad:
            print(f"  - {x}")
        print("\nC16: expensive work requires a surviving necessary "
              "condition.\nAn entry with no KILL is not a plan and does not "
              "get run.")
        return 1
    print(f"{a.plan}: all nine fields present, KILL names an observation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
