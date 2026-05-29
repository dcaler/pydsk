"""Tests for RNG infrastructure (Task 0.5)."""
import numpy as np
import pytest

from dsk.rng import make_master_rng, spawn_nation_rng


def test_make_master_rng_returns_seed_sequence():
    from numpy.random import SeedSequence
    master = make_master_rng(42)
    assert isinstance(master, SeedSequence)
    assert master.entropy == 42


def test_same_seed_same_nation_identical_draws():
    """Core acceptance criterion: two fresh constructions with same inputs → same stream."""
    draws1 = spawn_nation_rng(make_master_rng(42), "north").random(10)
    draws2 = spawn_nation_rng(make_master_rng(42), "north").random(10)
    np.testing.assert_array_equal(draws1, draws2)


def test_integer_nation_id_identical_draws():
    draws1 = spawn_nation_rng(make_master_rng(7), 0).random(10)
    draws2 = spawn_nation_rng(make_master_rng(7), 0).random(10)
    np.testing.assert_array_equal(draws1, draws2)


def test_different_seeds_different_draws():
    draws1 = spawn_nation_rng(make_master_rng(42), "north").random(10)
    draws2 = spawn_nation_rng(make_master_rng(99), "north").random(10)
    assert not np.array_equal(draws1, draws2)


def test_different_nation_ids_different_draws():
    master = make_master_rng(42)
    draws1 = spawn_nation_rng(master, "north").random(10)
    draws2 = spawn_nation_rng(master, "south").random(10)
    assert not np.array_equal(draws1, draws2)


def test_spawn_order_independent():
    """Spawning nations in different orders must not change either nation's stream."""
    master_a = make_master_rng(42)
    draws_north_first = spawn_nation_rng(master_a, "north").random(10)
    draws_south_second = spawn_nation_rng(master_a, "south").random(10)

    master_b = make_master_rng(42)
    draws_south_first = spawn_nation_rng(master_b, "south").random(10)
    draws_north_second = spawn_nation_rng(master_b, "north").random(10)

    np.testing.assert_array_equal(draws_north_first, draws_north_second)
    np.testing.assert_array_equal(draws_south_first, draws_south_second)


def test_independent_generators_do_not_share_state():
    """Advancing one nation's RNG must not affect another's draws."""
    master = make_master_rng(42)
    rng_north = spawn_nation_rng(master, "north")
    rng_south = spawn_nation_rng(master, "south")

    # Record south's first draw before touching north
    south_before = rng_south.random(10)

    # Advance north heavily
    rng_north.random(10_000)

    # Re-spawn south fresh and compare
    south_fresh = spawn_nation_rng(make_master_rng(42), "south").random(10)
    np.testing.assert_array_equal(south_before, south_fresh)
