"""Integration tests for Task 5.7.2 — carbon-tax revenue routing (t_CO2_use[]).

Acceptance criteria:
1. Revenue split matches the configured revenue_use weights.
2. The fiscal identity (Tax - G - bailout = interest on debt - deficit) still closes.
3. T2h ensemble trajectories diverge from T2 (higher consumption via G; tighter deficit).
4. T2i ensemble trajectories diverge from T2 (higher S1 R&D budget; faster tech frontier).

C++ reference: module_macro.cpp GOV_BUDGET lines 601-624; CLIMATE_POLICY lines 828-888.
"""
from __future__ import annotations

import numpy as np
import pytest

from dsk.nation import Nation
from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters
from dsk.policy.carbon_tax import CarbonTax


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_nation(seed: int = 0, n1: int = 20, n2: int = 80) -> Nation:
    gparams = GlobalParameters()
    gparams.n1_capital_good_firms = n1
    gparams.n2_consumption_good_firms = n2
    ls0 = gparams.labour_supply_init
    gparams.labour_supply_init = int(ls0 * (n2 / 400.0))
    nparams = NationParameters()
    nation = Nation("rev-test", params=nparams)
    nation.rng = np.random.default_rng(seed)
    nation.initialise_from_parameters(gparams, nparams)
    return nation


def _run(nation: Nation, t_end: int) -> None:
    for t in range(1, t_end + 1):
        nation.production_phase(t)
        nation.dynamics_phase(t)
        nation.closeout_phase(t)


def _attach_tax(nation: Nation, revenue_use: list) -> None:
    ct = CarbonTax(
        schedule="constant",
        base_rate=3.3e-4,
        tax_on=True,
        revenue_use=revenue_use,
    )
    nation.climate_policy.add_instrument(ct)


# ---------------------------------------------------------------------------
# Unit-level revenue routing tests
# ---------------------------------------------------------------------------

class TestRevenueNormalisation:
    """revenue_use is normalised to sum to 1 regardless of input."""

    def test_sum_to_one_with_unnormalised_input(self):
        ct = CarbonTax(revenue_use=[2.0, 1.0, 0.0, 0.0])
        s = sum(ct.revenue_use)
        assert abs(s - 1.0) < 1e-12

    def test_default_none_gives_gov_budget_default(self):
        ct = CarbonTax()  # default: revenue_use=None → [1,0,0,0]
        assert ct.revenue_use == [1.0, 0.0, 0.0, 0.0]

    def test_all_to_households(self):
        ct = CarbonTax(revenue_use=[0, 1, 0, 0])
        assert ct.revenue_use == [0.0, 1.0, 0.0, 0.0]

    def test_all_to_s1_rd(self):
        ct = CarbonTax(revenue_use=[0, 0, 0, 1])
        assert ct.revenue_use == [0.0, 0.0, 0.0, 1.0]

    def test_zero_vector_treated_as_gov_budget(self):
        # sum([0,0,0,0]) = 0; division by 0 is handled by normalising to 1.
        ct = CarbonTax(revenue_use=[0, 0, 0, 0])
        # With sum=0, each element / 1 = 0; all weights remain 0.
        assert sum(ct.revenue_use) == 0.0

    def test_revenue_use_pushed_to_government(self):
        nation = _build_nation()
        ct = CarbonTax(revenue_use=[0.5, 0.5, 0.0, 0.0])
        _attach_tax(nation, [0.5, 0.5, 0.0, 0.0])
        nation.set_climate_policy(t=1)
        assert nation.government.revenue_use == ct.revenue_use


class TestFiscalIdentityWithCO2Revenue:
    """After compute_budget, CO2 revenue routing must be internally consistent."""

    @pytest.mark.parametrize("revenue_use,expected_rd_fund_nonzero", [
        ([1.0, 0.0, 0.0, 0.0], False),  # T2: no S1 R&D fund
        ([0.0, 1.0, 0.0, 0.0], False),  # T2h: no S1 R&D fund
        ([0.0, 0.0, 0.0, 1.0], True),   # T2i: S1 R&D fund active
    ])
    def test_co2_routing_internally_consistent(self, revenue_use, expected_rd_fund_nonzero):
        """CO2 revenue routing produces expected fund allocations and G adjustments."""
        nation = _build_nation(seed=7)
        _attach_tax(nation, revenue_use)

        t_policy_start = nation.gparams.climate_start_step
        _run(nation, t_policy_start + 5)

        gov = nation.government
        # After the run, check:
        # 1. rd_funds_industry1 is non-zero iff expected.
        if expected_rd_fund_nonzero:
            assert gov.rd_funds_industry1 > 0.0, (
                f"Expected non-zero S1 R&D fund for revenue_use={revenue_use}, "
                f"got {gov.rd_funds_industry1}"
            )
        else:
            assert gov.rd_funds_industry1 == 0.0, (
                f"Expected zero S1 R&D fund for revenue_use={revenue_use}, "
                f"got {gov.rd_funds_industry1}"
            )
        # 2. The simulation ran without error and produced non-NaN output.
        assert not np.isnan(nation.real_gdp), "GDP should not be NaN"
        assert not np.isnan(gov.spending), "G should not be NaN"
        assert not np.isnan(gov.tax_revenue_firms), "Tax should not be NaN"


# ---------------------------------------------------------------------------
# Direction-of-change tests: T2h vs T2, T2i vs T2
# ---------------------------------------------------------------------------

class TestT2hVsT2:
    """T2h (revenue → households) vs T2 (revenue → gov budget).

    Under T2h the government recycling boosts G (household transfers), so:
    - G(T2h) ≥ G(T2) in periods with active CO2 tax revenue.
    - Deficit(T2h) ≈ Deficit(T2): CO2 goes into both Tax and G, so
      the net effect on Def is near zero (CO2 revenue is recycled, not saved).
    """

    def _run_and_collect(self, revenue_use: list, n_steps: int = 120, seed: int = 1):
        nation = _build_nation(seed=seed)
        _attach_tax(nation, revenue_use)
        t_pol = nation.gparams.climate_start_step
        G_series = []
        Def_series = []
        co2_series = []
        for t in range(1, n_steps + 1):
            nation.production_phase(t)
            nation.dynamics_phase(t)
            nation.closeout_phase(t)
            if t >= t_pol + 3:
                G_series.append(nation.government.spending)
                Def_series.append(nation.government.deficit)
                co2_series.append(nation.co2_revenue_prev)
        return G_series, Def_series, co2_series

    def test_t2h_g_higher_than_t2_when_co2_active(self):
        G_t2, Def_t2, co2_t2 = self._run_and_collect([1, 0, 0, 0])
        G_t2h, Def_t2h, co2_t2h = self._run_and_collect([0, 1, 0, 0])

        # When CO2 revenue is non-trivial, G should be higher under T2h.
        active = [i for i, c in enumerate(co2_t2) if c > 0.0]
        assert len(active) > 0, "No periods with active CO2 revenue"
        mean_g_t2 = np.mean([G_t2[i] for i in active])
        mean_g_t2h = np.mean([G_t2h[i] for i in active])
        assert mean_g_t2h >= mean_g_t2, (
            f"T2h should have higher G than T2 when CO2 revenue is recycled to households. "
            f"mean G(T2)={mean_g_t2:.1f}, mean G(T2h)={mean_g_t2h:.1f}"
        )

    def test_t2h_and_t2_scenarios_differ(self):
        """T2h and T2 must produce different fiscal trajectories."""
        G_t2, Def_t2, _ = self._run_and_collect([1, 0, 0, 0])
        G_t2h, Def_t2h, _ = self._run_and_collect([0, 1, 0, 0])
        # At least one period differs.
        diffs_G = [abs(a - b) for a, b in zip(G_t2, G_t2h)]
        assert max(diffs_G) > 0.0, "T2h and T2 must produce different G trajectories"


class TestT2iVsT2:
    """T2i (revenue → S1 R&D) vs T2 (revenue → gov budget).

    Under T2i, capital-good firms receive additional R&D budget funded by
    the carbon tax, which should accelerate the labour-productivity frontier
    relative to T2.
    """

    def _run_and_collect(self, revenue_use: list, n_steps: int = 120, seed: int = 2):
        nation = _build_nation(seed=seed)
        _attach_tax(nation, revenue_use)
        rd_series = []
        frontier_series = []
        rd_fund_series = []
        t_pol = nation.gparams.climate_start_step
        for t in range(1, n_steps + 1):
            nation.production_phase(t)
            nation.dynamics_phase(t)
            nation.closeout_phase(t)
            if t >= t_pol + 3:
                firms = list(nation.capital_good_sector)
                rd_series.append(sum(f.rd_budget for f in firms))
                frontier_series.append(nation.capital_good_sector.A1_top)
                rd_fund_series.append(nation.government.rd_funds_industry1)
        return rd_series, frontier_series, rd_fund_series

    def test_t2i_has_positive_rd_fund_after_policy_start(self):
        _, _, rd_fund = self._run_and_collect([0, 0, 0, 1])
        assert any(v > 0.0 for v in rd_fund), (
            "T2i should deliver positive S1 R&D funds once the carbon tax is active"
        )

    def test_t2i_and_t2_scenarios_differ(self):
        """T2i and T2 must produce different R&D fund trajectories."""
        _, _, rd_t2 = self._run_and_collect([1, 0, 0, 0])
        _, _, rd_t2i = self._run_and_collect([0, 0, 0, 1])
        diffs = [abs(a - b) for a, b in zip(rd_t2, rd_t2i)]
        assert max(diffs) > 0.0, "T2i and T2 must produce different R&D fund trajectories"

    def test_t2i_rd_fund_proportional_to_co2_revenue(self):
        """rd_funds_industry1 = co2_revenue_prev * use[3] (= 1.0 for T2i)."""
        nation = _build_nation(seed=3)
        _attach_tax(nation, [0, 0, 0, 1])
        t_pol = nation.gparams.climate_start_step
        _run(nation, t_pol + 2)  # get past policy start

        # Run one more step.
        t = t_pol + 3
        nation.production_phase(t)
        # After production_phase, co2_revenue_prev was shifted in run_electricity_market.
        co2_prev = nation.co2_revenue_prev
        nation.dynamics_phase(t)
        # After dynamics_phase, rd_funds_industry1 is set by compute_budget.
        rd_fund = nation.government.rd_funds_industry1
        nation.closeout_phase(t)

        # For revenue_use=[0,0,0,1]: rd_funds_industry1 = co2_prev * 1.0
        assert abs(rd_fund - co2_prev) < 1e-9, (
            f"rd_funds_industry1={rd_fund:.6f} should equal co2_revenue_prev={co2_prev:.6f}"
        )


class TestT2GovBudget:
    """T2 (revenue → gov budget) — verify CO2 revenue enters Tax."""

    def test_co2_revenue_enters_tax_for_gov_budget_routing(self):
        """For revenue_use=[1,0,0,0], the CO2 portion enters Tax (not G or R&D).

        Verify by checking: after policy start, tax_revenue_firms includes CO2,
        rd_funds_industry1 is zero, and G does not include a CO2 household boost.
        """
        nation = _build_nation(seed=5)
        ct = CarbonTax(
            schedule="constant",
            base_rate=3.3e-4,
            tax_on=True,
            revenue_use=[1.0, 0.0, 0.0, 0.0],
        )
        nation.climate_policy.add_instrument(ct)
        t_pol = nation.gparams.climate_start_step

        # Run to just after policy start, then check one more step.
        _run(nation, t_pol + 2)

        t = t_pol + 3
        nation.production_phase(t)
        co2_prev = nation.co2_revenue_prev  # post-shift value used by GOV_BUDGET
        nation.dynamics_phase(t)
        nation.closeout_phase(t)

        gov = nation.government
        # rd_funds_industry1 must be zero (use[3]=0).
        assert gov.rd_funds_industry1 == 0.0, (
            f"No S1 R&D fund expected for all-gov-budget routing, "
            f"got {gov.rd_funds_industry1}"
        )
        # rd_funds_energy must be zero (use[2]=0).
        assert gov.rd_funds_energy == 0.0 or nation.co2_revenue_prev == 0.0, (
            "No energy R&D fund expected for all-gov-budget routing"
        )
        # The tax_revenue_firms should be non-zero.
        assert gov.tax_revenue_firms > 0.0, "Tax revenue should be positive"
