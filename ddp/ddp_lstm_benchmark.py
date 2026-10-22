# Distributed PyTorch (DDP) scaling test for an LSTM rainfall-runoff model, on CPU.
# Same kind of model as my NeuralHydrology run: LSTM (hidden 256) reading 365 days of
# forcing + catchment attributes and predicting streamflow.
#
# It trains the SAME model with 1, 2, 4, 8 ... worker processes. The work (global batch) is
# split between the workers and their gradients are averaged after every step (all-reduce).
# All workers together always use the same total number of CPU threads, so the comparison is fair.
#
# Usage:   python ddp_lstm_benchmark.py --threads 16 --workers 1 2 4 8
# Output:  ddp_results.csv  and  fig_ddp_scaling.png  in the current folder
import argparse, csv, os, platform, socket, time
import numpy as np
import torch
import torch.nn as nn
import torch.distributed as dist
import torch.multiprocessing as mp
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data import TensorDataset, DataLoader
from torch.utils.data.distributed import DistributedSampler


# ---------------------------------------------------------------- data
def make_data(n, seq, n_in, seed):
    """Synthetic CAMELS-like data: rain-like input -> slow 'river' response, plus static attributes."""
    g = torch.Generator().manual_seed(seed)
    rain = torch.relu(torch.randn(n, seq, generator=g)) ** 2                     # spiky rain
    temp = torch.sin(torch.linspace(0, 6.28, seq)).repeat(n, 1) + 0.1 * torch.randn(n, seq, generator=g)
    static = torch.rand(n, 1, n_in - 2, generator=g).expand(n, seq, n_in - 2)  # catchment attributes
    x = torch.cat([rain[..., None], temp[..., None], static], dim=2)
    k = 0.05 + 0.2 * static[:, 0, 0]                                             # basin "speed"
    q = torch.zeros(n)
    for t in range(seq):                                                         # linear reservoir
        q = (1 - k) * q + k * rain[:, t] * (1 + 0.3 * temp[:, t].clamp(min=0))
    return x.float(), q[:, None].float()


class LSTMModel(nn.Module):
    def __init__(self, n_in, hidden):
        super().__init__()
        self.lstm = nn.LSTM(n_in, hidden, batch_first=True)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.head(out[:, -1])


def nse(pred, obs):
    return 1 - ((pred - obs) ** 2).sum() / ((obs - obs.mean()) ** 2).sum()


# ---------------------------------------------------------------- one worker
def worker(rank, world, args, port, result_q):
    tpw = args.threads_per_worker if args.threads_per_worker > 0 else max(1, args.threads // world)
    torch.set_num_threads(tpw)
    os.environ["MASTER_ADDR"], os.environ["MASTER_PORT"] = "127.0.0.1", str(port)
    os.environ.setdefault("GLOO_SOCKET_IFNAME", "lo")
    dist.init_process_group("gloo", rank=rank, world_size=world)
    torch.manual_seed(0)

    x, y = make_data(args.samples, args.seq, args.inputs, seed=1)
    xv, yv = make_data(1024, args.seq, args.inputs, seed=2)
    ym, ys = y.mean(), y.std()                     # standardise the target (like NeuralHydrology does)
    y, yv = (y - ym) / ys, (yv - ym) / ys
    ds = TensorDataset(x, y)
    sampler = DistributedSampler(ds, num_replicas=world, rank=rank, shuffle=True, seed=0)
    loader = DataLoader(ds, batch_size=args.batch // world, sampler=sampler, drop_last=True)

    model = DDP(LSTMModel(args.inputs, args.hidden))
    opt = torch.optim.Adam(model.parameters(), lr=3e-3)
    lossf = nn.MSELoss()

    times = []
    for ep in range(args.epochs):
        sampler.set_epoch(ep)
        dist.barrier(); t0 = time.perf_counter()
        for xb, yb in loader:
            opt.zero_grad()
            loss = lossf(model(xb), yb)
            loss.backward()                      # DDP averages gradients across workers here
            opt.step()
        dist.barrier(); times.append(time.perf_counter() - t0)

    if rank == 0:
        model.eval()
        with torch.no_grad():
            score = float(nse(model.module(xv), yv))
        ep_time = float(np.mean(times[1:])) if len(times) > 1 else times[0]   # skip warm-up epoch
        result_q.put(dict(workers=world, threads_per_worker=tpw, total_threads=tpw * world,
                          epoch_time_s=round(ep_time, 2),
                          samples_per_s=round(args.samples / ep_time, 1),
                          val_NSE=round(score, 3)))
    dist.destroy_process_group()


# ---------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--threads", type=int, default=16, help="total CPU threads shared by all workers")
    p.add_argument("--workers", type=int, nargs="+", default=[1, 2, 4, 8])
    p.add_argument("--threads-per-worker", type=int, default=0,
                   help="0 = share --threads between workers (fixed hardware); "
                        "N = every worker gets N threads, so hardware grows with workers (classic scaling test)")
    p.add_argument("--samples", type=int, default=4096)
    p.add_argument("--seq", type=int, default=365)
    p.add_argument("--inputs", type=int, default=32)
    p.add_argument("--hidden", type=int, default=256)
    p.add_argument("--batch", type=int, default=256, help="global batch size (split across workers)")
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--out", default=".")
    args = p.parse_args()

    cpu = platform.processor() or "cpu"
    try:
        cpu = [l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")][0]
    except Exception:
        pass
    host = socket.gethostname()
    print(f"Machine: {host} | {cpu} | torch {torch.__version__}")
    print(f"LSTM hidden {args.hidden}, {args.seq}-day sequences, {args.samples} samples, "
          f"global batch {args.batch}")
    mode = "grow" if args.threads_per_worker > 0 else "fixed"
    print(("Mode: each worker gets %d thread(s) -> more workers = more cores\n" % args.threads_per_worker)
          if mode == "grow" else f"Mode: the same {args.threads} threads are shared by all workers\n")

    rows, ctx = [], mp.get_context("spawn")
    for i, w in enumerate(args.workers):
        q = ctx.Queue()
        mp.start_processes(worker, args=(w, args, 29500 + i, q), nprocs=w, start_method="spawn", join=True)
        r = q.get()
        rows.append(r)
        print(f"  {w:2d} worker(s): {r['epoch_time_s']:8.2f} s/epoch, {r['samples_per_s']:8.1f} samples/s, "
              f"NSE {r['val_NSE']:.3f}")

    base = rows[0]["epoch_time_s"] * rows[0]["workers"] / rows[0]["workers"]
    for r in rows:
        r["speedup"] = round(base / r["epoch_time_s"], 2)
        r["efficiency_pct"] = (round(100 * r["speedup"] / (r["workers"] / rows[0]["workers"]), 0)
                               if mode == "grow" else "")
        r.update(machine=host, cpu=cpu, mode=mode)

    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, f"ddp_results_{host}_{mode}.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    print(f"\n{'workers':>8s}{'threads':>9s}{'s/epoch':>10s}{'speedup':>9s}{'efficiency':>12s}{'NSE':>7s}")
    for r in rows:
        eff = f"{r['efficiency_pct']:11.0f}%" if mode == "grow" else f"{'-':>12s}"
        print(f"{r['workers']:8d}{r['total_threads']:9d}{r['epoch_time_s']:10.2f}{r['speedup']:9.2f}{eff}{r['val_NSE']:7.3f}")

    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        ws = [r["workers"] for r in rows]; sp = [r["speedup"] for r in rows]
        fig, ax = plt.subplots(figsize=(5.5, 4))
        if mode == "grow":
            ax.plot(ws, [w / ws[0] for w in ws], "--", color="#8a8984", lw=1.2, label="Ideal (perfect scaling)")
        ax.plot(ws, sp, "o-", color="#2a78d6", lw=2, ms=8, label=f"Measured ({host})")
        for w_, s_ in zip(ws, sp):
            ax.annotate(f"{s_:.2f}x", (w_, s_), textcoords="offset points", xytext=(6, -12), fontsize=9)
        ax.set_xlabel("Number of DDP workers"); ax.set_ylabel("Speedup vs 1 worker")
        ax.set_xticks(ws); ax.grid(color="#e4e3df"); ax.legend(frameon=False)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_title(f"LSTM training: {args.threads_per_worker} thread(s) per worker" if mode == "grow"
                     else f"LSTM training: same {args.threads} threads split into N workers", loc="left")
        fig.tight_layout(); fig.savefig(os.path.join(args.out, f"fig_ddp_{host}_{mode}.png"), dpi=200)
    except ImportError:
        pass
    print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
