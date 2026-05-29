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
        A1_en_top: float = 0.0,
        A1p_en_top: float = 0.0,
        A1_ef_top: float = 0.0,
        A1p_ef_top: float = 0.0,
        A1p_el_top: float = 0.0,
        elec_price: float = 0.0,
        current_t: int = 1,
    ) -> None:
        """Run TECHANGEND for this firm (FULL path — labour + energy axes).

        Ports C++ dsk_main.cpp TECHANGEND() lines 7155-7823 (the
        flag_clim_tech==1 endogenous-frontier path), Task 5.7.1: in addition to
        the labour-productivity axes (A1, A1p) this now advances the five energy
        axes — machine energy efficiency A1_en, process energy need A1p_en,
        machine env filthiness A1_ef, process env filthiness A1p_ef, and
        electrification fraction A1p_el.

        Axis → Python state map:
          A1     = self.machine_labour_prod                 A1p   = self.process_labour_prod
          A1_en  = current_technology.energy_efficiency      A1p_en = self.process_energy_need
          A1_ef  = current_technology.env_cleanliness        A1p_ef = self.process_env_filthiness
          A1p_el = current_technology.electrification_fraction

        Sequence:
          1-2. RD budget + labour units (unchanged).
          3.   Split innovation pool by xin: RDin1 (energy) = RDin*xin,
               RDin2 (labour) = RDin*(1-xin); emergency split (0.2/0.8) when the
               firm lags the EXPECTED electrification mandate; spin-up override
               sends all innovation R&D to labour (RDin1=0).
          4.   Two innovation Bernoullis — Inn1 (energy, rate o11·RDin1) and
               Inn2 (labour, rate o12·RDin2) — plus imitation (o2·RDim).
          5.   Energy candidates (Inn1): Beta draws for EE/EEp/EF/EFp (improve
               downward toward floors) and additive draw for EL (toward [0,1]);
               labour candidates (Inn2): A1inn/A1pinn (unchanged form).
          6.   Imitation: energy-aware Td norm; copy ALL axes from the victim.
          7.   Lifetime-cost decision over the FULL bundle (labour + energy):
               (1+mi1)·cost_sect1 + b·cost_sect2; imitation first, then innovation.

        elec_price : c_en(1) — current-period electricity price.
        current_t  : current period (for the spin-up innovation override).
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
        # Energy-axis innovation parameters (Task 5.7.1).
        o11       = gparams.rd_productivity_energy          # C++ o11     (0.6)
        xin       = gparams.innovation_sector1_share_initial  # C++ xin0  (0.07, constant: xin1=0)
        flag_spinup_innov = gparams.allow_energy_innovation_in_spinup  # flag_spinup_innov (0)
        t_spinup  = gparams.spin_up_steps                   # C++ t_spinup (60)
        # rescale ranges
        uu1_eep   = gparams.s1_energy_eff_innov_lower       # uu1_eep (-0.15)
        uu2_eep   = gparams.s1_energy_eff_innov_upper       # uu2_eep ( 0.15)
        uu1_ee    = gparams.s2_energy_eff_innov_lower       # uu1_ee  (-0.15)
        uu2_ee    = gparams.s2_energy_eff_innov_upper       # uu2_ee  ( 0.15)
        uu1_efp   = gparams.s1_proc_emission_innov_lower    # uu1_efp (-0.05)
        uu2_efp   = gparams.s1_proc_emission_innov_upper    # uu2_efp ( 0.05)
        uu1_ef    = gparams.s2_proc_emission_innov_lower    # uu1_ef  (-0.05)
        uu2_ef    = gparams.s2_proc_emission_innov_upper    # uu2_ef  ( 0.05)
        uu1_elp   = gparams.s1_elfrac_innov_lower           # uu1_elp (-0.15)
        uu2_elp   = gparams.s1_elfrac_innov_upper           # uu2_elp ( 0.15)
        # limits (EN/EF: lower is better, with floors; EL: clamp to [low, upp])
        A1p_en_limlow = gparams.s1_energy_need_floor
        A1_en_limlow  = gparams.s2_energy_need_floor
        A1p_ef_limlow = gparams.s1_proc_emission_floor
        A1_ef_limlow  = gparams.s2_proc_emission_floor
        A1p_el_limlow = gparams.elfrac_floor
        A1p_el_limupp = gparams.elfrac_ceil
        flag_el_inn   = gparams.fuel_to_elec_innovation_rule  # flag_fuel_to_elec_inn (0)
        A0_ef         = gparams.env_filthiness_init           # for Td denominators
        A0_el         = gparams.electrification_fraction_init_s1
        elconv        = gparams.fuel_to_electricity_equivalence
        rule          = gparams.fuel_to_elec_rule
        pf            = self.nation.params.fossil_fuel_price
        ff2em         = gparams.fuel_to_emissions_factor
        t_co2_I1      = self.nation.government.carbon_tax_rate_industry1
        t_co2_I2      = self.nation.government.carbon_tax_rate_industry2

        # Current energy-axis state (C++ axis names in comments).
        A1_en_cur  = self.current_technology.energy_efficiency        # A1_en
        A1p_en_cur = self.process_energy_need                         # A1p_en
        A1_ef_cur  = self.current_technology.env_cleanliness          # A1_ef
        A1p_ef_cur = self.process_env_filthiness                      # A1p_ef
        A1p_el_cur = self.current_technology.electrification_fraction  # A1p_el

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

        # --- 3. Split innovation pool by xin (energy vs labour) ---
        # C++ 7265-7288. Real-R&D baseline splits the LABOUR units (Ld1rd).
        if flag_realrd == 0:
            rd_inn_total = self.rd_budget * xi
            rd_imm       = self.rd_budget * (1.0 - xi)
        else:
            rd_inn_total = self.rd_labour_demand * xi
            rd_imm       = self.rd_labour_demand * (1.0 - xi)

        elfrac_reg_exp  = self.nation.elfrac_reg_exp
        elfrac_reg_fine = self.nation.elfrac_reg_fine

        # RDin1 = energy properties; RDin2 = labour properties.
        rd_in1 = rd_inn_total * xin
        rd_in2 = rd_inn_total * (1.0 - xin)
        # Emergency split when lagging the EXPECTED electrification mandate (7280).
        if elfrac_reg_exp > A1p_el_cur:
            rd_in1 = rd_inn_total * 0.2
            rd_in2 = rd_inn_total * 0.8
        # Spin-up override (7283-7288): no energy innovation during spin-up.
        if flag_spinup_innov == 0 and current_t < t_spinup:
            rd_in2 = rd_inn_total
            rd_in1 = 0.0

        self.rd_innovation_budget = rd_inn_total
        self.rd_imitation_budget  = rd_imm

        # --- 4. Bernoulli trials: Inn1 (energy), Inn2 (labour), Imm ---
        parber_in1 = max(0.0, min(1.0, (1.0 - math.exp(-o11 * rd_in1)) * probinim))
        inn1 = bool(self.rng.binomial(1, parber_in1)) if parber_in1 > 0.0 else False
        parber_in2 = max(0.0, min(1.0, (1.0 - math.exp(-o12 * rd_in2)) * probinim))
        inn2 = bool(self.rng.binomial(1, parber_in2)) if parber_in2 > 0.0 else False
        self.innovated_sector1 = inn1
        self.innovated_sector2 = inn2

        parber_imm = max(0.0, min(1.0, (1.0 - math.exp(-o2 * rd_imm)) * probinim))
        imm = bool(self.rng.binomial(1, parber_imm)) if parber_imm > 0.0 else False
        self.imitated = imm

        # --- 5. Innovation candidates (full bundle) ---
        # Energy axes (C++ 7330-7435): only drawn if Inn1; else inherit current.
        if inn1:
            # EEp_inn (A1p_en): improves downward toward floor.
            rnd = uu1_eep + float(self.rng.beta(b_a1, b_b1)) * (uu2_eep - uu1_eep)
            eep_inn = max(A1p_en_limlow, A1p_en_limlow + (A1p_en_cur - A1p_en_limlow) * (1.0 - rnd))
            # EFp_inn (A1p_ef): improves downward toward floor (0 in baseline → stays 0).
            rnd = uu1_efp + float(self.rng.beta(b_a1, b_b1)) * (uu2_efp - uu1_efp)
            efp_inn = max(A1p_ef_limlow, A1p_ef_limlow + (A1p_ef_cur - A1p_ef_limlow) * (1.0 - rnd))
            # ELp_inn (A1p_el): ADDITIVE draw, clamp to [low, upp]; pinned if
            # already 1. C++ (7360-7400) always draws the Beta then pins, so we
            # draw unconditionally to keep the RNG sequence faithful.
            rnd = uu1_elp + float(self.rng.beta(b_a1, b_b1)) * (uu2_elp - uu1_elp)
            if A1p_el_cur == 1.0:
                elp_inn = A1p_el_cur
            else:
                elp_inn = min(A1p_el_limupp, max(A1p_el_limlow, A1p_el_cur + rnd))
            # EE_inn (A1_en): sector-2 energy need, improves downward toward floor.
            rnd = uu1_ee + float(self.rng.beta(b_a1, b_b1)) * (uu2_ee - uu1_ee)
            ee_inn = max(A1_en_limlow, A1_en_limlow + (A1_en_cur - A1_en_limlow) * (1.0 - rnd))
            # EF_inn (A1_ef): improves downward toward floor.
            rnd = uu1_ef + float(self.rng.beta(b_a1, b_b1)) * (uu2_ef - uu1_ef)
            ef_inn = max(A1_ef_limlow, A1_ef_limlow + (A1_ef_cur - A1_ef_limlow) * (1.0 - rnd))
        else:
            eep_inn, efp_inn, elp_inn = A1p_en_cur, A1p_ef_cur, A1p_el_cur
            ee_inn, ef_inn = A1_en_cur, A1_ef_cur
        # Labour axes (C++ 7438-7457): drawn if Inn2; else inherit current.
        if inn2:
            rnd = uu1_ap + float(self.rng.beta(b_a1, b_b1)) * (uu2_ap - uu1_ap)
            a1p_inn = self.process_labour_prod * (1.0 + rnd)
            rnd = uu1_a + float(self.rng.beta(b_a1, b_b1)) * (uu2_a - uu1_a)
            a1_inn = self.machine_labour_prod * (1.0 + rnd)
        else:
            a1p_inn = self.process_labour_prod
            a1_inn = self.machine_labour_prod
        has_inn = inn1 or inn2

        # --- 6. Imitation target (energy-aware Td norm) ---
        # C++ 7510-7567: Td^2 sums squared per-axis gaps normalised by frontier tops.
        a1_imm = a1p_imm = ee_imm = eep_imm = ef_imm = efp_imm = elp_imm = sentinel
        if imm and len(all_firms) > 0:
            A1top_e  = max(A1top, 1e-6)
            A1ptop_e = max(A1ptop, 1e-6)
            # Energy Td terms are included only when real frontier tops were
            # supplied (production path); direct labour-only callers omit them.
            use_energy_td = A1p_en_top > 0.0
            en_t  = max(abs(A1_en_top), 1e-12)
            enp_t = max(abs(A1p_en_top), 1e-12)
            ef_t  = abs(A1_ef_top) + 0.1 * A0_ef
            efp_t = abs(A1p_ef_top) + 0.1 * A0_ef
            # C++ 7541 uses A0_el then A0_ef in the two electrification factors (sic).
            elp_d = (A1p_el_top + 0.1 * A0_el) * (A1p_el_top + 0.1 * A0_ef)
            inv_td = np.zeros(len(all_firms))
            for ii, other in enumerate(all_firms):
                td_sq = (
                    (other.machine_labour_prod - self.machine_labour_prod) ** 2 / (A1top_e * A1top_e)
                    + (other.process_labour_prod - self.process_labour_prod) ** 2 / (A1ptop_e * A1ptop_e)
                )
                if use_energy_td:
                    td_sq += (
                        (other.current_technology.energy_efficiency - A1_en_cur) ** 2 / (en_t * en_t)
                        + (other.process_energy_need - A1p_en_cur) ** 2 / (enp_t * enp_t)
                        + (other.current_technology.env_cleanliness - A1_ef_cur) ** 2 / (ef_t * ef_t)
                        + (other.process_env_filthiness - A1p_ef_cur) ** 2 / (efp_t * efp_t)
                        + (other.current_technology.electrification_fraction - A1p_el_cur) ** 2 / elp_d
                    )
                td = math.sqrt(td_sq)
                inv_td[ii] = 1.0 / td if td > 0.0 else 0.0

            Tdtot = float(inv_td.sum())
            if Tdtot > 0.0:
                cumprob = np.cumsum(inv_td) / Tdtot
                rnd = float(self.rng.uniform(0.0, 1.0))
                prev = 0.0
                for ii, other in enumerate(all_firms):
                    c = float(cumprob[ii])
                    if rnd > prev and rnd <= c:
                        if other.patent_timer == 0:
                            a1_imm  = other.machine_labour_prod
                            a1p_imm = other.process_labour_prod
                            ee_imm  = other.current_technology.energy_efficiency
                            eep_imm = other.process_energy_need
                            ef_imm  = other.current_technology.env_cleanliness
                            efp_imm = other.process_env_filthiness
                            elp_imm = other.current_technology.electrification_fraction
                        break
                    prev = c

        # --- 7. Lifetime-cost decision over the FULL bundle ---
        # C++ 7624-7725: (1+mi1)*cost_sect1 + b*cost_sect2 over labour + energy axes.
        def _lifetime(a1p_v, a1_v, a1p_en_v, a1p_ef_v, a1p_el_v, a1_en_v, a1_ef_v):
            if a1p_v <= 0.0 or a1_v <= 0.0:
                return math.inf
            eld = _electdemand(a1p_el_v, a1p_en_v, elconv, rule)
            ffd = _ffueldemand(a1p_el_v, a1p_en_v, elconv, rule)
            elfrac_diff = elfrac_reg_exp - a1p_el_v  # raw; cost_sect1 fines only if > 0
            c1 = cost_sect1(
                wage_net=wage, process_prod=a1p_v * a,
                elec_demand_per_unit=eld, elec_price=elec_price,
                fossil_demand_per_unit=ffd, fossil_price=pf, ff2em=ff2em,
                env_filthiness=a1p_ef_v, carbon_tax_s1=t_co2_I1,
                elfrac_deficit=elfrac_diff, fine=elfrac_reg_fine, rule=rule,
            )
            c2 = cost_sect2(wage, a1_v, a1_en_v, elec_price, a1_ef_v, t_co2_I2)
            return (1.0 + mi1) * c1 + b * c2

        cost_current = _lifetime(self.process_labour_prod, self.machine_labour_prod,
                                 A1p_en_cur, A1p_ef_cur, A1p_el_cur, A1_en_cur, A1_ef_cur)
        # Imitation first (C++ 7636): adopt the whole victim bundle if cheaper.
        if imm and a1_imm is not sentinel:
            cost_imm = _lifetime(a1p_imm, a1_imm, eep_imm, efp_imm, elp_imm, ee_imm, ef_imm)
            if cost_imm < cost_current:
                self.machine_labour_prod = a1_imm
                self.process_labour_prod = a1p_imm
                A1_en_cur, A1p_en_cur = ee_imm, eep_imm
                A1_ef_cur, A1p_ef_cur = ef_imm, efp_imm
                A1p_el_cur = elp_imm

        # Innovation next (C++ 7678), evaluated against the post-imitation state.
        cost_after_imm = _lifetime(self.process_labour_prod, self.machine_labour_prod,
                                   A1p_en_cur, A1p_ef_cur, A1p_el_cur, A1_en_cur, A1_ef_cur)
        if has_inn:
            cost_inn = _lifetime(a1p_inn, a1_inn, eep_inn, efp_inn, elp_inn, ee_inn, ef_inn)
            if cost_inn < cost_after_imm:
                self.vintage += 1
                self.machine_labour_prod = a1_inn
                self.process_labour_prod = a1p_inn
                A1_en_cur, A1p_en_cur = ee_inn, eep_inn
                A1_ef_cur, A1p_ef_cur = ef_inn, efp_inn
                A1p_el_cur = elp_inn

        # --- 8. Commit all axes back to firm state ---
        self.process_energy_need = A1p_en_cur
        self.process_env_filthiness = A1p_ef_cur
        self.current_technology = Technology(
            labour_productivity=self.machine_labour_prod,
            energy_efficiency=A1_en_cur,
            env_cleanliness=A1_ef_cur,
            electrification_fraction=A1p_el_cur,
        )
        if has_inn:
            self.innovation_candidate = Technology(labour_productivity=a1_inn)
        if imm and a1_imm is not sentinel:
            self.imitation_candidate = Technology(labour_productivity=a1_imm)
