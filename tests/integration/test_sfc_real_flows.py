"""Integration test for Task 1.11 — PROFIT + ALLOC + GOV_BUDGET (skeleton).

Acceptance criterion from IMPLEMENTATION_PLAN:
    After PROFIT + ALLOC, `NationalAccounts.check_real_flows(tol=1e-6 * GDP)`
    passes for 10 random initial states stepped 20 times each.

We instantiate a small but realistic single-nation model (N1=10, N2=40, NB=1),
exercise the full production + dynamics phase loop, and verify the real-flow
identity at every step.
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

def _build_initialised_nation(
    seed: int = 0, n1: int = 10, n2: int = 40
) -> Nation:
    """Construct a fully-initialised single nation ready to run dynamics.

    Bypasses Simulation.__init__ to keep the test self-contained; uses the same
    init sequence the test_credit.py integration tests use.
    """
    gparams = GlobalParameters()
    gparams.n1_capital_good_firms = n1
    gparams.n2_consumption_good_firms = n2
    nparams = NationParameters()

    nation = Nation("sfc-test", params=nparams)
    nation.gparams = gparams
    nation.rng = np.random.default_rng(seed)

    # Labour market + central bank + household + government
    nation.labour_market.initialise_from_parameters(gparams, nparams)
    nation.central_bank.initialise_from_parameters(gparams, nparams)
    nation.household_sector.initialise_from_parameters(gparams, nparams)
    nation.government.initialise_from_parameters(gparams, nparams)

    # Capital-good firms
    for _ in range(n1):
        cf = CapitalGoodFirm(nation, nation.rng)
        cf.initialise_from_parameters(gparams)
        nation.capital_good_sector.add(cf)

    # Consumption-good firms (rotating preferred supplier)
    machine_counter = 0
    s2_firms = []
    for j in range(n2):
        f = ConsumptionGoodFirm(nation, nation.rng)
        machine_counter = f.initialise_from_parameters(
            gparams, nparams, j % n1, 0, machine_counter
        )
        nation.consumption_good_sector.add(f)
        s2_firms.append(f)

    # Banking sector (NB=1) — assigns firms to bank, initialises balance sheet
    nation.banking_sector.initialise_from_parameters(
        gparams, nparams, nation.rng, nation, s2_firms
    )

    return nation


def _run_one_step(nation: Nation, t: int) -> None:
    """Run production_phase + dynamics_phase for period t (no closeout / climate)."""
    nation.production_phase(t)
    nation.dynamics_phase(t)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSfcRealFlows:
    """Acceptance: real-flow SFC check passes for 10 seeds × 20 steps each."""

    @pytest.mark.parametrize("seed", list(range(10)))
    def test_real_flow_closes_each_step(self, seed: int) -> None:
        """For each of 10 random seeds, run 20 steps; check_real_flows must pass."""
        nation = _build_initialised_nation(seed=seed)

        for t in range(1, 21):
            _run_one_step(nation, t)

            gdp_scale = max(1.0, nation.gdp_nominal)
            tol = 1e-6 * gdp_scale

            ok = nation.accounting.check_real_flows(tol=tol)
            residual = nation.accounting.last_real_flow_residual
            assert ok, (
                f"SFC real-flow check failed at t={t}, seed={seed}: "
                f"residual={residual:.6g}, gdp={gdp_scale:.6g}, tol={tol:.6g}"
            )

    def test_real_flow_residual_is_finite(self) -> None:
        """The residual must be finite (no NaN/inf) after a single step."""
        nation = _build_initialised_nation(seed=42)
        _run_one_step(nation, t=1)
        nation.accounting.check_real_flows()
        assert np.isfinite(nation.accounting.last_real_flow_residual)


class TestProfitAccounting:
    """Per-firm and aggregate book-keeping established by PROFIT."""

    def test_sector1_profit_sets_fields(self) -> None:
        """Sector-1 firms have non-zero profit and updated net worth after PROFIT."""
        nation = _build_initialised_nation(seed=1)
        _run_one_step(nation, t=1)

        s1 = list(nation.capital_good_sector)
        # At least some firms should have realised positive sales-cost-RD
        assert any(f.profit != 0.0 for f in s1)
        assert all(f.net_worth >= 0.0 for f in s1)

    def test_sector2_profit_sets_fields(self) -> None:
        """Sector-2 firms have computed sales, mol, inventory updated after PROFIT."""
        nation = _build_initialised_nation(seed=1)
        _run_one_step(nation, t=1)

        s2 = list(nation.consumption_good_sector)
        # Sales > 0 for firms that produced and received demand
        active_with_sales = [f for f in s2 if f.is_alive and f.sales > 0.0]
        assert len(active_with_sales) > 0
        # Inventory should be ≥ 0 after PROFIT clamps
        assert all(f.inventory >= 0.0 for f in s2)

    def test_household_consumption_budget_set(self) -> None:
        """Cons = wage * LD + Divtot_prev + G; non-zero after first step."""
        nation = _build_initialised_nation(seed=1)
        _run_one_step(nation, t=1)
        assert nation.consumption_budget_nominal > 0.0
        assert nation.household_sector.consumption_budget == pytest.approx(
            nation.consumption_budget_nominal
        )

    def test_government_spending_matches_unemployment(self) -> None:
        """G = max(0, (LS-LD) * w * wu) in flagC=2 baseline.

        Note: G is computed during PROFIT *before* WAGE updates `lm.wage`,
        so the wage that fed into G is the pre-step wage (= `wage_init`
        at t=1).  Reading `lm.wage` after the step would use the post-WAGE
        value and miscompute the expected G.
        """
        nation = _build_initialised_nation(seed=1)
        _run_one_step(nation, t=1)

        wu = nation.params.unemployment_benefit_share
        ls = nation.labour_market.labour_supply
        ld = nation.labour_market.labour_demand_total
        wage_at_profit = nation.gparams.wage_init   # w(2) at t=1
        expected_G = max(0.0, (ls - ld) * wage_at_profit * wu)
        assert nation.government.spending == pytest.approx(expected_G)


class TestAllocConsumption:
    """ALLOC iterative allocation correctness."""

    def test_demand_assigned_to_all_firms(self) -> None:
        """After ALLOC, every alive firm has D2(1,j) >= 0."""
        nation = _build_initialised_nation(seed=2)
        _run_one_step(nation, t=1)
        s2 = list(nation.consumption_good_sector)
        for f in s2:
            if f.is_alive:
                assert f.demand >= 0.0

    def test_unfilled_demand_set(self) -> None:
        """l2(j) = 1 for satisfied firms, >= 1 for rationed firms."""
        nation = _build_initialised_nation(seed=2)
        _run_one_step(nation, t=1)
        for f in nation.consumption_good_sector:
            if f.is_alive and f.market_share > 0.0:
                assert f.unfilled_demand >= 1.0 - 1e-9, (
                    f"l2(j)={f.unfilled_demand} should be ≥ 1"
                )

    def test_total_real_served_plus_cpast_equals_initial_budget(self) -> None:
        """Σ min(D2(j), Q2(j)+N_prev(j)) + Cpast ≈ Cons/cpi (real budget closure).

        This is the C++ ALLOC closure: of the initial real budget Cres = Cons/cpi,
        either supply gets served (Σ actual_consumption) or it remains as forced
        household saving (Cpast). The cumulative D2(j) itself can exceed Cres for
        non-rationed firms because iteration 1 adds full D_temp regardless of
        rationing — the C++ uses min() in PROFIT to derive served consumption.
        """
        nation = _build_initialised_nation(seed=2)
        _run_one_step(nation, t=1)
        Cons = nation.consumption_budget_nominal
        cpi = nation.cpi
        cres_initial = Cons / cpi

        total_served = 0.0
        for f in nation.consumption_good_sector:
            if not f.is_alive:
                continue
            # Reconstruct opening inventory N(2,j): PROFIT set N(1,j) = max(0, Q2+N_prev-D2)
            # so N_prev = N_new + actual_cons - Q2 (when not rationed at supply)
            # Simpler: use the just-recorded inventory_change_real stored on the firm.
            # Even simpler: served = min(D2, supply_open). Supply_open is no longer
            # directly recoverable post-PROFIT, but in this test we rerun ALLOC's
            # cap directly using the FIRM totals tracked by Nation aggregates.
            pass

        # Use Nation's aggregate, computed during realise_profits_and_taxes
        total_served = nation.total_real_consumption
        Cpast = nation.household_sector.unmet_real_demand_prev
        assert total_served + Cpast == pytest.approx(cres_initial, rel=1e-6, abs=1.0)


class TestSector1RealClosure:
    """Sector-1 production = sector-1 demand (Q1 = D1 by construction)."""

    def test_sector1_production_equals_demand(self) -> None:
        """Σ Q1 = Σ D1 after PRODMACH (with labour rationing accounted for)."""
        nation = _build_initialised_nation(seed=3)
        _run_one_step(nation, t=1)

        sum_q1 = sum(f.production for f in nation.capital_good_sector if f.is_alive)
        sum_d1 = sum(f.demand for f in nation.capital_good_sector if f.is_alive)
        # Allow tiny rounding (the C++ uses floor() in labour rationing)
        assert sum_q1 == pytest.approx(sum_d1, abs=1.0)
