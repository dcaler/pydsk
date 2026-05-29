"""National accounts — stock-flow consistency checks for the nation.

Provides two per-step invariants over the agents of a `Nation`:

1. ``check_real_flows(tol)`` — production = consumption + investment + ΔN + G
   in real units, expressed at current prices for tolerance comparison.

2. ``check_balance_sheet(tol)`` — for every bank,
   ``assets (cash + loans + bonds) = liabilities (deposits) + equity``.
   The C++ baseline enforces this by setting ``BankDeposits`` as the residual
   plug in ALLOCATECREDIT (`dsk_main.cpp:4436`); we replicate the identity at
   `Nation.allocate_credit_to_demand` (`nation.py:647`) and check the residual.

Both methods leave the magnitude of the last residual on
``self.last_real_flow_residual`` / ``self.last_balance_sheet_residual``
for diagnostic comparison after a failed check.

References
----------
- Per-firm sector-2 inventory identity (exact by construction in PROFIT):
    ``Q2(j) + N_prev(j) = actual_cons(j) + N_new(j)``  →
    ``Q2(j) = actual_cons(j) + (N_new(j) - N_prev(j))``
- Per-firm sector-1 closure (exact by construction in PRODMACH, modulo
  floor()-rounding from labour rationing): ``Q1(i) = D1(i)``.
- Bank identity: see `dsk_main.cpp:4436` and `nation.py:647`.
- Government spending on goods in M1 baseline (`flagC=2`) is identically zero;
  the only G is the unemployment transfer to households, which folds into
  household consumption budget `Cons` rather than appearing as a direct
  goods purchase. The G term is therefore included for forward compatibility
  but resolves to 0 here.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dsk.nation import Nation


class NationalAccounts:
    """Per-nation balance-sheet and flow ledger; exposes SFC consistency checks."""

    def __init__(self, nation: "Nation") -> None:
        self.nation = nation
        # Residuals recorded by the most recent check, for diagnostic readout.
        self.last_real_flow_residual: float = 0.0
        self.last_real_flow_s2_residual: float = 0.0
        self.last_real_flow_s1_residual: float = 0.0
        self.last_balance_sheet_residual: float = 0.0
        self.last_bank_residuals: dict = {}  # bank unique_id → residual

    # ------------------------------------------------------------------
    # Real-flow identity: production = consumption + investment + ΔN + G
    # ------------------------------------------------------------------

    def check_real_flows(self, tol: float = 1e-6) -> bool:
        """Production = consumption + investment + Δinventory + government spending.

        Evaluated using the pre-ENTRYEXIT snapshot of per-period flows that
        ``Nation.realise_profits_and_taxes`` writes to the Nation aggregates.
        This is the only consistent reference: ENTRYEXIT replaces dead firms
        in-place with copies of incumbents, after which a firm-level scan of
        ``firm.production`` etc. double-counts.

        Identity (real units, per-firm sums):
            Σ Q2 - Σ actual_cons - Σ (N_new - N_prev) ≈ 0      (sector 2)
            Σ Q1 - Σ machine_units_invested ≈ 0                 (sector 1)
            G_goods = 0 in M1 baseline (flagC=2 transfer-only)

        Tolerance is interpreted in NOMINAL units. We translate the real
        residual into a nominal-comparable value using the current CPI for
        the sector-2 component and a unit price for sector-1 (since
        ``total_real_investment_machines == total_production_s1_real`` by
        construction, the sector-1 residual is always 0 — no nominal
        rescaling needed).

        Parameters
        ----------
        tol : float, default 1e-6
            Absolute tolerance, in the same units as
            ``nation.gdp_nominal`` (callers typically pass
            ``1e-6 * max(gdp_nominal, 1)``).

        Returns
        -------
        bool
            True iff the absolute aggregate residual is ≤ ``tol``.
        """
        nation = self.nation

        # ── Sector-2 identity (in real units) ─────────────────────────
        s2_residual_real = (
            nation.total_production_s2_real
            - nation.total_real_consumption
            - nation.total_real_inventory_change
        )

        # ── Sector-1 identity (in real units; exact by construction) ──
        s1_residual_real = (
            nation.total_production_s1_real
            - nation.total_real_investment_machines
        )

        # ── Government on-goods spending (zero in M1 baseline) ────────
        g_goods = 0.0

        # ── Combine into nominal residual ─────────────────────────────
        cpi = nation.cpi if nation.cpi > 0.0 else 1.0
        # Sector-1 closure is identity in real units; use ppi for symmetry
        # so the residual scales like nominal currency.
        ppi = nation.ppi if nation.ppi > 0.0 else 1.0
        residual_nominal = s2_residual_real * cpi + s1_residual_real * ppi - g_goods

        self.last_real_flow_s2_residual = s2_residual_real
        self.last_real_flow_s1_residual = s1_residual_real
        self.last_real_flow_residual = residual_nominal
        return abs(residual_nominal) <= tol

    # ------------------------------------------------------------------
    # Balance-sheet identity: assets = liabilities + equity, per bank
    # ------------------------------------------------------------------

    def check_balance_sheet(self, tol: float = 1e-6) -> bool:
        """Per-bank ``assets = liabilities + equity`` across the banking sector.

        For each active bank:

            cash + total_loans_s2 + total_loans_s1 + bonds_held
                = deposits + equity                                     (1)

        The C++ baseline enforces (1) by setting ``BankDeposits`` as the
        residual plug in ALLOCATECREDIT (`dsk_main.cpp:4436`). Our
        ``Nation.allocate_credit_to_demand`` does the same at
        ``nation.py:647``. After PROFIT and ENTRYEXIT none of the four bank
        balance-sheet fields are mutated in M1 (the BANKING and BAILOUT
        update routines are stubs until Task 2.4), so the identity holds at
        any point post-ALLOCATECREDIT within a step.

        Tolerance scales to the absolute size of bank equity (or 1, whichever
        is larger) so that the check is meaningful on both an empty and
        full-sized economy.

        Parameters
        ----------
        tol : float, default 1e-6
            Relative tolerance against the equity scale.

        Returns
        -------
        bool
            True iff every active bank satisfies (1) within ``tol``.
        """
        nation = self.nation
        banks = list(nation.banking_sector)

        max_residual = 0.0
        equity_scale = 0.0
        residuals: dict = {}

        for bank in banks:
            if not bank.is_active:
                continue
            assets = (
                bank.cash
                + bank.total_loans_s2
                + bank.total_loans_s1
                + bank.bonds_held
            )
            liabilities_plus_equity = bank.deposits + bank.equity
            residual = assets - liabilities_plus_equity

            residuals[bank.unique_id] = residual
            abs_r = abs(residual)
            if abs_r > max_residual:
                max_residual = abs_r

            # Track the largest bank equity for scaling.
            if abs(bank.equity) > equity_scale:
                equity_scale = abs(bank.equity)

        self.last_bank_residuals = residuals
        self.last_balance_sheet_residual = max_residual

        scale = max(1.0, equity_scale)
        return max_residual <= tol * scale
