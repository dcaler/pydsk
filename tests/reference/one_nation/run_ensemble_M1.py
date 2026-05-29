"""Run a 32-MC Python ensemble of the M1 baseline simulation.

Configures N1=50, N2=200 to match the on-disk C++ basecode output_B/ ensemble,
runs T=60 steps per replicate, and writes parquet files for the macro time
series and the per-firm sector-2 sales snapshot (used downstream to estimate
the Pareto firm-size exponent).

Cached outputs land in this directory:
    py_macro_M1.parquet      one row per (mc_run, t)
    py_firm_snapshot_M1.parquet   one row per (mc_run, firm_id) at t=spin_up
"""
from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# Make `dsk` importable when running from anywhere.
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from dsk.io.config import load_simulation
from dsk.io.output_sink import OutputSink


SIM_YAML = ROOT / "configs" / "simulations" / "one_nation_baseline.yaml"

# Match C++ basecode/output_B/ which was produced with the pre-doubled
# N1=50, N2=200, LS0=250000 settings. Both dsk_constant.h.orig_N50 and the
# in-tree dsk_constant.h comment "//250000→500000 (doubled for 2-eco
# verification)" confirm the pre-doubling baseline.
N1_OVERRIDE = 50
N2_OVERRIDE = 200
LS_INIT_OVERRIDE = 250_000.0


def _run_one(seed: int, t_max: int) -> dict:
    sim = load_simulation(str(SIM_YAML))
    gp = sim.global_params
    gp.n1_capital_good_firms = N1_OVERRIDE
    gp.n2_consumption_good_firms = N2_OVERRIDE
    gp.n1_foreign_firms = N1_OVERRIDE
    gp.labour_supply_init = LS_INIT_OVERRIDE

    # Wire a fresh sink (load_simulation set one, but we re-init below).
    sink = OutputSink()
    sim.output_sink = sink

    # Re-seed at the master level to get reproducibility per MC run.
    from dsk.rng import make_master_rng, spawn_nation_rng

    master = make_master_rng(seed)
    for nation in sim.nations:
        nation.rng = spawn_nation_rng(master, nation.nation_id)
        nation.gparams = gp
        nation._mc_run = seed
        nation.sink = sink
        nation.initialise_from_parameters(gp)

    for _ in range(1, t_max + 1):
        sim.step()

    # The OutputSink "macro" table is written by Nation.save_outputs *before*
    # update_state_for_next_period — so labour_demand_total and the wage are
    # captured pre-reset. Pulling raw nation attributes post-step misses this.
    macro_rows = list(sink._rows["macro"])

    # Per-firm snapshot at the final step (for Pareto exponent estimation).
    nation = sim.nations[0]
    firm_rows = []
    for j, firm in enumerate(nation.consumption_good_sector):
        if firm is None:
            continue
        firm_rows.append(
            {
                "mc_run": seed,
                "firm_id": j,
                "production": float(firm.production),
                "sales": float(firm.sales),
                "market_share": float(firm.market_share),
            }
        )

    return {"macro": macro_rows, "firms": firm_rows}


def _worker(args):
    seed, t_max = args
    try:
        return _run_one(seed, t_max)
    except Exception as exc:  # pragma: no cover
        return {"error": repr(exc), "seed": seed}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n-runs", type=int, default=32, help="number of MC replicates")
    p.add_argument("--t-max", type=int, default=60, help="steps per replicate")
    p.add_argument(
        "--workers",
        type=int,
        default=min(16, mp.cpu_count()),
        help="multiprocessing workers",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="output directory for parquet files",
    )
    args = p.parse_args()

    seeds = list(range(args.n_runs))
    work = [(s, args.t_max) for s in seeds]

    t0 = time.time()
    print(
        f"Running {args.n_runs} MC reps × {args.t_max} steps "
        f"(N1={N1_OVERRIDE}, N2={N2_OVERRIDE}) "
        f"on {args.workers} workers …"
    )
    if args.workers == 1:
        results = [_worker(w) for w in work]
    else:
        with mp.Pool(args.workers) as pool:
            results = pool.map(_worker, work)
    elapsed = time.time() - t0
    print(f"Done in {elapsed:.1f}s ({elapsed/args.n_runs:.2f}s/run avg).")

    failed = [r for r in results if "error" in r]
    if failed:
        for f in failed:
            print(f"  seed {f['seed']} FAILED: {f['error']}")
        raise SystemExit(1)

    macro_df = pd.DataFrame(
        [row for r in results for row in r["macro"]]
    ).sort_values(["mc_run", "t"]).reset_index(drop=True)
    firm_df = pd.DataFrame(
        [row for r in results for row in r["firms"]]
    ).sort_values(["mc_run", "firm_id"]).reset_index(drop=True)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    macro_path = args.out_dir / "py_macro_M1.parquet"
    firm_path = args.out_dir / "py_firm_snapshot_M1.parquet"
    macro_df.to_parquet(macro_path, index=False)
    firm_df.to_parquet(firm_path, index=False)

    print(f"Wrote {macro_path}  ({len(macro_df):,} rows)")
    print(f"Wrote {firm_path}   ({len(firm_df):,} rows)")


if __name__ == "__main__":
    main()
