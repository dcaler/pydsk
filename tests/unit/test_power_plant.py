"""Task 3.1 acceptance tests: PowerPlant, GreenPlant, BrownPlant.

Acceptance criterion: construct a few plants; unit_cost(fuel_price, carbon_tax)
returns expected values.

Reference constants from dsk_constant.h:
  pf0       = 0.03 / 1.5   ≈ 0.020   (initial fossil fuel price)
  A_de0     = 2.5           (initial thermal inefficiency, fuel per unit energy)
  EM0       = 1.0           (ratio emissivity energy vs industry)
  ff2em     = 1100          (emissions per unit fossil fuel, industry scaling)
  t_CO2_en  = 0.0           (carbon tax energy sector — zero at baseline)

Derived:
  CF_de0 = A_de0 * pf0 * life_plant * 2/3 = 2.5 * 0.02 * 60 * 2/3 = 2.0
  CF_ge0 = A_de0 * pf0 * life_plant * 5/3 * 2 = 2.5 * 0.02 * 60 * 10/3 = 10.0
  C_de   = pf * A_de + t_CO2_en * EM_de * A_de = 0.02 * 2.5 = 0.05 (no tax)
"""
import pytest

from dsk.agents.power_plant import BrownPlant, GreenPlant, PowerPlant


# ---------------------------------------------------------------------------
# Constants mirrored from dsk_constant.h
# ---------------------------------------------------------------------------
PF0 = 0.03 / 1.5          # initial fossil fuel price
A_DE0 = 2.5                # initial thermal inefficiency
EM_DE0 = 1100.0            # ff2em * EM0 = emissions per unit fuel (energy sector)
LIFE_PLANT = 60
CF_DE0 = A_DE0 * PF0 * LIFE_PLANT * 2 / 3   # ≈ 2.0
CF_GE0 = A_DE0 * PF0 * LIFE_PLANT * 5 / 3 * 2  # ≈ 10.0


class _MockNation:
    """Minimal stand-in for Nation for Agent.__init__."""


@pytest.fixture()
def nation():
    return _MockNation()


# ---------------------------------------------------------------------------
# GreenPlant
# ---------------------------------------------------------------------------

class TestGreenPlant:
    def test_construct(self, nation):
        p = GreenPlant(nation, vintage=1, count=500, building_cost=CF_GE0)
        assert p.vintage == 1
        assert p.count == 500
        assert p.building_cost == pytest.approx(CF_GE0)

    def test_unit_cost_always_zero(self, nation):
        p = GreenPlant(nation, vintage=1, count=100, building_cost=CF_GE0)
        assert p.unit_cost(fuel_price=PF0, carbon_tax=0.0) == 0.0
        assert p.unit_cost(fuel_price=PF0, carbon_tax=0.05) == 0.0
        assert p.unit_cost(fuel_price=0.0, carbon_tax=0.0) == 0.0

    def test_subsidy_and_full_cost_defaults(self, nation):
        p = GreenPlant(nation, vintage=1, count=50, building_cost=CF_GE0)
        assert p.subsidy_received == 0.0
        assert p.full_building_cost == 0.0

    def test_subsidy_and_full_cost_set(self, nation):
        p = GreenPlant(
            nation, vintage=5, count=200,
            building_cost=CF_GE0,
            subsidy_received=1.0,
            full_building_cost=CF_GE0 - 1.0,
        )
        assert p.subsidy_received == pytest.approx(1.0)
        assert p.full_building_cost == pytest.approx(CF_GE0 - 1.0)

    def test_inflation_adjust_scales_both_costs(self, nation):
        factor = 1.02
        p = GreenPlant(
            nation, vintage=1, count=10,
            building_cost=CF_GE0, full_building_cost=CF_GE0 * 0.9,
        )
        p.inflation_adjust(factor)
        assert p.building_cost == pytest.approx(CF_GE0 * factor)
        assert p.full_building_cost == pytest.approx(CF_GE0 * 0.9 * factor)

    def test_age(self, nation):
        p = GreenPlant(nation, vintage=10, count=1, building_cost=CF_GE0)
        assert p.age(current_t=15) == 5
        assert p.age(current_t=10) == 0


# ---------------------------------------------------------------------------
# BrownPlant
# ---------------------------------------------------------------------------

class TestBrownPlant:
    def test_construct(self, nation):
        p = BrownPlant(
            nation, vintage=1, count=5000,
            building_cost=CF_DE0,
            thermal_inefficiency=A_DE0,
            emission_intensity=EM_DE0,
        )
        assert p.vintage == 1
        assert p.count == 5000
        assert p.building_cost == pytest.approx(CF_DE0)
        assert p.thermal_inefficiency == pytest.approx(A_DE0)
        assert p.emission_intensity == pytest.approx(EM_DE0)

    def test_active_count_defaults_to_count(self, nation):
        p = BrownPlant(nation, vintage=1, count=100, building_cost=CF_DE0,
                       thermal_inefficiency=A_DE0, emission_intensity=EM_DE0)
        assert p.active_count == 100

    def test_unit_cost_no_carbon_tax(self, nation):
        """C_de = pf * A_de = 0.02 * 2.5 = 0.05 when t_CO2_en = 0."""
        p = BrownPlant(nation, vintage=1, count=100, building_cost=CF_DE0,
                       thermal_inefficiency=A_DE0, emission_intensity=EM_DE0)
        expected = PF0 * A_DE0
        assert p.unit_cost(fuel_price=PF0, carbon_tax=0.0) == pytest.approx(expected)

    def test_unit_cost_with_carbon_tax(self, nation):
        """C_de = A_de * (pf + t_CO2_en * EM_de)."""
        t_CO2_en = 0.01
        p = BrownPlant(nation, vintage=1, count=100, building_cost=CF_DE0,
                       thermal_inefficiency=A_DE0, emission_intensity=EM_DE0)
        expected = A_DE0 * (PF0 + t_CO2_en * EM_DE0)
        assert p.unit_cost(fuel_price=PF0, carbon_tax=t_CO2_en) == pytest.approx(expected)

    def test_unit_cost_higher_tax_raises_cost(self, nation):
        p = BrownPlant(nation, vintage=1, count=100, building_cost=CF_DE0,
                       thermal_inefficiency=A_DE0, emission_intensity=EM_DE0)
        low  = p.unit_cost(fuel_price=PF0, carbon_tax=0.0)
        high = p.unit_cost(fuel_price=PF0, carbon_tax=0.05)
        assert high > low

    def test_unit_cost_more_efficient_plant(self, nation):
        """A more efficient plant (lower thermal_inefficiency) has lower unit cost."""
        p_old = BrownPlant(nation, vintage=1, count=10, building_cost=CF_DE0,
                           thermal_inefficiency=A_DE0, emission_intensity=EM_DE0)
        p_new = BrownPlant(nation, vintage=5, count=10, building_cost=CF_DE0,
                           thermal_inefficiency=A_DE0 * 0.9, emission_intensity=EM_DE0)
        assert p_new.unit_cost(PF0, 0.0) < p_old.unit_cost(PF0, 0.0)

    def test_fuel_per_unit_energy(self, nation):
        p = BrownPlant(nation, vintage=1, count=1, building_cost=CF_DE0,
                       thermal_inefficiency=A_DE0, emission_intensity=EM_DE0)
        assert p.fuel_per_unit_energy() == pytest.approx(A_DE0)

    def test_emissions_per_unit_energy(self, nation):
        p = BrownPlant(nation, vintage=1, count=1, building_cost=CF_DE0,
                       thermal_inefficiency=A_DE0, emission_intensity=EM_DE0)
        assert p.emissions_per_unit_energy() == pytest.approx(EM_DE0 * A_DE0)

    def test_inflation_adjust(self, nation):
        factor = 1.03
        p = BrownPlant(nation, vintage=1, count=1, building_cost=CF_DE0,
                       thermal_inefficiency=A_DE0, emission_intensity=EM_DE0)
        p.inflation_adjust(factor)
        assert p.building_cost == pytest.approx(CF_DE0 * factor)
        # thermal_inefficiency and emission_intensity are NOT inflation-adjusted
        assert p.thermal_inefficiency == pytest.approx(A_DE0)

    def test_age(self, nation):
        p = BrownPlant(nation, vintage=20, count=1, building_cost=CF_DE0,
                       thermal_inefficiency=A_DE0, emission_intensity=EM_DE0)
        assert p.age(current_t=35) == 15


# ---------------------------------------------------------------------------
# PowerPlant base — unit_cost is abstract
# ---------------------------------------------------------------------------

class TestPowerPlantBase:
    def test_unit_cost_raises(self, nation):
        p = PowerPlant(nation, vintage=1, count=1, building_cost=1.0)
        with pytest.raises(NotImplementedError):
            p.unit_cost(fuel_price=0.1, carbon_tax=0.0)

    def test_both_plant_types_are_subclasses(self, nation):
        g = GreenPlant(nation, vintage=1, count=1, building_cost=1.0)
        b = BrownPlant(nation, vintage=1, count=1, building_cost=1.0,
                       thermal_inefficiency=2.5, emission_intensity=1100.0)
        assert isinstance(g, PowerPlant)
        assert isinstance(b, PowerPlant)

    def test_unique_ids_differ(self, nation):
        g = GreenPlant(nation, vintage=1, count=1, building_cost=1.0)
        b = BrownPlant(nation, vintage=1, count=1, building_cost=1.0,
                       thermal_inefficiency=2.5, emission_intensity=1100.0)
        assert g.unique_id != b.unique_id
