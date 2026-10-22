# Kerala / Idukki flood, August 2018: WRF rain against the IMD 0.25 deg gridded rain.
# Window = the three IMD rain days labelled 15, 16 and 17 Aug 2018
#          (14 Aug 03:00 UTC to 17 Aug 03:00 UTC = 08:30 to 08:30 IST), the same window as FourCastNet.
# WRF 3 km rain is averaged into the IMD 0.25 deg boxes, so both are compared at the same grid size.
#
# Usage:
#   python compare_imd_kerala.py  <IMD 2018 .grd>  <output folder>  <label>=<WRF run folder> ...
# e.g.
#   python compare_imd_kerala.py ~/wrf/data/Rainfall_ind2018_rfp25.grd ~/wrf/results_kerala K1=~/wrf/cases/kerala2018/run
#
# Reads wrfrain_d03_* (rain-only hourly output) if present, otherwise wrfout_d03_*.
import sys, os, glob, csv
import numpy as np
from netCDF4 import Dataset
from datetime import datetime, timedelta
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap

imd_file = os.path.expanduser(sys.argv[1])
out_dir = os.path.expanduser(sys.argv[2]); os.makedirs(out_dir, exist_ok=True)
runs = [(a.split("=", 1)[0], os.path.expanduser(a.split("=", 1)[1])) for a in sys.argv[3:]]

WIN_START = datetime(2018, 8, 14, 3)
DAYS = [WIN_START + timedelta(days=k) for k in range(4)]          # day edges: 14,15,16,17 Aug 03 UTC
DAY_LABELS = ["15 Aug", "16 Aug", "17 Aug"]                        # IMD labels the day by its end morning
DAY_INDEX = [226, 227, 228]                                       # 0-based day of year 2018 for 15-17 Aug
REGION = dict(lat=(8.0, 12.0), lon=(74.75, 78.25))                 # inside the WRF 3 km box
IDUKKI = (9.85, 76.97)                                            # Idukki dam / Painavu area
REF = {"Observed (reports, basin)": 588.0, "IMD grid (FourCastNet study)": 455.5,
       "ERA5": 314.9, "FourCastNet": 302.8}
DAILY_T = [(64.5, "heavy"), (115.6, "very heavy"), (204.5, "extremely heavy")]
TOTAL_T = [(3 * t, n) for t, n in DAILY_T]                         # 3-day totals: 194, 347, 614 mm

TEXT, MUTED = "#0b0b0b", "#52514e"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED})

# ---------------- IMD ----------------
allimd = np.fromfile(imd_file, dtype="<f4").reshape(-1, 129, 135)
print(f"IMD file: {allimd.shape[0]} days")
imd_days = allimd[DAY_INDEX].astype(float)
imd_days[imd_days < -900] = np.nan
glat = 6.5 + 0.25 * np.arange(129); glon = 66.5 + 0.25 * np.arange(135)
js = np.where((glat >= REGION["lat"][0]) & (glat <= REGION["lat"][1]))[0]
is_ = np.where((glon >= REGION["lon"][0]) & (glon <= REGION["lon"][1]))[0]
rlat, rlon = glat[js], glon[is_]
imd_d = imd_days[:, js][:, :, is_]                                 # (3, ny, nx)
imd_tot = imd_d.sum(0)
valid = ~np.isnan(imd_tot)


def nearest_valid(lat0, lon0):
    d = np.hypot(rlat[:, None] - lat0, (rlon[None, :] - lon0) * np.cos(np.radians(lat0)))
    d = np.where(valid, d, np.inf); a, b = np.unravel_index(np.argmin(d), d.shape)
    return a, b


ia, ib = nearest_valid(*IDUKKI)
print(f"IMD cell nearest Idukki: {rlat[ia]:.2f}N {rlon[ib]:.2f}E -> "
      + ", ".join(f"{l}: {imd_d[k, ia, ib]:.1f}" for k, l in enumerate(DAY_LABELS))
      + f", 3-day total {imd_tot[ia, ib]:.1f} mm  (FourCastNet study used {REF['IMD grid (FourCastNet study)']} mm)")


# ---------------- WRF ----------------
def wrf_read(run_dir, dom="d03"):
    files = sorted(glob.glob(os.path.join(run_dir, f"wrfrain_{dom}_*"))) or \
            sorted(glob.glob(os.path.join(run_dir, f"wrfout_{dom}_*")))
    if not files:
        sys.exit(f"No wrfrain_{dom}_* or wrfout_{dom}_* files in {run_dir}")
    times, acc, lat, lon, hgt = [], [], None, None, None
    for f in files:
        with Dataset(f) as nc:
            if lat is None:
                lat = nc["XLAT"][0].filled(np.nan); lon = nc["XLONG"][0].filled(np.nan)
                hgt = nc["HGT"][0].filled(np.nan) if "HGT" in nc.variables else None
            times += [datetime.strptime("".join(x.astype(str)), "%Y-%m-%d_%H:%M:%S") for x in nc["Times"][:]]
            tot = nc["RAINNC"][:].filled(0) + nc["RAINC"][:].filled(0)
            if "RAINSH" in nc.variables:
                tot = tot + nc["RAINSH"][:].filled(0)
            acc.append(tot)
    times = np.array(times); acc = np.concatenate(acc)
    idx = []
    for t in DAYS:
        w = np.where(times == t)[0]
        if not len(w):
            sys.exit(f"{run_dir}: no output at {t:%Y-%m-%d %H:%M} (output runs {times[0]} to {times[-1]})")
        idx.append(w[0])
    days = np.stack([acc[idx[k + 1]] - acc[idx[k]] for k in range(3)])  # (3, ny, nx) at 3 km
    return lat, lon, hgt, days, os.path.basename(files[0]).split("_")[0]


def to_imd_grid(lat, lon, field):
    out = np.full(valid.shape, np.nan)
    for a, la in enumerate(rlat):
        for b, lo in enumerate(rlon):
            m = (np.abs(lat - la) <= 0.125) & (np.abs(lon - lo) <= 0.125)
            if m.sum() > 0:
                out[a, b] = field[m].mean()
    return np.where(valid, out, np.nan)


def km(p, q):
    return 111.2 * np.hypot(p[0] - q[0], (p[1] - q[1]) * np.cos(np.radians(10)))


def scores(f, o, thr):
    m = ~np.isnan(f) & ~np.isnan(o); f, o = f[m], o[m]
    s = {"mean_mm": f.mean(), "max_mm": f.max(), "bias_pct": 100 * (f.mean() - o.mean()) / o.mean(),
         "pattern_corr": np.corrcoef(f, o)[0, 1]}
    for t, _ in thr:
        hit = ((f >= t) & (o >= t)).sum(); miss = ((f < t) & (o >= t)).sum(); fa = ((f >= t) & (o < t)).sum()
        s[f"CSI_{t:g}"] = hit / (hit + miss + fa) if hit + miss + fa else np.nan
    return s


def peak(field):
    g = np.where(valid, field, -1); a, b = np.unravel_index(np.nanargmax(g), g.shape)
    return rlat[a], rlon[b]


ip = peak(imd_tot)
print(f"\nRegion {REGION['lat'][0]}-{REGION['lat'][1]}N, {REGION['lon'][0]}-{REGION['lon'][1]}E, "
      f"{valid.sum()} IMD land boxes; 3-day rain 14 Aug 03 UTC - 17 Aug 03 UTC 2018")
print(f"IMD: mean {np.nanmean(imd_tot):.0f} mm, max {np.nanmax(imd_tot):.0f} mm at {ip[0]:.2f}N {ip[1]:.2f}E\n")

rows, grid_fields, fine = [], {"IMD (observed)": imd_tot}, {}
hdr = (f"{'3-day total':16s}{'mean':>7s}{'max':>7s}{'bias%':>7s}{'corr':>6s}{'peak at':>16s}{'km off':>8s}"
       + "".join(f"{'CSI>' + format(t, '.0f'):>10s}" for t, _ in TOTAL_T))
print(hdr)
print(f"{'IMD (observed)':16s}{np.nanmean(imd_tot):7.0f}{np.nanmax(imd_tot):7.0f}{'':13s}{ip[0]:8.2f}N{ip[1]:6.2f}E")
point_rows = []
for label, d in runs:
    lat, lon, hgt, days, src = wrf_read(d)
    tot3 = days.sum(0)
    g_days = np.stack([to_imd_grid(lat, lon, days[k]) for k in range(3)])
    g_tot = g_days.sum(0)
    name = f"WRF {label}"
    grid_fields[name] = g_tot; fine[name] = (lat, lon, hgt, tot3)
    s = scores(g_tot, imd_tot, TOTAL_T); p = peak(g_tot)
    print(f"{name:16s}{s['mean_mm']:7.0f}{s['max_mm']:7.0f}{s['bias_pct']:7.0f}{s['pattern_corr']:6.2f}"
          f"{p[0]:8.2f}N{p[1]:6.2f}E{km(p, ip):8.0f}" + "".join(f"{s[f'CSI_{t:g}']:10.2f}" for t, _ in TOTAL_T))
    row = {"run": name, "period": "3-day", **{k: round(float(v), 3) for k, v in s.items()},
           "peak_lat": p[0], "peak_lon": p[1], "peak_km_from_imd_peak": round(float(km(p, ip)), 0)}
    rows.append(row)
    for k in range(3):
        sd = scores(g_days[k], imd_d[k], DAILY_T)
        rows.append({"run": name, "period": DAY_LABELS[k], **{kk: round(float(v), 3) for kk, v in sd.items()}})
    # point values at Idukki (3 km field)
    dist = 111.2 * np.hypot(lat - IDUKKI[0], (lon - IDUKKI[1]) * np.cos(np.radians(IDUKKI[0])))
    j, i = np.unravel_index(np.argmin(dist), dist.shape)
    box = (np.abs(lat - rlat[ia]) <= 0.125) & (np.abs(lon - rlon[ib]) <= 0.125)
    reg = (lat >= REGION["lat"][0]) & (lat <= REGION["lat"][1]) & (lon >= REGION["lon"][0]) & (lon <= REGION["lon"][1])
    rj, ri = np.unravel_index(np.argmax(np.where(reg, tot3, -1)), tot3.shape)
    point_rows.append(dict(run=name, source=src, at_idukki=tot3[j, i], imd_cell_mean=tot3[box].mean(),
                           max_25km=tot3[dist <= 25].max(), max_50km=tot3[dist <= 50].max(),
                           regional_peak=tot3[rj, ri], peak_lat=lat[rj, ri], peak_lon=lon[rj, ri]))

print("\nPer IMD day (daily thresholds 64.5 / 115.6 / 204.5 mm):")
print(f"{'':16s}{'day':>8s}{'IMD mean':>9s}{'WRF mean':>9s}{'corr':>6s}{'CSI>64':>8s}{'CSI>116':>8s}{'CSI>204':>8s}")
for r in rows:
    if r["period"] == "3-day":
        continue
    k = DAY_LABELS.index(r["period"])
    print(f"{r['run']:16s}{r['period']:>8s}{np.nanmean(imd_d[k]):9.0f}{r['mean_mm']:9.0f}{r['pattern_corr']:6.2f}"
          f"{r['CSI_64.5']:8.2f}{r['CSI_115.6']:8.2f}{r['CSI_204.5']:8.2f}")

print(f"\n3-day rain at Idukki (mm). For reference: " + ", ".join(f"{k} {v:g}" for k, v in REF.items()))
print(f"IMD cell used here ({rlat[ia]:.2f}N {rlon[ib]:.2f}E): {imd_tot[ia, ib]:.1f}")
print(f"{'':16s}{'at point':>9s}{'IMD cell':>9s}{'max<25km':>9s}{'max<50km':>9s}{'reg. peak':>10s}  peak location")
for r in point_rows:
    print(f"{r['run']:16s}{r['at_idukki']:9.1f}{r['imd_cell_mean']:9.1f}{r['max_25km']:9.1f}{r['max_50km']:9.1f}"
          f"{r['regional_peak']:10.1f}  {r['peak_lat']:.2f}N {r['peak_lon']:.2f}E (from {r['source']} files)")

with open(os.path.join(out_dir, "kerala_wrf_vs_imd_scores.csv"), "w", newline="") as fh:
    keys = sorted({k for r in rows for k in r}, key=lambda k: list(rows[0]).index(k) if k in rows[0] else 99)
    w = csv.DictWriter(fh, fieldnames=keys); w.writeheader(); w.writerows(rows)
with open(os.path.join(out_dir, "kerala_wrf_point_values.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(point_rows[0])); w.writeheader()
    w.writerows([{k: (round(float(v), 2) if not isinstance(v, str) else v) for k, v in r.items()} for r in point_rows])

# ---------------- maps ----------------
levels = [0, 25, 50, 100, 194, 347, 500, 614, 800, 1200]
ramp = ["#ffffff", "#e3eefc", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
cmap, norm = ListedColormap(ramp), BoundaryNorm(levels, len(ramp))
el = np.append(rlon - 0.125, rlon[-1] + 0.125); ea = np.append(rlat - 0.125, rlat[-1] + 0.125)
n = len(grid_fields)
fig, axes = plt.subplots(1, n, figsize=(3.0 * n + 1, 4.4), sharey=True)
for ax, (name, f) in zip(np.atleast_1d(axes), grid_fields.items()):
    pm = ax.pcolormesh(el, ea, f, cmap=cmap, norm=norm)
    ax.plot(IDUKKI[1], IDUKKI[0], "o", ms=6, mfc="none", mec="#e34948", mew=1.8)
    ax.set_title(name, loc="left", color=TEXT); ax.set_aspect("equal"); ax.set_xlabel("°E")
np.atleast_1d(axes)[0].set_ylabel("°N")
cb = fig.colorbar(pm, ax=axes, shrink=0.85, ticks=levels); cb.set_label("3-day rain (mm)")
fig.suptitle("Kerala floods: rain 14 Aug 03 UTC - 17 Aug 03 UTC 2018, all on the IMD 0.25° grid", x=0.01, ha="left")
fig.text(0.01, 0.01, "Red circle = Idukki. White = no IMD data (sea). 194 / 347 / 614 mm = 3 x IMD heavy / very heavy / "
         "extremely heavy daily rain.", color=MUTED, fontsize=8)
fig.savefig(os.path.join(out_dir, "fig_kerala_imd_vs_wrf.png"), dpi=200, bbox_inches="tight"); plt.close(fig)

for name, (lat, lon, hgt, tot3) in fine.items():
    fig, ax = plt.subplots(figsize=(5.2, 5.0))
    pm = ax.pcolormesh(lon, lat, tot3, cmap=cmap, norm=norm, shading="nearest")
    if hgt is not None:
        cs = ax.contour(lon, lat, hgt, levels=[500, 1000, 1500], colors=["#8a8984"], linewidths=0.6)
        ax.clabel(cs, fmt="%d m", fontsize=6)
    ax.plot(IDUKKI[1], IDUKKI[0], "o", ms=7, mfc="none", mec="#e34948", mew=1.8)
    ax.set_xlim(REGION["lon"]); ax.set_ylim(REGION["lat"]); ax.set_aspect("equal")
    ax.set_title(f"{name}: 3 km, 3-day rain (grey = terrain height)", loc="left", fontsize=9)
    fig.colorbar(pm, ax=ax, shrink=0.8, ticks=levels).set_label("mm")
    fig.savefig(os.path.join(out_dir, f"fig_kerala_{name.split()[-1]}_3km.png"), dpi=200, bbox_inches="tight")
    plt.close(fig)

print("\nSaved in", out_dir, ": kerala_wrf_vs_imd_scores.csv, kerala_wrf_point_values.csv, fig_kerala_*.png")
