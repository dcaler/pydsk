"""Task 0.7 acceptance test: Simulation harness runs without raising."""
import pytest

from dsk.nation import Nation
from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters
from dsk.simulation import Simulation


def _make_sim(seed: int = 0, total_steps: int = 5) -> Simulation:
    params = NationParameters()
    nation = Nation(nation_id="baseline", params=params)
    return Simulation(
        global_params=GlobalParameters(),
        nations=[nation],
        rng_seed=seed,
    )


def test_simulation_constructs_without_error():
    sim = _make_sim()
    assert sim.t == 0
    assert len(sim.nations) == 1


def test_run_five_steps_does_not_raise():
    sim = _make_sim()
    sim.run(5)
    assert sim.t == 5


def test_nation_rng_assigned_after_construction():
    sim = _make_sim(seed=42)
    nation = sim.nations[0]
    assert nation.rng is not None


def test_multiple_nations_run_without_error():
    nation_a = Nation(nation_id="north", params=NationParameters())
    nation_b = Nation(nation_id="south", params=NationParameters())
    sim = Simulation(
        global_params=GlobalParameters(),
        nations=[nation_a, nation_b],
        rng_seed=7,
    )
    sim.run(5)
    assert sim.t == 5


def test_step_increments_t():
    sim = _make_sim()
    for expected in range(1, 4):
        sim.step()
        assert sim.t == expected
