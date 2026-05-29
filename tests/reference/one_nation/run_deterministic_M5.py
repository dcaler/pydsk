"""Run Python deterministic-mode trajectories per scenario for the M5 gate.

The C++ side only ships a deterministic baseline (``basecode/out_Bd/``, N1=100,
N2=400, t up to 208).  There is no deterministic Tc / T2 on disk, so the
deterministic certificate proper is baseline-only (as in M1-M4).  We still emit
deterministic Tc / T2 trajectories here because the *policy delta* between two
deterministic Python runs (scenario minus baseline) is the cleanest, RNG-noise-
free way to read the direction and magnitude of each instrument's effect inside
the Python model — which the notebook compares against the C++ stochastic policy
delta.

Writes one parquet per scenario:
    py_det_M5_<scenario>.parquet
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dsk.io.config import load_simulation
from dsk.io.output_sink import OutputSink
from dsk.rng import make_deterministic_rng

N1 = 100
N2 = 400
LS0 = 500_000.0

SCENARIO_YAML = {
    "baseline": ROOT / "configs" / "simulations" / "one_nation_baseline.yaml",
    "Tc": ROOT / "configs" / "simulations" / "one_nation_Tc.yaml",
    "T2": ROOT / "configs" / "simulations" / "one_nation_T2.yaml",
}


def run_deterministic_scenario(scenario: str, t_max: int) -> pd.DataFrame:
    sim = load_simulation(str(SCENARIO_YAML[scenario]))
    gp = sim.global_params
    gp.n1_capital_good_firms = N1
    gp.n2_consumption_good_firms = N2
    gp.n1_foreign_firms = N1
    gp.labour_supply_init = LS0

    sink = OutputSink()
    sim.output_sink = sink
    for nation in sim.nations:
        nation.rng = make_deterministic_rng()
        nation.gparams = gp
        nation._mc_run = 0
        nation.sink = sink
        nation.initialise_from_parameters(gp)

    for _ in range(1, t_max + 1):
        sim.step()
    return pd.DataFrame(sink._rows["macro"])


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--scenarios", nargs="+", default=["baseline", "Tc", "T2"])
    p.add_argument("--t-max", type=int, default=220)
    p.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    args = p.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for scenario in args.scenarios:
        print(f"[{scenario}] deterministic, T={args.t_max} ...")
        t0 = time.time()
        df = run_deterministic_scenario(scenario, args.t_max)
        print(f"[{scenario}] done in {time.time() - t0:.1f}s.")
        out_path = args.out_dir / f"py_det_M5_{scenario}.parquet"
        df.to_parquet(out_path, index=False)
        print(f"[{scenario}] wrote {out_path}  ({len(df):,} rows)")


if __name__ == "__main__":
    main()
