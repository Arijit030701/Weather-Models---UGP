#!/bin/bash
# Installs WRF v4.8.0 + WPS v4.7.0 on Ubuntu 24.04 (WSL or server).
# Usage:   bash install_wrf.sh
# Result:  ~/wrf/WRF/main/wrf.exe, real.exe  and  ~/wrf/WPS/geogrid.exe, ungrib.exe, metgrid.exe
set -e

NCPU=${NCPU:-$(nproc)}
BASE=$HOME/wrf
LIBS=$BASE/libs

# conda puts its own libraries first in PATH, which breaks the build
if [ -n "$CONDA_PREFIX" ]; then
  echo "Conda is active. Run 'conda deactivate' (until (base) disappears) and run this script again."
  exit 1
fi

mkdir -p "$BASE" "$LIBS"
cd "$BASE"

echo "=== 1/5  Installing compilers, MPI and NetCDF (asks for your Linux password) ==="
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
$SUDO apt-get update
$SUDO apt-get install -y build-essential gfortran m4 csh tcsh perl git cmake file wget \
     libopenmpi-dev openmpi-bin libnetcdf-dev libnetcdff-dev netcdf-bin \
     libpng-dev zlib1g-dev libhdf5-dev time

echo "=== 2/5  Making one NetCDF folder (Ubuntu splits it up, WRF wants one place) ==="
mkdir -p "$LIBS/netcdf/bin" "$LIBS/netcdf/include" "$LIBS/netcdf/lib"
ln -sf /usr/bin/nc-config /usr/bin/nf-config "$LIBS/netcdf/bin/"
ln -sf /usr/include/netcdf* "$LIBS/netcdf/include/"
ln -sf /usr/lib/x86_64-linux-gnu/libnetcdf* "$LIBS/netcdf/lib/"

echo "=== 3/5  Building jasper (WPS needs it for GRIB2; not in Ubuntu 24.04) ==="
if [ ! -f "$LIBS/lib/libjasper.a" ]; then
  rm -rf jasper-src jasper-build
  git clone -q --depth 1 --branch version-2.0.33 https://github.com/jasper-software/jasper jasper-src
  mkdir jasper-build && cd jasper-build
  cmake ../jasper-src -DCMAKE_INSTALL_PREFIX="$LIBS" -DCMAKE_BUILD_TYPE=Release \
        -DJAS_ENABLE_SHARED=OFF -DJAS_ENABLE_PROGRAMS=OFF -DJAS_ENABLE_DOC=OFF \
        -DJAS_ENABLE_OPENGL=OFF -DJAS_ENABLE_LIBJPEG=OFF -DCMAKE_POLICY_VERSION_MINIMUM=3.5 > cmake.log
  make -j "$NCPU" install > make.log
  cd "$BASE"
fi

export NETCDF=$LIBS/netcdf
export JASPERLIB=$LIBS/lib
export JASPERINC=$LIBS/include

echo "=== 4/5  Building WRF (takes ~20-40 min) ==="
[ -d WRF ] || git clone -q --depth 1 --branch v4.8.0 --recurse-submodules --shallow-submodules \
                 https://github.com/wrf-model/WRF WRF
cd WRF
./clean -a > /dev/null 2>&1 || true
# 34 = GNU gfortran, dmpar (runs on many cores with MPI);  1 = basic nesting
printf '34\n1\n' | ./configure > configure.log 2>&1
./compile -j "$NCPU" em_real > compile.log 2>&1 || true
if [ ! -x main/wrf.exe ] || [ ! -x main/real.exe ]; then
  echo "WRF build FAILED. Send me the file ~/wrf/WRF/compile.log"; exit 1
fi
echo "WRF OK"
cd "$BASE"

echo "=== 5/5  Building WPS (takes ~2 min) ==="
[ -d WPS ] || git clone -q --depth 1 --branch v4.7.0 https://github.com/wrf-model/WPS WPS
cd WPS
./clean -a > /dev/null 2>&1 || true
export WRF_DIR=$BASE/WRF
# 1 = Linux x86_64, gfortran, serial (with GRIB2)
printf '1\n' | ./configure > configure.log 2>&1
./compile > compile.log 2>&1 || true
for exe in geogrid.exe ungrib.exe metgrid.exe; do
  if [ ! -e "$exe" ]; then echo "WPS build FAILED ($exe missing). Send me ~/wrf/WPS/compile.log"; exit 1; fi
done
echo "WPS OK"

echo
echo "================  ALL DONE  ================"
ls -l "$BASE/WRF/main/"*.exe "$BASE/WPS/"*.exe
