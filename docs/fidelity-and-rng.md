# Fidelity & randomness

pydsk is a **port**: its job is to reproduce the Wieners (2026) C++ model exactly,
while being far easier to use. This page explains how randomness works, how pydsk
proves it matches the original, and — importantly — what to do when you change the
model on purpose.

## Two randomness modes

pydsk's random-number generation (`dsk/rng.py`) runs in one of two modes, chosen by
`rng_mode` in the simulation YAML (default `stochastic`):

=== "Stochastic (default)"

    Each nation gets a `numpy` random generator derived from the run's
    `master_seed`. Randomness is real, but **reproducible**: the same seed always
    produces the same run. This is what you use for production runs and Monte-Carlo
    ensembles.

    ```yaml
    master_seed: 42
    # rng_mode: stochastic   # the default
    ```

=== "Deterministic"

    Every random draw is replaced by the **expected value** of its distribution (a
    coin flip returns its probability, a normal returns its mean, and so on). This
    removes Monte-Carlo noise entirely, so two runs are **bit-identical**.

    ```yaml
    rng_mode: deterministic
    ```

    Deterministic mode is how pydsk is verified against the C++ and how it guards
    against regressions (below). It is not an "average run" of the model — it's a
    single noise-free trajectory — but it is perfectly reproducible, which is exactly
    what a regression oracle needs.

Reproducibility in stochastic mode is **order-independent**: a nation's stream is
derived from its `nation_id` folded into the master seed, so adding or reordering
nations doesn't disturb the others' draws.

## The golden-output regression check

Because deterministic mode is bit-identical, the repository stores a **golden copy**
of the deterministic output for each milestone (the `py_det_*.parquet` /
`py_macro_*.parquet` files under `tests/reference/one_nation/`). Regenerating the
deterministic run and comparing to the golden copy is a precise, fast regression
test:

```bash
# regenerate one milestone's deterministic output
python tests/reference/one_nation/run_deterministic_M1.py --t-max 60 --out-dir /tmp/check

# compare to the committed golden copy
python - <<'PY'
import pandas as pd
from pandas.testing import assert_frame_equal
new = pd.read_parquet("/tmp/check/py_det_M1.parquet")
old = pd.read_parquet("tests/reference/one_nation/py_det_M1.parquet")
assert_frame_equal(new, old, check_exact=True)
print("bit-identical ✓")
PY
```

The full test suite (`pytest tests/`) includes these comparisons, so a green suite
means your build reproduces the reference model exactly.

## I changed behaviour on purpose — now what?

If your change is meant to alter results, the golden tests **should** fail — that's
them doing their job. The workflow:

1. **Confirm the failure is only where you expect.** A pure refactor (renaming,
   reorganising) should change *nothing*; if a "harmless" edit moves numbers, you've
   found a real bug. A behavioural change should move numbers *only* in the parts of
   the model you touched.
2. **Regenerate the golden fixtures on purpose** once you're satisfied the new
   behaviour is correct, so the tests describe your new model:
   ```bash
   ./regenerate_results.sh        # re-runs deterministic + ensemble outputs and the suite
   ```
3. **Record what changed and why** (the verification notes under `planningDocs/` are
   the existing pattern). If you're maintaining fidelity to the paper for a separate
   baseline, keep your variant on a branch or as a subclass so the reference stays
   intact (see [Extending → why overriding beats editing in place](extending.md#recipe-replace-a-decision-rule)).

!!! tip "Refactors are cheap to verify; behaviour changes need new goldens"
    For a behaviour-preserving change, the deterministic diff staying bit-identical is
    proof you didn't disturb anything. For a deliberate behaviour change, the diff is
    expected to move and the golden must be regenerated. Knowing which case you're in
    tells you whether a failing golden test is good news or bad.

## How pydsk maps to the C++

Two references make the port auditable, and they're useful when you extend the model:

- **`planningDocs/NAME_MAP.md`** — the dictionary between the C++ symbols (`f2`, `W2`,
  `Deb2`, `Q2`, …) and pydsk's descriptive names (`market_share`, `net_worth`,
  `debt`, `production`, …). Every agent attribute also carries its C++ name in an
  inline comment.
- **C++ line references in docstrings** — most methods cite the exact C++ function and
  line they port (e.g. `dsk_main.cpp:5048`), so you can compare behaviour directly if
  you ever need to.

You do not need the C++ to use or extend pydsk — but if you're checking fidelity, the
trail is there.

## Building this manual locally

The docs you're reading are a MkDocs site. To preview changes:

```bash
pip install -e ".[docs]"     # mkdocs + material theme
mkdocs serve                 # live preview at http://127.0.0.1:8000
mkdocs build                 # render static HTML into site/
```

The pages are plain Markdown under `docs/`, so they also render directly on GitHub
without building anything.

---

That's the manual. Start runs from [Running simulations](running-simulations.md),
change behaviour from [Extending the model](extending.md), and keep this page in mind
whenever a number moves.
