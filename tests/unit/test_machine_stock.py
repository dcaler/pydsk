"""Acceptance tests for Task 1.2 — MachineStock and Technology value object."""
import numpy as np
import pytest

from dsk.agents.machine_stock import MachineStock
from dsk.agents.technology import Technology


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

N_SUPPLIERS = 10


@pytest.fixture()
def stock():
    return MachineStock(n_suppliers=N_SUPPLIERS)


@pytest.fixture()
def tech_a():
    return Technology(labour_productivity=2.0, energy_efficiency=1.5,
                      env_cleanliness=0.8, electrification_fraction=0.3)


@pytest.fixture()
def tech_b():
    return Technology(labour_productivity=4.0)


# ---------------------------------------------------------------------------
# Technology value object
# ---------------------------------------------------------------------------

def test_technology_defaults():
    t = Technology()
    assert t.labour_productivity == 1.0
    assert t.energy_efficiency == 1.0
    assert t.env_cleanliness == 1.0
    assert t.electrification_fraction == 0.0


def test_technology_is_frozen():
    t = Technology(labour_productivity=2.0)
    with pytest.raises((AttributeError, TypeError)):
        t.labour_productivity = 3.0


def test_technology_equality():
    assert Technology(2.0) == Technology(2.0)
    assert Technology(2.0) != Technology(3.0)


# ---------------------------------------------------------------------------
# Acceptance criterion 1: add + count_at
# ---------------------------------------------------------------------------

def test_add_machines_count_at(stock, tech_a):
    """Add 10 machines of vintage 5 from supplier 3; assert count == 10."""
    stock.add_machines(vintage_key=5, supplier_idx=3, count=10, technology=tech_a)
    assert stock.count_at(5, 3) == 10.0


def test_count_at_absent_vintage_returns_zero(stock):
    assert stock.count_at(99, 0) == 0.0


def test_count_at_absent_supplier_returns_zero(stock, tech_a):
    stock.add_machines(vintage_key=1, supplier_idx=2, count=5, technology=tech_a)
    assert stock.count_at(1, 7) == 0.0


# ---------------------------------------------------------------------------
# Acceptance criterion 2: aggregate effective productivity
# ---------------------------------------------------------------------------

def test_effective_productivity_single_vintage(stock, tech_a):
    """All machines same productivity → effective_productivity equals that value."""
    stock.add_machines(vintage_key=5, supplier_idx=3, count=10, technology=tech_a)
    # harmonic mean of [2.0, 2.0, ...] = 2.0
    assert stock.effective_labour_productivity() == pytest.approx(2.0)


def test_effective_productivity_harmonic_mean(stock):
    """Two groups: 10 machines at prod=2.0 and 5 machines at prod=4.0.

    Expected A2 = 1 / ((1/2 * 10 + 1/4 * 5) / 15)
               = 1 / ((5.0 + 1.25) / 15)
               = 1 / (6.25 / 15)
               = 1 / 0.4167 ≈ 2.4
    """
    tech2 = Technology(labour_productivity=2.0)
    tech4 = Technology(labour_productivity=4.0)
    stock.add_machines(vintage_key=5, supplier_idx=3, count=10, technology=tech2)
    stock.add_machines(vintage_key=5, supplier_idx=7, count=5, technology=tech4)
    expected = 1.0 / ((10 / 2.0 + 5 / 4.0) / 15)
    assert stock.effective_labour_productivity() == pytest.approx(expected, rel=1e-9)


def test_effective_productivity_multiple_vintages(stock):
    """Machines from different vintages contribute to the same harmonic mean."""
    tech1 = Technology(labour_productivity=2.0)
    tech2 = Technology(labour_productivity=8.0)
    stock.add_machines(vintage_key=1, supplier_idx=0, count=4, technology=tech1)
    stock.add_machines(vintage_key=2, supplier_idx=0, count=4, technology=tech2)
    # A2 = 1 / ((4/2.0 + 4/8.0) / 8) = 1 / ((2 + 0.5) / 8) = 1 / 0.3125 = 3.2
    expected = 1.0 / ((4 / 2.0 + 4 / 8.0) / 8)
    assert stock.effective_labour_productivity() == pytest.approx(expected, rel=1e-9)


def test_effective_productivity_empty_stock_returns_zero(stock):
    assert stock.effective_labour_productivity() == 0.0


# ---------------------------------------------------------------------------
# total_machines
# ---------------------------------------------------------------------------

def test_total_machines_empty(stock):
    assert stock.total_machines() == 0.0


def test_total_machines_accumulates(stock, tech_a):
    stock.add_machines(vintage_key=1, supplier_idx=0, count=10, technology=tech_a)
    stock.add_machines(vintage_key=2, supplier_idx=2, count=5, technology=tech_a)
    assert stock.total_machines() == 15.0


def test_add_to_same_slot_accumulates_count(stock, tech_a):
    """Multiple calls to add_machines on the same slot accumulate the count."""
    stock.add_machines(vintage_key=1, supplier_idx=0, count=3, technology=tech_a)
    stock.add_machines(vintage_key=1, supplier_idx=0, count=7, technology=tech_a)
    assert stock.count_at(1, 0) == 10.0


# ---------------------------------------------------------------------------
# remove_machines
# ---------------------------------------------------------------------------

def test_remove_machines_zeros_count(stock, tech_a):
    stock.add_machines(vintage_key=3, supplier_idx=5, count=8, technology=tech_a)
    stock.remove_machines(vintage_key=3, supplier_idx=5)
    assert stock.count_at(3, 5) == 0.0


def test_remove_machines_zeros_age(stock, tech_a):
    stock.add_machines(vintage_key=3, supplier_idx=5, count=8, technology=tech_a, age=10.0)
    stock.remove_machines(vintage_key=3, supplier_idx=5)
    row = stock.row_for(3)
    assert stock.age[row, 5] == 0.0


def test_remove_absent_vintage_is_noop(stock):
    # Should not raise
    stock.remove_machines(vintage_key=99, supplier_idx=0)


def test_effective_productivity_excludes_scrapped_machines(stock):
    tech2 = Technology(labour_productivity=2.0)
    tech4 = Technology(labour_productivity=4.0)
    stock.add_machines(vintage_key=1, supplier_idx=0, count=10, technology=tech2)
    stock.add_machines(vintage_key=2, supplier_idx=0, count=10, technology=tech4)
    stock.remove_machines(vintage_key=1, supplier_idx=0)
    # Only vintage-2 machines remain; harmonic mean of [4.0] = 4.0
    assert stock.effective_labour_productivity() == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# increment_ages
# ---------------------------------------------------------------------------

def test_increment_ages_non_zero_slots(stock, tech_a):
    stock.add_machines(vintage_key=1, supplier_idx=0, count=5, technology=tech_a, age=3.0)
    stock.add_machines(vintage_key=2, supplier_idx=1, count=0, technology=tech_a, age=0.0)
    stock.increment_ages()
    row1 = stock.row_for(1)
    row2 = stock.row_for(2)
    assert stock.age[row1, 0] == 4.0   # had count > 0 → incremented
    assert stock.age[row2, 1] == 0.0   # had count == 0 → unchanged


def test_increment_ages_multiple_times(stock, tech_a):
    stock.add_machines(vintage_key=1, supplier_idx=0, count=1, technology=tech_a, age=0.0)
    for _ in range(5):
        stock.increment_ages()
    assert stock.age[stock.row_for(1), 0] == 5.0


# ---------------------------------------------------------------------------
# vintage_keys and row_for
# ---------------------------------------------------------------------------

def test_vintage_keys_in_insertion_order(stock, tech_a):
    stock.add_machines(vintage_key=10, supplier_idx=0, count=1, technology=tech_a)
    stock.add_machines(vintage_key=3, supplier_idx=0, count=1, technology=tech_a)
    stock.add_machines(vintage_key=7, supplier_idx=0, count=1, technology=tech_a)
    assert stock.vintage_keys == [10, 3, 7]


def test_row_for_absent_returns_none(stock):
    assert stock.row_for(99) is None


def test_arrays_have_correct_shape_after_insertions(stock, tech_a):
    stock.add_machines(vintage_key=1, supplier_idx=0, count=1, technology=tech_a)
    stock.add_machines(vintage_key=2, supplier_idx=0, count=1, technology=tech_a)
    assert stock.count.shape == (2, N_SUPPLIERS)
    assert stock.labour_productivity.shape == (2, N_SUPPLIERS)


# ---------------------------------------------------------------------------
# Technology properties stored correctly
# ---------------------------------------------------------------------------

def test_technology_properties_stored(stock, tech_a):
    """After add_machines, all Technology fields are stored in the arrays."""
    stock.add_machines(vintage_key=5, supplier_idx=3, count=10, technology=tech_a)
    row = stock.row_for(5)
    assert stock.labour_productivity[row, 3] == pytest.approx(tech_a.labour_productivity)
    assert stock.energy_efficiency[row, 3] == pytest.approx(tech_a.energy_efficiency)
    assert stock.env_cleanliness[row, 3] == pytest.approx(tech_a.env_cleanliness)
    assert stock.electrification_fraction[row, 3] == pytest.approx(tech_a.electrification_fraction)


def test_age_set_at_add_time(stock, tech_a):
    stock.add_machines(vintage_key=5, supplier_idx=3, count=10, technology=tech_a, age=7.0)
    row = stock.row_for(5)
    assert stock.age[row, 3] == 7.0
