# Reads the WRF output for the Mumbai 26 July 2005 flood and compares the rain with
# the rain gauge, the IMD grid, ERA5 and FourCastNet (numbers from my earlier notebooks).
#
# Usage:  python analyse_wrf_rain.py ~/wrf/cases/mumbai2005/run  ~/wrf/results_mumbai2005
# Needs:  pip install netCDF4 matplotlib numpy
import sys, os, glob, csv
import numpy as np
from netCDF4 import Dataset
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap

run_dir = os.path.expanduser(sys.argv[1])
out_dir = os.path.expanduser(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(run_dir, "results")
os.makedirs(out_dir, exist_ok=True)

# ---------- settings ----------
SANTACRUZ = (19.09, 72.85)                       # IMD Santacruz rain gauge (lat, lon)
WIN_START = datetime(2005, 7, 26, 3)             # IMD rain day = 08:30 IST 26 Jul -> 08:30 IST 27 Jul
WIN_END   = datetime(2005, 7, 27, 3)             #              = 03:00 UTC  -> 03:00 UTC
# reference values from my FourCastNet notebook (same window)
REF = {"Rain gauge (Santacruz)": 944.0, "IMD grid (0.25°)": 423.4,
       "ERA5 (0.25°)": 74.3, "FourCastNet (0.25°)": 59.8}
DOMAINS = {"d01": "27 km", "d02": "9 km", "d03": "3 km"}

# colours (reference palette): observations = neutral ink, AI/reanalysis = orange, WRF = blue
C_OBS, C_AI, C_WRF = "#52514e", "#eb6834", "#2a78d6"
C_LINES = {"d01": "#eb6834", "d02": "#1baf7a", "d03": "#2a78d6"}
TEXT, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": TEXT,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
                     "axes.spines.right": False})


def read_domain(dom):
    files = sorted(glob.glob(os.path.join(run_dir, f"wrfout_{dom}_*")))
    if not files:
        return None
    lat = lon = land = None
    times, rain = [], []
    for f in files:
        with Dataset(f) as nc:
            if lat is None:
                lat = nc["XLAT"][0].filled(np.nan); lon = nc["XLONG"][0].filled(np.nan)
                land = nc["LANDMASK"][0].filled(0)
            t = ["".join(x.astype(str)) for x in nc["Times"][:]]
            times += [datetime.strptime(s, "%Y-%m-%d_%H:%M:%S") for s in t]
            total = nc["RAINNC"][:].filled(0) + nc["RAINC"][:].filled(0)
            if "RAINSH" in nc.variables:
                total = total + nc["RAINSH"][:].filled(0)
            rain.append(total)                 # accumulated since model start (mm)
    return dict(lat=lat, lon=lon, land=land, times=np.array(times), acc=np.concatenate(rain))


def dist_km(lat, lon, p):
    la, lo = np.radians(lat), np.radians(lon)
    pla, plo = np.radians(p[0]), np.radians(p[1])
    a = np.sin((la - pla) / 2) ** 2 + np.cos(la) * np.cos(pla) * np.sin((lo - plo) / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(a))


def at(times, t):
    idx = np.where(times == t)[0]
    if len(idx) == 0:
        raise SystemExit(f"Time {t} not in output - check history_interval / run length")
    return idx[0]


rows, data = [], {}
for dom, res in DOMAINS.items():
    d = read_domain(dom)
    if d is None:
        print(f"{dom}: no files, skipped"); continue
    i0, i1 = at(d["times"], WIN_START), at(d["times"], WIN_END)
    day = d["acc"][i1] - d["acc"][i0]                    # 24 h rain in the IMD window
    dist = dist_km(d["lat"], d["lon"], SANTACRUZ)
    j, i = np.unravel_index(np.argmin(dist), dist.shape)
    box = (np.abs(d["lat"] - SANTACRUZ[0]) <= 0.125) & (np.abs(d["lon"] - SANTACRUZ[1]) <= 0.125)
    r25, r50 = dist <= 25, dist <= 50
    # wettest point inside the 3 km box area (same area for all domains, for fairness)
    area = (d["lat"] >= 17) & (d["lat"] <= 21) & (d["lon"] >= 70.7) & (d["lon"] <= 75)
    k = np.argmax(np.where(area, day, -1)); jm, im = np.unravel_index(k, day.shape)
    row = {"domain": dom, "grid": res,
           "point_mm": round(float(day[j, i]), 1),
           "box_0.25deg_mean_mm": round(float(day[box].mean()), 1) if box.any() else np.nan,
           "max_within_25km_mm": round(float(day[r25].max()), 1),
           "max_within_50km_mm": round(float(day[r50].max()), 1),
           "area_max_mm": round(float(day[jm, im]), 1),
           "area_max_lat": round(float(d["lat"][jm, im]), 2),
           "area_max_lon": round(float(d["lon"][jm, im]), 2),
           "area_max_dist_km": round(float(dist[jm, im]), 0)}
    rows.append(row)
    d.update(day=day, j=j, i=i, dist=dist)
    data[dom] = d

# ---------- 1. summary table ----------
with open(os.path.join(out_dir, "wrf_mumbai2005_summary.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

print("\n24-h rain, 26 Jul 03 UTC -> 27 Jul 03 UTC (IMD rain day ending 08:30 IST 27 Jul)")
print(f"{'':28s}{'point':>8s}{'0.25° box':>11s}{'max<25km':>10s}{'max<50km':>10s}")
for k, v in REF.items():
    print(f"{k:28s}{v:8.1f}")
for r in rows:
    print(f"{'WRF ' + r['grid']:28s}{r['point_mm']:8.1f}{r['box_0.25deg_mean_mm']:11.1f}"
          f"{r['max_within_25km_mm']:10.1f}{r['max_within_50km_mm']:10.1f}")
for r in rows:
    print(f"  WRF {r['grid']}: wettest point in Mumbai region = {r['area_max_mm']} mm at "
          f"{r['area_max_lat']}N {r['area_max_lon']}E ({r['area_max_dist_km']:.0f} km from Santacruz)")

# ---------- 2. bar chart: all sources ----------
labels = list(REF.keys()) + [f"WRF {r['grid']}" for r in rows]
vals = list(REF.values()) + [r["point_mm"] for r in rows]
cols = [C_OBS, C_OBS, C_AI, C_AI] + [C_WRF] * len(rows)
fig, ax = plt.subplots(figsize=(8, 4.2))
bars = ax.barh(labels[::-1], vals[::-1], color=cols[::-1], height=0.62)
for b, v in zip(bars, vals[::-1]):
    ax.text(b.get_width() + 8, b.get_y() + b.get_height() / 2, f"{v:.0f} mm", va="center", color=TEXT)
ax.set_xlabel("Rain on 26 July 2005 at Santacruz, Mumbai (mm in 24 h)")
ax.grid(axis="x", color=GRID); ax.set_axisbelow(True)
ax.set_xlim(0, max(vals) * 1.15)
ax.set_title("Mumbai 2005 flood day: observed vs predicted rain", loc="left", color=TEXT)
fig.text(0.01, 0.01, "Grey = observations, orange = ERA5 / AI model, blue = WRF (value at the grid cell nearest the gauge)",
         color=MUTED, fontsize=8)
fig.tight_layout(rect=(0, 0.04, 1, 1))
fig.savefig(os.path.join(out_dir, "fig_rain_sources.png"), dpi=200); plt.close(fig)

# ---------- 3. map of the 3 km rain ----------
if "d03" in data:
    d = data["d03"]
    levels = [0, 10, 35.5, 64.5, 115.6, 204.5, 400, 700, 1000, 2000]
    ramp = ["#ffffff", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#104281", "#0d366b"]
    cmap, norm = ListedColormap(ramp), BoundaryNorm(levels, len(ramp))
    fig, ax = plt.subplots(figsize=(6.6, 6))
    pm = ax.pcolormesh(d["lon"], d["lat"], d["day"], cmap=cmap, norm=norm, shading="auto")
    ax.contour(d["lon"], d["lat"], d["land"], levels=[0.5], colors=MUTED, linewidths=0.8)
    ax.plot(SANTACRUZ[1], SANTACRUZ[0], marker="o", ms=8, mfc="none", mec="#e34948", mew=2)
    ax.annotate("Santacruz\n(944 mm observed)", (SANTACRUZ[1], SANTACRUZ[0]), xytext=(10, -28),
                textcoords="offset points", color=TEXT, fontsize=9)
    cb = fig.colorbar(pm, ax=ax, shrink=0.85, ticks=levels)
    cb.set_label("24-h rain (mm)")
    fig.text(0.01, 0.01, "IMD classes: 64.5 mm heavy, 115.6 mm very heavy, 204.5 mm extremely heavy. Grey line = coast.", color=MUTED, fontsize=8)
    ax.set_xlabel("Longitude (°E)"); ax.set_ylabel("Latitude (°N)")
    ax.set_title("WRF 3 km rain, 26 Jul 2005 (08:30 IST to 08:30 IST)", loc="left", color=TEXT)
    ax.set_aspect("equal")
    fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(os.path.join(out_dir, "fig_wrf_d03_map.png"), dpi=200); plt.close(fig)

# ---------- 4. how the rain builds up at Santacruz ----------
fig, ax = plt.subplots(figsize=(8, 4.2))
hourly = {}
for dom, d in data.items():
    i0, i1 = at(d["times"], WIN_START), at(d["times"], WIN_END)
    t = d["times"][i0:i1 + 1]
    cum = d["acc"][i0:i1 + 1, d["j"], d["i"]] - d["acc"][i0, d["j"], d["i"]]
    hours = [(x - WIN_START).total_seconds() / 3600 for x in t]
    ax.plot(hours, cum, color=C_LINES[dom], lw=2, label=f"WRF {DOMAINS[dom]}: {cum[-1]:.0f} mm")
    hourly[dom] = (t, cum)
ax.axhline(944, color=C_OBS, lw=1.2, ls="--")
ax.text(0.3, 944 + 15, "Gauge total 944 mm", color=MUTED, fontsize=9)
ax.set_xlim(0, 24.5); ax.set_xticks(range(0, 25, 3))
ax.set_xticklabels([f"{(8 + h) % 24:02d}:30" for h in range(0, 25, 3)])
ax.set_xlabel("Time (IST), 26 Jul 08:30 to 27 Jul 08:30")
ax.set_ylabel("Rain so far (mm)")
ax.grid(color=GRID); ax.set_axisbelow(True); ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(0, 0.92))
ax.set_title("Rain building up at Santacruz during the flood day", loc="left", color=TEXT)
fig.tight_layout(); fig.savefig(os.path.join(out_dir, "fig_wrf_cumulative.png"), dpi=200); plt.close(fig)

# hourly table from the 3 km run (finest)
if "d03" in hourly:
    t, cum = hourly["d03"]
    with open(os.path.join(out_dir, "wrf_d03_santacruz_hourly.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["time_utc", "rain_this_hour_mm", "rain_since_0300utc_mm"])
        prev = 0.0
        for a, b in zip(t, cum):
            w.writerow([a.strftime("%Y-%m-%d %H:%M"), round(float(b - prev), 2), round(float(b), 1)]); prev = b

print("\nSaved in", out_dir)
for f in sorted(os.listdir(out_dir)):
    print("  ", f)
