"""Task 2.1 acceptance tests — BankingSector with NB=10 and Pareto distribution.

Acceptance criteria from IMPLEMENTATION_PLAN:
  1. market shares sum to 1
  2. Pareto distribution of clients per bank (non-uniform client counts)

Additional checks:
  - Total client-target count == N2
  - Every firm is assigned to exactly one bank
  - bank_for_firm returns the correct bank
  - Equal-split fallback works for NB=1
"""
from __future__ import annotations

import numpy as np
import pytest

from dsk.agents.consumption_good_firm import ConsumptionGoodFirm
from dsk.agents.capital_good_firm import CapitalGoodFirm
from dsk.nation import Nation
from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters
from dsk.sectors.banking_sector import BankingSector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def gparams():
    g = GlobalParameters()
    g.n1_capital_good_firms = 50
    g.n2_consumption_good_firms = 200
    g.n1_foreign_firms = 50
    g.labour_supply_init = 250_000.0
    return g


@pytest.fixture
def nparams_nb10():
    """NationParameters with n_banks=10 (baseline)."""
    return NationParameters()  # n_banks=10 is the default


@pytest.fixture
def nparams_nb1():
    n = NationParameters()
    n.n_banks = 1
    return n


@pytest.fixture
def nation(nparams_nb10):
    return Nation("banking-test", nparams_nb10)


@pytest.fixture
def rng():
    return np.random.default_rng(123)


@pytest.fixture
def s2_firms(nation, gparams, nparams_nb10, rng):
    """N2 ConsumptionGoodFirms with net_worth initialised."""
    firms = []
    counter = 0
    n1 = gparams.n1_capital_good_firms
    n2 = gparams.n2_consumption_good_firms
    for j in range(n2):
        f = ConsumptionGoodFirm(nation, rng)
        counter = f.initialise_from_parameters(
            gparams, nparams_nb10,
            preferred_supplier_idx=j % n1,
            bank_idx=0,
            machine_counter_start=counter,
        )
        firms.append(f)
    return firms


@pytest.fixture
def banking_sector_nb10(nation, gparams, nparams_nb10, rng, s2_firms):
    bs = BankingSector()
    bs.initialise_from_parameters(gparams, nparams_nb10, rng, nation, s2_firms)
    return bs


# ---------------------------------------------------------------------------
# Acceptance criterion 1: market shares sum to 1
# ---------------------------------------------------------------------------

def test_market_shares_sum_to_one(banking_sector_nb10):
    """fB sums to 1 across all NB banks (C++ line 1284: fB = 1/NB uniform)."""
    total = sum(b.market_share for b in banking_sector_nb10)
    assert abs(total - 1.0) < 1e-12, f"market shares sum to {total}, expected 1.0"


def test_market_share_uniform(banking_sector_nb10, nparams_nb10):
    """Each bank's market share equals 1/NB (uniform, as in C++)."""
    expected = 1.0 / nparams_nb10.n_banks
    for bank in banking_sector_nb10:
        assert abs(bank.market_share - expected) < 1e-12


# ---------------------------------------------------------------------------
# Acceptance criterion 2: Pareto distribution of clients per bank
# ---------------------------------------------------------------------------

def test_pareto_client_distribution_nonuniform(banking_sector_nb10, gparams):
    """With flag_pareto==1, client counts across banks are non-uniform."""
    assert gparams.pareto_client_distribution == 1, "baseline uses flag_pareto=1"
    client_counts = [b.n_clients_target for b in banking_sector_nb10]
    # Pareto distribution gives non-uniform counts — at least two banks differ
    assert len(set(client_counts)) > 1, (
        f"All banks have equal clients {client_counts[0]} — Pareto should make them non-uniform"
    )


def test_pareto_client_total_equals_n2(banking_sector_nb10, gparams):
    """Sum of NL targets across all banks equals N2 (rejection sampler guarantee)."""
    n2 = gparams.n2_consumption_good_firms
    total = sum(b.n_clients_target for b in banking_sector_nb10)
    assert total == n2, f"sum(NL) = {total}, expected N2 = {n2}"


# ---------------------------------------------------------------------------
# Firm assignment invariants
# ---------------------------------------------------------------------------

def test_all_firms_assigned_to_exactly_one_bank(banking_sector_nb10, s2_firms):
    """Every firm has bank_idx set (not None)."""
    for firm in s2_firms:
        assert firm.bank_idx is not None, f"firm {firm.unique_id} has no bank_idx"


def test_firm_in_exactly_one_bank_firm_match(banking_sector_nb10, s2_firms):
    """Each firm's unique_id appears in exactly one bank's firm_match set."""
    all_banks = list(banking_sector_nb10)
    for firm in s2_firms:
        count = sum(1 for bank in all_banks if firm.unique_id in bank.firm_match)
        assert count == 1, (
            f"firm {firm.unique_id} appears in {count} bank firm_match sets"
        )


def test_bank_for_firm_returns_correct_bank(banking_sector_nb10, s2_firms):
    """bank_for_firm(uid) returns the bank whose firm_match contains uid."""
    for firm in s2_firms[:10]:  # spot-check first 10 firms
        bank = banking_sector_nb10.bank_for_firm(firm.unique_id)
        assert firm.unique_id in bank.firm_match


def test_firm_bank_idx_consistent_with_bank_list(banking_sector_nb10, s2_firms):
    """firm.bank_idx matches the index of the bank containing that firm."""
    banks = list(banking_sector_nb10)
    for firm in s2_firms:
        b = banks[firm.bank_idx]
        assert firm.unique_id in b.firm_match


# ---------------------------------------------------------------------------
# NB count and basic balance-sheet checks
# ---------------------------------------------------------------------------

def test_nb10_creates_ten_banks(banking_sector_nb10, nparams_nb10):
    """BankingSector creates exactly n_banks=10 Bank objects."""
    assert len(banking_sector_nb10) == nparams_nb10.n_banks == 10


def test_nb10_all_banks_active(banking_sector_nb10):
    """All 10 banks are active after initialisation."""
    for bank in banking_sector_nb10:
        assert bank.is_active


def test_nb10_total_equity_equals_aggregate(banking_sector_nb10, gparams, nparams_nb10):
    """Sum of per-bank equity equals the nation-level expected total.

    Regardless of how firms are distributed across banks, total client NW is
    N2 * W20, so total deposits = N2*W20 / reserve_rate, and total equity =
    total_deposits * bank_equity_init_multiplier.
    """
    n2 = gparams.n2_consumption_good_firms
    w20 = gparams.s2_net_worth_init
    expected_total_equity = (
        n2 * w20
        / nparams_nb10.bank_reserve_requirement_rate
        * gparams.bank_equity_init_multiplier
    )
    actual = banking_sector_nb10.total_equity()
    assert abs(actual - expected_total_equity) < 1e-6, (
        f"total equity {actual:.2f} != expected {expected_total_equity:.2f}"
    )


# ---------------------------------------------------------------------------
# NB=1 fallback (equal split, no Pareto)
# ---------------------------------------------------------------------------

def test_nb1_equal_split(nation, gparams, nparams_nb1, rng, s2_firms):
    """With n_banks=1, a single bank gets all N2 firms."""
    nation2 = Nation("nb1-test", nparams_nb1)
    bs = BankingSector()
    bs.initialise_from_parameters(gparams, nparams_nb1, rng, nation2, s2_firms)
    assert len(bs) == 1
    bank = list(bs)[0]
    assert bank.market_share == pytest.approx(1.0)
    assert bank.n_clients_target == gparams.n2_consumption_good_firms


# ---------------------------------------------------------------------------
# BankingSector._bounded_pareto_rv unit test
# ---------------------------------------------------------------------------

def test_bounded_pareto_rv_within_range():
    """Draws are always in [ceil(k), ceil(p)] = [2, 400]."""
    rng = np.random.default_rng(0)
    draws = [
        BankingSector._bounded_pareto_rv(rng, alpha=0.8, lower_bound=2.0, upper_bound=400.0)
        for _ in range(500)
    ]
    assert all(2 <= d <= 400 for d in draws), "Pareto draws outside [k, p]"


def test_bounded_pareto_rv_integers():
    """Draws are always positive integers (ceil applied)."""
    rng = np.random.default_rng(42)
    draws = [
        BankingSector._bounded_pareto_rv(rng, alpha=0.8, lower_bound=2.0, upper_bound=400.0)
        for _ in range(200)
    ]
    assert all(isinstance(d, int) and d > 0 for d in draws)


# ---------------------------------------------------------------------------
# _draw_pareto_nl: sum constraint and impossible-case fallback
# ---------------------------------------------------------------------------

def test_draw_pareto_nl_sum_constraint():
    """Successful _draw_pareto_nl always returns list summing to N2."""
    rng = np.random.default_rng(7)
    nl = BankingSector._draw_pareto_nl(
        rng, nb=10, n2=200, alpha=0.8, lower_bound=2.0, upper_bound=400.0
    )
    assert sum(nl) == 200
    assert len(nl) == 10


def test_draw_pareto_nl_impossible_falls_back_to_equal_split():
    """When N2 < NB * ceil(k), falls back to equal split without infinite loop."""
    rng = np.random.default_rng(0)
    # n2=5 < nb*2=20, impossible
    nl = BankingSector._draw_pareto_nl(
        rng, nb=10, n2=5, alpha=0.8, lower_bound=2.0, upper_bound=400.0
    )
    assert sum(nl) == 5
    assert len(nl) == 10
    # Equal split: floor(5/10)=0 for each, bank[0] gets remainder 5
    assert nl[0] == 5
    assert all(nl[i] == 0 for i in range(1, 10))
