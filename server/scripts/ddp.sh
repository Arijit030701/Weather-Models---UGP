#!/bin/bash
cd ~/wrf/wrf_kit
P=0,2,4,6,8,10,12,14
echo "start $(date)"
echo "### grow, P-cores only"
taskset -c $P python3 ddp_lstm_benchmark.py --threads-per-worker 1 --workers 1 2 4 8 --samples 1024 --epochs 2 --out ~/ddp/grow_P
echo "### grow, all cores"
python3 ddp_lstm_benchmark.py --threads-per-worker 1 --workers 1 2 4 8 16 24 32 --samples 1024 --epochs 2 --out ~/ddp/grow_all
echo "### fixed 32 threads"
python3 ddp_lstm_benchmark.py --threads 32 --workers 1 2 4 8 16 32 --out ~/ddp/fixed32
echo "all done $(date)"
