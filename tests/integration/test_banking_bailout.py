"""Integration tests for Task 2.4: BANKING and BAILOUT.

Acceptance criterion:
  - A deliberately stressed bank (large cumulative_bad_debt) fails and is bailed out
    with positive equity after bailout_failed_banks().
  - Healthy banks retain positive equity throughout.

C++ reference:
  - BANKING: module_finance.cpp:14-205
  - BAILOUT: module_finance.cpp:210-570, flagbailout=0 branch
"""
import numpy as np
import pytest

from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters
from dsk.agents.bank import Bank
from dsk.agents.central_bank import CentralBank
from dsk.sectors.banking_sector import BankingSector


# ---------------------------------------------------------------------------
# Minimal stub infrastructure
# ---------------------------------------------------------------------------

class StubFirm:
    """Mimics a ConsumptionGoodFirm for BANKING accumulation."""
    _id_counter = 0

    def __init__(self, debt=0.0, debt_interest=0.0, bad_debt=0.0, debt_remittance=0.0):
        StubFirm._id_counter += 1
        self.unique_id = StubFirm._id_counter
        self.debt = debt
        self.debt_interest = debt_interest
        self.bad_debt = bad_debt
        self.debt_remittance = debt_remittance
        self.net_worth = max(0.0, 1000.0 - debt)  # positive net worth
        self.is_alive = True


class StubS2Sector:
    """Thin iterable over a list of StubFirm."""
    def __init__(self, firms):
        self._firms = firms

    def __iter__(self):
        return iter(self._firms)


class StubNation:
    def __init__(self, gparams, nparams, banks, firms):
        self.gparams = gparams
        self.params = nparams
        self.banking_sector = banks
        self.consumption_good_sector = StubS2Sector(firms)
        self.central_bank = CentralBank(self)
        self.central_bank.initialise_from_parameters(gparams, nparams)
        self.central_bank.apply_taylor_rule(
            inflation=gparams.inflation_target,
            unemployment=gparams.unemployment_target,
        )


def _make_bank(nation, rng, equity=5000.0, deposits=10000.0, cash=None):
    bank = Bank(nation, rng)
    bank.equity = equity
    bank.equity_prev = equity
    bank.deposits = deposits
    bank.cash = (equity + deposits) if cash is None else cash
    bank.cash_prev = bank.cash
    bank.is_active = True
    bank.reserve_interest_income = 0.0
    bank.cumulative_bad_debt = 0.0
    bank.bonds_held = 0.0
    bank.bonds_held_nominal = 0.0
    bank.total_loans_s2 = 0.0
    bank.total_bad_debt = 0.0
    bank.total_debt_remittances = 0.0
    bank.total_debt_interest = 0.0
    bank.leverage = 0.0
    bank.profits = 0.0
    bank.dividends = 0.0
    bank.failed_this_period = False
    return bank


# ---------------------------------------------------------------------------
# BANKING: healthy bank — no bad debt, positive profit
# ---------------------------------------------------------------------------

def test_healthy_bank_has_positive_equity_after_banking():
    """Bank with no bad debt and positive interest income has equity > 0 after BANKING."""
    gparams = GlobalParameters()
    nparams = NationParameters()
    rng = np.random.default_rng(42)

    firm = StubFirm(debt=5000.0, debt_interest=250.0, bad_debt=0.0, debt_remittance=1650.0)
    nation = StubNation(gparams, nparams, [], [firm])

    bank = _make_bank(nation, rng, equity=5000.0, deposits=10000.0, cash=15000.0)
    bank.firm_match = {firm.unique_id}

    result = bank.compute_profit_and_dividend()

    assert bank.equity > 0.0
    assert result["profits"] > 0.0 or result["profits"] == pytest.approx(
        firm.debt_interest - bank.deposits * nation.central_bank.deposit_rate
        + bank.reserve_interest_income
    )


def test_banking_accumulates_debt_interest_and_bad_debt():
    """BANKING sums debt interest and bad debt across all client firms."""
    gparams = GlobalParameters()
    nparams = NationParameters()
    rng = np.random.default_rng(0)

    firms = [
        StubFirm(debt=2000.0, debt_interest=100.0, bad_debt=0.0, debt_remittance=660.0),
        StubFirm(debt=3000.0, debt_interest=150.0, bad_debt=500.0, debt_remittance=0.0),
    ]
    nation = StubNation(gparams, nparams, [], firms)
    bank = _make_bank(nation, rng, equity=8000.0, deposits=20000.0, cash=28000.0)
    bank.firm_match = {f.unique_id for f in firms}

    bank.compute_profit_and_dividend()

    assert bank.total_debt_interest == pytest.approx(250.0)
    assert bank.total_bad_debt == pytest.approx(500.0)
    assert bank.cumulative_bad_debt == pytest.approx(500.0)
    # Only non-bad-debt firms contribute to remittances
    assert bank.total_debt_remittances == pytest.approx(660.0)


def test_banking_cumulative_bad_debt_accumulates():
    """cumulative_bad_debt accumulates across successive BANKING calls."""
    gparams = GlobalParameters()
    nparams = NationParameters()
    rng = np.random.default_rng(1)

    firm = StubFirm(debt=1000.0, debt_interest=50.0, bad_debt=200.0)
    nation = StubNation(gparams, nparams, [], [firm])
    bank = _make_bank(nation, rng, equity=8000.0, deposits=20000.0, cash=28000.0)
    bank.firm_match = {firm.unique_id}

    bank.compute_profit_and_dividend()
    assert bank.cumulative_bad_debt == pytest.approx(200.0)

    # Simulate next period: same bad debt again
    firm.bad_debt = 150.0
    bank.compute_profit_and_dividend()
    assert bank.cumulative_bad_debt == pytest.approx(350.0)


# ---------------------------------------------------------------------------
# BANKING: stressed bank fails
# ---------------------------------------------------------------------------

def test_fail_if_insolvent_sets_flag():
    """Bank with equity < 0 is marked failed after fail_if_insolvent()."""
    gparams = GlobalParameters()
    nparams = NationParameters()
    rng = np.random.default_rng(2)

    # Bank with large bad debt → equity goes negative
    firm = StubFirm(debt=0.0, debt_interest=0.0, bad_debt=999999.0)
    nation = StubNation(gparams, nparams, [], [firm])
    bank = _make_bank(nation, rng, equity=100.0, deposits=1000.0, cash=1100.0)
    bank.firm_match = {firm.unique_id}
    # gamma_bd=1.0 → equity = cash + bonds - cumulative_bad_debt
    # With bad_debt=999999, equity will be hugely negative
    bank.compute_profit_and_dividend()
    assert bank.equity < 0.0

    bank.fail_if_insolvent()
    assert bank.failed_this_period is True


def test_healthy_bank_not_marked_failed():
    """Bank with positive equity is NOT marked as failed."""
    gparams = GlobalParameters()
    nparams = NationParameters()
    rng = np.random.default_rng(3)

    firm = StubFirm(debt=500.0, debt_interest=25.0)
    nation = StubNation(gparams, nparams, [], [firm])
    bank = _make_bank(nation, rng, equity=5000.0, deposits=10000.0, cash=15000.0)
    bank.firm_match = {firm.unique_id}

    bank.compute_profit_and_dividend()
    bank.fail_if_insolvent()
    assert bank.failed_this_period is False


# ---------------------------------------------------------------------------
# BAILOUT: failed bank rescued, healthy bank unaffected
# ---------------------------------------------------------------------------

def _setup_two_bank_scenario(stressed_equity=-500.0, healthy_equity=5000.0):
    """Create a 2-bank nation where bank[0] has failed and bank[1] is healthy."""
    gparams = GlobalParameters()
    nparams = NationParameters()
    rng = np.random.default_rng(7)

    sector = BankingSector()
    firms = [StubFirm()]
    nation = StubNation(gparams, nparams, sector, firms)
    nation.rng = rng

    stressed = _make_bank(nation, rng, equity=stressed_equity, deposits=5000.0,
                          cash=4500.0)
    stressed.equity_prev = 3000.0  # was positive last period
    stressed.total_loans_s2 = 100.0
    stressed.failed_this_period = True

    healthy = _make_bank(nation, rng, equity=healthy_equity, deposits=10000.0,
                         cash=15000.0)
    healthy.equity_prev = healthy_equity
    healthy.total_loans_s2 = 200.0
    healthy.failed_this_period = False

    sector.add(stressed)
    sector.add(healthy)
    nation.banking_sector = sector

    return gparams, nparams, rng, sector, stressed, healthy


def test_bailout_restores_positive_equity_to_failed_bank():
    """Failed bank has positive equity after bailout_failed_banks()."""
    gparams, nparams, rng, sector, stressed, healthy = _setup_two_bank_scenario()

    sector.bailout_failed_banks(gparams, nparams, rng)

    assert stressed.equity > 0.0


def test_bailout_does_not_change_healthy_bank_equity():
    """Healthy bank equity is unchanged by bailout_failed_banks()."""
    gparams, nparams, rng, sector, stressed, healthy = _setup_two_bank_scenario()
    eq_before = healthy.equity

    sector.bailout_failed_banks(gparams, nparams, rng)

    assert healthy.equity == eq_before


def test_bailout_zeroes_failed_bank_bonds_and_bad_debt():
    """After bailout, failed bank has bonds=0 and cumulative_bad_debt cleared."""
    gparams, nparams, rng, sector, stressed, healthy = _setup_two_bank_scenario()
    stressed.bonds_held = 1000.0
    stressed.cumulative_bad_debt = 3000.0

    sector.bailout_failed_banks(gparams, nparams, rng)

    assert stressed.bonds_held == pytest.approx(0.0)
    # toxicap_G=1.0 → cumulative_bad_debt = (1-1)*3000 = 0
    assert stressed.cumulative_bad_debt == pytest.approx(0.0)


def test_bailout_cash_equals_new_equity():
    """After bailout, failed bank cash == new equity (bank starts from zero)."""
    gparams, nparams, rng, sector, stressed, healthy = _setup_two_bank_scenario()

    sector.bailout_failed_banks(gparams, nparams, rng)

    assert stressed.cash == pytest.approx(stressed.equity)


def test_bailout_cost_positive():
    """Government bailout cost is positive (equity was negative, now positive)."""
    gparams, nparams, rng, sector, stressed, healthy = _setup_two_bank_scenario(
        stressed_equity=-800.0
    )
    sector.bailout_failed_banks(gparams, nparams, rng)

    assert stressed.bailout_cost > 0.0


def test_bailout_all_banks_negative_fallback():
    """When ALL banks have negative equity, fallback path uses equity_prev."""
    gparams = GlobalParameters()
    nparams = NationParameters()
    rng = np.random.default_rng(99)

    sector = BankingSector()
    firms = []
    nation = StubNation(gparams, nparams, sector, firms)

    bank = _make_bank(nation, rng, equity=-100.0, deposits=5000.0, cash=4900.0)
    bank.equity_prev = 2000.0   # was positive last period
    bank.total_loans_s2 = 0.0
    bank.failed_this_period = True
    sector.add(bank)

    sector.bailout_failed_banks(gparams, nparams, rng)

    assert bank.equity > 0.0
    assert bank.cash == pytest.approx(bank.equity)


# ---------------------------------------------------------------------------
# BANKING + BAILOUT end-to-end via Nation
# ---------------------------------------------------------------------------

def test_nation_update_and_bailout_pipeline():
    """Nation.update_banks() then bailout_failed_banks() leaves all banks solvent."""
    from dsk.nation import Nation

    gparams = GlobalParameters()
    gparams.n1_capital_good_firms = 2
    gparams.n2_consumption_good_firms = 4
    nparams = NationParameters()
    nparams.n_banks = 1

    nation = Nation("test", params=nparams)
    nation.rng = np.random.default_rng(42)
    nation.initialise_from_parameters(gparams, nparams)

    # Stress the single bank: inject large cumulative bad debt so equity < 0
    bank = list(nation.banking_sector)[0]
    bank.cumulative_bad_debt = bank.cash * 10.0  # guarantees negative equity

    # Run BANKING → BAILOUT
    nation.update_banks()
    nation.bailout_failed_banks()

    assert bank.equity > 0.0, f"Bank equity still negative: {bank.equity}"


def test_nation_healthy_run_no_bailout_needed():
    """In a normal period with no bad debt, no bailout is triggered."""
    from dsk.nation import Nation

    gparams = GlobalParameters()
    gparams.n1_capital_good_firms = 2
    gparams.n2_consumption_good_firms = 4
    nparams = NationParameters()
    nparams.n_banks = 1

    nation = Nation("test", params=nparams)
    nation.rng = np.random.default_rng(7)
    nation.initialise_from_parameters(gparams, nparams)

    bank = list(nation.banking_sector)[0]
    eq_before_banking = bank.equity

    nation.update_banks()
    nation.bailout_failed_banks()

    assert not bank.failed_this_period
    assert bank.equity > 0.0
    assert nation.government.bailout_cost == pytest.approx(0.0)
