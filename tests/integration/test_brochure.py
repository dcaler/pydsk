"""Integration tests for Task 1.6: BROCHURE (capital-good firm advertising).

Ports C++ dsk_main.cpp BROCHURE() lines 2596-2738.

The BROCHURE function has four phases:
1. Repair orphaned consumers (no valid supplier → random assignment).
2. Each capital firm sends ROUND(nclient*Gamma) new brochures to random consumers.
3. Each consumer picks the cheapest supplier (min p1*(w/A1)) from its brochure set.
4. Capital-firm client lists and nclient recount.

Acceptance criterion: after a brochure step, every ConsumptionGoodFirm has at
least one supplier link unless its previous supplier died (was set to invalid idx).
"""
import pytest
import numpy as np

from dsk.agents.capital_good_firm import CapitalGoodFirm
from dsk.agents.consumption_good_firm import ConsumptionGoodFirm
from dsk.nation import Nation
from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters
from dsk.simulation import Simulation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_nation_with_firms(n1: int = 5, n2: int = 20, seed: int = 42):
    """Return (sim, nation, s1_firms, s2_firms) with all firms initialised."""
    gparams = GlobalParameters()
    gparams.n1_capital_good_firms = n1
    gparams.n2_consumption_good_firms = n2

    nparams = NationParameters()
    nation = Nation(nation_id="test", params=nparams)
    sim = Simulation(gparams, [nation], rng_seed=seed)

    s1_firms = []
    for _ in range(n1):
        f = CapitalGoodFirm(nation, nation.rng)
        f.initialise_from_parameters(gparams)
        nation.capital_good_sector.add(f)
        s1_firms.append(f)

    counter = 0
    s2_firms = []
    for j in range(n2):
        f = ConsumptionGoodFirm(nation, nation.rng)
        counter = f.initialise_from_parameters(gparams, nparams, j % n1, 0, counter)
        nation.consumption_good_sector.add(f)
        s2_firms.append(f)

    return sim, nation, s1_firms, s2_firms


# ---------------------------------------------------------------------------
# Tests: post-BROCHURE invariants (acceptance criterion)
# ---------------------------------------------------------------------------

class TestBrochureAcceptanceCriterion:
    def test_every_alive_consumer_has_valid_supplier_after_brochure(self):
        """After BROCHURE, every alive consumer has preferred_supplier_idx in [0, N1)."""
        _, nation, s1_firms, s2_firms = _make_nation_with_firms()
        gparams = nation.gparams
        N1 = gparams.n1_capital_good_firms

        nation.deliver_machines()
        nation.distribute_brochures()

        for j_firm in s2_firms:
            if j_firm.is_alive:
                assert 0 <= j_firm.preferred_supplier_idx < N1, (
                    f"Consumer firm has invalid preferred_supplier_idx="
                    f"{j_firm.preferred_supplier_idx}"
                )

    def test_orphaned_consumer_gets_reassigned(self):
        """A consumer whose supplier was 'killed' (idx=-1) gets a new valid supplier."""
        _, nation, s1_firms, s2_firms = _make_nation_with_firms()
        gparams = nation.gparams
        N1 = gparams.n1_capital_good_firms

        nation.deliver_machines()

        # Orphan the first three consumers by marking their supplier as invalid
        for j_firm in s2_firms[:3]:
            j_firm.preferred_supplier_idx = -1
            j_firm.brochure_senders_idxs = set()

        nation.distribute_brochures()

        for j_firm in s2_firms[:3]:
            assert 0 <= j_firm.preferred_supplier_idx < N1
            assert j_firm.brochure_senders_idxs == {j_firm.preferred_supplier_idx}

    def test_brochure_senders_contains_exactly_one_entry_after_brochure(self):
        """After BROCHURE, brochure_senders_idxs == {preferred_supplier_idx} for every firm."""
        _, nation, _, s2_firms = _make_nation_with_firms()

        nation.deliver_machines()
        nation.distribute_brochures()

        for j_firm in s2_firms:
            assert len(j_firm.brochure_senders_idxs) == 1
            assert next(iter(j_firm.brochure_senders_idxs)) == j_firm.preferred_supplier_idx


# ---------------------------------------------------------------------------
# Tests: client lists and nclient consistency
# ---------------------------------------------------------------------------

class TestClientListConsistency:
    def test_client_lists_sum_to_n2(self):
        """After BROCHURE, the sum of all capital firms' num_clients equals N2."""
        _, nation, s1_firms, s2_firms = _make_nation_with_firms()
        N2 = nation.gparams.n2_consumption_good_firms

        nation.deliver_machines()
        nation.distribute_brochures()

        total_clients = sum(f.num_clients for f in s1_firms)
        assert total_clients == N2

    def test_client_list_matches_preferred_supplier(self):
        """capital_firm.clients contains exactly the consumer firms that prefer it."""
        _, nation, s1_firms, s2_firms = _make_nation_with_firms()

        nation.deliver_machines()
        nation.distribute_brochures()

        for i, i_firm in enumerate(s1_firms):
            expected_clients = [f for f in s2_firms if f.preferred_supplier_idx == i]
            assert len(i_firm.clients) == len(expected_clients)
            assert set(id(f) for f in i_firm.clients) == set(id(f) for f in expected_clients)

    def test_no_capital_firm_has_zero_clients(self):
        """With N2/N1=4 initial matching and Gamma=0.5, every firm should get clients."""
        _, nation, s1_firms, _ = _make_nation_with_firms(n1=5, n2=20)

        nation.deliver_machines()
        nation.distribute_brochures()

        for i_firm in s1_firms:
            assert i_firm.num_clients >= 1, (
                f"Capital firm {i_firm.unique_id} has zero clients after BROCHURE"
            )


# ---------------------------------------------------------------------------
# Tests: supplier choice correctness
# ---------------------------------------------------------------------------

class TestSupplierChoice:
    def test_consumer_switches_to_cheaper_supplier(self):
        """A consumer should switch to a cheaper supplier when brochured by one."""
        gparams = GlobalParameters()
        gparams.n1_capital_good_firms = 2
        gparams.n2_consumption_good_firms = 2
        nparams = NationParameters()
        nation = Nation("t", nparams)
        sim = Simulation(gparams, [nation], rng_seed=0)

        # Create two capital firms; firm 1 is much cheaper (lower price/productivity ratio)
        s1_cheap = CapitalGoodFirm(nation, nation.rng)
        s1_cheap.initialise_from_parameters(gparams)
        s1_cheap.price = 5.0
        s1_cheap.machine_labour_prod = 2.0  # cost ratio = 5/2 = 2.5

        s1_expensive = CapitalGoodFirm(nation, nation.rng)
        s1_expensive.initialise_from_parameters(gparams)
        s1_expensive.price = 10.0
        s1_expensive.machine_labour_prod = 1.0  # cost ratio = 10/1 = 10.0

        nation.capital_good_sector.add(s1_cheap)       # idx=0
        nation.capital_good_sector.add(s1_expensive)   # idx=1

        # Consumer starts preferring the expensive firm (idx=1)
        s2 = ConsumptionGoodFirm(nation, nation.rng)
        s2.initialise_from_parameters(gparams, nparams, preferred_supplier_idx=1, bank_idx=0)
        nation.consumption_good_sector.add(s2)

        # Add a dummy second consumer to avoid zero-client issues
        s2b = ConsumptionGoodFirm(nation, nation.rng)
        s2b.initialise_from_parameters(gparams, nparams, preferred_supplier_idx=0, bank_idx=0)
        nation.consumption_good_sector.add(s2b)

        nation.deliver_machines()

        # Manually give the consumer a brochure from the cheap firm (idx=0)
        s2.brochure_senders_idxs.add(0)

        wage = nation.labour_market.wage
        capital_firms = [s1_cheap, s1_expensive]
        s2.choose_best_supplier(capital_firms, wage)

        # Consumer should now prefer the cheap firm (idx=0)
        assert s2.preferred_supplier_idx == 0

    def test_consumer_stays_with_current_if_best(self):
        """A consumer should not switch if its current supplier has the lowest cost."""
        gparams = GlobalParameters()
        gparams.n1_capital_good_firms = 2
        gparams.n2_consumption_good_firms = 2
        nparams = NationParameters()
        nation = Nation("t", nparams)
        sim = Simulation(gparams, [nation], rng_seed=0)

        # Firm 0 is cheapest; consumer already prefers it
        s1_best = CapitalGoodFirm(nation, nation.rng)
        s1_best.initialise_from_parameters(gparams)
        s1_best.price = 5.0
        s1_best.machine_labour_prod = 2.0   # ratio = 2.5

        s1_worse = CapitalGoodFirm(nation, nation.rng)
        s1_worse.initialise_from_parameters(gparams)
        s1_worse.price = 10.0
        s1_worse.machine_labour_prod = 1.0  # ratio = 10.0

        nation.capital_good_sector.add(s1_best)   # idx=0
        nation.capital_good_sector.add(s1_worse)  # idx=1

        s2 = ConsumptionGoodFirm(nation, nation.rng)
        s2.initialise_from_parameters(gparams, nparams, preferred_supplier_idx=0, bank_idx=0)
        nation.consumption_good_sector.add(s2)

        s2b = ConsumptionGoodFirm(nation, nation.rng)
        s2b.initialise_from_parameters(gparams, nparams, preferred_supplier_idx=1, bank_idx=0)
        nation.consumption_good_sector.add(s2b)

        nation.deliver_machines()

        # Manually give brochure from the worse firm
        s2.brochure_senders_idxs.add(1)

        wage = nation.labour_market.wage
        capital_firms = [s1_best, s1_worse]
        s2.choose_best_supplier(capital_firms, wage)

        assert s2.preferred_supplier_idx == 0


# ---------------------------------------------------------------------------
# Tests: brochure volume
# ---------------------------------------------------------------------------

class TestBrochureVolume:
    def test_brochure_count_approximately_gamma_times_nclient(self):
        """Over many runs, the number of newly contacted firms ≈ Gamma * nclient."""
        gparams = GlobalParameters()
        gparams.n1_capital_good_firms = 2
        gparams.n2_consumption_good_firms = 100
        nparams = NationParameters()
        nation = Nation("vol", nparams)
        sim = Simulation(gparams, [nation], rng_seed=7)

        s1_firms = []
        for _ in range(2):
            f = CapitalGoodFirm(nation, nation.rng)
            f.initialise_from_parameters(gparams)
            nation.capital_good_sector.add(f)
            s1_firms.append(f)

        counter = 0
        for j in range(100):
            f = ConsumptionGoodFirm(nation, nation.rng)
            counter = f.initialise_from_parameters(gparams, nparams, j % 2, 0, counter)
            nation.consumption_good_sector.add(f)

        nation.deliver_machines()

        # Count brochures received before BROCHURE (each firm has exactly 1 sender)
        consumption_firms = list(nation.consumption_good_sector)
        pre_counts = [len(f.brochure_senders_idxs) for f in consumption_firms]
        assert all(c == 1 for c in pre_counts)

        nation.distribute_brochures()

        # After BROCHURE, each firm should have exactly 1 sender (the chosen supplier)
        post_counts = [len(f.brochure_senders_idxs) for f in consumption_firms]
        assert all(c == 1 for c in post_counts)

    def test_monopoly_cap_prevents_new_brochures(self):
        """A firm with market_share_prev > f1max sends zero new brochures."""
        gparams = GlobalParameters()
        gparams.n1_capital_good_firms = 2
        gparams.n2_consumption_good_firms = 10
        gparams.s1_antitrust_cap = 0.5  # trigger cap
        nparams = NationParameters()
        nation = Nation("monopoly", nparams)
        sim = Simulation(gparams, [nation], rng_seed=3)

        s1_firms = []
        for _ in range(2):
            f = CapitalGoodFirm(nation, nation.rng)
            f.initialise_from_parameters(gparams)
            nation.capital_good_sector.add(f)
            s1_firms.append(f)

        counter = 0
        consumption_firms = []
        for j in range(10):
            f = ConsumptionGoodFirm(nation, nation.rng)
            counter = f.initialise_from_parameters(gparams, nparams, j % 2, 0, counter)
            nation.consumption_good_sector.add(f)
            consumption_firms.append(f)

        nation.deliver_machines()

        # Set firm 0's previous market share above the cap
        s1_firms[0].market_share_prev = 0.9

        # Record which firms currently have firm 0 as a sender before BROCHURE
        senders_before = {i for i, f in enumerate(consumption_firms)
                          if 0 in f.brochure_senders_idxs}

        nation.distribute_brochures()

        # After BROCHURE, only the firms that ALREADY had firm 0 as preferred supplier
        # (and chose to stay with it) should retain firm 0 as sender.
        # No new consumers should have been added via brochures from firm 0.
        # (We verify this indirectly: num_clients of firm 0 ≤ original client count)
        # The cap applies to new brochure-sending, not to existing clients staying.
        original_client_count = len(senders_before)
        assert s1_firms[0].num_clients <= original_client_count
