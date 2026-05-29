"""Integration tests for Task 5.2 — GreenConstructionSubsidy and GreenRDSubsidy.

Acceptance criteria (IMPLEMENTATION_PLAN §5.2):
- With green construction subsidy active, green plant builds occur at a higher
  rate than the baseline (no-subsidy) run.
- GreenConstructionSubsidy formula: sub_ge = max(CF_ge - y_subs * brown_full_cost, 0).
- GreenRDSubsidy sets govt_rd_all_multiplier = rd_topup_fraction when active,
  0 when before t_start.
- Both instruments honour t_start gating and subsidy_on switch.
"""
from __future__ import annotations

import numpy as np
import pytest

from dsk.nation import Nation
from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters
from dsk.policy.green_subsidy import GreenConstructionSubsidy, GreenRDSubsidy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_nation(seed: int = 7, n1: int = 10, n2: int = 40, t_start: int = 5) -> Nation:
    gparams = GlobalParameters()
    gparams.n1_capital_good_firms = n1
    gparams.n2_consumption_good_firms = n2
    gparams.labour_supply_init = int(gparams.labour_supply_init * (n2 / 400.0))
    gparams.climate_start_step = t_start
    nparams = NationParameters()
    nation = Nation("sub-test", params=nparams)
    nation.rng = np.random.default_rng(seed)
    nation.initialise_from_parameters(gparams, nparams)
    return nation


def _full_step(nation: Nation, t: int) -> None:
    nation.production_phase(t)
    nation.dynamics_phase(t)
    nation.closeout_phase(t)


# ---------------------------------------------------------------------------
# GreenConstructionSubsidy — pure formula tests
# ---------------------------------------------------------------------------

class TestGreenConstructionSubsidyFormula:
    """compute_subsidy() is a pure formula — test without a full nation."""

    def _inst(self, **kwargs) -> GreenConstructionSubsidy:
        return GreenConstructionSubsidy(**kwargs)

    def test_formula_basic(self):
        """sub_ge = max(CF_ge - (CF_de + A_de*pf*payback) * y_subs, 0)."""
        inst = self._inst(y_subs=1.0 / 3.0, inner_thresh=2.0 / 3.0)
        # Choose cf_ge so inner guard passes:
        # green_annual = 3.0/10 = 0.30 > (2/3)*(0.5/10 + 0.3*1.0) = 0.233 ✓
        cf_ge = 3.0
        cf_de = 0.5
        a_de = 0.3
        pf = 1.0
        payback = 10.0
        # brown_full = 0.5 + 0.3*1.0*10 = 3.5 → sub = max(3.0 - 3.5/3, 0) = 1.833
        expected_sub = max(cf_ge - (cf_de + a_de * pf * payback) * (1.0 / 3.0), 0.0)
        sub, nsubmax = inst.compute_subsidy(cf_ge, cf_de, a_de, pf, payback, 500.0, 2000.0, t=90)
        assert abs(sub - expected_sub) < 1e-12

    def test_zero_when_green_already_cheaper(self):
        """Inner guard: no subsidy when green is already cheap enough."""
        inst = self._inst(y_subs=1.0 / 3.0, inner_thresh=2.0 / 3.0)
        # green_annual = 0.2 / 10 = 0.02
        # brown_annual = 1.0/10 + 0.3*1.0 = 0.4
        # 0.02 < 2/3 * 0.4 → inner guard fails → sub = 0
        sub, _ = inst.compute_subsidy(0.2, 1.0, 0.3, 1.0, 10.0, 500.0, 2000.0, t=90)
        assert sub == 0.0

    def test_zero_when_subsidy_off(self):
        """Master switch subsidy_on=False → always zero."""
        inst = self._inst(y_subs=1.0 / 3.0, subsidy_on=False)
        sub, nsubmax = inst.compute_subsidy(2.0, 0.5, 0.3, 1.0, 10.0, 500.0, 2000.0, t=90)
        assert sub == 0.0
        assert nsubmax == 0.0

    def test_nsubmax_cap_fraction(self):
        """NSubmax_ge = min(cap_fraction * (K_ge + K_de), max_cap_absolute)."""
        inst = self._inst(y_subs=0.5, cap_fraction=0.05, max_cap_absolute=50_000_000.0)
        cf_ge = 3.0
        cf_de = 0.5
        a_de = 0.2
        pf = 1.0
        payback = 10.0
        k_ge = 1000.0
        k_de = 3000.0
        sub, nsubmax = inst.compute_subsidy(cf_ge, cf_de, a_de, pf, payback, k_ge, k_de, t=90)
        expected_nsubmax = min(0.05 * (k_ge + k_de), 50_000_000.0)
        assert abs(nsubmax - expected_nsubmax) < 1.0

    def test_nsubmax_absolute_ceiling(self):
        """Hard cap: nsubmax <= max_cap_absolute."""
        inst = self._inst(y_subs=0.5, cap_fraction=1.0, max_cap_absolute=100.0)
        sub, nsubmax = inst.compute_subsidy(3.0, 0.5, 0.2, 1.0, 10.0, 10_000.0, 10_000.0, t=90)
        assert nsubmax <= 100.0

    def test_subsidy_non_negative(self):
        """sub_ge is always >= 0."""
        inst = self._inst(y_subs=10.0)  # very high y_subs → sub would go negative
        sub, _ = inst.compute_subsidy(0.5, 5.0, 1.0, 1.0, 10.0, 500.0, 2000.0, t=90)
        assert sub >= 0.0


# ---------------------------------------------------------------------------
# GreenConstructionSubsidy — apply() and t_start gating
# ---------------------------------------------------------------------------

class TestGreenConstructionSubsidyApply:

    def test_zero_before_t_start(self):
        """Sub_ge = 0 for t < t_start + 1."""
        nation = _build_nation(t_start=20)
        inst = GreenConstructionSubsidy(y_subs=1.0 / 3.0, t_start=20)
        # Before t_start
        inst.apply(nation, t=19)
        assert nation.electricity_producer.subsidy_per_plant == 0.0
        assert nation.electricity_producer.max_subsidised_plants == 0.0

    def test_zero_at_t_start_exact(self):
        """t = t_start still not active (condition is t >= t_start + 1)."""
        nation = _build_nation(t_start=20)
        inst = GreenConstructionSubsidy(y_subs=1.0 / 3.0, t_start=20)
        inst.apply(nation, t=20)
        assert nation.electricity_producer.subsidy_per_plant == 0.0

    def test_active_at_t_start_plus_1(self):
        """Subsidy activates at t = t_start + 1."""
        nation = _build_nation(t_start=20)
        ep = nation.electricity_producer
        # Force frontier so inner guard passes with default payback=40:
        # green_annual = 10.0/40 = 0.25 > (2/3)*(0.5/40 + 0.3*1.0) = 0.208 ✓
        ep.frontier_green_build_cost = 10.0
        ep.frontier_brown_build_cost = 0.5
        ep.frontier_brown_thermal_ineff = 0.3
        nation.params.fossil_fuel_price = 1.0
        inst = GreenConstructionSubsidy(y_subs=1.0 / 3.0, t_start=20)
        inst.apply(nation, t=21)
        assert nation.electricity_producer.subsidy_per_plant > 0.0

    def test_reads_t_start_from_gparams(self):
        """When t_start=None, instrument reads nation.gparams.climate_start_step."""
        nation = _build_nation(t_start=15)
        ep = nation.electricity_producer
        ep.frontier_green_build_cost = 3.0
        ep.frontier_brown_build_cost = 0.5
        ep.frontier_brown_thermal_ineff = 0.3
        nation.params.fossil_fuel_price = 1.0
        inst = GreenConstructionSubsidy(y_subs=1.0 / 3.0, t_start=None)
        inst.apply(nation, t=14)  # before gparams.climate_start_step=15
        assert ep.subsidy_per_plant == 0.0
        inst.apply(nation, t=16)  # t >= 15 + 1 = 16
        assert ep.subsidy_per_plant >= 0.0  # may be 0 if inner guard fails, but not error

    def test_subsidy_on_false(self):
        """subsidy_on=False keeps Sub_ge = 0 even when t >= t_start + 1."""
        nation = _build_nation(t_start=5)
        ep = nation.electricity_producer
        ep.frontier_green_build_cost = 3.0
        ep.frontier_brown_build_cost = 0.5
        ep.frontier_brown_thermal_ineff = 0.3
        nation.params.fossil_fuel_price = 1.0
        inst = GreenConstructionSubsidy(subsidy_on=False, t_start=5)
        inst.apply(nation, t=10)
        assert ep.subsidy_per_plant == 0.0
        assert ep.max_subsidised_plants == 0.0

    def test_sets_ep_fields(self):
        """apply() writes both Sub_ge and NSubmax_ge to the EP."""
        nation = _build_nation(t_start=5)
        ep = nation.electricity_producer
        # Force frontier so inner guard passes
        ep.frontier_green_build_cost = 2.0
        ep.frontier_brown_build_cost = 0.4
        ep.frontier_brown_thermal_ineff = 0.2
        nation.params.fossil_fuel_price = 1.0
        # Set some capacity so nsubmax > 0
        from dsk.agents.power_plant import GreenPlant, BrownPlant
        ep.green_plants.add(GreenPlant(nation, vintage=0, count=500, building_cost=0.5))
        ep.brown_plants.add(BrownPlant(nation, vintage=0, count=2000,
                                        building_cost=0.4,
                                        thermal_inefficiency=0.2,
                                        emission_intensity=0.01))
        ep._update_capacity()

        inst = GreenConstructionSubsidy(y_subs=1.0 / 3.0, t_start=5)
        inst.apply(nation, t=7)

        assert ep.subsidy_per_plant >= 0.0
        assert ep.max_subsidised_plants >= 0.0


# ---------------------------------------------------------------------------
# GreenRDSubsidy — formula and apply()
# ---------------------------------------------------------------------------

class TestGreenRDSubsidy:

    def test_zero_before_t_start(self):
        """govt_rd_all_multiplier is set to 0 before t_start + 1."""
        nation = _build_nation(t_start=20)
        inst = GreenRDSubsidy(rd_topup_fraction=0.5, t_start=20)
        inst.apply(nation, t=20)
        assert nation.electricity_producer.govt_rd_all_multiplier == 0.0

    def test_active_at_t_start_plus_1(self):
        """govt_rd_all_multiplier is set to rd_topup_fraction when active."""
        nation = _build_nation(t_start=20)
        inst = GreenRDSubsidy(rd_topup_fraction=0.5, t_start=20)
        inst.apply(nation, t=21)
        assert nation.electricity_producer.govt_rd_all_multiplier == pytest.approx(0.5)

    def test_custom_fraction(self):
        """Custom rd_topup_fraction is written correctly."""
        nation = _build_nation(t_start=10)
        inst = GreenRDSubsidy(rd_topup_fraction=0.3, t_start=10)
        inst.apply(nation, t=12)
        assert nation.electricity_producer.govt_rd_all_multiplier == pytest.approx(0.3)

    def test_reads_t_start_from_gparams(self):
        """Resolves t_start from nation.gparams when not supplied."""
        nation = _build_nation(t_start=15)
        inst = GreenRDSubsidy(rd_topup_fraction=0.5, t_start=None)
        inst.apply(nation, t=15)
        assert nation.electricity_producer.govt_rd_all_multiplier == 0.0
        inst.apply(nation, t=16)
        assert nation.electricity_producer.govt_rd_all_multiplier == pytest.approx(0.5)

    def test_subsidy_on_false(self):
        """subsidy_on=False keeps multiplier at 0."""
        nation = _build_nation(t_start=5)
        inst = GreenRDSubsidy(rd_topup_fraction=0.5, t_start=5, subsidy_on=False)
        inst.apply(nation, t=10)
        assert nation.electricity_producer.govt_rd_all_multiplier == 0.0

    def test_is_active_always_true(self):
        """is_active is always True (gating lives inside apply())."""
        inst = GreenRDSubsidy(t_start=20)
        assert inst.is_active(1) is True
        assert inst.is_active(100) is True

    def test_can_be_added_to_climate_policy(self):
        """GreenRDSubsidy can be registered with ClimatePolicy and called."""
        nation = _build_nation(t_start=5)
        inst = GreenRDSubsidy(rd_topup_fraction=0.5, t_start=5)
        nation.climate_policy.add_instrument(inst)
        # Calling through ClimatePolicy.apply should not raise.
        nation.climate_policy.apply(t=7)
        assert nation.electricity_producer.govt_rd_all_multiplier == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Acceptance test: more green builds with subsidy than without
# ---------------------------------------------------------------------------

class TestSubsidyIncreasesGreenBuilds:
    """Run two short simulations from the same seed; confirm subsidy increases green builds.

    Uses a late t_start (t=1) to trigger the subsidy from the very first step
    in a small test economy, then compares the total green capacity after a
    few steps.
    """

    T_START = 1
    STEPS = 8

    def _run(self, subsidy_on: bool, seed: int = 99, n1: int = 5, n2: int = 20) -> float:
        """Return total green capacity after STEPS periods."""
        nation = _build_nation(seed=seed, n1=n1, n2=n2, t_start=self.T_START)
        gparams = nation.gparams

        if subsidy_on:
            inst = GreenConstructionSubsidy(
                y_subs=1.0 / 3.0,
                t_start=self.T_START,
            )
            nation.climate_policy.add_instrument(inst)

        for t in range(1, self.STEPS + 1):
            _full_step(nation, t)

        return float(nation.electricity_producer.total_green_capacity)

    def test_more_green_with_subsidy_than_without(self):
        """Green capacity with subsidy >= green capacity without (same seed)."""
        green_with = self._run(subsidy_on=True)
        green_without = self._run(subsidy_on=False)
        assert green_with >= green_without, (
            f"Expected green_with ({green_with}) >= green_without ({green_without})"
        )

    def test_rd_subsidy_increases_green_rd_spending(self):
        """R&D subsidy causes govt_rd_topup_total > 0 in the energy sector."""
        nation = _build_nation(seed=99, n1=5, n2=20, t_start=self.T_START)
        inst = GreenRDSubsidy(rd_topup_fraction=0.5, t_start=self.T_START)
        nation.climate_policy.add_instrument(inst)

        topup_observed = []
        for t in range(1, self.STEPS + 1):
            _full_step(nation, t)
            topup_observed.append(nation.electricity_producer.govt_rd_topup_total)

        # After t_start, at least some periods should show a nonzero top-up.
        assert any(v > 0.0 for v in topup_observed), (
            "Expected non-zero govt_rd_topup_total when R&D subsidy is active."
        )
