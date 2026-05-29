# RNG audit — C++ basecode vs Python `dsk/` (M1 scope)

**Purpose.** Enumerate every stochastic call site that fires during the
Milestone-1 spin-up (`t = 1 … 60`, single nation, no climate-box,
no climate policy active, `flagSTAG = 0`, `flagENTRY = 0`,
`flagENTRY2 = 5`, `flagEXP = 0`, `flagEXP_switch = 0`,
`flag_clim_tech = 1` but climate effects all guarded behind
`t > t_start_climbox + 21` = 101, so inactive).

Output is the input to **Step 2** (deterministic-mode patches on both
sides). Suggested deterministic-mode replacement value is the
distribution's expected value (`E[X]`); for Bernoulli we use the
parameter `p`-side floor (always-1 above 0.5, always-0 below) which
matches "majority outcome" deterministically.

Conventions:
- C++: `<file>:<line>` in `Code/Wieners_2025-main_slim/basecode/`.
- Python: `<file>:<line>` in `Code/dskPython2/dsk/`.
- M1 fires? = does this call site actually execute during M1 baseline?

---

## A. C++ side — full list of `ran1 / bnldev / betadev / bpareto / gasdev / rand` calls

72 call sites total in `dsk_main.cpp`. The active set during M1 is much
smaller; the rest are gated behind flags / time thresholds.

### A.1 Calls that **DO** fire in M1 spin-up

| Phase / function | C++ site | Distribution | Per period / per firm? | Notes |
|---|---|---|---|---|
| CLIMATE_POLICY | `dsk_main.cpp:703` (loop 1..20) | `ran1` (uniform[0,1]) | 20 / period | **"effectively change the seed"** — burns 20 draws every period before any model logic runs |
| INITIALIZE | `dsk_main.cpp:1321` | `ran1` ⇒ uniform integer `[1,NB]` | once per `j∈[1,N2]` at t=0 | Bank-assignment loop in firm-to-bank matching. Inside `while (CreditSupplier(j)==0)` so may loop several times until a free bank slot is found. |
| BROCHURE | `dsk_main.cpp:2614` | `ran1` ⇒ uniform integer `[1,N1]` | only when an s2 firm's supplier died last period | Rare in M1 since firm death is rare during spin-up |
| BROCHURE | `dsk_main.cpp:2649` | `ran1` ⇒ uniform integer `[1,N2]` | `newbroch ≈ ROUND(nclient(i)·Γ)` per `i∈[1,N1]` per period | Heavy: ~50-200 draws / period |
| ENTRYEXIT | `dsk_main.cpp:6236, 6413, 6660` | `ran1` ⇒ uniform integer `[1,N1]` | once per s1 entrant | Random-copy incumbent supplier for new s1 firm. Few entrants/period during spin-up |
| ENTRYEXIT | `dsk_main.cpp:6319, 6370` | `ran1`/`betadev` on `(b_a2, b_b2)` | once per s1 entrant (post-spin-up) | Productivity-multiplier draw; `flagENTRY2=5` selects branch starting line 6339 |
| ENTRYEXIT | `dsk_main.cpp:6437, 6445-6505` (s1 entry, flagENTRY2=5 branch) | `betadev(b_a2,b_b2)` | several per s1 entrant | Fixes A, K, W for s1 entrant relative to incumbent mean |
| ENTRYEXIT | `dsk_main.cpp:6558, 6630, 6779, 6965` | `ran1` ⇒ uniform integer `[1,N2]` | once per s2 entrant / replacement | s2 random-copy incumbent selection |
| ENTRYEXIT | `dsk_main.cpp:6737, 6746, 6824, 6828` | `ran1` | several per s2 entrant | Multipliers / NW draws for s2 entrant under `flagENTRY=0, flagENTRY2=5` |
| TECHANGEND | `dsk_main.cpp:7274` | `bnldev` (Bernoulli, `n=1, p≈0`) | per s1 firm per period | **Inn1 (energy axis)**: parber=`(1-exp(-o11·RDin1))·probinim`. During spin-up `RDin1=0` so parber=0 ⇒ Inn1=0 always — but **the draw still advances the RNG state**. Python skips this call. |
| TECHANGEND | `dsk_main.cpp:7278` | `bnldev` (Bernoulli) | per s1 firm per period | **Inn2 (labour axis)**: parber=`(1-exp(-o12·RDin2))·probinim`. Active. ↔ Python `capital_good_firm.py:430` |
| TECHANGEND | `dsk_main.cpp:7291` | `bnldev` (Bernoulli) | per s1 firm per period | **Imm**: parber=`(1-exp(-o2·RDim))·probinim`. ↔ Python `capital_good_firm.py:437` |
| TECHANGEND | `dsk_main.cpp:7312, 7323, 7337/7357, 7382, 7394` | `betadev(b_a1,b_b1)` | per s1 firm with `Inn1==1` | Energy-axis productivity gains. **Dead code in M1 spin-up** (Inn1==0). |
| TECHANGEND | `dsk_main.cpp:7418, 7423` | `betadev(b_a1,b_b1)` | per s1 firm with `Inn2==1` | A1pinn (process prod) and A1inn (machine prod) gains. ↔ Python `capital_good_firm.py:444, 448` |
| TECHANGEND | `dsk_main.cpp:7533` | `ran1` (uniform[0,1]) | per s1 firm with `Imm==1` | Imitation-target selection (1/Td-weighted CDF). ↔ Python `capital_good_firm.py:478` |
| TECHANGEND | `dsk_main.cpp:7881, 7889` | `betadev(b_a3,b_b3)` | per entrant s1 firm | Initial productivity for entrants. May fire during spin-up if any s1 firm exits. |
| TECHANGEND | `dsk_main.cpp:7964` | `bnldev` | per entrant s1 firm | Bernoulli for new firm's first-step innovation |
| TECHANGEND | `dsk_main.cpp:7969` | `bnldev` | per entrant s1 firm | Bernoulli for new firm's first-step imitation |
| TECHANGEND | `dsk_main.cpp:7978-8009` | `betadev(b_a1,b_b1)` | per entrant s1 firm | Beta draws for entrant productivity gains |
| TECHANGEND | `dsk_main.cpp:8085, 8114` | `ran1` (uniform[0,1]) | per entrant s1 firm | Entrant imitation target selection |
| PARETO | `dsk_main.cpp:9941` (calls `bpareto`) → `:9915` (`ran1`) | `bpareto(a, k, p)` | once per bank during INITIALIZE | Multi-bank client-count distribution. With NB=1 in M1 the outer while-loop terminates after a single iteration that sets `NL(1) = N2` directly, so this **does not effectively fire** in M1 ↔ Python `banking_sector.py:92` (analogue) |

### A.2 Calls that **do NOT** fire in M1 spin-up (gated off)

| Phase / function | C++ site | Why gated off |
|---|---|---|
| CLIMATE_POLICY | `dsk_main.cpp:912` (bnldev Inn_univ_ge) | Inside `if (t > t_start_climbox)` branches — t_start_climbox = 80 > 60 |
| CLIMATE_POLICY | `dsk_main.cpp:919` (betadev rnd_univ) | Same: climate-box gate |
| MACH | `dsk_main.cpp:2488` (bnldev p_change) | `if (flagSTAG==1 && t>1)`; baseline `flagSTAG=0` |
| EXPECT | `dsk_main.cpp:3206` (rand r_switch) | `if (flagEXP_switch==1)`; baseline `flagEXP_switch=0` |
| COSTPROD | `dsk_main.cpp:3977` (betadev shocks_capstock) | `if (flag_shocks==10 && t > t_start_climbox+21)` — t threshold = 101 |
| ALLOCATECREDIT | `dsk_main.cpp:4084` (betadev shocks_capstock) | `if (flag_shocks==11 && t > t_start_climbox+21)` |
| TECHANGEX | `dsk_main.cpp:7069, 7104` (gasdev epss) | TECHANGEX is the exogenous-frontier alternative; baseline uses TECHANGEND (`flag_clim_tech=1`) — TECHANGEX is not called |
| SAVEPARS | `dsk_main.cpp:9915` (ran1) | Only called once at start of run; produces stats summary; irrelevant for dynamics |
| Energy/climate modules | `module_energy.cpp:1032-1049`, `module_climate.cpp` | M1 doesn't run the energy / climate modules |

---

## B. Python side — full list of `rng.<method>` calls

12 active call sites in `dsk/`.

| Phase / function | Python site | Distribution | Per period / per firm? | C++ counterpart |
|---|---|---|---|---|
| `Nation.distribute_brochures` | `nation.py:369` | `rng.integers(0, N1)` (uniform integer) | when a sector-2 firm's supplier died | **C++ `dsk_main.cpp:2614`** |
| `CapitalGoodFirm.distribute_brochures` | `capital_good_firm.py:327` | `rng.integers(0, N2)` (uniform integer) | `newbroch` times per s1 firm per period | **C++ `dsk_main.cpp:2649`** |
| `CapitalGoodFirm.advance_technology` | `capital_good_firm.py:430` | `rng.binomial(1, parber_inn)` | once per s1 firm per period | **C++ `dsk_main.cpp:7278` (Inn2 only)** |
| `CapitalGoodFirm.advance_technology` | `capital_good_firm.py:437` | `rng.binomial(1, parber_imm)` | once per s1 firm per period | **C++ `dsk_main.cpp:7291` (Imm)** |
| `CapitalGoodFirm.advance_technology` | `capital_good_firm.py:444` | `rng.beta(b_a1, b_b1)` | once per s1 firm with innovation success | **C++ `dsk_main.cpp:7418`** |
| `CapitalGoodFirm.advance_technology` | `capital_good_firm.py:448` | `rng.beta(b_a1, b_b1)` | once per s1 firm with innovation success | **C++ `dsk_main.cpp:7423`** |
| `CapitalGoodFirm.advance_technology` | `capital_good_firm.py:478` | `rng.uniform(0.0, 1.0)` | once per s1 firm with imitation success | **C++ `dsk_main.cpp:7533`** |
| `Nation.process_entry_and_exit` | `nation.py:1394` | `rng.integers(0, len(alive_s1_idxs))` | once per s1 entrant | **C++ `dsk_main.cpp:6236` (or 6413/6660)** |
| `Nation.process_entry_and_exit` | `nation.py:1438` | `rng.integers(0, n2)` | once per s2 entrant | **C++ `dsk_main.cpp:6558`, `:6779` etc.** |
| `Nation.process_entry_and_exit` | `nation.py:1478` | `rng.integers(0, len(alive_s2_idxs))` | once per s2 entrant | **C++ `dsk_main.cpp:6630` etc.** |
| `Nation.process_entry_and_exit` | `nation.py:1547` | `rng.integers(0, n1)` | once per s1 entrant supplier selection | **C++ `dsk_main.cpp:6660`** |
| `BankingSector.<init>` | `banking_sector.py:92` | `rng.integers(nb)` | once per s2 firm at init | **C++ `dsk_main.cpp:1321`** |

---

## C. Side-by-side gap analysis

Five things stand out:

1. **C++ has site `:703` (the "burn 20 ran1 draws / period" loop) that
   Python does not.** It exists for the unrelated purpose of advancing
   the RNG state between MC reps and has no semantic effect. Harmless
   for ensemble means; matters for any bit-identical replay attempt.

2. **C++ executes `bnldev(parber=0, …)` on `Inn1` every period** during
   spin-up (line 7274) — the call returns 0 but advances the RNG by ≥1
   draw via `ran1`. Python skips this call entirely. Again, harmless
   for distribution comparisons but matters for bit-identical replay.

3. **C++ ENTRYEXIT does *many* draws per entrant** that Python
   collapses into a single `rng.integers(...)` choice. The entrant
   takes the productivity / NW / capital of an existing firm (random
   copy) in Python; in C++ it takes those values and then perturbs them
   with several `betadev(b_a2, b_b2, …)` draws (lines 6328–6503 under
   `flagENTRY2=5`). **Possibly material** — entry-flow productivity
   draws differ.

4. **`CapitalGoodFirm.advance_technology` reasonably matches its C++
   counterpart for M1.** Only one Bernoulli (Inn2, labour) fires under
   spin-up; Python's choice to skip Inn1 (energy axis) when M1 plan
   says "labour only" is consistent with `flag_spinup_innov=0` forcing
   `RDin1=0` in C++. The two beta draws (`:444`, `:448`) and one
   uniform (`:478`) line up 1:1 with C++ `:7418`, `:7423`, `:7533`.
   Same parameters (`b_a1=b_b1=3.0`, `uu1_a=-0.13`, `uu2_a=0.13`).

5. **PARETO bank-client distribution is effectively no-op in M1.**
   With `NB=1`, both C++ (while-loop terminator forces `NL(1)=N2`) and
   Python (single bank gets all firms) bypass the Pareto draw. Mute
   for now; matters at M2 when NB=10.

---

## D. Suggested Step-2 deterministic replacements

For each *active* M1 site, the replacement value to inject in
deterministic mode:

| Distribution call | E[X] | Notes |
|---|---|---|
| `ran1()` / `rng.uniform(0,1)` | **0.5** | Symmetric midpoint |
| `rng.uniform(a,b)` | **(a+b)/2** | |
| `rng.integers(0, n)` | **0** | First-of-list deterministic (alternative: floor of `n/2`) |
| `rng.binomial(1, p)` | **`1 if p ≥ 0.5 else 0`** | Sharpest non-stochastic Bernoulli |
| `rng.beta(α, β)` | **α / (α+β)** | For `α=β=3` ⇒ `0.5`; for `α=2, β=4` ⇒ `1/3` |
| `bpareto(a, k, p)` | `a / (1 − k^a)`-style mean | Not needed in M1 (PARETO is no-op at NB=1) |
| `gasdev()` | **0.0** | Not active in M1 |
| `C++ rand() / RAND_MAX` | **0.5** | Not active in M1 |

Replacement strategy (concrete):

- **Python.** Add `dsk/rng.py::DeterministicGenerator` — duck-typed
  subset of `numpy.random.Generator` with only the methods we use
  (`integers`, `binomial`, `beta`, `uniform`, `shuffle`). Each returns
  the E[X] value above. `Simulation.__init__` accepts
  `rng_mode='stochastic' | 'deterministic'` and wires
  `nation.rng = DeterministicGenerator()` for deterministic mode. Two
  Python runs with `rng_mode='deterministic'` must yield bit-identical
  parquets — that becomes the round-trip integration test.

- **C++.** Surgical patch — wrap each active site behind
  `#ifdef DETERMINISTIC` and replace with the constant. Specifically:
  | site | replacement |
  |---|---|
  | `:703` (burn loop) | drop the loop body |
  | `:1321` | rotate banks round-robin: `rni = (j % NB) + 1` |
  | `:2614` | `fornit(j) = (j % N1) + 1` |
  | `:2649` | `rni = ((newbroch_counter++) % N2) + 1` (deterministic walk) |
  | `:7274, 7278` (Inn Bernoullis) | `1 if parber >= 0.5 else 0` |
  | `:7291` (Imm Bernoulli) | same |
  | `:7418, 7423, 7881, 7889, 7978-8009` (beta(3,3)) | `0.5` |
  | `:7533, 8085, 8114` (uniform[0,1]) | `0.5` |
  | ENTRYEXIT block (6236-6828) | replace each with a round-robin / 0.5 / E[X] equivalent |
  Compile to a new binary `dsk_B_det` (CMake target). Existing
  `output_B/` is preserved.

The round-robin replacements for `rng.integers(0, n)` are preferred
over a fixed `0` so that *distinct* firms get distinct supplier IDs;
otherwise entry/brochure logic produces degenerate clumping.

---

## E. Open questions / risks for Step 2

1. **Does deterministic mode reveal the bug, or hide it?** The Task
   1.18 failure showed Python LD ~ 5 % below C++ LD averaged over
   50 MC; a single deterministic trace may show LD agreeing or
   disagreeing at different magnitude. If a single-trace comparison
   shows large agreement and the ensemble-mean disagreement is
   genuinely stochastic-only, the diagnosis flips back toward
   distributional differences (which would point at the *parameters*
   of the draws, not the model logic). Plan accordingly: run a small
   ensemble (5 MC) in deterministic mode on both sides as a second
   sanity check.

2. **The C++ `:703` burn loop and the `:7274` always-zero Inn1
   Bernoulli mean the C++ and Python RNG streams will diverge from
   period 1 even if we matched generators.** This is yet another
   reason deterministic mode (rather than bit-identical replay) is
   the right path.

3. **TECHANGEND for entrants (lines 7881–8009) is dense.** During
   spin-up with low firm-death rates this should fire only
   occasionally; if it fires more in Python (because Python's higher
   unemployment → more firm exits?), this could itself contribute to
   the LD divergence. Worth verifying in Step 6 that
   `n_entrants_per_period` matches between sides before drilling into
   per-firm differences.
