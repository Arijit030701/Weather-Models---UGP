#!/bin/bash
source ~/wrf_env.sh
slim () {   # keep only rain + lat/lon in d02/d03 outputs
  for f in $1/run/wrfout_d02_* $1/run/wrfout_d03_*; do
    v=Times,XLAT,XLONG,LANDMASK,RAINNC,RAINC
    ncdump -h $f | grep -q " RAINSH(" && v=$v,RAINSH
    nccopy -V $v $f $f.small && mv $f.small $f && echo "slimmed $(basename $f): $(du -h $f | cut -f1)"
  done
  rm -f $1/run/wrfinput_* $1/run/wrfbdy_* $1/run/wrffdda_*
}
D=~/wrf/cases/mumbai2005_nudge
echo "D OK"; slim $D
du -sh ~
E=~/wrf/cases/mumbai2005_nocu9
echo "=== rerun E $(date) ==="
taskset -c 0,2,4,6,8,10,12,14 bash ~/wrf/wrf_kit/run_wrf.sh $E 8 < /dev/null && slim $E
du -sh ~
echo "all done $(date)"
