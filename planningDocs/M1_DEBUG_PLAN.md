# M1 root-cause debugging plan

**Goal.** Localise the divergence that caused the Task 1.18 gate failure
(see `M1_VERIFICATION_FAILURE.md`) to one specific Python function and
one specific C++ function whose translations disagree. Stop guessing.

**Method, briefly.** The C++ basecode already dumps per-firm vectors
each step (`Qmach_*.txt`, `Qcons_*.txt`, `A1all_*.txt`, `A2all_*.txt`,
`invest2_*.txt`, plus the 42-column `out_*.txt` and 80-column
`ymc_*.txt`). Add matching per-firm dumps on the Python side. Run both
in *deterministic-noise mode* (all RNG draws replaced with a fixed
seed → fixed value, on both sides — see Step 1 caveat). At each
timestep, compare distributions (not individual firms — RNG order
still differs across languages). The first step where any aggregate or
distributional moment diverges is the bug location; the upstream call
chain narrows the search radius.

---

## Step 0 — Decide the noise policy (10 min, no code)

Three options, ranked best→worst for *this* debugging task:

a. **Deterministic mode on both sides.** Replace every RNG draw with a
   fixed value (or with `0.5` for `uniform`, `0.0` for `normal`, etc.).
   Distributional comparison becomes *exact* comparison; the first
   divergent value is the bug. Requires identifying every RNG call site
   on both sides — manageable in M1 because we don't have energy R&D
   or climate. **Estimated effort:** half a day per side.

b. **Match the RNG by replay.** Dump every C++ random number to a file
   in order; replay them in Python by reading sequentially. Gives
   bit-identical traces *if* the order of draws is also matched, which
   requires reading both implementations carefully. **Estimated effort:
   1–2 days.** Brittle and worse than (a) for the same goal.

c. **Compare ensemble means only.** Already done. Tells us "something
   is wrong" but not where. **No.**

**Recommendation: option (a).** Concretely:
- C++: identify every `rand()`, `random_device`, `mt19937`, `bpareto`,
  `bbeta`, `bernoulli`, `runif`, etc. call. The newmat-based `bpareto`
  / `bbeta` are the obvious ones for KS10. Replace with a constant
  that matches the *expected value* of the draw (or the median).
- Python: in `dsk/rng.py`, add a `DeterministicRNG` wrapper that returns
  constants for `uniform()`, `normal()`, `choice()`, etc. Swap in via
  `Simulation` constructor.

If swapping the entire RNG is too invasive, the smaller win is to fix
the *seed* on both sides and live with the order mismatch — that still
collapses variance but doesn't give exact equality. Acceptable fallback.

---

## Step 1 — Inventory the RNG call sites (~1 hour)

Read the two codebases to enumerate every RNG draw in M1. M1 covers
KS10 + multi-bank skeleton + government, so the draws are roughly:

| Phase | Likely draws |
|---|---|
| INITIALIZE | bpareto for bank-client distribution; uniform draws for initial productivity dispersion |
| TECHANGEND | Bernoulli innovation success, beta-distributed productivity gains, imitation choice |
| BROCHURE | (no draws; matching is deterministic) |
| INVEST | (deterministic) |
| ALLOCATECREDIT | (deterministic; ranks by net worth) |
| COMPET2 | (deterministic replicator) |
| ENTRYEXIT | uniform for entrant placement; net-worth draw for entrants |

Output: `planningDocs/RNG_AUDIT.md` — short table, one row per draw,
columns: `phase | C++ symbol | Python symbol | distribution | suggested fixed value`.

If the audit turns up something we missed in M1 (e.g. a draw in
COMPET2 we did not port), that itself is a candidate bug — note it but
defer the fix until tracing shows it matters.

---

## Step 2 — Patch in deterministic-noise mode (~2 hours)

**Python.** Add `dsk/rng.py::DeterministicRNG`:
- subclass of `numpy.random.Generator` (or duck-typed wrapper) that
  returns: `uniform → 0.5`, `normal → 0.0`, `bernoulli(p) → 1 if p>=0.5 else 0`,
  `choice([…]) → first element`, `beta(α,β) → α/(α+β)`, etc.
- `Simulation.__init__` accepts `rng_mode='stochastic' | 'deterministic'`
  and wires accordingly.
- Add a single integration test `tests/integration/test_deterministic_mode.py`
  asserting that two Python runs with the same `rng_mode='deterministic'`
  produce bit-identical outputs.

**C++.** Two options:
- Surgical: replace just the calls flagged in Step 1 with
  `#ifdef DETERMINISTIC` constants.
- Brute: replace `srand(seed)` with `srand(0)` and `rand()` with a
  constant macro. Simpler but breaks anything that depends on
  *distinct* draws within a call.

Choose surgical. Recompile the C++ to a new binary `dsk_B_det` so the
existing `output_B/` is preserved for comparison.

---

## Step 3 — Add Python per-firm trace dumps (~1 hour)

Extend `tests/reference/one_nation/run_ensemble_M1.py` (or split into a
new `run_trace_M1.py`):
- At every step, after `nation.save_outputs(t)` and *before*
  `update_state_for_next_period`, dump per-firm vectors for both
  sectors to a parquet file (one row per `(mc_run, t, firm_id, sector)`).
- Fields (sector 2): `production`, `sales`, `labour_demand`,
  `effective_productivity`, `process_labour_prod`, `price`,
  `competitiveness`, `market_share`, `expected_demand`,
  `expansion_investment_units`, `substitution_investment_units`,
  `net_worth`, `debt`, `inventory`.
- Fields (sector 1): `production`, `labour_demand`, `productivity`
  (offered for sale), `process_labour_prod`, `price`, `rd_budget`,
  `net_worth`, `debt`.
- Plus an aggregate vector per step matching the C++ `out_*.txt` columns:
  `Q1tot, Q2tot, Creal, Ir, EItot, SItot, dNtot, LD1, LD2, LD_rd,
   vital, U, w, cpi, ppi, Am, A_sd, Mutot, NW1tot, NW2tot`.

Output: `py_trace_M1.parquet` (per-firm) + `py_aggregates_M1.parquet`.

---

## Step 4 — Read what C++ already dumps; emit anything missing (~1 hour)

The on-disk C++ dump set:
| Per-step file | Content | Already on disk? |
|---|---|---|
| `out_*.txt` | 42 aggregates per step | Yes |
| `ymc_*.txt` | 80 aggregates per step | Yes |
| `Qcons_*.txt` | per-firm Q2 | Yes |
| `Qmach_*.txt` | per-firm Q1 | Yes |
| `A1all_*.txt` | per-firm A1p | Yes |
| `A2all_*.txt` | per-firm A2 | Yes |
| `invest2_*.txt` | per-firm sector-2 investment | Yes |
| `NW1all_*.txt` | per-firm net worth s1 | Yes (per `dsk_globalvar_old.h`) |
| `NW2all_*.txt` | per-firm net worth s2 | Yes |
| `Deb2all_*.txt` | per-firm debt s2 | Yes |
| per-firm LD (sector 1 / sector 2) | — | **No; need to add** |
| per-firm expected demand | — | **No; need to add** |
| per-firm effective productivity (`A2e`) | — | **No; need to add** |

The four "**No**" entries should be added to the C++ deterministic
binary in Step 2. They are small, mechanical additions (~30 lines
total in `dsk_main.cpp`'s SAVE function).

---

## Step 5 — The trace itself (~30 min)

Run, on the deterministic binary:
- C++: 5 steps, single MC rep, dump all the per-firm files plus the new ones.
- Python: 5 steps, single MC rep, in deterministic mode, dump
  `py_trace_M1.parquet`.

Five steps is enough — the failure document shows divergence is visible
by t=3.

---

## Step 6 — The actual diagnosis (~2-4 hours iterating)

A single notebook `tests/reference/one_nation/M1_trace_compare.ipynb`
that:

1. **Aggregate diff at each timestep.** For each variable in the
   aggregate table, compare Python vs C++ scalar values at t=1, t=2, ….
   First non-matching variable at the first non-matching step
   identifies the *phase* of the bug (e.g. "production is fine at t=1
   but LD differs → bug is in the LD computation, not production").
2. **Per-firm diff at the first bad step.** For the variable identified
   in (1), compare per-firm vectors. Python firm 0 ↔ C++ firm 0,
   firm 1 ↔ firm 1, … (initialisation should map them in the same
   order, especially in deterministic mode). Plot a scatter and a
   per-firm residual histogram.
3. **Drill upstream.** If `labour_demand[firm i] differs`, look at the
   computation: `production[i] / A2e[i]`. Compare `production[i]` and
   `A2e[i]` separately. If `A2e[i]` matches but `production[i]` differs,
   the bug is in production (PRODMACH). Etc.
4. **Iterate** until the smallest divergence is a single variable in a
   single function. That is the bug.

The first divergence is almost certainly at step 1 (initialisation),
step 2 (first production cycle), or step 3 (first investment cycle).
The "labour demand under-shoots by ~5 % from step 2 onwards" symptom
points at step 2.

---

## Step 7 — Fix and re-gate

Whatever Step 6 finds, fix it. Re-run the *stochastic* gate
(`run_ensemble_M1.py` then `M1_baseline.ipynb`). If it now passes,
delete `M1_VERIFICATION_FAILURE.md` and proceed to M2. If it still
fails (but on a different signature), repeat from Step 5.

There may be more than one bug — output looks like at least two
(LD/investment, plus Pareto). Address them serially, in order of
how much they bias the gate.

---

## Estimated total

| Step | Effort |
|---|---|
| 0 — decide noise policy | done above |
| 1 — RNG audit | 1 hour |
| 2 — deterministic mode (both sides) | 2 hours |
| 3 — Python per-firm dump | 1 hour |
| 4 — C++ extra dumps | 1 hour |
| 5 — run trace | 30 min |
| 6 — diagnose first bug | 2-4 hours |
| 7 — fix + re-gate | 1-2 hours |
| **Total** | **~1 day, plus per-iteration cost for additional bugs** |

This is roughly a single focused conversation per bug. Pareto-α may
well need a second iteration once the LD/investment bug is fixed.

---

## What this plan *won't* deliver

- Bit-identical Python ↔ C++ trajectories under stochastic mode.
  See "Step 0" note: would need to match RNG algorithm, draw order,
  and floating-point implementation.
- A general "trace any model output" framework. This is a one-shot
  debug instrument, optimised for the Task 1.18 gate.
- A guarantee that Pareto-α will pass after the labour/investment
  bug is fixed. It might (if the tail is downstream of competitiveness
  computed off correct LD/production). It might not — defer until the
  primary gate variables clear.
