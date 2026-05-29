"""Task 1.3 acceptance tests: ConsumptionGoodFirm initialisation.

Acceptance criterion: construct N2=400 firms; assert K0 initial capital
distributed correctly across machine vintages.

C++ reference: INITIALIZE() in dsk_main.cpp lines 1043-1711, specifically
the N2-firm machine stock loop (lines 1580-1608) and demand initialisation
(lines 1610-1638).
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from dsk.agents.consumption_good_firm import ConsumptionGoodFirm
from dsk.agents.technology import Technology
from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters


class _MockNation:
    """Minimal stand-in for Nation sufficient for Agent.__init__."""


@pytest.fixture
def gparams():
    return GlobalParameters()


@pytest.fixture
def nparams():
    return NationParameters()


@pytest.fixture
def mock_nation():
    return _MockNation()


@pytest.fixture
def firms_and_counter(mock_nation, gparams, nparams):
    """Construct N2=400 firms with the C++ machine-counter threading."""
    N1 = gparams.n1_capital_good_firms   # 100
    N2 = gparams.n2_consumption_good_firms  # 400
    step = N2 // N1  # = 4 (N2 must be divisible by N1)

    rng = np.random.default_rng(42)
    machine_counter = 0  # C++ `i=0` before the firm loop

    result = []
    for j0 in range(N2):  # 0-indexed firms
        # C++ fornit assignment: firm j0 belongs to supplier block j0 // step (0-indexed)
        preferred_supplier_idx = j0 // step
        firm = ConsumptionGoodFirm(mock_nation, rng)
        machine_counter = firm.initialise_from_parameters(
            gparams,
            nparams,
            preferred_supplier_idx=preferred_supplier_idx,
            bank_idx=0,
            machine_counter_start=machine_counter,
        )
        result.append(firm)

    return result, machine_counter


@pytest.fixture
def firms(firms_and_counter):
    return firms_and_counter[0]


# ---------------------------------------------------------------------------
# Acceptance criterion: K0 initial capital distributed correctly
# ---------------------------------------------------------------------------

def test_400_firms_constructed(firms, gparams):
    assert len(firms) == gparams.n2_consumption_good_firms


def test_total_machines_per_firm_equals_K0_over_dim_mach(firms, gparams):
    """Each firm holds exactly K0/dim_mach machines (= 20)."""
    expected = gparams.capital_init / gparams.machine_size_units
    for f in firms:
        assert math.isclose(f.machines.total_machines(), expected, rel_tol=1e-9)


def test_all_machines_at_vintage_zero(firms):
    """All initial machines are at vintage_key=0 (the C++ tt=1 → index 0 slot)."""
    for f in firms:
        assert f.machines.vintage_keys == [0]


def test_no_machines_at_other_vintages(firms):
    """Only one vintage should be present after initialization."""
    for f in firms:
        assert len(f.machines.vintage_keys) == 1


def test_total_capital_equals_K0(firms, gparams):
    """total_machines × dim_mach == K0 for every firm."""
    K0 = gparams.capital_init
    dim_mach = gparams.machine_size_units
    for f in firms:
        assert math.isclose(f.machines.total_machines() * dim_mach, K0, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# Machine stock properties
# ---------------------------------------------------------------------------

def test_machine_labour_productivity_is_A0(firms, gparams):
    """All machines start with labour_productivity == A0."""
    A0 = gparams.productivity_init
    for f in firms:
        row = f.machines.row_for(0)
        assert row is not None
        active = f.machines.count[row] > 0
        assert np.all(f.machines.labour_productivity[row][active] == A0)


def test_ages_positive_and_bounded(firms, gparams):
    """Machine ages are in [1, agemax+1] (C++ initialises from agemax+1 downward)."""
    agemax = gparams.machine_max_age
    for f in firms:
        row = f.machines.row_for(0)
        ages = f.machines.age[row][f.machines.count[row] > 0]
        assert np.all(ages >= 1.0)
        assert np.all(ages <= agemax + 1.0)


def test_machines_not_from_preferred_supplier(firms, gparams):
    """No machine is supplied by the firm's own preferred supplier."""
    for f in firms:
        preferred = f.preferred_supplier_idx
        row = f.machines.row_for(0)
        # machines from preferred supplier should be zero
        assert f.machines.count[row, preferred] == 0.0


# ---------------------------------------------------------------------------
# Financial and market state
# ---------------------------------------------------------------------------

def test_net_worth_equals_W20(firms, gparams):
    W20 = gparams.s2_net_worth_init
    assert all(f.net_worth == W20 for f in firms)
    assert all(f.net_worth_prev == W20 for f in firms)


def test_initial_debt_is_zero(firms):
    assert all(f.debt == 0.0 for f in firms)
    assert all(f.debt_prev == 0.0 for f in firms)


def test_market_shares_equal_and_sum_to_one(firms, gparams):
    N2 = gparams.n2_consumption_good_firms
    expected = 1.0 / N2
    shares = [f.market_share for f in firms]
    assert all(abs(s - expected) < 1e-12 for s in shares)
    assert abs(sum(shares) - 1.0) < 1e-9


def test_price_matches_cpp_formula(firms, gparams, nparams):
    """C++: p2 = (1+mi2) * w0 / A0."""
    expected = (1.0 + nparams.s2_markup_init) * gparams.wage_init / gparams.productivity_init
    assert all(abs(f.price - expected) < 1e-10 for f in firms)


def test_unit_cost_matches_cpp_formula(firms, gparams):
    """C++: c2 = w0 / A0."""
    expected = gparams.wage_init / gparams.productivity_init
    assert all(abs(f.unit_cost - expected) < 1e-10 for f in firms)


def test_markup_equals_mi2(firms, nparams):
    mi2 = nparams.s2_markup_init
    assert all(f.markup == mi2 for f in firms)


def test_price_equals_one_plus_markup_times_cost(firms):
    for f in firms:
        assert abs(f.price - (1.0 + f.markup) * f.unit_cost) < 1e-12


# ---------------------------------------------------------------------------
# Demand and inventory initialisation
# ---------------------------------------------------------------------------

def test_expected_demand_is_positive(firms):
    assert all(f.expected_demand > 0 for f in firms)


def test_expected_demand_is_uniform_across_firms(firms):
    """All firms start with the same expected demand (symmetric C++ init)."""
    demands = [f.expected_demand for f in firms]
    assert max(demands) - min(demands) < 1e-9


def test_expected_demand_matches_cpp_formula(firms, gparams, nparams):
    """D2 per firm = D20/N2 where D20 is from the flagC==2, flagTAX==2 branch."""
    N2 = gparams.n2_consumption_good_firms
    A0 = gparams.productivity_init
    a = gparams.s1_productivity_scale
    w0 = gparams.wage_init
    mi1 = gparams.s1_markup
    nu = gparams.rd_budget_fraction
    dim_mach = gparams.machine_size_units
    LS0 = gparams.labour_supply_init
    mi2 = nparams.s2_markup_init
    wu = nparams.unemployment_benefit_share

    p1 = (1.0 + mi1) * w0 / (A0 * a)
    p2 = (1.0 + mi2) * w0 / A0
    I_init = dim_mach

    d20 = (
        (w0 / (A0 * a) + nu * p1) * (I_init / dim_mach) * N2 * (1.0 - wu)
        + wu * w0 * LS0
    ) / (p2 - (1.0 - wu) * w0 / A0)

    expected_d2 = d20 / N2
    assert all(abs(f.expected_demand - expected_d2) < 1e-6 for f in firms)


def test_inventory_equals_theta_times_demand(firms, gparams):
    theta = gparams.inventory_target_fraction
    for f in firms:
        assert abs(f.inventory - theta * f.expected_demand) < 1e-10


def test_inventory_monetary_equals_inventory_times_price(firms):
    for f in firms:
        assert abs(f.inventory_monetary - f.inventory * f.price) < 1e-10


def test_sales_equals_demand_times_price(firms):
    for f in firms:
        assert abs(f.sales - f.expected_demand * f.price) < 1e-10


# ---------------------------------------------------------------------------
# Relationships and status
# ---------------------------------------------------------------------------

def test_preferred_supplier_idx_stored(firms, gparams):
    """Each firm's preferred_supplier_idx should be in [0, N1)."""
    N1 = gparams.n1_capital_good_firms
    for f in firms:
        assert 0 <= f.preferred_supplier_idx < N1


def test_bank_idx_stored(firms):
    assert all(f.bank_idx == 0 for f in firms)


def test_all_firms_alive(firms):
    assert all(f.is_alive for f in firms)


def test_unique_ids_distinct(firms):
    ids = [f.unique_id for f in firms]
    assert len(set(ids)) == len(firms)


def test_rng_is_stored(firms):
    assert all(isinstance(f.rng, np.random.Generator) for f in firms)


def test_effective_labour_prod_at_A0(firms, gparams):
    A0 = gparams.productivity_init
    assert all(abs(f.effective_labour_prod - A0) < 1e-12 for f in firms)


# ---------------------------------------------------------------------------
# Machine counter threading: two-firm cross-check
# ---------------------------------------------------------------------------

def test_machine_counter_is_threaded_across_firms(mock_nation, gparams, nparams):
    """The rotating machine counter carries over between firms (C++ `i` is global).

    With N1=100 and preferred_supplier_idx=0 for firm 0, the first machine of
    firm 0 goes to supplier 2 (skipping 1→preferred, landing at 2).
    With preferred_supplier_idx=0 for firm 1, machines continue from where firm 0
    left off — they do NOT restart from supplier 1.
    """
    N1 = gparams.n1_capital_good_firms
    n_mach = int(gparams.capital_init / gparams.machine_size_units)  # 20

    rng = np.random.default_rng(0)

    firm0 = ConsumptionGoodFirm(mock_nation, rng)
    counter_after_firm0 = firm0.initialise_from_parameters(
        gparams, nparams, preferred_supplier_idx=0, bank_idx=0,
        machine_counter_start=0,
    )

    firm1 = ConsumptionGoodFirm(mock_nation, rng)
    firm1.initialise_from_parameters(
        gparams, nparams, preferred_supplier_idx=0, bank_idx=0,
        machine_counter_start=counter_after_firm0,
    )

    # Firm 0: skips supplier 0 (1-indexed 1), places at 2..21 (0-indexed 1..20)
    # Firm 1: continues from counter_after_firm0=21, places at 22..41 (0-indexed 21..40)
    row = firm0.machines.row_for(0)
    firm0_suppliers = set(
        s for s in range(N1) if firm0.machines.count[row, s] > 0
    )
    firm1_suppliers = set(
        s for s in range(N1) if firm1.machines.count[firm1.machines.row_for(0), s] > 0
    )

    # The two supplier sets should be disjoint (no counter reset between firms)
    assert firm0_suppliers.isdisjoint(firm1_suppliers)
    # Each set has exactly n_mach=20 entries (one machine per supplier in this range)
    assert len(firm0_suppliers) == n_mach
    assert len(firm1_suppliers) == n_mach
