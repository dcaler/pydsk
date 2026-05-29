"""Labour market — wage-setting and labour-rationing singleton per Nation.

Mirrors C++ nation-level labour variables from dsk_globalvar.h:
LS, w[2], U[2], diff_w, ueff, Am[2], A[2], A2[1], N1r, N2r.
Not an AgentSet — no heterogeneous workers in v3.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dsk.nation import Nation
    from dsk.parameters.global_parameters import GlobalParameters
    from dsk.parameters.nation_parameters import NationParameters


class LabourMarket:
    """Wage-setting and labour-rationing logic. Not an AgentSet — no heterogeneous workers in v3."""

    def __init__(self, nation: "Nation") -> None:
        self.nation = nation

        # --- Labour supply ---
        # LS: total labour force (exogenous; grows at labour_supply_growth rate)
        self.labour_supply: float = 500_000.0
        self.labour_supply_prev: float = 500_000.0

        # --- Wage ---
        # w[2]: wage (two-period array; index 1=current, 2=prev-period)
        self.wage: float = 1.0           # w(1) = current-period wage
        self.wage_prev: float = 1.0      # w(2) = previous-period wage

        # diff_w: wage change (= w(1) - w(2)) — used in wage-inflation index
        self.wage_change: float = 0.0

        # --- Unemployment ---
        # U[2]: unemployment rate time series (flagWAGE uses unemployment gap)
        # U(2)=1 in C++ INITIALIZE — this is the *previous-period* slot, set to 1.
        # Interpretation: initial employment rate is 1 (= full employment; u = 0).
        self.unemployment_rate: float = 0.0      # U(1): current period (computed in MACRO)
        self.unemployment_rate_prev: float = 0.0  # U(2): previous period

        # ueff: effective unemployment (may differ from headline when flagWAGE varies)
        self.effective_unemployment: float = 0.0

        # --- Labour demand aggregates (computed in PRODMACH, MACRO) ---
        self.labour_demand_total: float = 0.0   # aggregate LD = LD1 + LD2
        self.labour_demand_s1: float = 0.0      # LD1tot
        self.labour_demand_s2: float = 0.0      # LD2tot
        self.labour_demand_rd: float = 0.0      # LD1rdtot (R&D labour in sector 1)

        # --- Mean productivities (economy-wide aggregates, updated in MACRO) ---
        # Am[2]: mean labour productivity of machines in use
        self.mean_machine_prod: float = 1.0      # Am(1)
        self.mean_machine_prod_prev: float = 1.0  # Am(2)
        # A[2]: mean labour productivity of sector-2 production processes
        self.mean_process_prod: float = 1.0      # A(1)
        self.mean_process_prod_prev: float = 1.0  # A(2)

        # --- Wage-subsidy pass-through from Government ---
        # Subwage(1,2,3): sector-1, sector-2, aggregate wage subsidies/taxes
        self.wage_subsidy: list = [0.0, 0.0, 0.0]

        # --- GDP growth rate (used in flagWAGE==3 wage rule) ---
        self.gdp_growth: float = 0.0

    # ------------------------------------------------------------------

    def initialise_from_parameters(
        self,
        gparams: "GlobalParameters",
        nparams: "NationParameters",
    ) -> None:
        """Set labour-market initial state to C++ INITIALIZE baseline.

        C++ lines 1072–1078, 1234–1241.
        """
        # LS = LS0; w = w0 (C++ lines 1072, 1234)
        self.labour_supply = gparams.labour_supply_init         # LS = LS0 = 500000
        self.labour_supply_prev = gparams.labour_supply_init
        self.wage = gparams.wage_init                           # w = w0 = 1.0
        self.wage_prev = gparams.wage_init                      # w(2) = w0

        # C++ INITIALIZE at dsk_main.cpp:1237 seeds U(2) = 1.  This is *not*
        # "100% unemployment in the prior period"; it's a numerical pivot
        # that makes the t=1 wage formula's d_U = (U(1) − U(2)) / U(2)
        # come out very negative (clamped to −mdw = −0.5), so the term
        # −psi3·d_U pushes wages *up* in the first period.
        #
        # Python's `aggregate_macro_indicators` shifts the unemployment
        # state with `unemployment_rate_prev = unemployment_rate` *before*
        # the wage formula reads it.  So to land the same pivot at the
        # first wage call, we have to seed `unemployment_rate` itself
        # (not `_prev`) to 1.0 — at t=1's MACRO it gets shifted into
        # `_prev` and the new U(1) is written on top.  Setting
        # `_prev = 1.0` directly would just be clobbered on line 1209
        # of nation.py.  See planningDocs/build_log.md entry
        # "Wage init mismatch" for the full diagnostic.
        #
        # Nothing else reads `unemployment_rate` before MACRO runs at
        # t=1 (verified by grep), so the seed is observation-safe.
        self.unemployment_rate = 1.0
        self.unemployment_rate_prev = 1.0
        self.effective_unemployment = 0.0
        self.wage_change = 0.0

        # Labour demand: 0 at t=0 (production hasn't run yet)
        self.labour_demand_total = 0.0
        self.labour_demand_s1 = 0.0
        self.labour_demand_s2 = 0.0
        self.labour_demand_rd = 0.0

        # Mean productivities: start at A0 = productivity_init
        a0 = gparams.productivity_init                          # A0 = 1.0
        self.mean_machine_prod = a0                             # Am(2) = A0
        self.mean_machine_prod_prev = a0
        self.mean_process_prod = a0                             # A(1) initialized later
        self.mean_process_prod_prev = a0

        # Wage subsidies: 0 at start (Subwage(1,2,3) = 0)
        self.wage_subsidy = [0.0, 0.0, 0.0]

        self.gdp_growth = 0.0
