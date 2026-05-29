"""Central bank (monetary authority) — singleton per Nation.

Mirrors C++ nation-level monetary variables from dsk_globalvar.h:
r (policy rate), Loans_CB, spread_marktomarket, mean_rdeb_all, Loan_profit_share.
The Taylor rule (TAYLOR, module_macro.cpp:263) is implemented in apply_taylor_rule().
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dsk.nation import Nation
    from dsk.parameters.global_parameters import GlobalParameters
    from dsk.parameters.nation_parameters import NationParameters


class CentralBank:
    """Monetary authority. Sets policy rate via Taylor rule, remunerates reserves."""

    def __init__(self, nation: "Nation") -> None:
        self.nation = nation

        # --- Policy rate and derived rates ---
        # r: central-bank base rate
        self.policy_rate: float = 0.02
        # r_depo = r*(1-bankmarkdown): deposit rate paid by banks to firm depositors
        self.deposit_rate: float = 0.0
        # r_cbreserves = r*(1-centralbankmarkdown): CB pays this on bank cash reserves
        self.cb_reserves_rate: float = 0.0
        # r_bonds = r*(1-bondsmarkdown) or fixed 0.01 if flag_bonds==2
        self.bonds_rate: float = 0.0

        # --- CB balance sheet ---
        # Loans_CB: outstanding CB loans to commercial banks (e.g. quantitative easing)
        self.loans_to_banks: float = 0.0

        # --- dskQE state ---
        # spread_marktomarket: mark-to-market spread on bonds (= 0 when flag_mtm=0)
        self.spread_marktomarket: float = 0.0
        # r_marktomarket = r + spread_marktomarket
        self.marktomarket_rate: float = 0.0
        # Loan_profit_share: share of bank loan profit repatriated to CB (dskQE)
        self.loan_profit_share: float = 0.0

        # --- Aggregate banking summaries ---
        # mean_rdeb_all: economy-wide mean lending rate
        self.mean_lending_rate: float = 0.0
        # Leverage: total bank leverage (Loans / Equity)
        self.leverage: float = 0.0

        # --- Bonds held by CB (purchased as residual buyer in bond market) ---
        self.bonds_held: float = 0.0
        # share_CB / count_share_def: running sum and count of Newbonds_financed/Def,
        # used by SAVEFINAL to report the mean share of the deficit financed by the CB.
        self.cb_bonds_share: float = 0.0      # share_CB
        self.count_share_def: int = 0         # count_share_def

        # --- Taylor rule targets (set from GlobalParameters at init) ---
        self.inflation_target: float = 0.005      # d_cpi_target = 0.02/4
        self.unemployment_target: float = 0.05    # ustar

        # --- Stats accumulators (for SAVEFINAL output) ---
        # avg_r: accumulated r across all steps and MC runs
        self.avg_rate_sum: float = 0.0
        # count_zerobound: steps where ZLB was binding
        self.zero_bound_count: int = 0

    # ------------------------------------------------------------------

    def initialise_from_parameters(
        self,
        gparams: "GlobalParameters",
        nparams: "NationParameters",
    ) -> None:
        """Set central-bank initial state to C++ baseline.

        C++ INITIALIZE line 1059: spread_marktomarket = 0.01.
        C++ experiment_setting.cpp experiment==0: r=0.02, r_base=r.
        """
        r = nparams.policy_rate                    # r = 0.02
        self.policy_rate = r
        self.deposit_rate = r * (1.0 - gparams.deposit_markdown)
        self.cb_reserves_rate = r * (1.0 - gparams.cb_reserve_markdown)
        if gparams.bonds_rate_rule == 2:
            self.bonds_rate = 0.01
        else:
            self.bonds_rate = r * (1.0 - gparams.bonds_markdown)
        self.marktomarket_rate = r                 # spread = 0 at init

        self.spread_marktomarket = 0.01            # C++ INITIALIZE: spread_marktomarket=0.01
        self.loan_profit_share = 0.0
        self.loans_to_banks = 0.0
        self.bonds_held = 0.0
        self.cb_bonds_share = 0.0
        self.count_share_def = 0
        self.mean_lending_rate = 0.0
        self.leverage = 0.0
        self.avg_rate_sum = 0.0
        self.zero_bound_count = 0

        self.inflation_target = gparams.inflation_target          # d_cpi_target
        self.unemployment_target = gparams.unemployment_target    # ustar

    # ------------------------------------------------------------------

    def apply_taylor_rule(self, inflation: float, unemployment: float) -> None:
        """Set policy rate via Taylor rule and derive all dependent rates.

        Implements C++ TAYLOR() in module_macro.cpp:263 for flagTAYLOR=2
        (inflation-gap + unemployment-gap rule).

        Parameters
        ----------
        inflation : float
            d_cpi = (cpi(1) - cpi(2)) / cpi(2) — CPI inflation rate this period.
        unemployment : float
            U(1) — current unemployment rate.
        """
        gparams = self.nation.gparams
        nparams = self.nation.params

        # r_base is a FIXED anchor set once at init (experiment_setting.cpp:114
        # `r_base = r`), NOT the lagged policy rate. Anchoring on the lagged rate
        # makes the rule integral: once it hits the zero lower bound it stays
        # stuck there. C++ flagTAYLOR=2 returns r_base in steady state (gaps→0).
        r_base = nparams.policy_rate           # = 0.02 (the baseline natural rate)
        taylor1 = nparams.taylor_rule_inflation_coef
        taylor2 = nparams.taylor_rule_unemployment_coef

        # flagTAYLOR=2: r = r_base + taylor1*(d_cpi - d_cpi_target) + taylor2*(ustar - U)
        r = (
            r_base
            + taylor1 * (inflation - self.inflation_target)
            + taylor2 * (self.unemployment_target - unemployment)
        )

        # Zero lower bound (C++ TAYLOR line 307)
        if r <= 0.0:
            r = 1e-6
            self.zero_bound_count += 1

        self.policy_rate = r
        self.avg_rate_sum += r

        # Derived rates (C++ TAYLOR lines 309-314)
        self.deposit_rate = r * (1.0 - gparams.deposit_markdown)
        self.cb_reserves_rate = r * (1.0 - gparams.cb_reserve_markdown)
        if gparams.bonds_rate_rule == 2:
            self.bonds_rate = 0.01
        else:
            self.bonds_rate = r * (1.0 - gparams.bonds_markdown)

        # Bank lending rates: r_deb(j) = r*(1+bankmarkup(j)) for flagSPREAD=0
        if gparams.endogenous_bank_markup == 0:
            for bank in self.nation.banking_sector:
                bank.lending_rate = r * (1.0 + bank.markup)

        # dskQE: mark-to-market spread (flag_mtm=0 → spread always 0)
        if gparams.use_dskqe:
            if gparams.mark_to_market_rule == 0:
                self.spread_marktomarket = 0.0
            # flag_mtm=1 branch (complex spread computation) deferred to Task 2.5
        self.marktomarket_rate = r + self.spread_marktomarket

    def remunerate_reserves(self, banks) -> None:
        """Store reserve interest income per bank for use in BANKING profit calculation.

        C++ BANKING: BankProfits(j) includes r_cbreserves * BankCash(2,j).
        Called before Bank.compute_profit_and_dividend() so BANKING can read
        bank.reserve_interest_income directly.

        Parameters
        ----------
        banks : iterable of Bank
        """
        rate = self.cb_reserves_rate
        for bank in banks:
            bank.reserve_interest_income = rate * bank.cash_prev

    def buy_residual_bonds(self, residual: float, deficit: float) -> None:
        """Absorb the deficit not financed by commercial banks (dskQE residual buyer).

        Makes explicit the implicit C++ behaviour: after the bank-allocation loop in
        GOV_BUDGET, the leftover Newbonds_financed is financed by the central bank via
        money creation (C++ tracks only share_CB += Newbonds_financed/Def). Here the CB
        holds those residual bonds as a stock so the bond market clears exactly:
        total new bonds issued = bank purchases + CB residual purchase.

        Parameters
        ----------
        residual : float
            Newbonds_financed left after banks bought all they could (>= 0).
        deficit : float
            Def — total new bonds issued this period; the share_CB denominator.
        """
        if residual < 0.0:
            residual = 0.0
        self.bonds_held += residual
        if deficit > 0.0:
            self.cb_bonds_share += residual / deficit   # share_CB += Newbonds_financed/Def
            self.count_share_def += 1                   # count_share_def++
