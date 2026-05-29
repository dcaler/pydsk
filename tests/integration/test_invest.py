"""Integration tests for Task 1.7 — EXPECT + SCRAPPING + ORD (INVEST).

Tests verify:
- form_demand_expectation: myopic rule (flagEXP=0)
- compute_desired_production_and_eid: Qd, Kd, EId computation
- plan_substitution_investment: payback scrapping and age scrapping
- compute_effective_productivity_and_cost: A2e and c2e (COSTPROD)
- plan_investment_order (ORD): EIp, SIp, Ip, Cmach under prudential limits

Acceptance criteria from IMPLEMENTATION_PLAN:
  - Given growing demand: expansion investment is positive
  - Given a much better available machine: scrapping is triggered
"""
import math

import numpy as np
import pytest

from dsk.agents.capital_good_firm import CapitalGoodFirm
from dsk.agents.consumption_good_firm import ConsumptionGoodFirm
from dsk.agents.machine_stock import MachineStock
from dsk.agents.technology import Technology
from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeNation:
    """Minimal nation stand-in for unit tests."""
    def __init__(self):
        from dsk.sectors.labour_market import LabourMarket
        self.params = NationParameters()
        self.rng = np.random.default_rng(42)

    class labour_market:
        wage = 1.0


def _make_s1_firm(nation, machine_labour_prod=1.0, price=10.4):
    """Construct a minimal CapitalGoodFirm with given productivity and price."""
    rng = np.random.default_rng(0)
    firm = CapitalGoodFirm(nation, rng)
    firm.machine_labour_prod = machine_labour_prod
    firm.price = price
    firm.is_alive = True
    return firm


def _make_s2_firm(nation, gparams=None, nparams=None, supplier_idx=0, bank_idx=0):
    """Construct an initialised ConsumptionGoodFirm with baseline parameters."""
    if gparams is None:
        gparams = GlobalParameters()
    if nparams is None:
        nparams = NationParameters()
    rng = np.random.default_rng(1)
    firm = ConsumptionGoodFirm(nation, rng)
    firm.initialise_from_parameters(gparams, nparams, supplier_idx, bank_idx, 0)
    return firm


# ---------------------------------------------------------------------------
# Class 1 — form_demand_expectation (EXPECT, flagEXP=0)
# ---------------------------------------------------------------------------

class TestFormDemandExpectation:
    """EXPECT function with myopic (naive) rule flagEXP=0."""

    def test_myopic_uses_demand_prev(self):
        """De = D2(2,j) = previous period's actual demand."""
        nation = _FakeNation()
        gparams = GlobalParameters()
        nparams = NationParameters()
        firm = _make_s2_firm(nation, gparams, nparams)
        firm.demand_prev = 500.0
        firm.form_demand_expectation(t=2)
        assert firm.expected_demand == pytest.approx(500.0)

    def test_demand_prev_zero_clamped_to_one(self):
        """De(1,j) <= 0 → De(1,j) = 1 (C++ guard)."""
        nation = _FakeNation()
        firm = _make_s2_firm(nation)
        firm.demand_prev = 0.0
        firm.form_demand_expectation(t=2)
        assert firm.expected_demand == 1.0

    def test_negative_demand_prev_clamped(self):
        nation = _FakeNation()
        firm = _make_s2_firm(nation)
        firm.demand_prev = -100.0
        firm.form_demand_expectation(t=2)
        assert firm.expected_demand == 1.0

    def test_positive_demand_prev_unchanged(self):
        nation = _FakeNation()
        firm = _make_s2_firm(nation)
        firm.demand_prev = 843.75
        firm.form_demand_expectation(t=1)
        assert firm.expected_demand == pytest.approx(843.75)


# ---------------------------------------------------------------------------
# Class 2 — compute_desired_production_and_eid
# ---------------------------------------------------------------------------

class TestDesiredProductionAndEid:
    """Qd, Kd, EId calculation from INVEST per-j body."""

    def _firm_with_state(self, demand_prev, inventory, capital_stock, n_machines):
        nation = _FakeNation()
        gparams = GlobalParameters()
        nparams = NationParameters()
        firm = _make_s2_firm(nation, gparams, nparams)
        firm.demand_prev = demand_prev
        firm.inventory = inventory
        firm.capital_stock = capital_stock
        firm.n_machines = n_machines
        # Pre-set expected_demand (normally set by form_demand_expectation)
        firm.form_demand_expectation(t=2)
        return firm, gparams

    def test_growing_demand_gives_positive_eid(self):
        """Acceptance criterion: growing demand → expansion investment is positive."""
        # demand_prev = 1200 > capital_stock = 800 → Kd >> K → EId > 0
        nation = _FakeNation()
        gparams = GlobalParameters()
        firm = _make_s2_firm(nation, gparams)
        firm.demand_prev = 1200.0
        firm.inventory = gparams.inventory_target_fraction * 1200.0
        firm.capital_stock = 800.0
        firm.n_machines = 20.0
        firm.form_demand_expectation(t=2)
        firm.compute_desired_production_and_eid(gparams, t=2)
        assert firm.desired_expansion_investment > 0.0, (
            "Expected positive EId when demand > current capital"
        )

    def test_no_expansion_when_demand_low(self):
        """When desired production < capital, no expansion investment."""
        nation = _FakeNation()
        gparams = GlobalParameters()
        firm = _make_s2_firm(nation, gparams)
        # Very low demand: Qd << K
        firm.demand_prev = 100.0
        firm.inventory = 10.0
        firm.capital_stock = 800.0
        firm.n_machines = 20.0
        firm.form_demand_expectation(t=2)
        firm.compute_desired_production_and_eid(gparams, t=2)
        assert firm.desired_expansion_investment == pytest.approx(0.0), (
            "No EId expected when Kd < Ktrig (demand much below capacity)"
        )

    def test_desired_production_capped_at_capital(self):
        """Qd is capped at K when desired > current capital."""
        nation = _FakeNation()
        gparams = GlobalParameters()
        firm = _make_s2_firm(nation, gparams)
        K = 800.0
        firm.demand_prev = 2000.0
        firm.inventory = 0.0
        firm.capital_stock = K
        firm.n_machines = K / gparams.machine_size_units
        firm.form_demand_expectation(t=2)
        firm.compute_desired_production_and_eid(gparams, t=2)
        assert firm.desired_production <= K

    def test_qd_non_negative(self):
        """Qd >= 0 even when inventory is above demand + target."""
        nation = _FakeNation()
        gparams = GlobalParameters()
        firm = _make_s2_firm(nation, gparams)
        firm.demand_prev = 100.0
        firm.inventory = 500.0   # far above Ne + De
        firm.capital_stock = 800.0
        firm.n_machines = 20.0
        firm.form_demand_expectation(t=2)
        firm.compute_desired_production_and_eid(gparams, t=2)
        assert firm.desired_production >= 0.0

    def test_eid_multiple_of_dim_mach(self):
        """EId is always a multiple of dim_mach (rounded via floor)."""
        nation = _FakeNation()
        gparams = GlobalParameters()
        firm = _make_s2_firm(nation, gparams)
        firm.demand_prev = 1500.0
        firm.inventory = 0.0
        firm.capital_stock = 800.0
        firm.n_machines = 20.0
        firm.form_demand_expectation(t=2)
        firm.compute_desired_production_and_eid(gparams, t=2)
        dim_mach = gparams.machine_size_units
        remainder = firm.desired_expansion_investment % dim_mach
        assert remainder == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Class 3 — plan_substitution_investment (SCRAPPING)
# ---------------------------------------------------------------------------

class TestPlanSubstitutionInvestment:
    """SCRAPPING: payback rule and age scrapping."""

    def _make_supplier_with_prod(self, nation, machine_labour_prod, price):
        return _make_s1_firm(nation, machine_labour_prod=machine_labour_prod, price=price)

    def test_payback_scrapping_triggered_for_much_better_machine(self):
        """Acceptance criterion: much better available machine triggers scrapping."""
        nation = _FakeNation()
        gparams = GlobalParameters()
        # Existing machine: low productivity A_old = 0.5
        # New machine from supplier: high productivity A1 = 2.0
        # Payback = p1 / (w/A_old - w/A1) = 10.4 / (1/0.5 - 1/2.0) = 10.4 / 1.5 ≈ 6.93
        # b = payback_threshold = 200 >> 6.93 → scrapping triggered
        A_old = 0.5
        A1_new = 2.0
        p1_new = 10.4
        wage = 1.0
        dim_mach = gparams.machine_size_units
        b = gparams.payback_threshold  # = 200

        supplier = self._make_supplier_with_prod(nation, A1_new, p1_new)
        capital_firms = [supplier]

        firm = _make_s2_firm(nation, gparams)
        firm.preferred_supplier_idx = 0

        # Replace machine stock with a slot that has low productivity
        firm.machines = MachineStock(n_suppliers=1)
        firm.machines.add_machines(
            vintage_key=0,
            supplier_idx=0,
            count=1.0,
            technology=Technology(labour_productivity=A_old),
            age=5.0,
        )
        firm.capital_stock = dim_mach
        firm.n_machines = 1.0

        firm.plan_substitution_investment(capital_firms, wage, gparams)

        assert firm.desired_substitution_investment == pytest.approx(dim_mach), (
            "Expected SId = dim_mach for one scrap-candidate machine"
        )
        assert len(firm.scrap_candidates) == 1

    def test_no_payback_scrapping_when_same_productivity(self):
        """No scrapping when old machine has same productivity as new machine."""
        nation = _FakeNation()
        gparams = GlobalParameters()
        A_common = 1.0
        p1_new = 10.4
        wage = 1.0
        dim_mach = gparams.machine_size_units

        supplier = self._make_supplier_with_prod(nation, A_common, p1_new)
        capital_firms = [supplier]

        firm = _make_s2_firm(nation, gparams)
        firm.preferred_supplier_idx = 0
        firm.machines = MachineStock(n_suppliers=1)
        firm.machines.add_machines(
            vintage_key=0,
            supplier_idx=0,
            count=1.0,
            technology=Technology(labour_productivity=A_common),
            age=5.0,
        )
        firm.capital_stock = dim_mach
        firm.n_machines = 1.0

        firm.plan_substitution_investment(capital_firms, wage, gparams)

        assert firm.desired_substitution_investment == pytest.approx(0.0)
        assert len(firm.scrap_candidates) == 0

    def test_age_scrapping_for_old_machine(self):
        """Machine older than agemax is always scrapped regardless of productivity."""
        nation = _FakeNation()
        gparams = GlobalParameters()
        agemax = gparams.machine_max_age        # = 19
        dim_mach = gparams.machine_size_units

        # Old machine has SAME productivity as supplier → no payback scrapping
        A = 1.0
        supplier = self._make_supplier_with_prod(nation, A, price=10.4)
        capital_firms = [supplier]

        firm = _make_s2_firm(nation, gparams)
        firm.preferred_supplier_idx = 0
        firm.machines = MachineStock(n_suppliers=1)
        firm.machines.add_machines(
            vintage_key=0,
            supplier_idx=0,
            count=1.0,
            technology=Technology(labour_productivity=A),
            age=agemax + 1.0,  # over the limit
        )
        firm.capital_stock = dim_mach
        firm.n_machines = 1.0

        firm.plan_substitution_investment(capital_firms, 1.0, gparams)

        assert firm.desired_substitution_investment == pytest.approx(dim_mach)
        assert len(firm.scrap_candidates) == 1

    def test_young_same_productivity_no_scrapping(self):
        """Young machine with same productivity → no scrapping."""
        nation = _FakeNation()
        gparams = GlobalParameters()
        agemax = gparams.machine_max_age
        dim_mach = gparams.machine_size_units
        A = 1.0

        supplier = self._make_supplier_with_prod(nation, A, price=10.4)
        capital_firms = [supplier]

        firm = _make_s2_firm(nation, gparams)
        firm.preferred_supplier_idx = 0
        firm.machines = MachineStock(n_suppliers=1)
        firm.machines.add_machines(
            vintage_key=0,
            supplier_idx=0,
            count=1.0,
            technology=Technology(labour_productivity=A),
            age=agemax - 5.0,   # well within age limit
        )
        firm.capital_stock = dim_mach
        firm.n_machines = 1.0

        firm.plan_substitution_investment(capital_firms, 1.0, gparams)

        assert firm.desired_substitution_investment == pytest.approx(0.0)

    def test_payback_scrapping_at_margin_exactly_equal_to_threshold(self):
        """Payback == b (threshold) → scrapping IS triggered (condition is <=)."""
        nation = _FakeNation()
        gparams = GlobalParameters()
        b = gparams.payback_threshold          # = 200
        dim_mach = gparams.machine_size_units

        # Choose A_old, A1 such that payback = exactly b
        # payback = p1 / (w/A_old - w/A1) = b
        # ⟹ w/A_old - w/A1 = p1/b
        # choose: p1=10.0, w=1.0, A1=1.0, then A_old: 1/A_old = p1/b + 1/A1
        p1 = 10.0
        wage = 1.0
        A1 = 1.0
        inv_A_old = p1 / b + 1.0 / A1
        A_old = 1.0 / inv_A_old

        supplier = self._make_supplier_with_prod(nation, A1, p1)
        capital_firms = [supplier]

        firm = _make_s2_firm(nation, gparams)
        firm.preferred_supplier_idx = 0
        firm.machines = MachineStock(n_suppliers=1)
        firm.machines.add_machines(
            vintage_key=0,
            supplier_idx=0,
            count=1.0,
            technology=Technology(labour_productivity=A_old),
            age=1.0,
        )
        firm.capital_stock = dim_mach
        firm.n_machines = 1.0

        firm.plan_substitution_investment(capital_firms, wage, gparams)

        assert firm.desired_substitution_investment == pytest.approx(dim_mach)

    def test_multi_vintage_partial_scrapping(self):
        """Only the slot with payback <= b is scrapped; the other stays."""
        nation = _FakeNation()
        gparams = GlobalParameters()
        dim_mach = gparams.machine_size_units
        b = gparams.payback_threshold  # = 200
        p1 = 10.4
        wage = 1.0
        A1_new = 2.0

        # Slot 0 (vintage 0, supplier 0): A_old=0.5 → payback ≈ 6.93 < 200 → scrap
        # Slot 1 (vintage 1, supplier 0): A_old=1.85 → payback ≈ 256 > 200 → keep
        # Verify: cost_saving = 1/1.85 - 1/2.0 = 0.04054; payback = 10.4/0.04054 ≈ 256
        A_bad  = 0.5
        A_good = 1.85

        supplier = self._make_supplier_with_prod(nation, A1_new, p1)
        capital_firms = [supplier]

        firm = _make_s2_firm(nation, gparams)
        firm.preferred_supplier_idx = 0
        firm.machines = MachineStock(n_suppliers=1)
        firm.machines.add_machines(
            vintage_key=0,
            supplier_idx=0,
            count=2.0,
            technology=Technology(labour_productivity=A_bad),
            age=5.0,
        )
        firm.machines.add_machines(
            vintage_key=1,
            supplier_idx=0,
            count=3.0,
            technology=Technology(labour_productivity=A_good),
            age=5.0,
        )
        firm.capital_stock = 5.0 * dim_mach
        firm.n_machines = 5.0

        firm.plan_substitution_investment(capital_firms, wage, gparams)

        # Only the 2 bad-productivity machines should be scrapped
        assert firm.desired_substitution_investment == pytest.approx(2.0 * dim_mach)
        assert len(firm.scrap_candidates) == 1
        assert firm.scrap_candidates[0][2] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Class 4 — compute_effective_productivity_and_cost (COSTPROD)
# ---------------------------------------------------------------------------

class TestComputeEffectiveProductivityAndCost:
    """COSTPROD: effective A2e and c2e for the subset of machines used."""

    def test_full_capacity_uses_A2_and_c2(self):
        """When Qd >= K, use aggregate A2 and c2 (trivial branch)."""
        nation = _FakeNation()
        gparams = GlobalParameters()
        firm = _make_s2_firm(nation, gparams)
        # Set Qd = K (full use)
        firm.desired_production = firm.capital_stock
        firm.effective_labour_prod = 1.0
        firm.unit_cost = 1.0
        firm.compute_effective_productivity_and_cost(wage=1.0, gparams=gparams)
        assert firm.effective_labour_prod_used == pytest.approx(1.0)
        assert firm.effective_unit_cost == pytest.approx(1.0)

    def test_partial_capacity_picks_best_machines(self):
        """When Qd < K, COSTPROD selects the most productive machines."""
        nation = _FakeNation()
        gparams = GlobalParameters()
        dim_mach = gparams.machine_size_units
        wage = 1.0

        firm = _make_s2_firm(nation, gparams)
        # Two vintages: one with high productivity, one with low
        A_high = 2.0
        A_low  = 0.5
        firm.machines = MachineStock(n_suppliers=1)
        firm.machines.add_machines(
            vintage_key=0, supplier_idx=0, count=2.0,
            technology=Technology(labour_productivity=A_high), age=1.0,
        )
        firm.machines.add_machines(
            vintage_key=1, supplier_idx=0, count=2.0,
            technology=Technology(labour_productivity=A_low), age=1.0,
        )
        firm.n_machines = 4.0
        firm.capital_stock = 4.0 * dim_mach

        # Only need 2 machines (= high productivity ones)
        firm.desired_production = 2.0 * dim_mach
        firm.compute_effective_productivity_and_cost(wage, gparams)

        # A2e should equal A_high (only the best machines used)
        assert firm.effective_labour_prod_used == pytest.approx(A_high)
        # c2e = wage / A_high
        assert firm.effective_unit_cost == pytest.approx(wage / A_high)

    def test_no_production_uses_aggregate(self):
        """Qd=0 → trivial branch, A2e = A2."""
        nation = _FakeNation()
        gparams = GlobalParameters()
        firm = _make_s2_firm(nation, gparams)
        firm.desired_production = 0.0
        firm.effective_labour_prod = 1.0
        firm.unit_cost = 0.5
        firm.compute_effective_productivity_and_cost(wage=1.0, gparams=gparams)
        assert firm.effective_labour_prod_used == pytest.approx(1.0)
        assert firm.effective_unit_cost == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Class 5 — plan_investment_order (ORD)
# ---------------------------------------------------------------------------

class TestPlanInvestmentOrder:
    """ORD: prudential credit limits, EIp, SIp, Ip, Cmach."""

    def _setup(self, gparams=None, desired_ei=40.0, desired_si=0.0,
               net_worth=1000.0, mol=0.0, production=0.0):
        """Build a firm + one supplier ready for plan_investment_order."""
        if gparams is None:
            gparams = GlobalParameters()
        nation = _FakeNation()
        # Supplier with price=10.4
        supplier = _make_s1_firm(nation, machine_labour_prod=1.0, price=10.4)
        capital_firms = [supplier]

        firm = _make_s2_firm(nation, gparams)
        firm.preferred_supplier_idx = 0
        firm.desired_expansion_investment = desired_ei
        firm.desired_substitution_investment = desired_si
        firm.net_worth = net_worth
        firm.gross_operating_margin = mol
        firm.production = production
        firm.desired_production = firm.capital_stock  # fully utilised
        firm.effective_labour_prod_used = 1.0
        firm.effective_unit_cost = firm.unit_cost  # c2 = 1.0
        return firm, capital_firms, gparams

    def test_investment_costs_computed_correctly(self):
        """Cmach = p1 * Ip / dim_mach when NW covers everything."""
        gparams = GlobalParameters()
        dim_mach = gparams.machine_size_units
        p1 = 10.4
        EId = 2.0 * dim_mach  # = 80 units

        firm, capital_firms, gparams = self._setup(
            gparams, desired_ei=EId, desired_si=0.0,
            net_worth=10000.0,  # ample NW
        )
        firm.desired_production = 0.0  # no production cost to worry about
        firm.plan_investment_order(capital_firms, gparams)

        expected_cmach = p1 * EId / dim_mach   # = 10.4 * 2 = 20.8
        assert firm.potential_expansion_investment == pytest.approx(EId)
        assert firm.machine_order_total_cost == pytest.approx(expected_cmach)
        assert firm.machine_order_expansion_cost == pytest.approx(expected_cmach)
        assert firm.machine_order_substitution_cost == pytest.approx(0.0)

    def test_positive_eid_gives_positive_potential_ei(self):
        """If EId > 0 and NW is sufficient, EIp == EId."""
        gparams = GlobalParameters()
        dim_mach = gparams.machine_size_units
        firm, capital_firms, _ = self._setup(
            gparams, desired_ei=dim_mach, desired_si=0.0,
            net_worth=10000.0,
        )
        firm.desired_production = 0.0
        firm.plan_investment_order(capital_firms, gparams)
        assert firm.potential_expansion_investment == pytest.approx(dim_mach)
        assert firm.potential_total_investment == pytest.approx(dim_mach)

    def test_si_and_ei_combined(self):
        """Ip = EIp + SIp when both are positive and affordable."""
        gparams = GlobalParameters()
        dim_mach = gparams.machine_size_units
        EId = 2.0 * dim_mach
        SId = 1.0 * dim_mach
        firm, capital_firms, _ = self._setup(
            gparams, desired_ei=EId, desired_si=SId,
            net_worth=20000.0,
        )
        firm.desired_production = 0.0
        firm.plan_investment_order(capital_firms, gparams)
        assert firm.potential_expansion_investment == pytest.approx(EId)
        assert firm.potential_substitution_investment == pytest.approx(SId)
        assert firm.potential_total_investment == pytest.approx(EId + SId)

    def test_no_investment_when_nw_and_mol_zero(self):
        """When NW after production = 0 and mol = 0, no investment possible."""
        gparams = GlobalParameters()
        dim_mach = gparams.machine_size_units
        c2 = 1.0  # unit cost
        K = gparams.capital_init  # = 800

        # Net worth exactly covers production cost; nothing left for investment
        # Production cost = c2 * Qd = c2 * K = 800
        firm, capital_firms, _ = self._setup(
            gparams,
            desired_ei=dim_mach,
            desired_si=0.0,
            net_worth=K * c2,     # NW = 800 → NW after prod = 0
            mol=0.0,
        )
        firm.desired_production = K
        firm.effective_unit_cost = c2
        firm.plan_investment_order(capital_firms, gparams)
        # EIp should be 0 (nothing left after production)
        assert firm.potential_expansion_investment == pytest.approx(0.0)
        assert firm.machine_order_total_cost == pytest.approx(0.0)

    def test_labour_demand_based_on_previous_production(self):
        """Ld2 = Q2(last period) / A2e(current)."""
        gparams = GlobalParameters()
        nation = _FakeNation()
        supplier = _make_s1_firm(nation, machine_labour_prod=1.0, price=10.4)
        capital_firms = [supplier]

        firm = _make_s2_firm(nation, gparams)
        firm.preferred_supplier_idx = 0
        firm.production = 600.0               # Q2 from last period
        firm.effective_labour_prod_used = 1.5  # A2e for current period's machines
        firm.net_worth = 10000.0
        firm.desired_production = 0.0
        firm.desired_expansion_investment = 0.0
        firm.desired_substitution_investment = 0.0
        firm.effective_unit_cost = 1.0
        firm.gross_operating_margin = 0.0
        firm.plan_investment_order(capital_firms, gparams)

        # Ld2 = 600 / 1.5 = 400
        assert firm.labour_demand == pytest.approx(600.0 / 1.5)

    def test_supplier_idx_recorded(self):
        """machine_order_supplier_idx is set to preferred_supplier_idx."""
        gparams = GlobalParameters()
        firm, capital_firms, _ = self._setup(gparams)
        firm.desired_production = 0.0
        firm.plan_investment_order(capital_firms, gparams)
        assert firm.machine_order_supplier_idx == 0

    def test_zero_investment_desired_gives_zero_cmach(self):
        """With EId=SId=0, Cmach=0."""
        gparams = GlobalParameters()
        firm, capital_firms, _ = self._setup(
            gparams, desired_ei=0.0, desired_si=0.0, net_worth=10000.0
        )
        firm.desired_production = 0.0
        firm.plan_investment_order(capital_firms, gparams)
        assert firm.machine_order_total_cost == pytest.approx(0.0)
        assert firm.potential_total_investment == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Class 6 — Nation.plan_investment (INVEST + ORD integration)
# ---------------------------------------------------------------------------

class TestNationPlanInvestment:
    """End-to-end: Nation.plan_investment calls all sub-routines in order."""

    def _build_minimal_nation(self, n1=5, n2=10):
        """Build a Nation with n1 capital firms and n2 consumption firms, initialised."""
        from dsk.nation import Nation
        from dsk.simulation import Simulation

        gparams = GlobalParameters()
        gparams.n1_capital_good_firms = n1
        gparams.n2_consumption_good_firms = n2
        nparams = NationParameters()
        nation = Nation(nation_id="test", params=nparams)
        sim = Simulation(gparams, [nation], rng_seed=0)

        # Initialise capital-good firms
        rng = np.random.default_rng(0)
        from dsk.agents.capital_good_firm import CapitalGoodFirm
        for _ in range(n1):
            f = CapitalGoodFirm(nation, rng)
            f.initialise_from_parameters(gparams)
            nation.capital_good_sector.add(f)

        # Initialise consumption-good firms
        machine_counter = 0
        from dsk.agents.consumption_good_firm import ConsumptionGoodFirm
        for j in range(n2):
            f = ConsumptionGoodFirm(nation, rng)
            machine_counter = f.initialise_from_parameters(
                gparams, nparams,
                preferred_supplier_idx=j % n1,
                bank_idx=0,
                machine_counter_start=machine_counter,
            )
            nation.consumption_good_sector.add(f)

        nation.labour_market.wage = gparams.wage_init
        return nation, gparams, sim

    def test_plan_investment_runs_without_error(self):
        """plan_investment(t=1) completes without exception."""
        nation, gparams, sim = self._build_minimal_nation()
        # MACH / BROCHURE would normally run first, but plan_investment can run standalone
        # We just ensure it doesn't raise.
        nation.plan_investment(t=1)

    def test_all_firms_get_expected_demand_set(self):
        """After plan_investment, every alive firm has expected_demand > 0."""
        nation, gparams, sim = self._build_minimal_nation()
        # Provide demand_prev so EXPECT has something to use
        for firm in nation.consumption_good_sector:
            firm.demand_prev = 500.0
        nation.plan_investment(t=2)
        for firm in nation.consumption_good_sector:
            assert firm.expected_demand > 0.0

    def test_expansion_investment_positive_for_high_demand(self):
        """At least some firms invest when demand is large.

        With n2=10, d2 at init is ~33343 so inventory=3334. Setting demand_prev much
        larger than inventory + target-inventory ensures Qd > K and EId > 0.
        We also reset inventory to 0 so Qd = De*theta + De = 1.1*De, simplifying the
        arithmetic.
        """
        nation, gparams, sim = self._build_minimal_nation()
        K = gparams.capital_init   # = 800
        for firm in nation.consumption_good_sector:
            # De = 2000 >> K/theta so Qd will be capped at K and Kd > Ktrig
            firm.demand_prev = 2000.0
            firm.inventory = 0.0   # reset so Qd = De + Ne > K
            firm.net_worth = 50000.0
        nation.plan_investment(t=2)
        ei_values = [f.potential_expansion_investment
                     for f in nation.consumption_good_sector]
        assert any(ei > 0.0 for ei in ei_values)

    def test_investment_order_supplier_idx_is_valid(self):
        """After ORD, each firm's machine_order_supplier_idx is a valid capital firm index."""
        nation, gparams, sim = self._build_minimal_nation(n1=5, n2=10)
        n1 = gparams.n1_capital_good_firms
        for firm in nation.consumption_good_sector:
            firm.demand_prev = 1000.0
            firm.net_worth = 50000.0
        nation.plan_investment(t=2)
        for firm in nation.consumption_good_sector:
            assert 0 <= firm.machine_order_supplier_idx < n1
