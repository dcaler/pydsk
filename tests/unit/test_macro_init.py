"""Task 1.4 acceptance tests.

Verifies that Bank, Government, CentralBank, LabourMarket, and HouseholdSector
initialise to C++ baseline values (INITIALIZE, dsk_main.cpp:1043-1711).

Key C++ baseline checks (flagtotalcredit==2, NB=1, N2=400):
  - WtotClient2(1) = N2 * W20 = 400 * 1000 = 400,000
  - BankDeposits(1) = 400,000 / 0.08 = 5,000,000
  - BankEquity(1,1) = BankDeposits * initialbankequitymultiplier(=1) = 5,000,000
  - BaselBankCredit(1) = 5,000,000 / 0.08 = 62,500,000
  - Total firm debt (s1 + s2) = 0
  - LS = 500,000; w = 1.0
"""
from __future__ import annotations

import numpy as np
import pytest

from dsk.agents.bank import Bank
from dsk.agents.capital_good_firm import CapitalGoodFirm
from dsk.agents.central_bank import CentralBank
from dsk.agents.consumption_good_firm import ConsumptionGoodFirm
from dsk.agents.government import Government
from dsk.agents.household import HouseholdSector
from dsk.nation import Nation
from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters
from dsk.sectors.banking_sector import BankingSector
from dsk.sectors.labour_market import LabourMarket


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def gparams():
    return GlobalParameters()


@pytest.fixture
def nparams():
    return NationParameters()


@pytest.fixture
def nation(nparams):
    return Nation("test", nparams)


@pytest.fixture
def rng():
    return np.random.default_rng(42)


@pytest.fixture
def s2_firms(nation, rng, gparams, nparams):
    """N2 ConsumptionGoodFirms initialised with default parameters (bank_idx=0)."""
    firms = []
    counter = 0
    n1 = gparams.n1_capital_good_firms
    n2 = gparams.n2_consumption_good_firms
    for j in range(n2):
        f = ConsumptionGoodFirm(nation, rng)
        counter = f.initialise_from_parameters(
            gparams, nparams,
            preferred_supplier_idx=j % n1,
            bank_idx=0,
            machine_counter_start=counter,
        )
        firms.append(f)
    return firms


@pytest.fixture
def s1_firms(nation, rng, gparams):
    """N1 CapitalGoodFirms initialised with default parameters."""
    firms = []
    for _ in range(gparams.n1_capital_good_firms):
        f = CapitalGoodFirm(nation, rng)
        f.initialise_from_parameters(gparams)
        firms.append(f)
    return firms


@pytest.fixture
def single_bank(nation, rng, gparams, nparams, s2_firms):
    """One Bank initialised with all N2 s2 firms as clients (NB=1)."""
    bank = Bank(nation, rng)
    bank.initialise_from_parameters(gparams, nparams, s2_firms)
    return bank


# ---------------------------------------------------------------------------
# Bank equity tests
# ---------------------------------------------------------------------------

def test_bank_total_nw_from_clients(gparams, s2_firms):
    """WtotClient2 = sum of positive s2 net worths = N2 * W20."""
    expected = gparams.n2_consumption_good_firms * gparams.s2_net_worth_init
    actual = sum(f.net_worth for f in s2_firms if f.net_worth > 0.0)
    assert abs(actual - expected) < 1e-9, f"WtotClient2 mismatch: {actual} != {expected}"


def test_bank_deposits(gparams, nparams, single_bank):
    """BankDeposits = WtotClient2 / bankreserve_requirement_rate."""
    wtot = gparams.n2_consumption_good_firms * gparams.s2_net_worth_init
    expected_deposits = wtot / nparams.bank_reserve_requirement_rate
    assert abs(single_bank.deposits - expected_deposits) < 1e-9


def test_bank_equity_matches_cpp_baseline(gparams, nparams, single_bank):
    """BankEquity = BankDeposits * initialbankequitymultiplier.

    C++ INITIALIZE line 1429 (flagtotalcredit==2):
      BankEquity(1,j) = BankDeposits(j) * initialbankequitymultiplier
    Baseline: initialbankequitymultiplier = 1.0, so equity = deposits.
    """
    wtot = gparams.n2_consumption_good_firms * gparams.s2_net_worth_init
    expected_equity = (
        wtot / nparams.bank_reserve_requirement_rate
        * gparams.bank_equity_init_multiplier
    )
    assert abs(single_bank.equity - expected_equity) < 1e-9, (
        f"Bank equity {single_bank.equity:.1f} != expected {expected_equity:.1f}"
    )


def test_bank_cash_flagtotalcredit2(gparams, nparams, single_bank):
    """BankCash(1,j) = BankEquity(1,j) + BankDeposits(j) for flagtotalcredit==2."""
    expected_cash = single_bank.equity + single_bank.deposits
    assert abs(single_bank.cash - expected_cash) < 1e-9


def test_bank_multiplier_credit_zero(single_bank):
    """MultiplierBankCredit = 0 for flagtotalcredit==2 (Basel II mode)."""
    assert single_bank.multiplier_credit == 0.0


def test_bank_basel_credit(gparams, nparams, single_bank):
    """BaselBankCredit = BankEquity / credit_multiplier."""
    expected = single_bank.equity / nparams.credit_multiplier
    assert abs(single_bank.basel_credit - expected) < 1e-9


def test_bank_credit_supply_equals_basel_credit(single_bank):
    """CreditSupply = BaselBankCredit after initialisation (basiccreditrate=0)."""
    # credit_homogeneous_share = 0.0 → BasicCreditLines = 0 → total_credit unchanged
    assert abs(single_bank.credit_supply - single_bank.basel_credit) < 1e-9


def test_bank_basic_credit_lines_zero(gparams, nparams, s2_firms, single_bank):
    """BasicCreditLines2(i,j) = 0 when basiccreditrate (credit_homogeneous_share) = 0."""
    assert gparams.credit_homogeneous_share == 0.0
    for firm in s2_firms:
        assert single_bank.basic_credit_lines.get(firm.unique_id, 0.0) == 0.0


def test_bank_initial_loans_zero(single_bank):
    """BankDebt totals (Debtot1, Debtot2, bad debt, remittances) = 0 at init."""
    assert single_bank.total_loans_s1 == 0.0
    assert single_bank.total_loans_s2 == 0.0
    assert single_bank.total_bad_debt == 0.0
    assert single_bank.total_debt_remittances == 0.0


def test_bank_active(single_bank):
    """Bank_active = True at initialisation."""
    assert single_bank.is_active is True


def test_bank_markup_and_lending_rate(gparams, nparams, single_bank):
    """bankmarkup = bankmarkup_init; r_deb = r*(1+markup)."""
    assert abs(single_bank.markup - gparams.bank_markup_init) < 1e-12
    expected_rate = nparams.policy_rate * (1.0 + gparams.bank_markup_init)
    assert abs(single_bank.lending_rate - expected_rate) < 1e-12


def test_bank_all_s2_firms_matched(s2_firms, single_bank):
    """All N2 firms are matched to the single bank."""
    matched_ids = single_bank.firm_match
    for firm in s2_firms:
        assert firm.unique_id in matched_ids


def test_bank_ratings_initialised(s2_firms, single_bank):
    """NWS2_rating(j,1) = j (1-indexed rank) for all firms."""
    for rank, firm in enumerate(s2_firms, start=1):
        assert single_bank.firm_ratings.get(firm.unique_id) == rank


# ---------------------------------------------------------------------------
# Total firm debt
# ---------------------------------------------------------------------------

def test_total_firm_debt_zero(s1_firms, s2_firms):
    """Deb1=0 for all s1 firms; Deb2=0 for all s2 firms at initialisation."""
    s1_total_debt = sum(f.debt for f in s1_firms)
    s2_total_debt = sum(f.debt for f in s2_firms)
    assert s1_total_debt == 0.0, f"Sector-1 total debt = {s1_total_debt}, expected 0"
    assert s2_total_debt == 0.0, f"Sector-2 total debt = {s2_total_debt}, expected 0"
    assert s1_total_debt + s2_total_debt == 0.0


# ---------------------------------------------------------------------------
# Labour market
# ---------------------------------------------------------------------------

def test_labour_supply_matches_cpp(nation, gparams, nparams):
    """LS = LS0 = 500,000 at initialisation."""
    lm = LabourMarket(nation)
    lm.initialise_from_parameters(gparams, nparams)
    assert lm.labour_supply == gparams.labour_supply_init  # 500000.0


def test_wage_init(nation, gparams, nparams):
    """w = w0 = 1.0 at initialisation."""
    lm = LabourMarket(nation)
    lm.initialise_from_parameters(gparams, nparams)
    assert lm.wage == gparams.wage_init        # 1.0
    assert lm.wage_prev == gparams.wage_init   # 1.0


def test_unemployment_rate_init(nation, gparams, nparams):
    """C++ INITIALIZE at dsk_main.cpp:1237 sets U(2)=1 — a numerical pivot
    for the t=1 wage formula's d_U term, not "100% prior unemployment".
    See planningDocs/build_log.md entry "Wage init mismatch" for the
    diagnostic.  Python's aggregate_macro_indicators shifts
    `unemployment_rate_prev = unemployment_rate` *before* WAGE reads it,
    so we have to seed `unemployment_rate` to 1.0 (not `_prev`) — at
    t=1's MACRO the shift makes prev=1.0, then U(1) overwrites
    unemployment_rate."""
    lm = LabourMarket(nation)
    lm.initialise_from_parameters(gparams, nparams)
    assert lm.unemployment_rate == 1.0
    assert lm.unemployment_rate_prev == 1.0


# ---------------------------------------------------------------------------
# Government
# ---------------------------------------------------------------------------

def test_government_debt_zero(nation, gparams, nparams):
    """Deb = 0 at initialisation (C++ line 1547)."""
    gov = Government(nation)
    gov.initialise_from_parameters(gparams, nparams)
    assert gov.debt == 0.0


def test_government_spending_zero_baseline(nation, gparams, nparams):
    """G = 0 for flagC==2 baseline (C++ line 1495-1496: else G=0)."""
    gov = Government(nation)
    gov.initialise_from_parameters(gparams, nparams)
    assert gov.spending == 0.0


def test_government_carbon_taxes_zero(nation, gparams, nparams):
    """Carbon tax rates = 0 at initialisation (Claudia comment, C++ lines 1124-1130)."""
    gov = Government(nation)
    gov.initialise_from_parameters(gparams, nparams)
    assert gov.carbon_tax_rate_industry1 == 0.0
    assert gov.carbon_tax_rate_industry2 == 0.0
    assert gov.carbon_tax_rate_energy == 0.0


def test_government_wage_subsidies_zero(nation, gparams, nparams):
    """Subwage(1,2,3) = 0 at initialisation (C++ lines 1073-1074)."""
    gov = Government(nation)
    gov.initialise_from_parameters(gparams, nparams)
    assert gov.wage_subsidy == [0.0, 0.0, 0.0]


def test_government_bailout_zero(nation, gparams, nparams):
    """Gbailout = 0 at initialisation (C++ line 1255)."""
    gov = Government(nation)
    gov.initialise_from_parameters(gparams, nparams)
    assert gov.bailout_cost == 0.0
    assert gov.total_bailout == 0.0


# ---------------------------------------------------------------------------
# Central bank
# ---------------------------------------------------------------------------

def test_central_bank_policy_rate(nation, gparams, nparams):
    """CentralBank.policy_rate = NationParameters.policy_rate = 0.025."""
    cb = CentralBank(nation)
    cb.initialise_from_parameters(gparams, nparams)
    assert cb.policy_rate == nparams.policy_rate  # 0.025


def test_central_bank_spread_marktomarket(nation, gparams, nparams):
    """spread_marktomarket = 0.01 (C++ INITIALIZE line 1048)."""
    cb = CentralBank(nation)
    cb.initialise_from_parameters(gparams, nparams)
    assert abs(cb.spread_marktomarket - 0.01) < 1e-12


def test_central_bank_loans_zero(nation, gparams, nparams):
    """Loans_CB = 0 at initialisation."""
    cb = CentralBank(nation)
    cb.initialise_from_parameters(gparams, nparams)
    assert cb.loans_to_banks == 0.0


# ---------------------------------------------------------------------------
# Household sector
# ---------------------------------------------------------------------------

def test_household_income_zero_at_init(nation, gparams, nparams):
    """Household income/budget = 0 before any production step."""
    hs = HouseholdSector(nation)
    hs.initialise_from_parameters(gparams, nparams)
    assert hs.income == 0.0
    assert hs.consumption_budget == 0.0


def test_household_unemployment_benefit_share(nation, gparams, nparams):
    """wu cached on HouseholdSector matches NationParameters."""
    hs = HouseholdSector(nation)
    hs.initialise_from_parameters(gparams, nparams)
    assert hs.unemployment_benefit_share == nparams.unemployment_benefit_share  # 0.4


# ---------------------------------------------------------------------------
# BankingSector orchestration (NB = nparams.n_banks = 10)
# ---------------------------------------------------------------------------

def test_banking_sector_init_creates_nb_banks(nation, rng, gparams, nparams, s2_firms):
    """BankingSector.initialise_from_parameters creates exactly nparams.n_banks banks."""
    bs = BankingSector()
    bs.initialise_from_parameters(gparams, nparams, rng, nation, s2_firms)
    assert len(bs) == nparams.n_banks


def test_banking_sector_all_firms_assigned(nation, rng, gparams, nparams, s2_firms):
    """All N2 firms have bank_idx assigned after sector init."""
    bs = BankingSector()
    bs.initialise_from_parameters(gparams, nparams, rng, nation, s2_firms)
    for firm in s2_firms:
        assert firm.bank_idx is not None


def test_banking_sector_total_equity_matches_cpp(nation, rng, gparams, nparams, s2_firms):
    """Sector-level total equity matches single-bank direct init."""
    bs = BankingSector()
    bs.initialise_from_parameters(gparams, nparams, rng, nation, s2_firms)
    expected_equity = (
        gparams.n2_consumption_good_firms
        * gparams.s2_net_worth_init
        / nparams.bank_reserve_requirement_rate
        * gparams.bank_equity_init_multiplier
    )
    assert abs(bs.total_equity() - expected_equity) < 1e-9
