# marketing_experimentation — research track 2

A separate, falsification-oriented research track. It does **not** continue the
lead-economics product hypothesis; it tests a different one.

> Can a vendor-neutral system decide, from a business's own historical data,
> whether a marketing experiment is worth running at all — and if so, which
> design and which estimator?

**Isolation.** The previous track is frozen at commit `7ce8c6b` and nothing
here modifies its manifests, results or report. Those stay reproducible
byte-for-byte.

**Phase discipline (brief §1, §76).** No modelling code until the landscape is
established. The first deliverables are documents, because the most likely
outcome of this research is discovering that the profession solved the
operational problem years ago — and that is far cheaper to learn from reading
than from building.

## Status

| Phase | Deliverable | State |
|---|---|---|
| 1. Domain archaeology | `docs/domain-archaeology.md` | in progress |
| 2. Product landscape | `docs/product-landscape.md` | first pass written |
| 3. Dataset reconnaissance | `docs/dataset-landscape.md` | not started |
| 4. Preregistration | `docs/preregistration.md` | blocked on 1–3 |
| 5+ | benchmark | **not started, deliberately** |

## The finding that already reshapes the hypothesis

Recast Research published a head-to-head simulation study of four open-source
geo-experiment tools in **June 2026**, with code. It reports that Meta GeoLift
is well calibrated under the null (3–5% FPR) and has a **91% false negative
rate**; that CausalImpact fires false alarms ~30% of the time; and that all
four recover a 7.5% lift point estimate within a few percentage points while
disagreeing sharply on uncertainty.

So "vendor-neutral comparison of geo estimators" is **not** an open gap. See
`docs/product-landscape.md` §1 for what the study does and does not cover.
