"""Integration tests for Task 3.6 — ElectricityProducer.aggregate_demand (EN_DEM).

Acceptance criteria (IMPLEMENTATION_PLAN §3.6):
- Total electricity demand == sum of firm-level demands.
- Sector-1 (capital-good) split between electricity and fossil fuel matches the
  flag_fuel_to_elec=1 nonlinear formula from dsk_electdemand.cpp /
  dsk_ffueldemand.cpp.
- Sector-2 (consumption-good) firms use electricity only: D2_en = Q2 * A2e_en.
"""
import math

import pytest
from unittest.mock import MagicMock

from dsk.agents.electricity_producer import (
    ElectricityProducer,
    _electdemand,
    _ffueldemand,
)
from dsk.parameters.global_parameters import GlobalParameters


# ---------------------------------------------------------------------------
# Helpers: lightweight stand-ins for capital-good and consumption-good firms
# ---------------------------------------------------------------------------

class _S1Firm:
    """Minimal capital-good firm stub for aggregate_demand tests."""
    def __init__(self, production, elf, energy_need, alive=True):
        self.is_alive = alive
        self.production = production
        self.current_technology = MagicMock()
        self.current_technology.electrification_fraction = elf
        self.process_energy_need = energy_need
        self.elec_demand = 0.0
        self.fossil_fuel_demand = 0.0


class _S2Firm:
    """Minimal consumption-good firm stub for aggregate_demand tests."""
    def __init__(self, production, energy_efficiency, alive=True):
        self.is_alive = alive
        self.production = production
        self.effective_energy_efficiency = energy_efficiency
        self.elec_demand = 0.0


def _make_ep(gparams=None):
    nation = MagicMock()
    nation.gparams = gparams or GlobalParameters()
    ep = ElectricityProducer(nation)
    ep.demand_history = [0.0] * 12
    return ep


# ---------------------------------------------------------------------------
# Unit tests for the _electdemand / _ffueldemand helpers
# ---------------------------------------------------------------------------

class TestHelperFormulas:
    """Verify the three flag_fuel_to_elec modes against the C++ formulas."""

    def test_rule0_elec_linear(self):
        # eldem = end * elf * phi
        assert abs(_electdemand(0.5, 10.0, 0.3, 0) - 10.0 * 0.5 * 0.3) < 1e-12

    def test_rule0_fuel_linear(self):
        # fudem = end * (1 - elf)
        assert abs(_ffueldemand(0.5, 10.0, 0.3, 0) - 10.0 * 0.5) < 1e-12

    def test_rule1_elec_baseline(self):
        # eldem = end * (elf^2 + elf) * 0.7 * 0.30
        elf, end = 0.3, 266.0
        expected = end * (elf**2 + elf) * 0.7 * 0.30
        assert abs(_electdemand(elf, end, 0.3, 1) - expected) < 1e-10

    def test_rule1_fuel_baseline(self):
        # fudem = end * ((1-elf)^2 + (1-elf)) * 2.1 * 0.30
        elf, end = 0.3, 266.0
        expected = end * ((1 - elf)**2 + (1 - elf)) * 2.1 * 0.30
        assert abs(_ffueldemand(elf, end, 0.3, 1) - expected) < 1e-10

    def test_rule2_nonlinear_nw(self):
        # rat = phi*elf/(1-elf); eldem = end*rat/(rat+2*sqrt(phi*rat)+phi)/2
        elf, end, phi = 0.4, 100.0, 0.3
        rat = phi * elf / (1.0 - elf)
        expected_el = end * rat / (rat + 2.0 * math.sqrt(phi * rat) + phi) / 2.0
        expected_ff = end / (rat + 2.0 * math.sqrt(phi * rat) + phi) / 2.0
        assert abs(_electdemand(elf, end, phi, 2) - expected_el) < 1e-10
        assert abs(_ffueldemand(elf, end, phi, 2) - expected_ff) < 1e-10

    def test_zero_electrification_means_no_electricity(self):
        assert _electdemand(0.0, 100.0, 0.3, 1) == 0.0

    def test_fully_electrified_rule0_means_no_fuel(self):
        assert _ffueldemand(1.0, 100.0, 0.3, 0) == 0.0


# ---------------------------------------------------------------------------
# aggregate_demand: totals == sum of per-firm demands
# ---------------------------------------------------------------------------

class TestAggregateDemandTotals:
    """Core acceptance: total demand = sum of individual firm demands."""

    def test_single_s1_firm_totals_match(self):
        p = GlobalParameters()
        ep = _make_ep(p)
        firm = _S1Firm(production=100.0, elf=0.3, energy_need=266.67)

        ep.aggregate_demand(t=1, capital_good_sector=[firm],
                            consumption_good_sector=[])

        assert abs(ep.s1_elec_demand_total - firm.elec_demand) < 1e-9
        assert abs(ep.s1_fossil_demand_total - firm.fossil_fuel_demand) < 1e-9
        assert ep.s2_elec_demand_total == 0.0
        # D_en_TOT = round(D1_en + D2_en)
        expected_total = round(firm.elec_demand)
        assert ep.total_energy_demand == expected_total

    def test_single_s2_firm_totals_match(self):
        p = GlobalParameters()
        ep = _make_ep(p)
        firm = _S2Firm(production=500.0, energy_efficiency=0.1333)

        ep.aggregate_demand(t=1, capital_good_sector=[],
                            consumption_good_sector=[firm])

        assert abs(ep.s2_elec_demand_total - firm.elec_demand) < 1e-9
        assert ep.s1_elec_demand_total == 0.0
        expected_total = round(firm.elec_demand)
        assert ep.total_energy_demand == expected_total

    def test_multiple_firms_sum_correctly(self):
        p = GlobalParameters()
        ep = _make_ep(p)
        s1_firms = [_S1Firm(production=50.0 + i, elf=0.3, energy_need=266.67)
                    for i in range(5)]
        s2_firms = [_S2Firm(production=200.0 + i, energy_efficiency=0.1333)
                    for i in range(3)]

        ep.aggregate_demand(t=1, capital_good_sector=s1_firms,
                            consumption_good_sector=s2_firms)

        expected_d1_en = sum(f.elec_demand for f in s1_firms)
        expected_d2_en = sum(f.elec_demand for f in s2_firms)
        expected_d1_ff = sum(f.fossil_fuel_demand for f in s1_firms)

        assert abs(ep.s1_elec_demand_total - expected_d1_en) < 1e-9
        assert abs(ep.s2_elec_demand_total - expected_d2_en) < 1e-9
        assert abs(ep.s1_fossil_demand_total - expected_d1_ff) < 1e-9
        assert ep.total_energy_demand == round(expected_d1_en + expected_d2_en)

    def test_dead_firms_contribute_zero(self):
        p = GlobalParameters()
        ep = _make_ep(p)
        alive = _S1Firm(production=100.0, elf=0.3, energy_need=266.67)
        dead = _S1Firm(production=100.0, elf=0.3, energy_need=266.67, alive=False)

        ep.aggregate_demand(t=1, capital_good_sector=[alive, dead],
                            consumption_good_sector=[])

        assert dead.elec_demand == 0.0
        assert dead.fossil_fuel_demand == 0.0
        assert ep.s1_elec_demand_total == alive.elec_demand


# ---------------------------------------------------------------------------
# aggregate_demand: sector-1 formula correctness
# ---------------------------------------------------------------------------

class TestSector1Formula:
    """Sector-1 split must match the flag_fuel_to_elec=1 formula (baseline)."""

    def test_s1_elec_demand_matches_formula(self):
        p = GlobalParameters()
        assert p.fuel_to_elec_rule == 1, "baseline must use rule=1"
        ep = _make_ep(p)

        elf = 0.3
        end = p.energy_need_init * p.s1_energy_need_init_factor
        phi = p.fuel_to_electricity_equivalence
        q1 = 150.0

        firm = _S1Firm(production=q1, elf=elf, energy_need=end)
        ep.aggregate_demand(t=1, capital_good_sector=[firm],
                            consumption_good_sector=[])

        expected_elec = q1 * _electdemand(elf, end, phi, rule=1)
        expected_fuel = q1 * _ffueldemand(elf, end, phi, rule=1)

        assert abs(firm.elec_demand - expected_elec) < 1e-8
        assert abs(firm.fossil_fuel_demand - expected_fuel) < 1e-8

    def test_higher_electrification_shifts_demand(self):
        """A firm with higher elf uses more electricity and less fossil fuel."""
        p = GlobalParameters()
        ep = _make_ep(p)
        end = p.energy_need_init * p.s1_energy_need_init_factor
        phi = p.fuel_to_electricity_equivalence

        low_elf = _S1Firm(production=100.0, elf=0.1, energy_need=end)
        high_elf = _S1Firm(production=100.0, elf=0.7, energy_need=end)
        ep.aggregate_demand(t=1, capital_good_sector=[low_elf, high_elf],
                            consumption_good_sector=[])

        assert high_elf.elec_demand > low_elf.elec_demand
        assert high_elf.fossil_fuel_demand < low_elf.fossil_fuel_demand


# ---------------------------------------------------------------------------
# aggregate_demand: sector-2 formula correctness
# ---------------------------------------------------------------------------

class TestSector2Formula:
    """Sector-2 uses electricity only: D2_en = Q2 * A2e_en."""

    def test_s2_demand_equals_production_times_energy_need(self):
        p = GlobalParameters()
        ep = _make_ep(p)
        q2 = 800.0
        a2e_en = p.energy_need_init  # = A0_en

        firm = _S2Firm(production=q2, energy_efficiency=a2e_en)
        ep.aggregate_demand(t=1, capital_good_sector=[],
                            consumption_good_sector=[firm])

        assert abs(firm.elec_demand - q2 * a2e_en) < 1e-10

    def test_s2_has_no_fossil_demand(self):
        """Sector-2 firms produce no fossil fuel demand field via aggregate_demand."""
        p = GlobalParameters()
        ep = _make_ep(p)
        firm = _S2Firm(production=100.0, energy_efficiency=0.1333)
        ep.aggregate_demand(t=1, capital_good_sector=[],
                            consumption_good_sector=[firm])
        # S2 firms have no fossil_fuel_demand attribute; only s1_fossil_demand_total
        assert ep.s1_fossil_demand_total == 0.0


# ---------------------------------------------------------------------------
# aggregate_demand: demand history and D_en_build
# ---------------------------------------------------------------------------

class TestDemandHistory:
    """History buffer and D_en_build logic (C++ EN_DEM :38-62)."""

    def test_history_initialised_at_t1(self):
        p = GlobalParameters()
        ep = _make_ep(p)
        firm = _S2Firm(production=100.0, energy_efficiency=0.2)
        ep.aggregate_demand(t=1, capital_good_sector=[], consumption_good_sector=[firm])

        expected = round(100.0 * 0.2)
        assert all(abs(v - expected) < 1e-9 for v in ep.demand_history)

    def test_history_shifts_at_t2(self):
        p = GlobalParameters()
        ep = _make_ep(p)
        firm1 = _S2Firm(production=100.0, energy_efficiency=0.2)
        firm2 = _S2Firm(production=200.0, energy_efficiency=0.2)

        ep.aggregate_demand(t=1, capital_good_sector=[], consumption_good_sector=[firm1])
        d1 = ep.total_energy_demand
        ep.aggregate_demand(t=2, capital_good_sector=[], consumption_good_sector=[firm2])
        d2 = ep.total_energy_demand

        # After t=2: history[0] = d2 just recorded; history[1] = d1 from t=1
        assert abs(ep.demand_history[0] - d2) < 1e-9
        assert abs(ep.demand_history[1] - d1) < 1e-9

    def test_d_en_build_equals_d_en_tot_at_lookback0(self):
        """With flag_demand_energy=0, D_en_build == D_en_TOT."""
        p = GlobalParameters()
        assert p.energy_nominal_demand_lookback == 0
        ep = _make_ep(p)
        firm = _S2Firm(production=500.0, energy_efficiency=0.2)
        ep.aggregate_demand(t=1, capital_good_sector=[], consumption_good_sector=[firm])

        assert abs(ep.total_energy_demand_build - ep.total_energy_demand) < 1e-9

    def test_d_en_build_uses_history_when_lookback_positive(self):
        """With lookback=1, D_en_build = max(current, history[0]*1.03)."""
        p = GlobalParameters()
        p.energy_nominal_demand_lookback = 1
        p.energy_demand_history_factor = 1.03
        ep = _make_ep(p)

        # t=1: seed high demand so history[0] is large
        high_firm = _S2Firm(production=1000.0, energy_efficiency=0.2)
        ep.aggregate_demand(t=1, capital_good_sector=[], consumption_good_sector=[high_firm])
        d1 = ep.total_energy_demand  # = round(1000 * 0.2) = 200

        # t=2: lower demand — D_en_build should be max(current, d1*1.03)
        low_firm = _S2Firm(production=100.0, energy_efficiency=0.2)
        ep.aggregate_demand(t=2, capital_good_sector=[], consumption_good_sector=[low_firm])
        d2 = ep.total_energy_demand  # = round(100 * 0.2) = 20

        expected_build = max(d2, d1 * 1.03)
        assert abs(ep.total_energy_demand_build - expected_build) < 1e-9
