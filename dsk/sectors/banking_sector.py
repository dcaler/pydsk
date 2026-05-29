"""Banking sector — AgentSet of Bank agents with aggregate helpers.

Mirrors C++ NB-indexed vectors: Bank_active, fB, NL, NbClient, BankMatch,
CreditSupplier, NWS2_rating.

Task 2.1: full multi-bank support with optional bounded-Pareto client
distribution (flag_pareto == 1, the baseline).
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from dsk.agent_set import AgentSet
from dsk.agents.bank import Bank

if TYPE_CHECKING:
    from dsk.nation import Nation
    from dsk.parameters.global_parameters import GlobalParameters
    from dsk.parameters.nation_parameters import NationParameters


class BankingSector(AgentSet):
    """Collection of Bank agents with banking-aggregate helpers."""

    # bonds_dem_tot — total bonds demanded by banks, set by compute_bonds_demand().
    # Class-level default so reads before the first BONDS_DEMAND call are safe.
    bonds_demand_total: float = 0.0

    # ------------------------------------------------------------------
    # Pareto helpers (C++ PARETO() and bpareto())
    # ------------------------------------------------------------------

    @staticmethod
    def _bounded_pareto_rv(
        rng: np.random.Generator, a: float, k: float, p: float
    ) -> int:
        """Single bounded Pareto integer draw via inverse CDF (C++ bpareto).

        C++ formula: rv = (k^a / (z*(k/p)^a - z + 1))^(1/a), then ceil.
        Rejects z == 0 or z == 1 (do-while in C++).
        """
        k_a = k ** a
        kp_a = (k / p) ** a
        while True:
            z = float(rng.uniform())
            if 0.0 < z < 1.0:
                break
        rv = (k_a / (z * kp_a - z + 1.0)) ** (1.0 / a)
        return int(math.ceil(rv))

    @staticmethod
    def _draw_pareto_nl(
        rng: np.random.Generator,
        nb: int,
        n2: int,
        a: float,
        k: float,
        p: float,
        max_attempts: int = 50_000,
    ) -> list:
        """Draw NB client-target integers via bounded Pareto rejection until sum == N2.

        C++ PARETO(): while (sum_NL != N2) { for i=1..NB: NL(i) = bpareto(...) }.
        Falls back to equal-split when N2 < NB * ceil(k) (geometrically impossible)
        or after max_attempts exhausted.
        """
        min_achievable = nb * int(math.ceil(k))
        if n2 < min_achievable:
            base = n2 // nb
            nl = [base] * nb
            nl[0] += n2 - base * nb
            return nl

        for _ in range(max_attempts):
            nl = [BankingSector._bounded_pareto_rv(rng, a, k, p) for _ in range(nb)]
            if sum(nl) == n2:
                return nl

        # Fallback: equal split (rarely reached in practice)
        base = n2 // nb
        nl = [base] * nb
        nl[0] += n2 - base * nb
        return nl

    # ------------------------------------------------------------------
    # Sector-level initialisation
    # ------------------------------------------------------------------

    def initialise_from_parameters(
        self,
        gparams: "GlobalParameters",
        nparams: "NationParameters",
        rng: np.random.Generator,
        nation: "Nation",
        consumption_firms: list,
    ) -> None:
        """Create NB banks, assign firms, initialise each bank.

        Implements C++ INITIALIZE lines 1283–1482:
        - fB = 1/NB (uniform market share, C++ line 1284)
        - NL targets: bounded Pareto if flag_pareto==1, else equal split
        - Random firm-to-bank matching (rejection draw until bank quota met)
        - Per-bank balance-sheet init (flagtotalcredit==2, Basel II)

        Parameters
        ----------
        gparams : GlobalParameters
        nparams : NationParameters
        rng : numpy Generator
            Nation-level RNG used for Pareto draws and random firm matching.
        nation : Nation
            Back-reference passed to new Bank agents.
        consumption_firms : list[ConsumptionGoodFirm]
            All N2 sector-2 firms (net_worth already set).
        """
        nb = nparams.n_banks
        n2 = len(consumption_firms)

        # --- Compute client-count targets NL(i) (C++ lines 1296–1318) ---
        if gparams.pareto_client_distribution == 1 and nb > 1:
            nl_targets = self._draw_pareto_nl(
                rng, nb, n2,
                gparams.pareto_alpha, gparams.pareto_k, gparams.pareto_p,
            )
        else:
            base = n2 // nb
            nl_targets = [base] * nb
            nl_targets[0] += n2 - base * nb  # remainder to bank 0

        # --- Create NB banks ---
        banks = []
        for _ in range(nb):
            bank = Bank(nation, rng)
            self.add(bank)
            banks.append(bank)

        # --- Uniform market shares: fB = 1/NB (C++ line 1284) ---
        for bank in banks:
            bank.market_share = 1.0 / nb

        for bank, nl in zip(banks, nl_targets):
            bank.n_clients_target = nl

        # --- Random firm-to-bank matching (C++ lines 1335–1362) ---
        # Each firm draws a random bank repeatedly until it lands on one with
        # remaining capacity (NbClient < NL).
        assigned_counts = [0] * nb
        for firm in consumption_firms:
            firm.bank_idx = None

        for firm in consumption_firms:
            while firm.bank_idx is None:
                candidate = int(rng.integers(nb))
                if assigned_counts[candidate] < nl_targets[candidate]:
                    firm.bank_idx = candidate
                    banks[candidate].firm_match.add(firm.unique_id)
                    assigned_counts[candidate] += 1

        # --- Initialise each bank with its assigned client portfolio ---
        for b_idx, bank in enumerate(banks):
            client_firms = [f for f in consumption_firms if f.bank_idx == b_idx]
            bank.n_active_clients = len(client_firms)
            bank.initialise_from_parameters(gparams, nparams, client_firms)

    # ------------------------------------------------------------------
    # Aggregate helpers
    # ------------------------------------------------------------------

    def compute_bonds_demand(self, gparams: "GlobalParameters") -> None:
        """Split each bank's Basel credit into bonds demand and loanable supply.

        Ports C++ BONDS_DEMAND() (dsk_main.cpp:1010-1050). Called after TOTCREDIT and
        before MAXCREDIT, only under dskQE (flag_dskQE==1). For each active bank, the
        Basel credit ceiling is split according to flag_portfolioallocation:

          0 (baseline): bonds_demand = 0; credit_supply = BaselBankCredit
          1           : bonds_demand = varphi*BaselBankCredit;
                        credit_supply = BaselBankCredit - bonds_demand

        Then total demand (bonds_dem_tot) and per-bank demand shares (bonds_dem_share)
        are computed. credit_supply here is the reported/diagnostic CreditSupply(j); the
        binding lending constraint downstream is BankCredit (bank.total_credit), which
        BONDS_DEMAND leaves untouched — matching the C++.
        """
        varphi = gparams.bonds_share_of_credit
        portfolio = gparams.bonds_portfolio_allocation
        active = [b for b in self if b.is_active]

        for bank in active:
            if portfolio == 0:
                bank.bonds_demand = 0.0
                bank.credit_supply = bank.basel_credit
            else:
                bank.bonds_demand = varphi * bank.basel_credit
                bank.credit_supply = bank.basel_credit - bank.bonds_demand
            # C++ emits an error if CreditSupply < 0 (varphi > 1) but does not clamp.

        total = sum(b.bonds_demand for b in active)
        self.bonds_demand_total = total
        for bank in active:
            bank.bonds_demand_share = (bank.bonds_demand / total) if total > 0.0 else 0.0

    def total_credit_supply(self) -> float:
        """Sum of credit_supply across all active banks."""
        return sum(b.credit_supply for b in self if b.is_active)

    def total_equity(self) -> float:
        """Sum of equity across all active banks (BankEquity_all)."""
        return sum(b.equity for b in self if b.is_active)

    def total_loans(self) -> float:
        """Sum of outstanding loans to s2 firms across all banks (Debtot2_all)."""
        return sum(b.total_loans_s2 for b in self if b.is_active)

    def bank_for_firm(self, firm_unique_id: int) -> "Bank":
        """Return the Bank that holds this firm as a client."""
        for bank in self:
            if firm_unique_id in bank.firm_match:
                return bank
        raise KeyError(f"No bank found for firm {firm_unique_id}")

    def bailout_failed_banks(
        self,
        gparams: "GlobalParameters",
        nparams: "NationParameters",
        rng: np.random.Generator,
    ) -> float:
        """Recapitalise failed banks via government bailout (flagbailout=0, BAILOUT).

        Implements C++ BAILOUT() in module_finance.cpp:210-570, flagbailout=0 branch.
        For each active bank with equity < 0:
          - If any bank has positive equity: new_equity = multip * min_positive_equity,
            floored at credit_multiplier * total_loans.
          - Fallback (all negative): new_equity = multip * equity_prev.
        Resets bonds to 0, cash = new_equity, clears cumulative_bad_debt by toxicap_G.

        Returns total government bailout cost (Gbailout_all).
        """
        active_banks = [b for b in self if b.is_active]
        gbailout_all = 0.0

        for bank in active_banks:
            if not bank.failed_this_period:
                continue

            # Collect current equities across all active banks
            equities = [b.equity for b in active_banks]
            max_eq = max(equities)

            if max_eq > 0.0:
                # Replace failed-bank entries with max_equity in temp array, find minimum
                eq_temp = [max_eq if e < 0.0 else e for e in equities]
                min_eq = min(eq_temp)

                multip = float(rng.uniform(
                    gparams.bailout_equity_multiplier_lower,
                    gparams.bailout_equity_multiplier_upper,
                ))
                old_equity = bank.equity
                new_equity = multip * min_eq

                # Basel floor: bank needs enough equity to cover its loans
                if new_equity < nparams.credit_multiplier * bank.total_loans_s2:
                    new_equity = nparams.credit_multiplier * bank.total_loans_s2

                bank.equity_prev = old_equity   # BankEquity(2,j) = old BankEquity(1,j)
                bank.equity = new_equity
                bank.bailout_cost = new_equity - old_equity
            else:
                # All banks have negative equity — fallback: fraction of previous equity
                multip = float(rng.uniform(
                    gparams.bailout_fallback_multiplier_lower,
                    gparams.bailout_fallback_multiplier_upper,
                ))
                old_equity = bank.equity
                bank.bailout_cost = -old_equity
                new_equity = multip * bank.equity_prev

                if new_equity < nparams.credit_multiplier * bank.total_loans_s2 or new_equity == 0.0:
                    new_equity = nparams.credit_multiplier * bank.total_loans_s2
                    bank.bailout_cost = new_equity

                bank.equity = new_equity

            # Reset balance sheet: bank starts from zero with new equity as cash
            bank.bonds_held = 0.0
            bank.bonds_held_nominal = 0.0
            bank.cash = bank.equity
            # BadDebttot(1,j) = (1-toxicap_G)*BadDebttot(1,j); toxicap_G=1 → 0
            bank.cumulative_bad_debt *= (1.0 - gparams.bailout_toxicap_share_govt)

            gbailout_all += bank.bailout_cost

        return gbailout_all
