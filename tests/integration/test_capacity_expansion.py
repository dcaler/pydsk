"""Integration tests for Task 3.4 — ElectricityProducer capacity expansion.

Acceptance criteria (IMPLEMENTATION_PLAN §3.4):
- Under a price advantage for green, green share grows.
- Under a brown-ban scenario, no new brown built after the ban start time.

Plus targeted checks on the building blocks: the green_plant_cost helper,
the hurry-cost surcharge, premature replacement, and the EI_en demand gate.
"""
import math

import pytest
from unittest.mock import MagicMock

from dsk.agents.electricity_producer import ElectricityProducer, green_plant_cost
from dsk.agents.power_plant import BrownPlant, GreenPlant
from dsk.parameters.global_parameters import GlobalParameters


@pytest.fixture
def nation():
    return MagicMock()


@pytest.fixture
def gparams():
    # Defaults already encode the Task-3.4 flags: flag_energy_exp=1,
    # flag_early_plants=2, flag_early_plants2=0, flag_early_brown=0.
    return GlobalParameters()


def make_ep(
    nation,
    *,
    frontier_brown_ineff=2.5,
    frontier_brown_em=1100.0,
    frontier_brown_cf=2.0,
    frontier_green_cf=10.0,
    net_worth=1.0e6,
    total_steps=220,
):
    ep = ElectricityProducer(nation)
    ep.frontier_brown_thermal_ineff = frontier_brown_ineff
    ep.frontier_brown_emission_intensity = frontier_brown_em
    ep.frontier_brown_build_cost = frontier_brown_cf
    ep.frontier_green_build_cost = frontier_green_cf
    ep.net_worth = net_worth
    ep.brown_invest_ban_year = 5 * total_steps   # no ban by default
    ep.brown_use_ban_year = 5 * total_steps
    return ep


def add_brown(ep, nation, count, vintage=1, building_cost=2.0,
              thermal_ineff=2.5, emission_int=1100.0):
    bp = BrownPlant(nation, vintage=vintage, count=count,
                    building_cost=building_cost,
                    thermal_inefficiency=thermal_ineff,
                    emission_intensity=emission_int)
    ep.brown_plants.add(bp)
    ep._update_capacity()
    return bp


def add_green(ep, nation, count, vintage=1, building_cost=10.0):
    gp = GreenPlant(nation, vintage=vintage, count=count,
                    building_cost=building_cost, full_building_cost=building_cost)
    ep.green_plants.add(gp)
    ep._update_capacity()
    return gp


def new_brown_vintages(ep, since):
    return [p for p in ep.brown_plants if p.vintage >= since and p.count > 0]


def new_green_vintages(ep, since):
    return [p for p in ep.green_plants if p.vintage >= since and p.count > 0]


# ----------------------------------------------------------------------
# green_plant_cost helper (C++ module_energy.cpp:1471)
# ----------------------------------------------------------------------

class TestGreenPlantCost:
    def test_base_cost_no_subsidy_no_hurry(self):
        # nsubmax=0 -> no subsidy; below hurry threshold -> base price.
        assert green_plant_cost(1, 1500, 0, 0.0, 10.0, 1.0) == 10.0

    def test_subsidy_applies_within_subsidy_limit(self):
        # nsubmax=1500 >= n_new -> subsidy subtracted.
        assert green_plant_cost(1, 1500, 1500, 2.0, 10.0, 1.0) == 8.0

    def test_hurry_doubles_price_at_double_quota(self):
        # Building 2x the no-hurry quota makes the marginal plant cost 2x base.
        assert green_plant_cost(3000, 1500, 0, 0.0, 10.0, 1.0) == pytest.approx(20.0)

    def test_no_hurry_flag_keeps_base_price(self):
        # hurry=0 -> no surcharge regardless of count.
        assert green_plant_cost(9999, 1500, 0, 0.0, 10.0, 0.0) == 10.0

    def test_zero_quota_first_plant_finite_then_infinite(self):
        # Mirrors C++ double-division-by-zero: n_new==0 finite, beyond -> +inf.
        assert green_plant_cost(0, 0, 0, 0.0, 5.0, 1.0) == 5.0
        assert green_plant_cost(1, 0, 0, 0.0, 5.0, 1.0) == math.inf


# ----------------------------------------------------------------------
# Acceptance criterion 1: green price advantage grows green share
# ----------------------------------------------------------------------

def test_green_price_advantage_grows_green_share(nation, gparams):
    ep = make_ep(nation, frontier_green_cf=0.5)  # green cheap per payback
    add_brown(ep, nation, count=100, vintage=1)
    assert ep.green_share() == 0.0

    shares = []
    for t in range(6, 13):
        demand = 100.0 + 30.0 * (t - 5)  # demand grows each period
        ep.plan_capacity_expansion(t, demand, fuel_price=0.02,
                                   carbon_tax=0.0, gparams=gparams)
        shares.append(ep.green_share())

    # Strictly increasing green share, ending well above zero.
    assert all(b > a for a, b in zip(shares, shares[1:])), shares
    assert shares[-1] > 0.3
    # No new brown was built (green out-competed it on payback).
    assert new_brown_vintages(ep, since=6) == []


# ----------------------------------------------------------------------
# Acceptance criterion 2: brown ban => no new brown after start time
# ----------------------------------------------------------------------

def test_brown_ban_blocks_new_brown(nation, gparams):
    ban_start = 8
    ep = make_ep(nation, frontier_green_cf=10.0)  # green expensive; brown preferred absent ban
    ep.brown_invest_ban_year = ban_start
    ep.brown_use_ban_year = ban_start
    add_brown(ep, nation, count=100, vintage=1)

    green_cap_before = ep.total_green_capacity
    for t in range(ban_start, ban_start + 4):
        demand = 100.0 + 25.0 * (t - ban_start + 1)
        ep.plan_capacity_expansion(t, demand, fuel_price=0.02,
                                   carbon_tax=0.0, gparams=gparams)

    # No brown plant of any banned-era vintage was built.
    assert new_brown_vintages(ep, since=ban_start) == []
    # Demand was instead met with green capacity.
    assert ep.total_green_capacity > green_cap_before


def test_brown_built_when_allowed_and_green_expensive(nation, gparams):
    ep = make_ep(nation, frontier_green_cf=10.0)  # green not worth it
    add_brown(ep, nation, count=100, vintage=1)

    ep.plan_capacity_expansion(6, demand_for_building=160.0,
                               fuel_price=0.02, carbon_tax=0.0, gparams=gparams)

    new_brown = new_brown_vintages(ep, since=6)
    assert len(new_brown) == 1
    # 160 demand - 100 capacity = 60 new brown plants.
    assert new_brown[0].count == 60
    assert new_green_vintages(ep, since=6) == []
    assert ep.expansion_investment == 60


# ----------------------------------------------------------------------
# Premature replacement (decide_premature_replacement)
# ----------------------------------------------------------------------

def test_premature_replacement_swaps_brown_for_green(nation, gparams):
    ep = make_ep(nation, frontier_green_cf=0.5)  # green cheap
    brown = add_brown(ep, nation, count=50, vintage=1)
    add_green(ep, nation, count=50, vintage=1)
    share_before = ep.green_share()

    # demand == capacity so EI_en == 0: isolate replacement from expansion.
    ep.plan_capacity_expansion(6, demand_for_building=100.0,
                               fuel_price=0.02, carbon_tax=0.0, gparams=gparams)

    assert ep.expansion_investment == 0
    # Green built purely by replacement.
    assert new_green_vintages(ep, since=6)
    # Some brown units were deactivated (premature replacement)...
    assert ep.brown_plants.total_active_capacity() < 50
    # ...but not scrapped (flag_early_plants2=0): count is unchanged, capacity holds.
    assert brown.count == 50
    assert ep.total_brown_capacity == 50
    assert ep.plant_worth_lost > 0.0
    assert ep.green_share() > share_before


def test_replacement_respects_net_worth_budget(nation, gparams):
    # prudinv = 2*net_worth; with zero net worth no replacement may occur.
    ep = make_ep(nation, frontier_green_cf=0.5, net_worth=0.0)
    add_brown(ep, nation, count=50, vintage=1)
    add_green(ep, nation, count=50, vintage=1)

    ep.plan_capacity_expansion(6, demand_for_building=100.0,
                               fuel_price=0.02, carbon_tax=0.0, gparams=gparams)

    assert ep.expansion_investment == 0
    assert ep.brown_plants.total_active_capacity() == 50  # nothing replaced
    assert new_green_vintages(ep, since=6) == []


# ----------------------------------------------------------------------
# EI_en demand gate
# ----------------------------------------------------------------------

def test_no_expansion_when_capacity_meets_demand(nation, gparams):
    ep = make_ep(nation, frontier_green_cf=10.0)
    add_brown(ep, nation, count=100, vintage=1)

    ep.plan_capacity_expansion(6, demand_for_building=80.0,
                               fuel_price=0.02, carbon_tax=0.0, gparams=gparams)

    assert ep.expansion_investment == 0
    assert new_brown_vintages(ep, since=6) == []
    assert new_green_vintages(ep, since=6) == []
    assert ep.total_brown_capacity == 100


def test_carbon_tax_tips_payback_toward_green(nation, gparams):
    # Green moderately priced: without carbon tax brown wins; with a high carbon
    # tax the brown alternative cost rises and green is built instead.
    add_kwargs = dict(frontier_green_cf=5.0)

    ep_no_tax = make_ep(nation, **add_kwargs)
    add_brown(ep_no_tax, nation, count=100, vintage=1)
    ep_no_tax.plan_capacity_expansion(6, 160.0, fuel_price=0.02,
                                      carbon_tax=0.0, gparams=gparams)
    assert new_brown_vintages(ep_no_tax, since=6)  # brown built

    ep_tax = make_ep(nation, **add_kwargs)
    add_brown(ep_tax, nation, count=100, vintage=1)
    ep_tax.plan_capacity_expansion(6, 160.0, fuel_price=0.02,
                                   carbon_tax=0.05, gparams=gparams)
    assert new_green_vintages(ep_tax, since=6)  # green built
    assert new_brown_vintages(ep_tax, since=6) == []
