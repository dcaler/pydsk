"""Task 0.8 acceptance test: load baseline YAML, run 5 steps, assert parquet output."""
from pathlib import Path

import pandas as pd
import pytest

from dsk.io.config import load_simulation

CONFIGS_DIR = Path(__file__).parents[2] / "configs"
BASELINE_YAML = CONFIGS_DIR / "simulations" / "one_nation_baseline.yaml"


def test_load_baseline_yaml_builds_simulation():
    sim = load_simulation(BASELINE_YAML)
    assert sim is not None
    assert len(sim.nations) == 1
    assert sim.nations[0].nation_id == "global"
    assert sim.output_sink is not None
    assert sim.nations[0].sink is sim.output_sink


def test_run_five_steps_and_flush_parquet(tmp_output_dir):
    sim = load_simulation(BASELINE_YAML)
    sim.run(5)

    written = sim.flush(tmp_output_dir)

    assert len(written) > 0, "flush() should have written at least one parquet file"
    for table_name, path in written.items():
        assert path.exists(), f"{table_name}.parquet was not created"
        df = pd.read_parquet(path)
        assert len(df.columns) >= 1, f"{table_name}.parquet has no columns"
        assert len(df) > 0, f"{table_name}.parquet has no rows"


def test_parquet_has_required_context_columns(tmp_output_dir):
    sim = load_simulation(BASELINE_YAML)
    sim.run(3)
    written = sim.flush(tmp_output_dir)

    for table_name, path in written.items():
        df = pd.read_parquet(path)
        for col in ("mc_run", "t", "nation_id"):
            assert col in df.columns, f"Expected column '{col}' in {table_name}"


def test_parameters_loaded_from_yaml():
    sim = load_simulation(BASELINE_YAML)
    gp = sim.global_params
    assert gp.n1_capital_good_firms == 100
    assert gp.n2_consumption_good_firms == 400
    assert gp.total_steps == 220
