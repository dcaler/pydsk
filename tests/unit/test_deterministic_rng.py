"""Tests for the noise-off DeterministicGenerator and rng_mode wiring.

These pin the property that under ``rng_mode='deterministic'`` the
simulation produces bit-identical outputs across runs.  This is the
foundation of the M1 root-cause trace (see ``planningDocs/M1_DEBUG_PLAN.md``
Step 2 and Step 6).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from dsk.io.config import load_simulation
from dsk.io.output_sink import OutputSink
from dsk.rng import DeterministicGenerator, make_deterministic_rng
from dsk.simulation import Simulation


# ---------------------------------------------------------------------------
# Generator-level tests
# ---------------------------------------------------------------------------


class TestDeterministicGeneratorReturnsExpectedValues:
    def test_uniform_returns_midpoint(self):
        g = DeterministicGenerator()
        assert g.uniform() == 0.5
        assert g.uniform(0.0, 1.0) == 0.5
        assert g.uniform(2.0, 4.0) == 3.0

    def test_normal_returns_loc(self):
        g = DeterministicGenerator()
        assert g.normal() == 0.0
        assert g.normal(loc=1.5) == 1.5
        assert g.normal(loc=-3.0, scale=10.0) == -3.0

    def test_binomial_returns_majority_outcome(self):
        g = DeterministicGenerator()
        # n=1: 1 if p>=0.5 else 0
        assert g.binomial(1, 0.7) == 1
        assert g.binomial(1, 0.5) == 1
        assert g.binomial(1, 0.49) == 0
        assert g.binomial(1, 0.0) == 0
        # n=3: same rule scaled
        assert g.binomial(3, 0.8) == 3
        assert g.binomial(3, 0.2) == 0

    def test_beta_returns_alpha_over_alpha_plus_beta(self):
        g = DeterministicGenerator()
        assert g.beta(3, 3) == 0.5
        assert g.beta(2, 4) == pytest.approx(1.0 / 3.0)
        assert g.beta(1, 9) == pytest.approx(0.1)

    def test_integers_round_robins(self):
        g = DeterministicGenerator()
        # integers(0, 3) walks 0, 1, 2, 0, 1, 2, ...
        seen = [g.integers(0, 3) for _ in range(7)]
        assert seen == [0, 1, 2, 0, 1, 2, 0]

    def test_integers_distinct_calls_distinct_values(self):
        """The whole point of round-robin: avoid degenerate clumping."""
        g = DeterministicGenerator()
        values = [g.integers(0, 100) for _ in range(50)]
        assert len(set(values)) == 50

    def test_shuffle_is_noop(self):
        g = DeterministicGenerator()
        x = [3, 1, 2]
        g.shuffle(x)
        assert x == [3, 1, 2]

    def test_choice_returns_first_element(self):
        g = DeterministicGenerator()
        assert g.choice([10, 20, 30]) == 10
        assert g.choice(5) == 0  # arange(5)[0]


# ---------------------------------------------------------------------------
# Property: two deterministic-mode runs are bit-identical
# ---------------------------------------------------------------------------


class TestDeterministicRunRoundTrip:
    """Two Python runs in deterministic mode produce identical outputs."""

    @staticmethod
    def _run_deterministic_simulation(t_max: int = 5) -> pd.DataFrame:
        sim = load_simulation("configs/simulations/one_nation_baseline.yaml")
        gp = sim.global_params
        # Small footprint for fast tests
        gp.n1_capital_good_firms = 50
        gp.n2_consumption_good_firms = 200
        gp.n1_foreign_firms = 50
        gp.labour_supply_init = 250_000.0
        # Re-wire deterministic generators per-nation. (load_simulation
        # already set them from the YAML default, but the configs/ baseline
        # does not yet carry an rng_mode entry, so we set it explicitly.)
        for nation in sim.nations:
            nation.rng = make_deterministic_rng()
            nation.gparams = gp
            nation._mc_run = 0

        sink = OutputSink()
        sim.output_sink = sink
        for nation in sim.nations:
            nation.sink = sink
            nation.initialise_from_parameters(gp)

        for _ in range(t_max):
            sim.step()

        rows = sink._rows["macro"]
        return pd.DataFrame(rows)

    def test_two_runs_produce_identical_macro_frames(self):
        df1 = self._run_deterministic_simulation(t_max=5)
        df2 = self._run_deterministic_simulation(t_max=5)
        pd.testing.assert_frame_equal(df1, df2, check_exact=True)

    def test_two_runs_produce_identical_gdp_trajectory(self):
        df1 = self._run_deterministic_simulation(t_max=10)
        df2 = self._run_deterministic_simulation(t_max=10)
        # Bit-equal float comparison (no tolerance)
        np.testing.assert_array_equal(
            df1["gdp_real"].to_numpy(),
            df2["gdp_real"].to_numpy(),
        )

    def test_deterministic_mode_produces_nonzero_output(self):
        """Sanity: deterministic mode is not pathologically degenerate."""
        df = self._run_deterministic_simulation(t_max=3)
        assert (df["gdp_real"] > 0).all()
        assert (df["wage"] > 0).all()


# ---------------------------------------------------------------------------
# Simulation.__init__ accepts and propagates rng_mode
# ---------------------------------------------------------------------------


class TestSimulationRngMode:
    def test_default_mode_is_stochastic(self):
        sim = load_simulation("configs/simulations/one_nation_baseline.yaml")
        assert sim.rng_mode == "stochastic"
        # Nation gets a real numpy Generator
        for nation in sim.nations:
            assert not isinstance(nation.rng, DeterministicGenerator)

    def test_deterministic_mode_replaces_nation_rngs(self):
        from dsk.parameters.global_parameters import GlobalParameters
        from dsk.nation import Nation
        sim = Simulation(
            global_params=GlobalParameters(),
            nations=[Nation(nation_id="test")],
            rng_seed=42,
            rng_mode="deterministic",
        )
        assert sim.rng_mode == "deterministic"
        for nation in sim.nations:
            assert isinstance(nation.rng, DeterministicGenerator)

    def test_invalid_rng_mode_raises(self):
        from dsk.parameters.global_parameters import GlobalParameters
        from dsk.nation import Nation
        with pytest.raises(ValueError, match="rng_mode"):
            Simulation(
                global_params=GlobalParameters(),
                nations=[Nation(nation_id="test")],
                rng_mode="nonsense",
            )
