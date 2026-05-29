# DSK Python Port — Architecture and Build Plan, v2

**Supersedes `PORT_PLAN.md`.** The substantive change in v2 is the introduction of `Nation` as a first-class container/composite agent, so the simulation can hold one or many nations that each have their own government, central bank, banks, firms, energy producer, and climate policy — all on a shared atmosphere, with cross-border trade as a deliberate but deferred extension.

The goal remains: **readability and accessibility**, not performance. Slower than C++ is fine; legible OOP that scales to multi-nation experiments is the prize.

---

## 0. What changes between v1 and v2

| Concern | v1 | v2 |
|---|---|---|
| World structure | `Simulation` directly owns sectors, government, central bank, energy producer | `Simulation` owns 1..N `Nation` instances + the shared `ClimateSystem` (+ later, inter-nation hooks like `TradeNetwork`) |
| Policy scoping | `ClimatePolicy` at simulation level | Each `Nation` has its own `ClimatePolicy`, `Government`, `CentralBank` |
| Parameter file | One `Parameters` dataclass | A `GlobalParameters` (climate, fuel price, RNG) + one `NationParameters` per nation |
| Scenario file | One YAML | A `simulation.yaml` referencing one `nation_*.yaml` per nation; composes naturally with policy fragments |
| Main loop | 20 sub-phases called in order | Three phase-groups: `production_phase()`, optional cross-nation `trade_phase()`, `dynamics_phase()`, optional `climate_phase()`, `closeout_phase()`. Each phase is per-nation parallel-safe; cross-nation steps happen between phases. |
| Verification | 1 baseline series from C++ basecode | Phase 1: 1-nation Python ≈ C++ `basecode/`. Phase 2: 2-nation Python ≈ C++ `twoDSKmodel/`. Cross-validation is now part of the build path. |

Prior art already on disk worth mining (for design lessons, not for code reuse — `dskPython2/` is a fresh OOP rewrite):
- `Code/Wieners_2025-main_slim/basecode/` — canonical 1-economy C++ baseline (this is the source of truth)
- `Code/twoDSKmodel/` — 2-economy C++ variant (canonical reference for trade and shared climate)
- `Code/python2Econ/` — a procedural Python port already done by the team, including a working `trade.py` and `flag_shared_climate` switch in `runner_neco.py`. We reuse none of its code but adopt its phase decomposition.

---

## 1. Evaluation of the "Nation as super-agent" proposal

### 1.1 Is it sound?

Yes. In ABM design vocabulary a `Nation` here is a **composite** (also called container, group, or organisation): it owns sub-agents and exposes their aggregate behaviour, but is not itself a decision-making agent in markets — the `Government` and `CentralBank` *inside* the nation do that. Calling it a "super-agent" is fine as long as we are clear that:

- Decisions live in concrete authorities (`Government` taxes, `CentralBank` sets rates, `ClimatePolicy` bundles instruments). The `Nation` orchestrates them.
- "Apply to all and only sub-national agents" is satisfied for free by **composition**: a `Government` taxes only the firms its `Nation` owns; a `CarbonTax` only enters the cost function of plants owned by that nation's `ElectricityProducer`.

### 1.2 Benefits

1. **Cleanly scoped policy.** Nation A's carbon tax simply does not exist in nation B's cost functions. No accidental cross-contamination, no need for an `if nation_id == X` guard.
2. **Multi-nation experiments become trivial.** Add a nation to the YAML; the loop iterates one more time.
3. **Comparable policy paths.** Two nations with different climate-policy packages but identical structural parameters give a clean A/B test of policy effectiveness — exactly the kind of study the Wieners et al. paper recommends as future work.
4. **Shared atmosphere falls out naturally.** Emissions aggregate; the `ClimateSystem` is the single global object that nations write to and read from.
5. **Trade hook is well-positioned.** A `trade_phase()` between production and dynamics is a natural seam — it's where the `python2Econ/dsk/trade/trade.py` precedent already places trade, and where the C++ `dsk_main_2eco.cpp` places it.
6. **Future extensibility.** Heterogeneous nation parameters, asymmetric initial conditions, climate-clubs, sectoral coupling, capital flows — all become parameterisations of an existing structure.

### 1.3 Costs and complications

| Issue | Resolution |
|---|---|
| **Synchronisation across nations.** If nations step independently, accounting blows up. | Lockstep phase ordering: every nation does phase X, *then* every nation does phase X+1. Cross-nation events happen between phases at fixed seams. |
| **What is global vs per-nation?** | See §2. Climate, fossil-fuel international price, and (later) trade prices are global. Almost everything else is per-nation. |
| **Per-nation parameters multiply.** | A `NationParameters` dataclass is loaded per nation; sensible defaults inherit from a baseline. |
| **The original "foreign firms" reference (`A1f`).** | Becomes optional. In multi-nation mode, imitation can target real firms in other nations (with an imitation-distance penalty). In single-nation mode, the original "fictional world frontier" mechanism is preserved as a strategy. |
| **Stock-flow consistency across borders.** | Without trade or capital flows, each nation closes within itself; SFC checks run per-nation. With trade, a counterparty entry on the other side of every cross-border flow keeps SFC global. |
| **Verification surface doubles.** | The 1-nation Python run must match the C++ `basecode/` baseline; the 2-nation Python run must match the C++ `twoDSKmodel/` baseline. Both gates are formalised in §6. |
| **Performance.** | Per-nation parallelism via `multiprocessing.Pool` or `joblib` is straightforward because the only synchronization points are well-defined phase seams. |
| **Naming.** | `Nation` is the class name. Alternatives considered (`Economy`, `Polity`, `Region`, `Country`): `Nation` is the user's choice and matches everyday language for the kind of entity that has its own fiscal and monetary policy. |
| **"Is a Nation an agent?"** | Pedantically: no, it's a composite. Practically: it's a useful organising object that simulates one economy. The plan uses "composite agent" or "nation" interchangeably. |

### 1.4 Verdict

Adopt. The proposal materially improves the architecture and matches both the team's existing direction (multi-economy verification suite already shipped, prior art in `python2Econ/` and `twoDSKmodel/`) and the paper's stated future work (asymmetric policy across regions).

---

## 2. What lives at which level

### 2.1 Global (owned by `Simulation`)
- `ClimateSystem` — atmosphere, oceans, biosphere, humus, surface temperature. Receives the sum of all nations' emissions per climate step.
- `FossilFuelMarket` — exogenous international price `pf`. (Initially a scalar that grows with inflation; later potentially endogenous.)
- `TradeNetwork` — a stub object until trade is enabled. Holds inter-nation matching parameters when active.
- Master RNG (a `numpy.random.SeedSequence`); spawns per-nation child generators.
- `GlobalParameters` — climate parameters, fuel emission factor, simulation horizon `total_steps`, Monte Carlo count.
- Output sink (parquet writer) — receives streams from all nations plus the global climate.

### 2.2 Per-nation (owned by each `Nation`)
- `Government`, `CentralBank`
- `CapitalGoodSector` (holds N1 `CapitalGoodFirm`s), `ConsumptionGoodSector` (holds N2 `ConsumptionGoodFirm`s and their `Machine`s), `BankingSector` (holds NB `Bank`s)
- `ElectricityProducer` (with its own `GreenPlant` and `BrownPlant` vintages)
- `LabourMarket`, `HouseholdSector`
- `ClimatePolicy` (composed of `CarbonTax`, `GreenSubsidy`, `BrownConstructionBan`, `ElectrificationMandate`)
- `NationParameters` — markup, payback, R&D intensity, wage-rule sensitivities, beta-distribution shapes, sector sizes, initial conditions, scenario tags, RNG (a child generator)
- Per-nation output buffer (flushed to the global sink each step)

### 2.3 Strictly global parameters (cannot be per-nation)
- Climate sensitivity, ocean diffusion, biospheric decay times — physics of the planet.
- Pre-industrial atmospheric carbon and the C-ROADS initial conditions.
- Fossil-fuel emission factor `ff2em`. (Could become per-nation if we ever model heterogeneous fuel mixes.)

### 2.4 Strictly per-nation parameters
- Sector sizes (`N1`, `N2`, `NB`), wages, payback periods, markup widths.
- All tax rates and subsidies.
- The composition of `ClimatePolicy`.
- All RNG state below the master seed.

### 2.5 Ambiguous parameters (per-nation by default, with a `share_across_nations` flag)
- Fossil-fuel price level — global by default (one international market) but the user can pin a nation-specific price for sensitivity tests.
- Foreign tech frontier — see §3.1.5.

---

## 3. Class catalogue (changes vs v1 in **bold**)

### 3.1 `Nation` *(new in v2)*
A composite that owns one full economy.

- **State:**
  - `id: str` — short tag used in output and config (e.g. `"north"`, `"south"`, `"global"` for the 1-nation case).
  - `parameters: NationParameters`
  - `rng: numpy.random.Generator` — child of the master RNG, seeded from `(master_seed, nation_id)`.
  - `government: Government`
  - `central_bank: CentralBank`
  - `capital_good_sector: CapitalGoodSector`
  - `consumption_good_sector: ConsumptionGoodSector`
  - `banking_sector: BankingSector`
  - `electricity_producer: ElectricityProducer`
  - `labour_market: LabourMarket`
  - `household_sector: HouseholdSector`
  - `climate_policy: ClimatePolicy`
  - `accounting: NationalAccounts` — per-step balance-sheet ledger for SFC checks
  - `output_buffer: OutputBuffer`
- **Methods (each is one of the 20 sub-phases, plus three aggregated wrappers):**
  - `set_climate_policy(t)` → calls the climate-policy bundle's `is_active(t)` and propagates rates into firm and energy cost functions.
  - `compute_bank_client_net_worth()` → mirrors `WTOTCLIENT`.
  - `deliver_machines()` → `MACH`.
  - `determine_total_credit()` → `TOTCREDIT`.
  - `compute_max_credit_per_firm()` → `MAXCREDIT`.
  - `distribute_brochures()` → `BROCHURE`.
  - `plan_investment()` → `INVEST`, which internally calls `EXPECT`, `SCRAPPING`, `ORD`.
  - `allocate_credit_to_demand()` → `ALLOCATECREDIT`.
  - `produce_machines()` → `PRODMACH`, which internally drives `LABOR`, `EN_DEM`, `CANCMACH`.
  - `compute_industrial_emissions()` → `EMISS_IND`. Returns the nation's emissions this step (consumed by the global climate accumulator).
  - `run_electricity_market()` → `ENERGY`.
  - `compute_market_shares()` → `COMPET2`.
  - `realise_profits_and_taxes()` → `PROFIT`, which internally drives `GOV_BUDGET`, `ALLOC`.
  - `update_banks()` → `BANKING`.
  - `bailout_failed_banks()` → `BAILOUT`.
  - `aggregate_macro_indicators()` → `MACRO` (also `WAGE`).
  - `set_policy_rate()` → `TAYLOR`.
  - `process_entry_and_exit()` → `ENTRYEXIT`.
  - `advance_technology()` → `TECHANGEND` (or `TECHANGEX` under the legacy flag).
  - `apply_climate_shocks(climate_state)` → `SHOCKS`.
  - `save_outputs(t)` → `SAVE`.
  - `update_state_for_next_period()` → `UPDATE`.
  - Aggregated wrappers: `production_phase(t)`, `dynamics_phase(t)`, `closeout_phase(t)` — these call the sub-phases in the canonical order.
- **Cross-nation hooks (initially no-ops, expanded later):**
  - `report_emissions() -> float` — emissions this step, for the global climate accumulator.
  - `receive_climate_state(climate) -> None` — pulls global temperature and CO₂ into local variables for shock and policy calculations.
  - `expose_trade_offer() -> TradeOffer` — a placeholder; in milestone 7+ this exposes excess supply / unmet demand for cross-border matching.
  - `accept_trade_assignment(assignment) -> None` — a placeholder; consumes the result of `TradeNetwork.match()`.
- **Invariants enforced after every phase (under debug):**
  - `accounting.check_balance_sheet(tol)` — sum of all financial assets in the nation equals sum of liabilities + equity.
  - `accounting.check_real_flows(tol)` — production = consumption + investment + inventory change + government spending.

### 3.2 `CapitalGoodFirm`, `ConsumptionGoodFirm`, `Machine`, `Bank`, `Government`, `CentralBank`, `ElectricityProducer`, `PowerPlant`, `HouseholdSector`, `LabourMarket`

State and behaviour identical to **v1 §3**, with two changes:
1. Each holds a reference back to its `Nation` for access to nation-level state (its own central bank's rate, its own carbon tax, its own labour market). No global lookups.
2. Each gets its RNG from `self.nation.rng` rather than a module-level singleton.

A small additional change: `CapitalGoodFirm` accepts an optional `imitation_pool` parameter at construction. In 1-nation mode this is `self.nation.capital_good_sector.firms`. In N-nation mode it can be `chain(*[n.capital_good_sector.firms for n in simulation.nations])` (subject to an "imitation distance" penalty configurable per nation — see §3.1.5).

### 3.3 `ClimateSystem` *(now strictly global)*
- State and methods as in v1 §3.9.
- **Single instance** owned by `Simulation`. Receives the sum of `nation.report_emissions()` over all nations at each climate-eligible step.
- Optional `flag_shared_climate=False` mode for verification — runs one `ClimateSystem` per nation, no aggregation. This mode exists only because the C++ `twoDSKmodel` has it; the production default is `True`.

### 3.4 `ClimatePolicy` *(scoped per nation in v2)*
- Container for `CarbonTax`, `GreenConstructionSubsidy`, `GreenRDSubsidy`, `BrownConstructionBan`, `ElectrificationMandate`.
- Each instrument has `nation_id` (so output is tagged), `is_active(t)`, and an `apply(...)` method that mutates the relevant nation-level cost/revenue function.
- A `Nation` constructs its `ClimatePolicy` from its YAML file, so different nations can run different policy packages simultaneously.

### 3.5 `TradeNetwork` *(new, stub until milestone 7)*
- Holds bilateral trade parameters (`trade_openness`, transport-cost matrices, currency or accounting conventions).
- `match(nation_offers) -> assignments` — the matching algorithm. For N=2 it reproduces the bilateral mechanism from `twoDSKmodel/src/dsk_trade.cpp`; for N>2 it generalises to all pairs.
- Holds persistent state across steps (mirroring `TradeState` from the prior art).
- Until milestone 7, this object exists but its `match` is a no-op.

### 3.6 `Simulation` *(orchestrator; changed)*
- **State:**
  - `nations: list[Nation]`
  - `climate: ClimateSystem`
  - `fossil_fuel_market: FossilFuelMarket`
  - `trade_network: TradeNetwork` (stub until trade is enabled)
  - `global_parameters: GlobalParameters`
  - `master_rng: numpy.random.SeedSequence`
  - `output_sink: OutputSink`
  - `t: int` — current step
- **Methods:**
  - `initialise()` — instantiates everything in dependency order.
  - `step()` — drives one period through the phase structure of §4.
  - `run(T)` — full run.
  - `run_monte_carlo(MC, T)` — outer MC loop.

### 3.7 `NationalAccounts` *(new in v2)*
A small helper per nation that records flows and stocks each step and exposes balance/flow checks. This was implicit in v1; v2 makes it an object because the multi-nation case requires per-nation SFC closure as an explicit invariant.

---

## 4. Main loop with phase decomposition

The 20 sub-phases of the C++ `dsk_main.cpp` are grouped into three per-nation phase blocks separated by two cross-nation seams. This mirrors what `python2Econ/dsk/sim/runner_neco.py` does, recast in OO form.

```python
def step(self, t):
    # PRODUCTION PHASE — each nation independently
    for nation in self.nations:
        nation.production_phase(t)
        # internally:
        #   set_climate_policy(t)
        #   compute_bank_client_net_worth()
        #   deliver_machines()
        #   determine_total_credit()
        #   compute_max_credit_per_firm()
        #   distribute_brochures()
        #   plan_investment()
        #   allocate_credit_to_demand()
        #   produce_machines()
        #   compute_industrial_emissions()
        #   run_electricity_market()
        #   compute_market_shares()

    # SEAM 1 — TRADE (no-op until milestone 7)
    if self.trade_network.is_enabled(t):
        offers = [n.expose_trade_offer() for n in self.nations]
        assignments = self.trade_network.match(offers)
        for nation, assignment in zip(self.nations, assignments):
            nation.accept_trade_assignment(assignment)

    # DYNAMICS PHASE — each nation independently
    for nation in self.nations:
        nation.dynamics_phase(t)
        # internally:
        #   realise_profits_and_taxes()
        #   update_banks()
        #   bailout_failed_banks()
        #   aggregate_macro_indicators()
        #   set_policy_rate()
        #   process_entry_and_exit()
        #   advance_technology()

    # SEAM 2 — CLIMATE (only on climate-eligible steps)
    if t > self.global_parameters.climate_start_step and t % self.global_parameters.climate_step == 0:
        total_emissions = sum(n.report_emissions() for n in self.nations)
        self.climate.step(total_emissions)
        for nation in self.nations:
            nation.receive_climate_state(self.climate)

    # CLOSEOUT PHASE — each nation independently
    for nation in self.nations:
        nation.closeout_phase(t)
        # internally:
        #   apply_climate_shocks(...)
        #   save_outputs(t)
        #   update_state_for_next_period()

    self.t += 1
```

**Why this ordering:** trade affects production-side inventories and unmet demand, so it must happen after production and before profit realisation. Climate must accumulate the period's industrial and energy emissions, which means after `EMISS_IND` / `ENERGY` and after profit realisation. Shocks come last so they affect the *next* period's productivity.

**Parallelisation:** the three per-nation phases are embarrassingly parallel across nations. A `joblib.Parallel(n_jobs=K)(delayed(nation.production_phase)(t) for nation in nations)` swap-in is trivial because nation state is local. The seams are the synchronisation barriers. This is a clean concurrency story without an event scheduler.

---

## 5. Package layout

```
dskPython2/
├── planningDocs/
│   ├── PORT_PLAN.md          # v1, kept for traceability
│   ├── PORT_PLAN_v2.md       # this document
│   └── …                     # papers
├── dsk/
│   ├── __init__.py
│   ├── simulation.py         # Simulation (orchestrator)
│   ├── nation.py             # Nation (composite)
│   ├── parameters/
│   │   ├── global_parameters.py
│   │   ├── nation_parameters.py
│   │   └── scenario.py       # scenario composition (e.g. BCERT = B+C+E+R+T)
│   ├── rng.py                # SeedSequence and child generator factories
│   ├── agents/
│   │   ├── capital_good_firm.py
│   │   ├── consumption_good_firm.py
│   │   ├── machine.py
│   │   ├── bank.py
│   │   ├── electricity_producer.py
│   │   ├── power_plant.py    # GreenPlant, BrownPlant
│   │   ├── government.py
│   │   ├── central_bank.py
│   │   └── household.py
│   ├── sectors/
│   │   ├── capital_good_sector.py
│   │   ├── consumption_good_sector.py
│   │   ├── banking_sector.py
│   │   └── labour_market.py
│   ├── markets/              # per-nation markets
│   │   ├── credit_market.py
│   │   ├── machine_market.py
│   │   ├── goods_market.py
│   │   └── electricity_market.py
│   ├── policy/               # per-nation policy instruments
│   │   ├── climate_policy.py
│   │   ├── carbon_tax.py
│   │   ├── green_subsidy.py
│   │   ├── brown_ban.py
│   │   ├── electrification_mandate.py
│   │   ├── monetary_policy.py
│   │   ├── fiscal_policy.py
│   │   └── bailout.py
│   ├── climate/              # global
│   │   ├── climate_system.py
│   │   ├── emissions.py      # aggregation helpers
│   │   └── fossil_fuel_market.py
│   ├── trade/                # global; stub until milestone 7
│   │   ├── trade_network.py
│   │   ├── trade_offer.py
│   │   └── matching.py
│   ├── accounting/
│   │   └── national_accounts.py
│   ├── innovation/
│   │   ├── bernoulli_trial.py
│   │   └── beta_draw.py
│   ├── io/
│   │   ├── output_sink.py
│   │   ├── output_buffer.py
│   │   └── config.py
│   └── monte_carlo.py
├── configs/
│   ├── global/
│   │   └── default.yaml      # climate, fossil-fuel, RNG seed, MC count
│   ├── nations/
│   │   ├── baseline.yaml
│   │   ├── BCERT.yaml
│   │   └── …                 # one per Wieners-2025 scenario
│   └── simulations/
│       ├── one_nation_baseline.yaml
│       ├── one_nation_BCERT.yaml
│       ├── two_nation_north_south.yaml
│       └── …
├── tests/
│   ├── unit/
│   ├── integration/
│   └── reference/
│       ├── one_nation/        # against Wieners_2025-main_slim/basecode
│       └── two_nation/        # against Code/twoDSKmodel
├── notebooks/
├── cli.py
└── README.md
```

A `simulations/*.yaml` file references one `global/*.yaml` and a list of `nations/*.yaml`. This makes scenario composition declarative and version-controllable.

---

## 6. Build milestones (revised)

| # | Milestone | Deliverable | Verification |
|---|---|---|---|
| **0** | Project scaffold | `dsk/` skeleton, `parameters`, `rng`, `output_sink`, `simulation`, `nation` (with no-op phases). One-nation `simulations/one_nation_baseline.yaml` loads cleanly. | `pytest tests/unit/test_scaffold.py` |
| **1** | KS10 core inside a single `Nation` — `CapitalGoodFirm`, `ConsumptionGoodFirm`, `Machine`, `Bank`, `LabourMarket`, `HouseholdSector` | One-nation simulation runs T steps; produces GDP, unemployment, wage. **The `Nation` layer exists from day 1**; we never have a "flat" version. | Stylised-fact tests (Pareto firm size, cyclical co-movements); per-step SFC check passes; trade hook is a no-op |
| **2** | Multi-bank, `Government`, `CentralBank`, fiscal/monetary policy — still 1-nation | Reproduces KS15 stylised facts | Time series of `Deb/GDP`, inflation, policy rate match Dosi et al. (KS15) qualitative behaviour |
| **3** | Energy module — `ElectricityProducer`, `GreenPlant`/`BrownPlant`, energy R&D, dispatch | Energy market clears; green share evolves under baseline | Baseline green-share trajectory ≈ Wieners Fig. 1f (Baseline) within 1-nation Monte Carlo bands |
| **4** | Global `ClimateSystem`, industrial emissions aggregation, temperature feedback off | Baseline emissions and temperature trajectories | Reproduce Baseline `Warming` curve (Wieners Fig. 1a, black line); confirm shared climate works with 1 nation as a trivial pass-through |
| **5** | `ClimatePolicy` instruments fully integrated; all Wieners 2025 scenarios runnable in 1-nation mode | Tc, T2, T2h, T2i, BE, CER, BCER, BCERT | Reproduce Wieners Figs. 1–5 in shape and ranking; ensemble means within ~20% of paper |
| **6** | **Multi-nation harness end-to-end** — instantiate two structurally identical nations with the same scenario; confirm they evolve to the same statistics (modulo RNG); confirm SFC closes per nation and globally | `two_nation_symmetric.yaml` runs and the two nations are statistically indistinguishable | A symmetric 2-nation run must match the 1-nation run on per-nation aggregates within MC noise. (This is the strongest test of the `Nation` boundary not leaking state.) |
| **7** | **Inter-nation trade** — `TradeNetwork` becomes non-trivial; bilateral matching for N=2 | A `north_high_demand` × `south_low_cost` scenario shows net export flows | Reproduce the 2-economy C++ results from `Code/twoDSKmodel/` outputs (verification suite already on disk, see `Paper/DSK_2eco_Verification_Suite.docx`) |
| **8** | **Asymmetric policy** — e.g. nation A runs BCERT, nation B runs Baseline; quantify carbon leakage and competitiveness effects | Working multi-policy scenarios | Direction-of-change checks; results are reasonable (no SFC failures, no negative debt explosions) |
| **9** | Performance and ergonomics — vectorised hot loops; multiprocess MC; CLI | < 30 min per MC run on 1 modern core for 1-nation, < 90 min for 2-nation | Profiling deliverable |
| **10** | Optional extensions | Heterogeneous `Household` agents; networked banking; alternative climate boxes (DICE, FaIR); N>2 nations; trade-currency layer | — |

The hard requirement is **milestones 0–7**. Milestone 6 is the milestone that proves the multi-nation refactor was worth it: a symmetric 2-nation run must be indistinguishable from a 1-nation run, modulo Monte Carlo noise. Until that passes, the rest is suspect.

---

## 7. Verification strategy (multi-nation)

### 7.1 1-nation Python vs C++ `basecode/`
Same as v1 §7. Reproduce baseline and BCERT ensemble means inside the published 10th–90th percentile bands.

### 7.2 Symmetric 2-nation Python vs 1-nation Python (the "boundary test")
Run a 2-nation simulation with identical parameters and the same total population (i.e. two N1/2 nations vs one N1 nation). Per-nation aggregates should be statistically indistinguishable from each other, and the global aggregates should be close to the 1-nation reference within MC noise. **Significant divergence = a leak between nations or a bug in cross-nation aggregation.**

### 7.3 2-nation Python vs C++ `twoDSKmodel/`
Reproduce the verification suite already on disk (`Paper/DSK_2eco_Verification_Suite.docx`, `verification_1eco_vs_2eco_v2.png`, `verification_trade_perturbation_v2.png`). These give us a precise target.

### 7.4 Asymmetric scenarios (qualitative)
Once the symmetric tests pass, we run asymmetric policy mixes (one nation aggressive, one nation laggard) and check direction-of-change predictions from the literature: carbon leakage, technology spillover, terms-of-trade effects. These are not gold-standard verification but they catch obvious modelling errors.

---

## 8. Cross-cutting decisions, revised

(Differences from v1 §5 only; the unchanged items still hold.)

### 8.1 RNG with nations
A master `numpy.random.SeedSequence` is built from a single user seed. `simulation.master_rng.spawn(N_nations)` produces a child sequence per nation, from which each nation creates its `Generator`. Per-Monte-Carlo replicates spawn from the master seed in a deterministic order: `(seed, mc_run, nation_id)` → child generator. Reproducible, parallel-safe.

### 8.2 Output schema
Each row in the output parquet has columns `(mc_run, t, nation_id, …)`. Global series (climate) get `nation_id = "global"`. Per-firm dumps get `(mc_run, t, nation_id, agent_type, agent_id, …)`. This makes 1-nation and N-nation outputs queryable with the same code path.

### 8.3 Stock-flow consistency
SFC is enforced **per nation** by `NationalAccounts.check_balance_sheet()` and `NationalAccounts.check_real_flows()`. When trade is active, the cross-border flow must appear as an asset on one side and a liability on the other, and `Simulation.check_global_sfc()` runs after each step.

### 8.4 Configuration composition
A `simulations/*.yaml` file looks like:
```yaml
horizon_years: 220
monte_carlo_runs: 50
master_seed: 42
global: configs/global/default.yaml
nations:
  - id: north
    config: configs/nations/baseline.yaml
    policy:
      - configs/policies/brown_ban.yaml
      - configs/policies/green_construction_subsidy.yaml
      - configs/policies/green_rd_subsidy.yaml
      - configs/policies/electrification_mandate.yaml
      - configs/policies/carbon_tax_constant.yaml
  - id: south
    config: configs/nations/baseline.yaml
    policy: []   # no climate policy
trade:
  enabled: false
climate:
  shared: true
```

This is much cleaner than the C++ workflow (which requires copying `0_dsk_main.cpp`, `0_dsk_flag.h`, `0_dsk_constant.h` between folders and rebuilding) and trivially extends to asymmetric, multi-nation scenarios.

### 8.5 The "foreign firms" reference (A1f), reconsidered
- **1-nation mode (default):** preserve the original fictional foreign frontier; needed for the baseline reproduction.
- **N-nation mode:** the imitation pool is the union of all nations' capital-good firms, with an `imitation_distance` parameter per nation pair (1.0 = freely imitable, ∞ = invisible). This subsumes the original A1f mechanism: it's the limit where A1f's "world frontier" is a fixed, hardcoded country.

### 8.6 Climate sharing toggle
A `climate.shared: true|false` switch in the simulation YAML. `true` runs one global `ClimateSystem`; `false` runs one per nation (only used for verification against the C++ `flag_shared_climate=0` mode). Production default is `true`.

---

## 9. Risk register (updated)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Multi-nation refactor done too late | Low (we adopt it in v2 from milestone 0) | High | Build the `Nation` layer from day 1, even in 1-nation mode |
| State leak across nations (e.g. a shared mutable default argument) | Medium | High | The symmetric 2-nation boundary test (§7.2) catches this; SFC checks per nation |
| Per-nation RNG seeding subtly biases MC results | Low | Medium | Test that the 1-nation MC distribution is identical whether spawned through a 1-element SeedSequence or used directly |
| Climate aggregation order drifts from the C++ shared-climate mode | Medium | Medium | Reproduce the C++ output for the same emissions sequence; mark the climate step as a regression target |
| Trade design choices made too early | Medium | Medium | TradeNetwork is a stub until milestone 7; only the *hooks* are present earlier |
| Performance unacceptable for N≥4 nations | Low | Medium | Per-nation phases are parallel; `joblib.Parallel` swap-in is a 10-line change |
| C++ globals translated as Nation attributes but with wrong scope | Medium | High | Appendix A's bilingual name map (extended in v2 to mark scope: global/nation/agent) is the source of truth; PRs touching scoped state update the map |
| Verification cost doubles with multi-nation gates | Certain | Low | Accept it — the multi-nation gate is the proof the design is right |

---

## 10. Out of scope (unchanged from v1 unless noted)
- Climate damages on firm productivity (`flag_shocks > 0`)
- Hydrogen / biomass / negative-emissions pathways
- Endogenous political economy
- Individual heterogeneous households
- dskQE variants exposed as user-facing strategies (kept on internally for baseline reproduction)
- Networked / cross-border banking, lobbying, currency layers (deferred to milestone 10)
- **N>2 nations is *enabled* by the design but not on the milestone path** — milestone 7 demonstrates N=2 in earnest; N>2 follows naturally if anyone wants it

---

## Appendix A — Bilingual name map with scope tag

In addition to the C++ → English mapping in v1 Appendix A, each entry now carries a **scope** column:
- **G** = global (lives on `Simulation` or `ClimateSystem`)
- **N** = per-nation (lives on `Nation` or one of its sectors)
- **A** = per-agent (lives on a `CapitalGoodFirm`, `Bank`, etc.)

| C++ | Italian gloss | Python | Scope |
|---|---|---|---|
| `N1` | Numero imprese industria machine tools | `n_capital_good_firms` | N |
| `N2` | Numero imprese industria manifatturiera | `n_consumption_good_firms` | N |
| `NB` | Numero banche | `n_banks` | N |
| `T` | Numero cicli temporali | `total_steps` | G |
| `MC` | Numero replicazioni Monte Carlo | `n_monte_carlo_runs` | G |
| `nu` | Parametro spesa R&D | `rd_intensity` | N |
| `xi` | Alloca spesa R&D | `innovation_vs_imitation_share` | N |
| `mi1`, `mu2` | Mark-up | `markup_capital`, `markup_consumption` | N |
| `Gamma` | Regola contatti nuovi clienti | `brochure_outreach_rate` | N |
| `chi` | Replicator dynamics | `replicator_intensity` | N |
| `psi1, psi2, psi3` | Sensibilità salario | `wage_inflation_sens`, `wage_productivity_sens`, `wage_unemployment_sens` | N |
| `theta` | Scorte attese | `inventory_target_share` | N |
| `u` | Utilizzo capacità | `capacity_utilisation_target` | N |
| `b` | Pay-back | `payback_threshold` | N |
| `agemax` | Età massima macchinario | `machine_max_age` | N |
| `dim_mach` | Dimensione macchinario | `machine_size` | N |
| `wu` | Salario disoccupazione | `unemployment_replacement_rate` | N |
| `aliq`, `aliqb` | Aliquota imposta | `income_tax_rate`, `bank_profit_tax_rate` | N |
| `W1, W2` | Ricchezza netta | `net_worth_capital_firms`, `net_worth_consumption_firms` | A (sector-aggregated at N) |
| `S1, S2` | Sales | `sales_capital_firms`, `sales_consumption_firms` | A |
| `Q1, Q2` | Produzione | `output_capital`, `output_consumption` | A |
| `D1, D2` | Domanda | `demand_capital`, `demand_consumption` | A |
| `N` (matrix) | Scorte | `inventories` | A |
| `f1, f2, fB` | Quote di mercato | `market_share_*` | A |
| `tao` | Generazione (vintage) | `machine_vintage` | A |
| `A1, A1inn, A1imm` | Productivity (machine/innov/imit) | `tech_*` | A |
| `A1p` | Productivity of technique | `production_technique_productivity` | A |
| `A1p_en, A1p_ef, A1p_el` | EE, EF, electrification of technique | `energy_efficiency_*`, `environmental_cleanliness_*`, `electrification_fraction_*` | A |
| `K_ge, K_de` | Plant counts | `n_green_plants`, `n_brown_plants` | A (within `ElectricityProducer` at N) |
| `G_de, G_ge` | Plant counts by vintage | `brown_plants_by_vintage`, `green_plants_by_vintage` | A |
| `A_de` | Thermal efficiency brown | `brown_thermal_efficiency` | A |
| `EM_de` | Emissions per fuel | `brown_emission_intensity` | A |
| `CF_ge, CF_de` | Construction costs | `green_build_cost`, `brown_build_cost` | A |
| `c_en` | Electricity cost | `electricity_unit_cost` | N |
| `pf` | Fossil-fuel price | `fossil_fuel_price` | **G** (international) |
| `ff2em` | Fuel emission factor | `fuel_emission_factor` | **G** |
| `Cat, Con, Tmixed, Ton, biom, humm` | C-ROADS state | `atmospheric_carbon`, `ocean_carbon`, `surface_temperature`, `ocean_temperature`, `biospheric_carbon`, `humus_carbon` | **G** |
| `Emiss_TOT` | Emissions this step | `nation_emissions` (per-nation) summed into `global_emissions` | A/N/G |
| `Tax, Deb, Def, GDPm, G` | Macro aggregates | `tax_revenue`, `public_debt`, `public_deficit`, `nominal_gdp`, `government_spending` | N |
| `r, r_deb, r_depo, r_cbreserves` | Rates | `policy_rate`, `lending_rate`, `deposit_rate`, `reserve_rate` | N |
| `LS, LD, U, w` | Labour aggregates | `labour_supply`, `labour_demand`, `unemployment_rate`, `wage` | N |
| `Sub_ge, RnD_funds_En` | Green-subsidy levers | `green_plant_subsidy`, `green_rd_subsidy` | N |
| `brown_invest_ban, brown_use_ban` | Regulation timers | `brown_construction_ban_start`, `brown_use_ban_start` | N |
| `t_CO2_en, t_CO2_I1, t_CO2_I2` | Carbon-tax rates by sector | `carbon_tax_*` | N |
| `b_a1, b_b1` | Beta shape for innovation | `innovation_beta_alpha`, `innovation_beta_beta` | N |
| `freqclim, dtclim, dtecon` | Climate timing | `climate_steps_per_year`, `climate_step_years`, `economic_step_years` | G |
| `climsens, forCO2, outrad` | Climate physics | `climate_sensitivity`, `co2_radiative_forcing`, `outgoing_radiation_per_K` | G |

The PR template requires this table to be updated when a new C++ symbol is translated. Scope mistakes ("Looks like a tax rate but I made it global") are the single largest source of cross-nation contamination — so the **scope column is mandatory** in every entry.

---

## Appendix B — Open questions to resolve before milestone 1 (updated)

1. **Time-step length.** Confirm by inspection of a baseline C++ run whether each step is annual or quarterly (README and `dsk_constant.h:8` are ambiguous).
2. **`flag_dskQE` semantics.** Likely on for baseline (`flag_dskQE = 1`); confirm.
3. **Climate sharing in `twoDSKmodel`** — what does the C++ do by default? Match it.
4. **Trade mechanism details.** Read `twoDSKmodel/src/dsk_trade.cpp` carefully before milestone 7; do not depend on the `python2Econ` port's interpretation without cross-checking the C++.
5. **The `gtemp[T][N1][N2]` 3-tensor** — confirm during milestone 1 that it can be replaced by per-firm `Machine` lists.
6. **Foreign firms (`A1f`) under N=1** — keep the original mechanism. Under N≥2 — switch to inter-nation imitation pools with distance parameter (default 1.0 = freely imitable).
7. **Per-nation fossil-fuel price.** Default global; expose a YAML override per nation for sensitivity tests.

---
