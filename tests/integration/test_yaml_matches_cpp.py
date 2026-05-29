"""Test that YAML config loading produces parameters matching C++ baseline."""
import pytest
from pathlib import Path

from dsk.io.config import load_simulation
from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters


@pytest.fixture
def config_dir():
    """Return the configs directory."""
    return Path(__file__).parent.parent.parent / "configs"


def test_global_params_from_yaml(config_dir):
    """Load global parameters from YAML and verify they match C++ baseline."""
    sim = load_simulation(config_dir / "simulations" / "one_nation_baseline.yaml")

    # Verify global parameters
    assert sim.global_params.n1_capital_good_firms == 100
    assert sim.global_params.n2_consumption_good_firms == 400
    assert sim.global_params.total_steps == 220
    assert sim.global_params.mc_runs == 5
    assert sim.global_params.spin_up_steps == 60
    assert sim.global_params.climate_start_step == 80
    assert sim.global_params.use_dskqe == 1  # Flag dsk_qe ON (per v3 Appendix B)

    # Spot-check some behavioral parameters
    assert sim.global_params.rd_budget_fraction == 0.04
    assert sim.global_params.patent_duration == 12.0
    assert sim.global_params.s1_markup == 0.04
    assert sim.global_params.wage_subsistence == 1.0


def test_nation_params_from_yaml(config_dir):
    """Load nation parameters from YAML and verify they match C++ baseline."""
    sim = load_simulation(config_dir / "simulations" / "one_nation_baseline.yaml")

    assert len(sim.nations) == 1
    nation = sim.nations[0]

    # Verify nation parameters — values match the C++ baseline runtime
    # overrides from `auxiliary/experiment_setting.cpp:103-129`, not the
    # placeholder defaults in `dsk_constant.h`.
    assert nation.params.n_banks == 10
    assert nation.params.unemployment_benefit_share == 0.7   # wu = 0.4 * 7/4
    assert nation.params.tax_rate_firms_wages == 0.1
    assert nation.params.tax_rate_banks == 0.1
    assert nation.params.deficit_rule == 0.03
    assert nation.params.policy_rate == 0.02                  # r overridden
    assert nation.params.taylor_rule_inflation_coef == 1.1
    assert nation.params.taylor_rule_unemployment_coef == 0.0
    assert nation.params.fossil_fuel_price == 0.02

    # Credit parameters — both doubled in the C++ baseline override
    assert nation.params.credit_multiplier == 0.16
    assert nation.params.s2_markup_init == 0.15


def test_yaml_dict_diff():
    """Verify that YAML parameters match dataclass defaults (no surprises)."""
    # This test loads the defaults from the dataclasses and checks they're
    # preserved through YAML round-trip

    defaults_global = GlobalParameters()
    defaults_nation = NationParameters()

    sim = load_simulation(
        Path(__file__).parent.parent.parent / "configs" / "simulations" / "one_nation_baseline.yaml"
    )

    # All global parameters should match defaults
    for attr in dir(defaults_global):
        if not attr.startswith("_"):
            default_val = getattr(defaults_global, attr)
            loaded_val = getattr(sim.global_params, attr)
            if not callable(default_val):
                assert default_val == loaded_val, (
                    f"GlobalParameters.{attr}: default={default_val}, loaded={loaded_val}"
                )

    # All nation parameters should match defaults
    nation = sim.nations[0]
    for attr in dir(defaults_nation):
        if not attr.startswith("_"):
            default_val = getattr(defaults_nation, attr)
            loaded_val = getattr(nation.params, attr)
            if not callable(default_val):
                assert default_val == loaded_val, (
                    f"NationParameters.{attr}: default={default_val}, loaded={loaded_val}"
                )


def test_master_seed_propagates():
    """Verify that master_seed from YAML is used by the simulation."""
    sim = load_simulation(
        Path(__file__).parent.parent.parent / "configs" / "simulations" / "one_nation_baseline.yaml"
    )

    # The master seed should result in deterministic nation RNGs
    assert sim.nations[0].rng is not None

    # Two identical loads should produce identical RNG streams
    sim1 = load_simulation(
        Path(__file__).parent.parent.parent / "configs" / "simulations" / "one_nation_baseline.yaml"
    )
    sim2 = load_simulation(
        Path(__file__).parent.parent.parent / "configs" / "simulations" / "one_nation_baseline.yaml"
    )

    # Draw a few random numbers to confirm identical streams
    r1 = [sim1.nations[0].rng.random() for _ in range(5)]
    r2 = [sim2.nations[0].rng.random() for _ in range(5)]
    assert r1 == r2


def test_yaml_completeness():
    """Verify that all YAML files exist and are non-empty."""
    config_dir = Path(__file__).parent.parent.parent / "configs"

    assert (config_dir / "global" / "default.yaml").exists()
    assert (config_dir / "nations" / "baseline.yaml").exists()
    assert (config_dir / "simulations" / "one_nation_baseline.yaml").exists()

    # Verify they're not empty
    assert (config_dir / "global" / "default.yaml").stat().st_size > 100
    assert (config_dir / "nations" / "baseline.yaml").stat().st_size > 100
    assert (config_dir / "simulations" / "one_nation_baseline.yaml").stat().st_size > 50
