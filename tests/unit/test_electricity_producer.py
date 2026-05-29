"""Task 3.2 acceptance tests: ElectricityProducer, GreenPlantSet, BrownPlantSet.

Acceptance criterion: initial plants seeded so green share matches K_ge0_perc.

Key parameter values (defaults from GlobalParameters):
  green_capacity_share_init  = 0.0   (baseline: all brown)
  dirty_rd_share_init        = 0.6
  energy_markup_init         = 0.1
  energy_cost_init_box_off   = 0.001
  dirty_plant_one_over_eff_init = 2.5   (A_de0)
  fuel_to_emissions_factor   = 1100.0   (ff2em)
  energy_emissivity_ratio_init = 1.0    (EM0)
  => initial emission_intensity = 1100.0
"""
import math
import pytest

from dsk.agents.electricity_producer import (
    BrownPlantSet,
    ElectricityProducer,
    GreenPlantSet,
)
from dsk.agents.power_plant import BrownPlant, GreenPlant
from dsk.parameters.global_parameters import GlobalParameters


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class _MockNation:
    """Minimal stand-in for Nation."""


@pytest.fixture()
def nation():
    return _MockNation()


@pytest.fixture()
def gparams():
    return GlobalParameters()


@pytest.fixture()
def producer(nation):
    return ElectricityProducer(nation)


@pytest.fixture()
def initialised_producer(nation, gparams):
    ep = ElectricityProducer(nation)
    ep.initialise_from_parameters(gparams)
    return ep


# ---------------------------------------------------------------------------
# GreenPlantSet
# ---------------------------------------------------------------------------

class TestGreenPlantSet:
    def test_empty_total_capacity(self):
        s = GreenPlantSet()
        assert s.total_capacity() == 0

    def test_total_capacity_sums_counts(self, nation):
        s = GreenPlantSet()
        s.add(GreenPlant(nation, vintage=1, count=200, building_cost=10.0))
        s.add(GreenPlant(nation, vintage=2, count=300, building_cost=10.0))
        assert s.total_capacity() == 500

    def test_inflation_adjust_propagates(self, nation):
        s = GreenPlantSet()
        s.add(GreenPlant(nation, vintage=1, count=10, building_cost=10.0))
        s.inflation_adjust(1.05)
        p = list(s)[0]
        assert p.building_cost == pytest.approx(10.0 * 1.05)

    def test_retire_old_removes_expired(self, nation):
        s = GreenPlantSet()
        s.add(GreenPlant(nation, vintage=1, count=10, building_cost=10.0))
        s.add(GreenPlant(nation, vintage=50, count=10, building_cost=10.0))
        s.retire_old(current_t=61, life_plant=60)
        assert len(s) == 1
        assert list(s)[0].vintage == 50

    def test_retire_old_keeps_young(self, nation):
        s = GreenPlantSet()
        s.add(GreenPlant(nation, vintage=10, count=5, building_cost=10.0))
        s.retire_old(current_t=20, life_plant=60)
        assert len(s) == 1

    def test_is_agentset_subclass(self):
        from dsk.agent_set import AgentSet
        assert issubclass(GreenPlantSet, AgentSet)


# ---------------------------------------------------------------------------
# BrownPlantSet
# ---------------------------------------------------------------------------

class TestBrownPlantSet:
    def _make_plant(self, nation, count=100, active_count=None):
        p = BrownPlant(nation, vintage=1, count=count, building_cost=2.0,
                       thermal_inefficiency=2.5, emission_intensity=1100.0)
        if active_count is not None:
            p.active_count = active_count
        return p

    def test_empty_total_capacity(self):
        s = BrownPlantSet()
        assert s.total_capacity() == 0

    def test_total_capacity_sums_counts(self, nation):
        s = BrownPlantSet()
        s.add(self._make_plant(nation, count=1000))
        s.add(self._make_plant(nation, count=500))
        assert s.total_capacity() == 1500

    def test_total_active_capacity(self, nation):
        s = BrownPlantSet()
        s.add(self._make_plant(nation, count=200, active_count=150))
        s.add(self._make_plant(nation, count=100, active_count=80))
        assert s.total_active_capacity() == 230

    def test_inflation_adjust_propagates(self, nation):
        s = BrownPlantSet()
        s.add(self._make_plant(nation))
        s.inflation_adjust(1.03)
        assert list(s)[0].building_cost == pytest.approx(2.0 * 1.03)

    def test_retire_old_removes_expired(self, nation):
        s = BrownPlantSet()
        s.add(BrownPlant(nation, vintage=1, count=10, building_cost=2.0,
                         thermal_inefficiency=2.5, emission_intensity=1100.0))
        s.add(BrownPlant(nation, vintage=40, count=10, building_cost=2.0,
                         thermal_inefficiency=2.5, emission_intensity=1100.0))
        s.retire_old(current_t=61, life_plant=60)
        assert len(s) == 1
        assert list(s)[0].vintage == 40

    def test_merit_order_cheapest_first(self, nation):
        s = BrownPlantSet()
        cheap = BrownPlant(nation, vintage=5, count=10, building_cost=2.0,
                           thermal_inefficiency=2.0, emission_intensity=1100.0)
        expensive = BrownPlant(nation, vintage=1, count=10, building_cost=2.0,
                               thermal_inefficiency=3.0, emission_intensity=1100.0)
        s.add(expensive)
        s.add(cheap)
        ordered = s.merit_order(fuel_price=0.02, carbon_tax=0.0)
        assert ordered[0].thermal_inefficiency == pytest.approx(2.0)
        assert ordered[1].thermal_inefficiency == pytest.approx(3.0)

    def test_is_agentset_subclass(self):
        from dsk.agent_set import AgentSet
        assert issubclass(BrownPlantSet, AgentSet)


# ---------------------------------------------------------------------------
# ElectricityProducer — constructor
# ---------------------------------------------------------------------------

class TestElectricityProducerConstructor:
    def test_plant_sets_are_typed(self, producer):
        assert isinstance(producer.green_plants, GreenPlantSet)
        assert isinstance(producer.brown_plants, BrownPlantSet)

    def test_initial_fleets_empty(self, producer):
        assert len(producer.green_plants) == 0
        assert len(producer.brown_plants) == 0

    def test_financial_state_zero(self, producer):
        assert producer.net_worth == 0.0
        assert producer.profit == 0.0
        assert producer.revenue == 0.0

    def test_rd_state_zero(self, producer):
        assert producer.rd_spending_total == 0.0
        assert producer.rd_spending_green == 0.0
        assert producer.rd_spending_dirty == 0.0

    def test_capacity_zero(self, producer):
        assert producer.total_green_capacity == 0
        assert producer.total_brown_capacity == 0

    def test_green_share_empty(self, producer):
        assert producer.green_share() == 0.0


# ---------------------------------------------------------------------------
# ElectricityProducer — initialise_from_parameters (acceptance criterion)
# ---------------------------------------------------------------------------

class TestInitialiseFromParameters:
    def test_baseline_all_brown(self, initialised_producer, gparams):
        """K_ge0_perc = 0.0 → no green plants, all brown."""
        assert gparams.green_capacity_share_init == 0.0
        ep = initialised_producer
        assert len(ep.green_plants) == 0
        assert len(ep.brown_plants) == 1
        assert ep.green_share() == pytest.approx(0.0)

    def test_total_plants_positive(self, initialised_producer):
        ep = initialised_producer
        total = ep.total_green_capacity + ep.total_brown_capacity
        assert total > 0

    def test_green_share_matches_k_ge0_perc(self, nation, gparams):
        """Acceptance criterion: green share matches K_ge0_perc after init."""
        gparams.green_capacity_share_init = 0.2
        ep = ElectricityProducer(nation)
        ep.initialise_from_parameters(gparams)
        assert ep.green_share() == pytest.approx(0.2, abs=1e-3)

    def test_green_share_half(self, nation, gparams):
        gparams.green_capacity_share_init = 0.5
        ep = ElectricityProducer(nation)
        ep.initialise_from_parameters(gparams)
        assert ep.green_share() == pytest.approx(0.5, abs=1e-3)

    def test_green_share_full_green(self, nation, gparams):
        gparams.green_capacity_share_init = 1.0
        ep = ElectricityProducer(nation)
        ep.initialise_from_parameters(gparams)
        assert len(ep.brown_plants) == 0
        assert ep.green_share() == pytest.approx(1.0)

    def test_brown_plant_emission_intensity(self, initialised_producer, gparams):
        """EM_de0 = ff2em * EM0 = 1100.0 * 1.0 = 1100.0"""
        ep = initialised_producer
        plant = list(ep.brown_plants)[0]
        expected = gparams.fuel_to_emissions_factor * gparams.energy_emissivity_ratio_init
        assert plant.emission_intensity == pytest.approx(expected)

    def test_brown_plant_thermal_inefficiency(self, initialised_producer, gparams):
        ep = initialised_producer
        plant = list(ep.brown_plants)[0]
        assert plant.thermal_inefficiency == pytest.approx(gparams.dirty_plant_one_over_eff_init)

    def test_markup_set(self, initialised_producer, gparams):
        assert initialised_producer.markup == pytest.approx(gparams.energy_markup_init)

    def test_dirty_rd_share_set(self, initialised_producer, gparams):
        assert initialised_producer.dirty_rd_share == pytest.approx(gparams.dirty_rd_share_init)

    def test_electricity_price_set(self, initialised_producer, gparams):
        assert initialised_producer.electricity_price == pytest.approx(
            gparams.energy_cost_init_box_off
        )

    def test_demand_history_length(self, initialised_producer):
        assert len(initialised_producer.demand_history) == 12

    def test_capacity_updated_after_init(self, initialised_producer):
        ep = initialised_producer
        total_from_sets = (
            ep.green_plants.total_capacity() + ep.brown_plants.total_capacity()
        )
        assert ep.total_green_capacity + ep.total_brown_capacity == total_from_sets

    def test_cost_floors_set(self, initialised_producer, gparams):
        ep = initialised_producer
        assert ep.green_build_cost_floor == pytest.approx(
            gparams.green_plant_build_cost_floor_init
        )
        assert ep.brown_build_cost_floor == pytest.approx(
            gparams.dirty_plant_build_cost_floor_init
        )
        assert ep.green_build_cost_govt_floor == pytest.approx(
            gparams.green_plant_build_cost_govt_floor_init
        )
