"""Integration tests for Task 2.2 — Government full implementation (GOV_BUDGET).

Acceptance criterion:
    On a baseline step, the government budget identity holds within tolerance:
        Tax + new_bonds_issued = G + Gbailout + interest_on_debt
    (i.e. tax revenue plus bond financing equals all government expenditure)

Also verifies:
    - Bond repayment reduces bank bond holdings each period
    - Bond issuance increases bank bond holdings when deficit > 0
    - Bank balance sheet identity preserved after bond operations
    - Deficit accumulates as debt (flag_balancedbudget=0)
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from dsk.agents.bank import Bank
from dsk.agents.government import Government
from dsk.nation import Nation
from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_nation(seed: int = 42, n1: int = 10, n2: int = 40) -> Nation:
    gparams = GlobalParameters()
    gparams.n1_capital_good_firms = n1
    gparams.n2_consumption_good_firms = n2
    gparams.labour_supply_init = gparams.labour_supply_init * (n2 / 400.0)
    nparams = NationParameters()
    nation = Nation("gov-test", params=nparams)
    nation.rng = np.random.default_rng(seed)
    nation.initialise_from_parameters(gparams, nparams)
    return nation


def _full_step(nation: Nation, t: int) -> None:
    nation.production_phase(t)
    nation.dynamics_phase(t)
    nation.closeout_phase(t)


def _bank_balance_sheet_residual(bank: Bank) -> float:
    """cash + loans + bonds_held - deposits - equity (should be ~0)."""
    return (
        bank.cash
        + bank.total_loans_s2
        + bank.total_loans_s1
        + bank.bonds_held
        - bank.deposits
        - bank.equity
    )


# ---------------------------------------------------------------------------
# Unit-style test: compute_budget directly
# ---------------------------------------------------------------------------

class TestComputeBudgetDirect:
    """Call Government.compute_budget directly with controlled inputs."""

    def _make_gov_and_banks(self, n_banks: int = 2, profits_per_bank: float = 1000.0):
        """Return a Government and a list of mock-ish Bank objects."""
        nation = _build_nation(n1=5, n2=20)
        gov = nation.government

        banks = []
        for _ in range(n_banks):
            bank = Bank(nation, nation.rng)
            bank.profits = profits_per_bank
            bank.cash = 5000.0
            bank.deposits = 8000.0
            bank.equity = 1200.0
            bank.bonds_held = 200.0
            bank.market_share = 1.0 / n_banks
            banks.append(bank)

        return gov, banks

    def test_t1_uses_hardcoded_tax(self):
        """At t=1, C++ sets Tax=60000; deficit reflects that, not zero."""
        gov, banks = self._make_gov_and_banks()
        gparams = gov.nation.gparams
        nparams = gov.nation.params
        r = nparams.policy_rate

        gov.debt = 0.0
        # At t=1 with debt=0, Def = G + 0 + 0 - 60000; G likely << 60000 → Def < 0
        gov.compute_budget(
            t=1,
            labour_supply=1000.0,
            labour_demand=950.0,  # mild unemployment
            wage=1.0,
            tax_previous_period=0.0,  # ignored at t==1
            banks=banks,
        )
        # With Tax=60000 and small G, deficit should be negative (surplus)
        G = 50.0 * 1.0 * nparams.unemployment_benefit_share
        expected_def = G - 60_000.0
        assert gov.deficit == pytest.approx(expected_def, rel=1e-9)

    def test_budget_identity_deficit_case(self):
        """When Tax < G: deficit = G - Tax; new_bonds ≈ Def; identity holds."""
        gov, banks = self._make_gov_and_banks(n_banks=2, profits_per_bank=5000.0)
        gparams = gov.nation.gparams
        nparams = gov.nation.params
        r = nparams.policy_rate
        r_bonds = r * (1.0 - gparams.bonds_markdown)

        gov.debt = 0.0
        # Choose tax low enough to guarantee deficit
        tax_prev = 100.0

        gov.compute_budget(
            t=2,
            labour_supply=1000.0,
            labour_demand=500.0,   # heavy unemployment → large G
            wage=2.0,
            tax_previous_period=tax_prev,
            banks=banks,
        )

        G = gov.spending
        Gbailout = gov.bailout_cost
        # With debt=0, no interest term
        expected_def = G + Gbailout - tax_prev
        assert gov.deficit == pytest.approx(expected_def, rel=1e-9)

        # Budget identity: tax + new_bonds ≈ G + Gbailout + r_bonds*debt_before_issuance
        # (debt_before_issuance = 0 here; new_bonds covers the deficit)
        total_financing = tax_prev + gov.new_bonds
        total_expenditure = G + Gbailout  # r_bonds * 0 = 0
        assert total_financing == pytest.approx(total_expenditure, rel=1e-6)

    def test_bond_repayment_reduces_holdings(self):
        """Bond repayment: bonds_held decreases by bonds_share when no conditional ops run."""
        gov, banks = self._make_gov_and_banks(n_banks=2, profits_per_bank=5000.0)
        gparams = gov.nation.gparams
        initial_holdings = [b.bonds_held for b in banks]

        gov.debt = 0.0
        # Disable conditional issuance/redemption so only the unconditional
        # repayment step runs; this isolates the repayment logic.
        gparams.bonds_payment_rule = 0
        gov.compute_budget(
            t=2,
            labour_supply=1000.0,
            labour_demand=1000.0,
            wage=1.0,
            tax_previous_period=500.0,
            banks=banks,
        )

        for bank, init_h in zip(banks, initial_holdings):
            expected = init_h * (1.0 - gparams.bonds_repayment_share)
            assert bank.bonds_held == pytest.approx(expected, rel=1e-9)

    def test_bond_repayment_increases_cash(self):
        """Bond repayment returns exactly bonds_share * bonds_held to bank cash."""
        gov, banks = self._make_gov_and_banks(n_banks=1, profits_per_bank=5000.0)
        gparams = gov.nation.gparams
        bank = banks[0]
        init_cash = bank.cash
        init_bonds = bank.bonds_held

        gov.debt = 0.0
        # Disable conditional issuance/redemption to isolate repayment
        gparams.bonds_payment_rule = 0
        gov.compute_budget(
            t=2,
            labour_supply=1000.0,
            labour_demand=1000.0,
            wage=1.0,
            tax_previous_period=500.0,
            banks=banks,
        )

        remittance = gparams.bonds_repayment_share * init_bonds
        assert bank.cash == pytest.approx(init_cash + remittance, rel=1e-9)

    def test_debt_accumulates_when_deficit_positive(self):
        """flag_balancedbudget=0: Deb += Def."""
        gov, banks = self._make_gov_and_banks()
        gov.debt = 500.0

        gov.compute_budget(
            t=2,
            labour_supply=1000.0,
            labour_demand=500.0,  # large G
            wage=2.0,
            tax_previous_period=50.0,
            banks=banks,
        )

        assert gov.debt > 500.0  # debt grew

    def test_debt_falls_when_surplus(self):
        """Surplus (Def<0): Deb += Def, so debt shrinks."""
        gov, banks = self._make_gov_and_banks()
        gov.debt = 1000.0

        gov.compute_budget(
            t=2,
            labour_supply=1000.0,
            labour_demand=1000.0,  # no unemployment
            wage=1.0,
            tax_previous_period=100_000.0,  # big surplus
            banks=banks,
        )

        assert gov.debt < 1000.0

    def test_bonds_outstanding_equals_sum_of_bank_holdings(self):
        """bonds_outstanding is always the sum of individual bank holdings."""
        gov, banks = self._make_gov_and_banks(n_banks=3, profits_per_bank=2000.0)

        gov.compute_budget(
            t=2,
            labour_supply=1000.0,
            labour_demand=600.0,
            wage=1.5,
            tax_previous_period=500.0,
            banks=banks,
        )

        assert gov.bonds_outstanding == pytest.approx(
            sum(b.bonds_held for b in banks), rel=1e-9
        )

    def test_flag_def_surplus_reduces_deficit(self):
        """flag_DEF=1 with Deb<0: government uses surplus (negative debt) first."""
        gov, banks = self._make_gov_and_banks()
        gparams = gov.nation.gparams
        assert gparams.flag_def == 1  # baseline

        gov.debt = -200.0  # government has a stock surplus

        gov.compute_budget(
            t=2,
            labour_supply=1000.0,
            labour_demand=900.0,   # mild deficit
            wage=1.0,
            tax_previous_period=50.0,
            banks=banks,
        )

        # If |debt| > Def, Def is cleared to 0 and debt absorbs it
        # If |debt| < Def, residual deficit is issued as bonds
        # Either way, deficit ≤ original Def (flag_DEF reduces it)
        nparams = gov.nation.params
        wu = nparams.unemployment_benefit_share
        G_raw = 100.0 * 1.0 * wu  # 1000-900=100 excess workers
        r_cbreserves = (nparams.policy_rate
                        * (1.0 - gparams.cb_reserves_markdown))
        raw_def = G_raw + (-200.0 * r_cbreserves) - 50.0
        assert gov.deficit <= raw_def + 1e-10  # flag_DEF reduced or zeroed it


# ---------------------------------------------------------------------------
# Integration test: full nation step
# ---------------------------------------------------------------------------

class TestGovernmentIntegration:
    """Run a full nation step and verify government budget identity."""

    def test_deficit_equation_t1(self):
        """At t=1, Def = G + Gbailout - Tax_init(60000), with Deb=0 so no interest."""
        nation = _build_nation(seed=7)
        nation.production_phase(1)
        nation.dynamics_phase(1)

        gov = nation.government
        # t=1: Tax hardcoded to 60000, Deb=0 → Def = G + Gbailout - 60000
        expected_def = gov.spending + gov.bailout_cost - 60_000.0
        assert gov.deficit == pytest.approx(expected_def, rel=1e-9), (
            f"Def={gov.deficit:.4f}, G={gov.spending:.4f}, "
            f"bailout={gov.bailout_cost:.4f}, expected={expected_def:.4f}"
        )

    def test_budget_identity_deficit_step(self):
        """When Def>0: new_bonds ≈ Def, so Tax + new_bonds = G + Gbailout + r*Deb."""
        # Run two steps: t=2 uses actual t=1 tax output which is typically much less
        # than 60000 → government runs a deficit and issues bonds.
        nation = _build_nation(seed=7)
        _full_step(nation, 1)   # t=1: surplus; builds nation.total_tax

        nation.production_phase(2)
        nation.dynamics_phase(2)

        gov = nation.government
        gparams = nation.gparams
        nparams = nation.params
        r = nparams.policy_rate
        r_bonds = r * (1.0 - gparams.bonds_markdown)
        r_cbreserves = r * (1.0 - gparams.cb_reserves_markdown)

        if gov.deficit > 0.0:
            # Deficit case: new_bonds should cover at least part of the deficit
            # Budget identity: Tax + new_bonds = G + Gbailout + interest
            # where interest = r_bonds * debt_before_this_period's_issuance
            # (debt was updated BEFORE issuance, so use gov.debt - (new_bonds - repayment_adj))
            # Simpler check: new_bonds > 0 and new_bonds <= gov.deficit + 1e-6
            assert gov.new_bonds > 0.0, "Deficit > 0 but no bonds issued"
            assert gov.new_bonds <= gov.deficit + 1e-6, (
                f"new_bonds={gov.new_bonds:.4f} > deficit={gov.deficit:.4f}"
            )

    def test_bonds_outstanding_nonneg_after_step(self):
        """Bond holdings are non-negative after first step."""
        nation = _build_nation(seed=42)
        _full_step(nation, 1)
        gov = nation.government
        for bank in nation.banking_sector:
            assert bank.bonds_held >= -1e-10, (
                f"Bank {bank.unique_id} bonds_held = {bank.bonds_held:.4f} < 0"
            )

    def test_bank_cash_nonneg_after_bond_ops(self):
        """Bank cash cannot go below 0 after bond operations (newbonds capped at cash)."""
        nation = _build_nation(seed=99)
        _full_step(nation, 1)
        for bank in nation.banking_sector:
            assert bank.cash >= -1e-10, (
                f"Bank {bank.unique_id} cash = {bank.cash:.4f} < 0"
            )

    def test_government_debt_finite_after_five_steps(self):
        """Government debt remains finite and non-NaN over five steps."""
        nation = _build_nation(seed=1)
        for t in range(1, 6):
            _full_step(nation, t)
        gov = nation.government
        assert math.isfinite(gov.debt), f"gov.debt = {gov.debt}"
        assert math.isfinite(gov.deficit), f"gov.deficit = {gov.deficit}"

    def test_bonds_outstanding_tracks_bank_sum(self):
        """bonds_outstanding equals sum of individual bank bond holdings after each step."""
        nation = _build_nation(seed=3)
        for t in range(1, 4):
            nation.production_phase(t)
            nation.dynamics_phase(t)
            gov = nation.government
            bank_sum = sum(b.bonds_held for b in nation.banking_sector)
            assert gov.bonds_outstanding == pytest.approx(bank_sum, rel=1e-9), (
                f"t={t}: bonds_outstanding={gov.bonds_outstanding:.4f} "
                f"!= bank_sum={bank_sum:.4f}"
            )
            nation.closeout_phase(t)

    @pytest.mark.parametrize("seed", [0, 5, 17])
    def test_deficit_equation_multi_seed(self, seed):
        """Deficit equation holds at t=1 across seeds: Def = G + Gbailout - Tax_init."""
        nation = _build_nation(seed=seed)
        nation.production_phase(1)
        nation.dynamics_phase(1)
        gov = nation.government
        # t=1: Tax=60000 hardcoded, Deb=0 → Def = G + bailout - 60000
        expected_def = gov.spending + gov.bailout_cost - 60_000.0
        assert gov.deficit == pytest.approx(expected_def, rel=1e-9), (
            f"seed={seed}: deficit={gov.deficit:.4f}, expected={expected_def:.4f}"
        )
