#!/usr/bin/env bash
# =============================================================================
# Full Milestone-5 verification run (Python vs C++ / Wieners 2025 Figs 1-5).
#
#   Scenarios : 9  (baseline, Tc, T2, T2h, T2i, BE, CER, BCER, BCERT)
#   MC reps   : 64 per scenario  (matches the C++ 64-MC references)
#   Steps     : T = 220  (annual; climate starts t=80 ~ 2020)
#   Agents    : N1=100 capital firms, N2=400 consumption firms, LS0=500000, 1 nation
#
#   => 9 x 64 = 576 Python MC runs x 220 steps.
#   Wall-clock on a 32-core box: ~3.5-4 h ensembles + ~10 min C++ cache + <1 min notebook.
#
# Run from the repo root:  bash tests/reference/one_nation/RUN_FULL_VERIFICATION_M5.sh
# (or step through the blocks by hand).
#
# Outputs (all gitignored except the executed notebook):
#   py_macro_M5_<scenario>.parquet     Python ensembles  (regenerated)
#   cpp_ymc_M5_<scenario>.parquet      C++ macro refs    (cached)
#   cpp_micro_M5_<scenario>.parquet    C++ panels c/d/e  (cached)
#   M5_all_scenarios.ipynb             scored gate + verdict  (committed artifact)
# =============================================================================
set -euo pipefail

# Resolve repo root (dskPython2) regardless of where this is launched from.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
cd "$ROOT"
echo "repo root: $ROOT"
REF=tests/reference/one_nation

# Use all cores for the ensemble; lower --workers if you need the machine.
WORKERS=$(nproc)

# -----------------------------------------------------------------------------
# 1. (Optional) deterministic single-trajectory companions (baseline, Tc, T2).
#    Fast; not part of the 5.8 gate computation, kept for the structural cross-check.
# -----------------------------------------------------------------------------
python3 "$REF/run_deterministic_M5.py"

# -----------------------------------------------------------------------------
# 2. Python stochastic ensembles: 9 scenarios x 64 MC x 220 steps.   (~3.5-4 h)
#    Writes py_macro_M5_<scenario>.parquet (one row per mc_run x t).
# -----------------------------------------------------------------------------
python3 "$REF/run_ensemble_M5.py" --n-runs 64 --t-max 220 --workers "$WORKERS"

# -----------------------------------------------------------------------------
# 3. Cache the C++ 64-MC references (ymc macro + A1all_el/A1all_en/A2all_en micro).
#    Reads basecode/run_scenario_<S>/output_<S>/ ; writes cpp_{ymc,micro}_M5_<S>.parquet.
#    NOTE: the C++ BE and CER references from Task 5.7.3 are DEFECTIVE (no transition);
#          the notebook auto-detects this and scores BE/CER Python-vs-paper instead.
#          Rebuild those two C++ runs to score them Python-vs-C++.
# -----------------------------------------------------------------------------
python3 "$REF/cache_cpp_M5.py"

# -----------------------------------------------------------------------------
# 4. Regenerate the gate notebook source, then execute it (produces figures +
#    the PASS/REVIEW verdict in the last cell's stdout).
# -----------------------------------------------------------------------------
python3 "$REF/build_M5_all_scenarios_notebook.py"
jupyter nbconvert --to notebook --execute \
    "$REF/M5_all_scenarios.ipynb" --inplace --ExecutePreprocessor.timeout=1200

# -----------------------------------------------------------------------------
# 5. (Optional) regression check — full unit+integration suite (excl. slow SFC).
# -----------------------------------------------------------------------------
python3 -m pytest tests/ -q --deselect tests/integration/test_sfc_baseline_t1_t60.py

echo
echo "DONE. Open $REF/M5_all_scenarios.ipynb; the verdict is in the final cell."
echo "If this 64-MC run changes the verdict numbers, update planningDocs/M5_VERIFICATION_RESULT.md"
echo "(it currently records the 32-MC gate)."
