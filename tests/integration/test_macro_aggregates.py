"""Integration tests for Task 1.12 — MACRO + WAGE.

Acceptance criteria from IMPLEMENTATION_PLAN:
    - aggregate GDP equals sum of firm production values plus inventory change;
    - unemployment_rate = (LS - LD) / LS.

Additional checks: PPI > 0, wage > 0 and updates, nominal GDP identity.
"""
from __future__ import annotations

import numpy as np
import pytest

from dsk.agents.capital_good_firm import CapitalGoodFirm
from dsk.agents.consumption_good_firm import ConsumptionGoodFirm
from dsk.nation import Nation
from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_nation(seed: int = 0, n1: int = 10, n2: int = 40) -> Nation:
    gparams = GlobalParameters()
    gparams.n1_capital_good_firms = n1
    gparams.n2_consumption_good_firms = n2
    nparams = NationParameters()

    nation = Nation("macro-test", params=nparams)
    nation.gparams = gparams
    nation.rng = np.random.default_rng(seed)

    nation.labour_market.initialise_from_parameters(gparams, nparams)
    nation.central_bank.initialise_from_parameters(gparams, nparams)
    nation.household_sector.initialise_from_parameters(gparams, nparams)
    nation.government.initialise_from_parameters(gparams, nparams)

    for _ in range(n1):
        cf = CapitalGoodFirm(nation, nation.rng)
        cf.initialise_from_parameters(gparams)
        nation.capital_good_sector.add(cf)

    machine_counter = 0
    s2_firms = []
    for j in range(n2):
        f = ConsumptionGoodFirm(nation, nation.rng)
        machine_counter = f.initialise_from_parameters(
            gparams, nparams, j % n1, 0, machine_counter
        )
        nation.consumption_good_sector.add(f)
        s2_firms.append(f)

    nation.banking_sector.initialise_from_parameters(
        gparams, nparams, nation.rng, nation, s2_firms
    )
    return nation


def _run_step(nation: Nation, t: int) -> None:
    nation.production_phase(t)
    nation.dynamics_phase(t)


def _expected_real_gdp(nation: Nation) -> float:
    """Recompute real GDP from post-step firm state (mirrors aggregate_macro_indicators)."""
    alive_s1 = [f for f in nation.capital_good_sector if f.is_alive]
    alive_s2 = [f for f in nation.consumption_good_sector if f.is_alive]

    Qtot1 = sum(f.production for f in alive_s1)
    p1m = nation.capital_good_sector.mean_price
    p2m = sum(f.price for f in alive_s2) / len(alive_s2) if alive_s2 else 1.0

    cpi = nation.cpi
    Cons = nation.consumption_budget_nominal
    Creal = Cons / cpi if cpi > 0.0 else 0.0
    dNtot = nation.total_real_inventory_change
    Ir = Qtot1

    gdp = Creal + (Ir * p1m / p2m if p2m > 0.0 else 0.0) + dNtot
    if -1.0 < gdp < 0.0:
        gdp = 0.0
    return gdp


def _expected_nominal_gdp(nation: Nation) -> float:
    """Recompute nominal GDP from post-step firm state."""
    alive_s1 = [f for f in nation.capital_good_sector if f.is_alive]
    alive_s2 = [f for f in nation.consumption_good_sector if f.is_alive]

    Cmon = sum(f.price * f.production for f in alive_s2)
    Imon = sum(f.price * f.production for f in alive_s1)
    return Cmon + Imon + nation.inventory_change_nominal


# ---------------------------------------------------------------------------
# Tests — unemployment identity
# ---------------------------------------------------------------------------

class TestUnemploymentFormula:
    """Acceptance: unemployment_rate = (LS - LD) / LS after MACRO."""

    @pytest.mark.parametrize("seed", [0, 1, 2, 5, 7])
    def test_unemployment_rate_matches_formula(self, seed: int) -> None:
        """unemployment_rate = max(0, (LS - LD) / LS) holds exactly after MACRO."""
        nation = _build_nation(seed=seed)
        _run_step(nation, t=1)

        lm = nation.labour_market
        LS = lm.labour_supply   # unchanged (labour_supply_growth=0 by default)
        LD = lm.labour_demand_total
        expected = max(0.0, (LS - LD) / LS) if LS > 0.0 else 0.0

        assert lm.unemployment_rate == pytest.approx(expected, abs=1e-12), (
            f"seed={seed}: U={lm.unemployment_rate:.10f}, expected={expected:.10f}, "
            f"LS={LS:.1f}, LD={LD:.1f}"
        )

    def test_unemployment_is_non_negative(self) -> None:
        nation = _build_nation(seed=42)
        _run_step(nation, t=1)
        assert nation.labour_market.unemployment_rate >= 0.0

    def test_unemployment_rate_multi_step(self) -> None:
        """Formula holds at every step over a 5-step run."""
        nation = _build_nation(seed=3)
        for t in range(1, 6):
            _run_step(nation, t)
            lm = nation.labour_market
            LS = lm.labour_supply
            LD = lm.labour_demand_total
            expected = max(0.0, (LS - LD) / LS) if LS > 0.0 else 0.0
            assert lm.unemployment_rate == pytest.approx(expected, abs=1e-12), (
                f"t={t}: U={lm.unemployment_rate:.10f}, expected={expected:.10f}"
            )


# ---------------------------------------------------------------------------
# Tests — GDP identities
# ---------------------------------------------------------------------------

class TestGDPFormula:
    """Acceptance: real_gdp = Creal + Ir*p1m/p2m + dNtot."""

    def test_real_gdp_matches_components(self) -> None:
        """Nation.real_gdp equals the component formula reconstructed from firm state."""
        nation = _build_nation(seed=0)
        _run_step(nation, t=1)

        expected = _expected_real_gdp(nation)
        assert nation.real_gdp == pytest.approx(expected, rel=1e-10, abs=1e-10), (
            f"real_gdp={nation.real_gdp:.8g}, expected={expected:.8g}"
        )

    def test_nominal_gdp_matches_components(self) -> None:
        """Nation.gdp_nominal = Cmon + Imon + dNmtot (production-value identity)."""
        nation = _build_nation(seed=0)
        _run_step(nation, t=1)

        expected = _expected_nominal_gdp(nation)
        assert nation.gdp_nominal == pytest.approx(expected, rel=1e-10, abs=1e-10), (
            f"gdp_nominal={nation.gdp_nominal:.8g}, expected={expected:.8g}"
        )

    def test_real_gdp_formula_multi_step(self) -> None:
        """Real GDP formula holds at every step over a 5-step run."""
        nation = _build_nation(seed=1)
        for t in range(1, 6):
            _run_step(nation, t)
            expected = _expected_real_gdp(nation)
            assert nation.real_gdp == pytest.approx(expected, rel=1e-10, abs=1e-10), (
                f"t={t}: real_gdp={nation.real_gdp:.8g}, expected={expected:.8g}"
            )

    @pytest.mark.parametrize("seed", [0, 2, 4])
    def test_real_gdp_is_non_negative(self, seed: int) -> None:
        """GDP must be non-negative (small-negative clamp applied)."""
        nation = _build_nation(seed=seed)
        _run_step(nation, t=1)
        assert nation.real_gdp >= 0.0, f"seed={seed}: real_gdp={nation.real_gdp}"


# ---------------------------------------------------------------------------
# Tests — wage update
# ---------------------------------------------------------------------------

class TestWageUpdate:
    """WAGE function updates nominal wage positively each period."""

    def test_wage_is_positive_after_first_step(self) -> None:
        nation = _build_nation(seed=0)
        _run_step(nation, t=1)
        assert nation.labour_market.wage > 0.0

    def test_wage_changes_over_time(self) -> None:
        """Wage should change from its initialisation value over 5 steps."""
        nation = _build_nation(seed=0)
        wage_initial = nation.labour_market.wage
        wages = []
        for t in range(1, 6):
            _run_step(nation, t)
            wages.append(nation.labour_market.wage)

        assert all(w > 0.0 for w in wages), "Wage must stay positive"
        # At least one step should produce a non-zero wage change
        assert any(abs(w - wage_initial) > 1e-12 for w in wages), (
            "Wage never changed from initial value over 5 steps"
        )

    def test_real_wage_is_positive(self) -> None:
        """Real wage = w/cpi must be positive."""
        nation = _build_nation(seed=0)
        _run_step(nation, t=1)
        assert nation.real_wage > 0.0

    def test_ppi_is_positive(self) -> None:
        """Production price index must be positive after MACRO."""
        nation = _build_nation(seed=0)
        _run_step(nation, t=1)
        assert nation.ppi > 0.0

    def test_wage_change_stored_on_labour_market(self) -> None:
        """labour_market.wage_change is set during WAGE."""
        nation = _build_nation(seed=0)
        _run_step(nation, t=1)
        # wage_change should be a finite number (could be 0 at t=1 when d_cpi=0)
        assert np.isfinite(nation.labour_market.wage_change)

    def test_wage_subsistence_floor_respected(self) -> None:
        """wage >= w_min (subsistence floor) after WAGE."""
        nation = _build_nation(seed=0)
        w_min = nation.gparams.wage_subsistence
        for t in range(1, 4):
            _run_step(nation, t)
            assert nation.labour_market.wage >= w_min - 0.001, (
                f"t={t}: wage={nation.labour_market.wage:.6f} < w_min={w_min}"
            )


# ---------------------------------------------------------------------------
# Tests — s1 market shares
# ---------------------------------------------------------------------------

class TestS1MarketShares:
    """MACRO updates s1 market shares to f1(i) = Q1(i)/Qtot1."""

    def test_s1_shares_sum_to_one(self) -> None:
        """After MACRO, Σ f1(i) = 1 for alive sector-1 firms."""
        nation = _build_nation(seed=0)
        _run_step(nation, t=1)

        alive = [f for f in nation.capital_good_sector if f.is_alive]
        if alive:
            total = sum(f.market_share for f in alive)
            assert total == pytest.approx(1.0, abs=1e-10), (
                f"s1 market shares sum to {total:.10f}, not 1.0"
            )

    def test_s1_share_proportional_to_production(self) -> None:
        """f1(i) = Q1(i)/Qtot1 for each alive sector-1 firm."""
        nation = _build_nation(seed=0)
        _run_step(nation, t=1)

        alive = [f for f in nation.capital_good_sector if f.is_alive]
        Qtot1 = sum(f.production for f in alive)
        if Qtot1 > 0.0:
            for f in alive:
                expected_share = f.production / Qtot1
                assert f.market_share == pytest.approx(expected_share, abs=1e-12), (
                    f"firm share={f.market_share:.10f}, expected={expected_share:.10f}"
                )
