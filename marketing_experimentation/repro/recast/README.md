# Reproducing the Recast donor without modifying it

`getrecast/geolift-simulation-study` @ `5133d37` has **no licence**. It can be
read, cited and recomputed from its published outputs; it cannot be vendored
or forked into this repository. So nothing here contains donor source. This
directory is an **external wrapper**: instructions and scripts that stand
outside the donor and drive it in place.

It also does not patch the donor. Its bootstrap defect (D1, below) is
evidence about reproducibility in this field, and evidence is recorded, not
erased.

## Two lanes, deliberately separate

| | repro lane | robustness lane |
|---|---|---|
| R | **4.5.1** (donor's `renv.lock`) | 4.6.1 (CRAN apt, current) |
| Python | **3.12.8** (donor's `.python-version`) | 3.11.15 (host) |
| deps | `requirements.txt` frozen, then `-e . --no-deps` | same |
| question | *can we reproduce the donor?* | *is the donor sensitive to a current environment?* |

Mixing them would make a numerical disagreement uninterpretable.

## Getting R 4.5.1

Two routes. Prefer the first where it is available.

### 1. Rocker (preferred; needs a Docker daemon)

`rocker/r-ver:4.5.1` publishes a linux/amd64 image, digest
`sha256:55be3ae296dd21b6f2da705be44804ba7eb2ab2233a7050730506d7e64e8feda`.
Pin the digest, not just the tag. See `Dockerfile`.

**Not usable in this container**: there is no Docker daemon
(`/var/run/docker.sock` absent). Recorded because the right answer on a
normal machine is still Rocker.

### 2. Source build (used here)

`build-r-451.sh` fetches
`https://cran.r-project.org/src/base/R-4/R-4.5.1.tar.gz` (released
2025-06-13), records its SHA256, and installs to `/opt/R/4.5.1` so it cannot
collide with the system R that the robustness lane uses.

## The bootstrap defect, and the workaround

The donor's `.Rprofile` is one line:

```r
source("renv/activate.R")
```

`renv/` is in its `.gitignore` and absent from a pristine clone, while
`make env` runs `Rscript -e "renv::restore()"`. R sources `.Rprofile` at
startup, so on a cold clone R can fail looking for the very file the restore
would have created.

`bootstrap.R` is run through `R --vanilla`, which skips `.Rprofile`
entirely, installs `renv`, and restores from `renv.lock`. After that
`.Rprofile` resolves normally and the donor's own `make` targets work
unmodified.

## Python

Do **not** use the host interpreter. The donor pins 3.12.8 in
`.python-version`, and its `requirements.txt` header records "Generated from
Python 3.12.8 on macOS (ARM64), March 2026".

Install the frozen set first and the package **without** dependencies:

```
uv venv --python 3.12.8 .venv-repro
.venv-repro/bin/pip install -r requirements.txt
.venv-repro/bin/pip install -e . --no-deps
```

The `--no-deps` matters. `make env` runs `pip install -r requirements.txt`
and then `pip install -e .`, and `pyproject.toml` carries ranges
(`pymc>=5.10`) where `requirements.txt` carries pins (`pymc==5.28.1`). The
loose install runs second and can move a pinned version out from under the
published results.

## Turning the mismatch into an experiment

Once the repro lane passes G3, the same handful of fixtures runs across a
2×2 of runtimes — not a full benchmark, 10–20 fixed seeds:

| | Python 3.12.8 | Python 3.11 |
|---|---|---|
| **R 4.5.1** | E0 donor-exact | E2 |
| **R 4.6.1** | E1 | E3 |

measuring, per tool: Δ`att_pct`, Δ CI bounds, Δ`significant`, outright
failures, and diagnostic drift. That replaces a vague "an R minor version
might change something" with a per-tool sensitivity profile — and for a
project about trusting statistical machinery, a real dependency sensitivity
would be a finding rather than a nuisance.

## G3 acceptance, fixed before the replay

One row per tool is too few for anything with MCMC in it; it can produce
either a false alarm or false reassurance.

| tool | iterations | comparison |
|---|---|---|
| `google_mm` | 10 fixed | **per row.** OLS/TBR, expected deterministic |
| `geolift` | 10 fixed | **per row.** Donor states block-conformal inference is deterministic |
| `causalpy` | 20 fixed | two levels, below |
| `causalimpact` | 20 fixed | two levels, below |

For the stochastic pair:

- **Level 1** — does an identical seed approximately reproduce the individual
  output, judged against that method's own Monte Carlo error rather than
  against zero?
- **Level 2** — does the *distribution* across fixed seeds reproduce: mean
  ATT difference, CI-width distribution, coverage, and significance
  agreement?

Requiring every posterior draw to match a macOS ARM64 machine would be a test
of nothing useful.
