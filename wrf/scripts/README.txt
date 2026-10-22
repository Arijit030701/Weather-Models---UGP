WRF kit - Mumbai flood, 26 July 2005
=====================================
Files
  install_wrf.sh     builds WRF v4.8.0 + WPS v4.7.0 into ~/wrf   (run once)
  download_era5.py   downloads ERA5 input (needs cdsapi + ~/.cdsapirc)
  run_wps.sh         geogrid + ungrib + metgrid  -> met_em files
  run_wrf.sh         real.exe + wrf.exe          -> wrfout files, timing in ~/wrf/benchmark.csv
  mumbai2005/        settings for this case
      namelist.wps     3 nested boxes: 27 km (India) -> 9 km (west India) -> 3 km (Mumbai)
      namelist.input   run 25 Jul 00 UTC -> 27 Jul 12 UTC (60 h), physics choices

Folder layout after setup
  ~/wrf/WRF  ~/wrf/WPS  ~/wrf/WPS_GEOG     programs + terrain maps
  ~/wrf/wrf_kit                            these scripts
  ~/wrf/data/era5_mumbai2005               ERA5 GRIB files
  ~/wrf/cases/mumbai2005/wps               met_em files
  ~/wrf/cases/mumbai2005/run               wrfout files (the results)

Domains
  d01  27 km  100 x 100   ~63-89 E,  7-31 N
  d02   9 km  151 x 151   ~67-80 E, 13-25 N
  d03   3 km  151 x 151   ~70.7-75.0 E, 17.0-21.0 N  (Mumbai near the centre)

Physics (namelist.input)
  WSM6 microphysics, new Tiedtke cumulus on d01/d02 (off on 3 km d03),
  RRTMG radiation, YSU boundary layer, Noah land surface.
