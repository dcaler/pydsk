"""Integration tests for Task 2.5 — Bond market (BONDS_DEMAND).

Acceptance criteria (IMPLEMENTATION_PLAN.md):
    - bond supply = bond demand by banks + bonds held by CB
    - share allocation respects `varphi`

This exercises:
    BankingSector.compute_bonds_demand()  — ports C++ BONDS_DEMAND (dsk_main.cpp:1010)
    CentralBank.buy_residual_bonds()      — CB as residual buyer (dskQE)
    Government.compute_budget()            — the bond-issuance side, both
                                            flag_portfolioallocation branches
"""
from __future__ import annotations

import numpy as np
import pytest

from dsk.agents.bank import Bank
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
    nation = Nation("bonds-test", params=nparams)
    nation.rng = np.random.default_rng(seed)
    nation.initialise_from_parameters(gparams, nparams)
    return nation


def _make_banks(nation: Nation, basel: list[float]) -> list[Bank]:
    """Fresh active banks with the given Basel credit ceilings."""
    banks = []
    for bc in basel:
        bank = Bank(nation, nation.rng)
        bank.is_active = True
        bank.basel_credit = bc
        bank.market_share = 1.0 / len(basel)
        banks.append(bank)
    return banks


# ---------------------------------------------------------------------------
# BONDS_DEMAND — BankingSector.compute_bonds_demand
# ---------------------------------------------------------------------------

class TestComputeBondsDemand:
    """Port of C++ BONDS_DEMAND() — the credit/bonds split."""

    def test_baseline_no_portfolio_allocation(self):
        """flag_portfolioallocation=0: bonds_demand=0, credit_supply=basel_credit."""
        nation = _build_nation()
        gparams = nation.gparams
        gparams.bonds_portfolio_allocation = 0
        gparams.bonds_share_of_credit = 0.0

        banks = _make_banks(nation, [100.0, 200.0, 300.0])
        sector = nation.banking_sector
        sector._agents = banks  # swap in the controlled banks

        sector.compute_bonds_demand(gparams)

        for bank in banks:
            assert bank.bonds_demand == 0.0
            assert bank.credit_supply == bank.basel_credit
            assert bank.bonds_demand_share == 0.0
        assert sector.bonds_demand_total == 0.0

    def test_portfolio_allocation_respects_varphi(self):
        """flag_portfolioallocation=1: bonds_demand = varphi * BaselBankCredit.

        This is the "share allocation respects varphi" acceptance criterion.
        """
        nation = _build_nation()
        gparams = nation.gparams
        gparams.bonds_portfolio_allocation = 1
        varphi = 0.25
        gparams.bonds_share_of_credit = varphi

        basel = [100.0, 200.0, 300.0]
        banks = _make_banks(nation, basel)
        sector = nation.banking_sector
        sector._agents = banks

        sector.compute_bonds_demand(gparams)

        for bank, bc in zip(banks, basel):
            assert bank.bonds_demand == pytest.approx(varphi * bc)
            # CreditSupply = BaselBankCredit - bonds_demand = (1-varphi)*BaselBankCredit
            assert bank.credit_supply == pytest.approx((1.0 - varphi) * bc)

        # Total demand and per-bank shares
        assert sector.bonds_demand_total == pytest.approx(varphi * sum(basel))
        share_sum = sum(b.bonds_demand_share for b in banks)
        assert share_sum == pytest.approx(1.0)
        for bank, bc in zip(banks, basel):
            assert bank.bonds_demand_share == pytest.approx(bc / sum(basel))

    def test_nation_wrapper_gated_on_dskqe(self):
        """Nation.compute_bonds_demand is a no-op when use_dskqe=0."""
        nation = _build_nation()
        gparams = nation.gparams
        gparams.use_dskqe = 0
        gparams.bonds_portfolio_allocation = 1
        gparams.bonds_share_of_credit = 0.5

        banks = _make_banks(nation, [100.0, 200.0])
        for bank in banks:
            bank.bonds_demand = -999.0  # sentinel
        nation.banking_sector._agents = banks

        nation.compute_bonds_demand()  # gated → should not touch banks

        for bank in banks:
            assert bank.bonds_demand == -999.0


# ---------------------------------------------------------------------------
# CentralBank.buy_residual_bonds
# ---------------------------------------------------------------------------

class TestCentralBankResidual:

    def test_residual_added_to_holdings(self):
        nation = _build_nation()
        cb = nation.central_bank
        cb.bonds_held = 0.0

        cb.buy_residual_bonds(residual=150.0, deficit=600.0)

        assert cb.bonds_held == pytest.approx(150.0)
        assert cb.cb_bonds_share == pytest.approx(150.0 / 600.0)
        assert cb.count_share_def == 1

    def test_residual_accumulates(self):
        nation = _build_nation()
        cb = nation.central_bank
        cb.bonds_held = 0.0
        cb.buy_residual_bonds(residual=100.0, deficit=400.0)
        cb.buy_residual_bonds(residual=50.0, deficit=200.0)
        assert cb.bonds_held == pytest.approx(150.0)
        assert cb.count_share_def == 2

    def test_negative_residual_clamped(self):
        nation = _build_nation()
        cb = nation.central_bank
        cb.bonds_held = 0.0
        cb.buy_residual_bonds(residual=-10.0, deficit=100.0)
        assert cb.bonds_held == 0.0

    def test_zero_deficit_no_share_update(self):
        nation = _build_nation()
        cb = nation.central_bank
        cb.bonds_held = 0.0
        cb.buy_residual_bonds(residual=0.0, deficit=0.0)
        assert cb.count_share_def == 0
        assert cb.cb_bonds_share == 0.0


# ---------------------------------------------------------------------------
# Bond-market clearing: supply = bank demand + CB residual
# ---------------------------------------------------------------------------

class TestBondMarketClearing:
    """Def (new bonds issued) = banks' purchases + CB residual purchase."""

    def test_clearing_with_scarce_bank_cash(self):
        """When banks lack cash, the CB absorbs the rest; market still clears."""
        nation = _build_nation()
        gov = nation.government
        gparams = nation.gparams
        cb = nation.central_bank
        cb.bonds_held = 0.0
        gparams.bonds_portfolio_allocation = 0

        # Two banks with high profits (large demand) but tiny cash → capped at cash
        banks = []
        for _ in range(2):
            bank = Bank(nation, nation.rng)
            bank.is_active = True
            bank.profits = 10_000.0
            bank.cash = 100.0
            bank.bonds_held = 0.0
            bank.deposits = 5000.0
            bank.equity = 1000.0
            bank.market_share = 0.5
            banks.append(bank)

        gov.debt = 0.0
        gov.compute_budget(
            t=2,
            labour_supply=1000.0,
            labour_demand=0.0,     # max unemployment → large G → large deficit
            wage=10.0,
            tax_previous_period=0.0,
            banks=banks,
        )

        Def = gov.deficit
        assert Def > 0.0
        # Banks could only spend their cash (100 each) on bonds
        assert gov.new_bonds == pytest.approx(200.0)
        # Residual went to the central bank
        assert gov.new_bonds_financed == pytest.approx(Def - 200.0)
        assert cb.bonds_held == pytest.approx(Def - 200.0)
        # Market clears: supply = bank demand + CB holding
        assert Def == pytest.approx(gov.new_bonds + cb.bonds_held)
        assert gov.bonds_supply_total == pytest.approx(Def)

    def test_clearing_identity_full_step(self):
        """Per-step identity Def == new_bonds + new_bonds_financed holds in a real step."""
        nation = _build_nation(seed=7)
        nation.production_phase(1)
        nation.dynamics_phase(1)
        nation.closeout_phase(1)

        nation.production_phase(2)
        nation.dynamics_phase(2)
        gov = nation.government
        if gov.deficit > 0.0:
            assert gov.deficit == pytest.approx(
                gov.new_bonds + gov.new_bonds_financed, rel=1e-9, abs=1e-6
            )

    def test_portfolio_allocation_clearing(self):
        """flag_portfolioallocation=1: banks buy varphi-based demand, CB takes residual."""
        nation = _build_nation()
        gov = nation.government
        gparams = nation.gparams
        cb = nation.central_bank
        cb.bonds_held = 0.0
        gparams.bonds_portfolio_allocation = 1
        varphi = 0.1
        gparams.bonds_share_of_credit = varphi

        basel = [100.0, 100.0]
        banks = _make_banks(nation, basel)
        for bank in banks:
            bank.profits = 1.0  # small positive so total_net_profit > 0
            bank.cash = 1e6
            bank.bonds_held = 0.0
        nation.banking_sector._agents = banks

        # Pre-compute bonds demand (production phase analogue)
        nation.banking_sector.compute_bonds_demand(gparams)
        bonds_dem_tot = nation.banking_sector.bonds_demand_total
        assert bonds_dem_tot == pytest.approx(varphi * sum(basel))

        gov.debt = 0.0
        gov.compute_budget(
            t=2,
            labour_supply=1000.0,
            labour_demand=0.0,
            wage=10.0,
            tax_previous_period=0.0,
            banks=banks,
        )

        Def = gov.deficit
        assert Def > 0.0
        # Total demand (varphi*sum(basel)) << Def, so each bank takes its full demand
        assert gov.new_bonds == pytest.approx(bonds_dem_tot)
        for bank, bc in zip(banks, basel):
            assert bank.bonds_held == pytest.approx(varphi * bc)
        # CB absorbs the (large) residual; market clears
        assert Def == pytest.approx(gov.new_bonds + cb.bonds_held)
