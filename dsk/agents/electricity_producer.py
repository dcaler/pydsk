"""Electricity producer: manages green and brown plant fleets, R&D, dispatch, emissions."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from dsk.agent_set import AgentSet
from dsk.agents.power_plant import BrownPlant, GreenPlant

if TYPE_CHECKING:
    from dsk.nation import Nation
    from dsk.parameters.global_parameters import GlobalParameters


def _electdemand(elf: float, end: float, phi: float, rule: int) -> float:
    """Electricity demand per unit of production for a capital-good firm.

    C++ dsk_electdemand.cpp: electdemand(elf, end, phi).

    elf: electrification fraction of the firm's own process (A1p_el)
    end: energy demand scale (A1p_en, energy need per unit at full fuel use)
    phi: fuel-to-electricity equivalence (elconv = 0.3)
    rule: flag_fuel_to_elec (0=linear, 1=nonlinear-old, 2=nonlinear-NW)
    """
    if rule == 0:
        return end * elf * phi
    if rule == 1:
        return end * (elf * elf + elf) * 0.7 * 0.30
    # rule == 2
    if elf >= 1.0:
        return end  # fully electrified
    rat = phi * elf / (1.0 - elf)
    return end * rat / (rat + 2.0 * math.sqrt(phi * rat) + phi) / 2.0


def _ffueldemand(elf: float, end: float, phi: float, rule: int) -> float:
    """Fossil fuel demand per unit of production for a capital-good firm.

    C++ dsk_ffueldemand.cpp: ffueldemand(elf, end, phi).
    """
    if rule == 0:
        return end * (1.0 - elf)
    if rule == 1:
        return end * ((1.0 - elf) * (1.0 - elf) + (1.0 - elf)) * 2.1 * 0.30
    # rule == 2
    if elf >= 1.0:
        return 0.0
    rat = phi * elf / (1.0 - elf)
    return end / (rat + 2.0 * math.sqrt(phi * rat) + phi) / 2.0


def green_plant_cost(
    n_new: int,
    n_lim1: float,
    n_lim2: float,
    subsidy: float,
    price0: float,
    hurry: float,
) -> float:
    """Marginal cost of building the ``n_new``-th green plant this period.

    Faithful port of C++ ``green_plant_cost`` (module_energy.cpp:1471).

    - ``n_lim1``: plants buildable without "hurry" surcharge (= max(N_hurrycost_min,
      exp_quota * K_ge)).
    - ``n_lim2``: plants for which the per-plant ``subsidy`` is granted (= NSubmax_ge).
    - ``price0``: base build cost in absence of subsidy or hurry (= CF_ge(t)).
    - ``hurry``: how sharply price rises beyond ``n_lim1`` (0 / 1 / 10000 per flag).

    A hurry surcharge of ``hurry`` means the (2*n_lim1)-th plant costs 2*price0.
    """
    n_new = int(n_new)
    n_lim1 = int(n_lim1)
    n_lim2 = int(n_lim2)
    # C++ does hurry/Nlim1; Nlim1==0 yields +inf in C++ doubles (Python would raise).
    hurry_scaled = hurry / n_lim1 if n_lim1 > 0 else float("inf")

    if n_lim1 < n_lim2:
        if n_new <= n_lim1:
            return price0 - subsidy
        if n_new < n_lim2:  # n_lim1 < n_new < n_lim2
            return price0 - subsidy + price0 * hurry_scaled * (n_new - n_lim1)
        return price0 + price0 * hurry_scaled * (n_new - n_lim1)  # n_new >= n_lim2
    else:  # n_lim2 <= n_lim1
        if n_new <= n_lim2:
            return price0 - subsidy
        if n_new < n_lim1:  # n_lim2 < n_new < n_lim1
            return price0
        return price0 + price0 * hurry_scaled * (n_new - n_lim1)  # n_new >= n_lim1


@dataclass
class _BuildState:
    """Mutable scratch state shared between expansion and replacement steps."""

    new_green: int = 0              # G_ge(t): green plants built this period
    new_brown: int = 0             # G_de(t): brown plants built this period
    green_full_cost: float = 0.0   # CF_ge_full(t): running green expenditure (total)
    prudinv: float = 0.0           # prudinv: remaining prudential investment budget
    replace_quota_green: int = 0   # dummy_replace_ge: green replacements still allowed
    replace_quota_brown: int = 0   # dummy_replace_de: brown replacements still allowed
    plant_worth_lost: float = 0.0  # life-years of plants lost to premature replacement
    n_no_hurrycost: float = 0.0    # N_hurrycost
    hurry_cost: float = 0.0        # hurrycost


class GreenPlantSet(AgentSet):
    """Collection of GreenPlant vintage groups."""

    def total_capacity(self) -> int:
        return sum(int(p.count) for p in self)

    def inflation_adjust(self, factor: float) -> None:
        for p in self:
            p.inflation_adjust(factor)

    def retire_old(self, current_t: int, life_plant: int) -> None:
        to_remove = [p for p in self if p.age(current_t) >= life_plant]
        for p in to_remove:
            self.remove(p)


class BrownPlantSet(AgentSet):
    """Collection of BrownPlant vintage groups."""

    def total_capacity(self) -> int:
        return sum(int(p.count) for p in self)

    def total_active_capacity(self) -> int:
        return sum(int(p.active_count) for p in self)

    def inflation_adjust(self, factor: float) -> None:
        for p in self:
            p.inflation_adjust(factor)

    def retire_old(self, current_t: int, life_plant: int) -> None:
        to_remove = [p for p in self if p.age(current_t) >= life_plant]
        for p in to_remove:
            self.remove(p)

    def merit_order(self, fuel_price: float, carbon_tax: float) -> list:
        """Plants sorted cheapest-first (C++ merit-order dispatch)."""
        return sorted(self, key=lambda p: p.unit_cost(fuel_price, carbon_tax))


class ElectricityProducer:
    """Regulated electricity sector singleton per nation.

    Owns the green and brown plant fleets and all energy-sector state
    mirrored from module_energy.h.
    """

    def __init__(self, nation: "Nation") -> None:
        self.nation = nation
        self.green_plants: GreenPlantSet = GreenPlantSet()
        self.brown_plants: BrownPlantSet = BrownPlantSet()

        # R&D allocation
        self.rd_spending_total: float = 0.0        # RD_en
        self.rd_spending_green: float = 0.0        # RD_en_ge
        self.rd_spending_dirty: float = 0.0        # RD_en_de
        self.dirty_rd_share: float = 0.0           # share_de

        # Innovation outcomes
        self.innov_param_green: float = 0.0        # parber_en_ge
        self.innov_param_dirty: float = 0.0        # parber_en_de
        self.innov_success_green: float = 0.0      # Inn_en_ge
        self.innov_success_dirty: float = 0.0      # Inn_en_de

        # Financial state
        self.net_worth: float = 0.0                # NW_en
        self.profit: float = 0.0                   # Pi_en
        self.revenue: float = 0.0                  # Rev_en
        self.fuel_cost: float = 0.0                # Fuel_cost
        self.investment_cost: float = 0.0          # IC_en (building outlay this period)
        self.expansion_cost_green: float = 0.0     # IC_en_eff
        self.expansion_investment_green: float = 0.0   # EI_en_ge
        self.expansion_investment_dirty: float = 0.0   # EI_en_de
        self.expansion_investment: float = 0.0     # EI_en
        self.bailout_from_govt: float = 0.0        # Gbailout_en
        self.plant_worth_lost: float = 0.0         # plant_worth_lost (life-years scrapped early)
        self.prudent_investment_limit: float = 0.0 # prudinv (remaining after construction)
        # IC_en_quota(tt): per-vintage expansion-cost quota, summed over the payback
        # window by the financial phase (Task 3.5).
        self.expansion_cost_quota: dict[int, float] = {}

        # Frontier "technology to build now" (R&D state; evolved in Task 3.5).
        self.frontier_brown_thermal_ineff: float = 0.0      # A_de(t)
        self.frontier_brown_emission_intensity: float = 0.0  # EM_de(t)
        self.frontier_brown_build_cost: float = 0.0          # CF_de(t)
        self.frontier_green_build_cost: float = 0.0          # CF_ge(t)

        # Capacity and energy output
        self.total_green_capacity: int = 0         # K_ge(2)
        self.total_brown_capacity: int = 0         # K_de(2)
        self.total_green_energy: float = 0.0       # Q_ge(2)
        self.total_brown_energy: float = 0.0       # Q_de(2)

        # Electricity price
        self.electricity_price: float = 0.0        # c_en(1)
        self.electricity_price_prev: float = 0.0   # c_en(2)
        self.electricity_price_raw: float = 0.0    # c_en_raw(1)
        self.markup: float = 0.0                   # mi_en

        # Running production cost for the current period (reset each dispatch)
        self.production_cost: float = 0.0          # PC_en

        # Emissions
        self.emissions: float = 0.0                # Emiss_en_eff

        # Labour demand
        self.labour_demand_rd_green: float = 0.0   # LDrd_ge
        self.labour_demand_rd_dirty: float = 0.0   # LDrd_de
        self.labour_demand_rd_total: float = 0.0   # LDrd_en
        self.labour_demand_expansion: float = 0.0  # LDexp_en
        self.labour_demand_fuel: float = 0.0       # LDff_en

        # Cost floors (inflation-corrected each period)
        self.green_build_cost_floor: float = 0.0      # CF_ge_limlow
        self.brown_build_cost_floor: float = 0.0      # CF_de_limlow
        self.green_build_cost_govt_floor: float = 0.0 # CF_ge_gov_limlow

        # Policy state
        self.brown_invest_ban_year: int = 0        # brown_invest_ban
        self.brown_use_ban_year: int = 0           # brown_use_ban
        self.subsidy_per_plant: float = 0.0        # Sub_ge
        self.subsidy_used: float = 0.0             # Sub_ge_used
        self.max_subsidised_plants: float = 0.0    # NSubmax_ge

        # Energy demand
        self.total_energy_demand: float = 0.0      # D_en_TOT
        self.total_energy_demand_build: float = 0.0  # D_en_build
        self.demand_history: list[float] = []      # D_en_hist (12-entry circular buffer)
        self.s1_elec_demand_total: float = 0.0     # D1_en_TOT
        self.s2_elec_demand_total: float = 0.0     # D2_en_TOT
        self.s1_fossil_demand_total: float = 0.0   # D1_ff_TOT

        # Government R&D grant state
        self.govt_rd_funds_effective: float = 0.0  # RnD_funds_En_eff
        self.govt_rd_grant_cost: float = 0.0       # RnD_gov_grant_cost
        self.govt_rd_topup_total: float = 0.0      # RD_gov_topup_tot
        self.govt_rd_multiplier_green: float = 0.0 # RnD_en_ge_mult
        self.govt_rd_all_multiplier: float = 0.0   # RnD_en_all_mult
        self.govt_rd_for_green: float = 0.0        # RD_gov_ge

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def initialise_from_parameters(self, gparams: "GlobalParameters") -> None:
        """Seed the producer from global parameters (called once before the main loop)."""
        p = gparams
        self.dirty_rd_share = p.dirty_rd_share_init
        self.markup = p.energy_markup_init
        self.net_worth = 0.0
        self.electricity_price = p.energy_cost_init_box_off
        self.electricity_price_prev = p.energy_cost_init_box_off
        self.green_build_cost_floor = p.green_plant_build_cost_floor_init
        self.brown_build_cost_floor = p.dirty_plant_build_cost_floor_init
        self.green_build_cost_govt_floor = p.green_plant_build_cost_govt_floor_init
        self.demand_history = [0.0] * 12

        # Government R&D top-up: baseline no-op (C++ dsk_main.cpp:895-911).
        # RnD_en_ge_mult=1.0 ("do nothing"), RnD_en_all_mult=0.0, additive funds=0,
        # govt applied research RD_gov_ge=0.  Climate policy (milestone 5) overrides.
        self.govt_rd_multiplier_green = 1.0
        self.govt_rd_all_multiplier = 0.0
        self.govt_rd_funds_effective = 0.0
        self.govt_rd_for_green = 0.0

        # No climate ban in the baseline: the C++ sets brown_invest_ban = brown_use_ban
        # = 5*T (an irrelevant future).  Climate policy (Task 5.3) overrides these.
        self.brown_invest_ban_year = 5 * p.total_steps
        self.brown_use_ban_year = 5 * p.total_steps

        initial_emission_intensity = (
            p.fuel_to_emissions_factor * p.energy_emissivity_ratio_init
        )

        # Frontier technology available to build now (R&D evolves this in Task 3.5).
        self.frontier_brown_thermal_ineff = p.dirty_plant_one_over_eff_init
        self.frontier_brown_emission_intensity = initial_emission_intensity
        self.frontier_brown_build_cost = p.dirty_plant_build_cost_init
        self.frontier_green_build_cost = p.green_plant_build_cost_init

        n_total = self._estimate_initial_total_plants(p)
        n_green = int(round(n_total * p.green_capacity_share_init))
        n_brown = n_total - n_green

        if n_green > 0:
            self.green_plants.add(GreenPlant(
                self.nation,
                vintage=0,
                count=n_green,
                building_cost=p.green_plant_build_cost_init,
            ))
        if n_brown > 0:
            self.brown_plants.add(BrownPlant(
                self.nation,
                vintage=0,
                count=n_brown,
                building_cost=p.dirty_plant_build_cost_init,
                thermal_inefficiency=p.dirty_plant_one_over_eff_init,
                emission_intensity=initial_emission_intensity,
            ))

        self._update_capacity()

    def _estimate_initial_total_plants(self, gparams: "GlobalParameters") -> int:
        """Replicate C++ spin-up total: D_en_TOT × t_spinup_energy plants."""
        p = gparams
        s2_demand = p.n2_consumption_good_firms * p.capital_init * p.energy_need_init
        s1_demand = (
            p.n1_capital_good_firms * p.s1_energy_need_init_factor * p.energy_need_init
        )
        per_step = max(1, round(s2_demand + s1_demand))
        return per_step * p.t_spinup_energy

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_capacity(self) -> None:
        self.total_green_capacity = self.green_plants.total_capacity()
        self.total_brown_capacity = self.brown_plants.total_capacity()

    def green_share(self) -> float:
        """Fraction of total capacity that is green (K_ge / (K_ge + K_de))."""
        total = self.total_green_capacity + self.total_brown_capacity
        return self.total_green_capacity / total if total > 0 else 0.0

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def aggregate_demand(self, t: int, capital_good_sector, consumption_good_sector) -> float:
        """Aggregate electricity and fossil fuel demand across all firms.

        C++ EN_DEM() in module_energy.cpp.

        Computes per-firm electricity (and sector-1 fossil fuel) demands, stores
        them on each firm, sums to sector totals, manages the 12-period demand
        history buffer, and derives ``D_en_build`` used for plant-capacity planning.

        Returns D_en_TOT (total electricity demand used as the dispatch target).
        """
        gparams = self.nation.gparams
        phi = gparams.fuel_to_electricity_equivalence   # elconv = 0.3
        rule = gparams.fuel_to_elec_rule                # flag_fuel_to_elec = 1

        # Sector-1: capital-good firms
        d1_en_tot = 0.0
        d1_ff_tot = 0.0
        for firm in capital_good_sector:
            if not firm.is_alive or firm.production <= 0.0 or firm.process_energy_need <= 0.0:
                firm.elec_demand = 0.0
                firm.fossil_fuel_demand = 0.0
                continue
            elf = firm.current_technology.electrification_fraction  # A1p_el[i]
            end = firm.process_energy_need                           # A1p_en[i]
            firm.elec_demand = firm.production * _electdemand(elf, end, phi, rule)
            firm.fossil_fuel_demand = firm.production * _ffueldemand(elf, end, phi, rule)
            d1_en_tot += firm.elec_demand
            d1_ff_tot += firm.fossil_fuel_demand

        # Sector-2: consumption-good firms (electricity only)
        d2_en_tot = 0.0
        for firm in consumption_good_sector:
            if not firm.is_alive or firm.production <= 0.0 or firm.effective_energy_efficiency <= 0.0:
                firm.elec_demand = 0.0
                continue
            firm.elec_demand = firm.production * firm.effective_energy_efficiency  # Q2*A2e_en
            d2_en_tot += firm.elec_demand

        # Total electricity demand (C++: D_en_TOT = ROUND(D1_en_TOT + D2_en_TOT))
        d_en_tot = float(round(d1_en_tot + d2_en_tot))

        # History init at t==1 (C++: if(t==1) { for(i=1;i<=12;i++) D_en_hist(i)=D_en_TOT; })
        if t == 1:
            self.demand_history = [d_en_tot] * 12

        # D_en_build: max of current demand and extrapolated historical values
        lookback = gparams.energy_nominal_demand_lookback   # flag_demand_energy
        build_fac = gparams.energy_demand_history_factor    # D_en_build_fac = 1.03
        d_en_build = d_en_tot
        for i in range(1, lookback + 1):
            d_en_build = max(d_en_build, self.demand_history[i - 1] * (build_fac ** i))

        # Shift history buffer and record current demand (C++: t>1 branch)
        if t > 1:
            for idx in range(11, 0, -1):
                self.demand_history[idx] = self.demand_history[idx - 1]
            self.demand_history[0] = d_en_tot

        self.s1_elec_demand_total = d1_en_tot
        self.s2_elec_demand_total = d2_en_tot
        self.s1_fossil_demand_total = d1_ff_tot
        self.total_energy_demand = d_en_tot
        self.total_energy_demand_build = d_en_build

        return d_en_tot

    # ------------------------------------------------------------------

    def dispatch_merit_order(
        self,
        demand: float,
        fuel_price: float,
        carbon_tax: float = 0.0,
    ) -> None:
        """Run the electricity market (C++ ELECTRICITY_MARKET, flag_electricity_bidding=0).

        Green plants (zero variable cost) are dispatched first; brown plants
        fill residual demand in merit order (cheapest unit_cost first;
        ties broken by building_cost).  Electricity price = marginal plant's
        production-cost bid + markup.

        Updates: electricity_price, electricity_price_raw, total_green_energy,
        total_brown_energy, production_cost, fuel_cost, emissions,
        total_energy_demand (D_en_TOT, the R&D revenue base).
        """
        self._update_capacity()
        self.total_energy_demand = demand

        # Rank brown plants: primary key = unit_cost asc, tie-break = building_cost asc
        # (mirrors C++ derank sort: C_de then CF_de)
        brown_ranked = sorted(
            [p for p in self.brown_plants if p.count > 0],
            key=lambda p: (p.unit_cost(fuel_price, carbon_tax), p.building_cost),
        )
        # Rank green plants by full_building_cost asc (gerank sort by CF_ge_full)
        green_ranked = sorted(
            [p for p in self.green_plants if p.count > 0],
            key=lambda p: p.full_building_cost,
        )

        k_green = float(self.total_green_capacity)
        production_cost = 0.0
        fuel_cost_acc = 0.0
        emissions_acc = 0.0
        marginal_price = 0.0

        residual_for_brown = demand - k_green  # C++: Q_de(2)

        if residual_for_brown <= 0.5:
            # Green capacity is sufficient — serve all demand from green fleet
            self.total_green_energy = demand    # Q_ge(2) = D_en_TOT
            self.total_brown_energy = 0.0
            remaining = demand
            for p in green_ranked:
                if remaining <= 0.5:
                    break
                remaining -= min(remaining, float(p.count))
                marginal_price = 0.0  # flag_electricity_bidding=0: green bid = 0
        else:
            # Need brown plants for residual demand
            self.total_green_energy = k_green   # Q_ge(2) = K_ge (all green runs)
            self.total_brown_energy = residual_for_brown
            remaining = residual_for_brown      # C++: Q_de_temp
            for p in brown_ranked:
                if remaining <= 0.5:
                    break
                served = min(remaining, float(p.count))
                c_de = p.unit_cost(fuel_price, carbon_tax)
                production_cost += served * c_de                                    # PC_en
                fuel_cost_acc += served * fuel_price * p.thermal_inefficiency       # Fuel_cost
                emissions_acc += served * p.emission_intensity * p.thermal_inefficiency  # Emiss_en
                remaining -= served
                marginal_price = c_de   # derank_pe(tt) = derank_cp(tt) when bidding=0

        # flag_electricity_bidding == 0: c_en = c_en_raw + mi_en
        self.electricity_price_raw = marginal_price
        self.electricity_price = marginal_price + self.markup
        self.production_cost = production_cost
        self.fuel_cost = fuel_cost_acc
        self.emissions = emissions_acc

    # ------------------------------------------------------------------
    # Capacity expansion & premature replacement (C++ ENERGY, plant build)
    # ------------------------------------------------------------------

    def _brown_frontier_unit_cost(self, fuel_price: float, carbon_tax: float) -> float:
        """C_de(t): unit production cost of the frontier brown plant."""
        return self.frontier_brown_thermal_ineff * (
            fuel_price + carbon_tax * self.frontier_brown_emission_intensity
        )

    @staticmethod
    def _split_subsidised(n_prev: int, n_easy: int, nsubmax: int) -> tuple[int, int]:
        """Split the "easy" green plants into (subsidised, standard) counts.

        Faithful port of the C++ "sorting function" (module_energy.cpp:417-424).
        """
        n_subs = 0
        n_stan = 0
        if n_prev <= n_easy <= nsubmax:
            n_subs = n_easy - n_prev
        if n_prev < nsubmax < n_easy:
            n_subs = nsubmax - n_prev
            n_stan = n_easy - nsubmax
        if nsubmax <= n_prev <= n_easy:
            n_stan = n_easy - n_prev
        return n_subs, n_stan

    def _select_build_technology(
        self, fuel_price: float, carbon_tax: float, payback: float
    ) -> None:
        """Adopt the cheapest available make to build from (C++ :266-302).

        The "best historical plant" loop picks, among the frontier and every
        installed vintage, the brown make minimising ``C_de + CF_de/payback`` and
        the green make minimising ``CF_ge``.  R&D keeps the frontier monotonically
        best, so this is usually the identity, but it is ported for fidelity.
        """
        best_key = self._brown_frontier_unit_cost(fuel_price, carbon_tax) + (
            self.frontier_brown_build_cost / payback
        )
        best_brown = None
        for pl in self.brown_plants:
            if pl.count <= 0:
                continue
            key = pl.unit_cost(fuel_price, carbon_tax) + pl.building_cost / payback
            if key < best_key:
                best_key = key
                best_brown = pl
        if best_brown is not None:
            self.frontier_brown_thermal_ineff = best_brown.thermal_inefficiency
            self.frontier_brown_emission_intensity = best_brown.emission_intensity
            self.frontier_brown_build_cost = best_brown.building_cost

        best_green_cf = self.frontier_green_build_cost
        for pl in self.green_plants:
            if pl.count > 0 and pl.building_cost < best_green_cf:
                best_green_cf = pl.building_cost
        self.frontier_green_build_cost = best_green_cf

    def plan_capacity_expansion(
        self,
        t: int,
        demand_for_building: float,
        fuel_price: float,
        carbon_tax: float,
        gparams: "GlobalParameters",
    ) -> None:
        """Decide which new plants to build this period (C++ ENERGY, :244-766).

        Ports the post-spin-up plant-construction path under the baseline flags
        ``flag_energy_exp=1`` (soft hurry cost), ``flag_early_plants=2``
        (cost-based replacement capped by net worth), ``flag_early_plants2=0``
        (replaced brown become reserve, not scrapped), ``flag_early_brown=0``
        (only green may replace).

        ``demand_for_building`` is the C++ ``D_en_build`` capacity target.  Spin-up
        seeding and the ``t_tune`` redistribution are handled at initialisation;
        the government ``GreenBuildFund`` programme (fund=0 in baseline) and
        end-of-period scrapping are out of scope for this task.
        """
        p = gparams
        payback = p.green_plant_payback_threshold
        life_plant = p.plant_lifetime_years
        exp_quota = p.green_expansion_quota
        flag_energy_exp = p.green_expansion_constraint_mode
        flag_early_plants = p.energy_premature_replacement_mode
        flag_early_plants2 = p.replaced_plants_scrapped
        flag_brown_late = p.brown_quota_tolerant
        nsubmax_i = int(round(self.max_subsidised_plants))   # NSubmax_ge (0 baseline)
        sub_ge = self.subsidy_per_plant                      # Sub_ge (0 baseline)
        brown_invest_ban = self.brown_invest_ban_year
        brown_use_ban = self.brown_use_ban_year

        self._update_capacity()
        k_green = float(self.total_green_capacity)
        k_dirty = float(self.total_brown_capacity)

        # Expansionary investment required to meet demand (C++ :253-258).
        if k_green + k_dirty <= demand_for_building:
            ei_en = int(math.ceil(demand_for_building - k_green - k_dirty))
        else:
            ei_en = 0
        self.expansion_investment = ei_en

        # Adopt the cheapest make to build from, then read its cost terms.
        self._select_build_technology(fuel_price, carbon_tax, payback)
        cf_de = self.frontier_brown_build_cost
        c_de = self._brown_frontier_unit_cost(fuel_price, carbon_tax)
        cf_ge = self.frontier_green_build_cost

        hurry_cost = {0: 0.0, 1: 1.0, 2: 10000.0}[flag_energy_exp]
        n_no_hurry = max(p.n_plants_no_hurrycost_min, exp_quota * k_green)

        # Rank brown plants cheapest-first within their lifetime window
        # (C++ :329-377 preliminary ranking).  0-indexed vintages mean we keep the
        # whole operational lifetime rather than the C++ 1-indexed min(life_plant,t).
        ranked_brown = sorted(
            [pl for pl in self.brown_plants if pl.count > 0 and pl.age(t) < life_plant],
            key=lambda pl: (pl.unit_cost(fuel_price, carbon_tax), pl.building_cost),
        )
        n_vintage_de = len(ranked_brown)

        newplant = flag_early_plants in (1, 2) and t > 1 and n_vintage_de >= 1
        if newplant and flag_early_plants == 2:
            prudinv = 2.0 * self.net_worth
        elif newplant and flag_early_plants == 1:
            prudinv = 1.0e5 * (cf_de + cf_ge)
        else:
            prudinv = 0.0

        state = _BuildState(
            prudinv=prudinv,
            replace_quota_green=int(round(max(k_green * p.green_replacement_quota,
                                              p.n_plants_replace_min))),
            replace_quota_brown=int(round(max(k_dirty * p.dirty_replacement_quota,
                                              p.n_plants_replace_min))),
            n_no_hurrycost=n_no_hurry,
            hurry_cost=hurry_cost,
        )

        # Precautionary green when a brown ban looms and green lags (C++ :389-395).
        if brown_invest_ban - t <= life_plant and k_green < 0.4 * k_dirty:
            state.new_green = int(math.ceil(min(n_no_hurry * 2, 0.4 * k_dirty)))

        # Extra green when all brown are already "replaced" but not scrapped
        # (C++ :399-408; only under flag_early_plants>0 & flag_early_plants2==0).
        if flag_early_plants > 0 and flag_early_plants2 == 0:
            if self.brown_plants.total_active_capacity() == 0 and k_dirty > 0:
                dummy = round(min(
                    min(exp_quota, p.green_replacement_quota) * k_green,
                    max(demand_for_building - k_green, 0.0),
                ))
                state.new_green = max(int(dummy), state.new_green)

        # Cost-account the precautionary/extra green already counted (C++ :411-446).
        self._account_green_cost(
            state, n_prev=0, n_des=state.new_green,
            cf_ge=cf_ge, sub_ge=sub_ge, nsubmax_i=nsubmax_i,
            flag_early_plants=flag_early_plants,
        )

        if brown_invest_ban - t >= 1:
            # Brown investment still allowed (C++ :450-583).
            deadline = min(float(payback), max(float(brown_use_ban - t), 0.1))
            deadline_latebrown = deadline
            if flag_brown_late == 1 and self.brown_plants.total_active_capacity() == 0:
                deadline_latebrown = min(deadline, 1.0)

            if ei_en > 0:
                self._expand_with_brown_option(
                    state, ei_en, cf_ge, cf_de, c_de, sub_ge, nsubmax_i,
                    deadline_latebrown, payback, flag_early_plants,
                )
                state.new_brown = max(ei_en - state.new_green, 0)

            if newplant:
                self.decide_premature_replacement(
                    t, ranked_brown, fuel_price, carbon_tax, gparams, state,
                    brown_banned=False, deadline=deadline, k_green=k_green,
                    cf_ge=cf_ge, cf_de=cf_de, c_de=c_de,
                    sub_ge=sub_ge, nsubmax_i=nsubmax_i,
                )

        if brown_invest_ban - t <= 0:
            # Brown investment forbidden — build green only (C++ :588-666).
            if ei_en > 0:
                self._expand_green_only(
                    state, ei_en, cf_ge, sub_ge, nsubmax_i, flag_early_plants
                )
            state.new_brown = 0
            if newplant:
                self.decide_premature_replacement(
                    t, ranked_brown, fuel_price, carbon_tax, gparams, state,
                    brown_banned=True, deadline=0.0, k_green=k_green,
                    cf_ge=cf_ge, cf_de=cf_de, c_de=c_de,
                    sub_ge=sub_ge, nsubmax_i=nsubmax_i,
                )

        # IC_en_quota(t): total expansion outlay spread over the payback (C++ :717).
        self.expansion_cost_quota[t] = (
            state.green_full_cost + state.new_brown * cf_de
        ) / payback

        if state.new_green > 0:
            cf_ge_full_per_plant = state.green_full_cost / state.new_green
            self.subsidy_used = sub_ge * min(state.new_green, nsubmax_i)
        else:
            cf_ge_full_per_plant = cf_ge
            self.subsidy_used = 0.0

        # Materialise the new vintage-t plants.
        if state.new_green > 0:
            self.green_plants.add(GreenPlant(
                self.nation, vintage=t, count=state.new_green,
                building_cost=cf_ge, subsidy_received=self.subsidy_used,
                full_building_cost=cf_ge_full_per_plant,
            ))
        if state.new_brown > 0:
            bp = BrownPlant(
                self.nation, vintage=t, count=state.new_brown,
                building_cost=cf_de,
                thermal_inefficiency=self.frontier_brown_thermal_ineff,
                emission_intensity=self.frontier_brown_emission_intensity,
            )
            bp.active_count = state.new_brown
            self.brown_plants.add(bp)

        self._update_capacity()

        # Safety net: demand must be met after building (C++ :750-762).
        deficit = demand_for_building - self.total_green_capacity - self.total_brown_capacity
        if deficit > 0.5:
            n_add = int(math.ceil(deficit))
            if self.total_brown_capacity < self.total_green_capacity:
                self.green_plants.add(GreenPlant(
                    self.nation, vintage=t, count=n_add,
                    building_cost=cf_ge, full_building_cost=cf_ge_full_per_plant,
                ))
            else:
                bp = BrownPlant(
                    self.nation, vintage=t, count=n_add,
                    building_cost=cf_de,
                    thermal_inefficiency=self.frontier_brown_thermal_ineff,
                    emission_intensity=self.frontier_brown_emission_intensity,
                )
                bp.active_count = n_add
                self.brown_plants.add(bp)
            self._update_capacity()

        self.plant_worth_lost = state.plant_worth_lost
        self.prudent_investment_limit = state.prudinv

    def _account_green_cost(
        self, state: _BuildState, n_prev: int, n_des: int,
        cf_ge: float, sub_ge: float, nsubmax_i: int, flag_early_plants: int,
    ) -> None:
        """Accumulate the cost of green plants already counted (C++ :411-446).

        Does not change ``new_green`` — used for the precautionary/extra green that
        was added directly to the count beforehand.
        """
        n_easy = min(n_des, int(state.n_no_hurrycost))
        n_subs, n_stan = self._split_subsidised(n_prev, n_easy, nsubmax_i)

        mc = green_plant_cost(1, state.n_no_hurrycost, nsubmax_i, sub_ge, cf_ge, state.hurry_cost)
        state.green_full_cost += mc * n_subs
        if flag_early_plants == 2:
            state.prudinv -= mc * n_subs

        mc = green_plant_cost(state.n_no_hurrycost, state.n_no_hurrycost, nsubmax_i,
                              sub_ge, cf_ge, state.hurry_cost)
        state.green_full_cost += mc * n_stan
        if flag_early_plants == 2:
            state.prudinv -= mc * n_stan

        if n_des > n_easy:
            for i in range(n_easy + 1, n_des + 1):
                mc = green_plant_cost(i, state.n_no_hurrycost, nsubmax_i,
                                      sub_ge, cf_ge, state.hurry_cost)
                state.green_full_cost += mc
                if flag_early_plants == 2:
                    state.prudinv -= mc

    def _expand_green_only(
        self, state: _BuildState, ei_en: int,
        cf_ge: float, sub_ge: float, nsubmax_i: int, flag_early_plants: int,
    ) -> None:
        """Build green plants to cover ``ei_en`` (brown banned, C++ :588-632)."""
        n_prev = state.new_green
        n_easy = min(ei_en, int(state.n_no_hurrycost))
        n_subs, n_stan = self._split_subsidised(n_prev, n_easy, nsubmax_i)

        mc = green_plant_cost(1, state.n_no_hurrycost, nsubmax_i, sub_ge, cf_ge, state.hurry_cost)
        state.new_green += n_subs
        state.green_full_cost += mc * n_subs
        if flag_early_plants == 2:
            state.prudinv -= mc * n_subs

        mc = green_plant_cost(state.n_no_hurrycost, state.n_no_hurrycost, nsubmax_i,
                              sub_ge, cf_ge, state.hurry_cost)
        state.new_green += n_stan
        state.green_full_cost += mc * n_stan
        if flag_early_plants == 2:
            state.prudinv -= mc * n_stan

        if ei_en > n_easy:
            for i in range(n_easy + 1, ei_en + 1):
                mc = green_plant_cost(i, state.n_no_hurrycost, nsubmax_i,
                                      sub_ge, cf_ge, state.hurry_cost)
                state.new_green += 1
                state.green_full_cost += mc
                if flag_early_plants == 2:
                    state.prudinv -= mc

    def _expand_with_brown_option(
        self, state: _BuildState, ei_en: int,
        cf_ge: float, cf_de: float, c_de: float, sub_ge: float, nsubmax_i: int,
        deadline_latebrown: float, payback: float, flag_early_plants: int,
    ) -> None:
        """Build green where cheaper than brown in payback terms (C++ :459-525).

        Brown fills whatever green declines to cover (computed by the caller).
        """
        n_prev = state.new_green
        n_easy = min(ei_en, int(state.n_no_hurrycost))
        n_subs, n_stan = self._split_subsidised(n_prev, n_easy, nsubmax_i)
        brown_alt = cf_de / deadline_latebrown + c_de
        unwill = False

        mc = green_plant_cost(1, state.n_no_hurrycost, nsubmax_i, sub_ge, cf_ge, state.hurry_cost)
        if mc / payback < brown_alt:
            state.new_green += n_subs
            state.green_full_cost += mc * n_subs
            if flag_early_plants == 2:
                state.prudinv -= mc * n_subs
        else:
            unwill = True

        mc = green_plant_cost(state.n_no_hurrycost, state.n_no_hurrycost, nsubmax_i,
                              sub_ge, cf_ge, state.hurry_cost)
        if mc / payback < brown_alt:
            state.new_green += n_stan
            state.green_full_cost += mc * n_stan
            if flag_early_plants == 2:
                state.prudinv -= mc * n_stan
        else:
            unwill = True

        if ei_en > n_easy:
            for i in range(n_easy + 1, ei_en + 1):
                if unwill:
                    break
                mc = green_plant_cost(i, state.n_no_hurrycost, nsubmax_i,
                                      sub_ge, cf_ge, state.hurry_cost)
                if mc / payback < brown_alt:
                    state.new_green += 1
                    state.green_full_cost += mc
                    if flag_early_plants == 2:
                        state.prudinv -= mc
                else:
                    unwill = True

    def decide_premature_replacement(
        self, t: int, ranked_brown: list, fuel_price: float, carbon_tax: float,
        gparams: "GlobalParameters", state: _BuildState, *,
        brown_banned: bool, deadline: float, k_green: float,
        cf_ge: float, cf_de: float, c_de: float, sub_ge: float, nsubmax_i: int,
    ) -> None:
        """Replace old brown plants with green where worthwhile (C++ :537-581/639-665).

        Walks brown vintages worst-first.  A brown unit is "replaced" by marking it
        inactive (``active_count -= 1``); under ``flag_early_plants2=0`` the unit is
        not scrapped, so ``count`` is unchanged and it stays in reserve.  Building
        green here is capped by ``prudinv`` (net-worth budget) and — when brown is
        allowed — by the green replacement quota and the deadline-discounted brown
        alternative.
        """
        p = gparams
        payback = p.green_plant_payback_threshold
        exp_quota = p.green_expansion_quota
        flag_early_plants = p.energy_premature_replacement_mode
        flag_early_plants2 = p.replaced_plants_scrapped
        n_lim1 = int(round(exp_quota * k_green))

        unwill = False
        for pl in reversed(ranked_brown):  # worst (most expensive) brown first
            if int(pl.active_count) < 1:
                continue
            for _ in range(int(pl.active_count)):
                unwill = True
                mc = green_plant_cost(state.new_green, n_lim1, nsubmax_i,
                                      sub_ge, cf_ge, state.hurry_cost)
                pl_unit_cost = pl.unit_cost(fuel_price, carbon_tax)

                if brown_banned:
                    do_replace = mc < pl_unit_cost * payback and state.prudinv > 0.0
                else:
                    do_replace = (
                        mc / payback < pl_unit_cost
                        and mc / payback < cf_de / deadline + c_de
                        and state.prudinv > 0.0
                        and state.replace_quota_green > 0
                    )

                if do_replace:
                    unwill = False
                    state.new_green += 1
                    state.green_full_cost += mc
                    if not brown_banned:
                        state.replace_quota_green -= 1
                    pl.active_count -= 1
                    if flag_early_plants2 == 1:
                        pl.count -= 1
                    state.plant_worth_lost += pl.building_cost * max(
                        (payback - (t - pl.vintage)) / payback, 0.0
                    )
                    if flag_early_plants == 2:
                        state.prudinv -= mc
                # flag_early_brown==0: brown-replaces-brown branch is not ported.

                if unwill:
                    break
            if unwill:
                break

    # ------------------------------------------------------------------
    # R&D phase (C++ ENERGY, :931-1204)
    # ------------------------------------------------------------------

    def do_rd(
        self,
        t: int,
        fuel_price: float,
        carbon_tax: float,
        wage: float,
        gparams: "GlobalParameters",
    ) -> None:
        """Run the energy-sector R&D phase (C++ ENERGY, module_energy.cpp:931-1204).

        Decides the R&D budget (endogenous green/dirty split under
        ``flag_share_END=1``), settles the producer's finances (revenue, profit,
        net worth, government bailout), runs the two-stage Schumpeterian
        innovation (Bernoulli success trials then Beta-distributed gains under
        ``flagRD=1`` worker-based success), and adopts any improved technology
        into next period's frontier.

        The frontier fields hold ``A_de(t)`` / ``EM_de(t)`` / ``CF_de(t)`` /
        ``CF_ge(t)`` on entry (the make to build from, set by
        :meth:`plan_capacity_expansion`'s best-historical selection — C++ :296-301)
        and are overwritten with ``A_de(t+1)`` etc. on exit.

        Reads ``electricity_price`` (c_en), ``total_energy_demand`` (D_en_TOT) and
        ``production_cost`` (PC_en) populated by dispatch, and the per-vintage
        ``expansion_cost_quota`` populated by expansion.  Government R&D top-up
        (``govt_rd_*``) is a baseline no-op; climate policy (milestone 5) sets it.

        Baseline flags: flag_share_END=1, flagRD=1 (worker-based success),
        flag_ff2em_en=0 (emissions per fuel held constant).  End-of-period
        plant scrapping (C++ :1210-1230) is deferred to the closeout wiring.
        """
        p = gparams
        rng = self.nation.rng
        payback = float(p.green_plant_payback_threshold)         # payback_en
        share_rd = p.energy_rd_share_of_revenue                  # share_RD_en
        o1_de = p.rd_coefficient_dirty_energy                    # o1_en_de
        o1_ge = p.rd_coefficient_clean_energy                    # o1_en_ge
        b_a1 = p.beta_innov_alpha
        b_b1 = p.beta_innov_beta
        flag_real_rd = p.rd_real_vs_nominal                      # flagRD (1 baseline)
        flag_share_end = p.endogenous_dirty_rd_share            # flag_share_END
        flag_ff2em = p.dirty_emissions_per_fuel_variable        # flag_ff2em_en

        # Innovation-gain supports (rescaled Beta draws).
        uu1_eede, uu2_eede = p.dirty_fuel_eff_innov_lower, p.dirty_fuel_eff_innov_upper
        uu1_cfde, uu2_cfde = p.dirty_buildcost_innov_lower, p.dirty_buildcost_innov_upper
        uu1_efde, uu2_efde = p.dirty_emission_innov_lower, p.dirty_emission_innov_upper
        # uu1_ge/uu2_ge never broaden in baseline (university research is *0), so
        # they stay at the initial support (C++ dsk_main.cpp:1131-1132).
        uu1_ge, uu2_ge = (
            p.green_buildcost_innov_lower_init,
            p.green_buildcost_innov_upper_init,
        )

        # Technology limits (floors carry inflation correction once 3.9 wires it).
        a_de_limlow = p.dirty_plant_inv_eff_floor               # A_de_limlow (1.6)
        cf_de_limlow = self.brown_build_cost_floor              # CF_de_limlow
        cf_ge_limlow = self.green_build_cost_floor              # CF_ge_limlow
        cf_ge_gov_limlow = self.green_build_cost_govt_floor     # CF_ge_gov_limlow
        em_de_limlow = p.dirty_plant_emission_floor            # EM_de_limlow
        em_de_limupp = p.dirty_plant_emission_ceil            # EM_de_limupp
        em_constant = p.fuel_to_emissions_factor * p.energy_emissivity_ratio_init  # EM0*ff2em

        # Frontier = A_de(t)/EM_de(t)/CF_de(t)/CF_ge(t).
        a_de = self.frontier_brown_thermal_ineff
        em_de = self.frontier_brown_emission_intensity
        cf_de = self.frontier_brown_build_cost
        cf_ge = self.frontier_green_build_cost

        self._update_capacity()
        k_green = float(self.total_green_capacity)
        k_dirty = float(self.total_brown_capacity)

        # --- IC_en: building outlay this period = quotas inside the payback window
        # (C++ :773-781).  The financial phase owns this summation.
        ic_en = sum(
            q for tt, q in self.expansion_cost_quota.items() if 0 <= t - tt <= payback
        )
        self.investment_cost = ic_en
        self.expansion_cost_green = ic_en
        self.labour_demand_expansion = ic_en / wage if wage > 0.0 else 0.0  # LDexp_en

        # --- Endogenous green/dirty R&D split (C++ :938-945).
        if flag_share_end == 1:
            total_cap = k_dirty + k_green
            share_de = k_dirty / total_cap if total_cap > 0.0 else p.dirty_rd_share_init
        else:
            share_de = p.dirty_rd_share_init
        self.dirty_rd_share = share_de

        # --- Revenue and R&D budget (C++ :948-993; the spin-up-innov ban is a
        # no-op since the C++ guard `t < t_spinup*0` is always false).
        rev_en = self.electricity_price * self.total_energy_demand
        self.revenue = rev_en

        dirty_at_limit = (a_de == a_de_limlow and cf_de == cf_de_limlow)
        if rev_en * share_rd < rev_en - self.production_cost:
            # Enough money: spend the fixed revenue share.
            rd_de = share_rd * share_de * rev_en
            rd_ge = share_rd * (1.0 - share_de) * rev_en
            if dirty_at_limit:
                rd_de = 0.0  # dirty R&D is pointless once dirty tech is maxed out
        else:
            # Not enough money: spend out of the margin until profits turn positive.
            rd_de = max(share_de * (rev_en - self.production_cost), 0.0)
            rd_ge = max((1.0 - share_de) * (rev_en - self.production_cost), 0.0)
            if dirty_at_limit:
                rd_de = 0.0
                rd_ge = min(
                    share_rd * (1.0 - share_de) * rev_en,
                    rev_en - self.production_cost - ic_en,
                )

        # Approaching a brown-investment ban: stop improving brown plants (C++ :988-992).
        if self.brown_invest_ban_year - t <= 0.5 * p.plant_lifetime_years:
            rd_ge += rd_de
            rd_de = 0.0

        # --- Government R&D top-up (baseline no-op; C++ :997-1006).
        rnd_funds_eff = self.govt_rd_funds_effective                  # RnD_funds_En_eff
        rd_gov_topup = (
            rd_ge * (self.govt_rd_multiplier_green - 1.0)
            + (rd_ge + rd_de) * self.govt_rd_all_multiplier
        )
        self.govt_rd_topup_total = rd_gov_topup
        self.govt_rd_grant_cost = rd_gov_topup + rnd_funds_eff
        rd_ge += rd_gov_topup + rnd_funds_eff

        # --- Totals, labour demand, profit (C++ :1008-1012).
        rd_gov_ge = self.govt_rd_for_green                           # RD_gov_ge
        rd_en = rd_de + rd_ge
        ld_rd_de = rd_de / wage if wage > 0.0 else 0.0
        ld_rd_ge = rd_ge / wage if wage > 0.0 else 0.0
        ld_rd_gov = rd_gov_ge / wage if wage > 0.0 else 0.0
        self.rd_spending_dirty = rd_de
        self.rd_spending_green = rd_ge
        self.rd_spending_total = rd_en
        self.labour_demand_rd_dirty = ld_rd_de
        self.labour_demand_rd_green = ld_rd_ge
        self.labour_demand_rd_total = ld_rd_de + ld_rd_ge + ld_rd_gov

        # Government funds and top-up are not a cost to the firm (C++ :1012).
        pi_en = rev_en - self.production_cost - ic_en - rd_de - (
            rd_ge - rnd_funds_eff - rd_gov_topup
        )
        self.profit = pi_en
        self.net_worth += pi_en

        # --- Bailout if insolvent (C++ :1019-1025).  Faithful to the C++ formula,
        # including its missing factor between CF_ge(t) and G_ge(t).
        if self.net_worth < 0.0:
            g_de_t = sum(int(pl.count) for pl in self.brown_plants if pl.vintage == t)
            g_ge_t = sum(int(pl.count) for pl in self.green_plants if pl.vintage == t)
            bailout = (cf_de * g_de_t + cf_ge + g_ge_t) * 0.05 - self.net_worth
            self.net_worth += bailout
        else:
            bailout = 0.0
        self.bailout_from_govt = bailout

        # --- Stage 1: Bernoulli innovation-success trials (C++ :1029-1050).
        # flagRD=1 (baseline): success probability scales with workers hired.
        if flag_real_rd == 1:
            sig_de, sig_ge, sig_gov = ld_rd_de, ld_rd_ge, ld_rd_gov / 10.0
        else:
            sig_de, sig_ge, sig_gov = rd_de, rd_ge, rd_gov_ge / 10.0

        parber_de = 1.0 - math.exp(-o1_de * sig_de)
        inn_de = self._bernoulli(rng, parber_de)
        self.innov_param_dirty = parber_de
        self.innov_success_dirty = float(inn_de)

        parber_ge = 1.0 - math.exp(-o1_ge * sig_ge)
        inn_ge = self._bernoulli(rng, parber_ge)
        self.innov_param_green = parber_ge
        self.innov_success_green = float(inn_ge)

        parber_gov = (1.0 - math.exp(-o1_ge * sig_gov)) * 0.2
        inn_gov_ge = self._bernoulli(rng, parber_gov)

        # --- Stage 2: Beta-distributed productivity gains (C++ :1060-1169).
        if inn_de:
            rnd = uu1_eede + float(rng.beta(b_a1, b_b1)) * (uu2_eede - uu1_eede)
            a_de_inn = max(a_de_limlow + (a_de - a_de_limlow) * (1.0 - rnd), a_de_limlow)

            rnd = uu1_cfde + float(rng.beta(b_a1, b_b1)) * (uu2_cfde - uu1_cfde)
            cf_de_inn = max(
                cf_de_limlow + (cf_de - cf_de_limlow) * (1.0 - rnd), cf_de_limlow
            )

            if flag_ff2em == 0:
                em_de_inn = em_constant  # constant fuel mix
            else:
                rnd = uu1_efde + float(rng.beta(b_a1, b_b1)) * (uu2_efde - uu1_efde)
                em_de_inn = em_de_limlow + (em_de - em_de_limlow) * (1.0 - rnd)
                em_de_inn = min(max(em_de_inn, em_de_limlow), em_de_limupp)
        else:
            a_de_inn, em_de_inn, cf_de_inn = a_de, em_de, cf_de

        if inn_ge and cf_ge > 0.0:
            rnd = uu1_ge + float(rng.beta(b_a1, b_b1)) * (uu2_ge - uu1_ge)
            cf_ge_inn = cf_ge_limlow + (cf_ge - cf_ge_limlow) * (1.0 - rnd)
            cf_ge_inn = max(cf_ge_inn, 0.0)
            cf_ge_inn = max(cf_ge_inn, cf_ge_limlow)
        else:
            cf_ge_inn = cf_ge

        if inn_gov_ge and cf_ge > cf_ge_gov_limlow:
            rnd = (uu1_ge + float(rng.beta(b_a1, b_b1)) * (uu2_ge - uu1_ge)) * 3.0
            rnd = min(rnd, 1.0)
            cf_ge_gov_inn = max(
                cf_ge_gov_limlow + (cf_ge - cf_ge_gov_limlow) * (1.0 - rnd),
                cf_ge_gov_limlow,
            )
        else:
            cf_ge_gov_inn = cf_ge

        # --- Adoption into next period's frontier (C++ :1175-1204; only if t<T).
        if t < p.total_steps:
            new_lifetime_cost = (
                cf_de_inn / payback
                + fuel_price * a_de_inn
                + carbon_tax * em_de_inn * a_de_inn
            )
            old_lifetime_cost = (
                cf_de / payback
                + fuel_price * a_de
                + carbon_tax * em_de * a_de
            )
            if new_lifetime_cost < old_lifetime_cost:
                self.frontier_brown_thermal_ineff = a_de_inn
                self.frontier_brown_emission_intensity = em_de_inn
                self.frontier_brown_build_cost = cf_de_inn

            cf_ge_next = cf_ge
            if cf_ge_inn < cf_ge:
                cf_ge_next = cf_ge_inn
            if cf_ge_gov_inn < cf_ge:
                cf_ge_next = cf_ge_gov_inn
            self.frontier_green_build_cost = cf_ge_next

    @staticmethod
    def _bernoulli(rng, p: float) -> bool:
        """Draw a single Bernoulli success (C++ bnldev(p,1)); guard p∉(0,1)."""
        p = min(max(p, 0.0), 1.0)
        return bool(rng.binomial(1, p)) if p > 0.0 else False
