"""Commercial bank (one per index in BankingSector).

Mirrors C++ NB-indexed vectors from dsk_globalvar.h:
BankEquity[2,j], BankCash[2,j], BankDeposits[j], BankReserves[j],
BaselBankCredit[j], BankCredit[j], CreditSupply[j], bankmarkup[j], r_deb[j],
NL[j], NbClient[j], fB[1,j], Bank_active[j], BankProfits[j], Debtot2[j], etc.

Task 2.1 (M2): full multi-bank support. market_share is set by BankingSector
(C++ fB = 1/NB uniform), not by Bank.initialise_from_parameters.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from dsk.agents.agent import Agent

if TYPE_CHECKING:
    from dsk.nation import Nation
    from dsk.parameters.global_parameters import GlobalParameters
    from dsk.parameters.nation_parameters import NationParameters


class Bank(Agent):
    """Commercial bank. Extends credit to sector-2 firms, holds bonds, pays dividends."""

    def __init__(self, nation: "Nation", rng: np.random.Generator) -> None:
        super().__init__(nation)
        self.rng = rng

        # --- Activity ---
        # Bank_active(i): 1 while solvent
        self.is_active: bool = True

        # --- Pricing ---
        # bankmarkup(i): markup over central-bank rate
        self.markup: float = 0.0
        # r_deb(i) = r * (1 + markup): lending rate charged to firms
        self.lending_rate: float = 0.0

        # --- Client portfolio ---
        # NL(i): target number of clients for this bank
        self.n_clients_target: int = 0
        # NbClient(i): current active client count
        self.n_active_clients: int = 0
        # fB(1,j): bank market share (= 1/NB initially, uniform)
        self.market_share: float = 0.0
        # firm_match: set of unique_ids of matched sector-2 firms
        self.firm_match: set = set()

        # --- Balance sheet (two-period arrays in C++: index 1=current, 2=prev) ---
        # MonetaryBase(j): sum of positive net worths of client s2 firms (= WtotClient2)
        self.monetary_base: float = 0.0
        # BankReserves(j): = monetary_base at init
        self.reserves: float = 0.0
        # BankDeposits(j): = monetary_base / bankreserve_requirement_rate
        self.deposits: float = 0.0
        # BankEquity(1,j) / BankEquity(2,j)
        self.equity: float = 0.0
        self.equity_prev: float = 0.0
        # BankCash(1,j) / BankCash(2,j)
        self.cash: float = 0.0
        self.cash_prev: float = 0.0

        # --- Credit supply ---
        # MultiplierBankCredit(j): money-multiplier-based credit ceiling (0 in Basel II)
        self.multiplier_credit: float = 0.0
        # BaselBankCredit(j): equity / credit_multiplier (Basel II ceiling)
        self.basel_credit: float = 0.0
        # BankCredit(j): total credit the bank can allocate (= BaselBankCredit for flagtotalcredit==2)
        self.total_credit: float = 0.0
        # CreditSupply(j): remaining allocatable credit (reduced as credit lines are assigned)
        self.credit_supply: float = 0.0
        # BasicCreditLines2(i,j): homogeneous credit line per firm (= 0 when basiccreditrate=0)
        self.basic_credit_lines: dict = {}  # firm unique_id → amount
        # Per-firm allocated credit (rating-based remainder, populated by ALLOCATECREDIT)
        self.allocated_credit: dict = {}    # firm unique_id → amount

        # --- Loan-book aggregates ---
        # Debtot2(j): total outstanding loans to s2 firms
        self.total_loans_s2: float = 0.0
        # Debtot1(j): total outstanding loans to s1 firms (used in M2+)
        self.total_loans_s1: float = 0.0
        # BadDebttot(j): accumulated bad debt this period
        self.total_bad_debt: float = 0.0
        # DebtRemittancestot(j): debt repayments received this period
        self.total_debt_remittances: float = 0.0
        # Amount_lent(j): new credit extended this period
        self.amount_lent: float = 0.0

        # --- P&L and dividends ---
        # BankProfits(j)
        self.profits: float = 0.0
        # Divb(j): dividends paid
        self.dividends: float = 0.0

        # --- Credit-demand tracking ---
        # CreditDemand(j): aggregate demand by clients
        self.credit_demand: float = 0.0
        # AvgCreditDemandSupplyRatio(j)
        self.avg_credit_demand_supply_ratio: float = 0.0

        # --- Rating (NWS2_rating(j,i) in C++) ---
        # For NB=1: dict of firm unique_id → ranking integer (1-indexed, = firm's sequential order)
        self.firm_ratings: dict = {}  # firm unique_id → rating int
        # Ordered list of firm unique_ids from best (rank 1) to worst (rank N2).
        # Built by compute_max_credit_per_firm (MAXCREDIT); used by allocate_credit_to_demand.
        self.rated_firms_ordered: list = []

        # --- Loans to CB (dskQE) ---
        self.bonds_held: float = 0.0        # bonds held by this bank
        self.bonds_demand: float = 0.0      # bonds_dem(j)
        self.bonds_demand_share: float = 0.0  # bonds_dem_share(j)

        # --- Bailout (Task 2.4) ---
        self.bailout_cost: float = 0.0      # Gbailout(j): government subsidy this period
        self.failed_this_period: bool = False  # equity < 0 after BANKING

        # --- Reserve remuneration (Task 2.3, used in BANKING Task 2.4) ---
        # r_cbreserves * BankCash(2,j): pre-computed by CentralBank.remunerate_reserves()
        self.reserve_interest_income: float = 0.0

        # --- Leverage (Leverage(j) in C++) ---
        # (gamma_BD * BadDebttot) / (BankCash + bonds): used by TOTCREDIT for flagBUFFER=1
        self.leverage: float = 0.0

        # --- BANKING running totals (Task 2.4) ---
        # BadDebttot(1,j): cumulative bad debt across all periods
        self.cumulative_bad_debt: float = 0.0
        # bonds_NO_marktomarket: nominal bonds before MTM discount (used for interest calc)
        self.bonds_held_nominal: float = 0.0
        # Loan profit share: DebtInterestsClients2 / (DebtInterestsClients2 + bond interest)
        self.loan_profit_share: float = 0.0
        # Total debt interest from client s2 firms this period
        self.total_debt_interest: float = 0.0

    # ------------------------------------------------------------------

    def compute_profit_and_dividend(self) -> dict:
        """Compute bank profits, dividends, cash, and equity for this period (BANKING).

        Implements C++ BANKING() in module_finance.cpp:14-205 for the active-bank
        branch with flag_dskQE=1, flagTAX=2, flag_insurance=0, flagSPREAD=0.

        Accumulates per-client metrics (debt interest, bad debt, remittances) then
        computes bank profit, applies dividends and taxes, updates cash and equity.
        Must be called after CentralBank.remunerate_reserves() sets reserve_interest_income.

        Returns dict with keys: profits, dividends, tax.
        """
        gparams = self.nation.gparams
        nparams = self.nation.params
        cb = self.nation.central_bank

        # Reset period accumulators
        self.total_bad_debt = 0.0
        self.total_loans_s2 = 0.0
        self.total_debt_remittances = 0.0
        self.total_debt_interest = 0.0

        for firm in self.nation.consumption_good_sector:
            if firm.unique_id not in self.firm_match:
                continue
            if firm.bad_debt == 0.0:
                self.total_debt_remittances += firm.debt_remittance
            self.total_loans_s2 += firm.debt
            self.total_bad_debt += firm.bad_debt
            self.total_debt_interest += firm.debt_interest

        # BadDebttot(1,j) += BadDebttot_temp(j): cumulative running total
        self.cumulative_bad_debt += self.total_bad_debt

        # BankProfits(j) = DebtInterests - Deposits*r_depo + r_cbreserves*BankCash(2,j)
        r_depo = cb.deposit_rate
        self.profits = (
            self.total_debt_interest
            - self.deposits * r_depo
            + self.reserve_interest_income
        )

        # dskQE: MTM discount bonds; add bond interest on nominal value
        if gparams.use_dskqe:
            self.bonds_held_nominal = self.bonds_held
            if cb.marktomarket_rate > 0.0:
                self.bonds_held = self.bonds_held / (1.0 + cb.marktomarket_rate)
            self.profits += cb.bonds_rate * self.bonds_held_nominal

        # Loan profit share
        bond_int = cb.bonds_rate * (self.bonds_held_nominal if gparams.use_dskqe else self.bonds_held)
        total_int = self.total_debt_interest + bond_int
        if total_int > 0.0:
            self.loan_profit_share = self.total_debt_interest / total_int

        # Dividends and taxes (only on positive profits)
        bank_tax = 0.0
        self.dividends = 0.0
        if self.profits > 0.0:
            self.dividends = gparams.dividend_rate_bank * self.profits
            if gparams.tax_base_rule != 1:
                bank_tax = nparams.tax_rate_banks * self.profits
                self.cash -= bank_tax
            if gparams.deposit_insurance == 1:
                ins = gparams.deposit_insurance_tax_rate * self.profits
                self.cash -= ins

        # BankCash(1,j) += BankProfits(j) - Divb(j)
        self.cash += self.profits - self.dividends

        # BankEquity(1,j) = BankCash(1,j) + bonds(j) - gamma_BD * BadDebttot(1,j)
        gamma_bd = gparams.gamma_bd
        self.equity = self.cash + self.bonds_held - gamma_bd * self.cumulative_bad_debt

        # Leverage(j) = gamma_BD*BadDebttot / (BankCash + bonds) [used by TOTCREDIT]
        if self.equity > 0.0:
            denominator = self.cash + self.bonds_held
            if denominator > 0.0:
                self.leverage = (gamma_bd * self.cumulative_bad_debt) / denominator

        # Maintain SFC balance-sheet identity: cash + loans + bonds = deposits + equity
        # BANKING changes equity and cash, so re-derive deposits as the residual plug
        # (same role as BankDeposits in C++ ALLOCATECREDIT dsk_main.cpp:4436).
        self.deposits = self.cash + self.total_loans_s2 + self.bonds_held - self.equity

        return {"profits": self.profits, "dividends": self.dividends, "tax": bank_tax}

    def fail_if_insolvent(self) -> None:
        """Mark bank as failed if equity turned negative (BANKING insolvency check)."""
        if self.equity < 0.0:
            self.failed_this_period = True

    # ------------------------------------------------------------------

    def initialise_from_parameters(
        self,
        gparams: "GlobalParameters",
        nparams: "NationParameters",
        client_firms: list,
    ) -> None:
        """Initialise bank state from parameters and client firm portfolio.

        Implements C++ INITIALIZE lines 1302–1459 for this bank.
        Uses flagtotalcredit==2 (Basel II) branch — the baseline per dsk_flag.h:239.
        market_share (fB) is set by BankingSector before this call (C++ line 1284:
        fB=1/NB uniform regardless of Pareto client distribution).

        Parameters
        ----------
        gparams : GlobalParameters
        nparams : NationParameters
        client_firms : list[ConsumptionGoodFirm]
            Sector-2 firms assigned to this bank.
        """
        n2 = len(client_firms)
        self.n_clients_target = n2
        self.n_active_clients = n2
        self.is_active = True

        # bankmarkup(i) = bankmarkup_init; r_deb(i) = r*(1+markup)
        self.markup = gparams.bank_markup_init
        self.lending_rate = nparams.policy_rate * (1.0 + self.markup)

        # Note: market_share is NOT set here — it is set by BankingSector
        # (C++ fB = 1/NB, line 1284) before this method is called.

        # Record client set; initial ordering is the input order (sequential)
        self.rated_firms_ordered = []
        for rank, firm in enumerate(client_firms, start=1):
            self.firm_match.add(firm.unique_id)
            self.firm_ratings[firm.unique_id] = rank  # NWS2_rating(j,1) = j
            self.rated_firms_ordered.append(firm.unique_id)

        # WtotClient2(j): sum of positive s2 client net worths
        # C++: if W2(1,i)>0: WtotClient2(j) += W2(1,i)
        total_nw = sum(f.net_worth for f in client_firms if f.net_worth > 0.0)

        self.monetary_base = total_nw          # MonetaryBase(j)
        self.reserves = total_nw               # BankReserves(j)
        self.deposits = total_nw / nparams.bank_reserve_requirement_rate  # BankDeposits(j)

        # BankEquity(1,j) = BankDeposits(j) * initialbankequitymultiplier
        self.equity = self.deposits * gparams.bank_equity_init_multiplier
        self.equity_prev = self.equity

        # flagtotalcredit==2 branch (Basel II, baseline):
        # BankCash(1,j) = BankEquity(1,j) + BankDeposits(j)
        self.cash = self.equity + self.deposits
        self.cash_prev = self.cash
        self.multiplier_credit = 0.0           # MultiplierBankCredit(j) = 0

        if self.equity <= 0.0:
            self.basel_credit = 1.0 / nparams.credit_multiplier
        else:
            self.basel_credit = self.equity / nparams.credit_multiplier  # BaselBankCredit(j)

        self.total_credit = self.basel_credit   # BankCredit(j)
        self.credit_supply = self.basel_credit  # CreditSupply(j)

        # BasicCreditLines2(i,j) = (basiccreditrate * BankCredit(j)) / NL(j)
        # basiccreditrate = gparams.credit_homogeneous_share = 0.0 (baseline)
        basiccreditrate = gparams.credit_homogeneous_share
        base_line = (basiccreditrate * self.total_credit / n2) if n2 > 0 else 0.0
        for firm in client_firms:
            self.basic_credit_lines[firm.unique_id] = base_line

        # BankCredit(j) = (1 - basiccreditrate) * BankCredit(j)
        self.total_credit = (1.0 - basiccreditrate) * self.total_credit

        # Initialise aggregate trackers to zero
        self.total_loans_s2 = 0.0
        self.total_loans_s1 = 0.0
        self.total_bad_debt = 0.0
        self.total_debt_remittances = 0.0
        self.amount_lent = 0.0
        self.profits = 0.0
        self.dividends = 0.0
        self.credit_demand = 0.0
        self.avg_credit_demand_supply_ratio = 0.0
        self.bonds_held = 0.0
        self.cumulative_bad_debt = 0.0
        self.bonds_held_nominal = 0.0
        self.loan_profit_share = 0.0
        self.total_debt_interest = 0.0
        self.failed_this_period = False
        self.bonds_demand = 0.0
        self.bonds_demand_share = 0.0
        self.leverage = 0.0
