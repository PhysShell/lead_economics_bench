# Exact-reproduction lane for getrecast/geolift-simulation-study @ 5133d37.
#
# The digest is pinned as well as the tag: a tag can be re-pushed, and this
# image is the only thing standing between us and "it worked on my machine".
FROM rocker/r-ver:4.5.1@sha256:55be3ae296dd21b6f2da705be44804ba7eb2ab2233a7050730506d7e64e8feda

# Python 3.12.8 to match the donor's .python-version. The host interpreter is
# deliberately not used.
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3.12 python3.12-venv python3-pip git make curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /repo
# The donor is mounted, never copied: it carries no licence, so it is driven
# in place rather than redistributed inside an image.
#   docker run --rm -v $DONOR:/repo -v $PWD:/wrapper <image> bash /wrapper/run-smoke.sh
