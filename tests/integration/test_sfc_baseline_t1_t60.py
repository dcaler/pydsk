"""Integration test for Task 1.17 — NationalAccounts stock-flow consistency.

Acceptance criterion from IMPLEMENTATION_PLAN:
    Both checks pass for the baseline run from t=1 to t=60 (spin-up period).

We run a single-nation model (modest-but-non-trivial N1=20, N2=80, NB=1) for
60 steps across multiple seeds, and verify both invariants per step:

    (a) check_real_flows(tol)      — per-period real-flow identity
    (b) check_balance_sheet(tol)   — per-bank assets = liabilities + equity

Both should hold by construction of PROFIT (real-flow identity is per-firm)
and ALLOCATECREDIT (deposits set as the residual plug in the bank balance).
The spin-up window (t=1..60) exercises the model under firm entry and exit,
which is the regime where stock/flow accounting bugs typically surface.
"""
from __future__ import annotations

import numpy as np
import pytest

from dsk.agents.capital_good_firm import CapitalGoodFirm
from dsk.agents.consumption_good_firm import ConsumptionGoodFirm
from dsk.nation import Nation
from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_nation(seed: int = 0, n1: int = 20, n2: int = 80) -> Nation:
    """Construct a fully-initialised single nation ready to run dynamics.

    Sizes are chosen to be representative without making the 60-step loop
    expensive: N1=20, N2=80 keeps the same N1:N2 ratio as the C++ baseline
    (1:4) and stresses entry/exit at a meaningful but tractable scale.
    """
    gparams = GlobalParameters()
    gparams.n1_capital_good_firms = n1
    gparams.n2_consumption_good_firms = n2
    nparams = NationParameters()

    nation = Nation("sfc-baseline", params=nparams)
    nation.gparams = gparams
    nation.rng = np.random.default_rng(seed)

    nation.labour_market.initialise_from_parameters(gparams, nparams)
    nation.central_bank.initialise_from_parameters(gparams, nparams)
    nation.household_sector.initialise_from_parameters(gparams, nparams)
    nation.government.initialise_from_parameters(gparams, nparams)

    for _ in range(n1):
        cf = CapitalGoodFirm(nation, nation.rng)
        cf.initialise_from_parameters(gparams)
        nation.capital_good_sector.add(cf)

    machine_counter = 0
    s2_firms = []
    for j in range(n2):
        f = ConsumptionGoodFirm(nation, nation.rng)
        machine_counter = f.initialise_from_parameters(
            gparams, nparams, j % n1, 0, machine_counter
        )
        nation.consumption_good_sector.add(f)
        s2_firms.append(f)

    nation.banking_sector.initialise_from_parameters(
        gparams, nparams, nation.rng, nation, s2_firms
    )

    return nation


def _run_one_step(nation: Nation, t: int) -> None:
    """Run production + dynamics for period t (no closeout / climate)."""
    nation.production_phase(t)
    nation.dynamics_phase(t)


# ---------------------------------------------------------------------------
# Acceptance tests — spin-up window
# ---------------------------------------------------------------------------

class TestSfcBaselineSpinUp:
    """Both SFC checks pass over the full spin-up t=1..60 across seeds."""

    @pytest.mark.parametrize("seed", [0, 1, 7, 42, 1337])
    def test_real_flows_pass_t1_to_t60(self, seed: int) -> None:
        nation = _build_nation(seed=seed)
        for t in range(1, 61):
            _run_one_step(nation, t)
            gdp_scale = max(1.0, abs(nation.gdp_nominal))
            tol = 1e-6 * gdp_scale
            ok = nation.accounting.check_real_flows(tol=tol)
            residual = nation.accounting.last_real_flow_residual
            assert ok, (
                f"check_real_flows FAILED at t={t}, seed={seed}: "
                f"residual={residual:.6g}, "
                f"s2_real={nation.accounting.last_real_flow_s2_residual:.6g}, "
                f"s1_real={nation.accounting.last_real_flow_s1_residual:.6g}, "
                f"gdp={gdp_scale:.6g}, tol={tol:.6g}"
            )

    @pytest.mark.parametrize("seed", [0, 1, 7, 42, 1337])
    def test_balance_sheet_passes_t1_to_t60(self, seed: int) -> None:
        nation = _build_nation(seed=seed)
        for t in range(1, 61):
            _run_one_step(nation, t)
            ok = nation.accounting.check_balance_sheet(tol=1e-6)
            residual = nation.accounting.last_balance_sheet_residual
            assert ok, (
                f"check_balance_sheet FAILED at t={t}, seed={seed}: "
                f"max_bank_residual={residual:.6g}, "
                f"per_bank={nation.accounting.last_bank_residuals}"
            )

    def test_both_checks_pass_under_closeout(self) -> None:
        """Identity must also hold after closeout_phase (UPDATE/SAVE)."""
        nation = _build_nation(seed=11)
        for t in range(1, 11):
            _run_one_step(nation, t)
            nation.closeout_phase(t)
            assert nation.accounting.check_real_flows(
                tol=1e-6 * max(1.0, abs(nation.gdp_nominal))
            ), (
                f"check_real_flows after closeout failed at t={t}: "
                f"residual={nation.accounting.last_real_flow_residual:.6g}"
            )
            assert nation.accounting.check_balance_sheet(tol=1e-6), (
                f"check_balance_sheet after closeout failed at t={t}: "
                f"residual={nation.accounting.last_balance_sheet_residual:.6g}"
            )


# ---------------------------------------------------------------------------
# Direct invariant tests
# ---------------------------------------------------------------------------

class TestRealFlowInvariants:
    """The real-flow identity should be exact (≈ 0) by construction each step."""

    def test_sector2_identity_per_period(self) -> None:
        """Q2 = actual_cons + ΔN per period across multiple periods."""
        nation = _build_nation(seed=3)
        for t in range(1, 21):
            _run_one_step(nation, t)
            s2_residual = (
                nation.total_production_s2_real
                - nation.total_real_consumption
                - nation.total_real_inventory_change
            )
            # The per-firm identity is exact; the aggregate residual should
            # be at most floating-point noise.
            scale = max(1.0, nation.total_production_s2_real)
            assert abs(s2_residual) <= 1e-9 * scale, (
                f"Sector-2 SFC identity broken at t={t}: residual={s2_residual:.6g}"
            )

    def test_sector1_identity_per_period(self) -> None:
        """Q1 = Σ machine_units_ordered per period — exact by construction."""
        nation = _build_nation(seed=4)
        for t in range(1, 21):
            _run_one_step(nation, t)
            s1_residual = (
                nation.total_production_s1_real
                - nation.total_real_investment_machines
            )
            # Both quantities are the same Nation aggregate (total_machine_units),
            # so this residual must be exactly 0.
            assert s1_residual == 0.0, (
                f"Sector-1 SFC identity broken at t={t}: residual={s1_residual:.6g}"
            )

    def test_residual_finite_each_step(self) -> None:
        """No NaN/inf in either residual under the baseline run."""
        nation = _build_nation(seed=5)
        for t in range(1, 16):
            _run_one_step(nation, t)
            nation.accounting.check_real_flows()
            nation.accounting.check_balance_sheet()
            assert np.isfinite(nation.accounting.last_real_flow_residual)
            assert np.isfinite(nation.accounting.last_balance_sheet_residual)


class TestBalanceSheetInvariants:
    """Each bank's stored balance sheet identity must hold each step."""

    def test_per_bank_assets_equal_liabilities_plus_equity(self) -> None:
        """For each bank: cash + loans + bonds = deposits + equity (exact-ish)."""
        nation = _build_nation(seed=6)
        for t in range(1, 21):
            _run_one_step(nation, t)
            for bank in nation.banking_sector:
                if not bank.is_active:
                    continue
                assets = (
                    bank.cash
                    + bank.total_loans_s2
                    + bank.total_loans_s1
                    + bank.bonds_held
                )
                lhs = bank.deposits + bank.equity
                # ALLOCATECREDIT pegs deposits as the residual plug; identity
                # is exact up to floating-point noise.
                scale = max(1.0, abs(bank.equity))
                assert abs(assets - lhs) <= 1e-9 * scale, (
                    f"Bank balance-sheet identity broken at t={t} "
                    f"bank.uid={bank.unique_id}: assets={assets:.6g}, "
                    f"liab+eq={lhs:.6g}"
                )

    def test_residuals_dict_populated_after_check(self) -> None:
        """check_balance_sheet should expose per-bank residuals for diagnostics."""
        nation = _build_nation(seed=8)
        _run_one_step(nation, t=1)
        nation.accounting.check_balance_sheet(tol=1e-6)
        residuals = nation.accounting.last_bank_residuals
        # NB=1 in M1, so exactly one entry
        active_banks = [b for b in nation.banking_sector if b.is_active]
        assert len(residuals) == len(active_banks)
        for bank in active_banks:
            assert bank.unique_id in residuals
            assert np.isfinite(residuals[bank.unique_id])


class TestRobustnessAcrossSeeds:
    """Spot-check across additional seeds, including extreme values."""

    @pytest.mark.parametrize("seed", [2**16 - 1, 2**20 + 17, 99999])
    def test_60_step_run_no_failures(self, seed: int) -> None:
        nation = _build_nation(seed=seed)
        for t in range(1, 61):
            _run_one_step(nation, t)
            gdp_scale = max(1.0, abs(nation.gdp_nominal))
            assert nation.accounting.check_real_flows(tol=1e-6 * gdp_scale)
            assert nation.accounting.check_balance_sheet(tol=1e-6)
