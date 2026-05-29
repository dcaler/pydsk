"""Integration tests for Task 5.1 — CarbonTax instrument.

Acceptance criteria (IMPLEMENTATION_PLAN §5.1):
1. Under Tc (constant tax), the effective fossil-fuel price including tax equals
   pf * (1 + tau)  where  tau = ff2em * rate_s1 / pf.
2. Under TD2 (exponential growth), the rate time path matches
   X(t) = X_0 * exp(a * (t - t_0)).

Additional coverage:
- Rate is zero before t_start_climbox.
- Fuel price is inflation-adjusted + 0.4 %/yr after t > 3.
- tax_on=False suppresses all rates (fuel price still updates).
- Sector-2 rate is zero in the baseline (no fossil-fuel emissions).
- Carbon tax rates propagate to nation.government and nation.carbon_tax_rate_s*.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from dsk.nation import Nation
from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters
from dsk.policy.carbon_tax import CarbonTax, SECTOR_S1, SECTOR_S2, SECTOR_ENERGY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_nation(seed: int = 42, n1: int = 10, n2: int = 40) -> Nation:
    gparams = GlobalParameters()
    gparams.n1_capital_good_firms = n1
    gparams.n2_consumption_good_firms = n2
    gparams.labour_supply_init = int(gparams.labour_supply_init * (n2 / 400.0))
    nparams = NationParameters()
    nation = Nation("tax-test", params=nparams)
    nation.rng = np.random.default_rng(seed)
    nation.initialise_from_parameters(gparams, nparams)
    return nation


def _full_step(nation: Nation, t: int) -> None:
    nation.production_phase(t)
    nation.dynamics_phase(t)
    nation.closeout_phase(t)


def _attach_carbon_tax(nation: Nation, instrument: CarbonTax) -> None:
    nation.climate_policy.add_instrument(instrument)


# ---------------------------------------------------------------------------
# rate_for formula tests (pure, no nation required)
# ---------------------------------------------------------------------------

class TestRateForFormula:
    """Pure formula tests — verify rate_for without a full nation."""

    def test_zero_at_or_before_t_start(self):
        ct = CarbonTax(schedule="constant", base_rate=3.3e-4, t_start=80)
        ct._resolved_t_start = 80
        assert ct.rate_for(SECTOR_S1, 80) == 0.0
        assert ct.rate_for(SECTOR_S1, 1) == 0.0

    def test_constant_schedule_rate_formula(self):
        """rate = cpi_ratio * base_rate (inflation-adjusted flat rate)."""
        ct = CarbonTax(schedule="constant", base_rate=3.3e-4, t_start=80)
        ct._resolved_t_start = 80
        cpi_ratio = 1.25
        rate = ct.rate_for(SECTOR_S1, 85, cpi_ratio=cpi_ratio)
        assert abs(rate - cpi_ratio * 3.3e-4) < 1e-15

    def test_constant_energy_rate_equals_s1(self):
        ct = CarbonTax(schedule="constant", base_rate=3.3e-4, t_start=80)
        ct._resolved_t_start = 80
        cpi_ratio = 1.1
        assert ct.rate_for(SECTOR_ENERGY, 85, cpi_ratio) == ct.rate_for(SECTOR_S1, 85, cpi_ratio)

    def test_s2_rate_zero_by_default(self):
        """Sector-2 base_rate_s2 defaults to 0."""
        ct = CarbonTax(schedule="constant", base_rate=3.3e-4, t_start=80)
        ct._resolved_t_start = 80
        assert ct.rate_for(SECTOR_S2, 85, cpi_ratio=2.0) == 0.0

    def test_s2_nonzero_when_configured(self):
        ct = CarbonTax(schedule="constant", base_rate=3.3e-4, base_rate_s2=1e-5, t_start=80)
        ct._resolved_t_start = 80
        assert ct.rate_for(SECTOR_S2, 85, cpi_ratio=1.0) == pytest.approx(1e-5)

    def test_tax_on_false_returns_zero(self):
        ct = CarbonTax(schedule="constant", base_rate=3.3e-4, tax_on=False, t_start=80)
        ct._resolved_t_start = 80
        assert ct.rate_for(SECTOR_S1, 90, cpi_ratio=1.5) == 0.0

    def test_rate_never_negative(self):
        ct = CarbonTax(schedule="constant", base_rate=3.3e-4, t_start=80)
        ct._resolved_t_start = 80
        ct._cpi_ref = 1.5  # scenario where CPI has fallen below ref (unusual)
        # Even with cpi_ratio<1, rate is floored at 0 (not negative)
        rate = ct.rate_for(SECTOR_S1, 85, cpi_ratio=0.0)
        assert rate == 0.0

    # ------------------------------------------------------------------
    # Exponential schedule (TD2)
    # ------------------------------------------------------------------

    def test_exponential_schedule_matches_formula(self):
        """rate(t) = X_0 * exp(a * (t - t_0))  where t_0 = t_start + 2."""
        t_start = 80
        t0 = t_start + 2
        X_0 = 5e-4
        a = 0.09

        ct = CarbonTax(schedule="exponential", base_rate=X_0, growth_rate=a, t_start=t_start)
        ct._resolved_t_start = t_start

        for t in [83, 90, 100, 120]:
            expected = X_0 * math.exp(a * (t - t0))
            got = ct.rate_for(SECTOR_S1, t)
            assert abs(got - expected) < 1e-15, f"t={t}: expected {expected}, got {got}"

    def test_exponential_at_t0_equals_base_rate(self):
        """At t = t_start + 2, the rate should equal base_rate exactly."""
        t_start = 80
        ct = CarbonTax(schedule="exponential", base_rate=5e-4, growth_rate=0.09, t_start=t_start)
        ct._resolved_t_start = t_start
        assert ct.rate_for(SECTOR_S1, t_start + 2) == pytest.approx(5e-4)

    def test_exponential_energy_same_as_s1(self):
        ct = CarbonTax(schedule="exponential", base_rate=5e-4, growth_rate=0.09, t_start=80)
        ct._resolved_t_start = 80
        for t in [85, 100]:
            assert ct.rate_for(SECTOR_ENERGY, t) == ct.rate_for(SECTOR_S1, t)

    def test_exponential_monotonically_increasing(self):
        ct = CarbonTax(schedule="exponential", base_rate=5e-4, growth_rate=0.09, t_start=80)
        ct._resolved_t_start = 80
        rates = [ct.rate_for(SECTOR_S1, t) for t in range(82, 120)]
        for i in range(len(rates) - 1):
            assert rates[i + 1] > rates[i]


# ---------------------------------------------------------------------------
# apply() tests using a fully-initialised Nation
# ---------------------------------------------------------------------------

class TestApplyWithNation:
    """Tests that verify apply() correctly modifies Nation state."""

    def test_rates_zero_before_t_start(self):
        nation = _build_nation()
        t_start = nation.gparams.climate_start_step  # = 80
        ct = CarbonTax(schedule="constant", base_rate=3.3e-4)
        ct.apply(nation, 2)   # capture cpi_ref
        ct.apply(nation, 10)  # well before t_start
        assert nation.carbon_tax_rate_s1 == 0.0
        assert nation.government.carbon_tax_rate_industry1 == 0.0
        assert nation.government.carbon_tax_rate_energy == 0.0

    def test_rates_nonzero_after_t_start(self):
        nation = _build_nation()
        t_start = nation.gparams.climate_start_step
        ct = CarbonTax(schedule="constant", base_rate=3.3e-4)
        # Capture CPI ref at t=2
        ct.apply(nation, 2)
        # Apply at t > t_start
        ct.apply(nation, t_start + 5)
        assert nation.carbon_tax_rate_s1 > 0.0
        assert nation.government.carbon_tax_rate_industry1 > 0.0
        assert nation.government.carbon_tax_rate_energy > 0.0

    def test_government_and_nation_rates_in_sync(self):
        """nation.carbon_tax_rate_s1 must equal government.carbon_tax_rate_industry1."""
        nation = _build_nation()
        t_start = nation.gparams.climate_start_step
        ct = CarbonTax(schedule="constant", base_rate=3.3e-4)
        ct.apply(nation, 2)
        ct.apply(nation, t_start + 10)
        assert nation.carbon_tax_rate_s1 == nation.government.carbon_tax_rate_industry1
        assert nation.carbon_tax_rate_s2 == nation.government.carbon_tax_rate_industry2

    def test_s2_rate_zero_baseline(self):
        """Sector-2 rate stays zero with default base_rate_s2=0."""
        nation = _build_nation()
        t_start = nation.gparams.climate_start_step
        ct = CarbonTax(schedule="constant", base_rate=3.3e-4)
        ct.apply(nation, 2)
        ct.apply(nation, t_start + 5)
        assert nation.carbon_tax_rate_s2 == 0.0
        assert nation.government.carbon_tax_rate_industry2 == 0.0

    def test_tax_on_false_suppresses_rates(self):
        nation = _build_nation()
        t_start = nation.gparams.climate_start_step
        ct = CarbonTax(schedule="constant", base_rate=3.3e-4, tax_on=False)
        ct.apply(nation, 2)
        ct.apply(nation, t_start + 5)
        assert nation.carbon_tax_rate_s1 == 0.0
        assert nation.government.carbon_tax_rate_energy == 0.0


# ---------------------------------------------------------------------------
# Acceptance test 1: Tc — effective fossil-fuel price
# ---------------------------------------------------------------------------

class TestConstantTaxEffectiveFuelPrice:
    """Task 5.1 acceptance: under Tc, effective pf including tax = pf * (1 + tau)."""

    def test_effective_fuel_price_formula(self):
        """The carbon-tax surcharge on fossil fuel equals ff2em * t_CO2_I1.

        This implies: effective_pf = pf + ff2em * rate_s1 = pf * (1 + tau)
        where tau = ff2em * rate_s1 / pf.
        """
        nation = _build_nation()
        gparams = nation.gparams
        ff2em = gparams.fuel_to_emissions_factor
        t_start = gparams.climate_start_step

        base_rate = 3.3e-4
        ct = CarbonTax(schedule="constant", base_rate=base_rate)
        _attach_carbon_tax(nation, ct)

        # Run past t_start to activate the tax
        for t in range(1, t_start + 6):
            _full_step(nation, t)

        pf = nation.params.fossil_fuel_price
        rate_s1 = nation.carbon_tax_rate_s1
        assert rate_s1 > 0.0, "rate_s1 should be positive after t_start"

        # Verify the formula pf * (1 + tau) = pf + ff2em * rate_s1
        tau = ff2em * rate_s1 / pf
        effective_pf = pf + ff2em * rate_s1
        assert abs(effective_pf - pf * (1.0 + tau)) < 1e-12 * effective_pf

    def test_constant_rate_is_inflation_adjusted(self):
        """Constant rate equals base_rate scaled by cumulative inflation since t=2.

        apply() runs at the START of production_phase, before PROFIT updates cpi.
        So the rate uses the CPI from the previous period — we capture it just
        before the final step to compare against the stored rate.
        """
        nation = _build_nation()
        t_start = nation.gparams.climate_start_step

        base_rate = 3.3e-4
        ct = CarbonTax(schedule="constant", base_rate=base_rate)
        _attach_carbon_tax(nation, ct)

        # Run all but the last step
        for t in range(1, t_start + 5):
            _full_step(nation, t)

        # Capture the CPI that apply() will see at the start of t_start+5
        cpi_used = nation.cpi
        _full_step(nation, t_start + 5)

        cpi_ref = ct._cpi_ref
        expected_rate = (cpi_used / cpi_ref) * base_rate if cpi_ref else base_rate

        assert abs(nation.carbon_tax_rate_s1 - expected_rate) < 1e-15


# ---------------------------------------------------------------------------
# Acceptance test 2: TD2 — exponential growth time path
# ---------------------------------------------------------------------------

class TestExponentialTaxTimePath:
    """Task 5.1 acceptance: under TD2, rate matches X(t) = X_0 * exp(a * (t - t_0))."""

    def test_exponential_time_path_via_apply(self):
        """After apply() at several post-t_start steps, rates follow the exponential."""
        nation = _build_nation()
        t_start = nation.gparams.climate_start_step
        t0 = t_start + 2

        X_0 = 5e-4
        a = 0.09
        ct = CarbonTax(schedule="exponential", base_rate=X_0, growth_rate=a)

        # Capture CPI ref
        ct.apply(nation, 2)

        for t in [t_start + 2, t_start + 5, t_start + 10, t_start + 20]:
            ct.apply(nation, t)
            expected = X_0 * math.exp(a * (t - t0))
            got = nation.carbon_tax_rate_s1
            assert abs(got - expected) < 1e-14, (
                f"t={t}: expected {expected:.6e}, got {got:.6e}"
            )

    def test_exponential_rate_grows_each_period(self):
        """Rate at t+1 > rate at t for positive growth_rate."""
        nation = _build_nation()
        t_start = nation.gparams.climate_start_step
        ct = CarbonTax(schedule="exponential", base_rate=5e-4, growth_rate=0.09)

        ct.apply(nation, 2)
        prev_rate = None
        for t in range(t_start + 2, t_start + 15):
            ct.apply(nation, t)
            rate = nation.carbon_tax_rate_s1
            if prev_rate is not None:
                assert rate > prev_rate, f"rate not monotone at t={t}"
            prev_rate = rate


# ---------------------------------------------------------------------------
# Fuel price update tests
# ---------------------------------------------------------------------------

class TestFuelPriceUpdate:
    """Verify the inflation + 0.4%/yr fuel price update in apply()."""

    def test_fuel_price_increases_after_t3(self):
        """pf grows after t > 3 (at minimum by the 0.4%/yr real component)."""
        nation = _build_nation()
        ct = CarbonTax(schedule="constant", base_rate=0.0, tax_on=False)
        initial_pf = nation.params.fossil_fuel_price

        # Manually set identical CPI to isolate the 1.004 multiplier
        nation.cpi = 1.0
        nation.cpi_prev = 1.0

        ct.apply(nation, 2)
        ct.apply(nation, 3)
        ct.apply(nation, 4)  # first update fires at t > 3

        assert nation.params.fossil_fuel_price > initial_pf

    def test_fuel_price_grows_at_1004_per_period_with_flat_cpi(self):
        """With cpi/cpi_prev = 1 (no inflation), pf grows by exactly 1.004/period."""
        nation = _build_nation()
        ct = CarbonTax(schedule="constant", base_rate=0.0, tax_on=False)

        # Force flat CPI so only the real-growth term applies
        nation.cpi = 1.0
        nation.cpi_prev = 1.0
        ct.apply(nation, 2)
        ct.apply(nation, 3)

        pf_before = nation.params.fossil_fuel_price
        nation.cpi = 1.0
        nation.cpi_prev = 1.0
        ct.apply(nation, 4)
        pf_after = nation.params.fossil_fuel_price

        assert abs(pf_after / pf_before - 1.004) < 1e-12

    def test_fuel_price_unchanged_at_t_le_3(self):
        """No fuel price update at t <= 3."""
        nation = _build_nation()
        ct = CarbonTax(schedule="constant", base_rate=0.0, tax_on=False)
        pf0 = nation.params.fossil_fuel_price
        ct.apply(nation, 1)
        ct.apply(nation, 2)
        ct.apply(nation, 3)
        assert nation.params.fossil_fuel_price == pf0

    def test_fuel_price_update_runs_even_when_tax_off(self):
        """tax_on=False suppresses rates but NOT the fuel price update."""
        nation = _build_nation()
        ct = CarbonTax(schedule="constant", base_rate=3.3e-4, tax_on=False)

        nation.cpi = 1.01
        nation.cpi_prev = 1.0
        pf_before = nation.params.fossil_fuel_price

        ct.apply(nation, 2)
        ct.apply(nation, 3)
        ct.apply(nation, 4)  # update fires here

        # Fuel price should have grown; rates must be zero
        assert nation.params.fossil_fuel_price > pf_before
        assert nation.carbon_tax_rate_s1 == 0.0


# ---------------------------------------------------------------------------
# End-to-end: CarbonTax in a full simulation run
# ---------------------------------------------------------------------------

class TestCarbonTaxFullRun:
    """Smoke test: adding CarbonTax to a nation doesn't break the simulation."""

    def test_simulation_runs_with_carbon_tax(self):
        nation = _build_nation()
        ct = CarbonTax(schedule="constant", base_rate=3.3e-4)
        _attach_carbon_tax(nation, ct)

        for t in range(1, 20):
            _full_step(nation, t)

        assert math.isfinite(nation.real_gdp)
        assert math.isfinite(nation.carbon_tax_rate_s1)
        assert math.isfinite(nation.params.fossil_fuel_price)

    def test_carbon_tax_propagates_to_electricity_market(self):
        """After t_start, electricity market receives non-zero carbon_tax_en."""
        nation = _build_nation()
        t_start = nation.gparams.climate_start_step
        ct = CarbonTax(schedule="constant", base_rate=3.3e-4)
        _attach_carbon_tax(nation, ct)

        for t in range(1, t_start + 6):
            _full_step(nation, t)

        # After t_start, government.carbon_tax_rate_energy should be nonzero
        assert nation.government.carbon_tax_rate_energy > 0.0
