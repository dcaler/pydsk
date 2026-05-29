"""Sector-1 capital-good firm.

Mirrors C++ N1-indexed state vectors in dsk_globalvar.h:
A1[i], A1p[i], W1[i], Deb1[i], f1[i], p1[i], c1[i], RD[i], xin[i], Pat[i], etc.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional

import numpy as np

from dsk.agents.agent import Agent
from dsk.agents.technology import Technology

if TYPE_CHECKING:
    from dsk.nation import Nation
    from dsk.parameters.global_parameters import GlobalParameters


class CapitalGoodFirm(Agent):
    """Sector-1 firm: produces capital goods (machines) via R&D and sells to sector-2 firms."""

    def __init__(self, nation: "Nation", rng: np.random.Generator) -> None:
        super().__init__(nation)
        self.rng = rng

        # --- Technology ---
        # A1[i]: labour productivity of the machine this firm sells (when used in sector 2)
        self.machine_labour_prod: float = 1.0
        # A1p[2,i]: labour productivity of this firm's own production process
        self.process_labour_prod: float = 1.0
        self.process_labour_prod_prev: float = 1.0
        # Technology object representing what this firm currently sells (A1, and DSK energy axes)
        self.current_technology: Technology = Technology(labour_productivity=1.0)
        # tao[i]: machine vintage/generation counter (increments each time firm upgrades tech)
        self.vintage: int = 1

        # --- R&D and innovation ---
        # RD[2,i]: total R&D expenditure (current and previous period)
        self.rd_budget: float = 0.0
        self.rd_budget_prev: float = 0.0
        # RDin[i], RDim[i]: innovation and imitation sub-budgets
        self.rd_innovation_budget: float = 0.0
        self.rd_imitation_budget: float = 0.0
        # xin[i]: fraction of innovation R&D going to sector-1 own-process properties (vs sector-2 properties)
        self.rd_sector1_share: float = 0.07
        # Ld1rd[i]: R&D labour demand
        self.rd_labour_demand: float = 0.0

        # Inn1[i], Inn2[i], Imm[i]: binary flags for this period's events
        self.innovated_sector1: bool = False
        self.innovated_sector2: bool = False
        self.imitated: bool = False
        # Technology candidates — None when no event occurred this period
        self.innovation_candidate: Optional[Technology] = None
        self.imitation_candidate: Optional[Technology] = None

        # Pat[i]: remaining patent duration in periods
        self.patent_timer: float = 0.0

        # --- Market state ---
        # f1[2,i]: sector-1 market share
        self.market_share: float = 0.0
        self.market_share_prev: float = 0.0
        # p1[2,i]: price per machine unit
        self.price: float = 0.0
        self.price_prev: float = 0.0
        # c1[i]: unit cost to produce one machine
        self.unit_cost: float = 0.0
        # S1[2,i]: sales revenue
        self.sales: float = 0.0
        self.sales_prev: float = 0.0
        # D1[i]: total machine demand received from clients this period
        self.demand: float = 0.0
        # Q1[i]: machines produced this period
        self.production: float = 0.0

        # --- Financial state ---
        # W1[2,i]: net worth / liquid assets
        self.net_worth: float = 0.0
        self.net_worth_prev: float = 0.0
        # Deb1[2,i]: stock of outstanding debt
        self.debt: float = 0.0
        self.debt_prev: float = 0.0
        # Pi1[i]: profit this period
        self.profit: float = 0.0
        # div1[i]: dividends paid
        self.dividends: float = 0.0
        # DebtInterests1[i]: interest paid on debt
        self.debt_interest: float = 0.0
        # NetWorthToSales1[i]: used for credit rationing ranking
        self.net_worth_to_sales: float = 0.0

        # --- Credit ---
        # Debmax1[i]: maximum credit this firm may carry
        self.max_credit: float = 0.0
        # debres1[i]: remaining credit line after allocation
        self.credit_line_remaining: float = 0.0

        # --- Labour demand (production side) ---
        # Ld1[2,i]: labour used in machine production
        self.labour_demand: float = 0.0

        # --- Energy (sector-1 own-process properties, M3 Tasks 3.6–3.7) ---
        # A1p_en[i]: energy demand scale of this firm's own production process
        self.process_energy_need: float = 0.0
        # D1_en[i]: electricity demand this period (computed by aggregate_demand)
        self.elec_demand: float = 0.0
        # D1_ff[i]: fossil fuel demand this period
        self.fossil_fuel_demand: float = 0.0
        # A1p_ef[i]: process env filthiness (= 0 when allow_proc_emissions_s1=0)
        self.process_env_filthiness: float = 0.0
        # Emiss1[i], Emiss1FF[i], Emiss1EF[i]: per-firm emissions (EMISS_IND)
        self.emissions: float = 0.0
        self.emissions_fossil: float = 0.0
        self.emissions_process: float = 0.0

        # --- Client relationships ---
        # Replaces C++ Match(N2,N1) matrix: each firm owns its client list directly
        self.clients: list = []      # ConsumptionGoodFirm references receiving brochures
        self.num_clients: int = 0   # nclient[i]

        # --- Electrification mandate fine (M5, Task 5.4) ---
        # Per-unit fine paid by this firm due to insufficient electrification fraction.
        # C++ tp_elfrac accumulation: cost_sect1_with_fine - cost_sect1_without_fine.
        # Set in update_price_and_cost(); accumulated into government.total_electrification_fine
        # in Nation.realise_profits_and_taxes().
        self.elfrac_fine_per_unit: float = 0.0

        # --- Status ---
        self.is_alive: bool = True   # !die[i]

    def initialise_from_parameters(self, gparams: "GlobalParameters") -> None:
        """Set this firm to the C++ baseline initial values (pre-TECHANGEND).

        Mirrors INITIALIZE() in dsk_main.cpp for N1 sector-1 firms.
        All firms start identical at productivity A0. TECHANGEND() (Task 1.14)
        adds inter-firm dispersion via the first innovation/imitation round.

        C++ reference lines 1043-1711:
          A1=A0; A1p=A0; f1=1/N1r; W1=W10; Deb1=0; tao=1;
          c1=w0/(A0*a); p1=(1+mi1)*w0/(A0*a);
          S1=(I(2,1)/dim_mach * N2r/N1r) * p1; RD=nu*S1;
        """
        A0 = gparams.productivity_init              # = 1.0
        a = gparams.s1_productivity_scale           # = 0.1  (sector-1 labour-size scale)
        w0 = gparams.wage_init                      # = 1.0
        mi1 = gparams.s1_markup                     # = 0.04
        N1 = gparams.n1_capital_good_firms          # = 100
        N2 = gparams.n2_consumption_good_firms      # = 400
        dim_mach = gparams.machine_size_units       # = 40.0
        nu = gparams.rd_budget_fraction             # = 0.04
        xi = gparams.innovation_imitation_split     # = 0.5
        xin0 = gparams.innovation_sector1_share_initial  # = 0.07
        W10 = gparams.s1_net_worth_init             # = 1000.0

        # All firms start at the technology frontier A0 (C++: A1=A0; A1p=A0)
        self.machine_labour_prod = A0
        self.process_labour_prod = A0
        self.process_labour_prod_prev = A0
        # C++: A1p_el = A0_el = 0.3; A1_en = A0_en; A1_ef = A0_ef * flag_EF_sector1
        el0 = gparams.electrification_fraction_init_s1   # A0_el = 0.3
        a1_en = gparams.energy_need_init                 # A0_en
        a1_ef = gparams.env_filthiness_init * gparams.allow_proc_emissions_s1
        self.current_technology = Technology(
            labour_productivity=A0,
            energy_efficiency=a1_en,
            env_cleanliness=a1_ef,
            electrification_fraction=el0,
        )
        self.vintage = 1                            # tao=1

        # C++: A1p_en = A0_en * A0_en_sect1fac
        self.process_energy_need = gparams.energy_need_init * gparams.s1_energy_need_init_factor
        # C++: A1p_ef = A0_ef * flag_EF_sector1 (= 0 in baseline)
        self.process_env_filthiness = gparams.env_filthiness_init * gparams.allow_proc_emissions_s1

        # Unit cost and price (C++: c1=w0/(A0*a); p1=(1+mi1)*w0/(A0*a))
        self.unit_cost = w0 / (A0 * a)
        self.price = (1.0 + mi1) * self.unit_cost
        self.price_prev = self.price

        # Equal market shares across N1 firms (C++: f1=1/N1r)
        self.market_share = 1.0 / N1
        self.market_share_prev = self.market_share

        # Net worth and debt (C++: W1=W10; Deb1=0)
        self.net_worth = W10
        self.net_worth_prev = W10
        self.debt = 0.0
        self.debt_prev = 0.0

        # Initial sales: each sector-1 firm serves N2/N1 sector-2 firms, each buying 1 machine.
        # C++: S1 = (I(2,1)/dim_mach * N2r/N1r) * p1; with I=dim_mach => I/dim_mach=1
        clients_per_firm = float(N2) / float(N1)   # = 4.0
        self.sales = clients_per_firm * self.price   # = 4 * 10.4 = 41.6
        self.sales_prev = self.sales

        # R&D budget split between innovation and imitation (C++: RD=nu*S1; xi splits it)
        self.rd_budget = nu * self.sales
        self.rd_budget_prev = self.rd_budget
        self.rd_innovation_budget = xi * self.rd_budget
        self.rd_imitation_budget = (1.0 - xi) * self.rd_budget
        self.rd_sector1_share = xin0               # xin=xin0 initially

        # Patent timer starts at zero (C++: Pat zero-initialised)
        self.patent_timer = 0.0

        # Expected client count from uniform matching (actual refs set by sector init)
        self.num_clients = N2 // N1               # step = N2/N1 = 4
        self.clients = []

    # ------------------------------------------------------------------
    # Per-period update (called at start of MACH)
    # ------------------------------------------------------------------

    def update_price_and_cost(
        self,
        wage: float,
        gparams: "GlobalParameters",
        elec_price: float = 0.0,
    ) -> None:
        """Recompute unit cost c1 and price p1 (MACH, DSK17 baseline).

        C++ dsk_main.cpp MACH() DSK17 path (flag_clim_tech==1):
          d1_en = electdemand(A1p_el, A1p_en, elconv)
          d1_ff = ffueldemand(A1p_el, A1p_en, elconv)
          elfrac_diff = elfrac_reg_now - A1p_el  (= 0 pre-M5)
          c1(i) = cost_sect1(w, A1p*a, d1_en, c_en(2), d1_ff, pf, ff2em, A1p_ef, ...)
          p1(1,i) = (1+mi1) * c1(i)

        Parameters
        ----------
        wage : w(2) = current wage (Subwage=0 in baseline, so wage_net = wage)
        gparams : global parameters
        elec_price : c_en(2) — previous-period electricity price; 0 → labour cost only
        """
        from dsk.agents.electricity_producer import _electdemand, _ffueldemand
        from dsk.agents.firm_costs import cost_sect1

        a = gparams.s1_productivity_scale
        mi1 = gparams.s1_markup
        pmin = gparams.firm_price_floor
        rule = gparams.fuel_to_elec_rule
        elconv = gparams.fuel_to_electricity_equivalence
        fossil_price = self.nation.params.fossil_fuel_price
        ff2em = gparams.fuel_to_emissions_factor

        self.sales = 0.0  # S1(1,i)=0 — reset; PRODMACH will accumulate

        # Per-machine-unit energy demands from process technology characteristics
        elf = self.current_technology.electrification_fraction
        en  = self.process_energy_need
        eld = _electdemand(elf, en, elconv, rule)  # d1_en per unit of output
        ffd = _ffueldemand(elf, en, elconv, rule)  # d1_ff per unit of output

        proc_prod = self.process_labour_prod * a
        # t_CO2_I1: carbon tax rate for sector 1 (set by CarbonTax instrument)
        t_co2_s1 = self.nation.government.carbon_tax_rate_industry1

        # Electrification mandate fine (C++ CLIMATE_POLICY, elfrac_reg_now / elfrac_reg_fine)
        # elfdis = max(0, elfrac_reg_now - A1p_el); fine only if positive deficit.
        elfrac_now  = self.nation.elfrac_reg_now
        elfrac_fine = self.nation.elfrac_reg_fine
        elfrac_deficit = max(0.0, elfrac_now - elf) if elfrac_now > 0.0 else 0.0

        self.unit_cost = cost_sect1(
            wage_net=wage,
            process_prod=proc_prod,
            elec_demand_per_unit=eld,
            elec_price=elec_price,
            fossil_demand_per_unit=ffd,
            fossil_price=fossil_price,
            ff2em=ff2em,
            env_filthiness=self.process_env_filthiness,
            carbon_tax_s1=t_co2_s1,
            elfrac_deficit=elfrac_deficit,
            fine=elfrac_fine,
            rule=rule,
        )

        # Track per-unit fine for government revenue accounting (C++ tp_elfrac).
        # C++ PROFIT: cost1_dummy1 (with fine) - cost1_dummy2 (without fine).
        if elfrac_deficit > 0.0 and elfrac_fine > 0.0:
            cost_no_fine = cost_sect1(
                wage_net=wage,
                process_prod=proc_prod,
                elec_demand_per_unit=eld,
                elec_price=elec_price,
                fossil_demand_per_unit=ffd,
                fossil_price=fossil_price,
                ff2em=ff2em,
                env_filthiness=self.process_env_filthiness,
                carbon_tax_s1=t_co2_s1,
                elfrac_deficit=0.0,
                fine=0.0,
                rule=rule,
            )
            self.elfrac_fine_per_unit = self.unit_cost - cost_no_fine
        else:
            self.elfrac_fine_per_unit = 0.0

        self.price = (1.0 + mi1) * self.unit_cost
        if self.price < pmin:
            self.price = pmin
            if self.price_prev < pmin:
                self.price_prev = pmin

        # Reset transient state
        self.innovated_sector1 = False
        self.innovated_sector2 = False
        self.imitated = False
        self.innovation_candidate = None
        self.imitation_candidate = None
        self.profit = 0.0
        self.production = 0.0
        self.demand = 0.0
        self.labour_demand = 0.0
        self.rd_labour_demand = 0.0
        self.is_alive = True

    # ------------------------------------------------------------------
    # PROFIT (sector 1)
    # ------------------------------------------------------------------

    def realise_profit(self, aliq: float, gparams: "GlobalParameters") -> dict:
        """Compute sector-1 profit, pay tax + dividend, update net worth (PROFIT).

        Ports C++ dsk_main.cpp PROFIT() sector-1 loop, lines 5090-5200, M1 path
        (no energy fine, no carbon tax, flagdieW=1 baseline).

        Sequence:
          Pi1 = S1 - c1*Q1 - RD
          if Pi1 > 0: div1 = d1*Pi1; tax1 = aliq*Pi1; W1 -= tax1
          W1 += Pi1 - div1
          if W1 <= 0 (flagdieW=1): W1 = 1; mark died
          if W1 <= 0 still: W1 += 0.01  (residual safety, matches C++)

        Returns
        -------
        dict with keys: profit, dividend, tax, died (bool), net_worth (post-update)
        """
        d1 = gparams.dividend_rate_s1  # = 0.0 baseline

        Pi1 = self.sales - self.unit_cost * self.production - self.rd_budget
        self.profit = Pi1

        if Pi1 > 0.0:
            self.dividends = d1 * Pi1
            tax = aliq * Pi1
            self.net_worth -= tax
        else:
            self.dividends = 0.0
            tax = 0.0

        # W1 += Pi1 - div1  (matches C++ line 5124: W1+=Pi1-div1; tax was already deducted)
        self.net_worth += Pi1 - self.dividends

        died = False
        # flagdieW = 1 baseline (s1_firms_persist_with_negative_w): W1 set to 1 if non-positive
        if self.net_worth <= 0.0:
            self.net_worth = 1.0
            died = True

        # C++ line 5188: residual safety pad if W1 still ≤ 0 after the rule (defensive)
        if self.net_worth <= 0.0:
            self.net_worth += 0.01

        return {
            "profit": Pi1,
            "dividend": self.dividends,
            "tax": tax,
            "died": died,
            "net_worth": self.net_worth,
        }

    # ------------------------------------------------------------------
    # Brochure sending (BROCHURE)
    # ------------------------------------------------------------------

    def distribute_brochures(
        self,
        firm_idx: int,
        consumption_firms: list,
        gparams: "GlobalParameters",
        rng: np.random.Generator,
    ) -> None:
        """Send ROUND(nclient * Gamma) new brochures to random consumption-good firms.

        C++ dsk_main.cpp BROCHURE() lines 2627-2653:
          nclient(i) = #{j : Match(j,i)==1}
          newbroch = ROUND(nclient(i) * Gamma); if 0 → 1
          if f1(2,i) > f1max: newbroch = 0   (anti-monopoly cap)
          for newbroch times: rni = random j; Match(rni,i) = 1

        Parameters
        ----------
        firm_idx
            0-indexed position of this firm in the capital-good sector list.
        consumption_firms
            Ordered list of all ConsumptionGoodFirm in this nation.
        gparams
            GlobalParameters for brochure_growth_factor and s1_antitrust_cap.
        rng
            Nation-level numpy.random.Generator.
        """
        Gamma = gparams.brochure_growth_factor   # = 0.5
        f1max = gparams.s1_antitrust_cap         # = 1.0 (effectively off)
        N2 = len(consumption_firms)

        # Count current clients: #{j with firm_idx in j.brochure_senders_idxs}
        # C++: for j: nclient(i) += Match(j,i)
        nclient = sum(1 for f in consumption_firms if firm_idx in f.brochure_senders_idxs)

        # New brochures = ROUND(nclient * Gamma); minimum 1
        newbroch = int(round(nclient * Gamma))
        if newbroch == 0:
            newbroch = 1

        # Anti-monopoly: if previous-period market share > cap, no new brochures
        # C++: if f1(2,i) > f1max: newbroch = 0
        if self.market_share_prev > f1max:
            newbroch = 0

        # Send brochures to newbroch randomly chosen consumption firms (duplicates OK)
        for _ in range(newbroch):
            rni = int(rng.integers(0, N2))
            consumption_firms[rni].brochure_senders_idxs.add(firm_idx)

    # ------------------------------------------------------------------
    # TECHANGEND (Task 1.14) — Schumpeterian R&D for labour productivity
    # ------------------------------------------------------------------

    _TECH_SENTINEL = 1e-5  # C++ "no innovation candidate" sentinel value

    def advance_technology(
        self,
        *,
        wage: float,
        A1top: float,
        A1ptop: float,
        all_firms: list,
        gparams: "GlobalParameters",
        elec_price: float = 0.0,
    ) -> None:
        """Run TECHANGEND for this firm (labour-only, M1 path).

        Ports the labour-productivity portion of C++ dsk_main.cpp TECHANGEND()
        lines 7132-7858 (the flag_clim_tech==1 endogenous-frontier path).
        Energy axes (A1_en, A1p_en, A1_ef, A1p_ef, A1p_el) are deferred to M3.

        Sequence:
          1. Update RD budget: RD(1,i) = nu * S1(1,i); fall back to previous RD
             when sales are zero (C++ lines 7220-7228).
          2. Labour units of R&D: Ld1rd = RD / w.
          3. Split into innovation pool (× xi) and imitation pool (× 1-xi);
             real-vs-nominal R&D mode (flagRD=1 baseline) splits the LABOUR units.
          4. Innovation Bernoulli: p = (1 - exp(-o12 * RDin)) * probinim.
          5. Imitation Bernoulli:  p = (1 - exp(-o2  * RDim)) * probinim.
          6. On Inn success: A1pinn = A1p * (1 + Beta(b_a1,b_b1) rescaled to
             (uu1_ap,uu2_ap)); A1inn analogous on (uu1_a, uu2_a).
          7. On Imm success: pick a target with probability ∝ 1/Td where
             Td is the norm-based labour-only technological distance
             (flag_techdist=1, energy terms dropped for M1).
          8. Lifetime-cost decision: candidate with min (1+mi1)*c1 + b*c2
             replaces current technology (imitation evaluated first, then
             innovation may override).

        elec_price : c_en(1) — current-period electricity price; 0 → labour only.
        """
        from dsk.agents.electricity_producer import _electdemand, _ffueldemand
        from dsk.agents.firm_costs import cost_sect1, cost_sect2
        # --- Parameter look-ups (named per Appendix A of PORT_PLAN_v3) ---
        nu        = gparams.rd_budget_fraction              # C++ nu      (0.04)
        xi        = gparams.innovation_imitation_split      # C++ xi      (0.5)
        o12       = gparams.rd_productivity_labour          # C++ o12     (0.15)
        o2        = gparams.rd_productivity_imitation       # C++ o2      (0.3)
        probinim  = gparams.innov_imit_probability_scale    # C++ probinim (1.0)
        flag_realrd = gparams.rd_real_vs_nominal            # C++ flagRD  (1)
        a         = gparams.s1_productivity_scale           # C++ a       (0.1)
        mi1       = gparams.s1_markup                       # C++ mi1     (0.04)
        b         = gparams.payback_threshold               # C++ b       (200)
        uu1_a     = gparams.labour_prod_s2_innov_lower      # C++ uu1_a   (-0.13)
        uu2_a     = gparams.labour_prod_s2_innov_upper      # C++ uu2_a   (0.13)
        uu1_ap    = gparams.labour_prod_s1_innov_lower      # C++ uu1_ap  (-0.13)
        uu2_ap    = gparams.labour_prod_s1_innov_upper      # C++ uu2_ap  (0.13)
        b_a1      = gparams.beta_innov_alpha                # C++ b_a1    (3.0)
        b_b1      = gparams.beta_innov_beta                 # C++ b_b1    (3.0)
        sentinel  = self._TECH_SENTINEL

        # --- Reset transient flags ---
        self.innovated_sector1 = False
        self.innovated_sector2 = False
        self.imitated = False
        self.innovation_candidate = None
        self.imitation_candidate = None

        # --- 1. Update R&D budget ---
        # C++ 7220-7228: RD(1,i) = nu * S1(1,i); fallback to RD(2,i) if no sales.
        # At this point self.rd_budget still holds the value PROFIT just used
        # (= C++ RD(1,i) before this period's TECHANGEND), so saving it as
        # rd_budget_prev makes it the analogue of C++ RD(2,i) for the fallback.
        self.rd_budget_prev = self.rd_budget
        if self.sales > 0.0:
            self.rd_budget = nu * self.sales
        else:
            self.rd_budget = self.rd_budget_prev

        # --- 2. Labour units of R&D ---
        if wage > 0.0:
            self.rd_labour_demand = self.rd_budget / wage
        else:
            self.rd_labour_demand = 0.0

        # --- 3. Split into innovation/imitation pools ---
        # C++ 7242-7255: nominal vs. real-R&D modes. Baseline flagRD=1 (real).
        # In M1/M3 we skip the energy-axis innovation (xin partition), so the
        # whole innovation pool goes to labour properties (RDin2 = RDin).
        # This matches the C++ spinup override at lines 7260-7265.
        if flag_realrd == 0:
            rd_inn_total = self.rd_budget * xi
            rd_imm       = self.rd_budget * (1.0 - xi)
        else:
            rd_inn_total = self.rd_labour_demand * xi
            rd_imm       = self.rd_labour_demand * (1.0 - xi)

        # Emergency R&D split (C++ 7280-7282): when a firm is below the EXPECTED
        # electrification mandate, shift a fraction from labour to energy innovation.
        # RDin1 (energy) = 0.2 * RDin; RDin2 (labour) = 0.8 * RDin.
        # Energy-axis innovation is not yet ported (M3), so the energy portion is
        # unused — but the labour portion is correctly reduced, which lowers the
        # innovation Bernoulli probability when the firm lags on electrification.
        elfrac_reg_exp  = self.nation.elfrac_reg_exp
        elfrac_reg_fine = self.nation.elfrac_reg_fine
        elf_current     = self.current_technology.electrification_fraction
        if elfrac_reg_exp > elf_current:
            rd_inn_labour = rd_inn_total * 0.8  # C++ RDin2 = RDin * 0.8
        else:
            rd_inn_labour = rd_inn_total  # Normal: all goes to labour (no energy axis yet)

        self.rd_innovation_budget = rd_inn_total
        self.rd_imitation_budget  = rd_imm

        # --- 4. Innovation Bernoulli (labour properties only) ---
        # C++ 7276: parber = (1 - exp(-o12 * RDin2(i))) * probinim
        parber_inn = (1.0 - math.exp(-o12 * rd_inn_labour)) * probinim
        parber_inn = max(0.0, min(1.0, parber_inn))
        inn2 = bool(self.rng.binomial(1, parber_inn)) if parber_inn > 0.0 else False
        self.innovated_sector2 = inn2

        # --- 5. Imitation Bernoulli ---
        # C++ 7289: parber = (1 - exp(-o2 * RDim(i))) * probinim
        parber_imm = (1.0 - math.exp(-o2 * rd_imm)) * probinim
        parber_imm = max(0.0, min(1.0, parber_imm))
        imm = bool(self.rng.binomial(1, parber_imm)) if parber_imm > 0.0 else False
        self.imitated = imm

        # --- 6. Innovation candidate (labour productivity only) ---
        # C++ 7418-7425: A1pinn(i) = A1p(1,i) * (1 + rnd) where rnd is Beta(b_a1,b_b1)
        # rescaled onto (uu1_ap, uu2_ap); A1inn(i) analogous on (uu1_a, uu2_a).
        if inn2:
            rnd_ap = float(self.rng.beta(b_a1, b_b1))
            rnd_ap = uu1_ap + rnd_ap * (uu2_ap - uu1_ap)
            a1p_inn = self.process_labour_prod * (1.0 + rnd_ap)

            rnd_a = float(self.rng.beta(b_a1, b_b1))
            rnd_a = uu1_a + rnd_a * (uu2_a - uu1_a)
            a1_inn = self.machine_labour_prod * (1.0 + rnd_a)
        else:
            a1p_inn = sentinel
            a1_inn = sentinel

        # --- 7. Imitation target selection (Td norm-based, labour-only) ---
        # C++ 7510-7546 (flag_techdist=1 branch with energy terms dropped):
        # Td[ii]^2 = (A1(ii)-A1(i))^2 / A1top^2 + (A1p(1,ii)-A1p(1,i))^2 / A1ptop^2
        # Probability of selection ∝ 1/Td. Patented firms (Pat(ii)>0) are skipped.
        a1_imm = sentinel
        a1p_imm = sentinel
        if imm and len(all_firms) > 0:
            A1top_eps  = max(A1top, 1e-6)
            A1ptop_eps = max(A1ptop, 1e-6)
            inv_td = np.zeros(len(all_firms))
            for ii, other in enumerate(all_firms):
                dA1 = other.machine_labour_prod - self.machine_labour_prod
                dA1p = other.process_labour_prod - self.process_labour_prod
                td_sq = (dA1 * dA1) / (A1top_eps * A1top_eps) \
                      + (dA1p * dA1p) / (A1ptop_eps * A1ptop_eps)
                td = math.sqrt(td_sq)
                inv_td[ii] = 1.0 / td if td > 0.0 else 0.0

            Tdtot = float(inv_td.sum())
            if Tdtot > 0.0:
                # Cumulative distribution over firms; draw uniform; pick the
                # bucket containing the draw. Skip firms with an active patent.
                cumprob = np.cumsum(inv_td) / Tdtot
                rnd = float(self.rng.uniform(0.0, 1.0))
                prev = 0.0
                for ii, other in enumerate(all_firms):
                    c = float(cumprob[ii])
                    if rnd > prev and rnd <= c:
                        if other.patent_timer == 0:
                            a1_imm = other.machine_labour_prod
                            a1p_imm = other.process_labour_prod
                        break
                    prev = c

        # --- 8. Lifetime-cost decision ---
        # C++ 7613-7702: cost = (1+mi1)*c1 + b*c2
        # DSK17 (elec_price > 0): c1 = cost_sect1(w, a1p*a, eld, c_en, ...)
        #                          c2 = cost_sect2(w, a1, A1_en, c_en, ...)
        # KS15 (elec_price == 0): c1 = w/(a1p*a), c2 = w/a1
        # Energy R&D not yet ported → candidates inherit current energy axes.
        # Electrification mandate: use elfrac_reg_exp (expected, not current) so
        # firms plan ahead. elfrac_diff = elfrac_reg_exp - candidate_el_frac.
        _elf    = self.current_technology.electrification_fraction
        _en     = self.process_energy_need
        _rule   = gparams.fuel_to_elec_rule
        _elconv = gparams.fuel_to_electricity_equivalence
        _pf     = self.nation.params.fossil_fuel_price
        _ff2em  = gparams.fuel_to_emissions_factor
        _eld    = _electdemand(_elf, _en, _elconv, _rule)
        _ffd    = _ffueldemand(_elf, _en, _elconv, _rule)
        _a1_en  = self.current_technology.energy_efficiency
        _a1_ef  = self.current_technology.env_cleanliness
        _t_co2  = self.nation.government.carbon_tax_rate_industry1

        def _lifetime(a1p_val: float, a1_val: float, el_frac: float = _elf) -> float:
            if a1p_val <= 0.0 or a1_val <= 0.0:
                return math.inf
            # elfrac_diff1 = elfrac_reg_exp - el_frac (C++ lines 7523, 7628)
            elfrac_def = max(0.0, elfrac_reg_exp - el_frac) if elfrac_reg_exp > 0.0 else 0.0
            if elec_price > 0.0:
                c1 = cost_sect1(
                    wage_net=wage,
                    process_prod=a1p_val * a,
                    elec_demand_per_unit=_eld,
                    elec_price=elec_price,
                    fossil_demand_per_unit=_ffd,
                    fossil_price=_pf,
                    ff2em=_ff2em,
                    env_filthiness=self.process_env_filthiness,
                    carbon_tax_s1=_t_co2,
                    elfrac_deficit=elfrac_def,
                    fine=elfrac_reg_fine,
                    rule=_rule,
                )
                c2 = cost_sect2(wage, a1_val, _a1_en, elec_price, _a1_ef, _t_co2)
                return (1.0 + mi1) * c1 + b * c2
            return (1.0 + mi1) * wage / (a1p_val * a) + b * wage / a1_val

        cost_current = _lifetime(self.process_labour_prod, self.machine_labour_prod)
        cost_imm = _lifetime(a1p_imm, a1_imm) if imm else math.inf
        cost_inn = _lifetime(a1p_inn, a1_inn) if inn2 else math.inf

        if imm and cost_imm < cost_current:
            self.machine_labour_prod = a1_imm
            self.process_labour_prod = a1p_imm
            # M1 baseline: flagPAT=0; no patent timer to reset.

        cost_after_imm = _lifetime(self.process_labour_prod, self.machine_labour_prod)
        if inn2 and cost_inn < cost_after_imm:
            self.vintage += 1
            self.machine_labour_prod = a1_inn
            self.process_labour_prod = a1p_inn

        # --- 9. Refresh current technology and diagnostics ---
        prev_tech = self.current_technology
        self.current_technology = Technology(
            labour_productivity=self.machine_labour_prod,
            energy_efficiency=prev_tech.energy_efficiency,
            env_cleanliness=prev_tech.env_cleanliness,
            electrification_fraction=prev_tech.electrification_fraction,
        )
        if inn2:
            self.innovation_candidate = Technology(labour_productivity=a1_inn)
        if imm:
            self.imitation_candidate = Technology(labour_productivity=a1_imm)
