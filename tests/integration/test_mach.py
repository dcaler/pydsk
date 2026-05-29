"""Integration tests for Task 1.5: MACH (machine delivery).

Ports C++ dsk_main.cpp MACH() for flag_clim_tech==0.

Deviation from IMPLEMENTATION_PLAN.md Task 1.5:
  The plan says MACH "pays for them out of net worth and credit, kills firms with
  negative net worth." In the CURRENT C++ codebase, the payment block was removed
  from MACH ('**new** ==> eliminate round of credit that was here', lines 2529-2590).
  Payment now happens in ALLOCATECREDIT (Task 1.8). No firm death occurs in MACH.
  These tests verify only what the current C++ MACH actually does:
    - Capital-good firm price/cost update.
    - Pending machines delivered into MachineStock.
    - Capital stock K updated (expansion investment part).
    - A2, c2, mu2, p2 recomputed on s2 firms.
"""
import pytest

from dsk.agents.capital_good_firm import CapitalGoodFirm
from dsk.agents.consumption_good_firm import ConsumptionGoodFirm
from dsk.agents.electricity_producer import _electdemand, _ffueldemand
from dsk.agents.firm_costs import cost_sect1
from dsk.agents.technology import Technology
from dsk.nation import Nation
from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters
from dsk.simulation import Simulation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_nation_with_firms(n1: int = 3, n2: int = 6, seed: int = 42):
    """Return (sim, nation, s1_firms, s2_firms) with all firms initialised."""
    gparams = GlobalParameters()
    gparams.n1_capital_good_firms = n1
    gparams.n2_consumption_good_firms = n2

    nparams = NationParameters()
    nation = Nation(nation_id="test", params=nparams)
    sim = Simulation(gparams, [nation], rng_seed=seed)

    s1_firms = []
    for _ in range(n1):
        f = CapitalGoodFirm(nation, nation.rng)
        f.initialise_from_parameters(gparams)
        nation.capital_good_sector.add(f)
        s1_firms.append(f)

    counter = 0
    s2_firms = []
    for j in range(n2):
        f = ConsumptionGoodFirm(nation, nation.rng)
        counter = f.initialise_from_parameters(gparams, nparams, j % n1, 0, counter)
        nation.consumption_good_sector.add(f)
        s2_firms.append(f)

    return sim, nation, s1_firms, s2_firms


# ---------------------------------------------------------------------------
# Tests: capital-good firm price/cost update
# ---------------------------------------------------------------------------

class TestCapitalFirmPriceUpdate:
    def test_price_cost_updated_from_wage(self):
        """MACH recomputes c1 and p1 from current wage."""
        gparams = GlobalParameters()
        nparams = NationParameters()
        nation = Nation("t", nparams)
        sim = Simulation(gparams, [nation], 0)

        s1 = CapitalGoodFirm(nation, nation.rng)
        s1.initialise_from_parameters(gparams)
        nation.capital_good_sector.add(s1)

        # Simulate wage increase from 1.0 to 1.1
        nation.labour_market.wage = 1.1

        # Deliver (no s2 firms; only s1 update runs)
        nation.deliver_machines()

        # Expected cost includes fossil fuel term (DSK17 baseline, elec_price_prev=0.0)
        wage = 1.1
        a = gparams.s1_productivity_scale        # 0.1
        mi1 = gparams.s1_markup                 # 0.04
        elf = gparams.electrification_fraction_init_s1
        en = gparams.energy_need_init * gparams.s1_energy_need_init_factor
        phi = gparams.fuel_to_electricity_equivalence
        rule = gparams.fuel_to_elec_rule
        eld = _electdemand(elf, en, phi, rule)
        ffd = _ffueldemand(elf, en, phi, rule)
        expected_c1 = cost_sect1(
            wage_net=wage,
            process_prod=1.0 * a,   # A0=1.0
            elec_demand_per_unit=eld,
            elec_price=0.0,         # electricity_price_prev=0.0 (not initialised in test)
            fossil_demand_per_unit=ffd,
            fossil_price=nparams.fossil_fuel_price,
            ff2em=gparams.fuel_to_emissions_factor,
            env_filthiness=gparams.env_filthiness_init * gparams.allow_proc_emissions_s1,
        )
        expected_p1 = (1 + mi1) * expected_c1

        assert s1.unit_cost == pytest.approx(expected_c1)
        assert s1.price == pytest.approx(expected_p1)

    def test_s1_sales_reset_to_zero(self):
        """MACH resets S1(1,i) = 0 for every capital-good firm."""
        gparams = GlobalParameters()
        nparams = NationParameters()
        nation = Nation("t", nparams)
        sim = Simulation(gparams, [nation], 0)

        s1 = CapitalGoodFirm(nation, nation.rng)
        s1.initialise_from_parameters(gparams)
        s1.sales = 999.0  # pre-set some sales
        nation.capital_good_sector.add(s1)

        nation.deliver_machines()

        assert s1.sales == 0.0

    def test_sector_means_computed(self):
        """Sector-mean price, unit cost, and mean productivity are set."""
        sim, nation, s1_firms, _ = _make_nation_with_firms(n1=3, n2=0)

        nation.deliver_machines()

        cgs = nation.capital_good_sector
        assert cgs.mean_price > 0
        assert cgs.mean_unit_cost > 0
        assert cgs.mean_machine_labour_prod > 0


# ---------------------------------------------------------------------------
# Tests: pending machine delivery into MachineStock
# ---------------------------------------------------------------------------

class TestMachineDelivery:
    def test_pending_machines_added_to_stock(self):
        """Pending order is added to the MachineStock after deliver_machines()."""
        sim, nation, s1_firms, s2_firms = _make_nation_with_firms(n1=3, n2=1)
        firm = s2_firms[0]
        gparams = nation.gparams

        initial_count = firm.machines.total_machines()

        tech = Technology(labour_productivity=1.2)
        firm.pending_order_n_machines = 4.0
        firm.pending_expansion_investment = 4.0 * gparams.machine_size_units
        firm.pending_order_supplier_idx = 0
        firm.pending_order_vintage = 1
        firm.pending_order_technology = tech

        nation.deliver_machines()

        assert firm.machines.total_machines() == pytest.approx(initial_count + 4.0)
        assert firm.machines.count_at(1, 0) == pytest.approx(4.0)

    def test_capital_stock_updated_by_expansion(self):
        """K(j) increases by the expansion investment amount (EI(2,j))."""
        sim, nation, s1_firms, s2_firms = _make_nation_with_firms(n1=3, n2=1)
        firm = s2_firms[0]
        gparams = nation.gparams

        initial_K = firm.capital_stock
        expansion = 3.0 * gparams.machine_size_units

        firm.pending_order_n_machines = 3.0
        firm.pending_expansion_investment = expansion
        firm.pending_order_supplier_idx = 0
        firm.pending_order_vintage = 2
        firm.pending_order_technology = Technology(labour_productivity=1.0)

        nation.deliver_machines()

        assert firm.capital_stock == pytest.approx(initial_K + expansion)

    def test_n_machines_updated(self):
        """n_machines field reflects the new total after delivery."""
        sim, nation, s1_firms, s2_firms = _make_nation_with_firms(n1=3, n2=1)
        firm = s2_firms[0]

        firm.pending_order_n_machines = 5.0
        firm.pending_expansion_investment = 5.0 * nation.gparams.machine_size_units
        firm.pending_order_supplier_idx = 1
        firm.pending_order_vintage = 3
        firm.pending_order_technology = Technology(labour_productivity=1.0)

        nation.deliver_machines()

        assert firm.n_machines == pytest.approx(firm.machines.total_machines())

    def test_pending_state_cleared_after_delivery(self):
        """Pending order fields are reset to zero after delivery."""
        sim, nation, s1_firms, s2_firms = _make_nation_with_firms(n1=3, n2=1)
        firm = s2_firms[0]

        firm.pending_order_n_machines = 2.0
        firm.pending_expansion_investment = 2.0 * nation.gparams.machine_size_units
        firm.pending_order_supplier_idx = 0
        firm.pending_order_vintage = 1
        firm.pending_order_technology = Technology(labour_productivity=1.0)

        nation.deliver_machines()

        assert firm.pending_order_n_machines == 0.0
        assert firm.pending_expansion_investment == 0.0
        assert firm.pending_order_supplier_idx == -1
        assert firm.pending_order_vintage == -1
        assert firm.pending_order_technology is None

    def test_no_order_leaves_stock_unchanged(self):
        """If pending_order_n_machines==0, MachineStock is unchanged."""
        sim, nation, s1_firms, s2_firms = _make_nation_with_firms(n1=3, n2=1)
        firm = s2_firms[0]
        before = firm.machines.total_machines()

        nation.deliver_machines()

        assert firm.machines.total_machines() == pytest.approx(before)


# ---------------------------------------------------------------------------
# Tests: productivity, cost, markup, price recomputation
# ---------------------------------------------------------------------------

class TestProductivityAndPriceRecompute:
    def test_effective_labour_prod_recomputed(self):
        """A2(j) is recomputed as harmonic mean of machine productivities."""
        sim, nation, s1_firms, s2_firms = _make_nation_with_firms(n1=3, n2=1)
        firm = s2_firms[0]

        # Add a higher-productivity machine from vintage 1
        tech_high = Technology(labour_productivity=2.0)
        firm.pending_order_n_machines = 10.0
        firm.pending_expansion_investment = 10.0 * nation.gparams.machine_size_units
        firm.pending_order_supplier_idx = 0
        firm.pending_order_vintage = 1
        firm.pending_order_technology = tech_high

        nation.deliver_machines()

        # Harmonic mean over mixed stock (20 baseline + 10 high-productivity)
        # must be between 1.0 (baseline) and 2.0
        assert 1.0 < firm.effective_labour_prod < 2.0

    def test_unit_cost_recomputed(self):
        """c2(j) is recomputed as weighted average of machine unit costs."""
        gparams = GlobalParameters()
        nparams = NationParameters()
        nation = Nation("t", nparams)
        sim = Simulation(gparams, [nation], 0)

        s1 = CapitalGoodFirm(nation, nation.rng)
        s1.initialise_from_parameters(gparams)
        nation.capital_good_sector.add(s1)

        s2 = ConsumptionGoodFirm(nation, nation.rng)
        s2.initialise_from_parameters(gparams, nparams, 0, 0, 0)
        nation.consumption_good_sector.add(s2)

        # At init: all machines have A=1.0, wage=1.0 → c2 = w/A = 1.0
        nation.deliver_machines()

        assert s2.unit_cost == pytest.approx(1.0)

    def test_price_equals_markup_times_cost(self):
        """p2(j) = (1+mu2(j)) * c2(j) after MACH."""
        sim, nation, s1_firms, s2_firms = _make_nation_with_firms(n1=3, n2=1)
        firm = s2_firms[0]

        nation.deliver_machines()

        expected_price = (1.0 + firm.markup) * firm.unit_cost
        assert firm.price == pytest.approx(expected_price)

    def test_markup_unchanged_when_no_history(self):
        """mu2 stays at mi2 on the first period (f2(3,j)==0 so update is skipped)."""
        gparams = GlobalParameters()
        nparams = NationParameters()
        nation = Nation("t", nparams)
        sim = Simulation(gparams, [nation], 0)

        s1 = CapitalGoodFirm(nation, nation.rng)
        s1.initialise_from_parameters(gparams)
        nation.capital_good_sector.add(s1)

        s2 = ConsumptionGoodFirm(nation, nation.rng)
        s2.initialise_from_parameters(gparams, nparams, 0, 0, 0)
        nation.consumption_good_sector.add(s2)

        mi2 = nparams.s2_markup_init   # 0.2
        nation.deliver_machines()

        assert s2.markup == pytest.approx(mi2)

    def test_markup_increases_when_share_gained(self):
        """mu2 increases if f2(2,j) > f2(3,j) (firm gained market share)."""
        gparams = GlobalParameters()
        nparams = NationParameters()
        nation = Nation("t", nparams)
        sim = Simulation(gparams, [nation], 0)

        s1 = CapitalGoodFirm(nation, nation.rng)
        s1.initialise_from_parameters(gparams)
        nation.capital_good_sector.add(s1)

        s2 = ConsumptionGoodFirm(nation, nation.rng)
        s2.initialise_from_parameters(gparams, nparams, 0, 0, 0)
        nation.consumption_good_sector.add(s2)

        # Simulate a period where the firm gained market share
        s2.market_share_prev = 0.003        # f2(2,j) = higher than initial
        s2.market_share_prev_prev = 0.002   # f2(3,j) = previous

        mi2_before = s2.markup
        nation.deliver_machines()

        assert s2.markup > mi2_before

    def test_markup_decreases_when_share_lost(self):
        """mu2 decreases if f2(2,j) < f2(3,j) (firm lost market share)."""
        gparams = GlobalParameters()
        nparams = NationParameters()
        nation = Nation("t", nparams)
        sim = Simulation(gparams, [nation], 0)

        s1 = CapitalGoodFirm(nation, nation.rng)
        s1.initialise_from_parameters(gparams)
        nation.capital_good_sector.add(s1)

        s2 = ConsumptionGoodFirm(nation, nation.rng)
        s2.initialise_from_parameters(gparams, nparams, 0, 0, 0)
        nation.consumption_good_sector.add(s2)

        s2.market_share_prev = 0.001        # f2(2,j) = lower
        s2.market_share_prev_prev = 0.003   # f2(3,j) = higher

        mi2_before = s2.markup
        nation.deliver_machines()

        assert s2.markup < mi2_before

    def test_price_floor_applied(self):
        """Price is at least pmin even if (1+mu2)*c2 would be smaller."""
        gparams = GlobalParameters()
        nparams = NationParameters()
        nation = Nation("t", nparams)
        sim = Simulation(gparams, [nation], 0)

        s1 = CapitalGoodFirm(nation, nation.rng)
        s1.initialise_from_parameters(gparams)
        nation.capital_good_sector.add(s1)

        s2 = ConsumptionGoodFirm(nation, nation.rng)
        s2.initialise_from_parameters(gparams, nparams, 0, 0, 0)
        nation.consumption_good_sector.add(s2)

        # Force a tiny markup so price would be < pmin without the floor
        s2.markup = 1e-6
        nation.labour_market.wage = 1e-6   # tiny wage → tiny c2

        nation.deliver_machines()

        assert s2.price >= gparams.firm_price_floor

    def test_new_entrant_skips_update(self):
        """New entrant (is_new_entrant=True) skips productivity/price recompute."""
        gparams = GlobalParameters()
        nparams = NationParameters()
        nation = Nation("t", nparams)
        sim = Simulation(gparams, [nation], 0)

        s1 = CapitalGoodFirm(nation, nation.rng)
        s1.initialise_from_parameters(gparams)
        nation.capital_good_sector.add(s1)

        s2 = ConsumptionGoodFirm(nation, nation.rng)
        s2.initialise_from_parameters(gparams, nparams, 0, 0, 0)
        s2.is_new_entrant = True
        original_price = s2.price
        original_markup = s2.markup
        nation.consumption_good_sector.add(s2)

        nation.deliver_machines()

        assert s2.price == pytest.approx(original_price)
        assert s2.markup == pytest.approx(original_markup)


# ---------------------------------------------------------------------------
# Tests: multiple firms, no cross-contamination
# ---------------------------------------------------------------------------

class TestMultipleFirms:
    def test_multiple_s2_firms_all_updated(self):
        """All s2 firms receive the MACH update in one deliver_machines() call."""
        sim, nation, s1_firms, s2_firms = _make_nation_with_firms(n1=3, n2=6)

        nation.deliver_machines()

        for firm in s2_firms:
            assert firm.unit_cost > 0
            assert firm.price > 0
            assert firm.effective_labour_prod > 0

    def test_multiple_s2_deliveries_independent(self):
        """Different pending orders for different firms don't bleed into each other."""
        sim, nation, s1_firms, s2_firms = _make_nation_with_firms(n1=3, n2=2)
        f0, f1 = s2_firms[0], s2_firms[1]
        gparams = nation.gparams

        # Only firm 0 has a pending order
        f0.pending_order_n_machines = 2.0
        f0.pending_expansion_investment = 2.0 * gparams.machine_size_units
        f0.pending_order_supplier_idx = 0
        f0.pending_order_vintage = 5
        f0.pending_order_technology = Technology(labour_productivity=1.5)

        before_f1 = f1.machines.total_machines()
        nation.deliver_machines()

        assert f0.machines.count_at(5, 0) == pytest.approx(2.0)
        assert f1.machines.total_machines() == pytest.approx(before_f1)
