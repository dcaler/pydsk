"""Run per-scenario Python MC ensembles for the M5 (climate-policy) gate.

Unlike the M1-M4 ensemble runners (which used the N1=50 config to match the
top-level ``basecode/output_B/`` ensemble), the M5 gate compares against the
*paper-level* scenario runs in ``basecode/run_scenario_<S>/output_<S>/`` which
were produced with the full N1=100, N2=400, LS0=500000 config and 64 MC reps
(mc 100-163), T=220.  So this runner matches that configuration.

Each scenario loads its own simulation YAML (so its ``policy:`` block — e.g. the
CarbonTax instrument for Tc / T2 — is attached by ``load_simulation``), then the
per-MC worker re-seeds the nation RNG and re-initialises agents, leaving the
climate-policy container intact.

Writes one parquet per scenario:
    py_macro_M5_<scenario>.parquet     one row per (mc_run, t)

Usage:
    python3 run_ensemble_M5.py                       # 9 ref scenarios ; 64 MC ; T=220
    python3 run_ensemble_M5.py --scenarios baseline Tc T2 --n-runs 64
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

from dsk.io.config import load_simulation
from dsk.io.output_sink import OutputSink
from dsk.rng import make_master_rng, spawn_nation_rng

# Full paper-level config — matches basecode/run_scenario_<S>/output_<S>/.
N1 = 100
N2 = 400
LS0 = 500_000.0

# Scenarios with on-disk C++ reference ensembles (Task 5.7.3 built the
# green-industrial set BE/CER/BCER/BCERT; the carbon-pricing set B/Tc/T2/T2h/T2i
# pre-dates the partial gate).  TD2/TDh/Tsec/ET2/RT2/BCR have no C++ reference
# (not built — exponential/sector tax commented out in the current C++ source).
_SIMDIR = ROOT / "configs" / "simulations"
SCENARIO_YAML = {
    "baseline": _SIMDIR / "one_nation_baseline.yaml",
    "Tc": _SIMDIR / "one_nation_Tc.yaml",
    "T2": _SIMDIR / "one_nation_T2.yaml",
    "T2h": _SIMDIR / "one_nation_T2h.yaml",
    "T2i": _SIMDIR / "one_nation_T2i.yaml",
    "BE": _SIMDIR / "one_nation_BE.yaml",
    "CER": _SIMDIR / "one_nation_CER.yaml",
    "BCER": _SIMDIR / "one_nation_BCER.yaml",
    "BCERT": _SIMDIR / "one_nation_BCERT.yaml",
}


def _run_one(args) -> dict:
    scenario, seed, t_max = args
    try:
        sim = load_simulation(str(SCENARIO_YAML[scenario]))
        gp = sim.global_params
        gp.n1_capital_good_firms = N1
        gp.n2_consumption_good_firms = N2
        gp.n1_foreign_firms = N1
        gp.labour_supply_init = LS0

        sink = OutputSink()
        sim.output_sink = sink

        master = make_master_rng(seed)
        for nation in sim.nations:
            nation.rng = spawn_nation_rng(master, nation.nation_id)
            nation.gparams = gp
            nation._mc_run = seed
            nation.sink = sink
            nation.initialise_from_parameters(gp)
            # climate_policy container is left intact (attached by load_simulation).

        for _ in range(1, t_max + 1):
            sim.step()

        return {"scenario": scenario, "macro": list(sink._rows["macro"])}
    except Exception as exc:  # pragma: no cover
        return {"error": repr(exc), "scenario": scenario, "seed": seed}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--scenarios",
        nargs="+",
        default=["baseline", "Tc", "T2", "T2h", "T2i", "BE", "CER", "BCER", "BCERT"],
    )
    p.add_argument("--n-runs", type=int, default=64)   # match the C++ 64-MC references
    p.add_argument("--t-max", type=int, default=220)
    p.add_argument("--workers", type=int, default=min(24, mp.cpu_count()))
    p.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    args = p.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    for scenario in args.scenarios:
        if scenario not in SCENARIO_YAML:
            raise SystemExit(f"Unknown scenario {scenario!r}; known: {list(SCENARIO_YAML)}")
        work = [(scenario, s, args.t_max) for s in range(args.n_runs)]
        t0 = time.time()
        print(
            f"[{scenario}] {args.n_runs} MC x {args.t_max} steps "
            f"(N1={N1}, N2={N2}) on {args.workers} workers ..."
        )
        if args.workers == 1:
            results = [_run_one(w) for w in work]
        else:
            with mp.Pool(args.workers) as pool:
                results = pool.map(_run_one, work)
        print(f"[{scenario}] done in {time.time() - t0:.1f}s.")

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
        out_path = args.out_dir / f"py_macro_M5_{scenario}.parquet"
        macro_df.to_parquet(out_path, index=False)
        print(f"[{scenario}] wrote {out_path}  ({len(macro_df):,} rows)")


if __name__ == "__main__":
    main()
