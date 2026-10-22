#!/bin/bash
# Runs real.exe (makes start + boundary files) and wrf.exe (the forecast). Records time and memory.
# Usage:  bash run_wrf.sh  <case folder>  [number of cores, default 16]
#   e.g.  bash run_wrf.sh ~/wrf/cases/mumbai2005 16
set -e
CASE=$(realpath "$1"); NP=${2:-16}
BASE=$HOME/wrf; BENCH=$BASE/benchmark.csv
CPU=$(lscpu | sed -n 's/^Model name: *//p' | head -1)
[ -f "$HOME/wrf_env.sh" ] && source "$HOME/wrf_env.sh"      # CSE server: our own MPICH + NetCDF
if mpirun --version 2>&1 | grep -qi "open mpi"; then             # laptop (OpenMPI)
  MPI="mpirun --oversubscribe --bind-to none"
  [ "$(id -u)" -eq 0 ] && MPI="$MPI --allow-run-as-root"
else                                                             # server (MPICH)
  MPI="mpirun"
fi

mkdir -p "$CASE/run" && cd "$CASE/run"
rm -f rsl.* wrfout_* wrfrain_* wrfinput_* wrfbdy_* met_em.*
ln -sf "$BASE"/WRF/run/* .
rm -f namelist.input && cp ../namelist.input .
for f in ../*.txt; do [ -f "$f" ] && cp "$f" . || true; done        # e.g. rain_io.txt (rain-only output list)
ln -sf ../wps/met_em.d0* .

# use the real number of ERA5 levels found by metgrid
NL=$(ncdump -h $(ls met_em.d01.* | head -1) | grep -m1 'num_metgrid_levels =' | awk '{print $3}')
sed -i "s/num_metgrid_levels *= *[0-9]*/num_metgrid_levels = $NL/" namelist.input

# memory watcher: samples used RAM every 5 s
( while true; do free -m | awk '/^Mem/{print $3}'; sleep 5; done ) > mem.log &
MEMPID=$!
trap "kill $MEMPID 2>/dev/null" EXIT
BASELINE=$(free -m | awk '/^Mem/{print $3}')

record () { # step seconds
  PEAK=$(sort -n mem.log | tail -1); PEAK=$(( ${PEAK:-$BASELINE} - BASELINE ))
  [ -f "$BENCH" ] || echo "date,machine,cpu,nprocs,case,step,seconds,peak_ram_mb" > "$BENCH"
  echo "$(date +%F_%T),$(hostname),\"$CPU\",$3,$(basename "$CASE"),$1,$2,$PEAK" >> "$BENCH"
  echo "   -> $1 took $2 s ($(( $2 / 60 )) min), extra RAM used ~${PEAK} MB"
}

echo "== real.exe =="
t0=$(date +%s); $MPI -np 4 ./real.exe > /dev/null 2>&1 || true
grep -q "SUCCESS COMPLETE REAL_EM" rsl.error.0000 || { echo "real.exe FAILED - send me $CASE/run/rsl.error.0000"; exit 1; }
record real $(( $(date +%s) - t0 )) 4
mkdir -p logs_real && mv rsl.* logs_real/

echo "== wrf.exe on $NP cores (this is the long one; follow progress with:  tail -f $CASE/run/rsl.error.0000) =="
: > mem.log; t0=$(date +%s)
$MPI -np "$NP" ./wrf.exe > /dev/null 2>&1 || true
grep -q "SUCCESS COMPLETE WRF" rsl.error.0000 || { echo "wrf.exe FAILED - send me the last 50 lines of $CASE/run/rsl.error.0000"; exit 1; }
record wrf $(( $(date +%s) - t0 )) "$NP"

echo
echo "WRF finished. Output files:"
ls -lh wrfout_d0* wrfrain_d0* 2>/dev/null | awk '{print "  "$9"  "$5}'
echo "Timing saved in $BENCH"
