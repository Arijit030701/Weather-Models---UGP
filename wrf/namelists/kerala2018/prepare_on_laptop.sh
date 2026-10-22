#!/bin/bash
# LAPTOP (WSL): ERA5 download + WPS for the Kerala 2018 case, then shrink the met_em files for the server.
# Usage:  conda activate ; bash ~/wrf/wrf_kit/kerala2018/prepare_on_laptop.sh
set -e
KIT=$HOME/wrf/wrf_kit; CASE=$HOME/wrf/cases/kerala2018; DATA=$HOME/wrf/data/era5_kerala2018
mkdir -p "$CASE"
cp "$KIT"/kerala2018/namelist.wps "$KIT"/kerala2018/namelist.input "$KIT"/kerala2018/rain_io.txt "$CASE"/

if [ ! -s "$DATA/era5_sfc.grib" ]; then
  echo "=== ERA5 download (13-17 Aug 2018, 6-hourly; ~10-20 min) ==="
  python "$KIT"/download_era5.py 2018-08-13 2018-08-17 "$DATA" 27,60,-7,94
fi

echo "=== WPS ==="
bash "$KIT"/run_wps.sh "$CASE" "$DATA"

echo "=== Compressing met_em files (same data, smaller files for the server quota) ==="
cd "$CASE/wps"
before=$(du -cm met_em.d0* | tail -1 | cut -f1)
for f in met_em.d0*; do nccopy -k nc4 -d 2 "$f" "$f.z" && mv "$f.z" "$f"; done
after=$(du -cm met_em.d0* | tail -1 | cut -f1)
echo "met_em: ${before} MB -> ${after} MB, $(ls met_em.d0* | wc -l) files"
echo "READY. Next: copy to the server (see instructions)."
