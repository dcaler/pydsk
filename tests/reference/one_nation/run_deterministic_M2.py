"""Run Python in deterministic mode for the M2 gate (pairs with C++ out_Bd/).

Same configuration as ``run_deterministic_M1.py`` (N1=100, N2=400, LS0=500000,
matching the C++ ``dsk_B_det`` binary), but persists the macro frame — now
carrying the M2 fiscal/monetary fields — to a M2-named parquet.  This is the
RNG-free comparison that isolates the M2 financial machinery from stochastic
mean-skew (see M2_VERIFICATION_RESULT.md).

    py_det_M2.parquet   per-step macro aggregates (bit-identical across runs)
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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--t-max", type=int, default=60)
    p.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    args = p.parse_args()

    print(f"Running Python deterministic (M2), T={args.t_max} ...")
    t0 = time.time()
    out = run_deterministic(args.t_max, dump_firms_every=0)
    print(f"Done in {time.time() - t0:.1f}s.")

    macro_path = args.out_dir / "py_det_M2.parquet"
    out["macro"].to_parquet(macro_path, index=False)
    print(f"Wrote {macro_path}  ({len(out['macro']):,} rows)")


if __name__ == "__main__":
    main()
