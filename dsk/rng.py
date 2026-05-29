"""RNG infrastructure for the DSK Python port.

Two modes:

- **Stochastic** (the default; for the verification gate and production
  runs): per-nation `numpy.random.Generator` derived from a master
  `SeedSequence` so runs are reproducible given a seed.

- **Deterministic**: a duck-typed `Generator` subset whose methods
  return the expected value of the distribution (or a round-robin
  walk for `integers`).  Eliminates Monte-Carlo noise from the model
  so two Python runs in deterministic mode produce bit-identical
  outputs, which is the entry point for the M1 root-cause trace —
  see `planningDocs/M1_DEBUG_PLAN.md` Step 2 and `RNG_AUDIT.md` §D.

The deterministic generator implements only the methods we actually
call in the M1 baseline: `integers`, `binomial`, `beta`, `uniform`,
`shuffle`, `normal`, `choice`.  Adding more is mechanical — see
`DeterministicGenerator.__doc__` for the convention.
"""
from __future__ import annotations

import hashlib
from typing import Any, Sequence

import numpy as np
from numpy.random import Generator, SeedSequence


# -----------------------------------------------------------------------------
# Stochastic mode — original API
# -----------------------------------------------------------------------------


def make_master_rng(seed: int) -> SeedSequence:
    """Return a master SeedSequence from an integer seed."""
    return SeedSequence(seed)


def _stable_hash(nation_id) -> int:
    """Return a stable 64-bit integer hash of nation_id, independent of PYTHONHASHSEED."""
    if isinstance(nation_id, int):
        return nation_id & 0xFFFFFFFFFFFFFFFF
    digest = hashlib.sha256(str(nation_id).encode()).digest()
    return int.from_bytes(digest[:8], "little")


def spawn_nation_rng(master: SeedSequence, nation_id) -> Generator:
    """Return a Generator deterministically derived from (master.entropy, nation_id).

    Order-independent: spawning 'north' before or after 'south' gives the same
    stream for each, because the nation_id is folded into the entropy rather than
    derived from a spawn-order index.
    """
    nation_bits = _stable_hash(nation_id)
    base = master.entropy if master.entropy is not None else 0
    if isinstance(base, (list, tuple)):
        child_entropy = list(base) + [nation_bits]
    else:
        child_entropy = [int(base), nation_bits]
    return np.random.default_rng(SeedSequence(child_entropy))


# -----------------------------------------------------------------------------
# Deterministic mode — noise-off generator for debugging
# -----------------------------------------------------------------------------


class DeterministicGenerator:
    """Duck-typed `numpy.random.Generator` whose draws return E[X].

    Behaves like a `Generator` for the methods we actually call.  All draws
    are *deterministic* given the call order:

    - ``uniform(low=0, high=1)`` → ``(low + high) / 2``
    - ``normal(loc=0, scale=1)`` → ``loc``
    - ``binomial(n, p)`` → ``n if p >= 0.5 else 0``
    - ``beta(a, b)`` → ``a / (a + b)``
    - ``integers(low, high=None)`` → **round-robin** counter mod ``(high - low) + low``.
      Returning a fixed ``0`` would cause degenerate clumping (every
      "random firm" pick lands on firm 0); the counter sweeps the
      range so distinct calls return distinct values.
    - ``shuffle(x)`` → no-op (preserves input order).
    - ``choice(a, size=None, replace=True, p=None)`` → first element of ``a``.

    Implementing the wider Generator API is mechanical: add the
    method, return its E[X].

    Notes
    -----
    - Two Python runs that issue the **same sequence of method calls**
      against this generator produce bit-identical state — the
      :func:`tests.unit.test_deterministic_rng` round-trip test pins
      this property.
    - The C++ counterpart of this generator lives behind
      ``#ifdef DETERMINISTIC`` in the basecode (see
      ``planningDocs/RNG_AUDIT.md`` §D).
    """

    __slots__ = ("_int_counter",)

    def __init__(self) -> None:
        self._int_counter: int = 0

    # ------------------------------------------------------------------
    # uniform / normal
    # ------------------------------------------------------------------
    def uniform(
        self,
        low: float = 0.0,
        high: float = 1.0,
        size: "int | tuple | None" = None,
    ) -> Any:
        v = 0.5 * (float(low) + float(high))
        if size is None:
            return v
        return np.full(size, v, dtype=np.float64)

    def normal(
        self,
        loc: float = 0.0,
        scale: float = 1.0,
        size: "int | tuple | None" = None,
    ) -> Any:
        v = float(loc)
        if size is None:
            return v
        return np.full(size, v, dtype=np.float64)

    def standard_normal(self, size: "int | tuple | None" = None) -> Any:
        return self.normal(0.0, 1.0, size)

    # ------------------------------------------------------------------
    # binomial / beta
    # ------------------------------------------------------------------
    def binomial(
        self,
        n: "int | float",
        p: "int | float",
        size: "int | tuple | None" = None,
    ) -> Any:
        v = int(n) if float(p) >= 0.5 else 0
        if size is None:
            return v
        return np.full(size, v, dtype=np.int64)

    def beta(
        self,
        a: "int | float",
        b: "int | float",
        size: "int | tuple | None" = None,
    ) -> Any:
        a_f = float(a)
        b_f = float(b)
        v = a_f / (a_f + b_f) if (a_f + b_f) > 0.0 else 0.0
        if size is None:
            return v
        return np.full(size, v, dtype=np.float64)

    # ------------------------------------------------------------------
    # integers / choice / shuffle
    # ------------------------------------------------------------------
    def integers(
        self,
        low: int,
        high: "int | None" = None,
        size: "int | tuple | None" = None,
        dtype: Any = np.int64,
        endpoint: bool = False,
    ) -> Any:
        # numpy semantics: integers(n) → [0, n); integers(low, high) → [low, high)
        if high is None:
            lo, hi = 0, int(low)
        else:
            lo, hi = int(low), int(high)
        if endpoint:
            hi += 1
        rng_len = max(1, hi - lo)
        if size is None:
            v = lo + (self._int_counter % rng_len)
            self._int_counter += 1
            return int(v)
        # Vector form: walk the counter forward by `size` steps so
        # different array calls produce distinct sequences.
        n = int(np.prod(size)) if isinstance(size, tuple) else int(size)
        out = np.empty(n, dtype=dtype)
        for i in range(n):
            out[i] = lo + (self._int_counter % rng_len)
            self._int_counter += 1
        return out.reshape(size) if isinstance(size, tuple) else out

    def choice(
        self,
        a: Any,
        size: "int | tuple | None" = None,
        replace: bool = True,
        p: "Sequence[float] | None" = None,
    ) -> Any:
        # Return first element. Could be made smarter (e.g. argmax p) but
        # for the M1 active sites first-element is fine.
        if isinstance(a, (int, np.integer)):
            arr = np.arange(int(a))
        else:
            arr = np.asarray(a)
        v = arr[0]
        if size is None:
            return v
        return np.full(size, v, dtype=arr.dtype)

    def shuffle(self, x: Any, axis: int = 0) -> None:
        """In-place no-op shuffle (preserves input order)."""
        return None

    # ------------------------------------------------------------------
    # Convenience predicates so call sites can do `isinstance(rng, DeterministicGenerator)`
    # ------------------------------------------------------------------
    @property
    def is_deterministic(self) -> bool:
        return True


def make_deterministic_rng() -> DeterministicGenerator:
    """Return a fresh deterministic generator.

    The signature is symmetric with :func:`spawn_nation_rng` so that
    `Simulation.__init__(rng_mode='deterministic')` can drop this in for
    every nation without further plumbing.
    """
    return DeterministicGenerator()
