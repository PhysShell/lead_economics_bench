# Donor reproducibility gate — `getrecast/geolift-simulation-study`

We are building research **about whether statistical machinery can be
trusted**. Beginning it with "the environment installed, more or less" would be
an unusually elegant way to curse the project. So the donor harness passes a
gate before it produces a single new number.

**Donor:** `getrecast/geolift-simulation-study` @ `5133d37`
(2026-06-15, "Geo experiment simulation study")

```
G0  pristine clone, environment recorded
 ↓
G1  two lanes assembled, not one
      VERSION-MATCHED  R 4.5.1 + Python 3.12.8 + frozen reqs + exact SHAs
      ROBUSTNESS       host: R 4.6.1 + Python 3.11.15
 ↓
G2  upstream `make smoke`, N=5, all four estimators, in the matched lane
 ↓
G3  golden replay: DGP -> estimator -> raw output, against published rows
 ↓
G4  theta mutation at +2%, then at -5%, N=20-50
```

The two lanes answer different questions and must not be mixed:

| lane | question |
|---|---|
| **version-matched** | can we reproduce the donor at all? |
| **robustness** | how sensitive is the donor to a current environment? |

### R0 / R1 / R2 — three levels of "reproduced", and only one is passed

"Reproducible" is not one claim. The donor's chain has three links, and
passing the last one says nothing about the first two:

| level | claim | what is held fixed | state |
|---|---|---|---|
| **R0** analytical replay | published `results.jsonl` → published aggregate metrics | the raw rows themselves | **PASS** (M0) |
| **R1** generated-data replay | same DGP seed → same `true_att_level`, effect arm | the generator and its RNG | **PASS** (§4d) |
| **R2** estimator replay | same panel + same config + same seed → same estimator output | the four tools and their stacks | **PASS** (§4d) |

R0 was passed in an afternoon and is the weakest of the three: it recomputes
summary statistics from numbers somebody else produced. It cannot detect a
broken generator, a version-sensitive estimator, or a platform difference.
Publishing R0 and calling the study reproducible would be the field's
characteristic mistake, and it is available to us too, so it is written down
here as *not sufficient* before the harder levels are attempted.

**All three now pass**, which is the result §4d reports. Worth noting what
that cost: thirteen packaging defects had to be worked through first, two of
them blocking. Anyone who had stopped at R0 would have reached the same
conclusion about the donor's numbers for none of the work and none of the
entitlement to it.

R1 and R2 are separated deliberately, because they fail for different
reasons and a combined test cannot tell you which link broke. R1 failing
means the data are not the donor's data and nothing downstream is
comparable. R2 failing with R1 passing is the interesting case: same inputs,
different answers, which is a per-tool platform-sensitivity finding rather
than a defect.

**Forensic hashing, and a correction to how R1 has to work.** The plan was to
hash each regenerated panel and compare it against the donor's. **That is not
available: the donor ships no panels.** `panels/` is gitignored and absent
from the repository; only `results/raw/results.jsonl` (32,000 rows) and the
aggregates are published. There is no upstream hash to match.

A panel hash is therefore only an *internal* determinism check — same seed,
same machine, same bytes twice — which is worth having and proves nothing
about the donor.

The donor comparison has to run through a quantity that is a function of the
generated panel and *is* published. There is one, and it is sharper than
expected:

> `true_att_level = mean(Y − Y_counterfactual)` over the treated post-period,
> recorded on every row.

Checked against the published file:

| | |
|---|---|
| distinct values on the **effect** arm | **4,000** — exactly one per (scenario, iteration) |
| tools disagreeing on it for the same key | **0** of 4,000 |
| distinct values on the **null** arm | **1** (`0.0`) |

So the effect arm gives 4,000 independent fingerprints of the generated data,
each one a full-precision function of that panel's noise realisation. The
null arm gives none at all — with θ = 0, `Y ≡ Y_cf` and the quantity is
identically zero by construction, carrying no information about the panel
whatsoever. **R1 is therefore an effect-arm test.** Anyone reporting "the DGP
reproduced" from null-arm agreement would be reporting that zero equals zero.

`google_mm` then does double duty. It is OLS/TBR and expected deterministic,
and its `att_level` depends on all 21 geos across the whole window rather
than on the treated post-period alone. If its estimate matches to
floating-point tolerance, R1 and R2 are both established for that tool in one
comparison, and it becomes the instrument against which the three stochastic
tools are judged.

Per-tool input hashes are still taken, at the point *after* each adapter has
converted the panel — long/wide reshapes, date encodings, donor-pool
selection all happen there, and a hash taken only at the panel boundary would
miss an adapter that changed. That way a disagreement at R2 is attributable
to the estimator rather than argued about.

Only after G4 does an effect-size sweep begin.

---

## 1. Milestones

| | milestone | state |
|---|---|---|
| M0 | published raw metrics reproduced from `results.jsonl` | **PASS** |
| M1 | decision-theory invariants (`0 ≤ EVSI ≤ EVPI`, free info never hurts) | **PASS** |
| M2 | significance-gate bug isolated and relabelled | **PASS** |
| M3 | information ladder on two-point θ | **PASS**, conclusion limited to S0→S1 |
| M4a | pristine-clone audit (defects D1–D13 below) | **PASS** |
| M4b | version-matched runtime (R 4.5.1, Py 3.12.8) | **PASS** — 99/99 R packages, 83/83 Python pins, `renv::status()` clean |
| M4c | upstream `make smoke` in the matched lane | **PASS** — exits 0, all four adapters complete |
| M4d | host-drift smoke in the robustness lane | deferred; its library was rolled back (D8) |
| M5a | R1 — DGP reproduced via `true_att_level` | **PASS** — 320/320 exact to 1e-9 (§4d.1) |
| M5b | R2 — golden estimator replay against published rows | **PASS** — 160 rows/tool, clears the preregistered count (§4d.1) |
| M6a | θ mutation +2% (six PASS criteria, §5) | **PASS 6/6** (§5c); figure fix verified separately |
| M6b | θ mutation −5% (sign mutation) | **PASS 6/6** (§5b.1); 65.9% of estimates negative |
| M7 | coarse θ likelihood atlas | running: θ ∈ {−10,−5,0,+2,+5,+7.5,+15}%, N=25, 4 scenarios |
| M8 | continuous prior + richer action set | blocked on M7 |
| M9 | business VOI / RUN–DON'T-RUN | blocked on M8 |
| M10 | regime map / method selection | blocked on M9 |

## 2. G0 — environment, recorded rather than assumed

| component | donor (`VERSIONS.md`, `renv.lock`) | version-matched lane | robustness lane |
|---|---|---|---|
| OS / arch | macOS ARM64 (Darwin) | **Linux x86_64** 6.18.44 | same — **platform differs in both** |
| Python | 3.12.8 | **3.12.8** ✓ (uv, `--seed`) | 3.11.15 (host) |
| R | **4.5.1** (`renv.lock`) | **4.5.1** ✓ (source build, sha256 `b42a7921…`) | 4.6.1 (CRAN apt) |
| Python deps | `requirements.txt`, 83 pins | **83/83 exact**, 0 drift ✓ | same manifest, different interpreter |
| R deps | `renv.lock`, 99 packages | rebuilt from source on 4.5.1 | rebuilt on 4.6.1 |
| Make | GNU Make | GNU Make 4.3 | ok |
| C compiler | — | gcc 13.3.0 | recorded |
| CRAN reachable | — | yes (HTTP 200) | ok |
| disk free | — | 25 GB | ok |

Pinned tool versions the replay must match: CausalPy 0.8.0, PyMC 5.28.1,
ArviZ 0.23.4, CausalImpact 1.4.1, `google/matched_markets` @ `5e3cd95`,
`facebookincubator/GeoLift` @ `4d2afd4`, `augsynth` @ `65c5a6f`.

**Correction to an earlier version of this document.** It said R 4.5.1 "could
not be obtained". That was wrong: it checked two *package* sources and
declared the search exhausted. R 4.5.1 is available from at least two ordinary
routes — the official source tarball
`https://cran.r-project.org/src/base/R-4/R-4.5.1.tar.gz` (released 13 June
2025) and `rocker/r-ver:4.5.1` (linux/amd64, digest `sha256:55be3ae296dd…`).

**It has since been built from that tarball and verified here**, so this is
no longer a claim about availability but a fact about the running system:
R 4.5.1 (2025-06-13) "Great Square Root", gcc 13.3.0, reference BLAS,
configure line recorded in `repro/recast/build-r-451.sh`. Logged as **F5** in
`failures.md`, because the original claim had already been used to justify
accepting a different runtime.

So 4.6.1 is **not** accepted as the reproduction environment. It becomes the
robustness lane instead.

A second correction, to a claim that was too strong: "4.5 → 4.6 is a new minor
series and R packages are not binary-compatible across it". The accurate
statement is narrower — **R 4.6.1 is not the runtime the lockfile was created
on, and compiled dependencies are rebuilt or fetched for a different R minor
series, so this is an environment perturbation rather than an exact
reproduction.** It does not follow that any given package behaves differently.

**The platform difference is not a defect, but it must be recorded**, because
it is the most likely explanation for any numerical disagreement at G3 — and
because attributing a real disagreement to "probably the platform" without
having written the platform down first is how reproducibility studies quietly
fail.

The specific suspect is named rather than left as "the platform": **BLAS**.
The donor almost certainly ran Apple Accelerate on ARM64; this build links
reference BLAS. The two do not accumulate floating-point sums in the same
order, and all four estimators go through a matrix decomposition. So
last-digit differences are a *prediction made in advance*, recorded in
`repro/recast/README.md` alongside the build provenance. A disagreement at
the size of the `google_mm` tolerance (1e-9 relative) is consistent with it;
a disagreement larger than that is not, and must not be excused by it.

## 3. Donor defects found before running anything

None of these are complaints. Each one would have cost compute or confidence
if discovered after a long run.

### D1 — bootstrap deadlock: `.Rprofile` needs a file the repo excludes

```
.Rprofile      ->  source("renv/activate.R")
.gitignore:22  ->  renv/
```

`renv/` is absent from a pristine clone (confirmed), and `make env` runs
`Rscript -e "renv::restore()"` as its R step. R sources `.Rprofile` at
startup, so on a cold clone R can fail looking for `renv/activate.R` *before*
it is able to run the restore that would create it.

**Our handling:** bootstrap explicitly with `R --vanilla` (which skips
`.Rprofile`), install `renv`, then restore from `renv.lock`. We do **not**
patch the donor — the defect is evidence and gets recorded, not erased.

### D2 — README gives a clone URL that does not exist

```
README.md:84   git clone https://github.com/getrecast/geolift-study.git
actual repo    https://github.com/getrecast/geolift-simulation-study
```

Trivial, and pointed: a reproducibility study whose first instruction is a
404.

### D3 — `VERSIONS.md` contradicts `renv.lock` on the R version

`VERSIONS.md` records R as "(captured at install time — run `R --version`)"
while `renv.lock` pins **R 4.5.1** exactly. The manifest that a reader
consults is vaguer than the lockfile that actually governs the restore.

### D4 — two dependency specifications that disagree

| | `pyproject.toml` | `requirements.txt` |
|---|---|---|
| PyMC | `pymc>=5.10` | `pymc==5.28.1` |
| arviz | `arviz>=0.15` | `arviz==0.23.4` |
| matched-markets | `git+...` (no pin) | resolved pin |

`requirements.txt` states its own provenance — "Frozen dependencies for exact
reproduction. Generated from Python 3.12.8 on macOS (ARM64), March 2026".
`make env` installs **both**, `requirements.txt` first and then `pip install
-e .`, so the loose constraints run second and could in principle move a
pinned version.

**Our handling:** install from `requirements.txt` only, then `pip install -e .
--no-deps`.

### D5 — no licence

No `LICENSE`, `LICENSE.md` or `LICENSE.txt` in the repository, and the GitHub
API reports no SPDX licence. Reading the artefact, recomputing from published
outputs and citing it are ordinary research use. **Forking the harness into a
product is not available without a grant from the authors.**

**Our handling:** we do not vendor donor source into this repository. We
record bootstrap instructions and content hashes, and keep the clone external
at `/home/user/getrecast/geolift-simulation-study`.

### D6 — `make smoke` begins by deleting the published results

```make
smoke: clean ...
clean:
	rm -rf panels/ results/ figures/
```

`results/raw/results.jsonl` is the 32,000-row artefact every golden
comparison is measured against. It is git-tracked, so it survives — but an
acceptance target whose first act is deleting the thing it accepts against is
a trap for anyone running it on a dirty tree.

**Our handling:** the reference clone's `results/` is `chmod a-w` and never
runs `make`. A disposable clone (`git clone --shared`) at
`/home/user/donor-smoke` takes every make target.

### D7 — the figure layer is not parameterised in θ, while everything else is

See §5a. `plot_forest.py` and `plot_ci_gallery.py` hard-code the true effect
at 7.5% while the metrics layer derives it from the data. Latent in the
published study, because 7.5% was the truth; live the moment anyone varies θ,
and silent when it fires.

### D8 — two dependencies resolvable only through an authenticated, rate-limited API, and a restore that is all-or-nothing

Found by running the restore, not by reading the lockfile.

`renv.lock` pins two packages to GitHub commits rather than to CRAN:

```
GeoLift   2.7.5  GitHub  facebookincubator/GeoLift  @ 4d2afd4
augsynth  0.2.0  GitHub  ebenmichael/augsynth       @ 65c5a6f
```

renv resolves a GitHub pin through
`https://api.github.com/repos/<owner>/<repo>/tarball/<sha>`. On this network
that endpoint returns **403**, as does `codeload.github.com`. Both packages
failed to download; the other 92 built successfully over 47 minutes.

**Two things are worth separating here.** The 403 is this environment's, not
the donor's. The fragility is the donor's: the pinned version of **GeoLift —
one of the four tools the study is actually about** — has exactly one
published installation route, and it runs through an API that is
rate-limited, often requires a token, and is not guaranteed to serve
arbitrary commit tarballs indefinitely. There is no vendored copy, no CRAN
fallback, and no recorded hash of what that tarball should contain.

**And the failure is total, not partial — more total than first recorded.**
An earlier version of this section said 92 packages installed and 2 failed,
leaving an unusable project. Checking the library afterwards:

```
/home/user/donor-smoke/renv/library/.../x86_64-pc-linux-gnu   0 packages
/root/.cache/R/renv/cache/.../x86_64-pc-linux-gnu            92 packages
```

renv installs into a staging area and commits to the library only if **every**
package succeeds. Two failures out of 94 therefore roll back all 92 — the
project library ends up **empty**, not partially populated. The cache keeps
the builds, which is why a retry is fast, but nothing is installed.

And `renv/activate.R` is written at the end of a successful restore, so it is
never created. The donor's `.Rprofile` sources exactly that file, so every
`Rscript` in the repository dies at start-up. This is **D1 compounding**: the
bootstrap deadlock is not a cold-clone problem, it returns after *any*
interruption anywhere in a 47-minute build — a failed download, a rate limit,
a container restart.

The practical shape of it: a 47-minute all-or-nothing transaction whose last
two steps depend on a third-party API. That is not a robust way to distribute
a reproducibility study, and it is the single thing most worth fixing in the
donor.

**Our handling**, and it is worth stating in full because it is a deviation
from the donor's own install path:

1. The 92 cached builds are linked into the project library directly. A renv
   library *is* symlinks into `renv/cache`, so this is the layout renv would
   have produced had it committed the transaction.
2. `GeoLift` and `augsynth` are built from a `git clone` checked out at the
   pinned SHA, which git serves normally on this network. That is the same
   tree the API tarball would have contained — `git archive` of a commit and
   the API's tarball of that commit are the same content — so this is a
   change of **transport**, not of version. (`augsynth` must be installed
   first; `GeoLift` depends on it.)
3. The built trees' hashes are recorded:

   | package | tree sha256 |
   |---|---|
   | `GeoLift` @ `4d2afd4` | `7f6b0a4dfabcb0a9816f85244da88567a181e28f8cfa95d9904787648e052a49` |
   | `augsynth` @ `65c5a6f` | `98d03cf82dc90b0511f0a10738740f2dfbe80f6beee3d0fd94ec236c43fdbedd` |

4. `renv::activate()` is called explicitly to write the file the aborted
   restore never reached.
5. `RemoteSha` and the other `Remote*` fields are written into the two
   installed `DESCRIPTION`s, which `R CMD INSTALL` from a plain checkout does
   not do. **This is the step that matters**: without it renv reports both as
   `(Unknown Source)` and the provenance is a claim in a log file. With it,
   `renv::status()` verifies the installed commit against the lockfile's
   pinned SHA, and the substitution becomes machine-checkable.

**Verification, not assertion.** Afterwards, against the lockfile's 99
packages: **0 missing, 0 version mismatches**, and `renv::status()` reports
no out-of-sync package. An ordinary `Rscript` in the project — the thing D1
broke — starts cleanly and loads the stack at the pinned versions:

```
R 4.5.1 (2025-06-13)    renv 1.2.0 (pinned)
arrow 23.0.1.2   jsonlite 2.0.0   CausalImpact 1.4.1
GeoLift 2.7.5    augsynth 0.2.0   bsts 0.9.11   MarketMatching 1.2.1
```

One residual, recorded rather than swept: `renv::status()` still lists
`RcppEigen` as "installed, recorded, not used" — a dependency renv cannot see
being used. It is a bookkeeping note, not a version discrepancy.

**What a donor could do about it**, since four of the audit's eight findings
are now packaging: record the expected tarball hashes, or vendor the two
GitHub dependencies, or note the CRAN-only subset that works without them.
Any of the three would have turned a dead stop into a warning.

### D9 — the lockfile pins a package version, not the build that version needs

Found by the smoke run failing at the first panel:

```
Error in parquet___WriterProperties___Builder__create()
```

`renv.lock` pins `arrow 23.0.1.2` and that is exactly what was installed. But
the R `arrow` package is a thin wrapper over a C++ library it builds or
downloads at install time, and what got built was the **minimal** libarrow:

```
acero TRUE | dataset FALSE | parquet FALSE | json FALSE
snappy FALSE | gzip FALSE | zstd FALSE | lz4 FALSE | bz2 FALSE
```

The donor's panels are **Parquet**. So a correctly-pinned, correctly-versioned
`arrow 23.0.1.2` cannot read or write the study's own data format. Twenty-five
minutes of compilation produced a package that satisfies the lockfile and
cannot run the pipeline.

**This is not a variant of D8 and it is more interesting.** D8 is a package
that could not be fetched — loud, obvious, fatal at install time. D9 is a
package that installed cleanly, reports the pinned version, satisfies
`renv::status()`, and is silently missing the one capability the study needs.
A lockfile records *what* was installed. It does not record *how it was
built*, and for any package that compiles or downloads a backend at install
time — `arrow`, and in a different way BLAS under R itself — the build
configuration is a free variable that no lockfile in common use captures.

**Our handling.** `apache.jfrog.io`, where `arrow` fetches prebuilt libarrow,
answers 200 here; the first build simply fell back to minimal without using
it. Rebuilt with `LIBARROW_MINIMAL=false` and `NOT_CRAN=true`, installed into
the project library directly rather than through the renv cache — a
differently-configured build of the same version must not be shared with the
robustness lane, or the two lanes stop being independent.

After the rebuild (5 minutes, using the prebuilt binary the first attempt
never reached):

```
arrow 23.0.1.2
parquet TRUE | dataset TRUE | snappy TRUE | gzip TRUE | zstd TRUE
round-trip of a panel-shaped frame: TRUE
```

**Recorded as a limit on the version-matched claim**, alongside BLAS. The
donor published neither its libarrow build flags nor its BLAS backend, so
neither is matched, and neither can be. What can be stated is narrower and
is now stated that way: the version is the pinned one, and the capability
the pipeline needs is present and verified by round-trip rather than assumed
from the version string.

**The general lesson, which is the reusable part.** A version check is not a
capability check. `arrow 23.0.1.2` was true both before and after the
rebuild; only one of those two could open a Parquet file. Any environment
audit that stops at versions will pass a build like the first one. The
capability probe — write a frame shaped like the study's data, read it back —
costs three lines and is the only thing that caught it.

### D10 — data generation aborts on a graphics failure

Minor, and separable. `make panels` runs `generate_panels.R`, which writes
the 40 Parquet panels **and then** a `scenario_timeseries.png`. On a headless
R without a working bitmap device the `png()` call fails, the script halts
non-zero, and `make smoke` stops — *after* every panel has already been
written correctly to disk.

So a graphics device is a hard dependency of the **data** stage, which has
nothing to do with plotting. On a minimal or containerised R, the study
cannot generate its own data.

Low severity and a one-line fix upstream (wrap the figure in `tryCatch`, or
move it to the `figures` target where it belongs). Recorded because it is a
third instance of the same pattern as D1 and D8: an incidental coupling that
turns a cosmetic failure into a total one.

**And the cause here was ours, not the donor's**, which is why it is worth
being precise. This R was configured `--with-x=no` (no X11 headers in the
container), which leaves `bitmapType` at `"Xlib"` even though cairo is
compiled in and `capabilities()["cairo"]` is `TRUE`. Fixed in
`Rprofile.site` of this build — `options(bitmapType = "cairo")` — not in the
donor. It is a property of the version-matched lane's R, recorded with the
rest of the build provenance, and it would not occur on the donor's macOS.

### D11 — the Makefile's `RSCRIPT` variable is a false affordance

`Makefile` parameterises the R interpreter:

```make
RSCRIPT := Rscript
panels:
	$(RSCRIPT) src/R/generate_panels.R --n_iterations $(N_ITERATIONS)
```

which reads as an invitation to point the pipeline at a chosen R. It governs
**only** `make panels`. The GeoLift and CausalImpact stages run as
subprocesses from the Python layer, and both hardcode the string:

```python
run_tools.py:115   "Rscript", "src/R/run_geolift.R", ...
run_tools.py:162   "Rscript", "src/R/run_causalimpact.R", ...
```

So `make smoke RSCRIPT=/path/to/R` generates data with the R you chose and
estimates with whatever `Rscript` PATH happens to resolve. Two of the four
tools silently leave the environment you specified.

**Low severity on a machine with one R. Total on a machine with two**, which
is the situation any reproducibility comparison is in by construction.

**How it surfaced, which is the part worth keeping.** It did not surface as a
wrong number. It surfaced as `att_pct: null` on 40 of 40 rows for both R
tools, with `runtime_seconds: 0` — the subprocesses died instantly because
the *other* R's renv library was empty (its restore had been rolled back by
the same D8 mechanism). The donor's own `smoke_test.py` caught it:

```
[FAIL] causalimpact has non-null att_pct — 40 records, all null
[FAIL] geolift has non-null att_pct — 40 records, all null
```

**Had that other library been complete, this would have produced plausible
numbers from a mixed environment and nothing would have complained.** A
broken library made a silent contamination loud. That is luck, and it is
recorded as `F11` in `failures.md` because the mistake was ours: the
two-lane isolation was asserted and not verified.

**Our handling.** `PATH=/opt/R/4.5.1/bin:$PATH` for the whole run, and the
run script now prints which `Rscript` it resolved before starting, so the
lane is evidenced on every run rather than assumed once.

### D12 — half the study's precision is lost to an unoverridden library default

§4a established that `geolift` and `causalimpact` publish every level and
interval at exactly 4 decimal places while `causalpy` and `google_mm` publish
full float64. The cause is one unpassed argument.

Neither R adapter rounds anything. Both end with:

```r
run_geolift.R:165        write(toJSON(result_json, auto_unbox = TRUE, pretty = TRUE, na = "null"), ...)
run_causalimpact.R:164   write(toJSON(result_json, auto_unbox = TRUE, pretty = TRUE, na = "null"), ...)
```

and `jsonlite::toJSON` has `digits = 4` as its **default**:

```
default     {"att_level":-290.8473,"att_pct":-0.0776}
digits = NA {"att_level":-290.847289091517,"att_pct":-0.0775934389776986}
```

So two of the four tools in a published methods comparison report their
results at four decimal places because nobody passed `digits = NA`. The
Python adapters write full precision, so the study's output precision is
inconsistent across tools for a reason unrelated to the tools.

**What it costs.** It is why the G3 tolerance for those two had to be
censored at 5e-5 (§4b), and why their cross-platform determinism **cannot be
measured below that from the published artefact**. The G3 result — worst
difference exactly 0 on 40/40 rows — means "identical after rounding to four
decimals", not "identical computation". The stronger claim is unavailable,
and it is unavailable because of a default argument rather than anything
about GeoLift or CausalImpact.

**Does it contaminate anything of ours?** Checked rather than assumed. The
information ladder uses `att_pct` and `ci_width` as KDE dimensions. The
quantisation is 5e-5 on a level near 290 (≈1.4e-7 relative) and ~1e-4 on
interval bounds expressed as proportions, against a Scott's-rule bandwidth
near 0.07 — a ratio of roughly 700. Far too fine to affect a density
estimate, and the S1/S2 results are unaffected.

**Fix: one argument.** `digits = NA`. It would also make the D-series
observation in §4a — that three of four tools are deterministic — verifiable
at full precision instead of censored.

### D13 — crash recovery duplicates rows when the config gains an option

`run_tools.py` scans an existing `results.jsonl` and skips work already
done — sensible for a study whose full run takes hours. The CausalPy branch
decides at tool granularity:

```python
run_tools.py:224   cp_keys = [(scenario, effect_label, iteration, f"causalpy_{pt}")
                              for pt in cp_config["posteriors"]]
run_tools.py:232   need_cp = any(k not in completed for k in cp_keys)
```

If **any** posterior type is missing it re-runs CausalPy, and the adapter
writes **all** configured types. So enabling a second posterior type on an
existing results file appends a fresh copy of the one already present. The
file ends with doubled rows, no warning, and a schema that still validates.

Observed exactly: 640 rows from the previous run, plus 320 appended
(`y_hat` + `mu` for 160 cells) = 960, with `y_hat` at twice the expected
count while the other three tools were skipped entirely.

**Attribution, honestly.** The trigger was ours — the F8 script omitted
`make clean`, which `make smoke` would have run. But `make all` has the same
shape, and the failure mode is silent duplication rather than an error, which
is what makes it worth a number. Low severity, narrow trigger, and a
disproportionate consequence: any downstream join on the run identity pairs
arbitrary rows. It did, in our own probe — recorded as **F12**.

**Fix upstream:** make the recovery key `(tool, posterior_type)` for the
write as well as the read, or refuse to append to a file whose configured
posteriors differ from those already in it.

### Audit summary

| | issue | severity | our workaround | upstream would need to change? |
|---|---|---|---|---|
| D1 | `.Rprofile` sources a gitignored file; `make env` can't bootstrap a cold clone | **blocking** | `R --vanilla -f bootstrap.R` | yes — one guard in `.Rprofile` |
| D2 | README clone URL 404s | cosmetic | use the real URL | yes, one line |
| D3 | `VERSIONS.md` vaguer than `renv.lock` on R | low | trust the lockfile | yes, regenerate |
| D4 | `pyproject.toml` ranges vs `requirements.txt` pins, loose install runs second | **material** | `requirements.txt`, then `-e . --no-deps` | yes — reorder or drop one |
| D5 | no licence | **blocking for reuse** | external wrapper, no vendored source | yes — add one |
| D6 | `make smoke` deletes published results | **material** | read-only reference + disposable clone | yes — guard `clean` |
| D7 | plots hard-code 7.5% truth | latent → **material on any θ ≠ 7.5%** | read `metadata.json` in the mutation diff | yes, two constants |
| D8 | GeoLift + augsynth resolvable only via `api.github.com` tarball; restore is all-or-nothing, rolls back all 92 | **blocking** where that API is restricted | build from `git` at the pinned SHA, write `Remote*` fields, `renv::activate()` by hand | yes — hashes, a vendored copy, or a documented CRAN-only subset |
| D9 | `arrow` satisfies the lockfile but built minimal: no Parquet, the study's own panel format | **blocking, and silent** — installs clean, reports the pinned version | rebuild with `LIBARROW_MINIMAL=false`, outside the shared cache | yes — record the build flags, or test the capability |
| D10 | `make panels` aborts on a `png()` failure after writing every panel correctly | low — but total where it fires | `options(bitmapType="cairo")` in our R build; cause was ours, not the donor's | yes — `tryCatch`, or move the figure to the `figures` target |
| D11 | `RSCRIPT` governs only `make panels`; two adapters hardcode `"Rscript"` | low with one R, **total with two** | set `PATH` for the whole run and print the resolved interpreter | yes — thread the interpreter through, or read it from config |
| D12 | two of four tools publish at 4 dp because `jsonlite::toJSON` defaults to `digits = 4` | low for the donor's own claims, **blocking for anyone measuring determinism** | censor the tolerance at 5e-5 and say so | yes — one argument, `digits = NA` |
| D13 | crash recovery re-runs CausalPy and appends **all** posterior types, duplicating existing rows | low, narrow trigger, **silent** | `make clean` before a config change; refuse duplicated join keys | yes — key the recovery on `(tool, posterior_type)` |

Eleven of the thirteen are one-line or one-file fixes. That is the characteristic
shape of reproducibility failure in this field: not deep methodological
error, but a handful of unguarded lines that make a correct study hard to
re-run. Worth stating plainly — **the donor's statistics have survived every
one of these intact. All thirteen are about packaging**, and one of them,
D10, turned out on inspection to be ours rather than the donor's.

The two that are not one-line are the two that matter most, and they are the
same failure seen twice: **D1 and D8 are both "the environment cannot
bootstrap itself"**. A `.Rprofile` that needs a file the restore creates, and
a restore that writes that file only if all 94 packages succeed — including
two that depend on a rate-limited API. Either alone is survivable. Together
they mean any interruption, anywhere in a 47-minute build, leaves a
repository where no R script will start.

**D9 is the one worth generalising from**, because it is the only finding
here that a lockfile cannot in principle prevent. A lockfile records *what
version* was installed. It does not record *how it was built* — and for any
package that compiles or downloads a backend at install time, the build
configuration is a free variable. `arrow` without Parquet passes every check
renv can perform and cannot open the study's data. The same class of gap
covers BLAS under R itself. "Pinned" and "reproducible" are not the same
claim, and the distance between them is exactly the kind of thing this track
exists to price.

A useful generalisation for the research question itself: every one of these
would be invisible to a reader, a reviewer, or a citation. They are visible
only to someone who runs the thing. That is the gap this track keeps finding,
in a different form each time — and it is the argument for the whole gate,
since the alternative was to accept published numbers and build on top of
them.

## 4. G3 tolerances, fixed before the replay

Defined in advance so a disagreement cannot be rationalised afterwards.

### 4a. A revision made before the replay, and why that is legitimate

An earlier version of this table split the tools into "deterministic, tight"
(`google_mm`, `geolift`) and "MCMC, platform-sensitive, loose" (`causalpy`,
`causalimpact`). **That split is wrong, and the donor's own published data
says so** — no replay required.

The test that shows it needs nothing but `results.jsonl`. Null and effect
panels of the same iteration share a seed and therefore share their entire
pre-treatment data; the effect is a multiplicative shift applied to the
treated geo's post-period alone. So for an estimator that is a deterministic
function of the panel,

```
att_level(effect) − att_level(null) − true_att_level(effect)  ==  0
```

per iteration, exactly. Across `A1`'s 1,000 iterations:

| tool | median residual | max residual | as % of the true effect | A1 / A2 / A3 / A4 |
|---|---|---|---|---|
| `google_mm` | **5.7e-14** | 3.4e-13 | 0.0000% | machine epsilon in all four |
| `geolift` | **2.9e-5** | 9.5e-5 | 0.0000% | 2.9–3.1e-5 in all four |
| `causalimpact` | **3.0e-5** | 9.5e-5 | 0.0000% | 2.9–3.1e-5 in all four |
| `causalpy` | **3.69** | 12.67 | **1.30%** | 1.30 / 1.33 / 1.33 / **3.18%** |

`google_mm` sits at machine epsilon — pure linear algebra, as expected.

**`causalimpact` is deterministic despite being BSTS.** `run_tools.py:173`
passes `--seed <iteration>` and `run_causalimpact.R:98` calls `set.seed()`
before fitting; R's Mersenne-Twister stream does not vary by platform, so its
draws should reproduce across macOS and Linux exactly.

**And the 3e-5 floor is not a solver — it is output formatting**, which an
earlier version of this section got wrong. The giveaway is that the residual
is a *constant absolute* 3e-5 across two different tools and four scenarios
spanning very different magnitudes. Reading the decimal places in the
published text:

| tool | `att_pct` | `att_level` | `ci_lower` | `ci_upper` | `ci_*_level` |
|---|---|---|---|---|---|
| `causalimpact` | 20 | **4** | **4** | **4** | **4** |
| `geolift` | 20 | **4** | **4** | **4** | **4** |
| `causalpy` | 20 | 17 | 20 | 20 | 16–17 |
| `google_mm` | 20 | 16 | 20 | 19 | 16 |

The two R adapters round every level and interval to **4 decimal places** on
output. A half-ULP of that is 5e-5, and the observed residual — which combines
three such values — has a median of 3e-5 and a maximum of 9.8e-5. That
accounts for it exactly.

So `geolift` and `causalimpact` are **as deterministic as `google_mm`**; the
donor simply did not publish enough digits to see it. This has a direct
consequence for the replay, below: those two cannot be tested more tightly
than the donor published, and a tolerance tighter than 5e-5 would fail for
reasons that have nothing to do with reproduction.

`att_pct` looks full-precision for all four, but for the R pair that is an
illusion — it is computed downstream in Python from the already-rounded level,
so it carries the same quantisation (about 1e-8 relative, given a
counterfactual mean near 3,750). Comparisons are made on `att_level`, where
the precision is visible, rather than on `att_pct`, where it is hidden.

`causalpy` is the only tool carrying genuine Monte Carlo noise in its
*published point estimate*, at 1.3% of the effect being measured — rising to
**3.2% on A4**, the short panel with only 30 pre-period days. Less
pre-period data, wider posterior, noisier predictive mean: the pattern is
coherent, which is mild evidence for the `y_hat` explanation below.

**The mechanism for `causalpy` is not established.** Two guesses have already
failed: it is not the seed (`random_seed = iteration`, `run_causalpy.py:100`)
and it is not standardisation drift (`run_causalpy.py:71–73` standardises on
the pre-period, which is identical across arms). The remaining candidate is
that the published rows are all `posterior_type = "y_hat"` — the posterior
*predictive*, whose mean carries simulated observation noise — while the
adapter's `"mu"` variant, which would not, was never published. That cannot
be confirmed from the donor's artefacts, so it is written down as an open
question and as a specific thing for M5b to test by running both.

Revising a tolerance before seeing any replay output is exactly when it is
allowed. Recorded here, with its evidence, so the revision is auditable and
cannot later be mistaken for a tolerance widened to fit a result.

### 4b. The tolerances

Ten fixed iterations per tool for `google_mm` and `geolift`, twenty for
`causalpy` and `causalimpact`, on `A1`, both arms, comparing `att_pct`,
`att_level`, `ci_lower`, `ci_upper`, `significant` and available diagnostics.

| tool | class | per-row tolerance on `att_level` | set by | verdict if exceeded |
|---|---|---|---|---|
| `google_mm` | exact | **1e-9 relative** | its own machine-epsilon determinism | BLAS/compiler difference — investigate, do not excuse |
| `geolift` | exact | **5e-5 absolute** | the donor's 4-dp output, not the tool | real finding |
| `causalimpact` | exact (seeded) | **5e-5 absolute** | the donor's 4-dp output, not the tool | R RNG or BSTS solver differs across platform — a finding |
| `causalpy` | stochastic | see below | its own posterior | — |

The two 5e-5 entries are **censored tolerances**: they are as tight as the
published artefact allows, not as tight as the tools deserve. If those two
agree at 5e-5 the honest statement is "reproduced to the precision the donor
published", and the residual determinism question stays open. Writing that
down now prevents it being reported later as a stronger result than it is.

For `causalpy`, a per-row equality test is not meaningful and would fail for
the right reasons. It is judged on two levels instead, against its own noise
scale rather than against zero. From the published `A1` runs its sampling SD
of `att_pct` is **7.22 pp** with a standard error of the mean of **0.228 pp**
over 1,000 iterations:

- **Level 1, per row** — `|Δatt_pct| ≤ 0.25 ×` its own median CI half-width
  (10.37 pp for the effect arm), i.e. **2.59 pp**. A row outside that is
  flagged, not fatal.
- **Level 2, distribution** — over the 20 fixed iterations: `|Δ mean att_pct|
  ≤ 2 × SE` on that sample, plus agreement on CI-width distribution, coverage
  and `significant` rate. **This is the binding test.** Level 1 exists only
  to catch a tool that has gone somewhere else entirely.

For the three exact tools, `significant` must agree on **every** row. For
`causalpy`, disagreement is tolerated on rows whose interval bound sits within
Level 1's tolerance of zero, and counted.

### 4c. Why the profile is worth having anyway

"Which of these tools gives the same answer on a different machine" is a
question a buyer would ask and nobody has published. The table in §4a is
already a partial answer derived from the donor's own artefacts: three of four
are deterministic to at least 1e-7, and the fourth publishes a point estimate
with 1.3% noise on it. A practitioner comparing two vendors' geo-lift readings
would want to know that before attributing the gap to the marketing.

**A note on what §4a is not.** It shows that three tools are deterministic
*on one machine*. Cross-platform determinism is a stronger claim and is
exactly what the replay tests. Reference BLAS here against Accelerate there
can move `google_mm`'s machine-epsilon agreement without any of these tools
being at fault.

## 4d. G3 result: the donor reproduces

Run at N=5 per scenario, all four scenarios, both arms — 160 rows, 40 per
tool. Tolerances as fixed in §4b, before any of this existed.

**`make smoke` exits 0.** The donor's own acceptance target passes unmodified
in the version-matched lane, which settles G4 criterion 3: all four adapters
complete.

| level | verdict | |
|---|---|---|
| **R1** DGP | **PASS** | 80/80 `true_att_level` exact to 1e-9, max abs 4.6e-13; 20 distinct fingerprints over 20 panels |
| **R2** estimators | **PASS** | all four, below |

| tool | result | `significant` |
|---|---|---|
| `google_mm` | **40/40** within 1e-9 relative, **worst 2.5e-13** | 40/40 |
| `geolift` | **40/40**, worst **exactly 0** | 40/40 |
| `causalimpact` | **40/40**, worst **exactly 0** | 40/40 |
| `causalpy` | mean Δ **+0.0010pp** against 2×SE = 0.0122pp; CI width ×1.012 | 39/40 |

### What this establishes, stated no more strongly than it is

**The donor's numerical results reproduce on a different operating system, a
different architecture and a different BLAS.** macOS ARM64 with (presumably)
Accelerate → Linux x86_64 with reference BLAS. Given how the audit above
reads — eleven packaging defects, two of them blocking — that is worth
saying plainly: **the packaging is fragile and the science underneath it is
sound.** Those are separate findings and the first does not impeach the
second.

The BLAS prediction made in §2 was right in both direction and size:
`google_mm` disagrees at 2.5e-13 relative, a few ULPs accumulated through a
decomposition, against a preregistered tolerance of 1e-9. Recorded as a
prediction beforehand precisely so that it could not be used as an excuse
afterwards; it was neither needed as one nor contradicted.

`geolift` and `causalimpact` came back with a worst-case difference of
**exactly zero** — identical at 4 decimal places on all 40 rows. That is
the censored tolerance doing its job: the honest claim is "identical to the
precision the donor published", and the determinism below that precision
remains untested because the artefact cannot test it.

### The by-product: a cross-platform reproducibility profile

Nobody has published this, and a buyer comparing two vendors' geo-lift
readings would want it:

| tool | does it give the same answer on a different machine? |
|---|---|
| `google_mm` | **Yes, to machine precision.** OLS/TBR, no RNG |
| `geolift` | **Yes**, exactly, at the precision it reports |
| `causalimpact` | **Yes**, exactly, at the precision it reports — seeded BSTS |
| `causalpy` | **Distributionally.** Individual runs differ by Monte Carlo noise of ~1.3% of the effect |

Three of four are reproducible run-for-run across platforms. The fourth is
reproducible in aggregate and not per-run — which is not a defect, but it is
the sort of thing that should be known before two teams argue about why their
numbers differ by a point.

**Caveat on the count.** §4b asked for 10 fixed iterations for the
deterministic pair and 20 for the stochastic pair, on A1. The run above gives
10 rows per tool on A1 (5 iterations × 2 arms) and 40 across all four
scenarios. So the preregistered A1 count was **met for `google_mm` and
`geolift` and under-met for `causalpy` and `causalimpact`**.

### 4d.1 The same test at the full preregistered count

Re-run at **20 iterations per scenario** — 640 rows, **160 per tool**, which
clears the preregistered count in every cell with room to spare. Both results
are kept; the first is not deleted now that a larger one exists.

| | N=5/scenario (40/tool) | **N=20/scenario (160/tool)** |
|---|---|---|
| **R1** DGP | 80/80 exact, max 4.6e-13 | **320/320 exact, max 8.0e-13** |
| `google_mm` | 40/40, worst 2.5e-13 rel | **160/160, worst 1.3e-12 rel** |
| `geolift` | 40/40, worst 0 | **160/160, worst 0** |
| `causalimpact` | 40/40, worst 0 | **160/160, worst 0** |
| `causalpy` | +0.0010pp vs 2×SE 0.0122 | **+0.0009pp vs 2×SE 0.0061** |
| `significant` agreement | 159/160 rows | **636/640 rows** |

**G3 verdict: PASS**, at four times the evidence and with every conclusion
in §4d unchanged.

Two details worth reading rather than skimming:

- `causalpy`'s mean difference stayed at ~+0.0009pp while its standard error
  **halved** (0.0122 → 0.0061 for 2×SE), exactly as √n predicts. The
  agreement is therefore not a tolerance too loose to fail — it survives a
  bar twice as tight.
- Its four `significant` disagreements out of 160 (97.5% agreement) are the
  expected consequence of a point estimate carrying 1.3% Monte Carlo noise
  landing near a threshold. §4b preregistered that such rows are tolerated
  and counted rather than silently excused; they are counted here.
- `google_mm`'s worst relative difference grew from 2.5e-13 to 1.3e-12
  with 4× the rows — the maximum of a larger sample of floating-point noise,
  not a drift. Still three orders of magnitude inside its 1e-9 tolerance.

## 5. G4 — the mutation test, and what it is really checking

Before any sweep: `A1`, θ = **+2%**, N = 20–50, then θ = **−5%**. Not for
statistics — to find out whether the pipeline is parameterised in θ or merely
appears to be. A generator can be fully parameterised while the analysis
quietly is not.

**PASS requires all six:**

| | criterion |
|---|---|
| 1 | the generator accepts an arbitrary θ |
| 2 | the recorded true ATT reflects +2%, not a hard-coded 7.5 |
| 3 | all four adapters complete without error |
| 4 | the output schema is unchanged |
| 5 | downstream metrics do not assume `effect_label` means exactly 7.5% |
| 6 | the decision layer can consume θ = 2% |

Criterion 5 is the one to distrust. The donor README describes only `null`
and `effect`, so a hidden binarity has somewhere comfortable to hide.

### 5a. Static audit, done before spending any compute

Reading the source first costs an hour and can save a 50-iteration run that
produces confidently wrong figures. The result is more interesting than a
straight pass or fail: **the numeric pipeline is parameterised in θ and the
figure layer is not.**

| | criterion | verdict | evidence |
|---|---|---|---|
| 1 | generator accepts arbitrary θ | **PARTIAL** | `generate_panels.R:41` `effect_sizes <- c(0.0, 0.075)` is a top-level constant. `parse_cli()` exists at :108 but wires only `--n_iterations` and `--output_base`. However `effect_pct` is a genuine *function argument* down to :265, so the gap is one unexported flag, not a refactor |
| 2 | true ATT reflects θ | **PASS** | `compute_true_att()` derives from `mean(Y − Y_counterfactual)` over the treated post-period; `generate_panels.R:265` sets `Y[post] <- Y_cf[post] * (1 + effect_pct)`. No constant anywhere in the chain |
| 3 | four adapters complete | untested | needs M4c |
| 4 | schema unchanged | **PASS** | `effect_pct` is already a first-class column and a grouping key in `compute_metrics.py:125`. θ = 0.02 needs no schema change |
| 5 | metrics free of 7.5 | **SPLIT — see below** | |
| 6 | decision layer consumes θ = 2% | **PASS** | `two_point_problem(pi, c_fp, c_fn, effect=0.075)` already takes `effect` as a parameter; 0.075 is only the default |

**Criterion 5, in detail.** The metrics layer is clean and the plotting layer
is not:

| file | θ-safe? | |
|---|---|---|
| `src/python/run_tools.py:441` | **yes** | iterates `meta["effect_sizes"].items()` — discovers arms from `metadata.json` rather than assuming two known ones |
| `analysis/compute_metrics.py` | **yes** | `true_att_pct` from the data; `bias = avg − true` |
| `analysis/audit_metrics.py` | **yes** | same, independently |
| `analysis/generate_tables.py` | **yes** | selects by label only, no magnitude |
| `analysis/plot_forest.py:66–67` | **NO** | `col_titles = ["7.5% Effect", …]`, `true_values = {"effect": 7.5, "null": 0.0}` |
| `analysis/plot_ci_gallery.py:42` | **NO** | `TRUE_ATT = 0.075`, drawn as "True ATT (7.5%)" |

So a θ = +2% run yields **correct numbers and lying figures**: bias and
coverage computed against the true 2%, while the forest plot draws its
reference line at 7.5% and titles the column "7.5% Effect". Every estimator
would appear massively biased, and the error is in the axis.

This is worth more as a finding than as a complaint. The donor's own
published figures are sound because 7.5% happened to be the truth. The defect
only fires when someone does what the parameterisation invites — and it fires
silently, in the direction of a dramatic result.

**A second, structural one.** `effect_labels <- c("null", "effect")` is used
as a *directory name* (`panels/{scenario}/{effect_label}/`) and as the arm key
throughout. Arms are keyed by label, not by magnitude, so a second θ
overwrites the first. Two effect sizes cannot coexist on disk. For a
two-truth study that is invisible; for the θ-atlas at M7 it is structural, and
the label has to encode magnitude (`eff_p020`, `eff_m050`) before any sweep
runs.

**Handling.** The donor is not patched in place. The mutation runs in the
disposable clone, and the change is recorded in this repository as a diff
rather than as vendored source (D5: no licence):
`repro/recast/theta-mutation.patch`.

It came out larger than the "roughly three lines" estimated here, because
writing it found a **third** θ-coupling the static audit had missed:
`plot_ci_gallery.load_results()` filters on `effect_label == "effect"` — a
literal label, which selects nothing once labels carry magnitude. So the
audit's own count was an undercount, found only by making the change rather
than describing it.

The patch is verified rather than sketched: `git apply --check` clean
against a pristine clone at `5133d37`, both plot files compile after
applying, `generate_panels.R` parses, and the label function returns
`null`, `effect`, `eff_p020`, `eff_m050`, `eff_p150` for the values it will
be given.

### 5c. M6a result — θ = +2%, G4 PASS 6/6

**Reproduce:** `repro/recast/theta-mutation.patch`, then
`Rscript src/R/generate_panels.R --n_iterations 20 --effect_sizes 0,0.02`,
then `repro/recast/g4_check.py --theta 0.02`.

640 rows, 20 iterations × 4 scenarios × 2 arms. Arms on disk:
`null`, `eff_p020` — the magnitude-bearing labels working, so a second θ no
longer overwrites the first.

| | criterion | | |
|---|---|---|---|
| 1 | generator accepts arbitrary θ | **PASS** | `effect_pct` present: 0.0, 0.02 |
| 2 | true ATT reflects θ, not 7.5 | **PASS** | median `true_att_pct` = **+0.020000** |
| 3 | all four adapters complete | **PASS** | 160/160 usable rows, each tool |
| 4 | output schema unchanged | **PASS** | identical to the published artefact |
| 5 | metrics free of a hard-coded 7.5 | **PASS** | `metrics.csv` records +2.000pp; bias identity residual **0.0000pp** |
| 6 | decision layer consumes θ | **PASS** | `two_point_problem(effect=0.02)` |

**So the static audit's verdict was right, including where it was uncertain.**
Criterion 1 was scored PARTIAL there — the generator was parameterised
internally but the flag was not exported — and one added flag was indeed all
it took. Criterion 2's worry, that a hard-coded `0.075` sat somewhere in the
generator, was unfounded: the recorded truth is exactly `+0.020000`.

#### What criterion 5 does and does not cover

The checker verifies the **numbers**. `make figures` is not part of this run,
so the figure layer — the half of D7 that actually was broken — is untested
by it. Checked separately, by running the patched `plot_forest.py` against
the θ = +2% results:

```
derived true_values : {'eff_p020': 2.0, 'null': 0.0}
derived col_titles  : ['2% Effect', 'Null (0%)']
```

The patched figure draws its reference line at 2.0 pp. **The unpatched one
would have drawn it at 7.5 pp — an error of 5.5 pp, or 275% of the true
effect.** Every estimator would have appeared to understate the lift by more
than the lift itself, in a figure captioned "7.5% Effect", with a metrics
table beside it reporting the correct 2%.

That is the whole of D7 in one number, and it is why the static audit was
worth doing before the compute rather than after.

### 5b. θ = −5%, the sign mutation

`+2%` tests magnitude. It does not test **sign**, and sign is where a
marketing decision actually lives: the question a business faces is not only
"how big is the lift" but "is this channel destroying money". A pipeline can
be perfectly parameterised in magnitude and still assume the effect is
positive — in a one-sided test, in an `abs()`, in a coverage check, in a
"detected" flag that means "significant *and* positive".

The two-point world cannot surface this, because both of its truths are ≥ 0.
θ = −5% is therefore not an extra data point on a curve; it is a separate
mutation test with its own pass condition: the sign of the recorded true ATT,
the direction of every interval, and the meaning of `significant` must all
survive a negative truth.

### 5b.1 M6b result — θ = −5%, G4 PASS 6/6

640 rows, arms `null` and `eff_m050` on disk. All six criteria pass, with
criterion 2 the one that matters here: **median `true_att_pct` = −0.050000**,
sign and magnitude both carried through. The metrics layer records
−5.000pp and the bias identity holds to 0.0000pp, so nothing downstream
takes an absolute value or assumes lift.

**The sign-specific check:** `65.9%` of estimates come back negative at
θ = −5%. A pipeline that quietly assumed lift would show that near 0%. It is
not near 100% either, and should not be — at −5% against a sampling SD of
roughly 6–7 pp, a majority-negative distribution is what a working estimator
looks like, not a failing one.

**What this does and does not establish.** It shows the harness survives a
negative truth end to end. It does **not** establish that the estimators are
sign-symmetric: that needs matched `+x / −x` pairs, and the M6b run has only
one truth. The atlas grid contains exactly one such pair, −5%/+5%, and the
symmetry test is deferred to it (`theta_atlas.py`, Q4).

The two mutations together answer the question G4 was built for: **the donor
is parameterised in θ in magnitude and in sign**, and the only thing that
was not — the figure layer — is the part the static audit predicted and the
patch fixes.

## 6. Then a two-stage sweep, not a uniform one

Coarse first — θ ∈ {−10%, −5%, 0, +2%, +5%, +7.5%, +15%}, `A1` only, ~100
iterations — to see the *shape* of `p(S|θ)`: discontinuities, pathological
failures, how variance moves, whether errors are symmetric about zero, and
whether the S0/S1 story survives more than two truths.

Only then place θ densely where the decision boundary actually moves. A
uniform 13 × 4 × 1000 × 4 grid is 208,000 fits, most of them spent confirming
that every method detects a +20% lift.

## 7. A limitation of the current result this gate will resolve

The information ladder found `S1 → S2` worth between −$1,475 and +$96, with a
sign that flips across bandwidths — the interval adding nothing measurable on
top of the point estimate.

**That may be an artefact of the two-point world rather than a property of
intervals.** With θ ∈ {0, +7.5%} the point estimate nearly identifies the
state on its own, leaving the interval nothing to contribute. Once θ ranges
over −10% to +15%, two identical point estimates carrying different
uncertainty can imply different posteriors and different actions, and S2 gets
its first fair test.

So the current conclusion is strictly: **the large loss is at thresholding a
continuous estimate into a significance bit.** It is *not* "confidence
intervals are useless", and nothing here licenses that.
