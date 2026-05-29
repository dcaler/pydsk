"""Integration tests for Task 5.5 — ClimatePolicy orchestrator.

Acceptance criterion (IMPLEMENTATION_PLAN §5.5):
    Composing instruments (e.g. ban + subsidies + tax = BCERT) works through
    YAML config without code change.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
import yaml

from dsk.nation import Nation
from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters
from dsk.policy.brown_ban import BrownConstructionBan
from dsk.policy.carbon_tax import CarbonTax
from dsk.policy.climate_policy import ClimatePolicy, _INSTRUMENT_REGISTRY
from dsk.policy.electrification_mandate import ElectrificationMandate
from dsk.policy.green_subsidy import GreenConstructionSubsidy, GreenRDSubsidy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_nation(seed: int = 42, n1: int = 10, n2: int = 40, t_start: int = 5) -> Nation:
    gparams = GlobalParameters()
    gparams.n1_capital_good_firms = n1
    gparams.n2_consumption_good_firms = n2
    gparams.labour_supply_init = int(gparams.labour_supply_init * (n2 / 400.0))
    gparams.climate_start_step = t_start
    nparams = NationParameters()
    nation = Nation("policy-test", params=nparams)
    nation.rng = np.random.default_rng(seed)
    nation.initialise_from_parameters(gparams, nparams)
    return nation


# ---------------------------------------------------------------------------
# Class 1 — Basic orchestrator
# ---------------------------------------------------------------------------

class TestClimatePolicy:
    def test_empty_policy_applies_without_error(self):
        nation = _build_nation()
        cp = ClimatePolicy(nation)
        cp.apply(1)  # should not raise

    def test_active_instrument_is_called(self):
        nation = _build_nation()
        cp = ClimatePolicy(nation)
        mock = MagicMock()
        mock.is_active.return_value = True
        cp.add_instrument(mock)
        cp.apply(10)
        mock.apply.assert_called_once_with(nation, 10)

    def test_inactive_instrument_is_skipped(self):
        nation = _build_nation()
        cp = ClimatePolicy(nation)
        mock = MagicMock()
        mock.is_active.return_value = False
        cp.add_instrument(mock)
        cp.apply(10)
        mock.apply.assert_not_called()

    def test_multiple_instruments_called_in_order(self):
        nation = _build_nation()
        cp = ClimatePolicy(nation)
        calls = []

        class Recorder:
            def __init__(self, name):
                self.name = name
            def is_active(self, t):
                return True
            def apply(self, nation, t):
                calls.append(self.name)

        cp.add_instrument(Recorder("A"))
        cp.add_instrument(Recorder("B"))
        cp.add_instrument(Recorder("C"))
        cp.apply(1)
        assert calls == ["A", "B", "C"]

    def test_instruments_receive_correct_nation(self):
        nation = _build_nation()
        cp = ClimatePolicy(nation)
        received = []

        class NationCapture:
            def is_active(self, t): return True
            def apply(self, n, t): received.append(n)

        cp.add_instrument(NationCapture())
        cp.apply(1)
        assert received[0] is nation


# ---------------------------------------------------------------------------
# Class 2 — from_config factory
# ---------------------------------------------------------------------------

class TestClimatePolicyFromConfig:
    def test_empty_config_produces_no_instruments(self):
        nation = _build_nation()
        cp = ClimatePolicy.from_config([], nation)
        assert len(cp._instruments) == 0

    def test_carbon_tax_instantiated(self):
        nation = _build_nation()
        cp = ClimatePolicy.from_config(
            [{"type": "CarbonTax", "base_rate": 1e-4}], nation
        )
        assert len(cp._instruments) == 1
        assert isinstance(cp._instruments[0], CarbonTax)
        assert cp._instruments[0].base_rate == 1e-4

    def test_brown_ban_instantiated(self):
        nation = _build_nation()
        cp = ClimatePolicy.from_config(
            [{"type": "BrownConstructionBan", "invest_ban_offset": 15}], nation
        )
        assert isinstance(cp._instruments[0], BrownConstructionBan)
        assert cp._instruments[0].invest_ban_offset == 15

    def test_green_construction_subsidy_instantiated(self):
        nation = _build_nation()
        cp = ClimatePolicy.from_config(
            [{"type": "GreenConstructionSubsidy", "y_subs": 0.25}], nation
        )
        assert isinstance(cp._instruments[0], GreenConstructionSubsidy)
        assert cp._instruments[0].y_subs == 0.25

    def test_green_rd_subsidy_instantiated(self):
        nation = _build_nation()
        cp = ClimatePolicy.from_config(
            [{"type": "GreenRDSubsidy", "rd_topup_fraction": 0.5}], nation
        )
        assert isinstance(cp._instruments[0], GreenRDSubsidy)
        assert cp._instruments[0].rd_topup_fraction == 0.5

    def test_electrification_mandate_instantiated(self):
        nation = _build_nation()
        cp = ClimatePolicy.from_config(
            [{"type": "ElectrificationMandate", "enforcement_offset": 31}], nation
        )
        assert isinstance(cp._instruments[0], ElectrificationMandate)
        assert cp._instruments[0].enforcement_offset == 31

    def test_bcert_composition_all_instruments(self):
        """BCERT = Ban + Construction subsidy + Electrification mandate + R&D subsidy + Tax."""
        nation = _build_nation()
        bcert_cfg = [
            {"type": "CarbonTax", "schedule": "constant", "base_rate": 3.3e-4},
            {"type": "BrownConstructionBan", "invest_ban_offset": 21},
            {"type": "GreenConstructionSubsidy", "y_subs": 1.0 / 3.0},
            {"type": "GreenRDSubsidy", "rd_topup_fraction": 0.5},
            {"type": "ElectrificationMandate", "enforcement_offset": 31},
        ]
        cp = ClimatePolicy.from_config(bcert_cfg, nation)
        assert len(cp._instruments) == 5
        types = [type(i) for i in cp._instruments]
        assert CarbonTax in types
        assert BrownConstructionBan in types
        assert GreenConstructionSubsidy in types
        assert GreenRDSubsidy in types
        assert ElectrificationMandate in types

    def test_unknown_type_raises_value_error(self):
        nation = _build_nation()
        with pytest.raises(ValueError, match="Unknown policy instrument type"):
            ClimatePolicy.from_config([{"type": "FakePolicy"}], nation)

    def test_spec_dict_is_not_mutated(self):
        """from_config pops 'type' internally but must not mutate the caller's dict."""
        nation = _build_nation()
        spec = {"type": "CarbonTax", "base_rate": 2e-4}
        ClimatePolicy.from_config([spec], nation)
        assert "type" in spec  # original dict unchanged

    def test_returned_policy_has_correct_nation(self):
        nation = _build_nation()
        cp = ClimatePolicy.from_config([{"type": "CarbonTax"}], nation)
        assert cp.nation is nation

    def test_registry_covers_all_exported_instruments(self):
        """Every instrument exported from dsk.policy appears in the registry."""
        from dsk.policy import (
            CarbonTax, GreenConstructionSubsidy, GreenRDSubsidy,
            BrownConstructionBan, ElectrificationMandate,
        )
        for cls in (
            CarbonTax, GreenConstructionSubsidy, GreenRDSubsidy,
            BrownConstructionBan, ElectrificationMandate,
        ):
            assert cls.__name__ in _INSTRUMENT_REGISTRY
            assert _INSTRUMENT_REGISTRY[cls.__name__] is cls


# ---------------------------------------------------------------------------
# Class 3 — YAML roundtrip via load_simulation
# ---------------------------------------------------------------------------

class TestClimatePolicyYAMLRoundtrip:
    def _write_sim_yaml(self, tmp_path: Path, policy_list: list) -> Path:
        """Write a minimal simulation YAML with the given policy list."""
        (tmp_path / "global.yaml").write_text(
            "n1_capital_good_firms: 10\nn2_consumption_good_firms: 40\n"
        )
        (tmp_path / "nation.yaml").write_text("")
        sim_cfg = {
            "master_seed": 1,
            "global": "global.yaml",
            "nations": [{"id": "test", "config": "nation.yaml", "policy": policy_list}],
            "trade": {"enabled": False},
            "climate": {"shared": True},
        }
        sim_path = tmp_path / "sim.yaml"
        sim_path.write_text(yaml.dump(sim_cfg))
        return sim_path

    def test_baseline_yaml_has_empty_policy(self, tmp_path):
        from dsk.io.config import load_simulation
        sim_path = self._write_sim_yaml(tmp_path, [])
        sim = load_simulation(sim_path)
        assert len(sim.nations[0].climate_policy._instruments) == 0

    def test_single_carbon_tax_from_yaml(self, tmp_path):
        from dsk.io.config import load_simulation
        sim_path = self._write_sim_yaml(
            tmp_path,
            [{"type": "CarbonTax", "base_rate": 5.0e-4, "schedule": "constant"}],
        )
        sim = load_simulation(sim_path)
        instruments = sim.nations[0].climate_policy._instruments
        assert len(instruments) == 1
        assert isinstance(instruments[0], CarbonTax)
        assert instruments[0].base_rate == pytest.approx(5e-4)

    def test_bcert_from_yaml(self, tmp_path):
        """BCERT composition through YAML produces five instruments, no code change needed."""
        from dsk.io.config import load_simulation
        bcert_policy = [
            {"type": "CarbonTax", "schedule": "constant", "base_rate": 3.3e-4},
            {"type": "BrownConstructionBan", "invest_ban_offset": 21},
            {"type": "GreenConstructionSubsidy", "y_subs": 0.333},
            {"type": "GreenRDSubsidy", "rd_topup_fraction": 0.5},
            {"type": "ElectrificationMandate", "enforcement_offset": 31},
        ]
        sim_path = self._write_sim_yaml(tmp_path, bcert_policy)
        sim = load_simulation(sim_path)
        instruments = sim.nations[0].climate_policy._instruments
        assert len(instruments) == 5
        types = {type(i) for i in instruments}
        assert types == {
            CarbonTax, BrownConstructionBan, GreenConstructionSubsidy,
            GreenRDSubsidy, ElectrificationMandate,
        }

    def test_bcert_instruments_affect_nation_when_applied(self, tmp_path):
        """After loading BCERT YAML, apply() must reach the instruments."""
        from dsk.io.config import load_simulation
        sim_path = self._write_sim_yaml(
            tmp_path,
            [
                {"type": "CarbonTax", "schedule": "constant", "base_rate": 3.3e-4},
                {"type": "BrownConstructionBan", "invest_ban_offset": 1, "t_start": 1},
            ],
        )
        sim = load_simulation(sim_path)
        nation = sim.nations[0]
        nation.rng = np.random.default_rng(0)
        nation.initialise_from_parameters(sim.global_params, nation.params)
        # Apply at t=10 — well past t_start=1, ban should fire
        nation.climate_policy.apply(10)
        ep = nation.electricity_producer
        # invest_ban_offset=1 → ban year = 1+1 = 2; t=10 > 2, so EP has the ban set
        assert ep.brown_invest_ban_year <= 2
