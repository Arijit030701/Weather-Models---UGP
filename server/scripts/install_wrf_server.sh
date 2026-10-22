#!/bin/bash
# Builds everything WRF needs in YOUR HOME FOLDER (no sudo) on the CSE server, then builds WRF.
#   tcsh (WRF's build scripts need csh), zlib, HDF5, NetCDF-C, NetCDF-Fortran, MPICH 5.0.2, WRF 4.8.0
# Usage:   bash install_wrf_server.sh            (run inside tmux; ~30-45 min on 32 threads)
# Result:  ~/wrf/WRF/main/wrf.exe and real.exe,  and ~/wrf_env.sh (load it with: source ~/wrf_env.sh)
set -e

NCPU=${NCPU:-24}                       # build with 24 of the 32 threads
LIBS=$HOME/wrf_libs                    # all libraries go here
SRC=$HOME/wrf_src                      # source code downloads (deleted at the end to save space)
BASE=$HOME/wrf                         # WRF goes here
STEP_ONLY=${STEP_ONLY:-all}            # for testing single steps
mkdir -p "$LIBS/lib" "$LIBS/include" "$LIBS/bin" "$SRC" "$BASE"

# same compiler version for C and Fortran (gcc 15 + gfortran 11 can clash)
export CC=gcc-11 CXX=g++-11 FC=gfortran-11 F77=gfortran-11 F90=gfortran-11
export PATH=$LIBS/bin:$PATH
export LD_LIBRARY_PATH=$LIBS/lib:$LD_LIBRARY_PATH
export CPPFLAGS="-I$LIBS/include" LDFLAGS="-L$LIBS/lib"

log () { echo; echo "=== $(date +%H:%M:%S)  $* ==="; }
done_flag () { [ -f "$LIBS/.done_$1" ]; }
mark () { touch "$LIBS/.done_$1"; }
want () { [ "$STEP_ONLY" = all ] || [ "$STEP_ONLY" = "$1" ]; }

# ---------------------------------------------------------------- 1. tcsh
if want tcsh && ! done_flag tcsh; then
  log "1/7 tcsh (needed by WRF's compile script)"
  cd "$SRC"; rm -rf tcsh
  git clone -q --depth 1 --branch TCSH6_24_16 https://github.com/tcsh-org/tcsh tcsh
  cd tcsh
  # use the system's terminal library even if its developer files are not installed
  [ -e /usr/lib/x86_64-linux-gnu/libtinfo.so ] || ln -sf /lib/x86_64-linux-gnu/libtinfo.so.6 "$LIBS/lib/libtinfo.so"
  ./configure --prefix="$LIBS" > configure.log 2>&1
  make -j "$NCPU" > make.log 2>&1 && make install > install.log 2>&1
  ln -sf "$LIBS/bin/tcsh" "$LIBS/bin/csh"
  mark tcsh
fi

# ---------------------------------------------------------------- 2. zlib
if want zlib && ! done_flag zlib; then
  log "2/7 zlib"
  cd "$SRC"; rm -rf zlib-1.3.1
  wget -q https://github.com/madler/zlib/releases/download/v1.3.1/zlib-1.3.1.tar.gz -O zlib.tgz
  tar xzf zlib.tgz && cd zlib-1.3.1
  ./configure --prefix="$LIBS" > configure.log 2>&1
  make -j "$NCPU" > make.log 2>&1 && make install > install.log 2>&1
  mark zlib
fi

# ---------------------------------------------------------------- 3. HDF5
if want hdf5 && ! done_flag hdf5; then
  log "3/7 HDF5 (~5-10 min)"
  cd "$SRC"; rm -rf hdf5-1.14.6
  wget -q https://github.com/HDFGroup/hdf5/releases/download/hdf5_1.14.6/hdf5-1.14.6.tar.gz -O hdf5.tgz
  tar xzf hdf5.tgz && cd hdf5-1.14.6
  ./configure --prefix="$LIBS" --with-zlib="$LIBS" --enable-hl --disable-fortran --disable-cxx \
              --disable-tests --disable-tools > configure.log 2>&1
  make -j "$NCPU" > make.log 2>&1 && make install > install.log 2>&1
  mark hdf5
fi

# ---------------------------------------------------------------- 4. NetCDF-C
if want netcdfc && ! done_flag netcdfc; then
  log "4/7 NetCDF-C"
  cd "$SRC"; rm -rf netcdf-c ncc-build
  git clone -q --depth 1 --branch v4.9.3 https://github.com/Unidata/netcdf-c netcdf-c
  cmake -S netcdf-c -B ncc-build -DCMAKE_INSTALL_PREFIX="$LIBS" -DCMAKE_PREFIX_PATH="$LIBS" \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_LIBDIR=lib \
        -DNETCDF_ENABLE_DAP=OFF -DNETCDF_ENABLE_BYTERANGE=OFF -DNETCDF_ENABLE_NCZARR=OFF \
        -DNETCDF_ENABLE_PLUGINS=OFF -DNETCDF_ENABLE_LIBXML2=OFF -DNETCDF_ENABLE_TESTS=OFF \
        -DENABLE_DAP=OFF -DENABLE_BYTERANGE=OFF -DENABLE_NCZARR=OFF -DENABLE_PLUGINS=OFF \
        -DENABLE_TESTS=OFF > ncc-cmake.log 2>&1
  cmake --build ncc-build -j "$NCPU" > ncc-make.log 2>&1
  cmake --install ncc-build > ncc-install.log 2>&1
  mark netcdfc
fi

# ---------------------------------------------------------------- 5. NetCDF-Fortran
if want netcdff && ! done_flag netcdff; then
  log "5/7 NetCDF-Fortran"
  cd "$SRC"; rm -rf netcdf-fortran ncf-build
  git clone -q --depth 1 --branch v4.6.2 https://github.com/Unidata/netcdf-fortran netcdf-fortran
  cmake -S netcdf-fortran -B ncf-build -DCMAKE_INSTALL_PREFIX="$LIBS" -DCMAKE_PREFIX_PATH="$LIBS" \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_LIBDIR=lib -DENABLE_TESTS=OFF \
        -DNETCDF_C_LIBRARY="$LIBS/lib/libnetcdf.so" -DNETCDF_C_INCLUDE_DIR="$LIBS/include" > ncf-cmake.log 2>&1
  cmake --build ncf-build -j "$NCPU" > ncf-make.log 2>&1
  cmake --install ncf-build > ncf-install.log 2>&1
  mark netcdff
fi

# ---------------------------------------------------------------- 6. MPICH 5
if want mpich && ! done_flag mpich; then
  log "6/7 MPICH 5.0.2 (~10-15 min)"
  cd "$SRC"; rm -rf mpich-5.0.2
  wget -q https://github.com/pmodels/mpich/releases/download/v5.0.2/mpich-5.0.2.tar.gz -O mpich.tgz
  tar xzf mpich.tgz && cd mpich-5.0.2
  ./configure --prefix="$LIBS" --disable-doc > configure.log 2>&1
  make -j "$NCPU" > make.log 2>&1 && make install > install.log 2>&1
  mark mpich
fi

# ---------------------------------------------------------------- environment file
cat > "$HOME/wrf_env.sh" <<EOF
# load with:  source ~/wrf_env.sh
export PATH=$LIBS/bin:\$PATH
export LD_LIBRARY_PATH=$LIBS/lib:\$LD_LIBRARY_PATH
export NETCDF=$LIBS
export HDF5=$LIBS
export WRFIO_NCD_LARGE_FILE_SUPPORT=1
EOF
source "$HOME/wrf_env.sh"

# ---------------------------------------------------------------- 7. WRF
if want wrf && ! done_flag wrf; then
  log "7/7 WRF 4.8.0 (~15-25 min)"
  echo "   using: $(which mpif90)  ->  $(mpif90 --version | head -1)"
  echo "   using: $(which csh)"
  cd "$BASE"
  [ -d WRF ] || git clone -q --depth 1 --branch v4.8.0 --recurse-submodules --shallow-submodules \
                  https://github.com/wrf-model/WRF WRF
  cd WRF
  ./clean -a > /dev/null 2>&1 || true
  printf '34\n1\n' | ./configure > configure.log 2>&1
  # make WRF's C parts use gcc-11 as well
  sed -i 's/^\(SCC *=\).*/\1 gcc-11/; s/^\(CCOMP *=\).*/\1 gcc-11/' configure.wrf
  ./compile -j "$NCPU" em_real > compile.log 2>&1 || true
  if [ ! -x main/wrf.exe ] || [ ! -x main/real.exe ]; then
    echo "WRF build FAILED - send me the last 40 lines of ~/wrf/WRF/compile.log"; exit 1
  fi
  mark wrf
fi

log "ALL DONE"
ls -l "$BASE/WRF/main/wrf.exe" "$BASE/WRF/main/real.exe"
echo "MPI:    $(mpirun --version 2>&1 | grep -m1 Version)"
echo "Space used: $(du -sh $LIBS | cut -f1) libraries, $(du -sh $BASE | cut -f1) WRF"
echo "Cleaning source downloads..."; rm -rf "$SRC"
echo "Remember: run 'source ~/wrf_env.sh' every time you log in before using WRF."
