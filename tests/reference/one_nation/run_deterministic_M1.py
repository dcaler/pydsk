"""Run Python in deterministic mode against the C++ `dsk_B_det` configuration.

Pairs with the C++ binary `Code/Wieners_2025-main_slim/basecode/dsk_B_det`
(see `Makefile` target `scenario_B_det` and `planningDocs/RNG_AUDIT.md` §D).

Both sides are configured to the *current* `dsk_constant.h` defaults so
the comparison is apples-to-apples:

    N1  = 100      (capital-good firms)
    N2  = 400      (consumption-good firms)
    N1f = 100      (foreign firms)
    LS0 = 500_000  (initial labour supply)
    NB  = 20       (banks)        — set by experiment_setting.cpp:119 when N2==400

Output: `py_det_M1.parquet` (per-step macro aggregates) and
`py_det_firms_M1.parquet` (per-firm snapshot per step).  Bit-identical
across runs by construction.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from dsk.io.config import load_simulation
from dsk.io.output_sink import OutputSink
from dsk.rng import make_deterministic_rng


SIM_YAML = ROOT / "configs" / "simulations" / "one_nation_baseline.yaml"

# Match the current C++ dsk_constant.h defaults exactly (the values
# the deterministic binary was built with).
N1 = 100
N2 = 400
LS0 = 500_000.0


def run_deterministic(t_max: int, dump_firms_every: int = 1) -> dict:
    sim = load_simulation(str(SIM_YAML))
    gp = sim.global_params
    gp.n1_capital_good_firms = N1
    gp.n2_consumption_good_firms = N2
    gp.n1_foreign_firms = N1
    gp.labour_supply_init = LS0

    # Reset all nation generators to the deterministic generator.
    sink = OutputSink()
    sim.output_sink = sink
    for nation in sim.nations:
        nation.rng = make_deterministic_rng()
        nation.gparams = gp
        nation._mc_run = 0
        nation.sink = sink
        nation.initialise_from_parameters(gp)

    firm_rows: list[dict] = []
    for step in range(1, t_max + 1):
        sim.step()
        if dump_firms_every > 0 and (step % dump_firms_every == 0):
            nation = sim.nations[0]
            for j, firm in enumerate(nation.consumption_good_sector):
                if firm is None:
                    continue
                firm_rows.append(
                    {
                        "t": step,
                        "firm_id": j,
                        "sector": "s2",
                        "production": float(firm.production),
                        "sales": float(firm.sales),
                        "labour_demand": float(firm.labour_demand),
                        "price": float(firm.price),
                        "market_share": float(firm.market_share),
                        "net_worth": float(firm.net_worth),
                        "debt": float(firm.debt),
                        "expected_demand": float(getattr(firm, "expected_demand", 0.0)),
                    }
                )
            for i, firm in enumerate(nation.capital_good_sector):
                if firm is None:
                    continue
                firm_rows.append(
                    {
                        "t": step,
                        "firm_id": i,
                        "sector": "s1",
                        "production": float(firm.production),
                        "sales": float(firm.sales),
                        "labour_demand": float(firm.labour_demand),
                        "price": float(firm.price),
                        "market_share": float(firm.market_share),
                        "net_worth": float(firm.net_worth),
                        "debt": float(firm.debt),
                        "expected_demand": 0.0,
                    }
                )

    macro = pd.DataFrame(sink._rows["macro"])
    firms = pd.DataFrame(firm_rows)
    return {"macro": macro, "firms": firms}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--t-max", type=int, default=60)
    p.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    args = p.parse_args()

    print(
        f"Running Python deterministic, T={args.t_max}, "
        f"N1={N1}, N2={N2}, LS0={LS0:.0f} …"
    )
    t0 = time.time()
    out = run_deterministic(args.t_max, dump_firms_every=1)
    elapsed = time.time() - t0
    print(f"Done in {elapsed:.1f}s.")

    macro_path = args.out_dir / "py_det_M1.parquet"
    firms_path = args.out_dir / "py_det_firms_M1.parquet"
    out["macro"].to_parquet(macro_path, index=False)
    out["firms"].to_parquet(firms_path, index=False)
    print(f"Wrote {macro_path}  ({len(out['macro']):,} rows)")
    print(f"Wrote {firms_path}  ({len(out['firms']):,} rows)")


if __name__ == "__main__":
    main()
