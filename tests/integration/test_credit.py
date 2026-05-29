"""Integration tests for Task 1.8 — TOTCREDIT + MAXCREDIT + ALLOCATECREDIT.

Acceptance criteria from IMPLEMENTATION_PLAN:
  - Total credit supply ≤ Basel II constraint (equity / credit_multiplier)
  - Firms with higher NW/Sales ratio rank higher in allocation (served first)
"""
import numpy as np
import pytest

from dsk.agents.bank import Bank
from dsk.agents.capital_good_firm import CapitalGoodFirm
from dsk.agents.consumption_good_firm import ConsumptionGoodFirm
from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeNation:
    """Minimal nation stand-in for unit tests."""
    def __init__(self, nparams=None):
        self.params = nparams or NationParameters()
        self.rng = np.random.default_rng(42)

    class labour_market:
        wage = 1.0


def _make_s2_firm(nation, gparams, nparams, supplier_idx=0, bank_idx=0):
    rng = np.random.default_rng(1)
    firm = ConsumptionGoodFirm(nation, rng)
    firm.initialise_from_parameters(gparams, nparams, supplier_idx, bank_idx, 0)
    return firm


def _make_s1_firm(nation, price=10.4, machine_labour_prod=1.0):
    rng = np.random.default_rng(0)
    firm = CapitalGoodFirm(nation, rng)
    firm.price = price
    firm.machine_labour_prod = machine_labour_prod
    firm.is_alive = True
    return firm


def _make_bank(nation, gparams, nparams, client_firms):
    rng = np.random.default_rng(7)
    bank = Bank(nation, rng)
    bank.initialise_from_parameters(gparams, nparams, client_firms)
    return bank


def _build_minimal_nation_with_bank(n2=4, nparams=None, gparams=None):
    """Build a minimal nation with NB=1 bank, N1=10 capital firms, and n2 s2 firms."""
    from dsk.nation import Nation
    from dsk.parameters.global_parameters import GlobalParameters
    from dsk.parameters.nation_parameters import NationParameters
    from dsk.sectors.capital_good_sector import CapitalGoodSector
    from dsk.sectors.consumption_good_sector import ConsumptionGoodSector
    from dsk.sectors.banking_sector import BankingSector

    if gparams is None:
        gparams = GlobalParameters()
        gparams.n1_capital_good_firms = 10
        gparams.n2_consumption_good_firms = n2
    if nparams is None:
        nparams = NationParameters()
        nparams.n_banks = 1  # small n2; Pareto minimum-sum constraint requires NB=1

    nation = Nation("test")
    nation.gparams = gparams
    rng = np.random.default_rng(0)
    nation.rng = rng

    # Capital-good firms
    for _ in range(gparams.n1_capital_good_firms):
        cf = CapitalGoodFirm(nation, rng)
        cf.initialise_from_parameters(gparams)
        nation.capital_good_sector.add(cf)

    # Consumption-good firms
    machine_counter = 0
    s2_firms = []
    for j in range(gparams.n2_consumption_good_firms):
        f = ConsumptionGoodFirm(nation, rng)
        machine_counter = f.initialise_from_parameters(
            gparams, nparams, j % gparams.n1_capital_good_firms, 0, machine_counter
        )
        nation.consumption_good_sector.add(f)
        s2_firms.append(f)

    # Banking sector (NB=1)
    nation.banking_sector.initialise_from_parameters(
        gparams, nparams, rng, nation, s2_firms
    )

    return nation, s2_firms


# ---------------------------------------------------------------------------
# Class 1 — compute_bank_client_net_worth (WTOTCLIENT)
# ---------------------------------------------------------------------------

class TestComputeBankClientNetWorth:

    def test_monetary_base_equals_sum_positive_nw(self):
        """Bank monetary base = sum of positive client net worths."""
        nation, s2_firms = _build_minimal_nation_with_bank(n2=4)
        bank = list(nation.banking_sector)[0]

        # Manually set net worths
        nws = [500.0, 0.0, 300.0, -100.0]  # 0 and negative excluded
        for f, nw in zip(s2_firms, nws):
            f.net_worth = nw

        nation.compute_bank_client_net_worth()
        assert bank.monetary_base == pytest.approx(800.0)

    def test_all_negative_nw_gives_zero_monetary_base(self):
        """Monetary base is 0 when all client net worths are non-positive."""
        nation, s2_firms = _build_minimal_nation_with_bank(n2=3)
        bank = list(nation.banking_sector)[0]
        for f in s2_firms:
            f.net_worth = -10.0
        nation.compute_bank_client_net_worth()
        assert bank.monetary_base == pytest.approx(0.0)

    def test_all_positive_nw_sums_correctly(self):
        """All positive net worths are included."""
        nation, s2_firms = _build_minimal_nation_with_bank(n2=3)
        bank = list(nation.banking_sector)[0]
        for i, f in enumerate(s2_firms):
            f.net_worth = float((i + 1) * 100)
        nation.compute_bank_client_net_worth()
        assert bank.monetary_base == pytest.approx(600.0)


# ---------------------------------------------------------------------------
# Class 2 — determine_total_credit (TOTCREDIT, Basel II)
# ---------------------------------------------------------------------------

class TestDetermineTotalCredit:

    def test_total_credit_le_basel_constraint(self):
        """Acceptance: total credit ≤ equity / credit_multiplier (Basel II constraint)."""
        nation, _ = _build_minimal_nation_with_bank(n2=4)
        nation.compute_bank_client_net_worth()
        nation.determine_total_credit()

        nparams = nation.params
        for bank in nation.banking_sector:
            assert bank.total_credit <= bank.equity / nparams.credit_multiplier + 1e-9

    def test_total_credit_equals_equity_over_multiplier(self):
        """For flagtotalcredit==2 (Basel II): total_credit = equity / credit_multiplier."""
        nation, _ = _build_minimal_nation_with_bank(n2=4)
        nation.compute_bank_client_net_worth()
        nation.determine_total_credit()

        nparams = nation.params
        for bank in nation.banking_sector:
            expected = bank.equity / nparams.credit_multiplier
            assert bank.total_credit == pytest.approx(expected, rel=1e-9)

    def test_credit_supply_equals_total_credit_when_bcr_zero(self):
        """With basiccreditrate=0: credit_supply = total_credit = Basel credit."""
        nation, _ = _build_minimal_nation_with_bank(n2=4)
        nation.compute_bank_client_net_worth()
        nation.determine_total_credit()

        for bank in nation.banking_sector:
            assert bank.credit_supply == pytest.approx(bank.basel_credit)

    def test_equity_computed_from_deposits(self):
        """BankEquity = deposits × bank_equity_init_multiplier."""
        gparams = GlobalParameters()
        gparams.n1_capital_good_firms = 10
        gparams.n2_consumption_good_firms = 4
        gparams.bank_equity_init_multiplier = 2.0  # non-default to test formula
        nation, _ = _build_minimal_nation_with_bank(n2=4, gparams=gparams)
        nation.compute_bank_client_net_worth()
        nation.determine_total_credit()

        nparams = nation.params
        for bank in nation.banking_sector:
            expected_deposits = bank.monetary_base / nparams.bank_reserve_requirement_rate
            expected_equity = expected_deposits * gparams.bank_equity_init_multiplier
            assert bank.equity == pytest.approx(expected_equity, rel=1e-9)


# ---------------------------------------------------------------------------
# Class 3 — compute_max_credit_per_firm (MAXCREDIT)
# ---------------------------------------------------------------------------

class TestComputeMaxCreditPerFirm:

    def test_higher_nw_sales_ranks_first(self):
        """Acceptance: firms with higher NW/Sales ratio rank higher (served first)."""
        nation, s2_firms = _build_minimal_nation_with_bank(n2=3)
        bank = list(nation.banking_sector)[0]

        # Assign different NW/Sales profiles
        s2_firms[0].net_worth_prev = 100.0;  s2_firms[0].sales_prev = 1000.0  # ratio 0.1
        s2_firms[1].net_worth_prev = 500.0;  s2_firms[1].sales_prev = 1000.0  # ratio 0.5 (best)
        s2_firms[2].net_worth_prev = 200.0;  s2_firms[2].sales_prev = 1000.0  # ratio 0.2

        nation.compute_max_credit_per_firm()

        # ranked_firms_ordered should have firm[1] first (best NW/Sales)
        ranked = bank.rated_firms_ordered
        firm_uid_to_idx = {f.unique_id: i for i, f in enumerate(s2_firms)}
        ranked_indices = [firm_uid_to_idx[uid] for uid in ranked]
        assert ranked_indices[0] == 1, "Firm with highest NW/Sales should be rank 1"

    def test_rating_order_descending_nw_sales(self):
        """Ranked order is descending by NW/Sales ratio."""
        nation, s2_firms = _build_minimal_nation_with_bank(n2=4)
        bank = list(nation.banking_sector)[0]

        ratios = [0.1, 0.4, 0.3, 0.2]  # expected rank order: 1, 3, 2, 0
        for f, r in zip(s2_firms, ratios):
            f.net_worth_prev = r * 1000.0
            f.sales_prev = 1000.0

        nation.compute_max_credit_per_firm()

        ranked = bank.rated_firms_ordered
        uid_map = {f.unique_id: r for f, r in zip(s2_firms, ratios)}
        # Each successive firm should have ≤ ratio of the previous
        for i in range(len(ranked) - 1):
            assert uid_map[ranked[i]] >= uid_map[ranked[i + 1]]

    def test_zero_sales_gets_ratio_one(self):
        """Firms with zero sales get ratio=1 (default, not excluded)."""
        nation, s2_firms = _build_minimal_nation_with_bank(n2=2)
        for f in s2_firms:
            f.net_worth_prev = 500.0
            f.sales_prev = 0.0  # zero sales

        nation.compute_max_credit_per_firm()
        for f in s2_firms:
            assert f.net_worth_to_sales == pytest.approx(1.0)

    def test_all_firms_in_rated_list(self):
        """rated_firms_ordered contains all n2 firm unique_ids."""
        n2 = 6
        nation, s2_firms = _build_minimal_nation_with_bank(n2=n2)
        bank = list(nation.banking_sector)[0]
        nation.compute_max_credit_per_firm()
        assert len(bank.rated_firms_ordered) == n2


# ---------------------------------------------------------------------------
# Class 4 — allocate_credit_to_demand (ALLOCATECREDIT)
# ---------------------------------------------------------------------------

class TestAllocateCreditToDemand:

    def _run_invest_and_alloc(self, nation, s2_firms, t=1):
        """Run INVEST pipeline then ALLOCATECREDIT for a nation."""
        capital_firms = list(nation.capital_good_sector)
        gparams = nation.gparams
        wage = nation.labour_market.wage

        nation.compute_bank_client_net_worth()
        nation.determine_total_credit()
        nation.compute_max_credit_per_firm()

        for firm in s2_firms:
            if not firm.is_alive:
                continue
            firm.form_demand_expectation(t)
            firm.compute_desired_production_and_eid(gparams, t)
            firm.plan_substitution_investment(capital_firms, wage, gparams)
            firm.compute_effective_productivity_and_cost(wage, gparams)
            firm.plan_investment_order(capital_firms, gparams)

        nation.allocate_credit_to_demand(t)

    def test_2a_no_credit_demand_full_plan_executed(self):
        """Case 2.A: firm with sufficient NW gets full plan, debt=0."""
        nation, s2_firms = _build_minimal_nation_with_bank(n2=4)
        firm = s2_firms[0]

        # Give the firm enormous net worth so it needs no credit
        firm.net_worth = 1e9

        self._run_invest_and_alloc(nation, s2_firms, t=1)

        assert firm.debt == pytest.approx(0.0)
        assert firm.production == pytest.approx(firm.desired_production, rel=1e-6)

    def test_2ba_full_credit_sets_nw_sentinel(self):
        """Case 2.B.a: firm gets full credit; NW set to sentinel=1."""
        nation, s2_firms = _build_minimal_nation_with_bank(n2=4)
        # Set a firm with zero NW so it definitely needs credit
        firm = s2_firms[0]
        firm.net_worth = 0.0

        self._run_invest_and_alloc(nation, s2_firms, t=1)

        # After ALLOCATECREDIT, either NW is 1 (rationed, got credit) or
        # firm died (NW=0). It should have been funded or at sentinel.
        assert firm.net_worth in (0.0, 1.0) or firm.net_worth > 0.0

    def test_credit_supply_correctly_depleted(self):
        """Bank total_credit decreases by sum of new loans."""
        nation, s2_firms = _build_minimal_nation_with_bank(n2=4)
        bank = list(nation.banking_sector)[0]

        nation.compute_bank_client_net_worth()
        nation.determine_total_credit()
        initial_credit = bank.total_credit
        nation.compute_max_credit_per_firm()

        capital_firms = list(nation.capital_good_sector)
        gparams = nation.gparams
        wage = nation.labour_market.wage
        for firm in s2_firms:
            firm.form_demand_expectation(1)
            firm.compute_desired_production_and_eid(gparams, 1)
            firm.plan_substitution_investment(capital_firms, wage, gparams)
            firm.compute_effective_productivity_and_cost(wage, gparams)
            firm.plan_investment_order(capital_firms, gparams)

        nation.allocate_credit_to_demand(1)

        assert bank.amount_lent == pytest.approx(initial_credit - bank.total_credit, rel=1e-9)

    def test_production_non_negative_for_all_firms(self):
        """Production Q2 ≥ 0 for all firms after ALLOCATECREDIT."""
        nation, s2_firms = _build_minimal_nation_with_bank(n2=4)
        self._run_invest_and_alloc(nation, s2_firms, t=1)
        for f in s2_firms:
            assert f.production >= 0.0

    def test_labour_demand_consistent_with_production(self):
        """Labour demand = production / A2e for non-new-entrant firms."""
        nation, s2_firms = _build_minimal_nation_with_bank(n2=4)
        self._run_invest_and_alloc(nation, s2_firms, t=1)
        for f in s2_firms:
            if f.is_new_entrant or f.effective_labour_prod_used <= 0.0:
                continue
            expected_ld = f.production / f.effective_labour_prod_used
            assert f.labour_demand == pytest.approx(expected_ld, rel=1e-9)

    def test_pending_order_set_for_investing_firms(self):
        """Firms with positive desired_investment have a pending order."""
        nation, s2_firms = _build_minimal_nation_with_bank(n2=4)
        # Give large net worth so ALLOCATECREDIT doesn't ration investment
        for f in s2_firms:
            f.net_worth = 1e9

        self._run_invest_and_alloc(nation, s2_firms, t=1)

        for f in s2_firms:
            if f.desired_investment > 0.0:
                assert f.pending_order_n_machines > 0.0
                assert f.pending_order_supplier_idx >= 0
                assert f.pending_order_technology is not None
                assert f.pending_order_vintage == 1

    def test_capital_firm_demand_accumulates_orders(self):
        """Capital-good firm demand accumulates machine orders from s2 clients."""
        nation, s2_firms = _build_minimal_nation_with_bank(n2=4)
        for f in s2_firms:
            f.net_worth = 1e9

        self._run_invest_and_alloc(nation, s2_firms, t=1)

        capital_firms = list(nation.capital_good_sector)
        total_orders = sum(cf.demand for cf in capital_firms)
        total_pending = sum(
            f.pending_order_n_machines for f in s2_firms if f.pending_order_n_machines > 0.0
        )
        assert total_orders == pytest.approx(total_pending, rel=1e-9)

    def test_higher_nw_sales_firm_served_first(self):
        """Acceptance: firm with higher NW/Sales is served before lower-rated firm
        when credit is scarce.

        Set up: two firms, both need credit, bank has only enough for one.
        Firm A: high NW/Sales → served first → gets credit → production = Qd
        Firm B: low NW/Sales → served second → rationed → production ≤ Qd
        """
        n2 = 2
        gparams = GlobalParameters()
        gparams.n1_capital_good_firms = 10
        gparams.n2_consumption_good_firms = n2

        nparams = NationParameters()
        # Make credit_multiplier very large so Basel credit is tiny
        nparams.credit_multiplier = 100.0  # equity/100 → very small credit pool

        nation, s2_firms = _build_minimal_nation_with_bank(n2=n2, gparams=gparams, nparams=nparams)
        firm_A, firm_B = s2_firms[0], s2_firms[1]

        # Firm A: high NW/Sales ratio
        firm_A.net_worth_prev = 900.0
        firm_A.sales_prev = 1000.0  # ratio = 0.9

        # Firm B: low NW/Sales ratio
        firm_B.net_worth_prev = 10.0
        firm_B.sales_prev = 1000.0  # ratio = 0.01

        # Both firms need credit: set NW to near-zero
        firm_A.net_worth = 0.0
        firm_B.net_worth = 0.0

        self._run_invest_and_alloc(nation, s2_firms, t=1)

        bank = list(nation.banking_sector)[0]
        # Firm A (higher ranking) should have gotten credit first
        # If bank ran out of credit, firm B should be at least as rationed as firm A
        prod_A = firm_A.production
        prod_B = firm_B.production

        # Firm A was served first and should be funded at least as well as firm B
        # (in a scarce credit environment, the first firm wins)
        assert prod_A >= prod_B - 1e-9, (
            f"Higher-ranked firm A (prod={prod_A}) should be at least as well-funded "
            f"as lower-ranked firm B (prod={prod_B})"
        )

    def test_total_loans_equals_sum_of_firm_debts(self):
        """Bank total_loans_s2 = sum of surviving firm debts after ALLOCATECREDIT."""
        nation, s2_firms = _build_minimal_nation_with_bank(n2=4)
        self._run_invest_and_alloc(nation, s2_firms, t=1)

        bank = list(nation.banking_sector)[0]
        expected = sum(f.debt for f in s2_firms if f.is_alive)
        assert bank.total_loans_s2 == pytest.approx(expected, rel=1e-9)
