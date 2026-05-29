"""Nation parameters dataclass — N-scope configuration parameters from NAME_MAP §11/§12/§15.

These are the per-nation policy and banking knobs listed in the KS15 baseline
comment at the bottom of dsk_constant.h, plus the fossil-fuel price override
(v3 Appendix B item 7).  Runtime state (aggregates, time-series, etc.) lives on
Nation and sector objects built in Tasks 0.7+.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=False)
class NationParameters:
    """Per-nation parameters.

    Defaults mirror the C++ baseline that ships with
    ``Code/Wieners_2025-main_slim/basecode/``.  Several of these are
    NOT the values declared in ``dsk_constant.h`` — that file is the
    "knob inventory", and ``auxiliary/experiment_setting.cpp::
    EXPERIMENT_INITIALIZE`` overrides the active baseline values at
    runtime in the ``if (experiment == 0)`` branch (lines 103-129).
    The overrides are documented per-field below.  We carry the
    *overridden* values as defaults, since they are what an actual
    baseline run uses.
    """

    # --- Banking structure ---
    n_banks: int = 10                     # NB; baseline for N2=200; doubled N2 keeps 10 per economy

    # --- Fiscal / labour-market policy ---
    unemployment_benefit_share: float = 0.7    # wu = 0.4 * 7/4 (experiment_setting.cpp:115)
    tax_rate_firms_wages: float = 0.1          # aliq
    tax_rate_banks: float = 0.1                # aliqb (= aliq baseline)
    deficit_rule: float = 0.03                 # def_rule — SGP 3% stability-pact ceiling

    # --- Monetary policy ---
    policy_rate: float = 0.02                  # r (experiment_setting.cpp:107: r=0.02)
    taylor_rule_inflation_coef: float = 1.1    # taylor1
    taylor_rule_unemployment_coef: float = 0.0 # taylor2 (0 when flagTAYLOR=2)
    beta_basel: float = 1.0                    # Basel-II credit multiplier coefficient

    # --- Credit and banking ---
    credit_multiplier: float = 0.16              # 0.08 * 2 (experiment_setting.cpp:105)
    bank_reserve_requirement_rate: float = 0.16  # = credit_multiplier (experiment_setting.cpp:106)
    bank_markup_init_rate: float = 0.3           # bankmarkup — initial uniform loan markup

    # --- Consumption-good sector ---
    s2_markup_init: float = 0.15              # mi2 (experiment_setting.cpp:118 — was 0.2 in dsk_constant.h placeholder)
    s2_markup_step_change: float = 0.01       # deltami2

    # --- Wage equation ---
    wage_inflation_response: float = 0.05     # psi1
    wage_unemployment_response: float = 0.1   # psi3 = 0.05 * 2 (experiment_setting.cpp:123)

    # --- Energy / fossil fuels ---
    fossil_fuel_price: float = 0.02           # pf — per-nation runtime value (= pf0 initially)

    # --- Entry ---
    entry_size_multiplier: float = 1.0        # multip_entry
