#!/bin/bash
# Prepares WRF input: terrain (geogrid) + ERA5 decode (ungrib) + put ERA5 on the WRF grid (metgrid)
# Usage:  bash run_wps.sh  <case folder>  <ERA5 folder>
#   e.g.  bash run_wps.sh ~/wrf/cases/mumbai2005 ~/wrf/data/era5_mumbai2005
set -e
CASE=$(realpath "$1"); DATA=$(realpath "$2")
BASE=$HOME/wrf; WPS=$BASE/WPS
BENCH=$BASE/benchmark.csv
CPU=$(lscpu | sed -n 's/^Model name: *//p' | head -1)
log_time () { # step seconds
  [ -f "$BENCH" ] || echo "date,machine,cpu,nprocs,case,step,seconds,peak_ram_mb" > "$BENCH"
  echo "$(date +%F_%T),$(hostname),\"$CPU\",1,$(basename "$CASE"),$1,$2," >> "$BENCH"
}

mkdir -p "$CASE/wps" && cd "$CASE/wps"
rm -f met_em.* FILE:* GRIBFILE.* geo_em.*
sed "s#GEOG_PATH_HERE#$BASE/WPS_GEOG#" ../namelist.wps > namelist.wps
ln -sfn "$WPS/geogrid" geogrid
ln -sfn "$WPS/metgrid" metgrid

echo "== geogrid (terrain + land maps) =="
t0=$(date +%s); "$WPS/geogrid.exe" > geogrid.log 2>&1 || true
grep -q "Successful completion" geogrid.log || { echo "geogrid FAILED - send me $CASE/wps/geogrid.log"; exit 1; }
log_time geogrid $(( $(date +%s) - t0 ))

echo "== ungrib (read ERA5 GRIB files) =="
"$WPS/link_grib.csh" "$DATA"/*.grib
ln -sf "$WPS/ungrib/Variable_Tables/Vtable.ECMWF" Vtable
t0=$(date +%s); "$WPS/ungrib.exe" > ungrib.log 2>&1 || true
grep -q "Successful completion" ungrib.log || { echo "ungrib FAILED - send me $CASE/wps/ungrib.log"; exit 1; }
log_time ungrib $(( $(date +%s) - t0 ))

echo "== metgrid (ERA5 onto the WRF grid) =="
t0=$(date +%s); "$WPS/metgrid.exe" > metgrid.log 2>&1 || true
grep -q "Successful completion" metgrid.log || { echo "metgrid FAILED - send me $CASE/wps/metgrid.log"; exit 1; }
log_time metgrid $(( $(date +%s) - t0 ))

echo
echo "WPS done. Files made:"
ls -1 geo_em.* | sed 's/^/  /'
echo "  $(ls met_em.* | wc -l) met_em files  ($(du -ch met_em.* | tail -1 | cut -f1))"
echo "  num_metgrid_levels = $(ncdump -h $(ls met_em.d01.* | head -1) | grep -m1 'num_metgrid_levels =' | awk '{print $3}')"
