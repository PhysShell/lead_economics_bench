#!/usr/bin/env Rscript
# Restore the donor's R environment WITHOUT modifying the donor.
#
# Must be run through `R --vanilla`, which skips .Rprofile. The donor's
# .Rprofile sources renv/activate.R, a file its .gitignore excludes and a
# pristine clone does not contain, so an ordinary R start-up can fail before
# renv::restore() has a chance to create it. Once this completes, .Rprofile
# resolves normally and the donor's own make targets work unmodified.
#
#   R --vanilla -f bootstrap.R --args /path/to/donor
#
# NOTE ON A BUG THIS FILE USED TO HAVE
# ------------------------------------
# An earlier version read the lockfile with jsonlite::fromJSON *before*
# installing anything. On a genuinely clean R that fails at the first line
# that matters -- which is to say, it carefully stepped around the donor's
# bootstrap deadlock and then built a smaller one of its own. The R version is
# now read with base R only, so this script depends on nothing before it has
# had the chance to install what it needs.

args <- commandArgs(trailingOnly = TRUE)
project <- if (length(args)) args[[1]] else getwd()
options(repos = c(CRAN = "https://cloud.r-project.org"))

lock <- file.path(project, "renv.lock")
if (!file.exists(lock)) {
  stop(sprintf("renv.lock not found under '%s' -- wrong project path?", project))
}

lockfile_r_version <- function(path) {
  # Base-R only, deliberately: no package may be required to discover which
  # packages we are about to install.
  txt <- paste(readLines(path, warn = FALSE), collapse = " ")
  # The "R" block's Version field is the first "Version" after '"R"'.
  after_r <- sub('.*"R"\\s*:\\s*\\{', "", txt)
  m <- regmatches(after_r, regexpr('"Version"\\s*:\\s*"[^"]+"', after_r))
  if (!length(m)) return(NA_character_)
  sub('.*"([^"]+)"$', "\\1", m)
}

running <- paste(R.version$major, R.version$minor, sep = ".")
pinned <- lockfile_r_version(lock)

cat("R running:", R.version.string, "\n")
cat("R pinned: ", if (is.na(pinned)) "(not found in lockfile)" else pinned, "\n")
cat("project:  ", project, "\n\n")

if (!is.na(pinned) && !identical(pinned, running)) {
  cat(strrep("-", 72), "\n")
  cat(sprintf("LANE: robustness, not reproduction.\n"))
  cat(sprintf("  lockfile pins R %s; this interpreter is R %s.\n", pinned, running))
  cat("  Compiled dependencies will be built for a different R minor series\n")
  cat("  than the donor used. Results from this lane are evidence about\n")
  cat("  environment sensitivity, not about reproducing the donor.\n")
  cat(strrep("-", 72), "\n\n")
} else if (!is.na(pinned)) {
  cat("LANE: version-matched. R version agrees with the lockfile.\n")
  cat("  Note this is still not 'exact': the donor published no compiler,\n")
  cat("  BLAS/LAPACK backend or ./configure invocation, and ran macOS ARM64.\n\n")
}

if (!requireNamespace("renv", quietly = TRUE)) {
  cat("installing renv...\n")
  install.packages("renv")
}
renv::restore(project = project, prompt = FALSE)
cat("\nrestore complete on R", running, "\n")
