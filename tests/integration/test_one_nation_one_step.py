"""Integration test for Task 1.16 — Wire phase methods.

Acceptance criterion from IMPLEMENTATION_PLAN:
    A 1-step run from the baseline initial state produces non-NaN, non-zero
    values for GDP, unemployment_rate, and wage.

Uses N1=10, N2=40 (same scale as all other M1 integration tests) for speed.
The phase wrappers (production_phase, dynamics_phase, closeout_phase) were
wired progressively during tasks 1.5–1.15; this test exercises the full
end-to-end sequence and catches any wiring omissions.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from dsk.nation import Nation
from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_nation(seed: int = 42, n1: int = 10, n2: int = 40) -> Nation:
    """Build a fully-initialised single nation ready to step.

    Scales ``labour_supply_init`` proportionally to N2 — the
    ``GlobalParameters`` default is LS=500_000 for N2=400, so with the
    test's small N2=40 we use LS=50_000 to keep the per-firm scale of
    expected demand vs initial capacity sane.  Without this, with the
    higher ``wu=0.7`` baseline override per-firm De would massively
    exceed K0=800 and dN drawdown drives nominal GDP negative on
    one-step tests — a numerical corner of the small-N harness, not a
    model bug.
    """
    gparams = GlobalParameters()
    gparams.n1_capital_good_firms = n1
    gparams.n2_consumption_good_firms = n2
    # Default LS_init is calibrated for N2=400; scale linearly with N2.
    gparams.labour_supply_init = (
        gparams.labour_supply_init * (n2 / 400.0)
    )
    nparams = NationParameters()

    nation = Nation("m1-test", params=nparams)
    nation.rng = np.random.default_rng(seed)
    nation.initialise_from_parameters(gparams, nparams)
    return nation


def _full_step(nation: Nation, t: int) -> None:
    nation.production_phase(t)
    nation.dynamics_phase(t)
    nation.closeout_phase(t)


# ---------------------------------------------------------------------------
# Acceptance tests
# ---------------------------------------------------------------------------

class TestOneNationOneStep:
    """Task 1.16 acceptance: single step produces finite, non-zero GDP/wage/unemployment."""

    def test_gdp_real_positive(self):
        nation = _build_nation()
        _full_step(nation, 1)
        assert math.isfinite(nation.real_gdp), "real_gdp is not finite"
        assert nation.real_gdp > 0, f"real_gdp = {nation.real_gdp}"

    def test_gdp_nominal_positive(self):
        nation = _build_nation()
        _full_step(nation, 1)
        assert math.isfinite(nation.gdp_nominal), "gdp_nominal is not finite"
        assert nation.gdp_nominal > 0, f"gdp_nominal = {nation.gdp_nominal}"

    def test_unemployment_rate_finite_and_nonneg(self):
        nation = _build_nation()
        _full_step(nation, 1)
        u = nation.labour_market.unemployment_rate
        assert math.isfinite(u), "unemployment_rate is not finite"
        assert u >= 0.0, f"unemployment_rate = {u}"

    def test_wage_positive(self):
        nation = _build_nation()
        _full_step(nation, 1)
        w = nation.labour_market.wage
        assert math.isfinite(w), "wage is not finite"
        assert w > 0.0, f"wage = {w}"

    def test_cpi_positive(self):
        nation = _build_nation()
        _full_step(nation, 1)
        assert math.isfinite(nation.cpi) and nation.cpi > 0.0, f"cpi = {nation.cpi}"

    def test_sector_sizes_unchanged(self):
        """Entry replaces exit: sector sizes must stay constant after one step."""
        nation = _build_nation()
        n1_before = len(nation.capital_good_sector)
        n2_before = len(nation.consumption_good_sector)
        _full_step(nation, 1)
        assert len(nation.capital_good_sector) == n1_before
        assert len(nation.consumption_good_sector) == n2_before

    @pytest.mark.parametrize("seed", [0, 1, 2])
    def test_three_seeds(self, seed):
        """Acceptance holds across three different random seeds."""
        nation = _build_nation(seed=seed)
        _full_step(nation, 1)
        assert math.isfinite(nation.real_gdp) and nation.real_gdp > 0
        assert math.isfinite(nation.labour_market.wage) and nation.labour_market.wage > 0
        assert nation.labour_market.unemployment_rate >= 0.0


# ---------------------------------------------------------------------------
# Multi-step stability
# ---------------------------------------------------------------------------

class TestMultiStepStability:
    """Five-step run stays finite and non-degenerate."""

    def test_five_steps_no_nan(self):
        nation = _build_nation()
        for t in range(1, 6):
            _full_step(nation, t)
        assert math.isfinite(nation.real_gdp) and nation.real_gdp > 0
        assert math.isfinite(nation.labour_market.wage) and nation.labour_market.wage > 0
        assert nation.labour_market.unemployment_rate >= 0.0

    def test_update_shifts_prev_fields(self):
        """After closeout, market_share_prev equals this period's market_share."""
        nation = _build_nation()
        nation.production_phase(1)
        nation.dynamics_phase(1)
        # Capture current shares before closeout
        shares_now = {
            f.unique_id: f.market_share
            for f in nation.consumption_good_sector
        }
        nation.closeout_phase(1)
        # After UPDATE, market_share_prev should equal what was market_share
        for firm in nation.consumption_good_sector:
            assert firm.market_share_prev == pytest.approx(shares_now[firm.unique_id]), (
                f"firm {firm.unique_id}: market_share_prev {firm.market_share_prev} != "
                f"pre-UPDATE market_share {shares_now[firm.unique_id]}"
            )

    @pytest.mark.parametrize("seed", [7, 13, 99])
    def test_three_seeds_five_steps(self, seed):
        nation = _build_nation(seed=seed)
        for t in range(1, 6):
            _full_step(nation, t)
        assert math.isfinite(nation.real_gdp) and nation.real_gdp > 0
        assert math.isfinite(nation.gdp_nominal) and nation.gdp_nominal > 0
        assert math.isfinite(nation.labour_market.wage) and nation.labour_market.wage > 0


# ---------------------------------------------------------------------------
# initialise_from_parameters unit check
# ---------------------------------------------------------------------------

class TestInitialiseFromParameters:
    """Nation.initialise_from_parameters populates all sectors correctly."""

    def test_sector_1_populated(self):
        nation = _build_nation(n1=5, n2=20)
        assert len(nation.capital_good_sector) == 5

    def test_sector_2_populated(self):
        nation = _build_nation(n1=5, n2=20)
        assert len(nation.consumption_good_sector) == 20

    def test_banking_sector_populated(self):
        nation = _build_nation(n1=5, n2=20)
        assert len(nation.banking_sector) >= 1

    def test_labour_market_initialised(self):
        nation = _build_nation()
        lm = nation.labour_market
        assert lm.wage > 0.0
        assert lm.labour_supply > 0.0
        assert lm.mean_machine_prod > 0.0

    def test_gparams_set(self):
        gparams = GlobalParameters()
        gparams.n1_capital_good_firms = 5
        gparams.n2_consumption_good_firms = 20
        nation = Nation("init-test")
        nation.rng = np.random.default_rng(0)
        nation.initialise_from_parameters(gparams)
        assert nation.gparams is gparams
