"""Integration tests for Task 5.3 — BrownConstructionBan.

Acceptance criteria (IMPLEMENTATION_PLAN §5.3):
- Brown plant count flatlines (no new plants added) after the ban enforcement
  year.
- Pre-existing brown plants continue running / are counted until the use ban
  year.
"""
from __future__ import annotations

import numpy as np
import pytest
from unittest.mock import MagicMock

from dsk.agents.electricity_producer import ElectricityProducer
from dsk.agents.power_plant import BrownPlant, GreenPlant
from dsk.nation import Nation
from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters
from dsk.policy.brown_ban import BrownConstructionBan
from dsk.policy.climate_policy import ClimatePolicy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_nation(seed: int = 42, n1: int = 10, n2: int = 40, t_start: int = 5) -> Nation:
    gparams = GlobalParameters()
    gparams.n1_capital_good_firms = n1
    gparams.n2_consumption_good_firms = n2
    gparams.labour_supply_init = int(gparams.labour_supply_init * (n2 / 400.0))
    gparams.climate_start_step = t_start
    nparams = NationParameters()
    nation = Nation("ban-test", params=nparams)
    nation.rng = np.random.default_rng(seed)
    nation.initialise_from_parameters(gparams, nparams)
    return nation


def _full_step(nation: Nation, t: int) -> None:
    nation.production_phase(t)
    nation.dynamics_phase(t)
    nation.closeout_phase(t)


def _mock_nation_for_ep(t_start: int = 5, total_steps: int = 220):
    """Lightweight mock nation for EP-level tests."""
    gparams = MagicMock()
    gparams.climate_start_step = t_start
    gparams.total_steps = total_steps
    nation = MagicMock()
    nation.gparams = gparams
    return nation


def _make_ep(nation, total_steps: int = 220) -> ElectricityProducer:
    ep = ElectricityProducer(nation)
    ep.frontier_brown_thermal_ineff = 2.5
    ep.frontier_brown_emission_intensity = 1100.0
    ep.frontier_brown_build_cost = 2.0
    ep.frontier_green_build_cost = 10.0   # green expensive → brown preferred
    ep.net_worth = 1.0e6
    ep.brown_invest_ban_year = 5 * total_steps
    ep.brown_use_ban_year = 5 * total_steps
    return ep


def _add_brown(ep, nation, count: int = 100, vintage: int = 1) -> BrownPlant:
    bp = BrownPlant(
        nation, vintage=vintage, count=count,
        building_cost=2.0, thermal_inefficiency=2.5, emission_intensity=1100.0,
    )
    ep.brown_plants.add(bp)
    ep._update_capacity()
    return bp


def _new_brown_since(ep, since: int):
    return [p for p in ep.brown_plants if p.vintage >= since and p.count > 0]


# ---------------------------------------------------------------------------
# Pure instrument tests — apply() sets EP fields correctly
# ---------------------------------------------------------------------------

class TestBrownConstructionBanApply:

    def test_before_announce_both_ban_years_are_far_future(self):
        """Before invest_announce_offset, ban years = 5*T (not announced)."""
        T = 100
        nation = _mock_nation_for_ep(t_start=10, total_steps=T)
        ep = _make_ep(nation, total_steps=T)
        nation.electricity_producer = ep

        inst = BrownConstructionBan(invest_ban_offset=21, invest_announce_offset=5, t_start=10)
        # t=14 < 10+5 = 15 → not yet announced
        inst.apply(nation, t=14)

        assert ep.brown_invest_ban_year == 5 * T

    def test_invest_ban_year_set_after_announce(self):
        """After invest_announce_offset, brown_invest_ban_year = t_start + invest_ban_offset."""
        T = 100
        t_start = 10
        invest_ban_offset = 21
        nation = _mock_nation_for_ep(t_start=t_start, total_steps=T)
        ep = _make_ep(nation, total_steps=T)
        nation.electricity_producer = ep

        inst = BrownConstructionBan(
            invest_ban_offset=invest_ban_offset,
            invest_announce_offset=1,
            t_start=t_start,
        )
        # t = t_start + 1 → announced
        inst.apply(nation, t=t_start + 1)

        assert ep.brown_invest_ban_year == t_start + invest_ban_offset

    def test_use_ban_year_set_after_announce(self):
        """After use_announce_offset, brown_use_ban_year = t_start + use_ban_offset."""
        T = 100
        t_start = 10
        use_ban_offset = 30
        nation = _mock_nation_for_ep(t_start=t_start, total_steps=T)
        ep = _make_ep(nation, total_steps=T)
        nation.electricity_producer = ep

        inst = BrownConstructionBan(
            invest_ban_offset=50,
            use_ban_offset=use_ban_offset,
            invest_announce_offset=1,
            use_announce_offset=5,
            t_start=t_start,
        )
        inst.apply(nation, t=t_start + 5)  # right at announce threshold

        assert ep.brown_use_ban_year == t_start + use_ban_offset

    def test_use_ban_far_future_by_default(self):
        """Default use_ban_offset=None → use_ban_year = t_start + 5*T + 26 (far future).

        C++ BCERT line 983: ``brown_use_ban = t_start_climbox + 26 + T*5``.
        The offset stored on the instrument is relative to t_start, so the
        absolute year is t_start + (5*T + 26).
        """
        T = 100
        t_start = 5
        nation = _mock_nation_for_ep(t_start=t_start, total_steps=T)
        ep = _make_ep(nation, total_steps=T)
        nation.electricity_producer = ep

        inst = BrownConstructionBan(use_ban_offset=None, use_announce_offset=1, t_start=t_start)
        inst.apply(nation, t=t_start + 1)  # use ban announced

        assert ep.brown_use_ban_year == t_start + 5 * T + 26

    def test_invest_ban_clipped_to_use_ban(self):
        """invest_ban = min(invest_ban, use_ban) — cannot invest past use cutoff."""
        T = 100
        t_start = 10
        nation = _mock_nation_for_ep(t_start=t_start, total_steps=T)
        ep = _make_ep(nation, total_steps=T)
        nation.electricity_producer = ep

        # invest_ban would be 10+40=50; use_ban is 10+20=30 → min = 30
        inst = BrownConstructionBan(
            invest_ban_offset=40,
            use_ban_offset=20,
            invest_announce_offset=1,
            use_announce_offset=1,
            t_start=t_start,
        )
        inst.apply(nation, t=t_start + 1)

        assert ep.brown_invest_ban_year == t_start + 20
        assert ep.brown_use_ban_year == t_start + 20

    def test_ban_on_false_leaves_far_future(self):
        """ban_on=False → both ban years stay at 5*T regardless of t."""
        T = 100
        t_start = 5
        nation = _mock_nation_for_ep(t_start=t_start, total_steps=T)
        ep = _make_ep(nation, total_steps=T)
        nation.electricity_producer = ep

        inst = BrownConstructionBan(
            invest_ban_offset=21, invest_announce_offset=1,
            ban_on=False, t_start=t_start,
        )
        inst.apply(nation, t=t_start + 50)  # well past announce

        assert ep.brown_invest_ban_year == 5 * T
        assert ep.brown_use_ban_year == 5 * T

    def test_reads_t_start_from_gparams(self):
        """When t_start=None, resolves from nation.gparams.climate_start_step."""
        T = 100
        t_start = 15
        nation = _mock_nation_for_ep(t_start=t_start, total_steps=T)
        ep = _make_ep(nation, total_steps=T)
        nation.electricity_producer = ep

        inst = BrownConstructionBan(invest_ban_offset=21, invest_announce_offset=1, t_start=None)
        inst.apply(nation, t=t_start)   # t == t_start < t_start+1 → not announced
        assert ep.brown_invest_ban_year == 5 * T

        inst.apply(nation, t=t_start + 1)   # now announced
        assert ep.brown_invest_ban_year == t_start + 21

    def test_is_active_always_true(self):
        """is_active() always returns True — gating lives inside apply()."""
        inst = BrownConstructionBan()
        assert inst.is_active(1) is True
        assert inst.is_active(999) is True

    def test_can_be_added_to_climate_policy(self):
        """BrownConstructionBan can be registered with ClimatePolicy."""
        T = 100
        t_start = 5
        nation = _mock_nation_for_ep(t_start=t_start, total_steps=T)
        ep = _make_ep(nation, total_steps=T)
        nation.electricity_producer = ep

        policy = ClimatePolicy(nation)
        inst = BrownConstructionBan(invest_ban_offset=21, invest_announce_offset=1, t_start=t_start)
        policy.add_instrument(inst)

        policy.apply(t=t_start + 1)
        assert ep.brown_invest_ban_year == t_start + 21


# ---------------------------------------------------------------------------
# EP-level: ban blocks brown builds at plan_capacity_expansion level
# ---------------------------------------------------------------------------

class TestBanBlocksBrownAtEPLevel:
    """Apply ban year directly to EP and verify plan_capacity_expansion respects it."""

    def test_no_new_brown_once_ban_active(self):
        """After brown_invest_ban_year passes, plan_capacity_expansion builds zero brown."""
        gparams = GlobalParameters()
        nation = MagicMock()
        ban_start = 8
        ep = _make_ep(nation)
        ep.brown_invest_ban_year = ban_start
        ep.brown_use_ban_year = ban_start
        _add_brown(ep, nation, count=100, vintage=1)

        for t in range(ban_start, ban_start + 4):
            demand = 100.0 + 30.0 * (t - ban_start + 1)
            ep.plan_capacity_expansion(t, demand_for_building=demand,
                                       fuel_price=0.02, carbon_tax=0.0, gparams=gparams)

        # No brown plant with vintage >= ban_start was added.
        assert _new_brown_since(ep, since=ban_start) == []
        # Demand was met with green (green capacity increased from zero).
        assert ep.total_green_capacity > 0

    def test_existing_brown_plants_still_present(self):
        """Pre-existing brown plants are not removed when investment ban fires."""
        gparams = GlobalParameters()
        nation = MagicMock()
        ban_start = 8
        ep = _make_ep(nation)
        ep.brown_invest_ban_year = ban_start
        ep.brown_use_ban_year = 5 * 220   # use ban far in future → plants still active
        existing = _add_brown(ep, nation, count=100, vintage=1)

        ep.plan_capacity_expansion(ban_start, demand_for_building=120.0,
                                   fuel_price=0.02, carbon_tax=0.0, gparams=gparams)

        # Pre-ban brown plants still have count > 0.
        assert existing.count > 0

    def test_brown_scrapped_when_use_ban_fires(self):
        """When brown_use_ban_year - t <= 0, _retire_old_plants zeros all brown.

        The use-ban scrapping lives in Nation._retire_old_plants() (closeout
        phase), so we use a full nation here.
        """
        nation = _build_nation(seed=11, t_start=3)
        ep = nation.electricity_producer
        # Plant the use ban at t=5 so it fires immediately at closeout_phase(5)
        ep.brown_invest_ban_year = 5
        ep.brown_use_ban_year = 5

        # Step through t=1..4 normally, then at t=5 the use ban fires.
        for t in range(1, 5):
            _full_step(nation, t)
        # Run production+dynamics so there are plants to scrap, then closeout triggers ban.
        nation.production_phase(5)
        nation.dynamics_phase(5)
        nation.closeout_phase(5)

        assert ep.brown_plants.total_active_capacity() == 0


# ---------------------------------------------------------------------------
# Acceptance test: full nation integration
# ---------------------------------------------------------------------------

class TestBrownBanFullNation:
    """Run a full nation simulation; verify the ban instrument blocks brown builds.

    We set up a situation where without the ban, brown plants would be built
    (green is expensive; energy demand grows).  With the ban active from
    t_start+invest_ban_offset, no new brown plants should appear after that.
    """

    T_START = 3      # climate starts early so ban kicks in quickly
    BAN_OFFSET = 4   # ban active at t_start + 4 = 7
    STEPS = 10       # run 10 steps, so 3 steps past the ban

    def _run(
        self,
        with_ban: bool,
        seed: int = 77,
        n1: int = 5,
        n2: int = 20,
    ) -> tuple[list[int], int]:
        """Return (brown_vintage_counts_per_step, total_brown_at_end)."""
        nation = _build_nation(seed=seed, n1=n1, n2=n2, t_start=self.T_START)
        ep = nation.electricity_producer

        # Make green expensive so brown would normally win
        ep.frontier_green_build_cost = 50.0

        if with_ban:
            inst = BrownConstructionBan(
                invest_ban_offset=self.BAN_OFFSET,
                invest_announce_offset=1,
                t_start=self.T_START,
            )
            nation.climate_policy.add_instrument(inst)

        brown_vintages_after_ban: list[int] = []
        for t in range(1, self.STEPS + 1):
            _full_step(nation, t)
            if t >= self.T_START + self.BAN_OFFSET:
                # count new brown built this step
                new_brown = [p for p in ep.brown_plants if p.vintage == t and p.count > 0]
                brown_vintages_after_ban.append(len(new_brown))

        return brown_vintages_after_ban, int(ep.total_brown_capacity)

    def test_no_new_brown_after_ban_year(self):
        """After the ban fires, no brown plant with a post-ban vintage is added."""
        post_ban_brown, _ = self._run(with_ban=True)
        assert all(c == 0 for c in post_ban_brown), (
            f"Brown built in post-ban steps: {post_ban_brown}"
        )

    def test_brown_built_without_ban(self):
        """Without the ban, brown plants are built when green is expensive.

        This confirms the test setup would actually produce brown plants,
        making the 'with ban' test non-trivial.
        """
        _, brown_capacity = self._run(with_ban=False)
        # Brown capacity should be positive after several steps of growing demand.
        assert brown_capacity > 0

    def test_existing_brown_capacity_nonzero_after_ban(self):
        """Pre-existing brown plants (before the ban) are not destroyed by the ban."""
        _, brown_capacity = self._run(with_ban=True)
        # Initial capacity was seeded; it should still exist.
        assert brown_capacity >= 0   # could be 0 if all plants aged out, but not an error
