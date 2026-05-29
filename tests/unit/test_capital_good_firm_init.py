"""Task 1.1 acceptance tests: CapitalGoodFirm initialisation.

Acceptance criterion: construct N1=100 firms; assert distribution of initial
productivities matches C++ initialisation (mean within 1%, std within 5% of A0).

Pre-TECHANGEND state: all N1 firms are identical (A0=1 everywhere).
TECHANGEND (Task 1.14) adds inter-firm dispersion in a later task.
"""
from __future__ import annotations

import numpy as np
import pytest

from dsk.agents.capital_good_firm import CapitalGoodFirm
from dsk.agents.technology import Technology
from dsk.parameters.global_parameters import GlobalParameters


class _MockNation:
    """Minimal stand-in for Nation sufficient for Agent.__init__."""


@pytest.fixture
def gparams():
    return GlobalParameters()


@pytest.fixture
def mock_nation():
    return _MockNation()


@pytest.fixture
def firms(mock_nation, gparams):
    rng = np.random.default_rng(42)
    result = []
    for _ in range(gparams.n1_capital_good_firms):
        f = CapitalGoodFirm(mock_nation, rng)
        f.initialise_from_parameters(gparams)
        result.append(f)
    return result


# --- Acceptance criterion ---

def test_machine_prod_mean_within_1pct(firms, gparams):
    """Mean machine_labour_prod within 1% of A0."""
    A0 = gparams.productivity_init
    prods = np.array([f.machine_labour_prod for f in firms])
    assert abs(np.mean(prods) - A0) / A0 < 0.01


def test_machine_prod_std_within_5pct_of_A0(firms, gparams):
    """Std of machine_labour_prod < 5% of A0 (pre-TECHANGEND: all firms identical)."""
    A0 = gparams.productivity_init
    prods = np.array([f.machine_labour_prod for f in firms])
    assert np.std(prods) < 0.05 * A0


# --- Per-field verification ---

def test_process_labour_prod_at_A0(firms, gparams):
    A0 = gparams.productivity_init
    assert all(f.process_labour_prod == A0 for f in firms)


def test_market_shares_equal_and_sum_to_one(firms, gparams):
    N1 = gparams.n1_capital_good_firms
    expected = 1.0 / N1
    shares = [f.market_share for f in firms]
    assert all(abs(s - expected) < 1e-12 for s in shares)
    assert abs(sum(shares) - 1.0) < 1e-10


def test_price_matches_cpp_formula(firms, gparams):
    """C++ p1 = (1+mi1) * w0 / (A0 * a)."""
    expected = (
        (1.0 + gparams.s1_markup)
        * gparams.wage_init
        / (gparams.productivity_init * gparams.s1_productivity_scale)
    )
    assert all(abs(f.price - expected) < 1e-10 for f in firms)


def test_unit_cost_matches_cpp_formula(firms, gparams):
    """C++ c1 = w0 / (A0 * a)."""
    expected = gparams.wage_init / (
        gparams.productivity_init * gparams.s1_productivity_scale
    )
    assert all(abs(f.unit_cost - expected) < 1e-10 for f in firms)


def test_price_equals_markup_times_cost(firms, gparams):
    for f in firms:
        assert abs(f.price - (1.0 + gparams.s1_markup) * f.unit_cost) < 1e-12


def test_net_worth_equals_W10(firms, gparams):
    W10 = gparams.s1_net_worth_init
    assert all(f.net_worth == W10 for f in firms)
    assert all(f.net_worth_prev == W10 for f in firms)


def test_initial_debt_is_zero(firms):
    assert all(f.debt == 0.0 for f in firms)


def test_patent_timer_is_zero(firms):
    assert all(f.patent_timer == 0.0 for f in firms)


def test_vintage_is_one(firms):
    assert all(f.vintage == 1 for f in firms)


def test_all_firms_alive(firms):
    assert all(f.is_alive for f in firms)


def test_unique_ids_distinct(firms):
    ids = [f.unique_id for f in firms]
    assert len(set(ids)) == len(firms)


def test_rd_budget_equals_nu_times_sales(firms, gparams):
    nu = gparams.rd_budget_fraction
    for f in firms:
        assert abs(f.rd_budget - nu * f.sales) < 1e-12


def test_rd_split_sums_to_total(firms):
    for f in firms:
        assert abs(f.rd_innovation_budget + f.rd_imitation_budget - f.rd_budget) < 1e-14


def test_rd_sector1_share_at_xin0(firms, gparams):
    xin0 = gparams.innovation_sector1_share_initial
    assert all(f.rd_sector1_share == xin0 for f in firms)


def test_current_technology_is_Technology_instance(firms):
    assert all(isinstance(f.current_technology, Technology) for f in firms)


def test_current_technology_labour_prod_at_A0(firms, gparams):
    A0 = gparams.productivity_init
    assert all(f.current_technology.labour_productivity == A0 for f in firms)


def test_num_clients_equals_N2_over_N1(firms, gparams):
    expected = gparams.n2_consumption_good_firms // gparams.n1_capital_good_firms
    assert all(f.num_clients == expected for f in firms)


def test_clients_list_initially_empty(firms):
    assert all(f.clients == [] for f in firms)


def test_initial_sales_value(firms, gparams):
    """S1 = (N2/N1) * p1; each s1 firm initially serves N2/N1 clients each buying 1 machine."""
    N1 = gparams.n1_capital_good_firms
    N2 = gparams.n2_consumption_good_firms
    expected_price = (
        (1.0 + gparams.s1_markup)
        * gparams.wage_init
        / (gparams.productivity_init * gparams.s1_productivity_scale)
    )
    expected_sales = (float(N2) / float(N1)) * expected_price
    assert all(abs(f.sales - expected_sales) < 1e-10 for f in firms)


def test_no_innovation_at_init(firms):
    assert all(not f.innovated_sector1 for f in firms)
    assert all(not f.innovated_sector2 for f in firms)
    assert all(not f.imitated for f in firms)
    assert all(f.innovation_candidate is None for f in firms)
    assert all(f.imitation_candidate is None for f in firms)


def test_rng_is_stored(firms):
    assert all(isinstance(f.rng, np.random.Generator) for f in firms)


def test_100_firms_constructed(firms, gparams):
    assert len(firms) == gparams.n1_capital_good_firms
