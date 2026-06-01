"""Cache the C++ paper-level scenario references to parquet for the M5 FULL gate.

For each scenario with on-disk C++ output, writes two parquets in this dir:
    cpp_ymc_M5_<scenario>.parquet     long (mc_run, t, <80 ymc cols>)
    cpp_micro_M5_<scenario>.parquet   long (mc_run, t, panels c/d/e firm-means)

Reading the raw text ensembles (64 MC x {ymc + 3 micro files}) is slow on the
NFS share, so the notebook reads these caches instead.  Re-run only when the
C++ output changes.

    python3 tests/reference/one_nation/cache_cpp_M5.py
    python3 tests/reference/one_nation/cache_cpp_M5.py --scenarios BE CER
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

NB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(NB_DIR))

import load_cpp_basecode as L  # noqa: E402

ALL = ["baseline", "Tc", "T2", "T2h", "T2i", "BE", "CER", "BCER", "BCERT"]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--scenarios", nargs="+", default=ALL)
    args = p.parse_args()

    for s in args.scenarios:
        t0 = time.time()
        try:
            ymc = L.load_cpp_scenario_ymc(s)
            ymc.to_parquet(NB_DIR / f"cpp_ymc_M5_{s}.parquet", index=False)
            micro = L.load_cpp_scenario_micro(s)
            micro.to_parquet(NB_DIR / f"cpp_micro_M5_{s}.parquet", index=False)
            print(
                f"[{s}] ymc {ymc.shape} ({ymc.mc_run.nunique()} MC), "
                f"micro {micro.shape} -> cached in {time.time() - t0:.0f}s"
            )
        except FileNotFoundError as exc:
            print(f"[{s}] SKIP (no C++ ref): {exc}")


if __name__ == "__main__":
    main()
