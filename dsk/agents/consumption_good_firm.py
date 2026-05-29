"""Sector-2 consumption-good firm.

Mirrors C++ N2-indexed state vectors in dsk_globalvar.h:
f2[j], W2[j], Deb2[j], p2[j], c2[j], mu2[j], D2[j], De[j],
Ne[j], N[j], Nm[j], S2[j], fornit[j], CreditSupplier[j],
g[tt][i][j] (via MachineStock), Em2[j], E2[j], etc.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional

import numpy as np

from dsk.agents.agent import Agent
from dsk.agents.machine_stock import MachineStock
from dsk.agents.technology import Technology

if TYPE_CHECKING:
    from dsk.nation import Nation
    from dsk.parameters.global_parameters import GlobalParameters
    from dsk.parameters.nation_parameters import NationParameters


class ConsumptionGoodFirm(Agent):
    """Sector-2 firm: produces consumption goods using a vintage capital stock."""

    def __init__(self, nation: "Nation", rng: np.random.Generator) -> None:
        super().__init__(nation)
        self.rng = rng

        # --- Capital stock ---
        # Backed by MachineStock; set by initialise_from_parameters.
        self.machines: MachineStock | None = None

        # --- Technology ---
        # A2[j]: harmonic-mean effective labour productivity across all machine vintages.
        self.effective_labour_prod: float = 1.0

        # --- Market state ---
        # f2[2,j]: market share (current and previous period)
        self.market_share: float = 0.0
        self.market_share_prev: float = 0.0
        # p2[2,j]: good price
        self.price: float = 0.0
        self.price_prev: float = 0.0
        # c2[j]: unit production cost
        self.unit_cost: float = 0.0
        # mu2[j]: price markup
        self.markup: float = 0.0
        # S2[2,j]: sales revenue
        self.sales: float = 0.0
        self.sales_prev: float = 0.0
        # Em2[j], E2[j]: competitiveness index (price + unfilled demand)
        self.competitiveness: float = 1.0
        self.competitiveness_prev: float = 1.0
        # l2[j]: unfulfilled demand (set by ALLOC; used in next period's COMPET2)
        # C++ comment: "per via dei logaritmi" — initialized to 1 after first ALLOC pass
        self.unfilled_demand: float = 0.0

        # --- Demand and production ---
        # D2[j]: actual demand received this period
        self.demand: float = 0.0
        # De[j]: expected demand (adaptive, myopic, or rule-based)
        self.expected_demand: float = 0.0
        # Q2[j]: actual production this period
        self.production: float = 0.0
        # Desired production before credit constraint
        self.desired_production: float = 0.0
        # Ld2[j]: labour demand
        self.labour_demand: float = 0.0

        # --- Inventory ---
        # N[j]: goods inventory in units
        self.inventory: float = 0.0
        # Nm[j]: goods inventory in nominal terms
        self.inventory_monetary: float = 0.0

        # --- Investment plans ---
        # SI[j]: substitution (replacement) investment in machine-size units
        self.desired_substitution_investment: float = 0.0
        # EI[j]: expansion investment in machine-size units
        self.desired_expansion_investment: float = 0.0
        # I[j]: total desired investment = EI + SI
        self.desired_investment: float = 0.0

        # --- Machine order (placed with capital-good supplier) ---
        # Number of machine units ordered (in dim_mach multiples)
        self.machine_order_quantity: float = 0.0
        # 0-indexed index into the CapitalGoodSector list of the chosen supplier
        self.machine_order_supplier_idx: int = -1

        # --- Financial state ---
        # W2[2,j]: net worth / liquid assets
        self.net_worth: float = 0.0
        self.net_worth_prev: float = 0.0
        # Deb2[2,j]: outstanding debt
        self.debt: float = 0.0
        self.debt_prev: float = 0.0
        # Pi2[j]: profit this period
        self.profit: float = 0.0
        # div2[j]: dividends paid
        self.dividends: float = 0.0
        # DebtInterests2[j]: interest paid on debt
        self.debt_interest: float = 0.0
        # NWS2[j]: net-worth-to-sales ratio (used for credit rationing rank)
        self.net_worth_to_sales: float = 0.0
        # Debmax2[j]: maximum credit this firm may carry
        self.max_credit: float = 0.0
        # Remaining credit line after allocation
        self.credit_line_remaining: float = 0.0

        # --- Capital stock ---
        # K[j]: total capital in machine-size units (= n_mach * dim_mach)
        self.capital_stock: float = 0.0
        # n_mach[j]: number of machines (K/dim_mach)
        self.n_machines: float = 0.0

        # --- Market share history (three periods for markup update) ---
        # f2(3,j): two periods ago — needed by mu2 update in MACH
        self.market_share_prev_prev: float = 0.0

        # --- Pending machine order (set by ORD/ALLOCATECREDIT; delivered in MACH) ---
        # Corresponds to I(2,j)/dim_mach: machines to deliver at the start of the next period.
        self.pending_order_n_machines: float = 0.0
        # EI(2,j): expansion part of the investment (changes K)
        self.pending_expansion_investment: float = 0.0
        # 0-indexed capital-good supplier that will deliver the machines
        self.pending_order_supplier_idx: int = -1
        # Vintage key (= period t when the order was placed; used as MachineStock key)
        self.pending_order_vintage: int = -1
        # Technology embedded in the pending machines (snapshot from capital-good firm)
        self.pending_order_technology: Optional[Technology] = None

        # --- Entry status ---
        # Ke(j) > 0 in C++ means new entrant; Ke(j)==0 means incumbent
        self.is_new_entrant: bool = False

        # --- Relationships ---
        # fornit[j] - 1: 0-indexed preferred capital-good supplier
        self.preferred_supplier_idx: int = -1
        # CreditSupplier[j] - 1: 0-indexed bank
        self.bank_idx: int = -1

        # --- Brochure matching (Match matrix column for this firm) ---
        # Set of 0-indexed capital-good firm indices that sent this firm a brochure.
        # Persists between periods; after each BROCHURE = {preferred_supplier_idx}.
        self.brochure_senders_idxs: set = set()

        # --- Status ---
        self.is_alive: bool = True

        # --- Energy (sector-2 machine energy properties, M3 Tasks 3.6–3.7) ---
        # A2e_en[j]: effective energy need per unit of output (arithmetic mean over
        # USED machines, weighted by machine count; analogous to A2e for labour).
        # C++ init: A2e_en = A2_en = A0_en.
        self.effective_energy_efficiency: float = 0.0
        # D2_en[j]: electricity demand this period (set by aggregate_demand)
        self.elec_demand: float = 0.0
        # A2e_ef[j]: effective env filthiness (process emissions; = 0 when allow_proc_emissions_s2=0)
        self.effective_env_filthiness: float = 0.0
        # Emiss2[j]: per-firm emissions (EMISS_IND)
        self.emissions: float = 0.0

        # ---------------------------------------------------------------
        # INVEST / ORD state  (Task 1.7)
        # ---------------------------------------------------------------

        # D2(2,j): previous period's actual demand (shifted from demand in UPDATE)
        self.demand_prev: float = 0.0

        # mol(j): gross operating margin = S2 - c2e*Q2, set in PROFIT, used in ORD
        # At initialisation = 0 (no prior production revenue)
        self.gross_operating_margin: float = 0.0

        # A2e(1,j): effective labour productivity over machines USED for production.
        # Equals A2 when all machines are used (Qd >= K); differs when Qd < K (COSTPROD).
        self.effective_labour_prod_used: float = 1.0

        # c2e(j): average unit production cost over USED machines (C(tt,i) weighted by g).
        # Equals unit_cost when all machines are used; may differ when Qd < K.
        self.effective_unit_cost: float = 1.0

        # Kd(j): desired capital stock in machine-size units
        self.desired_capital: float = 0.0

        # Scrapping candidates identified by SCRAPPING (plan_substitution_investment).
        # Each entry is (vintage_key, supplier_idx, machine_count).
        # Actual removal from MachineStock happens in ALLOCATECREDIT (Task 1.8).
        self.scrap_candidates: list = []

        # EIp(j): expansion investment after prudential credit limit (ORD output)
        self.potential_expansion_investment: float = 0.0
        # SIp(j): substitution investment after prudential credit limit (ORD output)
        self.potential_substitution_investment: float = 0.0
        # Ip(j) = EIp + SIp: total potential investment (ORD output)
        self.potential_total_investment: float = 0.0

        # Machine investment cost breakdown (CmachEI, CmachSI, Cmach in C++)
        self.machine_order_expansion_cost: float = 0.0
        self.machine_order_substitution_cost: float = 0.0
        self.machine_order_total_cost: float = 0.0

        # ---------------------------------------------------------------
        # ALLOCATECREDIT state  (Task 1.8)
        # ---------------------------------------------------------------

        # CreditDemand(1,j): credit demand computed at the start of ALLOCATECREDIT
        self.credit_demand: float = 0.0
        # baddebt(j): portion of old debt written off when firm dies
        self.bad_debt: float = 0.0

        # ---------------------------------------------------------------
        # PROFIT state  (Task 1.11)
        # ---------------------------------------------------------------
        # CF(j): cash flow this period; set in realise_profit and read by the
        # second-pass bad-debt loop in Nation.realise_profits_and_taxes.
        self.cash_flow: float = 0.0
        # DebtRemittances2(j): debt repayment made this period; stored for BANKING.
        self.debt_remittance: float = 0.0

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def initialise_from_parameters(
        self,
        gparams: "GlobalParameters",
        nparams: "NationParameters",
        preferred_supplier_idx: int,
        bank_idx: int,
        machine_counter_start: int = 0,
    ) -> int:
        """Set this firm to the C++ baseline initial values.

        Mirrors INITIALIZE() in dsk_main.cpp for N2 sector-2 firms
        (lines ~1205-1640, especially 1580-1625).

        Parameters
        ----------
        preferred_supplier_idx:
            0-indexed index of this firm's preferred capital-good supplier.
            C++ equivalent: fornit(j) - 1.
        bank_idx:
            0-indexed bank assignment. C++ equivalent: CreditSupplier(j) - 1.
        machine_counter_start:
            Value of the C++ global `i` counter at the start of this firm's
            machine initialisation loop (0 for the very first firm). The caller
            threads this across all N2 firms so each firm's machines are placed
            using a continuous rotating counter, matching C++ line 1588 `i++`.

        Returns
        -------
        int
            Updated machine counter value after placing all machines.
            Pass this as `machine_counter_start` for the next firm.
        """
        N1 = gparams.n1_capital_good_firms
        N2 = gparams.n2_consumption_good_firms
        A0 = gparams.productivity_init             # = 1.0
        a = gparams.s1_productivity_scale          # = 0.1
        w0 = gparams.wage_init                     # = 1.0
        mi1 = gparams.s1_markup                    # = 0.04
        nu = gparams.rd_budget_fraction            # = 0.04
        dim_mach = gparams.machine_size_units      # = 40.0
        theta = gparams.inventory_target_fraction  # = 0.1
        agemax = gparams.machine_max_age           # = 19.0
        LS0 = gparams.labour_supply_init           # = 500000.0
        K0 = gparams.capital_init                  # = 800.0
        W20 = gparams.s2_net_worth_init            # = 1000.0

        mi2 = nparams.s2_markup_init               # = 0.2
        wu = nparams.unemployment_benefit_share    # = 0.4

        # Store relationships
        self.preferred_supplier_idx = preferred_supplier_idx
        self.bank_idx = bank_idx
        self.brochure_senders_idxs = {preferred_supplier_idx}

        # Price and cost (C++: c2=w0/A0; p2=(1+mi2)*w0/A0)
        p1 = (1.0 + mi1) * w0 / (A0 * a)          # sector-1 price (10.4)
        p2 = (1.0 + mi2) * w0 / A0                 # = 1.2
        c2 = w0 / A0                               # = 1.0

        self.price = p2
        self.price_prev = p2
        self.unit_cost = c2
        self.markup = mi2

        # Market share (C++: f2=1/N2r)
        self.market_share = 1.0 / N2
        self.market_share_prev = self.market_share

        # Net worth and debt (C++: W2=W20; Deb2=0)
        self.net_worth = W20
        self.net_worth_prev = W20
        self.debt = 0.0
        self.debt_prev = 0.0

        # Initial investment = one machine per firm (C++: I=dim_mach)
        I_init = dim_mach

        # Aggregate demand at steady state (C++ INITIALIZE, flagC==2, flagTAX==2):
        # D20 = ((w/(A1p*a) + nu*p1) * I/dim_mach * N2 * (1-wu) + wu*w*LS)
        #       / (p2 - (1-wu)*w/A2)
        # At init all productivities are A0, so A1p=A0 and A2=A0.
        numerator = (
            (w0 / (A0 * a) + nu * p1) * (I_init / dim_mach) * N2 * (1.0 - wu)
            + wu * w0 * LS0
        )
        denominator = p2 - (1.0 - wu) * w0 / A0
        d20 = numerator / denominator
        d2 = d20 / N2  # per-firm expected demand

        self.expected_demand = d2
        self.demand = d2
        self.sales = d2 * p2
        self.sales_prev = self.sales

        # Inventory (C++: Ne=theta*D20/N2; N=theta*D20/N2; Nm=Ne*p2)
        self.inventory = theta * d2
        self.inventory_monetary = theta * d2 * p2

        # Competitiveness (C++: Em2=1; E2=1)
        self.competitiveness = 1.0
        self.competitiveness_prev = 1.0
        # Unfulfilled demand: set to 0 at init (first ALLOC hasn't run yet)
        self.unfilled_demand = 0.0

        # Effective labour productivity (all machines same A0)
        self.effective_labour_prod = A0

        # --- Machine stock ---
        # C++ lines 1580-1608: each firm j gets K0/dim_mach machines at vintage tt=1
        # (index 0), spread across N1 suppliers via a global rotating counter `i`.
        # The counter is not reset between firms; ages cycle agemax+1 → 1 per firm.
        n_mach_init = int(round(K0 / dim_mach))   # = 20
        self.machines = MachineStock(n_suppliers=N1)

        initial_tech = Technology(
            labour_productivity=A0,
            energy_efficiency=gparams.energy_need_init,
        )

        age0 = int(agemax) + 1   # reset per firm (C++: age0=agemax+1 inside j-loop)
        machine_counter = machine_counter_start   # 1-indexed C++ `i`; 0 = "before first"

        for _ in range(n_mach_init):
            # Advance counter; wrap; skip preferred supplier.
            # C++: i++; if(i>N1) i=1; if(fornit(j)!=i) { place; }
            while True:
                machine_counter += 1
                if machine_counter > N1:
                    machine_counter = 1
                if machine_counter != (preferred_supplier_idx + 1):  # +1 → 1-indexed
                    break

            supplier_0idx = machine_counter - 1   # 0-indexed for MachineStock

            self.machines.add_machines(
                vintage_key=0,
                supplier_idx=supplier_0idx,
                count=1.0,
                technology=initial_tech,
                age=float(age0),
            )

            age0 -= 1
            if age0 < 1:
                age0 = int(agemax) + 1

        # --- Capital stock (C++: K=K0; n_mach=K0/dim_mach) ---
        self.capital_stock = K0
        self.n_machines = float(n_mach_init)

        # --- Market share history (f2(3,j)=0 at t=0, matches C++ zero-init) ---
        self.market_share_prev_prev = 0.0

        # --- Reset transient / pending state ---
        self.profit = 0.0
        self.production = 0.0
        self.desired_production = 0.0
        self.desired_substitution_investment = 0.0
        self.desired_expansion_investment = 0.0
        self.desired_investment = 0.0
        self.machine_order_quantity = 0.0
        self.machine_order_supplier_idx = -1
        self.labour_demand = 0.0
        self.debt_interest = 0.0
        self.dividends = 0.0
        self.net_worth_to_sales = 0.0
        self.max_credit = 0.0
        self.credit_line_remaining = 0.0
        self.pending_order_n_machines = 0.0
        self.pending_expansion_investment = 0.0
        self.pending_order_supplier_idx = -1
        self.pending_order_vintage = -1
        self.pending_order_technology = None
        self.is_new_entrant = False
        self.is_alive = True

        # --- Energy fields (Task 3.6) ---
        # C++: A2e_en = A2_en = A0_en at init (each machine's energy_efficiency = A0_en)
        self.effective_energy_efficiency = gparams.energy_need_init
        self.elec_demand = 0.0

        # --- INVEST / ORD fields (Task 1.7) ---
        self.demand_prev = d2
        self.gross_operating_margin = 0.0
        self.effective_labour_prod_used = A0
        self.effective_unit_cost = c2
        self.desired_capital = 0.0
        self.scrap_candidates = []
        self.potential_expansion_investment = 0.0
        self.potential_substitution_investment = 0.0
        self.potential_total_investment = 0.0
        self.machine_order_expansion_cost = 0.0
        self.machine_order_substitution_cost = 0.0
        self.machine_order_total_cost = 0.0

        # --- ALLOCATECREDIT fields (Task 1.8) ---
        self.credit_demand = 0.0
        self.bad_debt = 0.0

        # --- PROFIT fields (Task 1.11) ---
        self.cash_flow = 0.0
        self.debt_remittance = 0.0

        return machine_counter

    # ------------------------------------------------------------------
    # Per-period update (MACH)
    # ------------------------------------------------------------------

    def receive_machines(
        self,
        gparams: "GlobalParameters",
        wage: float,
        elec_price: float = 0.0,
        carbon_tax_s2: float = 0.0,
    ) -> None:
        """Deliver pending machines; update capital, productivity, cost, markup, price (MACH).

        Ports C++ dsk_main.cpp MACH() lines 2386–2512.
        DSK17 baseline (flag_clim_tech==1): C(tt,i) includes electricity price.

        Note: In the current C++ ('new' version), machine PAYMENT was removed from
        MACH and moved to ALLOCATECREDIT (Task 1.8). This method does not deduct
        payment from net_worth or debt. No firm death occurs here.

        Parameters
        ----------
        gparams
            Global parameters (dim_mach, pmin, etc.).
        wage
            Current-period wage w(2) — used to compute machine unit costs C(tt,i).
        elec_price
            Previous-period electricity price c_en(2). Default 0 → KS15 labour-only cost.
        carbon_tax_s2
            Carbon tax rate for sector 2 (t_CO2_I2). Default 0 → baseline.
        """
        dim_mach = gparams.machine_size_units
        pmin = gparams.firm_price_floor
        deltami2 = self.nation.params.s2_markup_step_change

        # --- Deliver pending machines into stock ---
        # C++: K(j) += EI(2,j);  g[...] = gtemp[...]
        if self.pending_order_n_machines > 0 and self.pending_order_technology is not None:
            self.machines.add_machines(
                vintage_key=self.pending_order_vintage,
                supplier_idx=self.pending_order_supplier_idx,
                count=self.pending_order_n_machines,
                technology=self.pending_order_technology,
                age=0.0,
            )
        self.capital_stock += self.pending_expansion_investment
        self.n_machines = self.machines.total_machines()

        # Clear pending state after delivery
        self.pending_order_n_machines = 0.0
        self.pending_expansion_investment = 0.0
        self.pending_order_supplier_idx = -1
        self.pending_order_vintage = -1
        self.pending_order_technology = None

        # New entrants don't update productivity/price here (Ke(j) > 0 in C++)
        if self.is_new_entrant or self.n_machines <= 0:
            return

        # --- Recompute aggregate labour productivity (harmonic mean) ---
        # C++: A2(j) = 1 / sum_tt_i [ (1/A(tt,i)) * g[...] / n_mach ]
        self.effective_labour_prod = self.machines.effective_labour_productivity()

        # --- Recompute unit cost with energy (DSK17 baseline) ---
        # C++: C(tt,i) = cost_sect2(w, A(tt,i), A_en(tt,i), c_en(2), A_ef(tt,i), t_CO2_I2)
        #      c2(1,j) = sum_tt_i [C(tt,i) * g[...] / n_mach]
        self.unit_cost = self.machines.unit_cost_from_wage(wage, elec_price, carbon_tax_s2)

        # --- Recompute all-machine mean energy efficiency (A2_en → A2e_en base) ---
        # C++: A2_en(j) = sum_tt_i [A_en(tt,i) * g[...] / n_mach] (flag_clim_tech==1)
        # COSTPROD will override this with the USED-machine mean; this sets the
        # trivial-branch value (Qd >= K → A2e_en = A2_en).
        self.effective_energy_efficiency = self.machines.effective_energy_need()

        # --- Update markup based on lagged market-share change ---
        # C++: if f2(3,j)>0: mu2(1,j)=mu2(2,j)*(1+deltami2*(f2(2,j)-f2(3,j))/f2(3,j))
        if self.market_share_prev_prev > 0:
            self.markup = self.markup * (
                1.0
                + deltami2
                * (self.market_share_prev - self.market_share_prev_prev)
                / self.market_share_prev_prev
            )

        # --- Update price ---
        # C++: p2(1,j) = (1+mu2(1,j)) * c2(1,j)
        self.price = (1.0 + self.markup) * self.unit_cost
        if self.price < pmin:
            self.price = pmin
            if self.price_prev < pmin:
                self.price_prev = pmin

    # ------------------------------------------------------------------
    # Brochure matching (BROCHURE)
    # ------------------------------------------------------------------

    def choose_best_supplier(
        self,
        capital_firms: list,
        wage: float,
        elec_price: float = 0.0,
        carbon_tax_s2: float = 0.0,
        payback: float = 200.0,
    ) -> None:
        """Select the best capital-good supplier from brochure senders (BROCHURE phase 3).

        C++ dsk_main.cpp BROCHURE() lines 2666-2713:
        - flag_clim_tech==0 (KS15): argmin p1*(w/A1) — b cancels
        - flag_clim_tech==1 (DSK17, baseline): argmin p1 + cost_sect2(w,A1,A1_en,c_en,...)*b

        Activates DSK17 comparison when elec_price > 0.
        Updates preferred_supplier_idx and resets brochure_senders_idxs to {winner}.

        Parameters
        ----------
        elec_price : previous-period electricity price c_en(2); >0 activates DSK17 mode
        carbon_tax_s2 : t_CO2_I2 (0 in baseline)
        payback : b — payback threshold (200 in baseline); only used in DSK17 mode
        """
        from dsk.agents.firm_costs import cost_sect2 as _cost_sect2

        if not self.brochure_senders_idxs:
            return

        best_idx = self.preferred_supplier_idx

        # Guard: if current preferred supplier is out of range, seed with any valid sender
        if best_idx < 0 or best_idx >= len(capital_firms):
            for idx in self.brochure_senders_idxs:
                if 0 <= idx < len(capital_firms):
                    best_idx = idx
                    break

        def _supplier_cost(firm) -> float:
            if firm.machine_labour_prod <= 0:
                return float("inf")
            if elec_price > 0.0 or carbon_tax_s2 > 0.0:
                # DSK17: p1 + cost_sect2(w, A1, A1_en, c_en, A1_ef, t_CO2_I2) * b
                running = _cost_sect2(
                    wage,
                    firm.machine_labour_prod,
                    firm.current_technology.energy_efficiency,
                    elec_price,
                    firm.current_technology.env_cleanliness,
                    carbon_tax_s2,
                )
                return firm.price + running * payback
            else:
                # KS15: p1 * (w/A1)  [b cancels from both sides of the comparison]
                return firm.price * (wage / firm.machine_labour_prod)

        best_cost = _supplier_cost(capital_firms[best_idx])

        for sender_idx in self.brochure_senders_idxs:
            firm = capital_firms[sender_idx]
            cost = _supplier_cost(firm)
            if cost < best_cost:
                best_cost = cost
                best_idx = sender_idx

        self.preferred_supplier_idx = best_idx
        self.brochure_senders_idxs = {best_idx}

    # ------------------------------------------------------------------
    # INVEST sub-routines (Task 1.7)
    # ------------------------------------------------------------------

    def form_demand_expectation(self, t: int) -> None:
        """Set expected demand De(1,j) for this period (EXPECT, flagEXP=0 baseline).

        C++ dsk_main.cpp EXPECT() lines 2959-2964 (flagEXP=0 branch):
          De(1,j) = D2(2,j)   [myopic: expect last period's demand]
          if De(1,j) <= 0: De(1,j) = 1

        Parameters
        ----------
        t : int
            Current simulation period (1-indexed, matching C++).
        """
        De = self.demand_prev  # D2(2,j) = previous period's actual demand
        if De <= 0.0:
            De = 1.0
        self.expected_demand = De

    def _cpp_round(self, x: float) -> float:
        """C++ ROUND: floor if remainder <= 0.5, ceil otherwise (not banker's rounding)."""
        return math.floor(x) if (x - math.floor(x)) <= 0.5 else math.ceil(x)

    def compute_desired_production_and_eid(
        self,
        gparams: "GlobalParameters",
        t: int,
    ) -> None:
        """Compute desired production Qd, desired capital Kd, and desired expansion EId.

        Called once per firm after form_demand_expectation(), before plan_substitution_investment().
        Ports the per-j body of INVEST() in dsk_main.cpp lines 2783-2829.

        Sets self.desired_production, self.desired_capital, self.desired_expansion_investment.
        """
        theta = gparams.inventory_target_fraction   # = 0.1
        u = gparams.capacity_utilization            # = 0.75
        alfa = gparams.investment_trigger           # = 0.0
        alfasup = gparams.investment_trigger_upper  # = 0.5
        dim_mach = gparams.machine_size_units       # = 40.0

        De = self.expected_demand
        Ne = De * theta                             # desired inventory stock
        # N(2,j) in C++ = previous period's inventory = self.inventory at this point
        Qd = De + Ne - self.inventory
        if Qd < 0.0:
            Qd = 0.0

        # Desired capital (Kd)
        if t == 1:
            Kd = Qd
        else:
            Kd = Qd / u if u > 0.0 else Qd

        K = self.capital_stock

        # Investment trigger and upper cap (rounded to dim_mach multiples)
        Ktrig = self._cpp_round(K * (1.0 + alfa) / dim_mach) * dim_mach
        Ktop  = self._cpp_round(K * (1.0 + alfasup) / dim_mach) * dim_mach

        # Desired expansion investment EId(j)
        if Kd >= Ktrig:
            if alfa > 0.0:
                EId = Ktrig - K
            elif alfasup > 0.0 and Kd > Ktop:
                EId = Ktop - K
            else:
                EId = math.floor((Kd - K) / dim_mach) * dim_mach
        else:
            EId = 0.0

        # Production cannot exceed current capital stock
        if Qd > K:
            Qd = K

        self.desired_production = Qd
        self.desired_capital = Kd
        self.desired_expansion_investment = EId

    def plan_substitution_investment(
        self,
        capital_firms: list,
        wage: float,
        gparams: "GlobalParameters",
    ) -> None:
        """Identify machines to replace (SCRAPPING) and set desired substitution investment SId.

        C++ dsk_main.cpp SCRAPPING() lines 3302-3368 (flag_clim_tech==0 path).

        Two reasons to scrap machine slot (vintage_key, supplier_idx):
        1. Payback rule: replacing it with the potential new supplier's machine has a payback
           period <= b (payback_threshold). Condition: A(tt,i) < A1(indforn) so improvement exists.
        2. Age limit: machine age > agemax.

        Sets self.desired_substitution_investment and self.scrap_candidates.

        Parameters
        ----------
        capital_firms : list of CapitalGoodFirm
            Full list of capital-good firms (0-indexed).
        wage : float
            Current wage w(2).
        gparams : GlobalParameters
        """
        dim_mach = gparams.machine_size_units
        b = gparams.payback_threshold
        agemax = gparams.machine_max_age

        indforn = self.preferred_supplier_idx
        if indforn < 0 or indforn >= len(capital_firms):
            self.desired_substitution_investment = 0.0
            self.scrap_candidates = []
            return

        supplier = capital_firms[indforn]
        A1_new = supplier.machine_labour_prod   # A1(indforn): productivity of potential new machine
        p1_new = supplier.price                 # p1(1,indforn): price of potential new machine

        SId = 0.0
        scrap_candidates = []

        for vk in self.machines.vintage_keys:
            row = self.machines.row_for(vk)
            if row is None:
                continue
            n_sup = self.machines._n_suppliers
            for s in range(n_sup):
                cnt = self.machines.count[row, s]
                if cnt <= 0.0:
                    continue

                A_old = self.machines.labour_productivity[row, s]
                age   = self.machines.age[row, s]

                scraped = False

                # --- Payback rule ---
                # Only consider if new machine is strictly more productive
                if A_old < A1_new and wage > 0.0 and A_old > 0.0 and A1_new > 0.0:
                    cost_saving = wage / A_old - wage / A1_new   # = w/A_old - w/A1_new
                    if cost_saving > 0.0:
                        # payback = p1(indforn) / (w/A_old - w/A1_new)
                        payback = p1_new / cost_saving
                        if payback <= b:
                            scraped = True

                # --- Age scrapping (only if not already marked for payback scrapping) ---
                if not scraped and age > agemax:
                    scraped = True

                if scraped:
                    scrap_candidates.append((vk, s, cnt))
                    SId += dim_mach * cnt

        self.desired_substitution_investment = SId
        self.scrap_candidates = scrap_candidates

    def compute_effective_productivity_and_cost(
        self,
        wage: float,
        gparams: "GlobalParameters",
        elec_price: float = 0.0,
        carbon_tax_s2: float = 0.0,
    ) -> None:
        """Compute effective productivity A2e and effective unit cost c2e for USED machines.

        C++ dsk_main.cpp COSTPROD() lines 3373-3531:
        - flag_clim_tech==0 (KS15): max labour-productivity selection
        - flag_clim_tech==1 (DSK17, baseline): min cost_sect2 selection; also updates
          A2e_en (effective_energy_efficiency) and A2e_ef (effective_env_filthiness) for
          used machines.

        When Qd >= K (trivial): uses all machines; effective_* already set in receive_machines.

        Parameters
        ----------
        wage : current wage w(2)
        gparams : global parameters
        elec_price : previous-period electricity price c_en(2); >0 activates DSK17 selection
        carbon_tax_s2 : t_CO2_I2 (0 in baseline)
        """
        from dsk.agents.firm_costs import cost_sect2 as _cost_sect2

        Qd = self.desired_production
        K  = self.capital_stock
        dim_mach = gparams.machine_size_units

        # Trivial branch: use all machines (A2e = A2, c2e = c2, A2e_en = A2_en)
        # effective_energy_efficiency was already set to A2_en in receive_machines.
        if Qd <= 0.0 or Qd >= K or self.n_machines <= 0.0:
            self.effective_labour_prod_used = self.effective_labour_prod
            self.effective_unit_cost = self.unit_cost
            return

        # COSTPROD: greedy selection of machines
        # nmachprod = ceil(Qd / dim_mach) — number of machines needed
        n_mach_needed = math.ceil(Qd / dim_mach)
        n_remaining = n_mach_needed

        # Collect all non-empty slots: (vintage_key, supplier_idx, count, lp, en, ef)
        slots: list[tuple[int, int, float, float, float, float]] = []
        for vk in self.machines.vintage_keys:
            row = self.machines.row_for(vk)
            if row is None:
                continue
            n_sup = self.machines._n_suppliers
            for s in range(n_sup):
                cnt = self.machines.count[row, s]
                lp  = self.machines.labour_productivity[row, s]
                en  = self.machines.energy_efficiency[row, s]
                ef  = self.machines.env_cleanliness[row, s]
                if cnt > 0.0 and lp > 0.0:
                    slots.append((vk, s, cnt, lp, en, ef))

        if elec_price > 0.0 or carbon_tax_s2 > 0.0:
            # DSK17: min unit-cost selection — C++ COSTPROD flag_clim_tech==1
            # Sort ascending by cost_sect2 (cheapest machines used first)
            slots.sort(
                key=lambda x: _cost_sect2(wage, x[3], x[4], elec_price, x[5], carbon_tax_s2)
            )
        else:
            # KS15: max labour-productivity selection (descending)
            slots.sort(key=lambda x: x[3], reverse=True)

        inv_A2e = 0.0   # accumulates 1/A2e = sum( (1/A) * g_used / nmachprod )
        c2e_acc = 0.0   # accumulates c2e  = sum( C(tt,i) * g_used / nmachprod )
        en_acc  = 0.0   # accumulates A2e_en = sum( A_en * g_used / nmachprod )
        ef_acc  = 0.0   # accumulates A2e_ef = sum( A_ef * g_used / nmachprod )

        for _vk, _s, cnt, lp, en, ef in slots:
            if n_remaining <= 0:
                break
            use = min(cnt, n_remaining)
            weight = use / n_mach_needed
            inv_A2e += weight / lp
            c2e_acc += weight * _cost_sect2(wage, lp, en, elec_price, ef, carbon_tax_s2)
            en_acc  += weight * en
            ef_acc  += weight * ef
            n_remaining -= use

        if inv_A2e > 0.0:
            self.effective_labour_prod_used = 1.0 / inv_A2e
        else:
            self.effective_labour_prod_used = self.effective_labour_prod
        self.effective_unit_cost = c2e_acc
        # Update used-machine energy and env-filthiness means (A2e_en, A2e_ef)
        self.effective_energy_efficiency = en_acc
        self.effective_env_filthiness = ef_acc

    # ------------------------------------------------------------------
    # CANCMACH — actual machine scrapping (Task 1.9)
    # ------------------------------------------------------------------

    def execute_scrapping(self, wage: float, gparams: "GlobalParameters") -> None:
        """Remove scrapped machines from MachineStock (CANCMACH).

        Ports C++ dsk_main.cpp CANCMACH() lines 4852-4927.
        Called when desired_substitution_investment > 0 after ALLOCATECREDIT.

        Priority order (two-pass):
        1. Overaged machines first (age > agemax), iterating scrap_candidates as built.
        2. Remaining budget by highest production cost (wage / labour_productivity).

        scrapmax = desired_substitution_investment / dim_mach is the credit-confirmed
        machine budget — may be less than the original SId from SCRAPPING.

        Parameters
        ----------
        wage : float
            Current wage w(2), used to compute production costs in the second pass.
        gparams : GlobalParameters
        """
        if self.machines is None:
            return

        dim_mach = gparams.machine_size_units
        agemax = gparams.machine_max_age

        scrapmax = self.desired_substitution_investment / dim_mach
        if scrapmax <= 0.0:
            return

        # --- First pass: overaged machines from scrap_candidates ---
        # C++: for i, for tt: if g_pb[tt][i][j]>0 and age>agemax: scrap
        for (vk, s, _) in self.scrap_candidates:
            if scrapmax <= 0.0:
                break
            row = self.machines.row_for(vk)
            if row is None:
                continue
            if self.machines.age[row, s] > agemax:
                avail = self.machines.count[row, s]
                if avail <= 0.0:
                    continue
                remove = min(avail, scrapmax)
                self.machines.count[row, s] -= remove
                scrapmax -= remove

        if scrapmax <= 0.0:
            return

        # --- Second pass: highest production cost first ---
        # C++: while scrapmax > 0: cmax=max cost slot; scrap min(g_pb, scrapmax)
        remaining = []
        for (vk, s, _) in self.scrap_candidates:
            row = self.machines.row_for(vk)
            if row is None:
                continue
            cnt = self.machines.count[row, s]
            if cnt <= 0.0:
                continue
            lp = self.machines.labour_productivity[row, s]
            cost = (wage / lp) if lp > 0.0 else float("inf")
            remaining.append((vk, s, cost))

        remaining.sort(key=lambda x: x[2], reverse=True)

        for (vk, s, _cost) in remaining:
            if scrapmax <= 0.0:
                break
            row = self.machines.row_for(vk)
            if row is None:
                continue
            cnt = self.machines.count[row, s]
            if cnt <= 0.0:
                continue
            remove = min(cnt, scrapmax)
            self.machines.count[row, s] -= remove
            scrapmax -= remove

    # ------------------------------------------------------------------
    # PROFIT (sector 2)  — post-ALLOC per-firm loop
    # ------------------------------------------------------------------

    def realise_profit(
        self,
        aliq: float,
        lending_rate: float,
        deposit_rate: float,
        repayment_share: float,
        gparams: "GlobalParameters",
    ) -> dict:
        """Compute sector-2 sales, profit, debt service, cash-flow, inventory (PROFIT).

        Ports C++ dsk_main.cpp PROFIT() sector-2 main loop (lines 5302-5424) for
        flag_clim_tech==0, flagENTRY<2, flag_interest_rate==0, flagdieW=1 baseline.
        Called once per firm AFTER ALLOC has set self.demand (D2(1,j)).

        Sequence per firm:
          if D2 >= Q2 + N(2,j):      S2 = p2*(Q2+N(2,j));  size2 = Q2+N
          else:                       S2 = p2*D2;           size2 = D2
          mol(j) = S2 - c2e*Q2
          DebtInterests2 = lending_rate * Deb2(1,j)
          Pi2 = mol - DebtInterests2 + deposit_rate*W2(2,j)       [Deb >= 0]
          if Pi2 > 0: div2 = d2*Pi2; tax = aliq*Pi2; CF -= aliq*Pi2
          N(1,j)  = max(0, Q2 + N(2,j) - D2);  Nm = N*p2
          dN      = N(1,j) - N(2,j); dNm = Nm(1,j) - Nm(2,j)
          CF     += Pi2 + c2e*Q2 - repayment_share*Deb2(1,j) - div2
          if baddebt==0: DebtRemittances = repayment_share*Deb2; Deb -= remittance
          if CF<0 and W2 >= -CF:  W2 += CF                (covered case)
          else                  : W2 += CF                (positive CF or overcoverage)
        Note: the "CF<0 and W2 < -CF" death case is handled in PROFIT's second loop
        (see Nation.realise_profits_and_taxes); this method records cash_flow on
        the firm so the second pass can check it.

        Returns
        -------
        dict
          keys = sales, profit, dividend, tax, debt_interest, debt_remittance,
                 inventory_change_real, inventory_change_nominal, mol, cash_flow,
                 actual_consumption_real (= size2 in the C++ — units consumed)
        """
        d2 = gparams.dividend_rate_s2  # = 0.0 baseline

        q2 = self.production
        n_prev = self.inventory                       # N(2,j) — opening inventory
        nm_prev = self.inventory_monetary             # Nm(2,j)
        p2 = self.price
        c2e = self.effective_unit_cost
        d2_real = self.demand                         # D2(1,j) — real demand assigned

        supply_available = q2 + n_prev

        if d2_real >= supply_available:
            # Rationed at supply side: firm sells everything it has
            actual_cons = supply_available
            self.sales = p2 * supply_available
        else:
            # Demand met in full: surplus carried as closing inventory
            actual_cons = d2_real
            self.sales = p2 * d2_real

        # Gross operating margin (mol)
        self.gross_operating_margin = self.sales - c2e * q2

        # Debt service (interest on outstanding debt)
        self.debt_interest = lending_rate * self.debt

        # Profit
        Pi2 = self.gross_operating_margin - self.debt_interest
        if self.debt >= 0.0:
            # C++ line 5346: bank pays interest on deposits when firm has no debt
            Pi2 += deposit_rate * self.net_worth_prev
        self.profit = Pi2

        # Initial cash-flow accumulator (taxes deducted below if profit positive)
        cash_flow = 0.0

        if Pi2 > 0.0:
            self.dividends = d2 * Pi2
            tax = aliq * Pi2
            cash_flow -= tax
        else:
            self.dividends = 0.0
            tax = 0.0

        # Closing inventory (with floor at 0 for the rationed case)
        n_new = supply_available - d2_real
        if n_new < 0.0:
            n_new = 0.0
        self.inventory = n_new
        self.inventory_monetary = n_new * p2
        inv_change_real = n_new - n_prev
        inv_change_nominal = self.inventory_monetary - nm_prev

        # Cash flow proper
        # C++ line 5381: CF += Pi2 + c2e*Q2 - repayment_share*Deb - div2
        cash_flow += Pi2 + c2e * q2 - repayment_share * self.debt - self.dividends

        # Debt repayment for surviving (non-baddebt) firms
        if self.bad_debt == 0.0:
            debt_remittance = repayment_share * self.debt
            self.debt -= debt_remittance
        else:
            debt_remittance = 0.0

        # Net-worth update (first-loop case; the second-loop death case is handled
        # in Nation.realise_profits_and_taxes, which may reverse this and write off
        # bad debt).
        if cash_flow < 0.0:
            if self.net_worth >= -cash_flow:
                self.net_worth += cash_flow
        else:
            self.net_worth += cash_flow

        # Persist cash_flow for the second pass (Nation must read it to detect
        # firms whose negative cash flow exceeded net worth)
        self.cash_flow = cash_flow
        self.debt_remittance = debt_remittance

        return {
            "sales": self.sales,
            "profit": Pi2,
            "dividend": self.dividends,
            "tax": tax,
            "debt_interest": self.debt_interest,
            "debt_remittance": debt_remittance,
            "inventory_change_real": inv_change_real,
            "inventory_change_nominal": inv_change_nominal,
            "mol": self.gross_operating_margin,
            "cash_flow": cash_flow,
            "actual_consumption_real": actual_cons,
        }

    def plan_investment_order(
        self,
        capital_firms: list,
        gparams: "GlobalParameters",
    ) -> None:
        """Apply prudential credit limits to investment plans; compute order size and cost (ORD).

        C++ dsk_main.cpp ORD() lines 3751-4031, for a single firm j.
        Called once per firm after all per-j INVEST computations are done.

        Implements:
        - Labour demand: Ld2(1,j) = Q2(1,j) / A2e(1,j) [using previous period's Q2]
        - Prudential limit (prestmax = phi2 * mol(j)); deduct production costs from NW
        - EI determination under flag_loantovalue==1 (baseline) or ==0
        - SI determination under flag_loantovalue==1 (baseline) or ==0
        - Cmach, CmachEI, CmachSI cost computation

        Energy axis (flag_clim_tech==1) and entrant capital-buy (flagENTRY>=2) branches
        are deferred to milestones 3 and 1.13 respectively.

        Sets self.potential_expansion_investment, self.potential_substitution_investment,
        self.potential_total_investment, machine_order_{total,expansion,substitution}_cost,
        self.labour_demand, and self.machine_order_supplier_idx.
        """
        dim_mach = gparams.machine_size_units
        phi2 = gparams.credit_max_for_investment        # = 2.0
        flag_ltv = gparams.loan_to_value_binding        # = 1 (baseline)
        flag_alloc = gparams.credit_allocation_rule     # = 0 (baseline: rank-based)

        # Reset outputs
        EIp = 0.0
        SIp = 0.0

        # --- Labour demand: based on PREVIOUS period's production / current effective A2e ---
        # C++ ORD line 3772: Ld2(1,j) = Q2(1,j)/A2e(1,j)
        # Q2(1,j) at ORD time = firm.production (last period's actual production)
        if not self.is_new_entrant:
            A2e = self.effective_labour_prod_used
            if A2e > 0.0:
                self.labour_demand = self.production / A2e
            # else: A2e should never be 0 if firm is alive; leave labour_demand unchanged
        else:
            self.labour_demand = 0.0

        # --- Prudential investment limit (prestmax = phi2 * mol) ---
        # C++ ORD lines 3795-3817
        prestmax = phi2 * self.gross_operating_margin
        if prestmax < 0.0:
            prestmax = 0.0

        # flagallocatecredit==1: can use remaining credit line
        if flag_alloc == 1:
            if self.credit_line_remaining > prestmax:
                prestmax = self.credit_line_remaining

        # --- Net worth after paying for production ---
        # C++ ORD line 3821: NW = NW - c2e(j)*Qd(j)
        NW = self.net_worth
        NW -= self.effective_unit_cost * self.desired_production
        if NW < 0.0:
            NW = 0.0

        # --- Supplier price ---
        indforn = self.preferred_supplier_idx
        if indforn < 0 or indforn >= len(capital_firms):
            # No valid supplier — no investment possible
            self.potential_expansion_investment = 0.0
            self.potential_substitution_investment = 0.0
            self.potential_total_investment = 0.0
            self.machine_order_total_cost = 0.0
            self.machine_order_expansion_cost = 0.0
            self.machine_order_substitution_cost = 0.0
            return

        p1 = capital_firms[indforn].price    # p1(1,indforn)
        self.machine_order_supplier_idx = indforn

        EId = self.desired_expansion_investment
        SId = self.desired_substitution_investment

        # --- EI determination ---
        # C++ ORD lines 3840-3909
        if flag_ltv == 0:
            # No prudential limit on credit
            EIp = EId
            cost_ei = (EId / dim_mach) * p1
            NW = max(0.0, NW - cost_ei)
        else:
            # flag_loantovalue==1 (baseline)
            cost_ei = (EId / dim_mach) * p1
            if cost_ei < NW:
                EIp = EId
                NW -= cost_ei
            elif (cost_ei - NW) <= prestmax:
                EIp = EId
                prestmax -= (cost_ei - NW)
                NW = 0.0
            else:
                EIp = math.floor((NW + prestmax) / p1) * dim_mach if NW > 0.0 else 0.0
                prestmax = 0.0
                NW = 0.0

        # --- SI determination ---
        # C++ ORD lines 3925-3961
        if flag_ltv == 0:
            SIp = SId
            cost_si = (SId / dim_mach) * p1
            NW = max(0.0, NW - cost_si)
        else:
            cost_si = (SId / dim_mach) * p1
            if cost_si < NW:
                SIp = SId
            elif (cost_si - NW) <= prestmax:
                SIp = SId
            else:
                SIp = math.floor((NW + prestmax) / p1) * dim_mach

        Ip = EIp + SIp

        # --- Investment costs (Cmach, CmachEI, CmachSI) ---
        # C++ ORD lines 3988-4009
        if Ip > 0.0:
            CmachEI = p1 * EIp / dim_mach
            CmachSI = p1 * SIp / dim_mach
            Cmach   = CmachEI + CmachSI
        else:
            CmachEI = CmachSI = Cmach = 0.0

        self.potential_expansion_investment   = EIp
        self.potential_substitution_investment = SIp
        self.potential_total_investment        = Ip
        self.machine_order_expansion_cost      = CmachEI
        self.machine_order_substitution_cost   = CmachSI
        self.machine_order_total_cost          = Cmach
