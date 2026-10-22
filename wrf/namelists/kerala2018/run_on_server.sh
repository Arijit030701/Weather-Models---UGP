#!/bin/bash
# SERVER: runs the Kerala 2018 case on the 8 fast P-cores, then removes the large start-up files.
# Usage:  nohup bash ~/wrf/wrf_kit/kerala2018/run_on_server.sh > ~/kerala.log 2>&1 &
source ~/wrf_env.sh
C=$HOME/wrf/cases/kerala2018
echo "start $(date)"; du -sh ~
n=$(ls $C/wps/met_em.d0* 2>/dev/null | wc -l)
[ "$n" -eq 54 ] || { echo "Expected 54 met_em files in $C/wps, found $n - copy them first"; exit 1; }
taskset -c 0,2,4,6,8,10,12,14 bash ~/wrf/wrf_kit/run_wrf.sh $C 8 < /dev/null
rm -f $C/run/wrfinput_* $C/run/wrfbdy_*
ls -lh $C/run/wrfrain_d0* 2>/dev/null
du -sh ~
echo "all done $(date)"
