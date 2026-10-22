# Compares the WRF rain map with the IMD 0.25 deg gridded rain for the Mumbai flood day
# (24 h ending 08:30 IST, 27 Jul 2005). WRF 3 km rain is averaged into the same 0.25 deg boxes
# as IMD, so both are compared at the same grid size.
#
# Usage:
#   python compare_with_imd.py  <IMD .grd file>  <output folder>  <label1>=<run folder1>  <label2>=<run folder2> ...
# e.g.
#   python compare_with_imd.py ~/wrf/data/Rainfall_ind2005_rfp25.grd ~/wrf/results_imd \
#        A_25Jul=~/wrf/cases/mumbai2005/run  B_26Jul=~/wrf/cases/mumbai2005_late/run \
#        C_Thompson=~/wrf/cases/mumbai2005_thompson/run
import sys, os, glob, csv
import numpy as np
from netCDF4 import Dataset
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap

imd_file = os.path.expanduser(sys.argv[1])
out_dir = os.path.expanduser(sys.argv[2]); os.makedirs(out_dir, exist_ok=True)
runs = [(a.split("=", 1)[0], os.path.expanduser(a.split("=", 1)[1])) for a in sys.argv[3:]]

WIN_START, WIN_END = datetime(2005, 7, 26, 3), datetime(2005, 7, 27, 3)
FLOOD_DAY_INDEX = 207            # IMD file: day labelled 27 Jul (the morning it was measured) = flood day
REGION = dict(lat=(17.0, 21.0), lon=(72.5, 75.0))     # area covered by the WRF 3 km box
SANTACRUZ = (19.09, 72.85)
THRESH = [(64.5, "heavy"), (115.6, "very heavy"), (204.5, "extremely heavy")]

TEXT, MUTED = "#0b0b0b", "#52514e"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED})

# ---------- IMD ----------
imd = np.fromfile(imd_file, dtype="<f4").reshape(-1, 129, 135)[FLOOD_DAY_INDEX].astype(float)
imd[imd < -900] = np.nan
glat = 6.5 + 0.25 * np.arange(129); glon = 66.5 + 0.25 * np.arange(135)
js = np.where((glat >= REGION["lat"][0]) & (glat <= REGION["lat"][1]))[0]
is_ = np.where((glon >= REGION["lon"][0]) & (glon <= REGION["lon"][1]))[0]
imd_r = imd[np.ix_(js, is_)]; rlat, rlon = glat[js], glon[is_]
valid = ~np.isnan(imd_r)


# ---------- WRF -> 0.25 deg boxes ----------
def wrf_day(run_dir, dom="d03"):
    files = sorted(glob.glob(os.path.join(run_dir, f"wrfout_{dom}_*")))
    times, acc, lat, lon = [], [], None, None
    for f in files:
        with Dataset(f) as nc:
            if lat is None:
                lat = nc["XLAT"][0].filled(np.nan); lon = nc["XLONG"][0].filled(np.nan)
            times += [datetime.strptime("".join(x.astype(str)), "%Y-%m-%d_%H:%M:%S") for x in nc["Times"][:]]
            tot = nc["RAINNC"][:].filled(0) + nc["RAINC"][:].filled(0)
            if "RAINSH" in nc.variables:
                tot = tot + nc["RAINSH"][:].filled(0)
            acc.append(tot)
    times = np.array(times); acc = np.concatenate(acc)
    i0, i1 = np.where(times == WIN_START)[0][0], np.where(times == WIN_END)[0][0]
    return lat, lon, acc[i1] - acc[i0]


def to_imd_grid(lat, lon, day):
    out = np.full(imd_r.shape, np.nan)
    for a, la in enumerate(rlat):
        for b, lo in enumerate(rlon):
            m = (np.abs(lat - la) <= 0.125) & (np.abs(lon - lo) <= 0.125)
            if m.sum() > 0:
                out[a, b] = day[m].mean()
    return out


def scores(f, o):
    m = valid & ~np.isnan(f)
    f, o = f[m], o[m]
    s = {"mean_mm": f.mean(), "max_mm": f.max(), "bias_pct": 100 * (f.mean() - o.mean()) / o.mean(),
         "rmse_mm": np.sqrt(((f - o) ** 2).mean()), "pattern_corr": np.corrcoef(f, o)[0, 1]}
    for t, name in THRESH:
        hit = ((f >= t) & (o >= t)).sum(); miss = ((f < t) & (o >= t)).sum(); fa = ((f >= t) & (o < t)).sum()
        s[f"POD_{t}"] = hit / (hit + miss) if hit + miss else np.nan
        s[f"FAR_{t}"] = fa / (hit + fa) if hit + fa else np.nan
        s[f"CSI_{t}"] = hit / (hit + miss + fa) if hit + miss + fa else np.nan
    return s


def peak_place(field):
    g = np.where(valid, field, -1); a, b = np.unravel_index(np.nanargmax(g), g.shape)
    return rlat[a], rlon[b]


def km(p, q):
    return 111.2 * np.hypot(p[0] - q[0], (p[1] - q[1]) * np.cos(np.radians(19)))


fields = {"IMD (observed)": imd_r}
for label, d in runs:
    lat, lon, day = wrf_day(d)
    fields[f"WRF {label}"] = np.where(valid, to_imd_grid(lat, lon, day), np.nan)

# ---------- table ----------
ip = peak_place(imd_r)
rows = []
print(f"\nRegion {REGION['lat'][0]}-{REGION['lat'][1]}N, {REGION['lon'][0]}-{REGION['lon'][1]}E, "
      f"{valid.sum()} IMD land boxes (0.25 deg), flood day 26 Jul 2005\n")
hdr = f"{'':18s}{'mean':>7s}{'max':>7s}{'bias%':>7s}{'corr':>6s}{'peak at':>15s}{'km off':>7s}" \
      f"{'CSI>64':>8s}{'CSI>116':>8s}{'CSI>204':>8s}"
print(hdr)
for name, f in fields.items():
    p = peak_place(f)
    if name.startswith("IMD"):
        print(f"{name:18s}{np.nanmean(imd_r[valid]):7.0f}{np.nanmax(imd_r):7.0f}{'':7s}{'':6s}"
              f"{p[0]:7.2f}N{p[1]:6.2f}E{'':7s}")
        continue
    s = scores(f, imd_r)
    print(f"{name:18s}{s['mean_mm']:7.0f}{s['max_mm']:7.0f}{s['bias_pct']:7.0f}{s['pattern_corr']:6.2f}"
          f"{p[0]:7.2f}N{p[1]:6.2f}E{km(p, ip):7.0f}"
          f"{s['CSI_64.5']:8.2f}{s['CSI_115.6']:8.2f}{s['CSI_204.5']:8.2f}")
    rows.append({"run": name, **{k: round(float(v), 3) for k, v in s.items()},
                 "peak_lat": p[0], "peak_lon": p[1], "peak_km_from_imd_peak": round(float(km(p, ip)), 0)})

with open(os.path.join(out_dir, "wrf_vs_imd_scores.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

# ---------- maps, all at 0.25 deg ----------
levels = [0, 10, 35.5, 64.5, 115.6, 204.5, 400, 700, 1000]
ramp = ["#ffffff", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
cmap, norm = ListedColormap(ramp), BoundaryNorm(levels, len(ramp))
n = len(fields)
fig, axes = plt.subplots(1, n, figsize=(3.1 * n + 1, 4.6), sharey=True)
edges_lon = np.append(rlon - 0.125, rlon[-1] + 0.125); edges_lat = np.append(rlat - 0.125, rlat[-1] + 0.125)
for ax, (name, f) in zip(np.atleast_1d(axes), fields.items()):
    pm = ax.pcolormesh(edges_lon, edges_lat, f, cmap=cmap, norm=norm)
    ax.plot(SANTACRUZ[1], SANTACRUZ[0], "o", ms=6, mfc="none", mec="#e34948", mew=1.8)
    ax.set_title(name, loc="left", color=TEXT); ax.set_aspect("equal")
    ax.set_xticks([73, 74, 75]); ax.set_xlabel("°E")
np.atleast_1d(axes)[0].set_ylabel("°N")
cb = fig.colorbar(pm, ax=axes, shrink=0.8, ticks=levels); cb.set_label("24-h rain (mm)")
fig.suptitle("Flood-day rain, 26 Jul 2005 (08:30 to 08:30 IST), all on the IMD 0.25° grid", x=0.01, ha="left", color=TEXT)
fig.text(0.01, 0.01, "Red circle = Santacruz. White = no IMD data (sea). IMD heavy 64.5, very heavy 115.6, "
         "extremely heavy 204.5 mm.", color=MUTED, fontsize=8)
fig.savefig(os.path.join(out_dir, "fig_imd_vs_wrf_maps.png"), dpi=200, bbox_inches="tight"); plt.close(fig)

print("\nSaved:", os.path.join(out_dir, "wrf_vs_imd_scores.csv"), "and fig_imd_vs_wrf_maps.png")
