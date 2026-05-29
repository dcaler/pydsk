# DSK Python Port — Architecture and Build Plan, v3

**Supersedes `PORT_PLAN_v2.md`.** Three substantive changes:

1. **The procedural port (`Code/python2Econ/`) is stalled in verification.** It does not align with the C++ output. This OOP rewrite is therefore not a parallel artefact for a different audience — it is **the path forward**. v3 drops the v2 language that hedged on coexistence.
2. **Mesa 3 patterns are adopted as design influence** (not as a runtime dependency). Each sector is an `AgentSet`-like collection that supports `do(method)`, `shuffle_do(method)`, `select(filter)`, and `get(attribute) → np.ndarray`. The Mesa 3 convention (`model.agents` collection replacing schedulers) maps cleanly onto our `Nation` owning its sectors.
3. **Performance is explicitly not a constraint.** OOP-driven overhead is acceptable; the only optimisation target is "finishes a Monte Carlo run in reasonable wall-clock time on one modern machine." Vectorisation happens where it makes the *math* clearer (replicator dynamics, credit ranking, plant dispatch) — not as a performance discipline.

Plus housekeeping: open questions from v2 Appendix B are resolved (§ Appendix B); `Machine` is explicitly not an object class (state lives as numpy arrays inside `ConsumptionGoodFirm`); time step is annual to match C++ (configurable).

---

## 0. What changes between v2 and v3

| Concern | v2 | v3 |
|---|---|---|
| Status of `python2Econ` | "Procedural port; coexists with OOP rewrite as performance/verification reference" | "Stalled in verification, not aligned with C++. OOP rewrite is the canonical port. Salvage design lessons (phase ordering, `flag_shared_climate`) but not code." |
| Performance posture | Hedged ("trades performance for legibility") | Explicit: performance is not a constraint. Acceptable upper bound is "a few hours per MC run." |
| Framework reference | Vague | Mesa 3 conventions adopted: each sector is an `AgentSet`-like collection. No runtime dependency. |
| `Machine` class | Listed as a class | Removed. Machine state is per-firm numpy arrays inside `ConsumptionGoodFirm`. The C++ tensor `g[T][N1][N2]` is mirrored as such. |
| Time step | Open question | Annual by default (`dtecon=1.0`, matches C++ baseline). Configurable; `0.25` for quarterly. |
| `flag_dskQE` baseline | Open question | Resolved: ON for baseline (per C++ `dsk_flag.h:16`). Default in `GlobalParameters`. |
| `flag_shared_climate` default | Open question | Resolved: `True` (one global `ClimateSystem`). The per-nation-climate mode survives only as a verification toggle against the C++ `twoDSKmodel`. |
| Foreign firms (`A1f`) | Open | Resolved: N=1 keeps the original fictional frontier mechanism. N≥2 uses an inter-nation imitation pool with a per-pair `imitation_distance` parameter (default 1.0). |
| Fossil-fuel price | Open | Resolved: global by default; per-nation override available in YAML. |
| `gtemp[T][N1][N2]` audit | Open | Resolved by the no-`Machine`-object decision: stored as 2-D vintage × supplier numpy arrays inside each `ConsumptionGoodFirm`. |

Everything not listed here is unchanged from v2.

---

## 1. Why we are doing this, given the procedural port is stalled

The team already has a procedural Python port (`Code/python2Econ/`). It is faithful to the C++ structure — globals translated to a single `EconomyState` dataclass, C++ functions translated to module-level functions that mutate it. It is also stalled in verification: outputs do not align with the C++ reference run, and debugging is slow precisely *because* the structure is flat and the behavioural rules are spread across module-level functions that all see the same shared state.

The OOP rewrite addresses this directly:

1. **Encapsulation locates bugs faster.** When a `Bank`'s equity goes negative unexpectedly, the place to look is `Bank.update_after_loan_loss()` and the methods that mutate `Bank.equity`. The class is the search radius. In the procedural port, the search radius is "anything that touches `EconomyState.BankEquity` across the entire codebase."
2. **Stock-flow checks become per-agent assertions.** `Bank.assert_balance_sheet_balances()` is one method. `Nation.accounting.check_balance_sheet()` aggregates them. In the procedural port, the same check requires reaching into multiple loosely-coupled arrays whose update order matters.
3. **The English-naming pass is forced by the rewrite.** Translating the Italian/cryptic C++ names while keeping a procedural shape is psychologically harder than doing it while changing the shape — the procedural port understandably kept `BankEquity` etc. to stay close to the C++, and that *also* makes it hard for new readers.
4. **The multi-nation extension is cheaper as OOP.** The procedural port's path to multi-nation is the `EconomyState`-per-economy pattern (which it does adopt), but cross-nation operations then mutate multiple states with no structural support. The OOP `Nation` composite gives that support for free.

The lesson from the procedural port's stall, which we carry into v3: **build verification in from milestone 1**, not as an end-of-project gate. Every milestone must reproduce a specific C++ output before the next milestone starts. See §6.

---

## 2. Adopted Mesa 3 patterns (without the Mesa runtime)

Mesa 3 made one important refactor: it replaced `Scheduler` classes with an `AgentSet` collection on the `Model`. The user calls `model.agents.do("step")` (or `shuffle_do("step")`) rather than constructing a scheduler. AgentSets support `select(filter)`, `groupby(attribute)`, and `get(attribute)` (which returns an array of that attribute across the set).

This is exactly the "collection of agents that supports iteration *and* vectorised attribute access" pattern v2 described informally. v3 formalises it as a base class `AgentSet` in our own code, with a deliberately Mesa-3-compatible API so that anyone familiar with Mesa can read our code.

```python
class AgentSet:
    def __init__(self, agents: list = None): ...
    def add(self, agent): ...
    def remove(self, agent): ...
    def do(self, method_name: str, *args, **kwargs): ...           # call method on each agent
    def shuffle_do(self, method_name: str, *args, **kwargs): ...   # same, in random order
    def select(self, predicate) -> "AgentSet": ...                 # subset
    def get(self, attribute: str) -> np.ndarray: ...               # vectorised attribute pull
    def set(self, attribute: str, values: np.ndarray): ...         # vectorised attribute push
    def __iter__(self): ...
    def __len__(self): ...
```

A `Sector` is then literally an `AgentSet` subclass with sector-specific helpers:

```python
class CapitalGoodSector(AgentSet):
    def innovation_pool(self) -> AgentSet:
        return self.select(lambda f: f.rd_budget > 0)
    def market_shares_array(self) -> np.ndarray:
        return self.get("market_share")
```

**Why not depend on Mesa directly:**

- Mesa enforces a single-model orchestration (`Model.step()`); our `Simulation` owns multiple `Nation`s and the cross-nation hooks are unusual for Mesa.
- Mesa's `DataCollector` is convenient but not designed for our scenario YAML structure or parquet output.
- Mesa's RNG conventions and seed handling diverge from numpy's modern `SeedSequence` interface, which we want for reproducibility under parallel Monte Carlo.
- Mesa is a young, fast-moving framework; pinning to a major version adds a compatibility-maintenance task we don't need.
- Our `AgentSet` is ~80 lines. Reimplementing it is cheaper than coupling.

We do borrow Mesa's *vocabulary*: `Agent`, `AgentSet`, `do`, `shuffle_do`, `select`, `get`. Anyone who has used Mesa 3 should be able to read our `Nation` and `Sector` classes without surprise.

---

## 3. Class catalogue (changes vs v2)

### 3.1 `Nation`, `Simulation`, `Government`, `CentralBank`, `Bank`, `ElectricityProducer`, `PowerPlant`, `LabourMarket`, `HouseholdSector`, `ClimatePolicy`, `ClimateSystem`, `TradeNetwork`, `NationalAccounts`
Unchanged from v2 §3.

### 3.2 `CapitalGoodFirm`, `ConsumptionGoodFirm`
Unchanged behaviour, with one detail clarified:

- **`ConsumptionGoodFirm.machines`** is a `MachineStock` object — a thin wrapper around two numpy arrays:
  - `productivity[vintage, supplier]` — labour productivity of machines of given vintage from given supplier
  - `count[vintage, supplier]` — how many such machines are held
  - With parallel arrays for `energy_efficiency`, `environmental_cleanliness`, and `electrification_fraction` (each `[vintage, supplier]`).
- Operations on the stock (age, scrap, add new vintage, compute aggregate effective productivity) are vector operations on these arrays.

### 3.3 `Machine` — **explicitly NOT a class** (changed in v3)

Per the discussion of the C++ tensor `g[T][N1][N2]`: instantiating one Python object per machine would mean potentially millions of objects per Monte Carlo run. Even at our relaxed performance posture, this is wasteful for no readability gain — a `MachineStock` of numpy arrays expresses "this firm holds machines of vintage v from supplier s with these properties" just as clearly. The cost-side decisions (scrap, replace, compute effective productivity) are naturally array operations.

A `Machine` *type* — the technology embodied in a single make of machine — *does* exist as a value object: `Technology(labour_productivity, energy_efficiency, env_cleanliness, electrification_fraction)`. There is one `Technology` per `CapitalGoodFirm` per time step (the technology it currently sells), plus the candidate `Technology` instances generated during innovation and imitation. These are short-lived, lightweight, and immutable — fine as Python objects.

### 3.4 `AgentSet` and `Sector` — **new in v3**
See §2. Base `AgentSet` is generic; `CapitalGoodSector`, `ConsumptionGoodSector`, `BankingSector` (and, internally to `ElectricityProducer`, `GreenPlantSet`, `BrownPlantSet`) are subclasses with domain-specific helpers.

`LabourMarket` and `HouseholdSector` are not `AgentSet` subclasses (they don't hold heterogeneous agents in v3 — see §3.10 of v1, kept). If we later add heterogeneous `Household`s, `HouseholdSector` becomes an `AgentSet`.

### 3.5 Singletons-per-nation reassessed
v2 promised to "reassess at milestone 2" whether `Government`, `CentralBank`, `LabourMarket` earn their existence as classes or should be data on `Nation`. v3 decision:

- **`Government`** — keep. Tax collection, budget balancing, bond issuance, bailout decisions are all distinct behaviour blocks; the class is a real abstraction.
- **`CentralBank`** — keep. Taylor rule + reserve management is a meaningful module.
- **`LabourMarket`** — keep, even though it doesn't hold individual workers. It owns wage-setting (`flagWAGE`) and rationing logic, which is more than a data bag.

These remain singletons inside each `Nation`. They have RNGs derived from `Nation.rng` and access nation state via the back-reference set at construction.

---

## 4. Main loop with phase decomposition
Unchanged from v2 §4.

Implementation note: each phase loop becomes `nation.production_phase(t)` which internally does `self.capital_good_sector.shuffle_do("plan_innovation_and_imitation")` and similar `AgentSet` calls. The Mesa 3 vocabulary is visible at the implementation level, not at the architectural level.

---

## 5. Package layout (small adjustments)

```
dskPython2/
├── planningDocs/
│   ├── PORT_PLAN.md          # v1
│   ├── PORT_PLAN_v2.md       # v2
│   ├── PORT_PLAN_v3.md       # this document — canonical
│   └── …                     # papers
├── dsk/
│   ├── simulation.py
│   ├── nation.py
│   ├── parameters/
│   ├── rng.py
│   ├── agent_set.py          # NEW in v3: base AgentSet class
│   ├── agents/
│   │   ├── agent.py          # NEW in v3: base Agent class
│   │   ├── capital_good_firm.py
│   │   ├── consumption_good_firm.py
│   │   ├── machine_stock.py  # NEW in v3: numpy-backed vintage/supplier arrays
│   │   ├── technology.py     # NEW in v3: small immutable value object
│   │   ├── bank.py
│   │   ├── electricity_producer.py
│   │   ├── power_plant.py
│   │   ├── government.py
│   │   ├── central_bank.py
│   │   └── household.py
│   ├── sectors/
│   │   ├── capital_good_sector.py
│   │   ├── consumption_good_sector.py
│   │   ├── banking_sector.py
│   │   └── labour_market.py
│   ├── markets/
│   ├── policy/
│   ├── climate/
│   ├── trade/
│   ├── accounting/
│   ├── innovation/
│   ├── io/
│   └── monte_carlo.py
├── configs/
├── tests/
├── notebooks/
├── cli.py
└── README.md
```

`agents/machine.py` from v2 → `agents/machine_stock.py` + `agents/technology.py` in v3.

---

## 6. Build milestones with verification-from-milestone-1

Largely unchanged from v2 §6, with a single emphasis change: **every milestone must reproduce a specific C++ output before the next milestone starts.** This is the lesson from the procedural port's stall.

| # | Milestone | Verification (NOT optional) |
|---|---|---|
| **0** | Scaffold, `AgentSet`, `Nation`, `GlobalParameters` / `NationParameters`, RNG, output sink | Unit tests; loaded YAML matches a hand-computed parameter dump |
| **1** | KS10 core inside one `Nation`: `CapitalGoodFirm`, `ConsumptionGoodFirm` (with `MachineStock`), `Bank`, `LabourMarket`, `HouseholdSector` | Per-step GDP, unemployment, wage match C++ basecode to within ~10% ensemble mean across 50 MC runs over 60 spin-up periods. Stylised facts (Pareto firm size, cyclical co-movements) match. |
| **2** | Multi-bank, `Government`, `CentralBank`, fiscal/monetary policy | `Deb/GDP`, inflation, policy rate trajectories track C++ basecode baseline |
| **3** | Energy module, plants, dispatch, R&D | Baseline green-share trajectory ≈ C++ basecode |
| **4** | `ClimateSystem` (global), emissions aggregation | Baseline warming curve ≈ Wieners Fig. 1a (Baseline) within 10th–90th percentile band |
| **5** | All `ClimatePolicy` instruments; full Wieners 2025 scenarios in 1-nation | Reproduce Wieners Figs. 1–5 in shape and ranking |
| **6** | Multi-nation harness; symmetric 2-nation boundary test | Symmetric run is indistinguishable from 1-nation run within MC noise |
| **7** | Inter-nation trade | Reproduce `twoDSKmodel/` verification suite already on disk |
| **8** | Asymmetric policy scenarios | Direction-of-change tests pass |
| **9** | Performance & ergonomics | < 4 h per MC run on one modern core (1-nation); < 8 h (2-nation). See §11 for posture. |
| **10** | Optional extensions | — |

**Hard requirement: 0–7.** If any milestone fails its verification gate, work stops on the next milestone until the failure is resolved or the gate is justifiably relaxed (with team sign-off and a note in the planning docs).

---

## 7. Verification strategy
Unchanged from v2 §7. The only addition: a verification notebook is created at milestone 1 (`tests/reference/one_nation/baseline_M1.ipynb`) and *extended* at each subsequent milestone, so the comparison surface against the C++ output grows monotonically.

---

## 8. Cross-cutting design (unchanged + new note on Mesa)
v2 §8 unchanged. One new entry:

### 8.7 Mesa 3 vocabulary
We adopt Mesa 3's `Agent` / `AgentSet` vocabulary deliberately. A reader who has used Mesa 3 should be able to read our `Sector` classes without surprise. We do **not** depend on the `mesa` package at runtime; see §2 for the reasoning. If a user wants to lift our `Nation` into a Mesa-managed environment in the future, the API compatibility makes that a small adapter rather than a rewrite.

---

## 9. Risk register
Unchanged from v2 §9, with two updates:

| Risk | Mitigation update in v3 |
|---|---|
| **Verification deferred to the end** (the procedural port's failure mode) | Hard rule: each milestone has a C++-matching gate; no advance without passing it (§6) |
| Mesa version drift / runtime dependency | Mitigated by *not* depending on Mesa at runtime (§2) |

---

## 10. Out of scope
Unchanged from v2 §10.

---

## 11. Performance posture (new section)

Explicit, so it doesn't get re-litigated implicitly.

- **Target:** a single Monte Carlo run (T ≈ 220 annual steps, 100 capital firms, 400 consumption firms, ~10 banks, 1 nation) finishes in under 4 hours on one core. 2-nation runs under 8 hours. 50-MC ensembles under a day with `multiprocessing.Pool`.
- **Non-target:** matching the C++ runtime. The C++ does ~2–3 min/run; we are content with 10×–100× slower.
- **Vectorisation policy:** vectorise where the math is *clearer* as a vector formula (replicator dynamics, plant merit-order, credit ranking, machine ageing, balance-sheet aggregation). Don't vectorise just for speed. The `AgentSet.get("attr")` API exists for this — it returns a fresh numpy array each call, which is fine.
- **Profiling:** only at milestone 9. Earlier profiling is wasted effort.
- **Concurrency:** Monte Carlo replicates are embarrassingly parallel (separate processes via `multiprocessing.Pool`). Nation-level parallelism within one MC run is enabled by the phase-seam structure of §4 but not implemented until / unless 4+ nations make it worth the orchestration cost.

If we discover at milestone 5 that a single MC run takes >24 hours, we revisit. Until then, we don't pre-optimise.

---

## Appendix A — Bilingual name map with scope tag
Unchanged from v2 Appendix A. The PR template's requirement (every new C++→Python translation updates the table; scope column is mandatory) stands.

---

## Appendix B — Resolutions to the v2 open questions

1. **Time-step length** — **Annual** (`dtecon = 1.0`, `freqclim = 1`). Verified from `Wieners_2025-main_slim/{basecode,baseline,files_BCERT}/0_dsk_constant.h:388-389` (all three files agree). The C++ author preserved `0.25 = quarters` as a documented alternative in the comment. v3 makes the value a `GlobalParameters` field with annual as the default. Switching to quarterly requires multiplying `total_steps`, `spin_up_steps`, `climate_start_step`, and all duration-typed parameters (`patdur`, `agemax`, `life_plant`, `b`, `t_tune`) by 4.

2. **`flag_dskQE` baseline** — **ON**. Per `dsk_flag.h:16` the comment is explicit: `// 1 = on ===> dsk18 // [BASELINE = 1]`. v3 defaults `GlobalParameters.use_dsk_qe = True`. The OFF path (KS15 + DSK17 behaviour) is an opt-in legacy mode, not exposed in standard scenarios.

3. **`flag_shared_climate` in `twoDSKmodel`** — **Default `True`** (one global atmosphere). This matches the physical reality of one planet and matches how Wieners et al. report aggregate warming. The per-nation-climate mode (`False`) is preserved as a verification toggle against the C++ `twoDSKmodel`'s alternative mode and as a useful debugging aid when isolating one nation's contribution.

4. **Trade mechanism details** — Defer to milestone 7. When approaching that milestone, read `Code/twoDSKmodel/src/dsk_trade.cpp` and `dsk_trade.h` directly, *not* the `python2Econ/dsk/trade/trade.py` interpretation, since the procedural port is stalled in verification and we cannot trust its translation. The structural plan (bilateral matching for N=2, generalised to all pairs for N≥3, computed between production and dynamics phases) stands.

5. **`gtemp[T][N1][N2]` tensor** — Resolved by §3.3 (no `Machine` objects): each `ConsumptionGoodFirm` owns a `MachineStock` with `count[vintage, supplier]` and parallel productivity arrays. The `T` dimension of the C++ tensor was a worst-case bound on vintages; in Python we use a dictionary or compact array indexed by *actual* vintages present, growing as needed.

6. **Foreign firms (`A1f`) under N=1 vs N≥2**
   - **N=1:** preserve the original fictional foreign frontier — a parameterised distribution of foreign productivities updated each step independently of any firm. This is needed for baseline reproduction.
   - **N≥2:** the imitation pool is the union of all nations' real `CapitalGoodFirm`s. Each nation has a vector `imitation_distance[other_nation]` ∈ [0, ∞); 0 = freely imitable, ∞ = invisible. Default 1.0 (= as easy as domestic imitation). The original `A1f` mechanism is the limiting case where the "other nation" is a frozen hypothetical with one fixed productivity distribution.

7. **Per-nation fossil-fuel price** — **Global by default** (`GlobalParameters.fossil_fuel_price`). A YAML override `nation.fossil_fuel_price` (when present) overrides for that nation only. This supports sensitivity tests (a "fuel exporter" nation paying a lower price) without complicating the default case.

---

## Appendix C — Lessons from the stalled procedural port

The `Code/python2Econ/` port is a faithful translation of the C++ structure into Python: `EconomyState` is a dataclass mirroring `dsk_globalvar.h`, and module functions (`MACH`, `INVEST`, etc.) mirror the C++ function signatures. It does not match the C++ outputs.

We don't know precisely *why* it stalled without doing the verification work ourselves, but the structural factors that make stall hard to diagnose in the procedural port are exactly the factors the OOP rewrite reduces:

| Factor in procedural port | OOP rewrite mitigation |
|---|---|
| ~3000 globals translated as `EconomyState` attributes; any function can mutate any attribute | State on objects; mutations narrowly scoped to that object's methods |
| Italian / cryptic names preserved (e.g. `BankEquity`, `mi2`, `xi`) — author intentionally minimised renaming during port | English renaming is part of the port itself; bilingual map in Appendix A is the canonical reference |
| Hard to attribute a drift in (say) `BankEquity` to a specific code path; the search radius is "anywhere" | `Bank.equity` is mutated only by methods on `Bank`; search radius is one class |
| Verification was end-of-project; structural drift accumulated unnoticed | Per-milestone C++-matching gate is a hard requirement (§6) |
| The `MachineStock` semantics had to be reverse-engineered from the C++ tensor in one shot | Resolved early in milestone 1, with a clear `MachineStock` class boundary |

The OOP rewrite is therefore not just an aesthetic improvement. It is a debuggability improvement that we expect to *reach* verification where the procedural port did not.

We do still salvage two things from the procedural port without reusing its code:

1. **The phase-ordered loop** (`runner_neco.py`): production → trade → dynamics → climate → closeout. This is what v2/v3 §4 specifies.
2. **The `flag_shared_climate` switch.** Even though we default it to `True`, the toggle has verification value.

---

## Further questions for the user

None blocking. v3 is ready to start implementing from milestone 0. The only place where user input would still help is at milestone 6/7 when we need to confirm how interesting asymmetric multi-nation scenarios should be parameterised — but that is a research question that benefits from having the harness running first.
