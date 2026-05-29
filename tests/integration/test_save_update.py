"""Test SAVE + UPDATE functionality (Task 1.15).

Tests the state-shifting mechanics that prepare the economy for the next timestep,
and the macro output recording.

Mirrors C++ SAVE() (dsk_main.cpp:8632) and UPDATE() (dsk_main.cpp:9004).
"""

import pytest
import numpy as np

from dsk.io.output_sink import OutputSink
from dsk.nation import Nation
from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters
from dsk.simulation import Simulation


class TestSaveOutputs:
    """Test Nation.save_outputs() — macro-level output recording."""

    def test_save_outputs_writes_to_sink(self, tmp_output_dir):
        """save_outputs should record macro data when sink is attached."""
        params = GlobalParameters()
        nation = Nation(nation_id="test", params=NationParameters())
        sink = OutputSink()
        nation.sink = sink
        nation._mc_run = 1

        # Set some macro values to be saved
        nation.real_gdp = 100.5
        nation.gdp_nominal = 110.0
        nation.cpi = 1.02
        nation.ppi = 1.01
        nation.labour_market.wage = 2.5

        # Call save_outputs
        nation.save_outputs(t=5)

        # Verify the row was recorded
        assert sink.n_pending_rows("macro") == 1
        rows = sink._rows["macro"]
        assert len(rows) == 1
        assert rows[0]["t"] == 5
        assert rows[0]["mc_run"] == 1
        assert rows[0]["nation_id"] == "test"
        assert rows[0]["gdp_real"] == 100.5
        assert rows[0]["gdp_nominal"] == 110.0
        assert rows[0]["cpi"] == 1.02

    def test_save_outputs_with_no_sink_does_not_error(self):
        """save_outputs should be a no-op if sink is None."""
        nation = Nation(nation_id="test", params=NationParameters())
        nation.sink = None
        # Should not raise
        nation.save_outputs(t=1)

    def test_save_outputs_captures_labour_market_state(self, tmp_output_dir):
        """save_outputs should record labour market aggregates."""
        nation = Nation(nation_id="test", params=NationParameters())
        sink = OutputSink()
        nation.sink = sink

        nation.labour_market.wage = 1.5
        nation.labour_market.unemployment_rate = 0.05
        nation.labour_market.labour_supply = 500_000.0
        nation.labour_market.labour_demand_total = 450_000.0
        nation.labour_market.mean_machine_prod = 1.2

        nation.save_outputs(t=1)

        rows = sink._rows["macro"]
        assert rows[0]["wage"] == 1.5
        assert rows[0]["unemployment_rate"] == 0.05
        assert rows[0]["labour_supply"] == 500_000.0
        assert rows[0]["labour_demand"] == 450_000.0
        assert rows[0]["mean_machine_prod"] == 1.2

    def test_save_outputs_captures_banking_aggregates(self, tmp_output_dir):
        """save_outputs should record banking sector aggregates."""
        nation = Nation(nation_id="test", params=NationParameters())
        sink = OutputSink()
        nation.sink = sink

        # Initialize banking sector with a couple of banks (just set attributes directly)
        from dsk.agents.bank import Bank

        bank1 = Bank(nation=nation, rng=np.random.default_rng(42))
        bank1.equity = 100.0
        bank1.total_bad_debt = 5.0

        bank2 = Bank(nation=nation, rng=np.random.default_rng(43))
        bank2.equity = 90.0
        bank2.total_bad_debt = 3.0

        nation.banking_sector.add(bank1)
        nation.banking_sector.add(bank2)

        nation.save_outputs(t=1)

        rows = sink._rows["macro"]
        assert rows[0]["total_bank_equity"] == pytest.approx(100.0 + 90.0, rel=1e-3)
        assert rows[0]["total_bad_debt"] == pytest.approx(5.0 + 3.0, rel=1e-3)


class TestUpdateStateForNextPeriod:
    """Test Nation.update_state_for_next_period() — state shifting."""

    def test_nation_level_scalars_shift(self):
        """Nation-level scalars should shift from current to prev."""
        nation = Nation(nation_id="test", params=NationParameters())

        # Set current values
        nation.cpi = 1.05
        nation.ppi = 1.03
        nation.total_dividends = 100.0

        # Call update
        nation.update_state_for_next_period()

        # Verify shifts
        assert nation.cpi_prev == 1.05
        assert nation.ppi_prev == 1.03
        assert nation.total_dividends_prev == 100.0

    def test_labour_market_state_shifts(self):
        """LabourMarket state variables should shift from current to prev."""
        nation = Nation(nation_id="test", params=NationParameters())
        lm = nation.labour_market

        # Set current values
        lm.wage = 2.0
        lm.unemployment_rate = 0.1
        lm.mean_machine_prod = 1.5
        lm.mean_process_prod = 1.2
        lm.labour_supply = 510_000.0

        # Call update
        nation.update_state_for_next_period()

        # Verify shifts
        assert lm.wage_prev == 2.0
        assert lm.unemployment_rate_prev == 0.1
        assert lm.mean_machine_prod_prev == 1.5
        assert lm.mean_process_prod_prev == 1.2
        assert lm.labour_supply_prev == 510_000.0

    def test_sector1_firm_state_shifts(self):
        """Sector-1 firm state should shift."""
        nation = Nation(nation_id="test", params=NationParameters())

        from dsk.agents.capital_good_firm import CapitalGoodFirm

        firm = CapitalGoodFirm(nation=nation, rng=np.random.default_rng(42))
        firm.market_share = 0.05
        firm.price = 10.0
        firm.sales = 50.0
        firm.net_worth = 200.0
        firm.debt = 50.0
        firm.process_labour_prod = 1.1
        firm.rd_budget = 5.0

        nation.capital_good_sector.add(firm)

        # Call update
        nation.update_state_for_next_period()

        # Verify shifts
        assert firm.market_share_prev == 0.05
        assert firm.price_prev == 10.0
        assert firm.sales_prev == 50.0
        assert firm.net_worth_prev == 200.0
        assert firm.debt_prev == 50.0
        assert firm.process_labour_prod_prev == 1.1
        assert firm.rd_budget_prev == 5.0

    def test_sector2_firm_state_shifts(self):
        """Sector-2 firm state should shift, including double-lag market share."""
        nation = Nation(nation_id="test", params=NationParameters())

        from dsk.agents.consumption_good_firm import ConsumptionGoodFirm

        firm = ConsumptionGoodFirm(nation=nation, rng=np.random.default_rng(42))
        firm.market_share = 0.08
        firm.market_share_prev = 0.07
        firm.price = 5.0
        firm.sales = 100.0
        firm.net_worth = 150.0
        firm.debt = 30.0
        firm.competitiveness = 1.1
        firm.demand = 120.0

        nation.consumption_good_sector.add(firm)

        # Call update
        nation.update_state_for_next_period()

        # Verify shifts
        assert firm.market_share_prev_prev == 0.07
        assert firm.market_share_prev == 0.08
        assert firm.price_prev == 5.0
        assert firm.sales_prev == 100.0
        assert firm.net_worth_prev == 150.0
        assert firm.debt_prev == 30.0
        assert firm.competitiveness_prev == 1.1
        assert firm.demand_prev == 120.0

    def test_counters_reset(self):
        """Per-step counters should be reset."""
        nation = Nation(nation_id="test", params=NationParameters())

        # Set some counter values
        nation.government.bailout_cost = 50.0
        nation.labour_market.labour_demand_total = 400_000.0
        nation.labour_market.labour_demand_s1 = 100_000.0
        nation.labour_market.labour_demand_s2 = 300_000.0
        nation.labour_market.labour_demand_rd = 10_000.0

        # Call update
        nation.update_state_for_next_period()

        # Verify resets
        assert nation.government.bailout_cost == 0.0
        assert nation.labour_market.labour_demand_total == 0.0
        assert nation.labour_market.labour_demand_s1 == 0.0
        assert nation.labour_market.labour_demand_s2 == 0.0
        assert nation.labour_market.labour_demand_rd == 0.0


class TestSaveUpdateIntegration:
    """Integration tests for SAVE + UPDATE across a full step."""

    def test_state_shifts_after_one_step(self):
        """After a step, previous-period state should match what it was before the step."""
        from dsk.agents.capital_good_firm import CapitalGoodFirm
        from dsk.agents.consumption_good_firm import ConsumptionGoodFirm

        gparams = GlobalParameters()
        nparams = NationParameters()

        # Create a minimal simulation
        nation = Nation(nation_id="test", params=nparams)
        nation.gparams = gparams

        # Initialize sectors (just add firms without full initialization)
        firm_s1 = CapitalGoodFirm(nation=nation, rng=np.random.default_rng(42))
        nation.capital_good_sector.add(firm_s1)

        firm_s2 = ConsumptionGoodFirm(nation=nation, rng=np.random.default_rng(43))
        nation.consumption_good_sector.add(firm_s2)

        nation.labour_market.initialise_from_parameters(gparams, nparams)

        # Snapshot state before the step
        wage_before = nation.labour_market.wage
        cpi_before = nation.cpi
        s1_market_share_before = firm_s1.market_share
        s2_sales_before = firm_s2.sales

        # Modify some values (simulating what a production/dynamics phase might do)
        nation.labour_market.wage = wage_before * 1.02
        nation.cpi = cpi_before * 1.005
        firm_s1.market_share = s1_market_share_before * 1.01
        firm_s2.sales = s2_sales_before * 1.05

        # Call update
        nation.update_state_for_next_period()

        # Verify that _prev values now match what was set (not what they were before)
        assert nation.labour_market.wage_prev == pytest.approx(wage_before * 1.02)
        assert nation.cpi_prev == pytest.approx(cpi_before * 1.005)
        assert firm_s1.market_share_prev == pytest.approx(s1_market_share_before * 1.01)
        assert firm_s2.sales_prev == pytest.approx(s2_sales_before * 1.05)

    def test_save_and_update_sequence(self, tmp_output_dir):
        """Test that save_outputs and update_state_for_next_period work together."""
        nation = Nation(nation_id="test", params=NationParameters())

        sink = OutputSink()
        nation.sink = sink
        nation._mc_run = 1

        # Set values for period 1
        nation.real_gdp = 100.0
        nation.cpi = 1.0
        nation.labour_market.wage = 1.0

        # Save period 1
        nation.save_outputs(t=1)
        assert sink.n_pending_rows("macro") == 1

        # Update for period 2
        nation.update_state_for_next_period()

        # Verify _prev values are set
        assert nation.cpi_prev == 1.0
        assert nation.labour_market.wage_prev == 1.0

        # Now simulate period 2: values change
        nation.real_gdp = 102.0
        nation.cpi = 1.02
        nation.labour_market.wage = 1.05

        # Save period 2
        nation.save_outputs(t=2)
        assert sink.n_pending_rows("macro") == 2

        # Verify both rows are in the sink
        rows = sink._rows["macro"]
        assert rows[0]["t"] == 1
        assert rows[0]["cpi"] == 1.0
        assert rows[1]["t"] == 2
        assert rows[1]["cpi"] == 1.02

    def test_multiple_steps_state_consistency(self):
        """Over multiple steps, _prev values should always reflect the previous period."""
        nation = Nation(nation_id="test", params=NationParameters())
        nation.labour_market.initialise_from_parameters(
            GlobalParameters(), NationParameters()
        )

        initial_wage = nation.labour_market.wage
        initial_wage_prev = nation.labour_market.wage_prev

        # Step 1: change wage
        nation.labour_market.wage = initial_wage * 1.05
        nation.update_state_for_next_period()
        assert nation.labour_market.wage_prev == pytest.approx(initial_wage * 1.05)

        # Step 2: change wage again
        nation.labour_market.wage = initial_wage * 1.05 * 1.03
        nation.update_state_for_next_period()
        assert nation.labour_market.wage_prev == pytest.approx(initial_wage * 1.05 * 1.03)

        # Step 3: verify consistency
        nation.labour_market.wage = initial_wage * 1.05 * 1.03 * 0.98
        nation.update_state_for_next_period()
        assert nation.labour_market.wage_prev == pytest.approx(
            initial_wage * 1.05 * 1.03 * 0.98
        )
