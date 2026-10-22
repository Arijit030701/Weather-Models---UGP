#!/bin/bash
source ~/wrf_env.sh
echo "start $(date)"
SRC=$(readlink -f ~/wrf/cases/scale_8)
for t in "pin_P8 8 0,2,4,6,8,10,12,14" "pin_P4 4 0,2,4,6" "pin_P16ht 16 0-15" "pin_E16 16 16-31" "pin_P8E16 24 0,2,4,6,8,10,12,14,16-31"; do
  set -- $t; name=$1; np=$2; cpus=$3
  C=~/wrf/cases/$name
  mkdir -p $C && cp $SRC/namelist.input $C/ && ln -sfn $(readlink -f $SRC/wps) $C/wps
  echo "=== $name: $np ranks on CPUs $cpus ==="
  taskset -c $cpus bash ~/wrf/wrf_kit/run_wrf.sh $C $np < /dev/null
  rm -f $C/run/wrfout_* $C/run/wrfinput_* $C/run/wrfbdy_*
done
echo "all done $(date)"
