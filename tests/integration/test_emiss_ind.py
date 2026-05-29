"""Integration tests for Task 3.7 — Nation.compute_industrial_emissions (EMISS_IND).

Acceptance criteria (IMPLEMENTATION_PLAN §3.7):
- industrial emissions = fuel use × ff2em  (fossil-fuel path, sector 1)
- sector-2 baseline emissions = 0  (process emissions disabled in baseline)
- nation-level aggregates (Emiss1_TOT, Emiss2_TOT, tp_CO2_I1_TOT, tp_CO2_I2_TOT,
  LDff_1) are computed correctly
"""
from unittest.mock import MagicMock

import pytest

from dsk.parameters.global_parameters import GlobalParameters


# ---------------------------------------------------------------------------
# Minimal firm stubs
# ---------------------------------------------------------------------------

class _S1Firm:
    """Sector-1 stub: only the fields read by compute_industrial_emissions."""
    def __init__(self, fossil_fuel_demand, production, process_env_filthiness=0.0, alive=True):
        self.is_alive = alive
        self.fossil_fuel_demand = fossil_fuel_demand
        self.production = production
        self.process_env_filthiness = process_env_filthiness
        self.emissions = 0.0
        self.emissions_fossil = 0.0
        self.emissions_process = 0.0


class _S2Firm:
    """Sector-2 stub: only the fields read by compute_industrial_emissions."""
    def __init__(self, production, effective_env_filthiness=0.0, alive=True):
        self.is_alive = alive
        self.production = production
        self.effective_env_filthiness = effective_env_filthiness
        self.emissions = 0.0


# ---------------------------------------------------------------------------
# Helper: build a minimal nation-like object whose compute_industrial_emissions
# we can call via the real method.
# ---------------------------------------------------------------------------

def _make_nation(
    s1_firms,
    s2_firms,
    pf=0.02,
    wage=1.0,
    carbon_tax_s1=0.0,
    carbon_tax_s2=0.0,
    gparams=None,
):
    """Return a real Nation instance wired with stub firms."""
    from dsk.nation import Nation
    from dsk.parameters.global_parameters import GlobalParameters
    from dsk.parameters.nation_parameters import NationParameters

    gp = gparams or GlobalParameters()

    nation = Nation.__new__(Nation)
    # Call __init__ to set default fields (avoids duplicate __init__ logic).
    Nation.__init__(nation, nation_id="test")
    nation.gparams = gp
    nation.params = NationParameters(fossil_fuel_price=pf)

    # Replace real sectors with simple iterables
    nation.capital_good_sector = s1_firms
    nation.consumption_good_sector = s2_firms

    # Wire labour market
    nation.labour_market = MagicMock()
    nation.labour_market.wage = wage

    # Carbon tax rates
    nation.carbon_tax_rate_s1 = carbon_tax_s1
    nation.carbon_tax_rate_s2 = carbon_tax_s2

    return nation


# ---------------------------------------------------------------------------
# Tests: sector-1 fossil-fuel emissions
# ---------------------------------------------------------------------------

class TestS1FossilEmissions:
    """Emiss1(i) = fossil_fuel_demand * ff2em (process emissions = 0 in baseline)."""

    def test_per_firm_emissions_fossil(self):
        ff2em = GlobalParameters().fuel_to_emissions_factor  # 1100
        f = _S1Firm(fossil_fuel_demand=10.0, production=5.0)
        nation = _make_nation([f], [])
        nation.compute_industrial_emissions()
        assert abs(f.emissions_fossil - 10.0 * ff2em) < 1e-10

    def test_per_firm_emissions_process_zero_baseline(self):
        f = _S1Firm(fossil_fuel_demand=10.0, production=5.0, process_env_filthiness=0.0)
        nation = _make_nation([f], [])
        nation.compute_industrial_emissions()
        assert f.emissions_process == 0.0

    def test_per_firm_total_equals_fossil_when_no_process(self):
        ff2em = GlobalParameters().fuel_to_emissions_factor
        f = _S1Firm(fossil_fuel_demand=7.5, production=3.0)
        nation = _make_nation([f], [])
        nation.compute_industrial_emissions()
        assert abs(f.emissions - f.emissions_fossil) < 1e-10
        assert abs(f.emissions - 7.5 * ff2em) < 1e-10

    def test_process_emissions_nonzero_when_ef_set(self):
        ff2em = GlobalParameters().fuel_to_emissions_factor
        ef = 50000.0
        prod = 4.0
        ff_dem = 3.0
        f = _S1Firm(fossil_fuel_demand=ff_dem, production=prod, process_env_filthiness=ef)
        nation = _make_nation([f], [])
        nation.compute_industrial_emissions()
        assert abs(f.emissions_process - ef * prod) < 1e-10
        assert abs(f.emissions - (ff_dem * ff2em + ef * prod)) < 1e-10

    def test_s1_total_is_sum_of_per_firm(self):
        ff2em = GlobalParameters().fuel_to_emissions_factor
        firms = [_S1Firm(fossil_fuel_demand=float(i + 1), production=1.0) for i in range(5)]
        nation = _make_nation(firms, [])
        nation.compute_industrial_emissions()
        expected = sum((i + 1) * ff2em for i in range(5))
        assert abs(nation.emissions_total_s1 - expected) < 1e-9

    def test_dead_s1_firm_contributes_zero(self):
        alive = _S1Firm(fossil_fuel_demand=5.0, production=2.0)
        dead = _S1Firm(fossil_fuel_demand=9.0, production=3.0, alive=False)
        ff2em = GlobalParameters().fuel_to_emissions_factor
        nation = _make_nation([alive, dead], [])
        nation.compute_industrial_emissions()
        assert dead.emissions == 0.0
        assert dead.emissions_fossil == 0.0
        assert dead.emissions_process == 0.0
        assert abs(nation.emissions_total_s1 - 5.0 * ff2em) < 1e-10


# ---------------------------------------------------------------------------
# Tests: sector-2 emissions
# ---------------------------------------------------------------------------

class TestS2Emissions:
    """Emiss2(j) = A2e_ef(j) * Q2(j); in baseline A2e_ef=0 so emissions=0."""

    def test_s2_zero_in_baseline(self):
        f = _S2Firm(production=10.0, effective_env_filthiness=0.0)
        nation = _make_nation([], [f])
        nation.compute_industrial_emissions()
        assert f.emissions == 0.0
        assert nation.emissions_total_s2 == 0.0

    def test_s2_nonzero_when_ef_set(self):
        ef = 200.0
        prod = 5.0
        f = _S2Firm(production=prod, effective_env_filthiness=ef)
        nation = _make_nation([], [f])
        nation.compute_industrial_emissions()
        assert abs(f.emissions - ef * prod) < 1e-10

    def test_s2_total_sums_per_firm(self):
        firms = [_S2Firm(production=float(j + 1), effective_env_filthiness=100.0) for j in range(4)]
        nation = _make_nation([], firms)
        nation.compute_industrial_emissions()
        expected = sum((j + 1) * 100.0 for j in range(4))
        assert abs(nation.emissions_total_s2 - expected) < 1e-9

    def test_dead_s2_firm_contributes_zero(self):
        alive = _S2Firm(production=5.0, effective_env_filthiness=100.0)
        dead = _S2Firm(production=5.0, effective_env_filthiness=100.0, alive=False)
        nation = _make_nation([], [alive, dead])
        nation.compute_industrial_emissions()
        assert dead.emissions == 0.0
        assert abs(nation.emissions_total_s2 - 5.0 * 100.0) < 1e-10


# ---------------------------------------------------------------------------
# Tests: totals and cross-sector aggregates
# ---------------------------------------------------------------------------

class TestTotals:
    def test_emissions_this_step_is_s1_plus_s2(self):
        gp = GlobalParameters()
        ff2em = gp.fuel_to_emissions_factor
        s1 = [_S1Firm(fossil_fuel_demand=4.0, production=2.0)]
        s2 = [_S2Firm(production=3.0, effective_env_filthiness=50.0)]
        nation = _make_nation(s1, s2)
        nation.compute_industrial_emissions()
        expected = 4.0 * ff2em + 3.0 * 50.0
        assert abs(nation._emissions_this_step - expected) < 1e-9

    def test_report_emissions_matches_step_total(self):
        gp = GlobalParameters()
        ff2em = gp.fuel_to_emissions_factor
        s1 = [_S1Firm(fossil_fuel_demand=2.0, production=1.0)]
        nation = _make_nation(s1, [])
        nation.compute_industrial_emissions()
        assert abs(nation.report_emissions() - 2.0 * ff2em) < 1e-10

    def test_zero_production_all_sectors_gives_zero(self):
        s1 = [_S1Firm(fossil_fuel_demand=0.0, production=0.0)]
        s2 = [_S2Firm(production=0.0)]
        nation = _make_nation(s1, s2)
        nation.compute_industrial_emissions()
        assert nation.emissions_total_s1 == 0.0
        assert nation.emissions_total_s2 == 0.0
        assert nation._emissions_this_step == 0.0


# ---------------------------------------------------------------------------
# Tests: carbon tax revenue
# ---------------------------------------------------------------------------

class TestCarbonTax:
    def test_carbon_tax_zero_in_baseline(self):
        """Baseline: t_CO2_I1 = t_CO2_I2 = 0, so tp_CO2_*_TOT = 0."""
        s1 = [_S1Firm(fossil_fuel_demand=10.0, production=5.0)]
        s2 = [_S2Firm(production=5.0, effective_env_filthiness=1000.0)]
        nation = _make_nation(s1, s2, carbon_tax_s1=0.0, carbon_tax_s2=0.0)
        nation.compute_industrial_emissions()
        assert nation.carbon_tax_revenue_s1 == 0.0
        assert nation.carbon_tax_revenue_s2 == 0.0

    def test_s1_carbon_tax_revenue(self):
        ff2em = GlobalParameters().fuel_to_emissions_factor
        ff_dem = 5.0
        t_co2 = 1e-5
        f = _S1Firm(fossil_fuel_demand=ff_dem, production=2.0)
        nation = _make_nation([f], [], carbon_tax_s1=t_co2)
        nation.compute_industrial_emissions()
        expected = ff_dem * ff2em * t_co2
        assert abs(nation.carbon_tax_revenue_s1 - expected) < 1e-15

    def test_s2_carbon_tax_revenue(self):
        ef = 500.0
        prod = 3.0
        t_co2 = 1e-7
        f = _S2Firm(production=prod, effective_env_filthiness=ef)
        nation = _make_nation([], [f], carbon_tax_s2=t_co2)
        nation.compute_industrial_emissions()
        expected = ef * prod * t_co2
        assert abs(nation.carbon_tax_revenue_s2 - expected) < 1e-18


# ---------------------------------------------------------------------------
# Tests: fossil-fuel extraction labour demand (LDff_1)
# ---------------------------------------------------------------------------

class TestFuelLabourDemand:
    """LDff_1 = Σ fossil_fuel_demand[i] * pf * LDff_frac / wage."""

    def test_ldff1_formula(self):
        gp = GlobalParameters()
        ldf = gp.fuel_labour_cost_fraction   # 0.6
        pf = 0.02
        wage = 1.0
        ff_dem = 8.0
        f = _S1Firm(fossil_fuel_demand=ff_dem, production=4.0)
        nation = _make_nation([f], [], pf=pf, wage=wage)
        nation.compute_industrial_emissions()
        expected = ff_dem * pf * ldf / wage
        assert abs(nation.fuel_labour_demand_s1 - expected) < 1e-12

    def test_ldff1_sums_across_firms(self):
        gp = GlobalParameters()
        ldf = gp.fuel_labour_cost_fraction
        pf = 0.02
        wage = 1.5
        ffs = [2.0, 4.0, 6.0]
        firms = [_S1Firm(fossil_fuel_demand=d, production=1.0) for d in ffs]
        nation = _make_nation(firms, [], pf=pf, wage=wage)
        nation.compute_industrial_emissions()
        expected = sum(d * pf * ldf / wage for d in ffs)
        assert abs(nation.fuel_labour_demand_s1 - expected) < 1e-12

    def test_ldff1_zero_when_wage_zero(self):
        """Wage = 0 is degenerate; method should not raise and LDff_1 stays 0."""
        f = _S1Firm(fossil_fuel_demand=5.0, production=2.0)
        nation = _make_nation([f], [], wage=0.0)
        nation.compute_industrial_emissions()
        assert nation.fuel_labour_demand_s1 == 0.0

    def test_ldff1_excludes_dead_firms(self):
        gp = GlobalParameters()
        ldf = gp.fuel_labour_cost_fraction
        pf = 0.02
        wage = 1.0
        alive = _S1Firm(fossil_fuel_demand=5.0, production=2.0, alive=True)
        dead = _S1Firm(fossil_fuel_demand=10.0, production=3.0, alive=False)
        nation = _make_nation([alive, dead], [], pf=pf, wage=wage)
        nation.compute_industrial_emissions()
        expected = 5.0 * pf * ldf / wage
        assert abs(nation.fuel_labour_demand_s1 - expected) < 1e-12
