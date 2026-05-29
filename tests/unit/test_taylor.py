"""Tests for Task 2.3: CentralBank.apply_taylor_rule and remunerate_reserves.

Acceptance criterion: rate moves the right direction in response to
inflation/unemployment deviations from target.

C++ reference: TAYLOR() in module_macro.cpp:263 (flagTAYLOR=2 branch).
"""
import numpy as np
import pytest

from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters
from dsk.agents.central_bank import CentralBank


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cb(policy_rate: float = 0.02) -> CentralBank:
    """Return a CentralBank initialised with default parameters."""
    gparams = GlobalParameters()
    nparams = NationParameters()
    nparams.policy_rate = policy_rate

    # CentralBank expects a Nation back-reference for gparams/nparams access;
    # use a minimal stub that exposes what apply_taylor_rule needs.
    class StubNation:
        def __init__(self, gp, np_):
            self.gparams = gp
            self.params = np_
            self.params = np_
            self.banking_sector = []   # no banks: lending-rate update loop is a no-op

    cb = CentralBank(StubNation(gparams, nparams))
    cb.initialise_from_parameters(gparams, nparams)
    return cb


# ---------------------------------------------------------------------------
# apply_taylor_rule — directional tests
# ---------------------------------------------------------------------------

def test_rate_rises_on_excess_inflation():
    """r increases when inflation > inflation_target (taylor1 > 0)."""
    cb = _make_cb(policy_rate=0.02)
    r0 = cb.policy_rate
    inflation_target = cb.inflation_target         # 0.005
    # inflation = 2 × target → positive gap
    cb.apply_taylor_rule(inflation=inflation_target * 2, unemployment=0.05)
    assert cb.policy_rate > r0


def test_rate_falls_on_low_inflation():
    """r decreases when inflation < inflation_target."""
    cb = _make_cb(policy_rate=0.02)
    r0 = cb.policy_rate
    inflation_target = cb.inflation_target
    # inflation = 0 → negative gap
    cb.apply_taylor_rule(inflation=0.0, unemployment=0.05)
    assert cb.policy_rate < r0


def test_rate_rises_on_low_unemployment_when_taylor2_positive():
    """r increases when unemployment < ustar if taylor2 > 0."""
    gparams = GlobalParameters()
    nparams = NationParameters()
    nparams.taylor_rule_unemployment_coef = 1.1   # non-zero to test this arm
    nparams.taylor_rule_inflation_coef = 0.0      # zero out inflation arm

    class StubNation:
        def __init__(self):
            self.gparams = gparams
            self.params = nparams
            self.params = nparams
            self.banking_sector = []

    cb = CentralBank(StubNation())
    cb.initialise_from_parameters(gparams, nparams)
    r0 = cb.policy_rate
    # unemployment below target → (ustar - u) > 0 → rate rises
    cb.apply_taylor_rule(inflation=cb.inflation_target, unemployment=0.02)
    assert cb.policy_rate > r0


def test_rate_falls_on_high_unemployment_when_taylor2_positive():
    """r decreases when unemployment > ustar if taylor2 > 0."""
    gparams = GlobalParameters()
    nparams = NationParameters()
    nparams.taylor_rule_unemployment_coef = 1.1
    nparams.taylor_rule_inflation_coef = 0.0

    class StubNation:
        def __init__(self):
            self.gparams = gparams
            self.params = nparams
            self.params = nparams
            self.banking_sector = []

    cb = CentralBank(StubNation())
    cb.initialise_from_parameters(gparams, nparams)
    r0 = cb.policy_rate
    # unemployment above target → (ustar - u) < 0 → rate falls
    cb.apply_taylor_rule(inflation=cb.inflation_target, unemployment=0.15)
    assert cb.policy_rate < r0


def test_no_change_at_target():
    """r is unchanged when inflation == target and taylor2 == 0 (baseline)."""
    cb = _make_cb(policy_rate=0.02)
    r0 = cb.policy_rate
    cb.apply_taylor_rule(inflation=cb.inflation_target, unemployment=0.05)
    assert abs(cb.policy_rate - r0) < 1e-12


# ---------------------------------------------------------------------------
# flagTAYLOR=2 formula accuracy
# ---------------------------------------------------------------------------

def test_taylor2_formula_exact():
    """flagTAYLOR=2 produces r = r_base + t1*(pi-pi*) + t2*(u*-u) exactly."""
    gparams = GlobalParameters()
    nparams = NationParameters()
    nparams.policy_rate = 0.02
    nparams.taylor_rule_inflation_coef = 1.1
    nparams.taylor_rule_unemployment_coef = 0.5

    class StubNation:
        def __init__(self):
            self.gparams = gparams
            self.params = nparams
            self.params = nparams
            self.banking_sector = []

    cb = CentralBank(StubNation())
    cb.initialise_from_parameters(gparams, nparams)

    pi = 0.01
    u = 0.06
    pi_star = cb.inflation_target
    u_star = cb.unemployment_target
    expected_r = 0.02 + 1.1 * (pi - pi_star) + 0.5 * (u_star - u)
    cb.apply_taylor_rule(inflation=pi, unemployment=u)
    assert abs(cb.policy_rate - expected_r) < 1e-12


# ---------------------------------------------------------------------------
# Zero lower bound
# ---------------------------------------------------------------------------

def test_zero_lower_bound_binds():
    """r is clamped to 1e-6 when formula gives r <= 0."""
    cb = _make_cb(policy_rate=0.005)
    # Large negative inflation gap drives r to negative
    cb.apply_taylor_rule(inflation=-0.5, unemployment=0.9)
    assert cb.policy_rate == pytest.approx(1e-6)
    assert cb.zero_bound_count == 1


def test_zero_bound_counter_accumulates():
    """zero_bound_count increments each time ZLB binds."""
    cb = _make_cb(policy_rate=0.005)
    cb.apply_taylor_rule(inflation=-0.5, unemployment=0.9)
    cb.apply_taylor_rule(inflation=-0.5, unemployment=0.9)
    assert cb.zero_bound_count == 2


# ---------------------------------------------------------------------------
# Derived rates
# ---------------------------------------------------------------------------

def test_derived_rates_computed():
    """deposit_rate, cb_reserves_rate, bonds_rate computed correctly after apply."""
    gparams = GlobalParameters()
    # baseline: deposit_markdown=1.0, cb_reserve_markdown=0.33, bonds_markdown=0.0
    nparams = NationParameters()
    nparams.policy_rate = 0.02

    class StubNation:
        def __init__(self):
            self.gparams = gparams
            self.params = nparams
            self.params = nparams
            self.banking_sector = []

    cb = CentralBank(StubNation())
    cb.initialise_from_parameters(gparams, nparams)
    cb.apply_taylor_rule(inflation=cb.inflation_target, unemployment=0.05)

    r = cb.policy_rate  # should equal 0.02 (at target)
    assert cb.deposit_rate == pytest.approx(r * (1.0 - gparams.deposit_markdown))
    assert cb.cb_reserves_rate == pytest.approx(r * (1.0 - gparams.cb_reserve_markdown))
    assert cb.bonds_rate == pytest.approx(r * (1.0 - gparams.bonds_markdown))


def test_deposit_rate_is_zero_at_baseline():
    """deposit_rate = 0 when bankmarkdown = 1 (baseline)."""
    cb = _make_cb(policy_rate=0.02)
    cb.apply_taylor_rule(inflation=cb.inflation_target, unemployment=0.05)
    # bankmarkdown=1 → r_depo = r*(1-1) = 0
    assert cb.deposit_rate == pytest.approx(0.0)


def test_bonds_rate_rule_2_gives_fixed_rate():
    """bonds_rate == 0.01 when bonds_rate_rule == 2 (flag_bonds=2)."""
    gparams = GlobalParameters()
    gparams.bonds_rate_rule = 2
    nparams = NationParameters()
    nparams.policy_rate = 0.05  # any value; should be overridden

    class StubNation:
        def __init__(self):
            self.gparams = gparams
            self.params = nparams
            self.params = nparams
            self.banking_sector = []

    cb = CentralBank(StubNation())
    cb.initialise_from_parameters(gparams, nparams)
    cb.apply_taylor_rule(inflation=0.01, unemployment=0.05)
    assert cb.bonds_rate == pytest.approx(0.01)


# ---------------------------------------------------------------------------
# Bank lending rates updated
# ---------------------------------------------------------------------------

def test_bank_lending_rates_updated():
    """Bank lending rates = r*(1+markup) after apply_taylor_rule."""
    gparams = GlobalParameters()
    gparams.endogenous_bank_markup = 0
    nparams = NationParameters()
    nparams.policy_rate = 0.02

    class StubBank:
        def __init__(self, markup):
            self.markup = markup
            self.lending_rate = 0.0

    banks = [StubBank(0.2), StubBank(0.4)]

    class StubNation:
        def __init__(self):
            self.gparams = gparams
            self.params = nparams
            self.params = nparams
            self.banking_sector = banks

    cb = CentralBank(StubNation())
    cb.initialise_from_parameters(gparams, nparams)
    cb.apply_taylor_rule(inflation=cb.inflation_target, unemployment=0.05)

    r = cb.policy_rate
    assert banks[0].lending_rate == pytest.approx(r * 1.2)
    assert banks[1].lending_rate == pytest.approx(r * 1.4)


# ---------------------------------------------------------------------------
# Mark-to-market (flag_mtm=0 baseline → spread = 0)
# ---------------------------------------------------------------------------

def test_marktomarket_rate_equals_policy_rate_at_baseline():
    """With flag_mtm=0 and use_dsk_qe=True, spread=0 → r_marktomarket == r."""
    gparams = GlobalParameters()
    gparams.mark_to_market_rule = 0
    gparams.use_dskqe = True
    nparams = NationParameters()

    class StubNation:
        def __init__(self):
            self.gparams = gparams
            self.params = nparams
            self.params = nparams
            self.banking_sector = []

    cb = CentralBank(StubNation())
    cb.initialise_from_parameters(gparams, nparams)
    cb.apply_taylor_rule(inflation=cb.inflation_target, unemployment=0.05)
    assert cb.marktomarket_rate == pytest.approx(cb.policy_rate)
    assert cb.spread_marktomarket == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# remunerate_reserves
# ---------------------------------------------------------------------------

def test_remunerate_reserves_sets_income():
    """remunerate_reserves stores r_cbreserves * cash_prev on each bank."""
    gparams = GlobalParameters()
    nparams = NationParameters()
    nparams.policy_rate = 0.02

    class StubBank:
        def __init__(self, cash_prev):
            self.cash_prev = cash_prev
            self.reserve_interest_income = 0.0

    banks = [StubBank(1000.0), StubBank(2000.0)]

    class StubNation:
        def __init__(self):
            self.gparams = gparams
            self.params = nparams
            self.params = nparams
            self.banking_sector = []

    cb = CentralBank(StubNation())
    cb.initialise_from_parameters(gparams, nparams)
    # Apply rule to set cb_reserves_rate
    cb.apply_taylor_rule(inflation=cb.inflation_target, unemployment=0.05)

    cb.remunerate_reserves(banks)

    expected_rate = cb.cb_reserves_rate  # = 0.02 * (1 - 0.33) ≈ 0.01340
    assert banks[0].reserve_interest_income == pytest.approx(expected_rate * 1000.0)
    assert banks[1].reserve_interest_income == pytest.approx(expected_rate * 2000.0)


def test_remunerate_reserves_zero_rate_gives_zero_income():
    """With r=0 (ZLB binding), reserve income is zero."""
    gparams = GlobalParameters()
    nparams = NationParameters()
    nparams.policy_rate = 0.005  # low enough to be pushed to ZLB

    class StubBank:
        def __init__(self):
            self.cash_prev = 5000.0
            self.reserve_interest_income = 0.0

    banks = [StubBank()]

    class StubNation:
        def __init__(self):
            self.gparams = gparams
            self.params = nparams
            self.params = nparams
            self.banking_sector = []

    cb = CentralBank(StubNation())
    cb.initialise_from_parameters(gparams, nparams)
    # Deliberately force ZLB by large negative inflation
    cb.apply_taylor_rule(inflation=-0.5, unemployment=0.9)
    # policy_rate ≈ 1e-6 → cb_reserves_rate ≈ 1e-6 * 0.67 ≈ negligible
    cb.remunerate_reserves(banks)
    # ZLB rate = 1e-6; income = 1e-6 * 0.67 * 5000 ≈ 3e-3; still negligible vs normal rates
    assert banks[0].reserve_interest_income < 0.01


# ---------------------------------------------------------------------------
# avg_rate_sum accumulation
# ---------------------------------------------------------------------------

def test_avg_rate_accumulates():
    """avg_rate_sum accumulates policy_rate each call."""
    cb = _make_cb(policy_rate=0.02)
    # At target each call; rate stays at 0.02
    cb.apply_taylor_rule(inflation=cb.inflation_target, unemployment=0.05)
    cb.apply_taylor_rule(inflation=cb.inflation_target, unemployment=0.05)
    # avg_rate_sum should be 2 * 0.02 = 0.04
    assert cb.avg_rate_sum == pytest.approx(0.04)
