"""Load the on-disk C++ basecode/output_B/ ensemble into tidy pandas frames.

The C++ ``out_<exp>_<scen>_<mc>.txt`` files are fixed-width, header-less,
with 42 columns per row. Headers live separately in ``output_<…>.txt``.

Column order is determined from ``dsk_main.cpp:8632-8788`` (the active
``void SAVE(void)`` function):

    1  t
    2  GDPm        nominal GDP
    3  GDP(1)      real GDP                      <- target
    4  EItot
    5  SItot
    6  dNtot
    7  Qtot1
    8  Qtot2
    9  Creal
    10 Ir
    11 Pitot1
    12 Pitot2
    13 Wtot1
    14 Wtot2
    15 LD
    16 U(1)        unemployment rate             <- target
    17 w(1)        wage                          <- target
    18 diff_w(1)
    19 cpi(1)
    20 diff_cpi(1)
    21 Am(1)       mean labour productivity      <- target
    22 A_sd
    23 rw
    24 Mutot
    25 G(1)
    26 Tax
    27 Def
    28 Deb
    29 DefonGDP
    30 DebonGDP
    31 next2bc
    32 Debt_all
    33 BankEquity_all
    34 BankCash_all
    35 BadDebt_all
    36 r_bonds
    37 countbf_all2
    38 r
    39 count_def2
    40 count_def_rec2
    41 Gbailout_all
    42 GDP_g2

Per-firm sector-2 production is in ``Qcons_<exp>_<scen>_<mc>.txt`` —
one row per time step, N2 columns of per-firm Q2. Used to estimate the
Pareto exponent of the firm-size distribution.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

OUT_B_DIR = (
    Path(__file__).resolve().parents[3].parent
    / "Wieners_2025-main_slim"
    / "basecode"
    / "output_B"
)

OUT_COLUMNS = [
    "t", "gdp_nominal", "gdp_real", "EItot", "SItot", "dNtot",
    "Qtot1", "Qtot2", "Creal", "Ir",
    "Pitot1", "Pitot2", "Wtot1", "Wtot2", "LD",
    "unemployment_rate", "wage", "diff_w", "cpi", "diff_cpi",
    "mean_machine_prod", "A_sd", "rw", "Mutot",
    "G", "Tax", "Def", "Deb", "DefonGDP", "DebonGDP",
    "next2bc", "Debt_all", "BankEquity_all", "BankCash_all", "BadDebt_all",
    "r_bonds", "countbf_all2", "r", "count_def2", "count_def_rec2",
    "Gbailout_all", "GDP_g2",
]
assert len(OUT_COLUMNS) == 42


def _list_mc_files(prefix: str, out_dir: Path = OUT_B_DIR) -> list[Path]:
    """Return ``<prefix>_<exp>_<scen>_<mc>.txt`` files, sorted by mc index."""
    rx = re.compile(rf"^{re.escape(prefix)}_(\d+)_(\d+)_(\d+)\.txt$")
    found = []
    for p in out_dir.iterdir():
        m = rx.match(p.name)
        if m:
            found.append((int(m.group(3)), p))
    found.sort()
    return [p for _, p in found]


def load_cpp_macro_ensemble(out_dir: Path = OUT_B_DIR) -> pd.DataFrame:
    """Concatenate ``out_*.txt`` files into a long (mc_run, t, …) frame."""
    paths = _list_mc_files("out", out_dir)
    if not paths:
        raise FileNotFoundError(f"No out_*.txt found under {out_dir}")
    frames = []
    for path in paths:
        mc = int(path.stem.rsplit("_", 1)[-1])
        arr = np.loadtxt(path)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if arr.shape[1] != len(OUT_COLUMNS):
            raise ValueError(
                f"{path.name}: expected {len(OUT_COLUMNS)} cols, got {arr.shape[1]}"
            )
        df = pd.DataFrame(arr, columns=OUT_COLUMNS)
        df.insert(0, "mc_run", mc)
        df["t"] = df["t"].astype(int)
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    return out


# --------------------------------------------------------------------------
# M3 energy/climate per-MC time series — ymc_*.txt (80 columns)
#
# Column order is determined from dsk_main.cpp:8825-9007 (the active SAVE() ymc
# write block).  Only the columns the M3 gate compares are named here; the rest
# are tagged `ymc_NN_unused` so the assert on column count stays honest.
# --------------------------------------------------------------------------

YMC_COLUMNS = [
    "t",                          # 1
    "gdp_real",                   # 2  GDP(1)
    "consumption_real",           # 3  Creal
    "investment_real",            # 4  Ir
    "unemployment_rate",          # 5  U(1)
    "DefonGDP",                   # 6
    "DebonGDP",                   # 7
    "cpi",                        # 8  cpi(1)
    "diff_cpi",                   # 9
    "Am",                         # 10 Am(1)
    "Def",                        # 11
    "Deb",                        # 12
    "wage",                       # 13 w(2)
    "diff_w",                     # 14 diff_w(2)
    "dNtot",                      # 15
    "share_energy_green",         # 16 Share_energy_green     <- M3 target
    "total_energy_demand",        # 17 D_en_TOT               <- M3 target
    "emissions_yearly_calib",     # 18 Emiss_yearly_calib(1)
    "Cat",                        # 19
    "Tmixed",                     # 20
    "r",                          # 21
    "r_bonds",                    # 22
    "r_marktomarket",             # 23
    "bonds_dem_tot",              # 24
    "bonds_sup_tot",              # 25
    "BaselBankCredit_all",        # 26
    "CreditSupply_all_a",         # 27
    "share_CB",                   # 28
    "Debt_all",                   # 29
    "BankDeposits_all",           # 30
    "DebtRemittances_all",        # 31
    "BankEquity_all",             # 32
    "BankProfits_all",            # 33
    "BankCash_all",               # 34
    "BadDebt_all",                # 35
    "MultiplierBankCredit_all",   # 36
    "CreditSupply_all",           # 37
    "CreditDemand_all",           # 38
    "r_bonds_b",                  # 39
    "DFB",                        # 40
    "countbf_all2",               # 41
    "r_b",                        # 42
    "count_def2",                 # 43
    "count_def_rec2",             # 44
    "Gbailout_all",               # 45
    "Clim_policy_cost",           # 46
    "RD1tot",                     # 47
    "electricity_price",          # 48 c_en(1)                <- M3 target
    "fossil_fuel_price",          # 49 pf
    "carbon_tax_per_fuel_s1",     # 50
    "carbon_tax_per_fuel_en",     # 51
    "energy_firm_profit",         # 52 Pi_en
    "d1_fossil_fuel_demand",      # 53 D1_ff_TOT
    "emissions_s1_process",       # 54 Emiss1EF
    "emissions_s1_fuel",          # 55 Emiss1FF
    "emissions_energy",           # 56 Emiss_en_eff           <- M3 target
    "A_de",                       # 57
    "CF_de",                      # 58
    "CF_ge",                      # 59
    "plant_worth_lost",           # 60
    "tp_CO2_TOT_plus_elfrac",     # 61
    "Gbailout_en",                # 62
    "Am1",                        # 63
    "Am2",                        # 64
    "Pitot1",                     # 65
    "Pitot2",                     # 66
    "Wtot1",                      # 67
    "Wtot2",                      # 68
    "H1",                         # 69
    "H2",                         # 70
    "Inntot1",                    # 71
    "Immtot1",                    # 72
    "LD1rdtot",                   # 73
    "LDrd_en",                    # 74
    "LDexp_en",                   # 75
    "LDff_tot",                   # 76
    "LD1tot",                     # 77
    "LD2tot",                     # 78
    "next2bc",                    # 79
    "GDP_nominal",                # 80 GDPm
]
assert len(YMC_COLUMNS) == 80


def load_cpp_ymc_ensemble(out_dir: Path = OUT_B_DIR) -> pd.DataFrame:
    """Concatenate the C++ ``ymc_*.txt`` files into a (mc_run, t, ...) frame.

    Use the ymc table for the M3+ verification gates — it carries the energy /
    climate / fiscal-monetary columns that the M3 metrics live in (energy share,
    electricity price, emissions, fossil-fuel demand, etc.).  The M1/M2 macro
    table (``out_*.txt``) does not include these.
    """
    paths = _list_mc_files("ymc", out_dir)
    if not paths:
        raise FileNotFoundError(f"No ymc_*.txt found under {out_dir}")
    frames = []
    for path in paths:
        mc = int(path.stem.rsplit("_", 1)[-1])
        arr = np.loadtxt(path)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if arr.shape[1] != len(YMC_COLUMNS):
            raise ValueError(
                f"{path.name}: expected {len(YMC_COLUMNS)} cols, got {arr.shape[1]}"
            )
        df = pd.DataFrame(arr, columns=YMC_COLUMNS)
        df.insert(0, "mc_run", mc)
        df["t"] = df["t"].astype(int)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


# --------------------------------------------------------------------------
# M5 scenario ensembles — basecode/run_scenario_<S>/output_<S>/ymc_*.txt
#
# These are the *paper-level* runs (N1=100, N2=400, LS0=500000, T=220, 64 MC,
# mc indices 100-163) used to build the paper's Figure 1.  The on-disk set
# covers all scenarios once Task 5.7.3 is complete:
#   Carbon-pricing: B, Tc, T2, T2h, T2i    (compiled from standard dsk_main.cpp)
#   Green-industrial-policy: BE, CER, BCER, BCERT   (compiled from BCERT overlay;
#     see basecode/Makefile BCERT_SCENARIOS; runs launched by Task 5.7.3)
# --------------------------------------------------------------------------

_BASECODE_DIR = (
    Path(__file__).resolve().parents[3].parent / "Wieners_2025-main_slim" / "basecode"
)

# Python scenario name -> C++ scenario tag (directory suffix).
# Carbon-pricing scenarios: compiled from basecode/dsk_main.cpp (standard).
# Green-industrial-policy scenarios: compiled from files_BCERT/0_dsk_main.cpp
#   (BCERT overlay) with per-scenario -D flags; see basecode/Makefile BCERT_SCENARIOS.
_SCENARIO_CPP_TAG = {
    "baseline": "B",
    "B": "B",
    "Tc": "Tc",
    "T2": "T2",
    "T2h": "T2h",
    "T2i": "T2i",
    # Green-industrial-policy scenarios (Figs 3-5 of Wieners 2025)
    "BE": "BE",       # Brown ban + Electrification mandate (no subsidy, no tax)
    "CER": "CER",     # Construction subsidy + Electrification + R&D (no ban, no tax)
    "BCER": "BCER",   # Brown ban + CER (no tax)
    "BCERT": "BCERT", # Brown ban + CER + Carbon tax
}


def cpp_scenario_ymc_dir(scenario: str) -> Path:
    """Return ``run_scenario_<tag>/output_<tag>`` for a scenario name."""
    tag = _SCENARIO_CPP_TAG.get(scenario, scenario)
    return _BASECODE_DIR / f"run_scenario_{tag}" / f"output_{tag}"


def load_cpp_scenario_ymc(scenario: str) -> pd.DataFrame:
    """Load the C++ paper-level ymc ensemble for one carbon-pricing scenario.

    Returns a long (mc_run, t, ...) frame with the 80 YMC_COLUMNS.  Raises
    FileNotFoundError if the scenario has no on-disk C++ output (e.g. BCERT).
    """
    out_dir = cpp_scenario_ymc_dir(scenario)
    if not out_dir.is_dir():
        raise FileNotFoundError(
            f"No C++ output dir for scenario {scenario!r}: {out_dir}"
        )
    return load_cpp_ymc_ensemble(out_dir)


# --------------------------------------------------------------------------
# M5 FULL gate — per-firm micro files for Wieners Fig 1/3 panels c, d, e.
#
# The paper plots simple firm-means of three technical coefficients written by
# the C++ SAVE (dsk_main.cpp:5804-5945, flag_clim_tech==1 branch):
#   A1all_el_*.txt   A1p_el(i)  N1 cols  cap-good electrification fraction   panel e
#   A1all_en_*.txt   A1p_en(i)  N1 cols  cap-good energy use / unit output   panel d
#   A2all_en_*.txt   A2_en(j)   N2 cols  cons-good electricity / unit output panel c
#     (dead sector-2 firms written as "NaN" -> nanmean)
# Each file is one row per period; the paper takes ``.mean(axis=1)`` per row.
# --------------------------------------------------------------------------

# Python macro column  ->  (C++ micro-file prefix, aggregator)
_MICRO_PANELS = {
    "mean_elfrac_s1": "A1all_el",     # panel e
    "mean_energy_use_s1": "A1all_en",  # panel d
    "mean_elec_use_s2": "A2all_en",    # panel c
}


def _load_micro_firmmean(out_dir: Path, prefix: str) -> pd.DataFrame:
    """Per-(mc_run, t) firm-mean of one micro file (nanmean over firms)."""
    paths = _list_mc_files(prefix, out_dir)
    if not paths:
        raise FileNotFoundError(f"No {prefix}_*.txt under {out_dir}")
    rows = []
    for path in paths:
        mc = int(path.stem.rsplit("_", 1)[-1])
        # genfromtxt so the literal "NaN" entries (dead firms) parse to np.nan.
        arr = np.genfromtxt(path)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        means = np.nanmean(arr, axis=1)
        for i, m in enumerate(means):
            rows.append({"mc_run": mc, "t": i + 1, prefix: float(m)})
    return pd.DataFrame(rows)


def load_cpp_scenario_micro(scenario: str) -> pd.DataFrame:
    """Per-(mc_run, t) firm-means of panels c/d/e for one scenario.

    Returns a long frame with columns
    ``mc_run, t, mean_elfrac_s1, mean_energy_use_s1, mean_elec_use_s2`` — the
    same names the Python ``save_outputs`` records, so the notebook can compare
    them directly.  Raises FileNotFoundError if the scenario has no C++ output.
    """
    out_dir = cpp_scenario_ymc_dir(scenario)
    if not out_dir.is_dir():
        raise FileNotFoundError(
            f"No C++ output dir for scenario {scenario!r}: {out_dir}"
        )
    merged: pd.DataFrame | None = None
    for py_col, prefix in _MICRO_PANELS.items():
        df = _load_micro_firmmean(out_dir, prefix).rename(columns={prefix: py_col})
        merged = df if merged is None else merged.merge(df, on=["mc_run", "t"])
    return merged


def load_cpp_qcons_snapshot(t_snapshot: int, out_dir: Path = OUT_B_DIR) -> pd.DataFrame:
    """Return one row per (mc_run, firm_id) of Q2 at ``t_snapshot``."""
    paths = _list_mc_files("Qcons", out_dir)
    if not paths:
        raise FileNotFoundError(f"No Qcons_*.txt under {out_dir}")
    rows = []
    for path in paths:
        mc = int(path.stem.rsplit("_", 1)[-1])
        arr = np.loadtxt(path)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if t_snapshot < 1 or t_snapshot > arr.shape[0]:
            raise IndexError(
                f"{path.name}: t={t_snapshot} out of range [1,{arr.shape[0]}]"
            )
        # File rows are written starting at t=1 (one row per period).
        snapshot = arr[t_snapshot - 1]
        for j, q in enumerate(snapshot):
            rows.append({"mc_run": mc, "firm_id": j, "production": float(q)})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = load_cpp_macro_ensemble()
    print("Macro frame:", df.shape)
    print(df.groupby("t")[["gdp_real", "unemployment_rate", "wage",
                           "mean_machine_prod"]].mean().head(10))
    print(df.groupby("t")[["gdp_real", "unemployment_rate", "wage",
                           "mean_machine_prod"]].mean().tail(5))
    qc = load_cpp_qcons_snapshot(60)
    print("\nQcons snapshot at t=60:", qc.shape,
          "min", qc.production.min(), "max", qc.production.max())
