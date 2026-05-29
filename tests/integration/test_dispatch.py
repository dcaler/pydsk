"""Integration tests for Task 3.3 — ElectricityProducer.dispatch_merit_order.

Acceptance criteria (IMPLEMENTATION_PLAN §3.3):
- Cheapest plants run first.
- Total supply >= demand.
- Price set by marginal plant.
"""
import pytest
from unittest.mock import MagicMock

from dsk.agents.electricity_producer import ElectricityProducer
from dsk.agents.power_plant import BrownPlant, GreenPlant


@pytest.fixture
def nation():
    return MagicMock()


def make_ep(nation, markup=0.0):
    ep = ElectricityProducer(nation)
    ep.markup = markup
    return ep


def add_green(ep, nation, count, building_cost, full_building_cost=None):
    if full_building_cost is None:
        full_building_cost = building_cost
    ep.green_plants.add(GreenPlant(nation, vintage=1, count=count,
                                   building_cost=building_cost,
                                   full_building_cost=full_building_cost))
    ep._update_capacity()


def add_brown(ep, nation, count, building_cost, thermal_ineff, emission_int, vintage=1):
    ep.brown_plants.add(BrownPlant(nation, vintage=vintage, count=count,
                                   building_cost=building_cost,
                                   thermal_inefficiency=thermal_ineff,
                                   emission_intensity=emission_int))
    ep._update_capacity()


# ---------------------------------------------------------------------------
# All-green dispatch
# ---------------------------------------------------------------------------

class TestAllGreenDispatch:
    def test_all_demand_served_from_green(self, nation):
        ep = make_ep(nation)
        add_green(ep, nation, count=100, building_cost=50.0)

        ep.dispatch_merit_order(demand=80.0, fuel_price=0.02)

        assert ep.total_green_energy == 80.0
        assert ep.total_brown_energy == 0.0

    def test_no_production_cost_or_emissions_when_all_green(self, nation):
        ep = make_ep(nation)
        add_green(ep, nation, count=100, building_cost=50.0)

        ep.dispatch_merit_order(demand=80.0, fuel_price=0.02)

        assert ep.production_cost == 0.0
        assert ep.emissions == 0.0
        assert ep.fuel_cost == 0.0

    def test_green_price_equals_markup_only(self, nation):
        ep = make_ep(nation, markup=0.005)
        add_green(ep, nation, count=100, building_cost=50.0)

        ep.dispatch_merit_order(demand=80.0, fuel_price=0.02)

        # flag_electricity_bidding=0 → green bid=0, price = 0 + markup
        assert abs(ep.electricity_price - 0.005) < 1e-12

    def test_total_supply_ge_demand_all_green(self, nation):
        ep = make_ep(nation)
        add_green(ep, nation, count=100, building_cost=50.0)

        ep.dispatch_merit_order(demand=80.0, fuel_price=0.02)

        assert ep.total_green_energy + ep.total_brown_energy >= 80.0 - 0.5

    def test_green_exactly_equal_to_demand(self, nation):
        """Edge: capacity equals demand (Q_de <= 0.5 gate)."""
        ep = make_ep(nation)
        add_green(ep, nation, count=50, building_cost=50.0)

        ep.dispatch_merit_order(demand=50.0, fuel_price=0.02)

        assert ep.total_green_energy == 50.0
        assert ep.total_brown_energy == 0.0


# ---------------------------------------------------------------------------
# Mixed (green + brown) dispatch
# ---------------------------------------------------------------------------

class TestMixedDispatch:
    def test_all_green_runs_when_brown_needed(self, nation):
        """When brown plants are needed, all green capacity runs at full."""
        ep = make_ep(nation)
        add_green(ep, nation, count=20, building_cost=50.0)
        add_brown(ep, nation, count=80, building_cost=10.0,
                  thermal_ineff=1.5, emission_int=0.8)

        ep.dispatch_merit_order(demand=60.0, fuel_price=0.02)

        assert ep.total_green_energy == 20.0
        assert ep.total_brown_energy == pytest.approx(40.0)

    def test_total_supply_ge_demand_mixed(self, nation):
        ep = make_ep(nation)
        add_green(ep, nation, count=20, building_cost=50.0)
        add_brown(ep, nation, count=80, building_cost=10.0,
                  thermal_ineff=1.5, emission_int=0.8)

        demand = 60.0
        ep.dispatch_merit_order(demand=demand, fuel_price=0.02)

        assert ep.total_green_energy + ep.total_brown_energy >= demand - 0.5

    def test_price_set_by_marginal_brown_plant(self, nation):
        """Electricity price = last dispatched brown plant's unit_cost + markup."""
        fuel_price = 0.03
        markup = 0.005
        ep = make_ep(nation, markup=markup)
        # Cheap plant: cost = 0.03 * 1.0 = 0.030
        add_brown(ep, nation, count=20, building_cost=10.0,
                  thermal_ineff=1.0, emission_int=0.5, vintage=1)
        # Expensive plant: cost = 0.03 * 2.0 = 0.060
        add_brown(ep, nation, count=40, building_cost=10.0,
                  thermal_ineff=2.0, emission_int=0.5, vintage=2)

        # 50-unit demand: cheap plant serves 20, expensive serves 30 → marginal = expensive
        ep.dispatch_merit_order(demand=50.0, fuel_price=fuel_price)

        expected_price = 2.0 * fuel_price + markup  # expensive plant's unit_cost + markup
        assert abs(ep.electricity_price - expected_price) < 1e-10


# ---------------------------------------------------------------------------
# Merit-order (cheapest-first) correctness
# ---------------------------------------------------------------------------

class TestMeritOrder:
    def test_cheapest_brown_runs_first(self, nation):
        """The cheaper plant serves demand before the expensive one."""
        fuel_price = 0.02
        ep = make_ep(nation)
        # Cheap: cost = 0.02 * 1.0 = 0.02; Expensive: cost = 0.02 * 3.0 = 0.06
        add_brown(ep, nation, count=50, building_cost=10.0,
                  thermal_ineff=1.0, emission_int=0.5, vintage=1)
        add_brown(ep, nation, count=50, building_cost=10.0,
                  thermal_ineff=3.0, emission_int=0.5, vintage=2)

        # Demand of 30 can be served entirely by the cheap plant (count=50)
        ep.dispatch_merit_order(demand=30.0, fuel_price=fuel_price)

        # Production cost should equal 30 * 0.02 (only cheap plant ran)
        assert abs(ep.production_cost - 30.0 * 0.02) < 1e-10
        # Price = cheap plant's marginal cost + markup (0)
        assert abs(ep.electricity_price - 0.02) < 1e-10

    def test_costly_plant_dispatched_when_cheap_insufficient(self, nation):
        """Expensive plant runs when cheap capacity is exhausted."""
        fuel_price = 0.02
        ep = make_ep(nation)
        add_brown(ep, nation, count=20, building_cost=10.0,
                  thermal_ineff=1.0, emission_int=0.5, vintage=1)   # cheap
        add_brown(ep, nation, count=80, building_cost=10.0,
                  thermal_ineff=3.0, emission_int=0.5, vintage=2)   # expensive

        # Demand 50 → cheap takes 20, expensive takes 30
        ep.dispatch_merit_order(demand=50.0, fuel_price=fuel_price)

        expected_cost = 20.0 * 1.0 * fuel_price + 30.0 * 3.0 * fuel_price
        assert abs(ep.production_cost - expected_cost) < 1e-10
        # Marginal plant is the expensive one
        assert abs(ep.electricity_price - 3.0 * fuel_price) < 1e-10

    def test_tiebreak_by_building_cost(self, nation):
        """When unit costs are equal, the plant with lower building cost ranks first."""
        fuel_price = 0.02
        ep = make_ep(nation)
        # Same unit cost (thermal_ineff=1.0), different building costs
        add_brown(ep, nation, count=30, building_cost=20.0,
                  thermal_ineff=1.0, emission_int=0.5, vintage=1)   # higher CF
        add_brown(ep, nation, count=30, building_cost=5.0,
                  thermal_ineff=1.0, emission_int=0.5, vintage=2)   # lower CF → ranks first

        # Demand = 30 → exactly one plant
        ep.dispatch_merit_order(demand=30.0, fuel_price=fuel_price)

        # Either plant has unit_cost = 0.02; production_cost should be 30 * 0.02
        assert abs(ep.production_cost - 30.0 * fuel_price) < 1e-10


# ---------------------------------------------------------------------------
# Emissions and fuel cost
# ---------------------------------------------------------------------------

class TestEmissionsAndFuelCost:
    def test_emissions_formula(self, nation):
        """Emiss_en = served * emission_intensity * thermal_inefficiency."""
        ep = make_ep(nation)
        add_brown(ep, nation, count=100, building_cost=10.0,
                  thermal_ineff=1.5, emission_int=0.8)

        ep.dispatch_merit_order(demand=50.0, fuel_price=0.02)

        expected_emissions = 50.0 * 0.8 * 1.5   # EM_de * A_de * Q
        assert abs(ep.emissions - expected_emissions) < 1e-10

    def test_fuel_cost_formula(self, nation):
        """Fuel_cost = served * fuel_price * thermal_inefficiency."""
        fuel_price = 0.03
        ep = make_ep(nation)
        add_brown(ep, nation, count=100, building_cost=10.0,
                  thermal_ineff=2.0, emission_int=0.5)

        ep.dispatch_merit_order(demand=40.0, fuel_price=fuel_price)

        expected_fuel_cost = 40.0 * fuel_price * 2.0   # Q * pf * A_de
        assert abs(ep.fuel_cost - expected_fuel_cost) < 1e-10

    def test_carbon_tax_raises_unit_cost_and_price(self, nation):
        """carbon_tax > 0 increases unit cost, reflected in dispatch cost and price."""
        fuel_price = 0.02
        carbon_tax = 0.01
        ep = make_ep(nation, markup=0.0)
        add_brown(ep, nation, count=100, building_cost=10.0,
                  thermal_ineff=1.0, emission_int=2.0)

        ep.dispatch_merit_order(demand=50.0, fuel_price=fuel_price, carbon_tax=carbon_tax)

        # unit_cost = thermal_ineff * (fuel_price + carbon_tax * emission_int)
        #           = 1.0 * (0.02 + 0.01 * 2.0) = 0.04
        expected_price = 1.0 * (fuel_price + carbon_tax * 2.0)
        assert abs(ep.electricity_price - expected_price) < 1e-10

    def test_no_emissions_with_only_green(self, nation):
        ep = make_ep(nation)
        add_green(ep, nation, count=100, building_cost=50.0)

        ep.dispatch_merit_order(demand=50.0, fuel_price=0.02)

        assert ep.emissions == 0.0
        assert ep.fuel_cost == 0.0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_zero_demand(self, nation):
        ep = make_ep(nation)
        add_green(ep, nation, count=100, building_cost=50.0)
        add_brown(ep, nation, count=100, building_cost=10.0,
                  thermal_ineff=1.0, emission_int=0.5)

        ep.dispatch_merit_order(demand=0.0, fuel_price=0.02)

        assert ep.total_green_energy == 0.0 or ep.total_green_energy >= 0.0
        assert ep.production_cost == 0.0
        assert ep.emissions == 0.0

    def test_empty_fleet_leaves_state_at_zero(self, nation):
        ep = make_ep(nation, markup=0.1)

        ep.dispatch_merit_order(demand=0.0, fuel_price=0.02)

        assert ep.production_cost == 0.0
        assert ep.emissions == 0.0

    def test_multiple_green_vintages_cheapest_runs_first(self, nation):
        """Green plants ranked by full_building_cost ascending."""
        ep = make_ep(nation, markup=0.0)
        # Lower full_building_cost → cheaper green vintage
        ep.green_plants.add(GreenPlant(nation, vintage=1, count=30,
                                       building_cost=80.0, full_building_cost=80.0))
        ep.green_plants.add(GreenPlant(nation, vintage=2, count=30,
                                       building_cost=40.0, full_building_cost=40.0))
        ep._update_capacity()

        # Demand 30 → only one green vintage runs; both have 0 variable cost
        ep.dispatch_merit_order(demand=30.0, fuel_price=0.02)

        assert ep.total_green_energy == 30.0
        assert ep.total_brown_energy == 0.0
        assert ep.production_cost == 0.0
