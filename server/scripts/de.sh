#!/bin/bash
source ~/wrf_env.sh
SRC=$(readlink -f ~/wrf/cases/scale_8)
for name in nudge nocu9; do
  C=~/wrf/cases/mumbai2005_$name
  mkdir -p $C && cp ~/$name.nml $C/namelist.input && ln -sfn $(readlink -f $SRC/wps) $C/wps
  echo "=== $name on 8 P-cores, start $(date) ==="
  taskset -c 0,2,4,6,8,10,12,14 bash ~/wrf/wrf_kit/run_wrf.sh $C 8 < /dev/null
  du -sh ~
done
echo "all done $(date)"
