#!/usr/bin/env Rscript
# Restore the donor's R environment WITHOUT modifying the donor.
#
# Must be run through `R --vanilla`, which skips .Rprofile. The donor's
# .Rprofile sources renv/activate.R, a file its .gitignore excludes and a
# pristine clone does not contain, so an ordinary R start-up can fail before
# renv::restore() has a chance to create it. Once this completes, .Rprofile
# resolves normally and the donor's own make targets work unmodified.
#
#   R --vanilla -f bootstrap.R --args /home/user/getrecast/geolift-simulation-study

args <- commandArgs(trailingOnly = TRUE)
project <- if (length(args)) args[[1]] else getwd()
options(repos = c(CRAN = "https://cloud.r-project.org"))

cat("R:      ", R.version.string, "\n")
cat("project:", project, "\n")

lock <- file.path(project, "renv.lock")
stopifnot("renv.lock not found -- wrong project path?" = file.exists(lock))

pinned <- jsonlite::fromJSON(lock)$R$Version
if (!identical(pinned, paste(R.version$major, R.version$minor, sep = "."))) {
  cat(sprintf(
    "NOTE: lockfile pins R %s, running R %s.%s -- this is the robustness\n",
    pinned, R.version$major, R.version$minor))
  cat("      lane, not the exact-reproduction lane. Recorded, not silent.\n")
}

if (!requireNamespace("renv", quietly = TRUE)) install.packages("renv")
renv::restore(project = project, prompt = FALSE)
cat("restore complete\n")
