# Downloads ERA5 input for WRF (pressure levels + surface), 6-hourly, over the Indian region.
# Usage:  python download_era5.py 2005-07-25 2005-07-27 ~/wrf/data/era5_mumbai2005  [N,W,S,E]
#   e.g.  python download_era5.py 2018-08-13 2018-08-17 ~/wrf/data/era5_kerala2018 27,60,-7,94
# Needs:  pip install cdsapi   and your ~/.cdsapirc (same key you used in Colab)
import sys, os
from datetime import date, timedelta
import cdsapi

start, end, outdir = sys.argv[1], sys.argv[2], os.path.expanduser(sys.argv[3])
os.makedirs(outdir, exist_ok=True)

d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
days = [(d0 + timedelta(n)) for n in range((d1 - d0).days + 1)]
years  = sorted({f"{d.year}" for d in days})
months = sorted({f"{d.month:02d}" for d in days})
dlist  = sorted({f"{d.day:02d}" for d in days})

area  = [35, 58, 2, 94]                     # N, W, S, E  -> a bit bigger than the WRF outer box (Mumbai)
if len(sys.argv) > 4:
    area = [float(v) for v in sys.argv[4].split(",")]
times = ["00:00", "06:00", "12:00", "18:00"]

levels = ["1", "2", "3", "5", "7", "10", "20", "30", "50", "70", "100", "125", "150", "175",
          "200", "225", "250", "300", "350", "400", "450", "500", "550", "600", "650", "700",
          "750", "775", "800", "825", "850", "875", "900", "925", "950", "975", "1000"]

c = cdsapi.Client()

print("Downloading pressure-level data ...")
c.retrieve("reanalysis-era5-pressure-levels", {
    "product_type": ["reanalysis"],
    "variable": ["geopotential", "temperature", "u_component_of_wind",
                 "v_component_of_wind", "relative_humidity", "specific_humidity"],
    "pressure_level": levels,
    "year": years, "month": months, "day": dlist, "time": times,
    "area": area, "data_format": "grib", "download_format": "unarchived",
}, f"{outdir}/era5_pl.grib")

print("Downloading surface data ...")
c.retrieve("reanalysis-era5-single-levels", {
    "product_type": ["reanalysis"],
    "variable": ["10m_u_component_of_wind", "10m_v_component_of_wind", "2m_temperature",
                 "2m_dewpoint_temperature", "surface_pressure", "mean_sea_level_pressure",
                 "skin_temperature", "sea_surface_temperature", "land_sea_mask", "geopotential",
                 "soil_temperature_level_1", "soil_temperature_level_2",
                 "soil_temperature_level_3", "soil_temperature_level_4",
                 "volumetric_soil_water_layer_1", "volumetric_soil_water_layer_2",
                 "volumetric_soil_water_layer_3", "volumetric_soil_water_layer_4",
                 "snow_depth", "sea_ice_cover"],
    "year": years, "month": months, "day": dlist, "time": times,
    "area": area, "data_format": "grib", "download_format": "unarchived",
}, f"{outdir}/era5_sfc.grib")

print("Done. Files in", outdir)
for f in sorted(os.listdir(outdir)):
    print(f"  {f}  {os.path.getsize(os.path.join(outdir, f))/1e6:.1f} MB")
