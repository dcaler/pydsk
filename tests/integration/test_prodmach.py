"""Integration tests for Task 1.9 — PRODMACH (capital-good production and labour).

Acceptance criteria from IMPLEMENTATION_PLAN:
  - Ordered quantities produced: capital-firm production == demand accumulated by ALLOCATECREDIT
  - Labour demand matches Q1 / (A1p * a)

Additional tests cover:
  - CANCMACH: overaged and cost-ranked scrapping removes machines from MachineStock
  - LABOR full-employment rationing scales production proportionally
"""
import math

import numpy as np
import pytest

from dsk.agents.capital_good_firm import CapitalGoodFirm
from dsk.agents.consumption_good_firm import ConsumptionGoodFirm
from dsk.agents.technology import Technology
from dsk.nation import Nation
from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_nation(n1=4, n2=8, seed=42):
    """Build a minimal nation with initialised sectors ready for PRODMACH."""
    gparams = GlobalParameters()
    gparams.n1_capital_good_firms = n1
    gparams.n2_consumption_good_firms = n2
    nparams = NationParameters()
    nparams.n_banks = 1  # small n2; Pareto minimum-sum constraint requires NB=1

    nation = Nation("test", nparams)
    nation.gparams = gparams
    rng = np.random.default_rng(seed)
    nation.rng = rng

    # Capital-good firms
    capital_firms = []
    for _ in range(n1):
        cf = CapitalGoodFirm(nation, rng)
        cf.initialise_from_parameters(gparams)
        nation.capital_good_sector.add(cf)
        capital_firms.append(cf)

    # Consumption-good firms
    machine_counter = 0
    s2_firms = []
    for j in range(n2):
        f = ConsumptionGoodFirm(nation, rng)
        machine_counter = f.initialise_from_parameters(
            gparams, nparams, j % n1, 0, machine_counter
        )
        nation.consumption_good_sector.add(f)
        s2_firms.append(f)

    # Banking sector (NB=1)
    nation.banking_sector.initialise_from_parameters(
        gparams, nparams, rng, nation, s2_firms
    )

    # Initialise singleton domains
    nation.labour_market.initialise_from_parameters(gparams, nparams)

    return nation, capital_firms, s2_firms


def _run_up_to_prodmach(nation, t=1):
    """Run the phase sub-steps that must precede produce_machines()."""
    nation.compute_bank_client_net_worth()
    nation.deliver_machines()
    nation.determine_total_credit()
    nation.compute_max_credit_per_firm()
    nation.distribute_brochures()
    nation.plan_investment(t)
    nation.allocate_credit_to_demand(t)


# ---------------------------------------------------------------------------
# Class 1 — Ordered quantities produced (acceptance criterion 1)
# ---------------------------------------------------------------------------

class TestOrderedQuantitiesProduced:

    def test_capital_firm_production_equals_demand(self):
        """Acceptance: production Q1(i) = D1(i) for every alive capital firm."""
        nation, capital_firms, _ = _build_nation(n1=4, n2=8)
        _run_up_to_prodmach(nation, t=1)
        nation.produce_machines()

        for firm in capital_firms:
            if firm.is_alive:
                assert firm.production == pytest.approx(firm.demand), (
                    f"Q1={firm.production} != D1={firm.demand}"
                )

    def test_capital_firm_production_nonnegative(self):
        """Production is always >= 0."""
        nation, capital_firms, _ = _build_nation(n1=4, n2=8)
        _run_up_to_prodmach(nation, t=1)
        nation.produce_machines()
        for firm in capital_firms:
            assert firm.production >= 0.0

    def test_capital_firm_sales_equal_price_times_production(self):
        """S1(1,i) = p1(1,i) * Q1(i) after PRODMACH."""
        nation, capital_firms, _ = _build_nation(n1=4, n2=8)
        _run_up_to_prodmach(nation, t=1)
        nation.produce_machines()
        for firm in capital_firms:
            if firm.is_alive:
                assert firm.sales == pytest.approx(firm.price * firm.production)


# ---------------------------------------------------------------------------
# Class 2 — Labour demand matches Q / A1 (acceptance criterion 2)
# ---------------------------------------------------------------------------

class TestLabourDemandFormula:

    def test_labour_demand_matches_q1_over_a1p_a(self):
        """Acceptance: Ld1(i) = Q1(i) / (A1p(i) * a) for all alive capital firms."""
        nation, capital_firms, _ = _build_nation(n1=4, n2=8)
        _run_up_to_prodmach(nation, t=1)
        nation.produce_machines()

        a = nation.gparams.s1_productivity_scale
        for firm in capital_firms:
            if firm.is_alive and firm.process_labour_prod > 0.0:
                expected = firm.production / (firm.process_labour_prod * a)
                assert firm.labour_demand == pytest.approx(expected, rel=1e-9), (
                    f"Ld1={firm.labour_demand} != Q1/(A1p*a)={expected}"
                )

    def test_labour_demand_zero_for_zero_production(self):
        """A capital firm with no orders has zero labour demand."""
        nation, capital_firms, _ = _build_nation(n1=4, n2=8)
        _run_up_to_prodmach(nation, t=1)

        # Force the first capital firm to have zero demand
        capital_firms[0].demand = 0.0

        nation.produce_machines()
        assert capital_firms[0].labour_demand == pytest.approx(0.0)

    def test_labour_market_aggregates_updated(self):
        """LabourMarket.labour_demand_s1 == sum of capital-firm labour demands."""
        nation, capital_firms, _ = _build_nation(n1=4, n2=8)
        _run_up_to_prodmach(nation, t=1)
        nation.produce_machines()

        expected_ld1 = sum(
            f.labour_demand for f in capital_firms if f.is_alive
        )
        assert nation.labour_market.labour_demand_s1 == pytest.approx(expected_ld1)


# ---------------------------------------------------------------------------
# Class 3 — CANCMACH: actual scrapping removes machines from MachineStock
# ---------------------------------------------------------------------------

class TestCancmach:

    def test_overaged_machines_removed_on_scrapping(self):
        """CANCMACH removes overaged machines when SI > 0."""
        nation, capital_firms, s2_firms = _build_nation(n1=4, n2=4)
        gparams = nation.gparams
        _run_up_to_prodmach(nation, t=1)

        firm = s2_firms[0]
        # Force a scrapping scenario: mark all machines as overaged
        if firm.machines is not None:
            firm.machines.age[:] = gparams.machine_max_age + 1.0  # > agemax
            n_before = firm.machines.total_machines()

            # Populate scrap_candidates with all non-empty slots
            firm.scrap_candidates = []
            for vk in firm.machines.vintage_keys:
                row = firm.machines.row_for(vk)
                if row is None:
                    continue
                for s in range(firm.machines._n_suppliers):
                    cnt = firm.machines.count[row, s]
                    if cnt > 0.0:
                        firm.scrap_candidates.append((vk, s, cnt))

            # Set SI = 2 machines worth of scrapping
            firm.desired_substitution_investment = 2.0 * gparams.machine_size_units

            nation.produce_machines()

            n_after = firm.machines.total_machines()
            assert n_after == pytest.approx(n_before - 2.0), (
                f"Expected 2 machines removed; before={n_before} after={n_after}"
            )

    def test_no_scrapping_when_si_is_zero(self):
        """MachineStock unchanged when desired_substitution_investment == 0."""
        nation, capital_firms, s2_firms = _build_nation(n1=4, n2=4)
        _run_up_to_prodmach(nation, t=1)

        firm = s2_firms[0]
        if firm.machines is not None:
            n_before = firm.machines.total_machines()
            firm.desired_substitution_investment = 0.0
            firm.scrap_candidates = []

            nation.produce_machines()

            n_after = firm.machines.total_machines()
            assert n_after == pytest.approx(n_before)

    def test_scrapmax_limits_removal(self):
        """CANCMACH respects scrapmax: removes at most SI/dim_mach machines."""
        nation, capital_firms, s2_firms = _build_nation(n1=4, n2=4)
        gparams = nation.gparams
        _run_up_to_prodmach(nation, t=1)

        firm = s2_firms[0]
        if firm.machines is not None:
            # Mark all machines as overaged
            firm.machines.age[:] = gparams.machine_max_age + 1.0
            n_before = firm.machines.total_machines()

            # Populate all non-empty slots as candidates
            firm.scrap_candidates = []
            for vk in firm.machines.vintage_keys:
                row = firm.machines.row_for(vk)
                if row is None:
                    continue
                for s in range(firm.machines._n_suppliers):
                    cnt = firm.machines.count[row, s]
                    if cnt > 0.0:
                        firm.scrap_candidates.append((vk, s, cnt))

            # SI = only 1 machine, even though more are overaged
            firm.desired_substitution_investment = 1.0 * gparams.machine_size_units

            nation.produce_machines()

            n_after = firm.machines.total_machines()
            removed = n_before - n_after
            assert removed == pytest.approx(1.0), (
                f"Expected exactly 1 machine removed; got {removed}"
            )

    def test_highest_cost_scrapped_first_in_second_pass(self):
        """Second-pass: machine with highest w/A cost is removed first."""
        nation, capital_firms, s2_firms = _build_nation(n1=4, n2=4)
        gparams = nation.gparams
        wage = nation.labour_market.wage
        _run_up_to_prodmach(nation, t=1)

        firm = s2_firms[0]
        if firm.machines is None:
            return

        # Set up two slots with different labour productivity
        # High cost = low productivity; low cost = high productivity
        # Use the first two non-empty slots
        slots = []
        for vk in firm.machines.vintage_keys:
            row = firm.machines.row_for(vk)
            if row is None:
                continue
            for s in range(firm.machines._n_suppliers):
                if firm.machines.count[row, s] > 0.0:
                    slots.append((vk, s, row))
                    if len(slots) == 2:
                        break
            if len(slots) == 2:
                break

        if len(slots) < 2:
            pytest.skip("Need at least 2 non-empty machine slots for this test")

        vk0, s0, r0 = slots[0]
        vk1, s1, r1 = slots[1]

        # Slot 0: high cost (low productivity 0.5)
        # Slot 1: low cost (high productivity 2.0)
        firm.machines.labour_productivity[r0, s0] = 0.5
        firm.machines.labour_productivity[r1, s1] = 2.0
        # Ensure ages are NOT overaged (all must go through second pass)
        firm.machines.age[:] = 0.0

        n0_before = firm.machines.count[r0, s0]
        n1_before = firm.machines.count[r1, s1]

        # Mark both slots as candidates; SI = 1 machine (remove the expensive one only)
        firm.scrap_candidates = [(vk0, s0, n0_before), (vk1, s1, n1_before)]
        firm.desired_substitution_investment = 1.0 * gparams.machine_size_units

        nation.produce_machines()

        # The high-cost slot (lp=0.5) should have been reduced by 1
        n0_after = firm.machines.count[r0, s0]
        n1_after = firm.machines.count[r1, s1]

        assert n0_after == pytest.approx(n0_before - 1.0), (
            "High-cost slot should lose 1 machine"
        )
        assert n1_after == pytest.approx(n1_before), (
            "Low-cost slot should be unchanged"
        )

    def test_empty_slots_get_age_zeroed(self):
        """After PRODMACH, slots with count==0 have age==0."""
        nation, capital_firms, s2_firms = _build_nation(n1=4, n2=4)
        gparams = nation.gparams
        _run_up_to_prodmach(nation, t=1)

        firm = s2_firms[0]
        if firm.machines is None:
            return

        # Manually zero the count of one slot but leave its age non-zero
        vk = list(firm.machines.vintage_keys)[0]
        row = firm.machines.row_for(vk)
        for s in range(firm.machines._n_suppliers):
            if firm.machines.count[row, s] > 0.0:
                # Zero the count but set a stale age
                firm.machines.count[row, s] = 0.0
                firm.machines.age[row, s] = 5.0
                break

        nation.produce_machines()

        # All zero-count slots must have age==0
        for r in range(firm.machines.count.shape[0]):
            for s in range(firm.machines.count.shape[1]):
                if firm.machines.count[r, s] == 0.0:
                    assert firm.machines.age[r, s] == pytest.approx(0.0), (
                        f"Stale age in empty slot row={r} s={s}"
                    )


# ---------------------------------------------------------------------------
# Class 4 — LABOR full-employment rationing
# ---------------------------------------------------------------------------

class TestLaborFullEmployment:

    def test_no_rationing_when_demand_below_supply(self):
        """When LD1+LD2 <= LS, production is not scaled down."""
        nation, capital_firms, s2_firms = _build_nation(n1=4, n2=8)
        gparams = nation.gparams
        _run_up_to_prodmach(nation, t=1)

        # Record pre-LABOR demands for capital firms
        pre_demands = {f.unique_id: f.demand for f in capital_firms if f.is_alive}

        # Ensure labour supply is vastly larger than demand
        nation.labour_market.labour_supply = 1e9
        nation.produce_machines()

        for firm in capital_firms:
            if firm.is_alive and firm.unique_id in pre_demands:
                assert firm.production == pytest.approx(pre_demands[firm.unique_id])

    def test_rationing_reduces_production(self):
        """When LD1+LD2 > LS, capital-firm production is scaled down."""
        nation, capital_firms, s2_firms = _build_nation(n1=4, n2=8)
        _run_up_to_prodmach(nation, t=1)

        # Force full-employment by setting labour supply near zero
        # (must still be > LD1rdtot = 0 to avoid vital-labour error)
        nation.labour_market.labour_supply = 0.01  # tiny supply

        pre_demand = {f.unique_id: f.demand for f in capital_firms if f.is_alive}
        nation.produce_machines()

        # Some firms with non-zero demand should have reduced production
        scaled_any = any(
            f.production < pre_demand[f.unique_id]
            for f in capital_firms
            if f.is_alive and pre_demand[f.unique_id] > 0.0
        )
        assert scaled_any, "Expected at least one firm to be rationed"

    def test_labour_demand_totals_stored_in_labour_market(self):
        """labour_market.labour_demand_s1 and _s2 are set by produce_machines."""
        nation, capital_firms, s2_firms = _build_nation(n1=4, n2=8)
        _run_up_to_prodmach(nation, t=1)
        nation.produce_machines()

        lm = nation.labour_market
        assert lm.labour_demand_s1 >= 0.0
        assert lm.labour_demand_s2 >= 0.0
        assert lm.labour_demand_total == pytest.approx(
            lm.labour_demand_s1 + lm.labour_demand_s2
        )
