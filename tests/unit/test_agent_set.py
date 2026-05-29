"""Acceptance tests for Task 0.6 — Agent and AgentSet."""
import numpy as np
import pytest

from dsk.agent_set import AgentSet
from dsk.agents.agent import Agent


class DummyNation:
    """Minimal stand-in for Nation — enough for Agent.__init__."""
    pass


class DummyAgent(Agent):
    def __init__(self, nation, value: int) -> None:
        super().__init__(nation)
        self.value = int(value)

    def doubled(self) -> None:
        self.value = self.value * 2


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def nation():
    return DummyNation()


@pytest.fixture()
def ten_agents(nation):
    return [DummyAgent(nation, i) for i in range(10)]


@pytest.fixture()
def agent_set(ten_agents):
    return AgentSet(ten_agents)


# ---------------------------------------------------------------------------
# Basic collection behaviour
# ---------------------------------------------------------------------------

def test_len(agent_set):
    assert len(agent_set) == 10


def test_iter(agent_set, ten_agents):
    assert list(agent_set) == ten_agents


def test_add_remove(nation):
    s = AgentSet()
    a = DummyAgent(nation, 99)
    s.add(a)
    assert len(s) == 1
    s.remove(a)
    assert len(s) == 0


# ---------------------------------------------------------------------------
# unique_id auto-increment
# ---------------------------------------------------------------------------

def test_unique_ids_are_distinct(ten_agents):
    ids = [a.unique_id for a in ten_agents]
    assert len(set(ids)) == len(ids), "unique_ids must all differ"


# ---------------------------------------------------------------------------
# get / set round-trip (core acceptance criterion)
# ---------------------------------------------------------------------------

def test_set_then_get_round_trips(agent_set):
    values = np.arange(10, dtype=float)
    agent_set.set("value", values)
    result = agent_set.get("value")
    np.testing.assert_array_equal(result, values)


def test_get_returns_ndarray(agent_set):
    result = agent_set.get("value")
    assert isinstance(result, np.ndarray)


# ---------------------------------------------------------------------------
# select + do (core acceptance criterion)
# ---------------------------------------------------------------------------

def test_select_returns_correct_subset(agent_set):
    subset = agent_set.select(lambda a: a.value > 5)
    values = list(subset.get("value"))
    assert all(v > 5 for v in values)
    assert len(subset) == 4  # agents with value 6, 7, 8, 9


def test_do_calls_method_on_all(agent_set):
    agent_set.set("value", np.arange(10, dtype=float))
    agent_set.do("doubled")
    result = agent_set.get("value")
    expected = np.arange(10) * 2
    np.testing.assert_array_equal(result, expected)


def test_select_then_do(agent_set):
    agent_set.set("value", np.arange(10, dtype=float))
    subset = agent_set.select(lambda a: a.value > 5)
    subset.do("doubled")
    # Agents with original value > 5 (6,7,8,9) are doubled → 12,14,16,18
    vals = sorted(subset.get("value").tolist())
    assert vals == [12.0, 14.0, 16.0, 18.0]
    # Agents in original set with value ≤ 5 are unchanged
    low = agent_set.select(lambda a: a.value <= 5)
    low_vals = sorted(low.get("value").tolist())
    assert low_vals == [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]


# ---------------------------------------------------------------------------
# shuffle_do
# ---------------------------------------------------------------------------

def test_shuffle_do_calls_all_agents(agent_set):
    agent_set.set("value", np.zeros(10))
    # doubled() on 0 stays 0, so use a side-effect counter instead
    call_order = []
    for a in agent_set:
        original_doubled = a.doubled.__func__ if hasattr(a.doubled, '__func__') else None

    # Patch each agent to record call order
    called = []
    for a in agent_set:
        uid = a.unique_id
        original = a.doubled

        def make_recorder(u, orig):
            def recorder():
                called.append(u)
                orig()
            return recorder

        a.doubled = make_recorder(uid, original)

    agent_set.shuffle_do("doubled")
    assert len(called) == 10
    assert set(called) == {a.unique_id for a in agent_set}
