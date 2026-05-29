"""Config loader — build a Simulation from a YAML scenario file.

Scenario YAML format (paths are relative to the YAML file's directory):

    master_seed: 42
    global: ../global/default.yaml
    nations:
      - id: global
        config: ../nations/baseline.yaml
        policy: []
    trade:
      enabled: false
    climate:
      shared: true

The ``global`` and nation ``config`` YAMLs use Python attribute names from
``GlobalParameters`` and ``NationParameters``.  Unknown keys are silently
ignored; missing keys use dataclass defaults.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

import yaml

from dsk.io.output_sink import OutputSink
from dsk.nation import Nation
from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters
from dsk.policy.climate_policy import ClimatePolicy
from dsk.simulation import Simulation


def _load_yaml(path: Path) -> dict:
    with open(path) as fh:
        return yaml.safe_load(fh) or {}


def _build_params(cls, yaml_dict: dict):
    """Construct *cls* (a dataclass) from *yaml_dict*, ignoring unknown keys."""
    known = {f.name for f in dataclasses.fields(cls)}
    filtered = {k: v for k, v in yaml_dict.items() if k in known}
    return cls(**filtered)


def load_simulation(yaml_path: "str | Path") -> Simulation:
    """Return a fully wired :class:`~dsk.simulation.Simulation` from *yaml_path*.

    Side-effects:
    - Constructs an :class:`~dsk.io.output_sink.OutputSink` and attaches it to
      ``simulation.output_sink`` and to ``nation.sink`` for every nation.
    - Assigns per-nation RNGs (via ``Simulation.__init__``).
    """
    yaml_path = Path(yaml_path).resolve()
    sim_dir = yaml_path.parent
    sim_cfg = _load_yaml(yaml_path)

    # --- Global parameters ---
    global_yaml_ref = sim_cfg.get("global")
    if global_yaml_ref:
        global_dict = _load_yaml((sim_dir / global_yaml_ref).resolve())
    else:
        global_dict = {}
    global_params = _build_params(GlobalParameters, global_dict)

    # --- Nations ---
    nations: list[Nation] = []
    for nc in sim_cfg.get("nations", []):
        nation_id = nc.get("id", "default")
        nation_yaml_ref = nc.get("config")
        if nation_yaml_ref:
            nation_dict = _load_yaml((sim_dir / nation_yaml_ref).resolve())
        else:
            nation_dict = {}
        nation_params = _build_params(NationParameters, nation_dict)
        nation = Nation(nation_id=nation_id, params=nation_params)
        policy_cfg = nc.get("policy") or []
        if policy_cfg:
            nation.climate_policy = ClimatePolicy.from_config(policy_cfg, nation)
        nations.append(nation)

    if not nations:
        nations = [Nation(nation_id="default")]

    master_seed = sim_cfg.get("master_seed", 0)
    rng_mode = sim_cfg.get("rng_mode", "stochastic")
    sim = Simulation(
        global_params=global_params,
        nations=nations,
        rng_seed=master_seed,
        rng_mode=rng_mode,
    )

    # Wire the shared output sink to every nation
    sink = OutputSink()
    sim.output_sink = sink
    for nation in sim.nations:
        nation.sink = sink

    return sim
