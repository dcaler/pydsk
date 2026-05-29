"""Run a 32-MC Python ensemble for the M2 (financial) verification gate.

Identical harness to ``run_ensemble_M1.py`` (N1=50, N2=200, LS0=250000 to match
the on-disk C++ ``basecode/output_B/`` ensemble), but writes the macro frame —
which now carries the M2 fiscal/monetary fields added to ``Nation.save_outputs``
(government_debt, government_deficit, debt_on_gdp, policy_rate, bonds_rate,
n_bank_failures, government_bailout, tax_revenue) — to a M2-named parquet.

    py_macro_M2.parquet   one row per (mc_run, t)

The per-firm snapshot is not needed for M2 (no Pareto comparison), so only the
macro table is persisted.
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

# Reuse the M1 single-run worker verbatim — it already emits the macro rows
# (with the new M2 fields) via the OutputSink.
from run_ensemble_M1 import _run_one  # noqa: E402


def _worker(args):
    seed, t_max = args
    try:
        res = _run_one(seed, t_max)
        return {"macro": res["macro"]}
    except Exception as exc:  # pragma: no cover
        return {"error": repr(exc), "seed": seed}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n-runs", type=int, default=32)
    p.add_argument("--t-max", type=int, default=60)
    p.add_argument("--workers", type=int, default=min(16, mp.cpu_count()))
    p.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    args = p.parse_args()

    work = [(s, args.t_max) for s in range(args.n_runs)]
    t0 = time.time()
    print(f"Running {args.n_runs} MC reps x {args.t_max} steps on {args.workers} workers ...")
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
    macro_path = args.out_dir / "py_macro_M2.parquet"
    macro_df.to_parquet(macro_path, index=False)
    print(f"Wrote {macro_path}  ({len(macro_df):,} rows)")


if __name__ == "__main__":
    main()
