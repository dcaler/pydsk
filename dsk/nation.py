from __future__ import annotations

import copy
import math
from typing import TYPE_CHECKING, Optional

import numpy as np

from dsk.accounting.national_accounts import NationalAccounts
from dsk.agents.central_bank import CentralBank
from dsk.agents.electricity_producer import ElectricityProducer
from dsk.agents.government import Government
from dsk.agents.household import HouseholdSector
from dsk.parameters.nation_parameters import NationParameters
from dsk.policy.climate_policy import ClimatePolicy
from dsk.sectors.banking_sector import BankingSector
from dsk.sectors.capital_good_sector import CapitalGoodSector
from dsk.sectors.consumption_good_sector import ConsumptionGoodSector
from dsk.sectors.labour_market import LabourMarket
from dsk.trade.trade_offer import TradeOffer

if TYPE_CHECKING:
    from dsk.climate.climate_system import ClimateSystem
    from dsk.io.output_sink import OutputSink
    from dsk.parameters.global_parameters import GlobalParameters
    from numpy.random import Generator


class Nation:
    """Composite model of one economy.

    Owns all sector objects and singleton domain objects (Government, CentralBank, etc.).
    The phase methods (production_phase, dynamics_phase, closeout_phase) and their
    20 sub-phase constituents are all stubs in milestone 0; they gain real bodies in
    milestones 1–5.

    Attributes
    ----------
    nation_id : str
        Stable identifier used for RNG seeding and output tagging.
    params : NationParameters
        Per-nation configuration (policy, banking structure, etc.).
    rng : numpy.random.Generator | None
        Set by Simulation.__init__ after Nation is constructed.
    """

    def __init__(
        self,
        nation_id: str,
        params: Optional[NationParameters] = None,
    ) -> None:
        self.nation_id: str = nation_id
        self.params: NationParameters = params if params is not None else NationParameters()
        self.rng: Optional["Generator"] = None
        self.sink: Optional["OutputSink"] = None
        self.gparams: Optional["GlobalParameters"] = None  # set by Simulation.__init__
        self._mc_run: int = 0  # set by MC harness; 0 for single runs

        # --- Sector collections (AgentSet subclasses) ---
        self.capital_good_sector: CapitalGoodSector = CapitalGoodSector()
        self.consumption_good_sector: ConsumptionGoodSector = ConsumptionGoodSector()
        self.banking_sector: BankingSector = BankingSector()

        # --- Singleton domain objects ---
        self.labour_market: LabourMarket = LabourMarket(self)
        self.household_sector: HouseholdSector = HouseholdSector(self)
        self.government: Government = Government(self)
        self.central_bank: CentralBank = CentralBank(self)
        self.electricity_producer: ElectricityProducer = ElectricityProducer(self)
        self.climate_policy: ClimatePolicy = ClimatePolicy(self)
        self.accounting: NationalAccounts = NationalAccounts(self)

        # Internal state for cross-phase communication
        self._last_climate: Optional["ClimateSystem"] = None
        self._emissions_this_step: float = 0.0
        # Surface temperature anomaly (K above pre-industrial) from the last ClimateSystem step.
        # Populated by receive_climate_state(); read by apply_climate_shocks() and damage functions.
        self.temperature_anomaly: float = 0.0
        # Gbailout_all — this period's bank-bailout total (set by BAILOUT, read by SAVE)
        self.gbailout_this_period: float = 0.0

        # ------------------------------------------------------------------
        # Nation-level macro aggregates set by realise_profits_and_taxes (PROFIT)
        # ------------------------------------------------------------------
        # cpi(1) — consumer price index = Σ p2(j) * f2(1,j)
        self.cpi: float = 1.0
        # Cons — nominal household consumption budget = w*LD + Divtot_prev + G
        self.consumption_budget_nominal: float = 0.0
        # Divtot(1) and Divtot(2) — current and previous period total dividends
        self.total_dividends: float = 0.0
        self.total_dividends_prev: float = 0.0
        # Tax — total tax revenue this period
        self.total_tax: float = 0.0
        # Aggregate profits, net worths (Pitot1, Pitot2, Wtot1, Wtot2)
        self.total_profit_s1: float = 0.0
        self.total_profit_s2: float = 0.0
        self.total_net_worth_s1: float = 0.0
        self.total_net_worth_s2: float = 0.0
        # Real and nominal flows for SFC checks (set by PROFIT / MACRO)
        self.gdp_nominal: float = 0.0          # GDPm = Cmon + Imon + dNmtot (MACRO)
        self.consumption_nominal_realised: float = 0.0
        self.investment_nominal: float = 0.0
        self.inventory_change_nominal: float = 0.0
        self.total_production_s2_real: float = 0.0
        self.total_production_s1_real: float = 0.0
        self.total_real_consumption: float = 0.0
        self.total_real_inventory_change: float = 0.0
        self.total_real_investment_machines: float = 0.0

        # ------------------------------------------------------------------
        # Nation-level macro aggregates set by aggregate_macro_indicators (MACRO)
        # ------------------------------------------------------------------
        # cpi(2) — previous-period CPI (needed by WAGE for d_cpi)
        self.cpi_prev: float = 1.0
        # GDP(1) — real GDP (expenditure-based: Creal + Ir*p1m/p2m + dNtot)
        self.real_gdp: float = 1.0
        # ppi(1/2) — producer price index (production-weighted mean s1 price)
        self.ppi: float = 1.0
        self.ppi_prev: float = 1.0
        # Creal — real consumption = Cons/cpi
        self.real_consumption: float = 0.0
        # Ir — real investment = Qtot1 (sector-1 production in machine units)
        self.real_investment: float = 0.0
        # Am1 / Am2 — mean productivities (not the same as LabourMarket.mean_machine_prod)
        self.mean_prod_s1: float = 1.0   # production-weighted mean A1p across s1 firms
        self.mean_prod_s2: float = 1.0   # market-share-weighted mean A2e across s2 firms
        # Debtot1 — aggregate sector-1 debt
        self.s1_debt_total: float = 0.0
        # GDP_g2 — log growth rate of real GDP
        self.gdp_growth_rate: float = 0.0
        # rw — real wage = w(2)/cpi(1)
        self.real_wage: float = 1.0

        # ------------------------------------------------------------------
        # Energy and emissions aggregates (set by compute_industrial_emissions, EMISS_IND)
        # ------------------------------------------------------------------
        # Emiss1_TOT / Emiss2_TOT — total industrial emissions from each sector
        self.emissions_total_s1: float = 0.0
        self.emissions_total_s2: float = 0.0
        # next2bc — count of s2 firms exiting with positive bad debt this period.
        self.n_s2_bankruptcies: int = 0
        # tp_CO2_I1_TOT / tp_CO2_I2_TOT — carbon tax revenue collected from each sector
        self.carbon_tax_revenue_s1: float = 0.0
        self.carbon_tax_revenue_s2: float = 0.0
        # LDff_1 — labour demand in fossil-fuel extraction caused by sector-1 fuel use
        self.fuel_labour_demand_s1: float = 0.0
        # t_CO2_I1 / t_CO2_I2 — per-unit carbon tax rate (0 in baseline; set by climate policy)
        self.carbon_tax_rate_s1: float = 0.0
        self.carbon_tax_rate_s2: float = 0.0
        # elfrac_reg_now / elfrac_reg_exp / elfrac_reg_fine — electrification mandate state
        # (C++ CLIMATE_POLICY block; set by ElectrificationMandate instrument each period)
        self.elfrac_reg_now: float = 0.0   # current enforcement fraction (0 = no fine)
        self.elfrac_reg_exp: float = 0.0   # announced/expected fraction for tech decisions
        self.elfrac_reg_fine: float = 0.0  # fine multiplier per unit of deficit
        # tp_elfrac — total fine collected from sector-1 firms this period
        self.elfrac_revenue: float = 0.0

    # ------------------------------------------------------------------
    # Full-nation initialisation (C++ INITIALIZE block)
    # ------------------------------------------------------------------

    def initialise_from_parameters(
        self,
        gparams: "GlobalParameters",
        nparams: Optional[NationParameters] = None,
    ) -> None:
        """Initialise all nation components from parameters (C++ INITIALIZE block).

        Mirrors the C++ INITIALIZE() function in dsk_main.cpp (lines 1043–1713),
        creating all firms and calling every component's initialise_from_parameters
        in the canonical C++ order.

        Must be called after ``nation.rng`` is set (by ``Simulation.__init__`` or
        directly in tests). Creates N1 ``CapitalGoodFirm``s, N2
        ``ConsumptionGoodFirm``s, and NB=1 ``Bank`` (M1 simplification).

        Parameters
        ----------
        gparams : GlobalParameters
        nparams : NationParameters, optional
            Defaults to ``self.params`` when omitted.
        """
        from dsk.agents.capital_good_firm import CapitalGoodFirm
        from dsk.agents.consumption_good_firm import ConsumptionGoodFirm

        if nparams is None:
            nparams = self.params
        self.gparams = gparams

        n1 = gparams.n1_capital_good_firms
        n2 = gparams.n2_consumption_good_firms

        # --- Lagged-state seeds for the t=1 wage formula ------------------
        # C++ INITIALIZE at dsk_main.cpp:1207, 1209 seeds:
        #   cpi(2) = (1 + mi2) * w0 / A0
        #   ppi(2) = (1 + mi1) * w0 / A0   (note: A0 enters via a, see s1
        #                                   price formula in agents/consumption_good_firm.py)
        # Without these the first-period d_cpi reads as (p2 − 1)/1 = mi2,
        # which is far above the inflation target and inverts the sign of
        # the wage shock (see planningDocs/build_log.md entry "Wage init
        # mismatch").
        A0 = gparams.productivity_init
        a_scale = gparams.s1_productivity_scale
        w0 = gparams.wage_init
        mi1 = gparams.s1_markup
        mi2 = nparams.s2_markup_init
        self.cpi = (1.0 + mi2) * w0 / A0          # cpi(1) at start of step 1
        self.cpi_prev = (1.0 + mi2) * w0 / A0     # cpi(2) — C++ line 1207
        self.ppi = (1.0 + mi1) * w0 / (A0 * a_scale)
        self.ppi_prev = (1.0 + mi1) * w0 / (A0 * a_scale)  # ppi(2) — C++ line 1209

        # --- Singleton domain objects (C++ INITIALIZE lines 1043–1302) ---
        self.labour_market.initialise_from_parameters(gparams, nparams)
        self.central_bank.initialise_from_parameters(gparams, nparams)
        self.household_sector.initialise_from_parameters(gparams, nparams)
        self.government.initialise_from_parameters(gparams, nparams)
        self.electricity_producer.initialise_from_parameters(gparams)

        # --- Capital-good firms (C++ INITIALIZE lines 1303–1459) ---
        for _ in range(n1):
            cf = CapitalGoodFirm(self, self.rng)
            cf.initialise_from_parameters(gparams)
            self.capital_good_sector.add(cf)

        # --- Consumption-good firms (C++ INITIALIZE lines 1460–1702) ---
        # Preferred supplier rotates round-robin (j % N1); all assigned to bank 0.
        machine_counter = 0
        s2_firms: list = []
        for j in range(n2):
            f = ConsumptionGoodFirm(self, self.rng)
            machine_counter = f.initialise_from_parameters(
                gparams, nparams, j % n1, 0, machine_counter
            )
            self.consumption_good_sector.add(f)
            s2_firms.append(f)

        # --- Banking sector (NB=1 for M1; Task 2.1 will generalise) ---
        self.banking_sector.initialise_from_parameters(
            gparams, nparams, self.rng, self, s2_firms
        )

    # ------------------------------------------------------------------
    # Cross-nation hooks (initially no-ops; expanded in milestones 4/7)
    # ------------------------------------------------------------------

    def report_emissions(self) -> float:
        """Return total emissions accumulated this step for the global climate accumulator."""
        return self._emissions_this_step

    def receive_climate_state(self, climate: "ClimateSystem") -> None:
        """Pull global temperature / CO₂ from the shared ClimateSystem.

        Called by Simulation.step() immediately after ClimateSystem.step().
        Stores the full climate object for apply_climate_shocks() and exposes
        the temperature anomaly on the nation for damage functions.
        """
        self._last_climate = climate
        self.temperature_anomaly = climate.temperature_anomaly

    def expose_trade_offer(self) -> TradeOffer:
        """Return this nation's excess supply / unmet demand for cross-border matching."""
        return TradeOffer(nation_id=self.nation_id)

    def accept_trade_assignment(self, assignment) -> None:
        """Consume the result of TradeNetwork.match()."""
        pass

    # ------------------------------------------------------------------
    # Production-phase sub-phases  (C++ MACH → COMPET2)
    # ------------------------------------------------------------------

    def set_climate_policy(self, t: int) -> None:
        """Activate policy instruments for period t; propagate rates into cost functions."""
        self.climate_policy.apply(t)

    def compute_bank_client_net_worth(self) -> None:
        """Compute total net worth of each bank's client portfolio (WTOTCLIENT).

        C++ dsk_main.cpp WTOTCLIENT() lines 2138-2192 (flagDEPOSITS==0 branch):
          for j in banks: WtotClient2(j) = sum_{i: BankMatch(i,j)==1, W2(1,i)>0} W2(1,i)

        Uses current period's net_worth (W2(1,i) in C++), which at this call point equals
        the previous period's post-ALLOCATECREDIT value (before MACH changes it).
        """
        firm_by_uid = {f.unique_id: f for f in self.consumption_good_sector}
        for bank in self.banking_sector:
            bank.monetary_base = sum(
                firm_by_uid[uid].net_worth
                for uid in bank.firm_match
                if uid in firm_by_uid and firm_by_uid[uid].net_worth > 0.0
            )

    def deliver_machines(self) -> None:
        """Update s1 prices; deliver pending machines into s2 firms' stocks (MACH).

        Ports C++ MACH() for flag_clim_tech==0. Payment was removed from MACH in the
        current C++ codebase ('**new** ==> eliminate round of credit that was here');
        it now happens in ALLOCATECREDIT (Task 1.8). No firm death here.

        C++ call order (dsk_main.cpp ~138):
          1. Loop s1: reset S1; update c1, p1; accumulate p1m, c1m.
          2. Compute sector means p1m, c1m, A1m.
          3. Loop s2: K+=EI(2,j); g=gtemp; compute A2, c2, mu2, p2.
        """
        gparams = self.gparams
        if gparams is None:
            return  # not yet wired (e.g. standalone Nation in a test)

        wage = self.labour_market.wage  # w(2) = current wage
        elec_price_prev = self.electricity_producer.electricity_price_prev  # c_en(2)

        # --- Part 1: Update sector-1 firm prices/costs; accumulate sector means ---
        # C++: S1(1,i)=0; c1(i)=w/(A1p*a); p1(1,i)=(1+mi1)*c1; p1m+=p1(2,i); c1m+=c1
        for firm in self.capital_good_sector:
            firm.update_price_and_cost(wage, gparams, elec_price=elec_price_prev)

        self.capital_good_sector.update_sector_means()

        # --- Part 2: Deliver machines; update s2 firm productivity and prices ---
        for firm in self.consumption_good_sector:
            firm.receive_machines(gparams, wage, elec_price=elec_price_prev)

    def determine_total_credit(self) -> None:
        """Compute total credit supply from banking sector equity (TOTCREDIT).

        Implements flagtotalcredit==2 (Basel II) per-period branch from
        module_finance.cpp:574-670. Uses current bank.equity (set by BANKING in
        the previous dynamics phase) — does NOT recompute equity from deposits.
        Also shifts equity_prev = equity (BankEquity(2,j)=BankEquity(1,j) in C++).

        flagBUFFER==1 (endogenous_capital_buffer=1): buffer-adjusted Basel credit
        using the leverage ratio computed in the previous period's BANKING.
        """
        gparams = self.gparams
        if gparams is None:
            return
        nparams = self.params
        bcr = gparams.credit_homogeneous_share  # basiccreditrate = 0.0 baseline

        for bank in self.banking_sector:
            if not bank.is_active:
                continue

            # Update deposits from current client net-worth base (WTOTCLIENT relationship)
            bank.deposits = bank.monetary_base / nparams.bank_reserve_requirement_rate
            bank.reserves = bank.monetary_base
            bank.multiplier_credit = 0.0

            # BaselBankCredit from CURRENT equity (set by BANKING, not recomputed)
            if bank.equity <= 0.0:
                bank.basel_credit = 1.0 / nparams.credit_multiplier
            elif gparams.endogenous_capital_buffer == 1:
                beta = gparams.beta_basel
                buffer = nparams.credit_multiplier * (1.0 + beta * bank.leverage)
                bank.basel_credit = bank.equity / buffer
            else:
                bank.basel_credit = bank.equity / nparams.credit_multiplier

            bank.total_credit = bank.basel_credit
            bank.credit_supply = bank.basel_credit

            n_clients = bank.n_active_clients if bank.n_active_clients > 0 else 1
            base_line = (bcr * bank.total_credit) / n_clients
            for uid in bank.firm_match:
                bank.basic_credit_lines[uid] = base_line

            bank.total_credit *= (1.0 - bcr)

            # BankEquity(2,j) = BankEquity(1,j): shift used by BAILOUT fallback path
            bank.equity_prev = bank.equity

    def compute_bonds_demand(self) -> None:
        """Split each bank's Basel credit into bonds demand and loanable supply.

        Ports the C++ call sequence: BONDS_DEMAND() runs after TOTCREDIT and before
        MAXCREDIT, but only under dskQE (dsk_main.cpp:155-159). At baseline
        (varphi=0, flag_portfolioallocation=0) this just sets bonds_demand=0 and
        credit_supply=basel_credit on every bank.
        """
        if self.gparams is None or not self.gparams.use_dskqe:
            return
        self.banking_sector.compute_bonds_demand(self.gparams)

    def compute_max_credit_per_firm(self) -> None:
        """Compute per-firm credit ceiling from net worth and sales (MAXCREDIT).

        Implements flagallocatecredit==0 (NW/Sales ranking), dsk_main.cpp lines 1939-2100:
          NetWorthToSales2(j) = W2(2,j)/S2(2,j) if both >0, else 1
          For each bank: sort clients by NW/Sales descending → NWS2_rating

        Rank 1 = most creditworthy (highest NW/Sales). Stored in bank.rated_firms_ordered.
        Uses previous-period net worth and sales (W2(2,j), S2(2,j)).
        """
        if self.gparams is None:
            return

        firm_by_uid = {f.unique_id: f for f in self.consumption_good_sector}

        for bank in self.banking_sector:
            # Compute NW/Sales for each client; update firm.net_worth_to_sales
            def _nw_sales(uid: int) -> float:
                f = firm_by_uid[uid]
                if f.sales_prev > 0.0 and f.net_worth_prev > 0.0:
                    ratio = f.net_worth_prev / f.sales_prev
                    f.net_worth_to_sales = ratio
                    return ratio
                f.net_worth_to_sales = 1.0
                return 1.0

            ranked = sorted(bank.firm_match, key=_nw_sales, reverse=True)
            bank.rated_firms_ordered = ranked
            bank.firm_ratings = {uid: r + 1 for r, uid in enumerate(ranked)}

    def distribute_brochures(self) -> None:
        """Capital-good firms advertise to a subset of consumption-good firms (BROCHURE).

        Ports C++ dsk_main.cpp BROCHURE() lines 2596-2738.

        Four phases:
        1. Repair orphaned consumers (previous supplier died → random reassignment).
        2. Each capital firm sends ROUND(nclient*Gamma) brochures to random consumers.
        3. Each consumer picks the best supplier (lowest p1*(w/A1)) from its brochure set.
        4. Rebuild capital-firm client lists and recount nclient.
        """
        gparams = self.gparams
        if gparams is None:
            return

        N1 = gparams.n1_capital_good_firms
        rng = self.rng
        wage = self.labour_market.wage
        elec_price_prev = self.electricity_producer.electricity_price_prev  # c_en(2)

        capital_firms = list(self.capital_good_sector)
        consumption_firms = list(self.consumption_good_sector)

        # --- Phase 1: Repair orphaned consumers ---
        # C++: if fornit(j)<1 or >N1: fornit(j)=random; Match(j,fornit(j))=1
        # In Python, preferred_supplier_idx==-1 signals "no valid supplier".
        for j_firm in consumption_firms:
            idx = j_firm.preferred_supplier_idx
            if idx < 0 or idx >= N1:
                new_idx = int(rng.integers(0, N1))
                j_firm.preferred_supplier_idx = new_idx
                j_firm.brochure_senders_idxs = {new_idx}

        # --- Phase 2: Capital firms send new brochures ---
        # C++: for i: newbroch=ROUND(nclient*Gamma); send to random j
        for i, i_firm in enumerate(capital_firms):
            i_firm.distribute_brochures(i, consumption_firms, gparams, rng)

        # --- Phase 3: Consumer firms choose best supplier from brochure set ---
        # C++: for j: indforn=argmin p1*(w/A1) or p1+cost2*b over Match(j,i)==1
        for j_firm in consumption_firms:
            j_firm.choose_best_supplier(
                capital_firms, wage,
                elec_price=elec_price_prev,
                payback=gparams.payback_threshold,
            )

        # --- Phase 4: Rebuild capital-firm client lists and recount nclient ---
        # C++: nclient=0; for j: if Match(j,i)==1: nclient(i)++
        for i_firm in capital_firms:
            i_firm.clients = []
            i_firm.num_clients = 0

        for j_firm in consumption_firms:
            if j_firm.is_alive:
                i = j_firm.preferred_supplier_idx
                if 0 <= i < len(capital_firms):
                    capital_firms[i].clients.append(j_firm)
                    capital_firms[i].num_clients += 1

    def plan_investment(self, t: int) -> None:
        """Firms form demand expectations, scrap old machines, plan new orders (INVEST + ORD).

        Ports C++ dsk_main.cpp INVEST() (lines 2741-2938) and ORD() (lines 3746-4032).

        Two-pass loop matching C++ structure:
        Pass 1 (per-j in INVEST): EXPECT → compute Qd/EId → SCRAPPING → COSTPROD
        Pass 2 (ORD): apply prudential credit limits, compute Cmach and labour demand
        """
        gparams = self.gparams
        if gparams is None:
            return

        wage = self.labour_market.wage
        elec_price_prev = self.electricity_producer.electricity_price_prev  # c_en(2)
        capital_firms  = list(self.capital_good_sector)
        consumption_firms = list(self.consumption_good_sector)

        # ---- Pass 1: per-j sub-routines from INVEST ----
        # C++ dsk_main.cpp lines 2763-2857
        for firm in consumption_firms:
            if not firm.is_alive:
                continue

            # EXPECT (flagEXP=0 baseline)
            firm.form_demand_expectation(t)

            # Compute Qd, Kd, EId
            firm.compute_desired_production_and_eid(gparams, t)

            # SCRAPPING: identify machines to replace
            firm.plan_substitution_investment(capital_firms, wage, gparams)

            # COSTPROD: effective A2e and c2e for used machines
            firm.compute_effective_productivity_and_cost(wage, gparams, elec_price=elec_price_prev)

        # ---- Pass 2: ORD (loops internally over all j in C++) ----
        # C++ dsk_main.cpp ORD() lines 3746-4032
        for firm in consumption_firms:
            if not firm.is_alive:
                continue
            firm.plan_investment_order(capital_firms, gparams)

    def allocate_credit_to_demand(self, t: int = 0) -> None:
        """Bank allocates credit to firms ranked by creditworthiness (ALLOCATECREDIT).

        Ports C++ dsk_main.cpp ALLOCATECREDIT() lines 4037-4565 for
        flagtotalcredit==2 and flagallocatecredit==0 (both baseline).

        Three-step structure:
        1. Compute credit demand: CreditDemand = max(0, Deb2_prev + Cmach + c2e*Qd - W2)
        2. Allocate in rank order (highest NW/Sales first):
           2.A  No demand → full plan; W2 reduced by spending.
           2.B.a Full credit → full plan; W2 sentinel = 1.
           2.B.b.1 Drop SI → EI + production funded.
           2.B.b.2 Drop EI + SI → production only.
           2.B.b.3 Partial production (or death if Q2 < 1).
           2.B.b.4 Can't cover debt → firm dies.
        3. Labour demand Ld2 = Q2/A2e; pending machine orders set up.

        Parameters
        ----------
        t : int
            Current simulation period (used as vintage key for pending machine orders).
        """
        gparams = self.gparams
        if gparams is None:
            return

        dim_mach = gparams.machine_size_units
        capital_firms = list(self.capital_good_sector)
        firm_by_uid = {f.unique_id: f for f in self.consumption_good_sector}

        # Reset capital-firm demand accumulators (filled by machine orders below)
        for cf in capital_firms:
            cf.demand = 0.0

        # ── Step 1: Credit demand for all alive firms ──────────────────────────
        for firm in self.consumption_good_sector:
            if not firm.is_alive:
                firm.credit_demand = 0.0
                continue
            total_cost = (
                firm.debt_prev
                + firm.machine_order_total_cost
                + firm.effective_unit_cost * firm.desired_production
            )
            firm.credit_demand = max(0.0, total_cost - firm.net_worth)

        # ── Step 2: Allocate in rank order per bank ────────────────────────────
        for bank in self.banking_sector:
            if not bank.is_active:
                continue

            bank.total_loans_s2 = 0.0
            bank.total_bad_debt = 0.0
            bank.amount_lent = 0.0

            for uid in bank.rated_firms_ordered:
                firm = firm_by_uid.get(uid)
                if firm is None or not firm.is_alive:
                    continue

                firm.bad_debt = 0.0
                cd = firm.credit_demand

                # 2.A — no credit demand
                if cd == 0.0:
                    firm.debt = 0.0
                    firm.production = firm.desired_production
                    firm.desired_expansion_investment = firm.potential_expansion_investment
                    firm.desired_substitution_investment = firm.potential_substitution_investment
                    firm.desired_investment = (
                        firm.desired_expansion_investment + firm.desired_substitution_investment
                    )
                    firm.net_worth -= (
                        firm.effective_unit_cost * firm.desired_production
                        + firm.machine_order_expansion_cost
                        + firm.machine_order_substitution_cost
                        + firm.debt_prev
                    )

                # 2.B — credit demand > 0
                elif cd > 0.0:
                    if cd <= bank.total_credit:
                        # 2.B.a — full credit available
                        firm.debt = cd
                        bank.total_credit -= cd
                        bank.amount_lent += cd
                        firm.production = firm.desired_production
                        firm.desired_expansion_investment = firm.potential_expansion_investment
                        firm.desired_substitution_investment = firm.potential_substitution_investment
                        firm.desired_investment = (
                            firm.desired_expansion_investment + firm.desired_substitution_investment
                        )
                        firm.net_worth = 1.0

                    else:
                        # 2.B.b — credit rationing
                        # 2.B.b.1: drop SI; fund debt + prod + EI
                        need_drop_si = (
                            firm.debt_prev
                            + firm.machine_order_expansion_cost
                            + firm.effective_unit_cost * firm.desired_production
                            - firm.net_worth
                        )
                        if need_drop_si <= bank.total_credit:
                            if need_drop_si >= 0.0:
                                firm.debt = need_drop_si
                                firm.net_worth = 1.0
                            else:
                                firm.debt = 0.0
                                firm.net_worth -= (
                                    firm.debt_prev
                                    + firm.machine_order_expansion_cost
                                    + firm.effective_unit_cost * firm.desired_production
                                )
                            bank.total_credit -= firm.debt
                            bank.amount_lent += firm.debt
                            firm.production = firm.desired_production
                            firm.desired_expansion_investment = firm.potential_expansion_investment
                            firm.desired_substitution_investment = 0.0
                            firm.desired_investment = firm.desired_expansion_investment

                        else:
                            # 2.B.b.2: drop SI + EI; fund debt + prod
                            need_prod_only = (
                                firm.debt_prev
                                + firm.effective_unit_cost * firm.desired_production
                                - firm.net_worth
                            )
                            if need_prod_only <= bank.total_credit:
                                if need_prod_only >= 0.0:
                                    firm.debt = need_prod_only
                                    firm.net_worth = 1.0
                                else:
                                    firm.debt = 0.0
                                    firm.net_worth -= (
                                        firm.debt_prev
                                        + firm.effective_unit_cost * firm.desired_production
                                    )
                                bank.total_credit -= firm.debt
                                bank.amount_lent += firm.debt
                                firm.production = firm.desired_production
                                firm.desired_expansion_investment = 0.0
                                firm.desired_substitution_investment = 0.0
                                firm.desired_investment = 0.0
                                firm.net_worth = 1.0

                            else:
                                can_cover_debt = (
                                    firm.debt_prev - firm.net_worth <= bank.total_credit
                                )
                                if can_cover_debt:
                                    # 2.B.b.3: partial production or death
                                    c2e = firm.effective_unit_cost
                                    q2p = (
                                        (bank.total_credit - firm.debt_prev + firm.net_worth) / c2e
                                        if c2e > 0.0
                                        else 0.0
                                    )
                                    if q2p < 1.0:
                                        # Firm can't produce ≥ 1 unit → dies
                                        if firm.debt_prev > firm.net_worth:
                                            firm.debt = firm.debt_prev - firm.net_worth
                                            firm.bad_debt = firm.debt
                                            bank.total_credit -= firm.debt
                                            bank.amount_lent += firm.debt
                                            firm.debt = 0.0
                                            firm.debt_prev = 0.0
                                        else:
                                            firm.bad_debt = 0.0
                                            firm.debt = 0.0
                                            firm.debt_prev = 0.0
                                        firm.market_share = 0.0
                                        firm.market_share_prev = 0.0
                                        firm.market_share_prev_prev = 0.0
                                        firm.net_worth = 0.0
                                        firm.production = 0.0
                                    else:
                                        # Partial production (≥ 1 unit)
                                        firm.production = q2p
                                        firm.debt = bank.total_credit
                                        bank.amount_lent += firm.debt
                                        bank.total_credit = 0.0
                                        firm.net_worth = 1.0
                                    firm.desired_expansion_investment = 0.0
                                    firm.desired_substitution_investment = 0.0
                                    firm.desired_investment = 0.0

                                else:
                                    # 2.B.b.4: can't cover debt → dies
                                    firm.production = 0.0
                                    if firm.debt_prev > 0.0:
                                        firm.debt = firm.debt_prev - firm.net_worth
                                    else:
                                        firm.debt = firm.debt_prev
                                    firm.bad_debt = firm.debt
                                    firm.debt = 0.0
                                    firm.debt_prev = 0.0
                                    firm.desired_expansion_investment = 0.0
                                    firm.desired_substitution_investment = 0.0
                                    firm.desired_investment = 0.0
                                    firm.market_share = 0.0
                                    firm.market_share_prev = 0.0
                                    firm.market_share_prev_prev = 0.0
                                    firm.net_worth = 0.0

                bank.total_loans_s2 += firm.debt
                bank.total_bad_debt += firm.bad_debt

            # BankDeposits = Loans + bonds + BankCash - BankEquity
            bank.deposits = bank.total_loans_s2 + bank.bonds_held + bank.cash - bank.equity

        # ── Step 3: Labour demand + pending machine orders ─────────────────────
        for firm in self.consumption_good_sector:
            if not firm.is_alive:
                continue

            # Labour demand: Ld2(1,j) = Q2(1,j) / A2e(1,j)
            if not firm.is_new_entrant:
                A2e = firm.effective_labour_prod_used
                if A2e > 0.0:
                    firm.labour_demand = firm.production / A2e

            # Set up pending machine order for confirmed investment
            actual_inv = firm.desired_investment
            if actual_inv > 0.0 and firm.machine_order_supplier_idx >= 0:
                sidx = firm.machine_order_supplier_idx
                if sidx < len(capital_firms):
                    supplier = capital_firms[sidx]
                    n_mach = actual_inv / dim_mach
                    firm.pending_order_n_machines = n_mach
                    firm.pending_expansion_investment = firm.desired_expansion_investment
                    firm.pending_order_supplier_idx = sidx
                    firm.pending_order_vintage = t
                    firm.pending_order_technology = supplier.current_technology
                    supplier.demand += n_mach
                    continue
            # No investment or invalid supplier
            firm.pending_order_n_machines = 0.0
            firm.pending_expansion_investment = 0.0
            firm.pending_order_supplier_idx = -1
            firm.pending_order_vintage = -1
            firm.pending_order_technology = None

    def produce_machines(self) -> None:
        """Capital-good firms fill orders; hire labour; handle cancelled orders (PRODMACH).

        Ports C++ dsk_main.cpp PRODMACH() lines 4570-4847 (flag_clim_tech==0 path).

        Call sequence:
        1. Capital firms: compute credit limits, Q1=D1, S1=p1*Q1, Ld1=Q1/(A1p*a).
        2. LABOR: aggregate demands, check full-employment, ration if needed.
        3. Consumer firms: CANCMACH (execute scrapping); zero age of empty slots.
        """
        gparams = self.gparams
        if gparams is None:
            return

        dim_mach = gparams.machine_size_units
        a = gparams.s1_productivity_scale
        phi1 = gparams.credit_max_rule
        wage = self.labour_market.wage

        capital_firms = list(self.capital_good_sector)
        consumption_firms = list(self.consumption_good_sector)

        # ── Part 1: Capital-good firms ────────────────────────────────────────
        # C++ outer loop for i: Debmax1, debres1, Q1(i)=D1(i), S1+=p1*D1, Ld1=Q1/(A1p*a)
        for firm in capital_firms:
            if not firm.is_alive:
                continue

            # Debmax1(i) = phi1*S1(2,i); max with phi1*W1(2,i)
            debmax = phi1 * firm.sales_prev
            nw_based = phi1 * firm.net_worth_prev
            if nw_based > debmax:
                debmax = nw_based
            firm.max_credit = debmax
            firm.credit_line_remaining = max(0.0, debmax - firm.debt_prev)

            # Q1(i) = D1(i); D1 already accumulated in ALLOCATECREDIT via firm.demand
            firm.production = firm.demand
            # S1(1,i) = p1(1,i) * Q1(i)
            firm.sales = firm.price * firm.demand

            # Ld1(1,i) = Q1(i) / (A1p(1,i) * a)
            if firm.process_labour_prod > 0.0:
                firm.labour_demand = firm.production / (firm.process_labour_prod * a)
            else:
                firm.labour_demand = 0.0

        # ── Part 2: LABOR ─────────────────────────────────────────────────────
        self._run_labor_market()

        # ── Part 3: CANCMACH + age zeroing ────────────────────────────────────
        # C++ loop for j: if SI>0: CANCMACH; zero empty-slot ages; new-vintage update
        for firm in consumption_firms:
            if not firm.is_alive:
                continue

            # Execute actual scrapping when substitution investment was confirmed
            if firm.desired_substitution_investment > 0.0 and firm.machines is not None:
                firm.execute_scrapping(wage, gparams)

            # Zero age for empty machine slots (C++: if gtemp[tt][i][j]==0: age=0)
            if firm.machines is not None:
                zero_mask = firm.machines.count == 0.0
                firm.machines.age[zero_mask] = 0.0

            # New machine vintage: pending_order_n_machines was set in ALLOCATECREDIT;
            # machines are delivered to MachineStock in the next period's receive_machines().

    def _run_labor_market(self) -> None:
        """Aggregate labour demand; ration proportionally under full employment (LABOR).

        Ports module_macro.cpp LABOR() lines 406-575.
        M3 update: flag_clim_tech=1 path: energy labour (LDrd_en, LDexp_en, LDff_tot)
        is read from the previous period's electricity-producer and emissions state
        (these are updated by ENERGY and EMISS_IND of the *current* period, but LABOR
        runs before them, so it uses last period's values — matching C++ global state).

        Modifies:
        - capital firm production, labour_demand, sales, demand (under rationing)
        - consumer firm production, labour_demand, pending_order_n_machines (under rationing)
        - labour_market.labour_demand_s1, labour_demand_s2, labour_demand_total
        """
        lm = self.labour_market
        dim_mach = self.gparams.machine_size_units
        capital_firms = list(self.capital_good_sector)
        consumption_firms = list(self.consumption_good_sector)

        LS = lm.labour_supply
        LD1rdtot = lm.labour_demand_rd  # from prev period's TECHANGEND; 0 for t=1
        # Energy labour from prev period's ENERGY / EMISS_IND (C++ module_macro.cpp:440-445)
        ep = self.electricity_producer
        LDrd_en = ep.labour_demand_rd_total      # LDrd_en: set by do_rd
        LDexp_en = ep.labour_demand_expansion    # LDexp_en: set by plan_capacity_expansion
        LDff_tot = ep.labour_demand_fuel + self.fuel_labour_demand_s1  # LDff_en + LDff_1

        # Effective supply after assigning to R&D and energy (assumed to succeed)
        vital = LD1rdtot + LDrd_en + LDexp_en + LDff_tot
        LSe = LS - vital if vital < LS else LS

        # Aggregate production labour demands
        LD1tot = sum(f.labour_demand for f in capital_firms if f.is_alive)
        LD2tot = sum(f.labour_demand for f in consumption_firms if f.is_alive)

        if LD2tot + LD1tot <= LSe:
            # No rationing: all production demand met
            pass
        else:
            # Full employment: ration proportionally (C++ lines 461-518)
            scale = LSe / (LD1tot + LD2tot)

            for firm in consumption_firms:
                if firm.is_alive:
                    firm.production = firm.production * scale
                    firm.labour_demand = firm.labour_demand * scale

            for firm in capital_firms:
                if firm.is_alive and firm.production > 0.0:
                    Qpast = firm.production
                    firm.production = math.floor(Qpast * scale)
                    firm.labour_demand = firm.labour_demand * scale
                    firm.sales = firm.price * firm.production
                    firm.demand = firm.production

                    # Adjust matching consumer firms' pending investment orders
                    # C++: I(1,j)=floor(I(1,j)/dim_mach * Q1new/Q1old)*dim_mach
                    ratio = firm.production / Qpast if Qpast > 0.0 else 0.0
                    for consumer in firm.clients:
                        if not consumer.is_alive:
                            continue
                        old_n_mach = consumer.pending_order_n_machines
                        new_n_mach = math.floor(old_n_mach * ratio)
                        new_inv = new_n_mach * dim_mach

                        consumer.pending_order_n_machines = new_n_mach
                        old_ei = consumer.pending_expansion_investment
                        if new_inv < old_ei:
                            # C++: EI(1,j) = I(1,j)
                            consumer.pending_expansion_investment = new_inv
                            consumer.desired_expansion_investment = new_inv
                            consumer.desired_substitution_investment = 0.0
                        else:
                            consumer.desired_substitution_investment = new_inv - old_ei
                        consumer.desired_investment = new_inv

            # Re-aggregate after rationing (C++ lines 504-516)
            LD1tot = sum(f.labour_demand for f in capital_firms if f.is_alive)
            LD2tot = sum(f.labour_demand for f in consumption_firms if f.is_alive)

        # Store labour demand totals (C++: LD=LD1+LD2+LD1rdtot+energy; LD2=LD1+LD2 prod only)
        lm.labour_demand_s1 = LD1tot
        lm.labour_demand_s2 = LD2tot
        lm.labour_demand_total = LD1tot + LD2tot + vital

    def compute_industrial_emissions(self) -> None:
        """Aggregate fossil-fuel and process emissions from both sectors.

        Port of EMISS_IND (module_energy.cpp:68-115).

        Sector 1 (capital-good firms): emissions = fossil_fuel_demand * ff2em
          + process_env_filthiness * production.  Baseline has process emissions = 0
          (allow_proc_emissions_s1 = 0).

        Sector 2 (consumption-good firms): emissions = effective_env_filthiness
          * production (process emissions only; electricity-path emissions are in the
          electricity producer).  Baseline: effective_env_filthiness = 0.

        Also computes LDff_1 (labour in fossil-fuel extraction for sector 1) and
        carbon tax revenue from each sector.
        """
        gparams = self.gparams
        ff2em = gparams.fuel_to_emissions_factor          # ff2em = 1100
        ldf = gparams.fuel_labour_cost_fraction           # LDff_frac = 0.6
        pf = self.params.fossil_fuel_price
        wage = self.labour_market.wage
        t_co2_s1 = self.carbon_tax_rate_s1               # t_CO2_I1 (0 in baseline)
        t_co2_s2 = self.carbon_tax_rate_s2               # t_CO2_I2 (0 in baseline)

        tp_s1 = 0.0
        emiss1_tot = 0.0
        ldff1 = 0.0

        for firm in self.capital_good_sector:
            if not firm.is_alive:
                firm.emissions = 0.0
                firm.emissions_fossil = 0.0
                firm.emissions_process = 0.0
                continue
            # C++: Emiss1FF(i) = d1_ff_dummy1 * ff2em * Q1(i) = fossil_fuel_demand * ff2em
            firm.emissions_fossil = firm.fossil_fuel_demand * ff2em
            # C++: Emiss1EF(i) = A1p_ef(i) * Q1(i)
            firm.emissions_process = firm.process_env_filthiness * firm.production
            firm.emissions = firm.emissions_fossil + firm.emissions_process
            tp_s1 += firm.emissions * t_co2_s1
            emiss1_tot += firm.emissions
            # C++: LDff_1 += d1_ff_dummy1 * Q1(i) * pf * LDff_frac / w(1)
            if wage > 0.0:
                ldff1 += firm.fossil_fuel_demand * pf * ldf / wage

        tp_s2 = 0.0
        emiss2_tot = 0.0

        for firm in self.consumption_good_sector:
            if not firm.is_alive:
                firm.emissions = 0.0
                continue
            # C++: Emiss2(j) = A2e_ef(j) * Q2(1,j) (process emissions only for sector 2)
            firm.emissions = firm.effective_env_filthiness * firm.production
            tp_s2 += firm.emissions * t_co2_s2
            emiss2_tot += firm.emissions

        self.emissions_total_s1 = emiss1_tot
        self.emissions_total_s2 = emiss2_tot
        self.carbon_tax_revenue_s1 = tp_s1
        self.carbon_tax_revenue_s2 = tp_s2
        self.fuel_labour_demand_s1 = ldff1
        self._emissions_this_step = emiss1_tot + emiss2_tot

    def run_electricity_market(self, t: int) -> None:
        """Dispatch plants in merit order; set electricity price; run R&D (ENERGY).

        Port of C++ ENERGY() in module_energy.cpp.

        Phase order (mirrors C++ :119-1306):
        1. Inflation-correct all building costs (t > 3).
        2. Plant capacity expansion and premature replacement (t > t_spinup_energy).
        3. Merit-order dispatch (ELECTRICITY_MARKET).
        4. Schumpeterian R&D (innovation, imitation, frontier adoption).
        5. Fuel-extraction labour for the electricity producer (LDff_en).

        End-of-period plant retirement is done in closeout_phase (_retire_old_plants).
        The electricity_price_prev shift (c_en(2)=c_en(1)) is done in
        update_state_for_next_period.
        """
        gparams = self.gparams
        if gparams is None:
            return
        ep = self.electricity_producer
        wage = self.labour_market.wage
        pf = self.params.fossil_fuel_price
        carbon_tax_en = self.government.carbon_tax_rate_energy  # t_CO2_en

        # ── 1. Inflation-correct building costs (C++ ENERGY :126-141) ─────────
        # cpi_old(1)/cpi_old(2) = cpi(1)/cpi_prev (current/previous CPI).
        # At t<=3 cpi_prev is not yet reliably set; C++ also skips until t>3.
        if t > 3 and self.cpi_prev > 0.0:
            infl = self.cpi / self.cpi_prev
            if infl != 1.0:
                ep.green_plants.inflation_adjust(infl)
                ep.brown_plants.inflation_adjust(infl)
                ep.frontier_brown_build_cost *= infl
                ep.frontier_green_build_cost *= infl
                ep.green_build_cost_floor *= infl
                ep.brown_build_cost_floor *= infl
                ep.green_build_cost_govt_floor *= infl

        # ── 2. Plant capacity expansion (C++ ENERGY :244-782) ─────────────────
        # Spin-up (t <= t_spinup_energy): initial plants already seeded in
        # initialise_from_parameters; no new building during these periods.
        if t > gparams.t_spinup_energy:
            ep.plan_capacity_expansion(
                t, ep.total_energy_demand_build, pf, carbon_tax_en, gparams
            )

        # ── 3. Merit-order dispatch (C++ ELECTRICITY_MARKET) ──────────────────
        ep.dispatch_merit_order(ep.total_energy_demand, pf, carbon_tax_en)

        # ── 4. R&D phase (C++ ENERGY :931-1204) ───────────────────────────────
        ep.do_rd(t, pf, carbon_tax_en, wage, gparams)

        # ── 5. Fuel-extraction labour for electricity producer (C++ :1276) ────
        # LDff_en = Fuel_cost_eff * LDff_frac / w(2)
        # w(2) = previous-period wage (C++ uses lagged wage for this term)
        wage_prev = self.labour_market.wage_prev
        denom = wage_prev if wage_prev > 0.0 else (wage if wage > 0.0 else 1.0)
        ep.labour_demand_fuel = ep.fuel_cost * gparams.fuel_labour_cost_fraction / denom

    def compute_market_shares(self) -> None:
        """Replicator dynamics on consumption-good firms (COMPET2)."""
        if self.gparams is not None:
            self.consumption_good_sector.update_market_shares(self.gparams)

    # ------------------------------------------------------------------
    # Dynamics-phase sub-phases  (PROFIT → TECHANGEND)
    # ------------------------------------------------------------------

    def realise_profits_and_taxes(self, t: int = 1) -> None:
        """Realise firm profits, run GOV_BUDGET, ALLOC, sector-2 profit loop (PROFIT).

        Ports the C++ PROFIT() function (dsk_main.cpp 5048-5574) and the GOV_BUDGET()
        / ALLOC() calls it invokes, for the M1 baseline configuration:
          - flagdieW = 1   (sector-1 firms survive with W1=1 sentinel)
          - flagC = 2      (unemployment benefit = (LS-LD)*w*wu)
          - flagTAX = 2    (firm-profit taxes only; no wage tax)
          - flagCN = 0     (no carry-forward of Cpast into next period's Cons)
          - flag_interest_rate = 0  (homogeneous lending rate per bank)
          - flag_balancedbudget = 0 (no fiscal-rule corrections; Deb += Def)
          - No carbon tax, no electrification fine, no bonds market (Task 2.5).

        Phase order:
          1. Sector-1 firm-level PROFIT (Pi1, tax1, W1 update)
          2. GOV_BUDGET (G(1), Deb)
          3. Compute Cons = w*LD + Divtot_prev + G; reset Tax; add sector-1 taxes
          4. Compute cpi = Σ p2(j)*f2(1,j)
          5. ALLOC (sets per-firm D2(1,j), l2(j))
          6. Sector-2 firm-level PROFIT (S2, mol, Pi2, taxes, N, dN, CF, W2)
          7. Second-pass bad-debt loop (firms where CF < 0 and W2 < |CF|)
          8. Persist nation aggregates for next period (Divtot → Divtot_prev, ...)
        """
        gparams = self.gparams
        if gparams is None:
            return

        nparams = self.params
        aliq = nparams.tax_rate_firms_wages
        wage = self.labour_market.wage
        ls = self.labour_market.labour_supply
        ld = self.labour_market.labour_demand_total
        repayment_share = gparams.debt_repayment_fraction
        r_depo = self.central_bank.deposit_rate  # r_depo = r*(1-bankmarkdown); 0 at baseline (bankmarkdown=1)

        capital_firms = list(self.capital_good_sector)
        consumption_firms = list(self.consumption_good_sector)
        dim_mach = gparams.machine_size_units

        # ── Phase 1: Sector-1 PROFIT ──────────────────────────────────
        tax1_collect = 0.0
        Pitot1 = 0.0
        Wtot1 = 0.0
        Divtot1 = 0.0
        tp_elfrac = 0.0  # C++ tp_elfrac(1): total per-unit fine from sector-1 firms
        for firm in capital_firms:
            if not firm.is_alive:
                continue
            result = firm.realise_profit(aliq, gparams)
            Pitot1 += result["profit"]
            Wtot1 += max(0.0, result["net_worth"])
            Divtot1 += result["dividend"]
            tax1_collect += result["tax"]
            tp_elfrac += firm.elfrac_fine_per_unit  # C++ 5123: tp_elfrac(1) += cost1_dummy1-cost1_dummy2

        # Track electrification fine as government revenue (C++ ymc col 61: tp_elfrac)
        self.government.total_electrification_fine = tp_elfrac
        self.elfrac_revenue = tp_elfrac

        # ── Phase 2: GOV_BUDGET ───────────────────────────────────────
        # self.total_tax holds the PREVIOUS period's accumulated tax (not yet
        # updated this period — that happens in Phase 9). This matches C++
        # dsk_main.cpp:5093: "Taxes from previous period needed in Gov_budget".
        self.government.compute_budget(
            t=t,
            labour_supply=ls,
            labour_demand=ld,
            wage=wage,
            tax_previous_period=self.total_tax,
            banks=list(self.banking_sector),
        )
        G = self.government.spending

        # ── Phase 3: Cons + Tax reset ─────────────────────────────────
        # C++ line 5225: Tax = 0; then Tax += tax1_collect (5258)
        # flagTAX = 2 baseline → no wage tax
        # flagCN = 0 baseline → no Cpast carry-forward
        Cons = wage * ld + self.total_dividends_prev + G
        Tax = tax1_collect
        self.consumption_budget_nominal = Cons

        # ── Phase 4: Compute cpi and c2_weighted ──────────────────────
        cpi = 0.0
        c2tot = 0.0
        for firm in consumption_firms:
            if not firm.is_alive:
                continue
            cpi += firm.price * firm.market_share
            c2tot += firm.effective_unit_cost * firm.market_share
        if cpi < 0.01:
            # C++ line 5289: emergency floor to avoid /0; flag it but proceed
            cpi = 0.01
        self.cpi = cpi

        # ── Phase 5: ALLOC ────────────────────────────────────────────
        market_shares = [f.market_share for f in consumption_firms]
        prices = [f.price for f in consumption_firms]
        self.household_sector.allocate_consumption(
            market_shares=market_shares,
            prices=prices,
            firms=consumption_firms,
            cons_nominal=Cons,
            cpi=cpi,
        )

        # ── Phase 6: Sector-2 PROFIT main loop ────────────────────────
        Pitot2 = 0.0
        Wtot2 = 0.0
        Divtot2 = 0.0
        Qtot2 = 0.0
        dN_aggregate = 0.0
        dNm_aggregate = 0.0
        total_actual_consumption_real = 0.0
        nominal_consumption_value = 0.0
        nominal_inventory_change = 0.0
        nominal_value_output_s2 = 0.0
        for firm in consumption_firms:
            if not firm.is_alive:
                # Dead firms have already been removed from the bank credit
                # pool (ALLOCATECREDIT); skip in PROFIT.
                continue
            lending_rate = 0.0
            if firm.bank_idx is not None and 0 <= firm.bank_idx < len(self.banking_sector):
                bank = list(self.banking_sector)[firm.bank_idx]
                lending_rate = bank.lending_rate
            res = firm.realise_profit(
                aliq=aliq,
                lending_rate=lending_rate,
                deposit_rate=r_depo,
                repayment_share=repayment_share,
                gparams=gparams,
            )
            Pitot2 += res["profit"]
            Divtot2 += res["dividend"]
            Tax += res["tax"]
            Qtot2 += firm.production
            dN_aggregate += res["inventory_change_real"]
            dNm_aggregate += res["inventory_change_nominal"]
            total_actual_consumption_real += res["actual_consumption_real"]
            nominal_consumption_value += firm.price * res["actual_consumption_real"]
            nominal_inventory_change += res["inventory_change_nominal"]
            nominal_value_output_s2 += firm.price * firm.production
            if firm.net_worth >= 0.0:
                Wtot2 += firm.net_worth

        # ── Phase 7: Second-pass bad-debt loop ────────────────────────
        # C++ dsk_main.cpp lines 5434-5494. Triggered when CF<0 and W2 < |CF|.
        for firm in consumption_firms:
            if not firm.is_alive:
                continue
            cf = firm.cash_flow
            if firm.net_worth > 0.0 and cf < 0.0 and firm.net_worth < -cf:
                # Firm dies — bank-side bookkeeping: bad debt = max(remaining debt - NW, 0)
                bad = max(0.0, firm.debt)
                if firm.net_worth > 0.0 and bad > 0.0:
                    recovered = firm.net_worth
                    bad = max(0.0, bad - recovered)
                # If CF still positive (it isn't here), would also recover from CF
                firm.bad_debt = bad

                # C++ "Deb2(1,*)=0" line 5485 (the buggy `rated_firm_2` index in C++
                # is treated here as a clean per-firm reset; the Python port is
                # explicit about which firm dies).
                firm.debt = 0.0
                firm.debt_prev = 0.0

                # Apply the deferred W2 update from the first loop
                firm.net_worth += cf
                # Mark dead — exit handling happens in process_entry_and_exit (Task 1.13)
                firm.market_share = 0.0
                firm.market_share_prev = 0.0
                firm.market_share_prev_prev = 0.0
                if firm.net_worth < 0.0:
                    firm.net_worth = 0.0

        # ── Phase 8: Sector-1 real investment (machines delivered = Σ Q1) ────
        total_machine_units = 0.0
        for firm in capital_firms:
            if firm.is_alive:
                total_machine_units += firm.production
        # Convert to capital-stock units (× dim_mach) for SFC closure
        nominal_investment_value = 0.0
        for firm in capital_firms:
            if firm.is_alive:
                nominal_investment_value += firm.price * firm.production

        # ── Phase 9: Persist Nation-level aggregates ──────────────────
        self.total_tax = Tax
        self.total_profit_s1 = Pitot1
        self.total_profit_s2 = Pitot2
        self.total_net_worth_s1 = Wtot1
        self.total_net_worth_s2 = Wtot2
        # Save Divtot for next period (becomes Divtot_prev after UPDATE)
        # In M1 dividends are 0 (d1=d2=0), so this is a no-op for the SFC check.
        self.total_dividends = Divtot1 + Divtot2

        # Real-flow accumulators (used by NationalAccounts.check_real_flows)
        self.total_production_s2_real = Qtot2
        self.total_production_s1_real = total_machine_units
        self.total_real_consumption = total_actual_consumption_real
        self.total_real_inventory_change = dN_aggregate
        # Investment in machine units (matches sector-1 production units)
        self.total_real_investment_machines = total_machine_units

        # Nominal flow aggregates
        self.consumption_nominal_realised = nominal_consumption_value
        self.investment_nominal = nominal_investment_value
        self.inventory_change_nominal = nominal_inventory_change
        # Nominal GDP = nominal-value of total production (sector 1 + sector 2)
        self.gdp_nominal = nominal_value_output_s2 + nominal_investment_value

    def update_banks(self) -> None:
        """Banks realise profit, pay dividends, fail if insolvent (BANKING)."""
        gparams = self.gparams
        if gparams is None:
            return
        cb = self.central_bank
        banks = list(self.banking_sector)

        # Pre-compute reserve income: r_cbreserves * BankCash(2,j) for each bank
        cb.remunerate_reserves(banks)

        bank_dividends = 0.0
        bank_taxes = 0.0
        for bank in banks:
            if not bank.is_active:
                continue
            result = bank.compute_profit_and_dividend()
            bank_dividends += result["dividends"]
            bank_taxes += result["tax"]
            bank.fail_if_insolvent()

        # Accumulate bank dividends and taxes into nation aggregates
        self.total_dividends += bank_dividends
        self.total_tax += bank_taxes

    def bailout_failed_banks(self) -> None:
        """Government bails out failed banks; recapitalises (BAILOUT)."""
        gparams = self.gparams
        if gparams is None:
            return
        gbailout_all = self.banking_sector.bailout_failed_banks(
            gparams, self.params, self.rng
        )
        self.government.bailout_cost += gbailout_all
        # This period's bailout total (Gbailout_all, C++ output col 41), stored
        # cleanly for SAVE — government.bailout_cost is muddled by GOV_BUDGET's
        # prior-period read above, so keep an unambiguous per-period copy.
        self.gbailout_this_period = gbailout_all

    def aggregate_macro_indicators(self, t: int = 1) -> None:
        """Compute GDP, unemployment, mean productivity, PPI, wage (MACRO + WAGE).

        Ports module_macro.cpp MACRO() (lines 1124-1878) and WAGE() (lines 20-257)
        for the M1 baseline: flagPRODLAG=0, flagGDP=0, flagCN=0, flag_clim_tech=0,
        flagENTRY=0, flagWAGE=3 (inflation-target-adjusted wage rule), flagWAGE2=0.

        Call order: runs after PROFIT (so cpi, Cons, dNtot, dNmtot are already set)
        and before UPDATE.

        After this method:
          labour_market.unemployment_rate = (LS-LD)/LS
          labour_market.mean_machine_prod = Am(1)  [LD-weighted]
          labour_market.wage = new wage [w(2)*(1+dw)]
          self.real_gdp = GDP(1) = Creal + Ir*p1m/p2m + dNtot
          self.gdp_nominal = GDPm = Cmon + Imon + dNmtot
          self.ppi = ppi(1) [production-weighted mean s1 price]
          s1 firms: market_share updated to f1(i) = Q1(i)/Qtot1
        """
        gparams = self.gparams
        if gparams is None:
            return

        nparams = self.params
        lm = self.labour_market
        capital_firms = list(self.capital_good_sector)
        consumption_firms = list(self.consumption_good_sector)

        # Production labour demand: LD2(1) in C++ = LD1tot + LD2tot (excludes R&D)
        # C++ module_macro.cpp line 521: LD2 = LD1tot + LD2tot
        LD2_prod = lm.labour_demand_s1 + lm.labour_demand_s2
        LD = lm.labour_demand_total    # total (includes R&D)
        LS = lm.labour_supply

        # ── Sector-2 aggregates (C++ j-loop, lines 1208-1356) ──────────────────
        # C++ accumulates: Q2tot, Am2, Am(1) contribution, Cmon, Nt1/2tot, etc.
        Cmon = 0.0    # Σ p2(j)*Q2(j) — nominal sector-2 production
        Am_new = 0.0  # Am(1): production-LD-weighted mean productivity (both sectors)
        Am2 = 0.0     # Σ A2e(j)*f2(j) — market-share-weighted (sector 2 only)

        for firm in consumption_firms:
            if not firm.is_alive:
                continue
            # Am2 += A2e(j) * f2(1,j)  [C++ line 1219]
            Am2 += firm.effective_labour_prod_used * firm.market_share
            # Cmon += p2(j) * Q2(j)  [C++ line 1355]
            Cmon += firm.price * firm.production
            # Am(1) contribution from sector 2 (flagPRODLAG=0 branch, C++ line 1268)
            if LD2_prod > 0.0:
                Am_new += (firm.labour_demand / LD2_prod) * firm.effective_labour_prod_used

        # ── Sector-1 aggregates (C++ i-loop, lines 1413-1469) ─────────────────
        Qtot1 = sum(f.production for f in capital_firms if f.is_alive)
        Imon = 0.0    # Σ p1(i)*Q1(i) — nominal investment  [C++ line 1424]
        ppi_new = 0.0 # Σ p1(i)*Q1(i)/Qtot1 — PPI           [C++ line 1430]
        Am1 = 0.0     # Σ A1p(i)*Q1(i)/Qtot1 — production-wtd sector-1 productivity [1431]
        Debtot1 = 0.0

        n1_alive = sum(1 for f in capital_firms if f.is_alive)

        for firm in capital_firms:
            if not firm.is_alive:
                continue
            # Update s1 market share: f1(i) = Q1(i)/Qtot1  [C++ line 1416-1418]
            if Qtot1 > 0.0:
                firm.market_share = firm.production / Qtot1
            # else: keep previous market share (C++ uses f1(2,i))

            Imon += firm.price * firm.production
            Debtot1 += firm.debt

            if Qtot1 > 0.0:
                weight = firm.production / Qtot1
                ppi_new += firm.price * weight            # [C++ line 1430]
                Am1 += firm.process_labour_prod * weight  # [C++ line 1431]
                # Am(1) contribution from sector 1  [C++ line 1461]
                if LD2_prod > 0.0:
                    Am_new += (firm.labour_demand / LD2_prod) * firm.process_labour_prod
            else:
                # Qtot1==0: simple sum, divide by n1_alive below  [C++ lines 1445-1456]
                ppi_new += firm.price
                Am1 += firm.process_labour_prod
                if LD2_prod > 0.0:
                    Am_new += (firm.labour_demand / LD2_prod) * firm.process_labour_prod

        if n1_alive > 0 and Qtot1 == 0.0:
            ppi_new /= n1_alive
            Am1 /= n1_alive

        if ppi_new < 0.01:
            ppi_new = 0.01  # guard against zero PPI

        # Am(1) guard: if non-positive, fall back to previous period  [C++ line 1616-1617]
        if Am_new <= 0.0:
            Am_new = lm.mean_machine_prod  # use current (prev period's value)

        # ── p2m: mean sector-2 price (for GDP price-ratio term) ────────────────
        # C++ COMPET2 line 4942: p2m = p2.Sum()/N2r (mean over all alive firms)
        alive_cons = [f for f in consumption_firms if f.is_alive]
        p2m = sum(f.price for f in alive_cons) / len(alive_cons) if alive_cons else 1.0
        p1m = self.capital_good_sector.mean_price  # set in MACH (mean of prev-period s1 prices)

        # ── GDP and macro indicators (C++ lines 1627-1703) ────────────────────
        Ir = Qtot1      # real investment = sector-1 production (machines)
        cpi = self.cpi  # cpi(1): already set by PROFIT Phase 4
        Cons = self.consumption_budget_nominal  # set by PROFIT Phase 3

        # Creal = Cons / cpi(1)  [C++ line 1644]
        Creal = Cons / cpi if cpi > 0.0 else 0.0
        # flagCN=0 baseline: do NOT subtract Cpast from Creal

        # dNtot and dNmtot: computed in PROFIT (Σ(N1-N2) per firm)
        dNtot = self.total_real_inventory_change
        dNmtot = self.inventory_change_nominal

        # GDP(1) = Creal + Ir*p1m/p2m + dNtot  [C++ line 1662]
        gdp_real = Creal + (Ir * p1m / p2m if p2m > 0.0 else 0.0) + dNtot
        # Small-negative clamp (C++ lines 1665-1666)
        if -1.0 < gdp_real < 0.0:
            gdp_real = 0.0

        # TFP = GDP / LD  [C++ line 1668]
        TFP = gdp_real / LD if LD > 0.0 else gdp_real  # noqa: F841 (stored for future SAVE)

        # GDPm = Cmon + Imon + dNmtot  [C++ line 1673]
        gdp_nominal_m = Cmon + Imon + dNmtot

        # GDP growth rate (C++ lines 1693-1703; only for t > 1)
        old_real_gdp = self.real_gdp  # holds GDP from previous period
        if t > 1 and old_real_gdp > 0.0 and gdp_real > 0.0:
            gdp_growth = math.log(gdp_real) - math.log(old_real_gdp)
        else:
            gdp_growth = 0.0

        # U(1) = (LS - LD) / LS  [C++ line 1707]
        U1 = (LS - LD) / LS if LS > 0.0 else 0.0
        if U1 < 0.0:
            U1 = 0.0  # numerical clamp (C++ warns but doesn't crash for small negatives)

        # ── Store results on Nation ─────────────────────────────────────────────
        self.real_gdp = gdp_real        # GDP(1)
        self.gdp_nominal = gdp_nominal_m  # GDPm (overrides partial value set by PROFIT)
        self.ppi_prev = self.ppi
        self.ppi = ppi_new
        self.real_consumption = Creal
        self.real_investment = Ir
        self.mean_prod_s1 = Am1
        self.mean_prod_s2 = Am2
        self.s1_debt_total = Debtot1
        self.gdp_growth_rate = gdp_growth

        # ── Store results on LabourMarket ───────────────────────────────────────
        lm.unemployment_rate_prev = lm.unemployment_rate
        lm.unemployment_rate = U1
        # Save old Am before overwriting (WAGE uses it for d_Am)
        Am_old = lm.mean_machine_prod
        lm.mean_machine_prod_prev = Am_old
        lm.mean_machine_prod = Am_new

        # ── WAGE: update nominal wage (C++ WAGE() called at line 1809) ──────────
        self._compute_wage(Am_old=Am_old, Am_new=Am_new, U_new=U1, gparams=gparams, nparams=nparams)

        # NOTE: cpi(2) is shifted to cpi(1) only in update_state_for_next_period
        # (C++ UPDATE), NOT here. set_policy_rate (TAYLOR) runs after MACRO in the
        # dynamics phase and needs the *unshifted* cpi_prev to compute d_cpi; a
        # premature shift here was zeroing the Taylor inflation gap.

    def _compute_wage(
        self,
        *,
        Am_old: float,
        Am_new: float,
        U_new: float,
        gparams,
        nparams,
    ) -> None:
        """Nominal wage update (WAGE function, module_macro.cpp lines 20-257).

        Implements flagWAGE=3 (inflation-gap rule) and flagWAGE2=0 (no downward rigidity).
        Updates labour_market.wage and labour_market.labour_supply in-place.

        Parameters (passed explicitly to avoid re-reading nation state mid-computation):
        Am_old  — Am(2): previous period mean productivity (before this period's update)
        Am_new  — Am(1): current period mean productivity
        U_new   — U(1): current unemployment rate (just computed)
        """
        lm = self.labour_market
        ustar = gparams.unemployment_target    # natural rate = 0.05
        mdw   = gparams.wage_max_change        # max component change = 0.5
        psi1  = nparams.wage_inflation_response    # sensitivity to inflation gap = 0.05
        psi2  = gparams.wage_productivity_response # sensitivity to productivity = 0.9
        psi3  = nparams.wage_unemployment_response # sensitivity to unemployment = 0.05
        d_cpi_target = gparams.inflation_target    # = 0.02/4 = 0.005
        w_min = gparams.wage_subsistence           # = 1.0

        # U(2): clamp from below at ustar (C++ lines 33-34)
        U_prev = max(lm.unemployment_rate_prev, ustar)

        # d_U = (U(1) - U(2)) / U(2)  [C++ line 36]
        d_U = (U_new - U_prev) / U_prev if U_prev != 0.0 else 0.0

        # d_cpi = (cpi(1) - cpi(2)) / cpi(2)  [C++ lines 38-43]
        cpi_prev = self.cpi_prev  # saved from previous period
        if cpi_prev != 0.0:
            d_cpi = (self.cpi - cpi_prev) / cpi_prev
        else:
            d_cpi = 0.0

        # d_Am = (Am(1) - Am(2)) / Am(2)  [C++ lines 54-57]
        if Am_old != 0.0:
            d_Am = (Am_new - Am_old) / Am_old
        else:
            d_Am = 0.0

        # Apply ±mdw clamps to each component  [C++ lines 75-86]
        d_cpi = max(-mdw, min(mdw, d_cpi))
        d_Am  = max(-mdw, min(mdw, d_Am))
        d_U   = max(-mdw, min(mdw, d_U))

        # flagWAGE==3: target-inflation + inflation-gap rule  [C++ lines 113-128]
        # Both branches simplify to the same formula but are written symmetrically
        # around the target in the C++ to show intent clearly.
        if d_cpi < d_cpi_target:
            dw = d_cpi_target - psi1 * (d_cpi_target - d_cpi) + psi2 * d_Am - psi3 * d_U
        else:
            dw = d_cpi_target + psi1 * (d_cpi - d_cpi_target) + psi2 * d_Am - psi3 * d_U

        # flagWAGE2==1: downward rigidity floor  [C++ lines 130-141]
        if gparams.downward_wage_rigidity == 1:
            min_dw = gparams.wage_change_floor
            if dw < min_dw:
                dw = min_dw

        # w(1) = w(2) * (1 + dw)  [C++ line 149]
        # In Python: lm.wage holds the "active" wage = C++'s w(2) at call time
        new_wage = lm.wage * (1.0 + dw)

        # Subsistence floor  [C++ lines 223-229]
        if new_wage < w_min - 0.001:
            new_wage = w_min

        # Real wage: rw = w(2)/cpi(1)  [C++ line 246]
        self.real_wage = lm.wage / self.cpi if self.cpi > 0.0 else lm.wage

        # Store wage change rate and update wage
        lm.wage_change = dw
        lm.wage = new_wage  # takes effect as "active wage" for next period

        # Labour supply growth: LS *= (1+eta)  [C++ line 251]
        lm.labour_supply *= (1.0 + gparams.labour_supply_growth)

    def set_policy_rate(self) -> None:
        """Central bank applies Taylor rule (TAYLOR, module_macro.cpp:263).

        Computes d_cpi from nation.cpi / nation.cpi_prev, reads unemployment
        from labour_market, then delegates to CentralBank.apply_taylor_rule().
        """
        cpi_prev = self.cpi_prev
        if cpi_prev > 0.0:
            inflation = (self.cpi - cpi_prev) / cpi_prev
        else:
            inflation = 0.0
        unemployment = self.labour_market.unemployment_rate
        self.central_bank.apply_taylor_rule(inflation, unemployment)

    def process_entry_and_exit(self) -> None:
        """Failed/small firms exit; entrants created as copies of incumbents (ENTRYEXIT).

        C++ dsk_main.cpp ENTRYEXIT() lines 6072-6870, flagENTRY=0 (random copy) branch.

        Sequence (mirrors C++ function structure):
        1. Identify dead/surviving s1 and s2 firms; compute survivor means.
        2. Replace dead s1 firms in-place: copy random incumbent's state; distribute
           N2/N1 brochures as initial clients.
        3. Clear pending investment for any s2 firm whose s1 supplier just died.
        4. Replace dead s2 firms in-place: copy random incumbent's state; copy machine
           stock with ages reset to 0; assign random new s1 supplier.

        All replacements are in-place (sector list length stays constant).
        The 'entry_random_copy_scope' flag (flagENTRY) is 0 for M1 baseline.
        'entry_random_copy_fraction' (flagENTRY2) is 0 for M1 baseline (exact copy).
        """
        gparams = self.gparams
        rng = self.rng

        exit2 = gparams.s2_exit_market_share_floor
        nu = gparams.rd_budget_fraction
        xi = gparams.innovation_imitation_split
        step = gparams.n2_consumption_good_firms // gparams.n1_capital_good_firms

        capital_firms = list(self.capital_good_sector)
        consumption_firms = list(self.consumption_good_sector)
        n1 = len(capital_firms)
        n2 = len(consumption_firms)

        # ------------------------------------------------------------------
        # Pass 1 — identify dead / surviving firms, compute survivor means
        # ------------------------------------------------------------------

        # Sector-1: dead if num_clients == 0 or net_worth <= 0
        # C++: if (nclient(i) >= 1 && W1(1,i) > 0) → survivor; else dead
        W1m = 0.0
        nwm1 = 0
        s1_dead_idxs: list[int] = []
        for i, firm in enumerate(capital_firms):
            if firm.num_clients >= 1 and firm.net_worth > 0.0:
                W1m += firm.net_worth
                nwm1 += 1
            else:
                s1_dead_idxs.append(i)
        if nwm1 > 0:
            W1m /= nwm1

        # Sector-2: dead if market_share < exit2 or net_worth <= 0
        # C++: if (f2(1,j) >= exit2 && W2(1,j) > 0) → survivor; else dead
        # Guard: Ke(j)==0 — in flagENTRY=0, no new entrants this period, so no guard needed
        W2m = 0.0
        Km = 0.0
        nwm2 = 0
        s2_dead_idxs: list[int] = []
        # next2bc (C++ ymc col 79 "bancruptcy"): count of s2 firms exiting with
        # positive bad debt this period (dsk_main.cpp:6610-6617).  This is the
        # Fig 1/3/5 panel-g indicator (bankruptcy likelihood = next2bc / N2).
        n_s2_bankruptcies = 0
        for j, firm in enumerate(consumption_firms):
            if firm.market_share >= exit2 and firm.net_worth > 0.0:
                Km += firm.capital_stock
                W2m += firm.net_worth
                nwm2 += 1
            else:
                s2_dead_idxs.append(j)
                if firm.bad_debt > 0.0:
                    n_s2_bankruptcies += 1
        self.n_s2_bankruptcies = n_s2_bankruptcies
        if nwm2 > 0:
            W2m /= nwm2
            Km /= nwm2

        s1_dead_set = set(s1_dead_idxs)
        alive_s1_idxs = [i for i in range(n1) if i not in s1_dead_set]
        alive_s2_idxs = [j for j in range(n2) if j not in set(s2_dead_idxs)]

        # ------------------------------------------------------------------
        # Pass 2 — replace dead s1 firms in-place
        # C++ lines 6219-6566 (flagENTRY==0, flagENTRY2==0)
        # ------------------------------------------------------------------
        if alive_s1_idxs and s1_dead_idxs:
            for i_dead in s1_dead_idxs:
                dead_s1 = capital_firms[i_dead]

                # Remove dead s1 from all consumer brochure sets
                # C++: for j: Match(j,i)=0
                for j_firm in consumption_firms:
                    j_firm.brochure_senders_idxs.discard(i_dead)

                # Pick random alive incumbent for state copy (C++ rejection sampling
                # over alive firms via the while-loop at dsk_main.cpp:6651-6659).
                i_inc = alive_s1_idxs[int(rng.integers(0, len(alive_s1_idxs)))]
                inc = capital_firms[i_inc]

                # Copy incumbent state (C++ lines 6289-6298)
                dead_s1.net_worth = inc.net_worth
                dead_s1.net_worth_prev = inc.net_worth_prev
                dead_s1.machine_labour_prod = inc.machine_labour_prod
                dead_s1.unit_cost = inc.unit_cost
                dead_s1.price = inc.price
                dead_s1.price_prev = inc.price_prev
                dead_s1.process_labour_prod = inc.process_labour_prod
                dead_s1.process_labour_prod_prev = inc.process_labour_prod_prev
                dead_s1.current_technology = inc.current_technology  # immutable
                dead_s1.vintage = inc.vintage

                # --- C++ flagENTRY2=5 perturbations (dsk_main.cpp:6336-6454) ---
                # 1) Net worth: uniform[w1inf, w1sup] * W1m, overwriting the copy.
                # 2) Productivity: copied from a SEPARATE random firm `kkk` drawn
                #    from ALL N1 firms (may include freshly-dead ones — C++ uses
                #    `int(ran1()*10000) % N1 + 1` over the full N1 range).
                w1inf = gparams.s1_entrant_networth_lower      # 0.1
                w1sup = gparams.s1_entrant_networth_upper      # 0.9
                multip_W = w1inf + float(rng.uniform(0.0, 1.0)) * (w1sup - w1inf)
                dead_s1.net_worth = multip_W * W1m
                dead_s1.net_worth_prev = multip_W * W1m

                kkk = int(rng.integers(0, n1))                  # full N1 range, like C++ %N1
                src_s1 = capital_firms[kkk]
                dead_s1.machine_labour_prod = src_s1.machine_labour_prod
                dead_s1.process_labour_prod = src_s1.process_labour_prod
                dead_s1.process_labour_prod_prev = src_s1.process_labour_prod_prev
                dead_s1.current_technology = src_s1.current_technology

                # Reset market position (C++: f1=0; size1=0)
                dead_s1.market_share = 0.0
                dead_s1.market_share_prev = 0.0

                # Initial sales from step=N2/N1 initial clients; sets R&D budget
                # C++: S1(1,i)=p1(1,i)*step; S1(2,i)=S1(1,i)
                dead_s1.sales = dead_s1.price * step
                dead_s1.sales_prev = dead_s1.sales
                dead_s1.rd_budget = nu * dead_s1.sales
                dead_s1.rd_budget_prev = dead_s1.rd_budget
                dead_s1.rd_innovation_budget = xi * dead_s1.rd_budget
                dead_s1.rd_imitation_budget = (1.0 - xi) * dead_s1.rd_budget

                # Reset transient state
                dead_s1.debt = 0.0
                dead_s1.debt_prev = 0.0
                dead_s1.profit = 0.0
                dead_s1.patent_timer = 0.0
                dead_s1.production = 0.0
                dead_s1.demand = 0.0
                dead_s1.labour_demand = 0.0
                dead_s1.is_alive = True

                # Distribute step = N2/N1 random unique consumer clients
                # C++ lines 6555-6564: while(stepbis>0) {rni=rand()%N2; if Match==0: add, stepbis--}
                dead_s1.clients = []
                dead_s1.num_clients = 0
                assigned: set[int] = set()
                while len(assigned) < step:
                    rni = int(rng.integers(0, n2))
                    if rni not in assigned:
                        assigned.add(rni)
                        consumption_firms[rni].brochure_senders_idxs.add(i_dead)
                        dead_s1.clients.append(consumption_firms[rni])
                        dead_s1.num_clients += 1

        # ------------------------------------------------------------------
        # Pass 3 — clear pending investment for consumers whose s1 supplier died
        # C++ lines 6246-6274
        # ------------------------------------------------------------------
        for j_firm in consumption_firms:
            if j_firm.preferred_supplier_idx in s1_dead_set:
                # C++: EI(1,j)=EI(2,j)=SI(1,j)=SI(2,j)=I(1,j)=I(2,j)=0; fornit(j)=0
                j_firm.desired_expansion_investment = 0.0
                j_firm.desired_substitution_investment = 0.0
                j_firm.desired_investment = 0.0
                j_firm.pending_order_n_machines = 0.0
                j_firm.pending_expansion_investment = 0.0
                j_firm.machine_order_total_cost = 0.0
                j_firm.preferred_supplier_idx = -1  # orphaned; BROCHURE will reassign

        # ------------------------------------------------------------------
        # Pass 4 — replace dead s2 firms in-place
        # C++ lines 6578-6820 (flagENTRY==0, flagENTRY2==0)
        # ------------------------------------------------------------------
        if alive_s2_idxs and s2_dead_idxs:
            for j_dead in s2_dead_idxs:
                dead_s2 = consumption_firms[j_dead]

                # Remove dead s2 from its old supplier's client list
                # C++: Match(j,fornit(j))=0; fornit(j)=0
                old_sidx = dead_s2.preferred_supplier_idx
                if 0 <= old_sidx < n1 and old_sidx not in s1_dead_set:
                    old_sup = capital_firms[old_sidx]
                    if dead_s2 in old_sup.clients:
                        old_sup.clients.remove(dead_s2)
                        old_sup.num_clients -= 1

                # Pick random alive s2 incumbent (C++ rejection sampling)
                j_inc = alive_s2_idxs[int(rng.integers(0, len(alive_s2_idxs)))]
                inc = consumption_firms[j_inc]

                # Reset investment / debt state (C++ lines 6645-6659)
                dead_s2.inventory = 0.0
                dead_s2.inventory_monetary = 0.0
                dead_s2.desired_expansion_investment = 0.0
                dead_s2.desired_substitution_investment = 0.0
                dead_s2.desired_investment = 0.0
                dead_s2.pending_order_n_machines = 0.0
                dead_s2.pending_expansion_investment = 0.0
                dead_s2.pending_order_supplier_idx = -1
                dead_s2.pending_order_vintage = -1
                dead_s2.pending_order_technology = None
                dead_s2.debt = 0.0
                dead_s2.debt_prev = 0.0
                dead_s2.bad_debt = 0.0
                dead_s2.credit_demand = 0.0
                dead_s2.cash_flow = 0.0
                dead_s2.profit = 0.0
                dead_s2.dividends = 0.0
                dead_s2.debt_interest = 0.0
                dead_s2.labour_demand = 0.0
                dead_s2.machine_order_total_cost = 0.0
                dead_s2.machine_order_expansion_cost = 0.0
                dead_s2.machine_order_substitution_cost = 0.0
                dead_s2.potential_expansion_investment = 0.0
                dead_s2.potential_substitution_investment = 0.0
                dead_s2.potential_total_investment = 0.0
                dead_s2.scrap_candidates = []
                dead_s2.is_alive = True
                dead_s2.is_new_entrant = False  # flagENTRY==0: no Ke-style entrants

                # Copy incumbent state (C++ lines 6663-6703, flagENTRY==0)
                # f2(3,j) = f2(2,jjj): entrant's prev-prev = incumbent's prev (one step lag)
                dead_s2.market_share = inc.market_share
                dead_s2.market_share_prev = inc.market_share_prev
                dead_s2.market_share_prev_prev = inc.market_share_prev
                dead_s2.markup = inc.markup
                dead_s2.competitiveness = inc.competitiveness
                dead_s2.competitiveness_prev = inc.competitiveness_prev
                dead_s2.net_worth = inc.net_worth
                dead_s2.net_worth_prev = inc.net_worth_prev
                dead_s2.demand = inc.demand
                dead_s2.demand_prev = inc.demand_prev
                dead_s2.expected_demand = inc.expected_demand
                dead_s2.unit_cost = inc.unit_cost
                dead_s2.production = inc.production
                dead_s2.sales = inc.sales
                dead_s2.sales_prev = inc.sales_prev
                dead_s2.unfilled_demand = inc.unfilled_demand
                dead_s2.capital_stock = inc.capital_stock
                dead_s2.price = inc.price
                dead_s2.price_prev = inc.price_prev
                dead_s2.gross_operating_margin = inc.gross_operating_margin
                dead_s2.n_machines = inc.n_machines
                dead_s2.effective_labour_prod = inc.effective_labour_prod
                dead_s2.effective_labour_prod_used = inc.effective_labour_prod_used
                dead_s2.effective_unit_cost = inc.effective_unit_cost

                # Copy machine stock from the state-source incumbent, ages reset
                # C++ flagENTRY2==5 *overrides* the capital with that of a
                # SECOND random firm `lll` (line 6802-6805) — see below.
                if inc.machines is not None:
                    new_machines = copy.deepcopy(inc.machines)
                    if new_machines.age.size > 0:
                        new_machines.age[:] = 0.0
                    dead_s2.machines = new_machines

                # --- C++ flagENTRY2=5 perturbations (dsk_main.cpp:6754-6806) ---
                # 1) Net worth: uniform[w2inf, w2sup] * W2m, overwriting the copy.
                # 2) Capital + n_machines: from a SECOND random firm `lll` drawn
                #    from ALL N2 firms (C++: int(ran1()*10000) % N2 + 1).  This
                #    is a separate random draw from the state-copy source `j_inc`,
                #    so entrants get more dispersion than a single-source copy
                #    would provide.  Crucial for matching C++'s Pareto α ≈ 4.3
                #    (Python without this gives α ≈ 5.5 — too thin a tail).
                w2inf = gparams.s2_entrant_networth_lower      # 0.1
                w2sup = gparams.s2_entrant_networth_upper      # 0.9
                multip_W = w2inf + float(rng.uniform(0.0, 1.0)) * (w2sup - w2inf)
                dead_s2.net_worth = multip_W * W2m
                dead_s2.net_worth_prev = multip_W * W2m

                lll = int(rng.integers(0, n2))                  # full N2 range
                src_s2 = consumption_firms[lll]
                dead_s2.capital_stock = src_s2.capital_stock
                dead_s2.n_machines = src_s2.n_machines
                # Rebuild the machine matrix to match: a single vintage at the
                # current period with `n_machines` units of capacity from the
                # new supplier (matches C++ lines 6810-6828 which set all old-
                # vintage cells to 0 and concentrate the entrant's stock at
                # (current_period, indforn)).
                #
                # The supplier assignment happens just below; pre-build with
                # the machines from src_s2 here, supplier reassignment will
                # consolidate them into the indforn slot.
                if src_s2.machines is not None:
                    new_machines = copy.deepcopy(src_s2.machines)
                    if new_machines.age.size > 0:
                        new_machines.age[:] = 0.0
                    dead_s2.machines = new_machines

                # Assign random new s1 supplier (C++ lines 6660-6662)
                new_sidx = int(rng.integers(0, n1))
                dead_s2.preferred_supplier_idx = new_sidx
                dead_s2.brochure_senders_idxs = {new_sidx}
                capital_firms[new_sidx].clients.append(dead_s2)
                capital_firms[new_sidx].num_clients += 1

    def advance_technology(self) -> None:
        """Capital-good firms do R&D: Bernoulli trials, beta draws, imitation (TECHANGEND).

        M1 path: only labour-productivity is advanced (energy axes deferred to M3).
        Each firm runs the per-firm port of C++ TECHANGEND; afterwards the sector's
        A1top/A1ptop frontier is recomputed for use by next period's Td-norm
        imitation, and total R&D labour demand is published to the LabourMarket
        for next period's unemployment / TFP calculations.
        """
        gparams = self.gparams
        sector = self.capital_good_sector
        all_firms = list(sector)
        if not all_firms:
            return

        # TECHANGEND runs after MACRO+WAGE: lm.wage now = C++ w(1) post-update.
        wage = self.labour_market.wage
        elec_price = self.electricity_producer.electricity_price  # c_en(1) for TECHANGEND
        # A1top/A1ptop were set by the prior period's TECHANGEND (or initialise
        # via CapitalGoodSector.__init__ for t=1).
        A1top = sector.A1_top
        A1ptop = sector.A1p_top

        for firm in all_firms:
            firm.advance_technology(
                wage=wage,
                A1top=A1top,
                A1ptop=A1ptop,
                all_firms=all_firms,
                gparams=gparams,
                elec_price=elec_price,
            )

        # Recompute the sector frontier from updated firm state (C++ 7773-7800).
        sector.update_frontier()

        # Publish total R&D labour demand to the LabourMarket. Read by the
        # next production phase via lm.labour_demand_rd (see nation.py:703).
        self.labour_market.labour_demand_rd = sum(f.rd_labour_demand for f in all_firms)

    # ------------------------------------------------------------------
    # Closeout-phase sub-phases  (SHOCKS → UPDATE)
    # ------------------------------------------------------------------

    def apply_climate_shocks(self) -> None:
        """Apply temperature-driven productivity shocks (C++ SHOCKS in module_climate.cpp).

        Port of ``SHOCKS`` which runs after CLIMATEBOX and before UPDATECLIMATE.

        In the C++ call order:
          CLIMATEBOX → SHOCKS → SAVE → UPDATE → UPDATECLIMATE

        ``SHOCKS`` uses:
          - ``Tmixed(2)`` = surface temp from the *previous* climate step
            (pre-fold); exposed here as ``climate.previous_surface_temperature``.
          - ``Tanomaly(1)`` = the just-computed surface temp
            (post-CLIMATEBOX); exposed as ``nation.temperature_anomaly``.

        ``flag_shocks == 0`` (baseline): no shocks applied.  All other
        ``flag_shocks`` values (1–9) are future-work; flag_shocks==9 (Nordhaus
        GDP damage) is implemented here since it only requires macro aggregates.
        """
        if self.gparams is None or self._last_climate is None:
            return

        gp = self.gparams
        shock_type: int = int(gp.climate_shock_type)

        if shock_type == 0:
            return  # baseline: no shocks

        import math

        # --- Compute beta-distribution parameters (X_a, X_b) -----------------
        # C++ uses Tmixed(2) which is the previous-step temperature.
        tmixed_prev: float = self._last_climate.previous_surface_temperature
        t_pre: float = float(gp.temp_pre_industrial_global_mean)
        a_0: float = float(gp.shock_beta_a)
        b_0: float = float(gp.shock_beta_b)

        x_a = a_0 * (1.0 + math.log((tmixed_prev + t_pre) / t_pre))
        x_b = b_0  # V_5y_temp variance was removed by C++ author; use constant b_0

        # --- flag_shocks == 9: Nordhaus GDP-level damage ----------------------
        if shock_type == 9:
            # Loss = 1 / (1 + a2_nord * Tanomaly(1)^a3_nord)
            tanomaly_cur = self.temperature_anomaly
            a2 = float(gp.nordhaus_damage_coefficient)
            a3 = float(gp.nordhaus_damage_exponent)
            loss = 1.0 / (1.0 + a2 * math.pow(tanomaly_cur, a3))
            self.real_gdp *= loss

        # Other flag_shocks branches (1–8) apply shocks to individual firms,
        # plants, inventories, or labour supply — deferred until milestone 5
        # (scenario work) when the relevant scenarios are first run.

    def save_outputs(self, t: int) -> None:
        """Write current period's state to the output sink (SAVE).

        Writes the macro snapshot (time series of key aggregates) for later analysis.
        Mirrors C++ SAVE() in dsk_main.cpp:8632.
        """
        if self.sink is None:
            return

        # Real and nominal GDP (GDP(1), GDPm in C++)
        gdp_real = self.real_gdp
        gdp_nominal = self.gdp_nominal

        # Consumption and investment flows
        consumption_real = self.total_real_consumption
        consumption_nominal = self.consumption_nominal_realised
        investment_real = self.total_real_investment_machines
        investment_nominal = self.investment_nominal
        inventory_change = self.total_real_inventory_change

        # Price indices
        cpi = self.cpi
        ppi = self.ppi

        # Labour market
        unemployment_rate = self.labour_market.unemployment_rate
        wage = self.labour_market.wage
        labour_demand = self.labour_market.labour_demand_total
        labour_supply = self.labour_market.labour_supply

        # Productivity
        mean_machine_prod = self.labour_market.mean_machine_prod
        mean_process_prod = self.labour_market.mean_process_prod

        # Sector-level aggregates
        total_profit_s1 = self.total_profit_s1
        total_profit_s2 = self.total_profit_s2
        total_net_worth_s1 = self.total_net_worth_s1
        total_net_worth_s2 = self.total_net_worth_s2
        total_debt_s1 = self.s1_debt_total

        # Banking sector aggregates
        total_bank_equity = sum(
            bank.equity for bank in self.banking_sector if bank is not None
        )
        total_bad_debt = sum(
            bank.total_bad_debt for bank in self.banking_sector if bank is not None
        )
        # countbf_all2 (C++ output col 37): number of bank failures this period.
        # bank.failed_this_period is still set here — it is reset by
        # update_state_for_next_period(), which runs AFTER save_outputs().
        n_bank_failures = sum(
            1
            for bank in self.banking_sector
            if bank is not None and bank.is_active and bank.failed_this_period
        )

        # Government / fiscal (M2)
        government_spending = self.government.spending
        government_debt = self.government.debt              # Deb
        government_deficit = self.government.deficit        # Def
        government_bailout = self.gbailout_this_period      # Gbailout_all
        tax_revenue = self.total_tax                        # Tax
        # DebonGDP (C++ output col 30): Deb/GDPm when GDPm>1, else Deb
        # (module_macro.cpp:803-815).
        debt_on_gdp = (
            government_debt / gdp_nominal if gdp_nominal > 1.0 else government_debt
        )

        # Monetary policy (M2)
        policy_rate = self.central_bank.policy_rate         # r
        bonds_rate = self.central_bank.bonds_rate           # r_bonds

        # Energy / climate (M3) — C++ ymc cols 16, 17, 48, 50, 52, 53, 54, 55, 56,
        # plus a sector-electrification proxy not in ymc.
        ep = self.electricity_producer
        d_en_tot = float(ep.total_energy_demand)
        share_energy_green = (
            float(ep.total_green_energy) / d_en_tot if d_en_tot > 0.0 else 0.0
        )
        electricity_price = float(ep.electricity_price)
        emissions_energy = float(getattr(ep, "emissions", 0.0))
        emissions_total = (
            float(self.emissions_total_s1)
            + float(self.emissions_total_s2)
            + emissions_energy
        )
        d1_ff_total = float(getattr(self, "_d1_ff_tot", 0.0))
        if not d1_ff_total:
            # Fallback: re-sum from firms (kept cheap; only ~N1 floats).
            d1_ff_total = sum(
                float(getattr(f, "fossil_fuel_demand", 0.0))
                for f in self.capital_good_sector
                if getattr(f, "is_alive", True)
            )
        # Sector-1 electrification proxy: production-weighted mean of A1p_el.
        s1_elf_num = 0.0
        s1_elf_den = 0.0
        for f in self.capital_good_sector:
            if not getattr(f, "is_alive", True):
                continue
            q = float(getattr(f, "production", 0.0))
            if q <= 0.0:
                continue
            elf = float(getattr(f.current_technology, "electrification_fraction", 0.0))
            s1_elf_num += q * elf
            s1_elf_den += q
        mean_electrification_s1 = s1_elf_num / s1_elf_den if s1_elf_den > 0.0 else 0.0

        # M4 climate state — current period's atmospheric carbon, surface temperature, and
        # the calibrated emissions flux fed to the climate box (C++ ymc cols 19, 20, 18).
        # ``_last_climate`` is seeded at Simulation.__init__ so it is always populated.
        clim = self._last_climate
        if clim is not None:
            atmospheric_carbon = float(clim.atmospheric_carbon)
            surface_temperature = float(clim.surface_temperature)
            emissions_yearly_calib = float(getattr(clim, "_emiss_calib_prev", 0.0))
        else:  # pragma: no cover — unreachable once seeded by Simulation.
            atmospheric_carbon = 0.0
            surface_temperature = 0.0
            emissions_yearly_calib = 0.0

        # Record the full row
        self.sink.record(
            "macro",
            mc_run=self._mc_run,
            t=t,
            nation_id=self.nation_id,
            gdp_real=gdp_real,
            gdp_nominal=gdp_nominal,
            consumption_real=consumption_real,
            consumption_nominal=consumption_nominal,
            investment_real=investment_real,
            investment_nominal=investment_nominal,
            inventory_change=inventory_change,
            cpi=cpi,
            ppi=ppi,
            unemployment_rate=unemployment_rate,
            wage=wage,
            labour_demand=labour_demand,
            labour_supply=labour_supply,
            mean_machine_prod=mean_machine_prod,
            mean_process_prod=mean_process_prod,
            total_profit_s1=total_profit_s1,
            total_profit_s2=total_profit_s2,
            total_net_worth_s1=total_net_worth_s1,
            total_net_worth_s2=total_net_worth_s2,
            total_debt_s1=total_debt_s1,
            total_bank_equity=total_bank_equity,
            total_bad_debt=total_bad_debt,
            n_bank_failures=n_bank_failures,
            government_spending=government_spending,
            government_debt=government_debt,
            government_deficit=government_deficit,
            government_bailout=government_bailout,
            tax_revenue=tax_revenue,
            debt_on_gdp=debt_on_gdp,
            policy_rate=policy_rate,
            bonds_rate=bonds_rate,
            # M3 energy / climate
            share_energy_green=share_energy_green,
            electricity_price=electricity_price,
            total_energy_demand=d_en_tot,
            emissions_total_s1=float(self.emissions_total_s1),
            emissions_total_s2=float(self.emissions_total_s2),
            n_s2_bankruptcies=int(self.n_s2_bankruptcies),
            emissions_energy=emissions_energy,
            emissions_total=emissions_total,
            d1_fossil_fuel_demand=d1_ff_total,
            mean_electrification_s1=mean_electrification_s1,
            total_green_capacity=float(ep.total_green_capacity),
            total_brown_capacity=float(ep.total_brown_capacity),
            # M4 climate
            atmospheric_carbon=atmospheric_carbon,
            surface_temperature=surface_temperature,
            emissions_yearly_calib=emissions_yearly_calib,
        )

    def update_state_for_next_period(self) -> None:
        """Shift current-period state to previous-period storage arrays (UPDATE).

        Mirrors C++ UPDATE() in dsk_main.cpp:9004.
        Shifts: var(1) → var(2) for all time-series state.
        """
        # --- Nation-level macro scalars ---
        self.cpi_prev = self.cpi
        self.ppi_prev = self.ppi
        self.total_dividends_prev = self.total_dividends

        # --- Labour market state ---
        lm = self.labour_market
        lm.wage_prev = lm.wage
        lm.unemployment_rate_prev = lm.unemployment_rate
        lm.mean_machine_prod_prev = lm.mean_machine_prod
        lm.mean_process_prod_prev = lm.mean_process_prod
        lm.labour_supply_prev = lm.labour_supply

        # --- Capital-good firm (sector 1) state ---
        for firm in self.capital_good_sector:
            firm.market_share_prev = firm.market_share
            firm.price_prev = firm.price
            firm.sales_prev = firm.sales
            firm.net_worth_prev = firm.net_worth
            firm.debt_prev = firm.debt
            firm.process_labour_prod_prev = firm.process_labour_prod
            firm.rd_budget_prev = firm.rd_budget

        # --- Consumption-good firm (sector 2) state ---
        for firm in self.consumption_good_sector:
            # Standard shifts
            firm.market_share_prev_prev = firm.market_share_prev
            firm.market_share_prev = firm.market_share
            firm.price_prev = firm.price
            firm.sales_prev = firm.sales
            firm.net_worth_prev = firm.net_worth
            firm.debt_prev = firm.debt
            firm.competitiveness_prev = firm.competitiveness
            firm.demand_prev = firm.demand

        # --- Bank state shifts (C++ UPDATE: BankCash(2,j)=BankCash(1,j)) ---
        for bank in self.banking_sector:
            bank.cash_prev = bank.cash   # BankCash(2,j) = BankCash(1,j)
            bank.failed_this_period = False

        # --- Energy state shift (C++ UPDATE lines 9157-9158) ---
        # c_en(2) = c_en(1): previous electricity price used in cost functions
        ep = self.electricity_producer
        ep.electricity_price_prev = ep.electricity_price

        # --- Reset per-step counters (C++ UPDATE lines 9019-9024) ---
        # These are reset to ensure clean accumulation in the next step's production phase.
        self.government.bailout_cost = 0.0
        for bank in self.banking_sector:
            bank.bailout_cost = 0.0
            bank.reserve_interest_income = 0.0
        self.labour_market.labour_demand_total = 0.0
        self.labour_market.labour_demand_s1 = 0.0
        self.labour_market.labour_demand_s2 = 0.0
        self.labour_market.labour_demand_rd = 0.0

    # ------------------------------------------------------------------
    # Aggregated phase wrappers (called by Simulation.step)
    # ------------------------------------------------------------------

    def production_phase(self, t: int) -> None:
        """Run all production sub-phases in canonical C++ order."""
        self.set_climate_policy(t)
        self.compute_bank_client_net_worth()
        self.deliver_machines()
        self.determine_total_credit()
        self.compute_bonds_demand()
        self.compute_max_credit_per_firm()
        self.distribute_brochures()
        self.plan_investment(t)
        self.allocate_credit_to_demand(t)
        self.produce_machines()
        # EN_DEM: aggregate firm-level energy demands (C++ inside PRODMACH, after LABOR)
        if self.gparams is not None:
            self.electricity_producer.aggregate_demand(
                t, self.capital_good_sector, self.consumption_good_sector
            )
        self.compute_industrial_emissions()
        self.run_electricity_market(t)
        # C++: Emiss_TOT(1) = Emiss_en_eff + Emiss2_TOT + Emiss1_TOT (module_energy.cpp:1283)
        self._emissions_this_step += float(
            getattr(self.electricity_producer, "emissions", 0.0)
        )
        self.compute_market_shares()

    def dynamics_phase(self, t: int) -> None:
        """Run all dynamics sub-phases in canonical C++ order."""
        self.realise_profits_and_taxes(t)
        self.update_banks()
        self.bailout_failed_banks()
        self.aggregate_macro_indicators(t)
        self.set_policy_rate()
        self.process_entry_and_exit()
        self.advance_technology()

    def closeout_phase(self, t: int) -> None:
        """Run all closeout sub-phases in canonical C++ order."""
        self.apply_climate_shocks()
        self.save_outputs(t)
        self.update_state_for_next_period()
        self._retire_old_plants(t)

    def _retire_old_plants(self, t: int) -> None:
        """Scrap plants that have reached end-of-life (C++ ENERGY :1210-1230).

        Plants older than ``life_plant`` are removed at the end of the period.
        Under a brown-use ban, all brown plants are also scrapped immediately.
        Runs in closeout so the dispatch and R&D phases see a full fleet.
        """
        if self.gparams is None:
            return
        ep = self.electricity_producer
        life = self.gparams.plant_lifetime_years
        ep.green_plants.retire_old(t, life)
        ep.brown_plants.retire_old(t, life)
        # Brown-use ban: scrap any remaining brown plants (baseline never triggers)
        if ep.brown_use_ban_year - t <= 0:
            for plant in list(ep.brown_plants):
                ep.brown_plants.remove(plant)
        ep._update_capacity()
