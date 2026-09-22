#!/usr/bin/env bash
# Build R 4.5.1 from the official source tarball into its own prefix, so the
# exact-repro lane does not collide with the 4.6.1 the robustness lane uses.
# rocker/r-ver:4.5.1 would be the better route, but there is no Docker daemon
# in this container -- see repro/recast/README.md.
set -eux
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -qq --no-install-recommends \
  build-essential gfortran libreadline-dev libx11-dev libxt-dev \
  libpng-dev libjpeg-dev libcairo2-dev libbz2-dev liblzma-dev \
  libpcre2-dev libcurl4-openssl-dev zlib1g-dev libicu-dev \
  libdeflate-dev libtirpc-dev >/dev/null
mkdir -p /opt/src && cd /opt/src
curl -fsSLO https://cran.r-project.org/src/base/R-4/R-4.5.1.tar.gz
sha256sum R-4.5.1.tar.gz | tee /opt/src/R-4.5.1.sha256
tar xzf R-4.5.1.tar.gz && cd R-4.5.1
./configure --prefix=/opt/R/4.5.1 --enable-R-shlib --with-x=no \
  --with-blas --with-lapack >/tmp/r451_configure.log 2>&1
make -j"$(nproc)" >/tmp/r451_make.log 2>&1
make install >>/tmp/r451_make.log 2>&1
/opt/R/4.5.1/bin/Rscript --version
