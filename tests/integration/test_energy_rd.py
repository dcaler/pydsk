"""Integration tests for Task 3.5 — ElectricityProducer energy R&D (do_rd).

Acceptance criteria (IMPLEMENTATION_PLAN §3.5):
- Over 100 periods, mean CF_ge (green build cost) declines.
- Over 100 periods, mean A_de (brown thermal inefficiency) improves (declines).
- Share of R&D in green increases as the green capacity share rises.

Plus targeted checks on the building blocks: the endogenous green/dirty split,
the IC_en payback summation, revenue/profit/net-worth/bailout accounting,
emissions held constant under flag_ff2em_en=0, and dirty R&D stopping once the
dirty frontier reaches its floors.
"""
import math

import numpy as np
import pytest
from unittest.mock import MagicMock

from dsk.agents.electricity_producer import ElectricityProducer
from dsk.agents.power_plant import BrownPlant, GreenPlant
from dsk.parameters.global_parameters import GlobalParameters


@pytest.fixture
def gparams():
    # Defaults encode the Task-3.5 flags: flag_share_END=1, flagRD=1,
    # flag_ff2em_en=0.
    return GlobalParameters()


def make_ep(seed=0):
    """Build an ElectricityProducer with a real RNG and baseline frontier tech."""
    nation = MagicMock()
    nation.rng = np.random.default_rng(seed)
    ep = ElectricityProducer(nation)
    p = GlobalParameters()
    # Frontier = period-t make to build (A_de0=2.5, CF_de0=2.0, CF_ge0=10.0).
    ep.frontier_brown_thermal_ineff = p.dirty_plant_one_over_eff_init
    ep.frontier_brown_emission_intensity = (
        p.fuel_to_emissions_factor * p.energy_emissivity_ratio_init
    )
    ep.frontier_brown_build_cost = p.dirty_plant_build_cost_init
    ep.frontier_green_build_cost = p.green_plant_build_cost_init
    # Floors and government no-op defaults (as initialise_from_parameters sets them).
    ep.brown_build_cost_floor = p.dirty_plant_build_cost_floor_init
    ep.green_build_cost_floor = p.green_plant_build_cost_floor_init
    ep.green_build_cost_govt_floor = p.green_plant_build_cost_govt_floor_init
    ep.govt_rd_multiplier_green = 1.0
    ep.govt_rd_all_multiplier = 0.0
    ep.govt_rd_funds_effective = 0.0
    ep.govt_rd_for_green = 0.0
    ep.brown_invest_ban_year = 5 * p.total_steps
    ep.brown_use_ban_year = 5 * p.total_steps
    ep.net_worth = 1.0e9  # well capitalised: no bailouts in the dynamics tests
    return ep


def seed_fleet(ep, n_green, n_brown):
    if n_green > 0:
        ep.green_plants.add(
            GreenPlant(ep.nation, vintage=0, count=n_green, building_cost=10.0,
                       full_building_cost=10.0)
        )
    if n_brown > 0:
        bp = BrownPlant(ep.nation, vintage=0, count=n_brown, building_cost=2.0,
                        thermal_inefficiency=2.5, emission_intensity=1100.0)
        ep.brown_plants.add(bp)
    ep._update_capacity()


def set_market(ep, electricity_price=1.0, demand=10000.0, production_cost=100.0):
    """Populate the dispatch-side state do_rd reads (Rev_en = c_en * D_en_TOT)."""
    ep.electricity_price = electricity_price
    ep.total_energy_demand = demand
    ep.production_cost = production_cost


# ----------------------------------------------------------------------
# Acceptance: 100-period R&D dynamics
# ----------------------------------------------------------------------

class TestRdDynamics:
    def test_cf_ge_declines_over_100_periods(self, gparams):
        ep = make_ep(seed=1)
        seed_fleet(ep, n_green=5000, n_brown=5000)
        set_market(ep)
        initial = ep.frontier_green_build_cost
        trajectory = []
        for t in range(1, 101):
            ep.do_rd(t, fuel_price=0.02, carbon_tax=0.0, wage=1.0, gparams=gparams)
            trajectory.append(ep.frontier_green_build_cost)
        # Monotonically non-increasing (adoption only on improvement).
        assert all(b <= a + 1e-12 for a, b in zip(trajectory, trajectory[1:]))
        assert trajectory[-1] < initial
        # Never below the green build-cost floor.
        assert trajectory[-1] >= gparams.green_plant_build_cost_floor_init - 1e-9

    def test_a_de_improves_over_100_periods(self, gparams):
        ep = make_ep(seed=2)
        seed_fleet(ep, n_green=5000, n_brown=5000)
        fuel_price = 0.02
        set_market(ep)
        a_de0 = ep.frontier_brown_thermal_ineff
        a_de_traj, bundle_traj = [], []
        for t in range(1, 101):
            ep.do_rd(t, fuel_price=fuel_price, carbon_tax=0.0, wage=1.0, gparams=gparams)
            a_de = ep.frontier_brown_thermal_ineff
            a_de_traj.append(a_de)
            # Adoption minimises the joint lifetime cost (C++ :1178), not A_de
            # alone, so A_de itself wobbles but this bundle is a ratchet.
            bundle_traj.append(ep.frontier_brown_build_cost / gparams.green_plant_payback_threshold
                               + fuel_price * a_de)
        assert all(b <= a + 1e-12 for a, b in zip(bundle_traj, bundle_traj[1:]))
        # Thermal inefficiency improves (declines) over the horizon.
        assert a_de_traj[-1] < a_de0
        assert sum(a_de_traj[50:]) / 50 < sum(a_de_traj[:50]) / 50
        assert a_de_traj[-1] >= gparams.dirty_plant_inv_eff_floor - 1e-9

    def test_green_rd_share_rises_with_green_capacity(self, gparams):
        shares = []
        for n_green, n_brown in ((1000, 9000), (5000, 5000), (9000, 1000)):
            ep = make_ep(seed=3)
            seed_fleet(ep, n_green=n_green, n_brown=n_brown)
            set_market(ep)
            ep.do_rd(1, fuel_price=0.02, carbon_tax=0.0, wage=1.0, gparams=gparams)
            green_rd_share = ep.rd_spending_green / ep.rd_spending_total
            # Green R&D share equals the green capacity share (no govt top-up).
            expected = n_green / (n_green + n_brown)
            assert green_rd_share == pytest.approx(expected, abs=1e-9)
            shares.append(green_rd_share)
        # Strictly increasing in the green capacity share.
        assert shares[0] < shares[1] < shares[2]


# ----------------------------------------------------------------------
# Endogenous green/dirty split (C++ :938-945)
# ----------------------------------------------------------------------

class TestRdSplit:
    def test_endogenous_share_de(self, gparams):
        ep = make_ep()
        seed_fleet(ep, n_green=3000, n_brown=7000)
        set_market(ep)
        ep.do_rd(1, fuel_price=0.02, carbon_tax=0.0, wage=1.0, gparams=gparams)
        assert ep.dirty_rd_share == pytest.approx(0.7)

    def test_exogenous_share_de_when_flag_off(self, gparams):
        gparams.endogenous_dirty_rd_share = 0
        ep = make_ep()
        seed_fleet(ep, n_green=3000, n_brown=7000)
        set_market(ep)
        ep.do_rd(1, fuel_price=0.02, carbon_tax=0.0, wage=1.0, gparams=gparams)
        assert ep.dirty_rd_share == pytest.approx(gparams.dirty_rd_share_init)

    def test_enough_money_branch_uses_revenue_share(self, gparams):
        ep = make_ep()
        seed_fleet(ep, n_green=5000, n_brown=5000)
        # Rev_en=10000, share_RD_en=0.01, PC small -> enough-money branch.
        set_market(ep, electricity_price=1.0, demand=10000.0, production_cost=50.0)
        ep.do_rd(1, fuel_price=0.02, carbon_tax=0.0, wage=1.0, gparams=gparams)
        rev = 10000.0
        assert ep.rd_spending_dirty == pytest.approx(0.01 * 0.5 * rev)
        assert ep.rd_spending_green == pytest.approx(0.01 * 0.5 * rev)

    def test_not_enough_money_branch_spends_margin(self, gparams):
        ep = make_ep()
        seed_fleet(ep, n_green=5000, n_brown=5000)
        # PC so large that Rev*share_RD >= Rev - PC -> margin branch.
        set_market(ep, electricity_price=1.0, demand=10000.0, production_cost=9950.0)
        ep.do_rd(1, fuel_price=0.02, carbon_tax=0.0, wage=1.0, gparams=gparams)
        margin = 10000.0 - 9950.0
        assert ep.rd_spending_dirty == pytest.approx(0.5 * margin)
        assert ep.rd_spending_green == pytest.approx(0.5 * margin)


# ----------------------------------------------------------------------
# Financial accounting (C++ :948-1025)
# ----------------------------------------------------------------------

class TestRdFinance:
    def test_ic_en_payback_window_sum(self, gparams):
        ep = make_ep()
        seed_fleet(ep, n_green=5000, n_brown=5000)
        set_market(ep)
        payback = gparams.green_plant_payback_threshold  # 40
        # Quotas: one inside the window, one exactly on the edge, one outside.
        ep.expansion_cost_quota = {100: 10.0, 100 - payback: 20.0, 100 - payback - 1: 99.0}
        ep.do_rd(100, fuel_price=0.02, carbon_tax=0.0, wage=1.0, gparams=gparams)
        assert ep.investment_cost == pytest.approx(30.0)
        assert ep.expansion_cost_green == pytest.approx(30.0)

    def test_profit_and_net_worth_update(self, gparams):
        ep = make_ep()
        seed_fleet(ep, n_green=5000, n_brown=5000)
        set_market(ep, electricity_price=1.0, demand=10000.0, production_cost=50.0)
        ep.expansion_cost_quota = {}
        nw0 = ep.net_worth
        ep.do_rd(1, fuel_price=0.02, carbon_tax=0.0, wage=1.0, gparams=gparams)
        # Baseline: Pi = Rev - PC - IC - RD_de - RD_ge (no govt funds).
        expected_pi = (
            ep.revenue - ep.production_cost - ep.investment_cost
            - ep.rd_spending_dirty - ep.rd_spending_green
        )
        assert ep.profit == pytest.approx(expected_pi)
        assert ep.net_worth == pytest.approx(nw0 + expected_pi)
        assert ep.bailout_from_govt == 0.0

    def test_bailout_when_insolvent(self, gparams):
        ep = make_ep()
        seed_fleet(ep, n_green=5000, n_brown=5000)
        # Tiny revenue, huge production cost -> negative profit -> insolvency.
        set_market(ep, electricity_price=0.001, demand=100.0, production_cost=1.0e6)
        ep.net_worth = 0.0
        ep.do_rd(1, fuel_price=0.02, carbon_tax=0.0, wage=1.0, gparams=gparams)
        assert ep.bailout_from_govt > 0.0
        # Bailout restores solvency.
        assert ep.net_worth >= 0.0

    def test_labour_demand_rd(self, gparams):
        ep = make_ep()
        seed_fleet(ep, n_green=5000, n_brown=5000)
        set_market(ep, electricity_price=1.0, demand=10000.0, production_cost=50.0)
        ep.do_rd(1, fuel_price=0.02, carbon_tax=0.0, wage=2.0, gparams=gparams)
        assert ep.labour_demand_rd_dirty == pytest.approx(ep.rd_spending_dirty / 2.0)
        assert ep.labour_demand_rd_green == pytest.approx(ep.rd_spending_green / 2.0)


# ----------------------------------------------------------------------
# Technology limits and emissions
# ----------------------------------------------------------------------

class TestRdLimits:
    def test_emissions_held_constant(self, gparams):
        # flag_ff2em_en=0: emission intensity never changes through R&D.
        ep = make_ep(seed=7)
        seed_fleet(ep, n_green=5000, n_brown=5000)
        set_market(ep)
        em0 = ep.frontier_brown_emission_intensity
        for t in range(1, 51):
            ep.do_rd(t, fuel_price=0.02, carbon_tax=0.0, wage=1.0, gparams=gparams)
        assert ep.frontier_brown_emission_intensity == pytest.approx(em0)

    def test_frontier_respects_floors(self, gparams):
        ep = make_ep(seed=8)
        seed_fleet(ep, n_green=5000, n_brown=5000)
        set_market(ep)
        for t in range(1, 201):
            ep.do_rd(t, fuel_price=0.02, carbon_tax=0.0, wage=1.0, gparams=gparams)
        assert ep.frontier_brown_thermal_ineff >= gparams.dirty_plant_inv_eff_floor - 1e-9
        assert ep.frontier_brown_build_cost >= gparams.dirty_plant_build_cost_floor_init - 1e-9
        assert ep.frontier_green_build_cost >= gparams.green_plant_build_cost_floor_init - 1e-9

    def test_dirty_rd_stops_at_limits(self, gparams):
        ep = make_ep(seed=9)
        seed_fleet(ep, n_green=5000, n_brown=5000)
        set_market(ep)
        # Force the dirty frontier to its floors.
        ep.frontier_brown_thermal_ineff = gparams.dirty_plant_inv_eff_floor
        ep.frontier_brown_build_cost = ep.brown_build_cost_floor
        ep.do_rd(1, fuel_price=0.02, carbon_tax=0.0, wage=1.0, gparams=gparams)
        assert ep.rd_spending_dirty == 0.0
        # Green research continues.
        assert ep.rd_spending_green > 0.0
