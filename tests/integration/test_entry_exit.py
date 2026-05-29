"""Integration tests for Task 1.13 — ENTRYEXIT.

Acceptance criteria from IMPLEMENTATION_PLAN:
    - total firm count stays constant (entry replaces exit, in-place);
    - entrants' productivity is drawn from incumbents'.

Additional checks:
    - s1 entrant gets a valid supplier list and R&D budget;
    - s2 entrant copies incumbent's market/financial state;
    - s2 entrant's machine ages are reset to 0;
    - pending investment cleared for firms whose s1 supplier died;
    - multi-step run stays stable (no NaN / zero-population collapse).
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
# Helper: build a fully-initialised single-nation model
# ---------------------------------------------------------------------------

def _build_nation(seed: int = 0, n1: int = 10, n2: int = 40) -> Nation:
    gparams = GlobalParameters()
    gparams.n1_capital_good_firms = n1
    gparams.n2_consumption_good_firms = n2
    nparams = NationParameters()

    nation = Nation("ee-test", params=nparams)
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


# ---------------------------------------------------------------------------
# Test: firm count stays constant
# ---------------------------------------------------------------------------

class TestFirmCountConstant:
    """Acceptance criterion 1: entry replaces exit; sector sizes do not change."""

    def _force_s1_death(self, nation: Nation) -> "CapitalGoodFirm":
        """Kill the first s1 firm by setting num_clients=0, net_worth=-1."""
        victim = list(nation.capital_good_sector)[0]
        victim.num_clients = 0
        victim.net_worth = -1.0
        # Remove from all consumer brochure sets and preferred supplier
        for j in list(nation.consumption_good_sector):
            j.brochure_senders_idxs.discard(0)
            if j.preferred_supplier_idx == 0:
                j.preferred_supplier_idx = 1  # redirect so count stays sensible
        return victim

    def _force_s2_death(self, nation: Nation) -> "ConsumptionGoodFirm":
        """Kill the first s2 firm by setting market_share=0, net_worth=-1."""
        victim = list(nation.consumption_good_sector)[0]
        victim.market_share = 0.0
        victim.net_worth = -1.0
        victim.is_alive = False
        return victim

    def test_s1_count_unchanged_after_one_exit(self) -> None:
        nation = _build_nation(seed=42)
        n1 = len(list(nation.capital_good_sector))
        self._force_s1_death(nation)
        nation.process_entry_and_exit()
        assert len(list(nation.capital_good_sector)) == n1

    def test_s2_count_unchanged_after_one_exit(self) -> None:
        nation = _build_nation(seed=42)
        n2 = len(list(nation.consumption_good_sector))
        self._force_s2_death(nation)
        nation.process_entry_and_exit()
        assert len(list(nation.consumption_good_sector)) == n2

    def test_s1_count_unchanged_multiple_exits(self) -> None:
        nation = _build_nation(seed=42, n1=10, n2=40)
        n1 = len(list(nation.capital_good_sector))
        # Kill 3 s1 firms
        for i, f in enumerate(list(nation.capital_good_sector)[:3]):
            f.num_clients = 0
            f.net_worth = -1.0
            for j in list(nation.consumption_good_sector):
                j.brochure_senders_idxs.discard(i)
                if j.preferred_supplier_idx == i:
                    j.preferred_supplier_idx = 9  # redirect to last firm
        nation.process_entry_and_exit()
        assert len(list(nation.capital_good_sector)) == n1

    def test_s2_count_unchanged_multiple_exits(self) -> None:
        nation = _build_nation(seed=42)
        n2 = len(list(nation.consumption_good_sector))
        # Kill 5 s2 firms via market share floor
        for f in list(nation.consumption_good_sector)[:5]:
            f.market_share = 0.0
            f.net_worth = -1.0
        nation.process_entry_and_exit()
        assert len(list(nation.consumption_good_sector)) == n2


# ---------------------------------------------------------------------------
# Test: entrants' productivity drawn from incumbents' (acceptance criterion 2)
# ---------------------------------------------------------------------------

class TestEntrantProductivity:
    """Acceptance criterion 2: entrant productivity is from incumbents."""

    def test_s1_entrant_machine_prod_from_incumbent(self) -> None:
        """Replaced s1 firm gets machine_labour_prod from a surviving incumbent."""
        nation = _build_nation(seed=10)
        capital_firms = list(nation.capital_good_sector)

        # Give firms distinct productivities (easier to trace)
        for i, f in enumerate(capital_firms):
            f.machine_labour_prod = 1.0 + i * 0.1

        # Kill firm 0 (num_clients=0)
        victim = capital_firms[0]
        victim.num_clients = 0
        victim.net_worth = -1.0
        for j in list(nation.consumption_good_sector):
            j.brochure_senders_idxs.discard(0)

        incumbent_prods = {f.machine_labour_prod for f in capital_firms[1:]}
        nation.process_entry_and_exit()

        assert victim.machine_labour_prod in incumbent_prods

    def test_s2_entrant_net_worth_in_perturbation_range(self) -> None:
        """Replaced s2 firm gets net_worth = Uniform[w2inf, w2sup] * W2m.

        C++ flagENTRY2=5 (dsk_main.cpp:6760-6763) overrides the initial copy
        from the source incumbent with a perturbed value drawn from a uniform
        on [w2inf, w2sup] (= [0.1, 0.9] baseline) times the mean alive-incumbent
        net worth.  Before this was implemented the entrant kept the source
        incumbent's net worth verbatim — see planningDocs/build_log.md
        entry "Port C++ ENTRYEXIT entrant perturbation".
        """
        nation = _build_nation(seed=20)
        consumption_firms = list(nation.consumption_good_sector)

        # Give each firm a distinct net worth so we can compute W2m sharply.
        for j, f in enumerate(consumption_firms):
            f.net_worth = 1000.0 + j * 10.0

        # Kill firm 0 via market share
        victim = consumption_firms[0]
        original_nw = victim.net_worth
        victim.market_share = 0.0
        victim.net_worth = -1.0

        # W2m = mean over alive firms (excludes victim with negative NW)
        alive_nws = [f.net_worth for f in consumption_firms[1:]]
        W2m_expected = sum(alive_nws) / len(alive_nws)

        w2inf = nation.gparams.s2_entrant_networth_lower
        w2sup = nation.gparams.s2_entrant_networth_upper
        nation.process_entry_and_exit()

        # Entrant NW should land in [w2inf * W2m, w2sup * W2m]
        assert w2inf * W2m_expected <= victim.net_worth <= w2sup * W2m_expected, (
            f"victim.net_worth = {victim.net_worth} outside "
            f"[{w2inf * W2m_expected}, {w2sup * W2m_expected}] = [w2inf*W2m, w2sup*W2m]"
        )
        assert victim.net_worth != original_nw


# ---------------------------------------------------------------------------
# Test: s1 entrant structure
# ---------------------------------------------------------------------------

class TestS1EntrantStructure:
    """s1 entrant gets valid initial sales, R&D budget, and client list."""

    def test_s1_entrant_has_step_clients(self) -> None:
        """New s1 entrant has exactly step = N2/N1 initial clients."""
        n1, n2 = 10, 40
        nation = _build_nation(seed=5, n1=n1, n2=n2)
        victim = list(nation.capital_good_sector)[0]
        victim.num_clients = 0
        victim.net_worth = -1.0
        for j in list(nation.consumption_good_sector):
            j.brochure_senders_idxs.discard(0)

        nation.process_entry_and_exit()

        step = n2 // n1  # = 4
        assert victim.num_clients == step
        assert len(victim.clients) == step

    def test_s1_entrant_rd_budget_from_initial_sales(self) -> None:
        """R&D budget = nu * initial_sales."""
        nation = _build_nation(seed=5)
        gparams = nation.gparams
        nu = gparams.rd_budget_fraction

        victim = list(nation.capital_good_sector)[0]
        victim.num_clients = 0
        victim.net_worth = -1.0
        for j in list(nation.consumption_good_sector):
            j.brochure_senders_idxs.discard(0)

        nation.process_entry_and_exit()

        expected_rd = nu * victim.sales
        assert abs(victim.rd_budget - expected_rd) < 1e-9

    def test_s1_entrant_market_share_is_zero(self) -> None:
        """New s1 entrant has zero market share (will be updated in MACRO)."""
        nation = _build_nation(seed=5)
        victim = list(nation.capital_good_sector)[0]
        victim.num_clients = 0
        victim.net_worth = -1.0
        for j in list(nation.consumption_good_sector):
            j.brochure_senders_idxs.discard(0)

        nation.process_entry_and_exit()

        assert victim.market_share == 0.0
        assert victim.market_share_prev == 0.0

    def test_s1_entrant_clients_are_unique_consumers(self) -> None:
        """No consumer appears twice in entrant's client list."""
        nation = _build_nation(seed=7)
        victim = list(nation.capital_good_sector)[0]
        victim.num_clients = 0
        victim.net_worth = -1.0
        for j in list(nation.consumption_good_sector):
            j.brochure_senders_idxs.discard(0)

        nation.process_entry_and_exit()

        # unique_ids should be distinct
        ids = [c.unique_id for c in victim.clients]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Test: s2 entrant structure
# ---------------------------------------------------------------------------

class TestS2EntrantStructure:
    """s2 entrant copies incumbent state correctly and gets a new supplier."""

    def _kill_s2_victim(self, nation: Nation) -> "ConsumptionGoodFirm":
        victim = list(nation.consumption_good_sector)[0]
        victim.market_share = 0.0
        victim.net_worth = -1.0
        victim.is_alive = False
        return victim

    def test_s2_entrant_inventory_reset(self) -> None:
        """Entrant starts with zero inventory."""
        nation = _build_nation(seed=30)
        victim = self._kill_s2_victim(nation)
        victim.inventory = 500.0  # non-zero before entry

        nation.process_entry_and_exit()

        assert victim.inventory == 0.0
        assert victim.inventory_monetary == 0.0

    def test_s2_entrant_debt_reset(self) -> None:
        """Entrant starts with zero debt."""
        nation = _build_nation(seed=30)
        victim = self._kill_s2_victim(nation)
        victim.debt = 5000.0

        nation.process_entry_and_exit()

        assert victim.debt == 0.0
        assert victim.debt_prev == 0.0

    def test_s2_entrant_machine_ages_reset(self) -> None:
        """Entrant's machine stock is a copy of incumbent's with all ages = 0."""
        nation = _build_nation(seed=30)
        victim = self._kill_s2_victim(nation)

        nation.process_entry_and_exit()

        assert victim.machines is not None
        if victim.machines.age.size > 0:
            assert (victim.machines.age == 0.0).all()

    def test_s2_entrant_gets_new_supplier(self) -> None:
        """Entrant is assigned a valid new s1 supplier."""
        nation = _build_nation(seed=30)
        victim = self._kill_s2_victim(nation)
        old_sidx = victim.preferred_supplier_idx

        nation.process_entry_and_exit()

        new_sidx = victim.preferred_supplier_idx
        n1 = len(list(nation.capital_good_sector))
        assert 0 <= new_sidx < n1
        # Entrant appears in new supplier's client list
        assert victim in list(nation.capital_good_sector)[new_sidx].clients

    def test_s2_entrant_market_share_from_incumbent(self) -> None:
        """Entrant's market share is copied from a living incumbent."""
        nation = _build_nation(seed=30)
        consumption_firms = list(nation.consumption_good_sector)
        # Make all market shares distinct for traceability
        for j, f in enumerate(consumption_firms):
            f.market_share = 1.0 / len(consumption_firms) + j * 1e-6

        victim = consumption_firms[0]
        victim.market_share = 0.0
        victim.net_worth = -1.0

        incumbent_shares = {f.market_share for f in consumption_firms[1:]}
        nation.process_entry_and_exit()

        assert victim.market_share in incumbent_shares


# ---------------------------------------------------------------------------
# Test: pending investment cleared for consumers of dead s1 supplier
# ---------------------------------------------------------------------------

class TestPendingInvestmentCleared:
    """Consumers whose s1 supplier died have their pending orders zeroed."""

    def test_pending_cleared_when_supplier_dies(self) -> None:
        nation = _build_nation(seed=99)
        capital_firms = list(nation.capital_good_sector)
        consumption_firms = list(nation.consumption_good_sector)

        # Kill s1 firm 0
        victim_s1 = capital_firms[0]
        victim_s1.num_clients = 0
        victim_s1.net_worth = -1.0
        for j in consumption_firms:
            j.brochure_senders_idxs.discard(0)

        # Make a consumer prefer supplier 0 and have pending investment
        consumer = consumption_firms[0]
        consumer.preferred_supplier_idx = 0
        consumer.pending_order_n_machines = 5.0
        consumer.desired_expansion_investment = 200.0

        nation.process_entry_and_exit()

        # Pending investment should be cleared
        assert consumer.pending_order_n_machines == 0.0
        assert consumer.desired_expansion_investment == 0.0
        # preferred_supplier_idx reset to -1 (BROCHURE will reassign)
        assert consumer.preferred_supplier_idx == -1


# ---------------------------------------------------------------------------
# Test: multi-step stability
# ---------------------------------------------------------------------------

class TestMultiStepStability:
    """After several production+dynamics+entry-exit cycles, no NaN or collapse."""

    @pytest.mark.parametrize("seed", [0, 1, 2])
    def test_runs_10_steps_without_collapse(self, seed: int) -> None:
        nation = _build_nation(seed=seed)

        for t in range(1, 11):
            nation.production_phase(t)
            nation.dynamics_phase(t)
            # closeout would normally update state; minimal version:
            nation.update_state_for_next_period()

        n1 = len(list(nation.capital_good_sector))
        n2 = len(list(nation.consumption_good_sector))
        assert n1 == nation.gparams.n1_capital_good_firms
        assert n2 == nation.gparams.n2_consumption_good_firms

        # GDP should be a finite positive number
        assert np.isfinite(nation.gdp_nominal)
        assert nation.gdp_nominal > 0.0
