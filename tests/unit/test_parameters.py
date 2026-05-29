"""Tests for GlobalParameters and NationParameters dataclasses."""
import pytest
from dsk.parameters import GlobalParameters, NationParameters


def test_global_parameters_instantiate_with_defaults():
    gp = GlobalParameters()
    assert gp is not None


def test_global_simulation_dimensions():
    gp = GlobalParameters()
    assert gp.n1_capital_good_firms == 100
    assert gp.n2_consumption_good_firms == 400
    assert gp.total_steps == 220
    assert gp.mc_runs == 5
    assert gp.spin_up_steps == 60
    assert gp.climate_start_step == gp.spin_up_steps + 20


def test_global_payback_threshold_derived():
    gp = GlobalParameters()
    assert gp.payback_threshold == 5 * gp.machine_size_units


def test_global_fossil_fuel_price_init():
    gp = GlobalParameters()
    assert abs(gp.fossil_fuel_price_init - 0.03 / 1.5) < 1e-12


def test_global_inflation_target():
    gp = GlobalParameters()
    assert abs(gp.inflation_target - 0.02 / 4) < 1e-12


def test_global_climate_constants():
    gp = GlobalParameters()
    assert gp.atmos_carbon_pre_ind == 590.0
    assert gp.climate_call_frequency == 1
    assert gp.dt_economy_years == 1.0
    assert gp.n_ocean_layers == 5
    assert len(gp.ocean_layer_depths_m) == 5


def test_global_flags_baseline():
    gp = GlobalParameters()
    assert gp.use_dskqe == 1
    assert gp.enable_climate_tech == 1
    assert gp.use_mark_to_market == 0
    assert gp.taylor_rule_variant == 2
    assert gp.wage_rule == 3
    assert gp.total_credit_rule == 2
    assert gp.bailout_rule == 0


def test_global_parameters_mutable():
    gp = GlobalParameters()
    gp.n1_capital_good_firms = 50
    assert gp.n1_capital_good_firms == 50


def test_global_carbon_tax_revenue_allocation_defaults():
    gp = GlobalParameters()
    assert gp.carbon_tax_revenue_allocation == [0.0, 0.0, 0.0, 1.0]


def test_global_ocean_init_lists_are_independent():
    gp1 = GlobalParameters()
    gp2 = GlobalParameters()
    gp1.ocean_layer_depths_m.append(999)
    assert len(gp2.ocean_layer_depths_m) == 5


def test_nation_parameters_instantiate_with_defaults():
    np_ = NationParameters()
    assert np_ is not None


def test_nation_parameters_values():
    """Defaults match the C++ baseline overrides from
    `auxiliary/experiment_setting.cpp::EXPERIMENT_INITIALIZE` lines
    103-129 (the `if (experiment == 0)` branch), not the placeholder
    values declared in `dsk_constant.h`.  See the NationParameters
    docstring."""
    np_ = NationParameters()
    assert np_.n_banks == 10
    assert np_.unemployment_benefit_share == 0.7   # wu = 0.4 * 7/4
    assert np_.tax_rate_firms_wages == 0.1
    assert np_.tax_rate_banks == 0.1
    assert np_.policy_rate == 0.02                  # r overridden from 0.025
    assert np_.deficit_rule == 0.03
    assert np_.s2_markup_init == 0.15               # mi2 overridden from 0.2
    assert np_.wage_inflation_response == 0.05
    assert np_.wage_unemployment_response == 0.1    # psi3 = 0.05 * 2
    assert np_.credit_multiplier == 0.16            # 0.08 * 2
    assert np_.bank_reserve_requirement_rate == np_.credit_multiplier


def test_nation_parameters_fossil_fuel_price():
    np_ = NationParameters()
    assert abs(np_.fossil_fuel_price - 0.02) < 1e-12


def test_nation_parameters_mutable():
    np_ = NationParameters()
    np_.policy_rate = 0.05
    assert np_.policy_rate == 0.05
