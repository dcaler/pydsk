from __future__ import annotations

import random
from typing import Any, Callable, Iterable, Iterator

import numpy as np


class AgentSet:
    """Mesa-3-compatible collection of agents.

    Supports Mesa 3's vocabulary (do, shuffle_do, select, get, set) without
    depending on the mesa package at runtime.
    """

    def __init__(self, agents: list | None = None) -> None:
        self._agents: list = list(agents) if agents is not None else []

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add(self, agent) -> None:
        self._agents.append(agent)

    def remove(self, agent) -> None:
        self._agents.remove(agent)

    # ------------------------------------------------------------------
    # Iteration
    # ------------------------------------------------------------------

    def __iter__(self) -> Iterator:
        return iter(self._agents)

    def __len__(self) -> int:
        return len(self._agents)

    # ------------------------------------------------------------------
    # Mesa 3 core API
    # ------------------------------------------------------------------

    def do(self, method_name: str, *args: Any, **kwargs: Any) -> None:
        """Call `method_name(*args, **kwargs)` on every agent in order."""
        for agent in self._agents:
            getattr(agent, method_name)(*args, **kwargs)

    def shuffle_do(self, method_name: str, *args: Any, **kwargs: Any) -> None:
        """Call `method_name` on every agent in a uniformly random order."""
        order = list(self._agents)
        random.shuffle(order)
        for agent in order:
            getattr(agent, method_name)(*args, **kwargs)

    def select(self, predicate: Callable) -> "AgentSet":
        """Return a new AgentSet containing only agents for which predicate is True."""
        return AgentSet([a for a in self._agents if predicate(a)])

    def get(self, attribute: str) -> np.ndarray:
        """Return a numpy array of `attribute` values across all agents."""
        return np.fromiter(
            (getattr(a, attribute) for a in self._agents),
            dtype=float,
            count=len(self._agents),
        )

    def set(self, attribute: str, values: np.ndarray) -> None:
        """Set `attribute` on each agent from the corresponding element of `values`."""
        for agent, value in zip(self._agents, values):
            setattr(agent, attribute, value)
