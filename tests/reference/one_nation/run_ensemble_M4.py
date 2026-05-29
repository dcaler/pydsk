"""Run a 32-MC Python ensemble for the M4 (climate) verification gate.

Identical harness to ``run_ensemble_M3.py`` (N1=50, N2=200, LS0=250000 to match
the on-disk C++ ``basecode/output_B/`` ensemble) but writes a 220-period frame
so the climate-active window (t > climate_start_step = 80) is fully sampled.

The macro frame now carries the M4 climate fields added to ``Nation.save_outputs``:
``atmospheric_carbon``, ``surface_temperature``, ``emissions_yearly_calib``.

    py_macro_M4.parquet   one row per (mc_run, t)
"""
from __future__ import annotations

import argparse
import multiprocessing as mp
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Reuse the M1 single-run worker verbatim — it emits the macro rows (now with
# the M3 energy and M4 climate fields) via the OutputSink.
from run_ensemble_M1 import _run_one  # noqa: E402


def _worker(args):
    seed, t_max = args
    try:
        res = _run_one(seed, t_max)
        return {"macro": res["macro"]}
    except Exception as exc:  # pragma: no cover
        return {"error": repr(exc), "seed": seed}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n-runs", type=int, default=32)
    p.add_argument("--t-max", type=int, default=220)
    p.add_argument("--workers", type=int, default=min(16, mp.cpu_count()))
    p.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    args = p.parse_args()

    work = [(s, args.t_max) for s in range(args.n_runs)]
    t0 = time.time()
    print(
        f"Running {args.n_runs} MC reps x {args.t_max} steps on {args.workers} workers ..."
    )
    if args.workers == 1:
        results = [_worker(w) for w in work]
    else:
        with mp.Pool(args.workers) as pool:
            results = pool.map(_worker, work)
    print(f"Done in {time.time() - t0:.1f}s.")

    failed = [r for r in results if "error" in r]
    if failed:
        for f in failed:
            print(f"  seed {f['seed']} FAILED: {f['error']}")
        raise SystemExit(1)

    macro_df = (
        pd.DataFrame([row for r in results for row in r["macro"]])
        .sort_values(["mc_run", "t"])
        .reset_index(drop=True)
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    macro_path = args.out_dir / "py_macro_M4.parquet"
    macro_df.to_parquet(macro_path, index=False)
    print(f"Wrote {macro_path}  ({len(macro_df):,} rows)")


if __name__ == "__main__":
    main()
