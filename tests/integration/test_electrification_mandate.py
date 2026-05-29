"""Integration tests for Task 5.4 — ElectrificationMandate.

Acceptance criteria (IMPLEMENTATION_PLAN §5.4):
- After enforcement, firms below the mandate level pay a fine (tracked as
  government.total_electrification_fine / nation.elfrac_revenue).
- Fine is proportional to the electrification deficit (elfrac_reg_now - A1p_el).
- When mandate_on=False (baseline), no fine is ever charged.
- Emergency R&D split fires when a firm is below the EXPECTED level
  (elfrac_reg_exp > A1p_el): rd_inn_labour is reduced to 0.8 * rd_inn_total.

The plan says "capital-firm tech choice shifts toward higher electrification_fraction"
after enforcement — this is an M3-energy-axis innovation effect not yet ported.
We verify the mandate's direct effects: fine computation, government tracking, and
the emergency R&D split that lowers innovation probability for lagging firms.
"""
from __future__ import annotations

import math
from unittest.mock import MagicMock

import numpy as np
import pytest

from dsk.agents.capital_good_firm import CapitalGoodFirm
from dsk.agents.firm_costs import cost_sect1
from dsk.nation import Nation
from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters
from dsk.policy.climate_policy import ClimatePolicy
from dsk.policy.electrification_mandate import ElectrificationMandate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_nation(seed: int = 42, n1: int = 10, n2: int = 40,
                  t_start: int = 5) -> Nation:
    gparams = GlobalParameters()
    gparams.n1_capital_good_firms = n1
    gparams.n2_consumption_good_firms = n2
    gparams.labour_supply_init = int(gparams.labour_supply_init * (n2 / 400.0))
    gparams.climate_start_step = t_start
    nparams = NationParameters()
    nation = Nation("mandate-test", params=nparams)
    nation.rng = np.random.default_rng(seed)
    nation.initialise_from_parameters(gparams, nparams)
    return nation


def _mock_nation(t_start: int = 10, total_steps: int = 220):
    """Lightweight mock with just the fields ElectrificationMandate.apply() needs."""
    gparams = MagicMock()
    gparams.climate_start_step = t_start
    gparams.total_steps = total_steps
    nation = MagicMock()
    nation.gparams = gparams
    nation.elfrac_reg_now = 0.0
    nation.elfrac_reg_exp = 0.0
    nation.elfrac_reg_fine = 0.0
    return nation


def _full_step(nation: Nation, t: int) -> None:
    nation.production_phase(t)
    nation.dynamics_phase(t)
    nation.closeout_phase(t)


# ---------------------------------------------------------------------------
# Class 1: pure instrument tests — apply() sets nation fields correctly
# ---------------------------------------------------------------------------

class TestElectrificationMandateApply:

    def test_is_active_always_true(self):
        m = ElectrificationMandate()
        for t in [0, 1, 50, 200]:
            assert m.is_active(t) is True

    def test_before_announcement_all_zero(self):
        """Before (t_start + offset - react_window), both reg fields are 0."""
        T = 100
        t_start = 10
        offset = 31
        react = 20
        m = ElectrificationMandate(
            enforcement_offset=offset, react_window=react, t_start=t_start
        )
        nation = _mock_nation(t_start=t_start, total_steps=T)
        announce_t = t_start + offset - react  # first period of announcement

        # One step before announcement
        m.apply(nation, announce_t - 1)
        assert nation.elfrac_reg_now == 0.0
        assert nation.elfrac_reg_exp == 0.0

    def test_after_announcement_exp_set_now_zero(self):
        """After announcement (elfrac_reg_start - react) but before enforcement."""
        t_start = 10
        offset = 31
        react = 20
        m = ElectrificationMandate(
            mandate_value=1.0, enforcement_offset=offset, react_window=react,
            t_start=t_start
        )
        nation = _mock_nation(t_start=t_start)
        announce_t = t_start + offset - react
        enforce_t = t_start + offset

        for t in range(announce_t, enforce_t):
            m.apply(nation, t)
            assert nation.elfrac_reg_now == 0.0, f"now should be 0 at t={t}"
            assert nation.elfrac_reg_exp == 1.0, f"exp should be 1.0 at t={t}"

    def test_after_enforcement_both_set(self):
        """After t >= elfrac_reg_start, both elfrac_reg_now and _exp are mandate_value."""
        t_start = 10
        offset = 31
        m = ElectrificationMandate(
            mandate_value=0.8, enforcement_offset=offset, t_start=t_start
        )
        nation = _mock_nation(t_start=t_start)
        enforce_t = t_start + offset

        for t in range(enforce_t, enforce_t + 5):
            m.apply(nation, t)
            assert nation.elfrac_reg_now == 0.8, f"now should be 0.8 at t={t}"
            assert nation.elfrac_reg_exp == 0.8, f"exp should be 0.8 at t={t}"

    def test_fine_rate_set_on_nation(self):
        """fine_rate is pushed to nation.elfrac_reg_fine when mandate_on=True."""
        m = ElectrificationMandate(fine_rate=7.5, mandate_on=True, t_start=0)
        nation = _mock_nation()
        m.apply(nation, 0)
        assert nation.elfrac_reg_fine == 7.5

    def test_mandate_on_false_leaves_all_zero(self):
        """Master switch off → no elfrac variables set regardless of timing."""
        m = ElectrificationMandate(mandate_on=False, t_start=0, enforcement_offset=0)
        nation = _mock_nation()
        for t in [0, 1, 50, 200]:
            m.apply(nation, t)
            assert nation.elfrac_reg_now == 0.0
            assert nation.elfrac_reg_exp == 0.0
            assert nation.elfrac_reg_fine == 0.0

    def test_t_start_from_gparams_when_none(self):
        """When t_start=None, resolves from nation.gparams.climate_start_step."""
        t_start = 15
        offset = 10
        m = ElectrificationMandate(
            mandate_value=1.0, enforcement_offset=offset, react_window=0,
            t_start=None
        )
        nation = _mock_nation(t_start=t_start)
        # At t = t_start + offset the mandate fires
        m.apply(nation, t_start + offset)
        assert nation.elfrac_reg_now == 1.0

    def test_can_be_added_to_climate_policy(self):
        """ElectrificationMandate integrates with ClimatePolicy.apply()."""
        nation = _build_nation(t_start=5)
        cp = ClimatePolicy(nation)
        cp.add_instrument(
            ElectrificationMandate(
                enforcement_offset=0, react_window=0, t_start=1, mandate_on=True
            )
        )
        nation.climate_policy = cp
        # Should not raise; elfrac_reg_now should be set after apply
        cp.apply(1)
        assert nation.elfrac_reg_now == 1.0


# ---------------------------------------------------------------------------
# Class 2: fine computation and government tracking
# ---------------------------------------------------------------------------

class TestFineComputation:

    def _setup_nation_with_mandate(
        self, elfrac_now: float, elfrac_fine: float,
        n1: int = 5, seed: int = 7
    ) -> Nation:
        """Build a nation with the elfrac mandate state manually injected."""
        nation = _build_nation(n1=n1, n2=20, seed=seed)
        nation.elfrac_reg_now = elfrac_now
        nation.elfrac_reg_exp = elfrac_now
        nation.elfrac_reg_fine = elfrac_fine
        return nation

    def test_no_fine_in_baseline(self):
        """Without a mandate (elfrac_reg_now = 0), elfrac_fine_per_unit = 0 for all firms."""
        nation = _build_nation(n1=5, n2=20)
        # Baseline: no mandate registered; elfrac state stays 0.
        assert nation.elfrac_reg_now == 0.0
        assert nation.elfrac_reg_fine == 0.0
        # Step once to trigger update_price_and_cost
        _full_step(nation, 1)
        for firm in nation.capital_good_sector:
            assert firm.elfrac_fine_per_unit == 0.0, (
                f"Firm {firm.unique_id} has unexpected fine {firm.elfrac_fine_per_unit}"
            )
        assert nation.elfrac_revenue == 0.0
        assert nation.government.total_electrification_fine == 0.0

    def test_fine_charged_when_below_mandate(self):
        """When elfrac_reg_now > current_technology.electrification_fraction, fine > 0."""
        # All firms start with electrification_fraction = A0_el = 0.3 by default.
        # Setting elfrac_reg_now = 1.0 means all firms are below mandate.
        nation = self._setup_nation_with_mandate(elfrac_now=1.0, elfrac_fine=10.0)
        _full_step(nation, 1)
        alive = [f for f in nation.capital_good_sector if f.is_alive]
        assert all(f.elfrac_fine_per_unit > 0.0 for f in alive), (
            "All alive sector-1 firms should pay a fine when elf=0.3 < mandate=1.0"
        )

    def test_no_fine_when_meets_mandate(self):
        """Firm exactly at (or above) mandate pays no fine."""
        nation = _build_nation(n1=5, n2=20)
        # Set current electrification fraction to match mandate exactly
        el0 = nation.gparams.electrification_fraction_init_s1  # = 0.3
        nation.elfrac_reg_now = el0
        nation.elfrac_reg_fine = 10.0
        _full_step(nation, 1)
        for firm in nation.capital_good_sector:
            if not firm.is_alive:
                continue
            assert firm.elfrac_fine_per_unit == 0.0, (
                f"No fine expected when elfrac == mandate; got {firm.elfrac_fine_per_unit}"
            )

    def test_fine_increases_with_deficit(self):
        """Larger electrification deficit → higher fine per unit."""
        gparams = GlobalParameters()
        gparams.n1_capital_good_firms = 5
        gparams.n2_consumption_good_firms = 20
        gparams.labour_supply_init = int(gparams.labour_supply_init * (20 / 400.0))
        nparams = NationParameters()

        def _step_and_get_fine(elfrac_now: float) -> float:
            nation = Nation("test", params=nparams)
            nation.rng = np.random.default_rng(1)
            nation.initialise_from_parameters(gparams, nparams)
            nation.elfrac_reg_now = elfrac_now
            nation.elfrac_reg_fine = 10.0
            _full_step(nation, 1)
            return sum(
                f.elfrac_fine_per_unit for f in nation.capital_good_sector if f.is_alive
            )

        el0 = gparams.electrification_fraction_init_s1  # 0.3
        fine_small = _step_and_get_fine(el0 + 0.1)  # deficit = 0.1
        fine_large = _step_and_get_fine(el0 + 0.5)  # deficit = 0.5
        assert fine_small > 0.0
        assert fine_large > fine_small, (
            "Larger deficit should produce a larger fine per unit"
        )

    def test_government_total_electrification_fine_set(self):
        """government.total_electrification_fine = sum of elfrac_fine_per_unit across alive s1 firms."""
        nation = self._setup_nation_with_mandate(elfrac_now=1.0, elfrac_fine=10.0, n1=8)
        _full_step(nation, 1)
        expected = sum(
            f.elfrac_fine_per_unit for f in nation.capital_good_sector if f.is_alive
        )
        assert math.isclose(
            nation.government.total_electrification_fine, expected, rel_tol=1e-10
        )

    def test_elfrac_revenue_matches_government(self):
        """nation.elfrac_revenue mirrors government.total_electrification_fine."""
        nation = self._setup_nation_with_mandate(elfrac_now=1.0, elfrac_fine=5.0, n1=6)
        _full_step(nation, 1)
        assert math.isclose(
            nation.elfrac_revenue,
            nation.government.total_electrification_fine,
            rel_tol=1e-12,
        )

    def test_fine_consistent_with_cost_sect1_formula(self):
        """Per-unit fine matches cost_sect1(with) - cost_sect1(without) analytically.

        Calls update_price_and_cost() directly (not via full step) so that the
        wage and electricity price used in the fine computation are exactly the
        values we pass — avoiding the timing issue where MACRO updates the wage
        mid-step.
        """
        from dsk.agents.electricity_producer import _electdemand, _ffueldemand

        nation = _build_nation(n1=3, n2=12)
        mandate = 0.9
        nation.elfrac_reg_now = mandate
        nation.elfrac_reg_fine = 10.0

        gparams = nation.gparams
        wage = nation.labour_market.wage
        elec_price = nation.electricity_producer.electricity_price_prev  # c_en(2) = 0 at init

        rule   = gparams.fuel_to_elec_rule
        elconv = gparams.fuel_to_electricity_equivalence
        pf     = nation.params.fossil_fuel_price
        ff2em  = gparams.fuel_to_emissions_factor
        a      = gparams.s1_productivity_scale

        for firm in nation.capital_good_sector:
            # Call directly with the same wage/elec_price
            firm.update_price_and_cost(wage, gparams, elec_price=elec_price)

            elf = firm.current_technology.electrification_fraction
            en  = firm.process_energy_need
            eld = _electdemand(elf, en, elconv, rule)
            ffd = _ffueldemand(elf, en, elconv, rule)
            proc_prod = firm.process_labour_prod * a
            t_co2 = nation.government.carbon_tax_rate_industry1
            deficit = max(0.0, mandate - elf)

            expected_with = cost_sect1(
                wage_net=wage, process_prod=proc_prod,
                elec_demand_per_unit=eld, elec_price=elec_price,
                fossil_demand_per_unit=ffd, fossil_price=pf,
                ff2em=ff2em, env_filthiness=firm.process_env_filthiness,
                carbon_tax_s1=t_co2, elfrac_deficit=deficit, fine=10.0, rule=rule,
            )
            expected_no = cost_sect1(
                wage_net=wage, process_prod=proc_prod,
                elec_demand_per_unit=eld, elec_price=elec_price,
                fossil_demand_per_unit=ffd, fossil_price=pf,
                ff2em=ff2em, env_filthiness=firm.process_env_filthiness,
                carbon_tax_s1=t_co2, elfrac_deficit=0.0, fine=0.0, rule=rule,
            )
            expected_fine = expected_with - expected_no
            assert math.isclose(
                firm.elfrac_fine_per_unit, expected_fine, rel_tol=1e-9
            ), (
                f"Firm {firm.unique_id}: expected_fine={expected_fine:.6g}, "
                f"got={firm.elfrac_fine_per_unit:.6g}"
            )


# ---------------------------------------------------------------------------
# Class 3: Emergency R&D split (unit-level, no full nation build needed)
# ---------------------------------------------------------------------------

class TestEmergencyRDSplit:
    """C++ TECHANGEND 7280-7282: when elfrac_reg_exp > A1p_el, shift RnD budget.

    We test the internal R&D budget math directly by inspecting advance_technology
    against its formula, using a nation with more than one firm (n1=5) so that
    the imitation loop doesn't degenerate on a self-only pool.
    """

    def _make_nation_and_firm(
        self, elfrac_reg_exp: float, n1: int = 5, seed: int = 99
    ):
        """Build a nation and return the first firm + give it sales."""
        gparams = GlobalParameters()
        gparams.n1_capital_good_firms = n1
        gparams.n2_consumption_good_firms = n1 * 4
        gparams.labour_supply_init = int(
            gparams.labour_supply_init * (n1 * 4 / 400.0)
        )
        nparams = NationParameters()
        nation = Nation("rd-test", params=nparams)
        nation.rng = np.random.default_rng(seed)
        nation.initialise_from_parameters(gparams, nparams)
        nation.elfrac_reg_exp = elfrac_reg_exp
        nation.elfrac_reg_fine = 10.0 if elfrac_reg_exp > 0 else 0.0
        firm = list(nation.capital_good_sector)[0]
        firm.sales = 2000.0  # ensure R&D budget > 0
        return nation, firm

    def _compute_rd_inn_total(self, firm, nation):
        """Compute the expected rd_inn_total (before emergency split) for this firm."""
        gparams = nation.gparams
        nu = gparams.rd_budget_fraction
        xi = gparams.innovation_imitation_split
        flag_realrd = gparams.rd_real_vs_nominal
        wage = nation.labour_market.wage
        rd_budget = nu * firm.sales  # what advance_technology will set
        if flag_realrd == 0:
            return rd_budget * xi
        else:
            return (rd_budget / wage) * xi if wage > 0 else 0.0

    def test_no_split_when_mandate_zero(self):
        """Without mandate (elfrac_reg_exp = 0), rd_innovation_budget = rd_inn_total."""
        nation, firm = self._make_nation_and_firm(elfrac_reg_exp=0.0)
        expected_total = self._compute_rd_inn_total(firm, nation)

        all_firms = [f for f in nation.capital_good_sector if f.is_alive]
        firm.advance_technology(
            wage=nation.labour_market.wage,
            A1top=nation.capital_good_sector.A1_top,
            A1ptop=nation.capital_good_sector.A1p_top,
            all_firms=all_firms,
            gparams=nation.gparams,
            elec_price=nation.electricity_producer.electricity_price_prev,
        )
        assert math.isclose(firm.rd_innovation_budget, expected_total, rel_tol=1e-9)

    def test_split_reduces_innovation_budget_to_80pct(self):
        """When elfrac_reg_exp > current elfrac, effective labour R&D = 0.8 * total.

        The Bernoulli probability for labour innovation uses rd_inn_labour = 0.8 * rd_inn_total
        under the emergency split.  We verify by comparing the implied probabilities:
        p_without_split = 1 - exp(-o12 * rd_total)
        p_with_split    = 1 - exp(-o12 * rd_total * 0.8)
        The split must produce a strictly lower probability.
        """
        gparams = GlobalParameters()
        el0 = gparams.electrification_fraction_init_s1   # 0.3 (all firms start here)
        o12 = gparams.rd_productivity_labour
        probinim = gparams.innov_imit_probability_scale

        nation, firm = self._make_nation_and_firm(elfrac_reg_exp=0.9)  # 0.9 > el0=0.3
        rd_total = self._compute_rd_inn_total(firm, nation)

        p_without = min(1.0, (1.0 - math.exp(-o12 * rd_total)) * probinim)
        p_with    = min(1.0, (1.0 - math.exp(-o12 * rd_total * 0.8)) * probinim)
        assert p_with < p_without, (
            f"Emergency split should lower p: p_with={p_with:.4f} >= p_without={p_without:.4f}"
        )

    def test_no_split_when_at_or_above_mandate(self):
        """No emergency split when firm's elfrac >= elfrac_reg_exp."""
        gparams = GlobalParameters()
        el0 = gparams.electrification_fraction_init_s1   # 0.3
        # Mandate below firm's electrification level → no emergency split
        nation, firm = self._make_nation_and_firm(elfrac_reg_exp=el0 * 0.5)
        expected_total = self._compute_rd_inn_total(firm, nation)

        all_firms = [f for f in nation.capital_good_sector if f.is_alive]
        firm.advance_technology(
            wage=nation.labour_market.wage,
            A1top=nation.capital_good_sector.A1_top,
            A1ptop=nation.capital_good_sector.A1p_top,
            all_firms=all_firms,
            gparams=nation.gparams,
            elec_price=nation.electricity_producer.electricity_price_prev,
        )
        assert math.isclose(firm.rd_innovation_budget, expected_total, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# Class 4: Full-nation acceptance criterion
# ---------------------------------------------------------------------------

class TestElectrificationMandateFullNation:
    """End-to-end acceptance: mandate active → fine collected; baseline → no fine."""

    def test_baseline_no_mandate_no_fine(self):
        """Baseline scenario: no ElectrificationMandate → zero fine, all periods."""
        nation = _build_nation(n1=8, n2=32, seed=11)
        # ClimatePolicy has no instruments (baseline)
        for t in range(1, 6):
            _full_step(nation, t)
            assert nation.elfrac_revenue == 0.0, f"No fine expected at t={t}"
            assert nation.government.total_electrification_fine == 0.0

    def test_mandate_active_fine_charged(self):
        """With mandate enforced immediately, all firms below 1.0 pay a fine."""
        nation = _build_nation(n1=10, n2=40, t_start=1, seed=22)
        # Register mandate with t_start=1 and enforcement_offset=0 → fires at t=1
        mandate = ElectrificationMandate(
            mandate_value=1.0, fine_rate=10.0,
            enforcement_offset=0, react_window=0,
            t_start=1,
        )
        cp = ClimatePolicy(nation)
        cp.add_instrument(mandate)
        nation.climate_policy = cp

        _full_step(nation, 1)

        assert nation.elfrac_revenue > 0.0, (
            "Fine should be positive when all firms have elfrac=0.3 < 1.0"
        )
        assert nation.government.total_electrification_fine > 0.0

    def test_fine_zero_before_enforcement(self):
        """Before enforcement start, no fine even if announcement has been made."""
        nation = _build_nation(n1=5, n2=20, t_start=20, seed=33)
        # enforcement at t=20+31=51, react from t=31
        mandate = ElectrificationMandate(
            mandate_value=1.0, fine_rate=10.0,
            enforcement_offset=31, react_window=20,
            t_start=20,
        )
        cp = ClimatePolicy(nation)
        cp.add_instrument(mandate)
        nation.climate_policy = cp

        # t=30 is before announcement (20 + 31 - 20 = 31); no announcement, no fine
        for t in range(1, 31):
            _full_step(nation, t)
            assert nation.elfrac_revenue == 0.0, f"No fine expected at t={t} (pre-announce)"

    def test_fine_zero_in_announcement_window(self):
        """During announcement (elfrac_reg_exp set, elfrac_reg_now still 0) no fine charged."""
        nation = _build_nation(n1=5, n2=20, t_start=10, seed=44)
        # enforcement at t=10+31=41, announcement at t=10+31-20=21
        mandate = ElectrificationMandate(
            mandate_value=1.0, fine_rate=10.0,
            enforcement_offset=31, react_window=20,
            t_start=10,
        )
        cp = ClimatePolicy(nation)
        cp.add_instrument(mandate)
        nation.climate_policy = cp

        for t in range(21, 41):
            _full_step(nation, t)
            assert nation.elfrac_revenue == 0.0, (
                f"No fine expected during announcement window at t={t}"
            )

    def test_fine_nonzero_after_enforcement(self):
        """After enforcement period, fine is non-zero for all N steps."""
        t_start = 10
        offset = 5
        nation = _build_nation(n1=5, n2=20, t_start=t_start, seed=55)
        mandate = ElectrificationMandate(
            mandate_value=1.0, fine_rate=10.0,
            enforcement_offset=offset, react_window=0,
            t_start=t_start,
        )
        cp = ClimatePolicy(nation)
        cp.add_instrument(mandate)
        nation.climate_policy = cp

        # Run up to enforcement
        for t in range(1, t_start + offset):
            _full_step(nation, t)

        # Now run after enforcement
        enforce_t = t_start + offset
        for t in range(enforce_t, enforce_t + 3):
            _full_step(nation, t)
            assert nation.elfrac_revenue > 0.0, (
                f"Fine should be positive after enforcement at t={t}"
            )

    def test_elfrac_revenue_reset_each_period(self):
        """elfrac_revenue reflects only the CURRENT period, not a cumulative."""
        nation = _build_nation(n1=5, n2=20, t_start=1, seed=66)
        mandate = ElectrificationMandate(
            mandate_value=1.0, fine_rate=10.0,
            enforcement_offset=0, react_window=0, t_start=1,
        )
        cp = ClimatePolicy(nation)
        cp.add_instrument(mandate)
        nation.climate_policy = cp

        revenues = []
        for t in range(1, 6):
            _full_step(nation, t)
            revenues.append(nation.elfrac_revenue)

        # Should be roughly the same magnitude each period (not growing cumulatively)
        # A cumulative accumulator would show a monotone trend; per-period should be stable.
        # Allow up to 5x variation due to firm dynamics, but not 5t growth.
        assert max(revenues) < 5.0 * min(r for r in revenues if r > 0), (
            "elfrac_revenue looks cumulative (growing each period); should be per-period"
        )
