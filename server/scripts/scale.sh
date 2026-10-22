#!/bin/bash
source ~/wrf_env.sh
echo "start $(date)"
for n in 32 24 16 8; do
  echo "=== $n cores ==="
  bash ~/wrf/wrf_kit/run_wrf.sh ~/wrf/cases/scale_$n $n
  rm -f ~/wrf/cases/scale_$n/run/wrfout_* ~/wrf/cases/scale_$n/run/wrfinput_* ~/wrf/cases/scale_$n/run/wrfbdy_*
  du -sh ~
done
echo "all done $(date)"
