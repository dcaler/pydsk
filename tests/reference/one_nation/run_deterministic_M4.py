"""Run Python in deterministic mode for the M4 (climate) verification gate.

Pairs with the C++ basecode ``out_Bd/`` deterministic trajectory (N1=100, N2=400)
and writes a 220-period macro frame that now carries the M4 climate fields
added to ``Nation.save_outputs`` (``atmospheric_carbon``, ``surface_temperature``,
``emissions_yearly_calib``) on top of the M3 energy fields.

The C++ deterministic binary aborts somewhere around t=208; we run the full
220 by default so the Python trajectory tracks the C++ over the whole climate-
active window (climate box first fires at t = ``climate_start_step + 1`` = 81).

    py_det_M4.parquet   per-step macro aggregates (bit-identical across runs)
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_deterministic_M1 import run_deterministic  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--t-max", type=int, default=220)
    p.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    args = p.parse_args()

    print(f"Running Python deterministic (M4), T={args.t_max} ...")
    t0 = time.time()
    out = run_deterministic(args.t_max, dump_firms_every=0)
    print(f"Done in {time.time() - t0:.1f}s.")

    macro_path = args.out_dir / "py_det_M4.parquet"
    out["macro"].to_parquet(macro_path, index=False)
    print(f"Wrote {macro_path}  ({len(out['macro']):,} rows)")


if __name__ == "__main__":
    main()
