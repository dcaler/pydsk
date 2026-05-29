# DSK Python Port — Architecture and Build Plan

A plan to port the C++ Dystopian Schumpeter meeting Keynes (DSK) macro-financial integrated assessment model (Wieners et al., 2025, *Nature Sustainability*) into a clean, object-oriented Python implementation.

The goal is **readability and accessibility**, not performance. The Python version will be slower than the C++ original by ~10×–100× per Monte Carlo run, but its structure should make the model legible to economists, modellers, and students who would not otherwise touch the C++ codebase.

---

## 1. Guiding principles

1. **Agents are objects.** Each firm, bank, plant, household, and policy authority is an instance of a class. State lives on the agent; behaviour lives in the agent's methods (or a strategy object passed to it).
2. **English, descriptive names.** No `mi2`, `nu`, `xi`, `psi3`, `Wtot`, `tao`, `Anew`, `Imm`, `Pat`, `wu`, `LDff`, etc. Italian comments and abbreviations are translated. A bilingual name map (Appendix A) preserves traceability back to the C++ original for verification.
3. **No global state.** The C++ model uses ~3000 global variables (`dsk_globalvar.h`). The Python version routes everything through a `Simulation` (a.k.a. `World`) object that owns the agents, markets, and policy authorities.
4. **Flags become enums or strategy objects.** The ~70 C++ flags (`dsk_flag.h`) often choose between alternative behavioural rules. Each gets either an enum value, a boolean attribute on `Scenario`, or — where the alternatives are substantial — a separate strategy class.
5. **Parameters are data, not code.** The ~250 C++ constants become a `Parameters` dataclass loaded from YAML / TOML. Different scenarios produce different `Parameters` instances rather than recompilation.
6. **Vectorise inside sectors, not across them.** A `CapitalGoodSector` (collection) holds its firms as a list and may expose numpy arrays for hot loops (price-competitiveness, market-share replicator). Across-sector matching uses Python-level objects. This keeps a single OOP mental model without sacrificing all performance.
7. **Reproducibility first.** A single seeded `numpy.random.Generator` is threaded through the simulation. Monte Carlo replicates differ only in seed.
8. **Tests track the C++ output.** Every milestone (Section 6) is gated by reproducing a set of macro time series within tolerance of a C++ reference run (Section 7).

---

## 2. What the model does (short reference)

The DSK model simulates an economy of heterogeneous firms, banks, an electricity producer, and a government, from ~2000 to ~2160. Climate is coupled via a C-ROADS-style box. Decarbonization policies (carbon taxes, green subsidies, fossil-fuel bans, electrification mandates) are tested.

**Key actors** (with C++ name → Python name):

| C++ symbol | Role | Python class |
|---|---|---|
| `N1` firms in sector 1 | produce machines, do R&D | `CapitalGoodFirm` |
| `N2` firms in sector 2 | produce consumption goods, hold machines, set prices | `ConsumptionGoodFirm` |
| `N1f` firms (foreign) | provide an exogenous tech frontier reference | `ForeignCapitalGoodFirm` |
| Multiple banks | extend credit, hold deposits, fail/get bailed | `Bank` |
| Single energy monopolist | invests in green/brown power plants, R&Ds | `ElectricityProducer` |
| Plant vintages (`G_de`, `G_ge`, `CF_*`, `EM_de`, `A_de`) | individual plants by vintage | `PowerPlant` (subclassed `GreenPlant`/`BrownPlant`) |
| `Cat`, `Con`, `Ton`, `Tmixed`, `biom`, `humm` | atmosphere–ocean–biosphere carbon and heat | `ClimateSystem` |
| Government tax/subsidy variables | fiscal authority | `Government` |
| Taylor rule, `r`, `r_cbreserves` | monetary authority | `CentralBank` |
| Climate-policy parameters (`t_CO2_*`, `Sub_ge`, `brown_invest_ban`, etc.) | rules | `ClimatePolicy` (composed of `CarbonTax`, `GreenSubsidy`, `ConstructionBan`, `ElectrificationMandate`) |
| `LS`, `LD`, `w`, `wu`, `U` | aggregate labour market | `LabourMarket` (households implicit, see §3.10) |

**Main loop** (from `dsk_main.cpp`, lines 92–376; mirrors the README pseudocode):

```
for each time step t:
    set_climate_policy()                         # carbon tax level, subsidy, bans
    compute_bank_client_net_worth()              # WTOTCLIENT
    deliver_ordered_machines()                   # MACH
    determine_total_credit()                     # TOTCREDIT
    allocate_max_credit_to_firms()               # MAXCREDIT
    distribute_brochures()                       # BROCHURE
    plan_investment()                            # INVEST → EXPECT, SCRAPPING, ORD
    allocate_credit_to_demand()                  # ALLOCATECREDIT
    produce_machines()                           # PRODMACH (→ LABOR, EN_DEM, CANCMACH)
    compute_industrial_emissions()               # EMISS_IND
    run_energy_sector()                          # ENERGY (→ COST_GREEN_PLANT, ELECTRICITY_MARKET)
    compute_market_shares()                      # COMPET2
    realize_profits_and_taxes()                  # PROFIT (→ GOV_BUDGET, ALLOC)
    update_banks()                               # BANKING
    bailout_failed_banks()                       # BAILOUT
    aggregate_macro_indicators()                 # MACRO (→ WAGE)
    set_policy_rate()                            # TAYLOR
    process_entry_and_exit()                     # ENTRYEXIT
    advance_technology()                         # TECHANGEND (or TECHANGEX)
    if t > t_start_climate and t % freq_climate == 0:
        step_climate()                           # CLIMATEBOX
    apply_climate_shocks()                       # SHOCKS (off in this version)
    save_outputs()                               # SAVE
    update_state_for_next_period()               # UPDATE
```

---

## 3. Agent classes (state and behaviour)

For each class below: **state** is the persistent attributes; **methods** are the actions invoked from the main loop; **collaborators** lists who it talks to.

### 3.1 `CapitalGoodFirm`
*Originally `N1` firms (sector 1 / machine tools).*

- **State:** unit production cost; sales-price markup; machine productivity vector (labour, energy efficiency, environmental cleanliness, electrification fraction); R&D budget; net worth; debt; client list (consumption firms it has matched with); current and proposed innovation/imitation technology candidates; patent timer (if `flagPAT > 0`).
- **Methods:**
  - `do_innovation_and_imitation()` — Bernoulli trial on R&D, draw from beta distribution for technology gains (`uu1_*`, `uu2_*`, `b_a1`, `b_b1`).
  - `choose_technology_for_sale()` — pick from {incumbent, innovated, imitated} that minimises lifetime cost `p_h + b·c_h` (paper eq. for `c_{i,t}`).
  - `send_brochure(client_pool)` — gather new customers and resend to existing.
  - `produce_machines(orders)` — convert orders × machine size into production; hire labour; consume fuel/electricity.
  - `pay_wages_and_rd()`, `service_debt()`, `realise_profit()`.
- **Collaborators:** `Bank` (credit), `ConsumptionGoodFirm` (orders), `ElectricityProducer` (energy input), `Government` (carbon tax, electrification fine).

### 3.2 `ConsumptionGoodFirm`
*Originally `N2` firms (sector 2 / manufacturing).*

- **State:** capital stock (a list of `Machine` instances by vintage with their own productivity); expected demand history; inventory; net worth; debt; price; markup; competitiveness; market share; supplier link (the capital-good firm that sent it brochures and last sold to it); bank link.
- **Methods:**
  - `form_demand_expectation()` — naïve / adaptive rules (`flagEXP`).
  - `plan_substitution_investment()` — scrap rule based on payback `b` (paper eq.).
  - `plan_expansion_investment()` — close gap between desired capital and current capital.
  - `submit_order(capital_good_supplier)`.
  - `produce_goods(actual_capital, labour)` — apply effective machine productivity; consume electricity & fuel.
  - `set_price()` — markup over unit cost (`p2 = (1+mu2) c2`).
  - `compete_for_share()` — input to replicator dynamics.
  - `pay_taxes_and_dividends()`.
- **Collaborators:** `CapitalGoodFirm` (machine supplier), `Bank`, `ElectricityProducer`, `Government`, `LabourMarket`.

### 3.3 `Machine`
*A piece of capital owned by a `ConsumptionGoodFirm`.*

- **State:** vintage age; labour productivity `A`; energy efficiency `A_en` (1/`b_en`); environmental cleanliness `A_ef`; electrification fraction `A_el`; supplier ID; size (`dim_mach`).
- **Methods:** age-tick; produce; compare-with-newer-technology (for scrapping decisions).
- Tracked in the original as the dense tensor `g[T][N1][N2]` (machine-frequency-by-vintage-by-supplier-by-owner). In Python this is replaced by each firm holding a list of `Machine` instances (or a 2-D ragged array internally).

### 3.4 `Bank`
*Originally the `NB` banks.*

- **State:** equity; deposits; reserves; loan portfolio (`BankMatch`); bond holdings; bad debt; net worth; client list; active flag.
- **Methods:**
  - `compute_max_credit()` — Basel II rule or deposit multiplier (`flagtotalcredit`).
  - `rank_clients_and_extend_credit()` — by net-worth-to-sales ratio.
  - `collect_interest_and_principal()`.
  - `buy_bonds()` — proportional to share rule (`bonds_rule`).
  - `compute_profit_and_dividend()`.
  - `fail_or_get_bailed_out()` — via `BailoutPolicy`.
- **Collaborators:** firms (lender), `CentralBank` (reserves, lender of last resort), `Government` (bailout).

### 3.5 `ElectricityProducer` (singleton monopolist)

- **State:** lists of `GreenPlant` and `BrownPlant` instances (by vintage); cumulative R&D spending on green and brown; cost frontiers (`CF_ge`, `CF_de`); thermal efficiency frontier (`A_de`); emission intensity frontier (`EM_de`); revenue; net worth; price of electricity.
- **Methods:**
  - `forecast_demand(history)` — used to plan capacity (`D_en_build`).
  - `decide_capacity_expansion()` — green-vs-brown decision via payback rule with subsidy, regulation, and "hurry cost" (`exp_quota`, `repl_quota_*`).
  - `decide_premature_replacement()` — replace old brown with green when cost frontier allows it (`prudinv`, `flag_early_plants`).
  - `do_rd_green_and_brown(share_dirty)` — Bernoulli trials, beta-distributed gains; mirrors capital firm innovation but with separate productivity dimensions (cost, thermal efficiency, emission intensity).
  - `dispatch_merit_order()` — order plants by unit cost and serve demand sequentially.
  - `set_price()` — markup over marginal/inframarginal cost (`flag_electricity_bidding`).
  - `pay_carbon_tax()`, `receive_subsidy()`, `apply_construction_ban()`.
- **Collaborators:** firms (energy demand), `Government` (subsidy / regulation), `Bank` (rare, only when bailout requires).

### 3.6 `PowerPlant` (abstract → `GreenPlant`, `BrownPlant`)

- **Common state:** vintage; capacity; build cost paid; subsidy received; lifetime; alive flag.
- **`BrownPlant` extra state:** thermal efficiency `A_de`; emission intensity `EM_de`; unit operating cost (fuel + carbon tax).
- **`GreenPlant` extra state:** zero operating cost; no emissions. Just a build-cost vintage.
- **Methods:** `step_age()`; `unit_cost(fuel_price, carbon_tax)`; `is_obsolete(best_cost, threshold)`; `retire()`.

### 3.7 `Government`

- **State:** debt stock; outstanding bonds; deficit; tax rates (income, profit, bank-profit, sector-specific carbon); subsidy budget; bailout expenditure; R&D top-up budget.
- **Methods:**
  - `collect_taxes(firms, banks, energy)` — `flagTAX`.
  - `pay_unemployment_subsidy(labour_market)` — `flagC`.
  - `issue_bonds()` — `flag_bonds`.
  - `pay_bank_bailout()`, `pay_energy_bailout()`.
  - `run_balanced_budget_check()` — `flag_balancedbudget`.

### 3.8 `CentralBank`

- **State:** policy rate `r`; reserve rate; bond holdings (under QE flag); inflation target; unemployment target.
- **Methods:**
  - `apply_taylor_rule(inflation, unemployment)` — `flagTAYLOR`.
  - `remunerate_reserves()`.
  - `buy_residual_bonds()` — closes gap between supply and bank demand.

### 3.9 `ClimateSystem`

- **State:** atmospheric carbon `Cat`; carbon in each of `ndep` ocean layers `Con`; ocean heat `Hon`; ocean temperatures `Ton`; surface temperature `Tmixed`; biospheric carbon `biom`; humus carbon `humm`; yearly emissions buffer.
- **Methods:**
  - `step(emissions_this_year)` — discrete-time C-ROADS: photosynthesis & decay → atmosphere–ocean carbon equilibration → radiative forcing → mixed-layer heat balance → diffusion to deep ocean.
  - `temperature_anomaly()` — returns `Tmixed - T_pre`.
  - Alternative `step_cumulative()` for the simpler `flag_cum_emissions=1` mode.

### 3.10 `LabourMarket` and `HouseholdSector`

The C++ model represents households implicitly through aggregates: total labour supply `LS`, labour demand `LD`, wage `w`, unemployment subsidy `wu`, consumption budget = wages + subsidies. There are no individual household objects.

We keep this convention by default — `HouseholdSector` is a single object aggregating labour and consumption — but design it so that an extension can replace it with a list of `Household` agents (e.g. heterogeneous income, propensity to consume). This is a natural future hook for distributional analysis.

- **`LabourMarket` state:** total supply; total demand by capital-firm R&D, capital-firm production, cons-firm production, energy-firm R&D, energy-firm construction, fuel extraction; wage; unemployment rate; full-employment counter.
- **`LabourMarket` methods:** `set_wage()` (`flagWAGE` — adjusts to inflation and unemployment gap); `ration_to_demands()` (when LD > LS).
- **`HouseholdSector` methods:** `collect_income(wages, subsidies, dividends)`; `consume(prices)` (allocates total consumption budget to consumption-good firms via market share — `ALLOC`).

### 3.11 `ClimatePolicy`

Top-level container of policy instruments active in the current scenario. Each instrument is its own object, so scenarios are built compositionally.

- **`CarbonTax`** — sector-specific rate `t_CO2_{en,I1,I2}`, schedule (constant in real terms, growing, etc.), rebate destination (none / households / firms-as-RD-subsidy).
- **`GreenConstructionSubsidy`** — `Sub_ge` per plant, eligibility, cap.
- **`GreenRDSubsidy`** — `RnD_funds_En`, eligibility.
- **`BrownConstructionBan`** — start time, grace period.
- **`ElectrificationMandate`** — start time, target electrification fraction, fine schedule.

Each instrument has `is_active(t)` and `apply(...)` methods; the `ClimatePolicy` container calls them in `Simulation.set_climate_policy(t)`.

### 3.12 `Simulation` (the world / orchestrator)

- **State:** all sector objects (`CapitalGoodSector`, `ConsumptionGoodSector`, `BankingSector`); `ElectricityProducer`; `Government`; `CentralBank`; `LabourMarket`; `HouseholdSector`; `ClimateSystem`; `ClimatePolicy`; `Parameters`; RNG; current time step `t`; output sink.
- **Methods:** `initialise()` (replaces `INITIALIZE`); `step()` (one period); `run(T)` (full simulation); `run_monte_carlo(MC, T)` (the outermost loops).

---

## 4. Module / package layout

```
dskPython2/
├── planningDocs/          # this plan + papers
├── dsk/
│   ├── __init__.py
│   ├── parameters.py      # Parameters dataclass; loaders from YAML/TOML
│   ├── scenarios.py       # Baseline, Tc, T2, T2h, T2i, BE, CER, BCER, BCERT, …
│   ├── rng.py             # seeded numpy.random.Generator wrapper
│   ├── agents/
│   │   ├── capital_good_firm.py
│   │   ├── consumption_good_firm.py
│   │   ├── machine.py
│   │   ├── bank.py
│   │   ├── electricity_producer.py
│   │   ├── power_plant.py        # GreenPlant, BrownPlant
│   │   ├── government.py
│   │   ├── central_bank.py
│   │   └── household.py          # HouseholdSector + (future) Household
│   ├── sectors/                 # collections that hold homogeneous agents
│   │   ├── capital_good_sector.py
│   │   ├── consumption_good_sector.py
│   │   ├── banking_sector.py
│   │   └── labour_market.py
│   ├── markets/                 # cross-sector interactions
│   │   ├── credit_market.py     # TOTCREDIT, MAXCREDIT, ALLOCATECREDIT
│   │   ├── machine_market.py    # BROCHURE, INVEST, PRODMACH
│   │   ├── goods_market.py      # COMPET2, ALLOC
│   │   └── electricity_market.py
│   ├── climate/
│   │   ├── climate_system.py    # C-ROADS box
│   │   └── emissions.py         # EMISS_IND aggregation
│   ├── policy/
│   │   ├── climate_policy.py
│   │   ├── carbon_tax.py
│   │   ├── green_subsidy.py
│   │   ├── brown_ban.py
│   │   ├── electrification_mandate.py
│   │   ├── monetary_policy.py   # Taylor rules, QE
│   │   ├── fiscal_policy.py     # balanced-budget rules, bond issuance
│   │   └── bailout.py
│   ├── innovation/              # the Schumpeterian search machinery
│   │   ├── bernoulli_trial.py
│   │   └── beta_draw.py
│   ├── simulation.py            # Simulation/World class, main loop
│   ├── monte_carlo.py
│   └── io/
│       ├── output.py            # SAVE-equivalents; writes parquet or csv
│       └── config.py            # YAML / TOML loading
├── configs/
│   ├── baseline.yaml
│   ├── BCERT.yaml
│   └── …                        # one file per scenario in Wieners Table 1
├── tests/
│   ├── unit/                    # per-class behaviour tests
│   ├── integration/             # one-step end-to-end + invariants
│   └── reference/                # compare against C++ output series
├── notebooks/                   # exploratory & paper-figure reproduction
├── cli.py                       # invoke a scenario from the command line
└── README.md
```

---

## 5. Cross-cutting design decisions

### 5.1 Numerical kernel
- **NumPy** for arrays; **SciPy** only where strictly necessary (beta distribution sampling is already in `numpy.random.Generator.beta`).
- No newmat substitute — replace `Matrix`, `RowVector`, `ColumnVector` with `np.ndarray`. The C++ code's 1-based indexing becomes 0-based in Python (this requires careful translation of every loop).
- **Vectorisation policy.** Each sector exposes a `state_array(field)` that copies the requested attribute from its agents into a numpy array, and a `scatter(field, array)` that writes back. Hot inner loops (replicator dynamics for market shares, credit ranking, plant dispatch) use these arrays; one-off agent decisions stay as method calls.

### 5.2 Stock-flow consistency
The DSK is stock-flow consistent in the recent versions (Reissl et al. 2025, ref. 57). Each step must close:
- aggregate output = consumption + investment + inventories change + government spending
- assets of all agents = liabilities of all agents
- aggregate emissions = energy emissions + industrial process emissions

A `Simulation._check_accounting(tol)` method runs after every step under a debug flag (`assert` raised if imbalance > `tol`). Replaces the C++ `cout` debugging.

### 5.3 RNG and determinism
A single `numpy.random.Generator` is constructed from a seed at the top of `Simulation`. It is **passed explicitly** to every agent that needs randomness via `__init__` (or via a `World.rng` accessor). Monte Carlo loop generates child generators with `numpy.random.SeedSequence.spawn`. The C++ code uses Numerical Recipes' `ran1` / `gasdev` / `bnldev` / `betadev` — these are replaced by `Generator.uniform`, `.standard_normal`, `.binomial`, `.beta`. **Exact bit-for-bit reproduction of the C++ output is not a goal**; reproduction of the macro behaviour and stylised facts is.

### 5.4 Time semantics
The C++ comment "T=220, used to be 500 when time steps were quarters" implies the current canonical step is one year (T=220 ≈ 1940–2160 or 2000–2220). The climate box re-runs every `freqclim` economic steps with climate-step length `dtclim`. The `Parameters` dataclass carries:
- `economic_step_years` (default 1.0)
- `climate_step_years` (default 1.0)
- `economic_steps_per_climate_step` (=1 if both equal)
- `total_economic_steps` (replaces `T`)
- `spin_up_steps` (replaces `t_spinup`)
- `climate_start_step` (replaces `t_start_climbox`)

### 5.5 Configuration and scenarios

A `Scenario` is a `Parameters` + `ClimatePolicy` + initial-condition file. Concrete scenarios from Wieners Table 1 are translated to YAML files (see `configs/`). Composing scenarios (`BCERT = B + C + E + R + T`) is done by merging YAML files.

This replaces the C++ workflow of copying `0_dsk_*.cpp` files from `files_BCERT/` over `basecode/` and rebuilding — a fragile process that the README acknowledges with multi-step manual instructions.

### 5.6 Output
- Per-step macro time series → `parquet` (columnar, compressed, fast to read).
- Per-agent state at sparse intervals → `parquet` keyed by `(monte_carlo_run, step, agent_type, agent_id)`.
- Optional: keep CSV alongside parquet to ease comparison with C++ outputs.
- The `flag_writemicro` knob becomes a config option.

### 5.7 Error handling
- `assert` for invariants (debug builds).
- Custom exceptions: `EconomicCollapseError`, `BankSectorCollapseError`, `EnergyFirmInsolventError`. The C++ uses `break` in the main loop and a counter (`consgood_collapse`); we keep going (or abort, configurably) and log the event.

### 5.8 Verification harness
Beyond unit tests, a **regression notebook** reproduces the figures from Wieners et al. 2025 (Figs. 1, 3, 4) under the matching scenarios. The notebook is part of the milestone gate (Section 6).

---

## 6. Build milestones

Each milestone is a working simulation that produces meaningful output; tests gate the next one.

| # | Milestone | Deliverable | Verification |
|---|---|---|---|
| **0** | Project scaffold, RNG, parameter loading, baseline config | Project layout in place; `Parameters` loads `baseline.yaml`; RNG reproducible | `pytest tests/unit/test_parameters.py` |
| **1** | KS10 core (closed economy, no climate) — capital firms, consumption firms, single bank, household sector | Step-able simulation that produces GDP, unemployment, wage time series | Compare GDP growth, unemployment rate distribution against Dosi-Fagiolo-Roventini stylised facts (cyclical co-movements, firm-size Pareto) |
| **2** | Multi-bank, central bank, government, fiscal/monetary policy | Reproduces KS15 stylised facts | Time series of `Deb/GDP`, inflation, policy rate |
| **3** | Energy module — `ElectricityProducer`, `PowerPlant` vintages, dispatch, energy R&D | Energy demand met; green share evolves | Baseline scenario green-share trajectory ≈ Wieners Fig. 1f (Baseline) |
| **4** | Industrial emissions, `ClimateSystem` (C-ROADS), temperature feedback off | Baseline emissions and temperature trajectory | Reproduce Baseline `Warming` curve (Wieners Fig. 1a, black line) within tolerance |
| **5** | `ClimatePolicy` instruments — carbon tax, green subsidy, brown ban, electrification mandate | Each instrument plugs into `Simulation` | Reproduce Tc, T2, BE, CER scenarios qualitatively |
| **6** | Full set of Wieners (2025) scenarios | All policy mixes in Table 1 | Reproduce Wieners Figs. 1–5 in shape and ranking; ensemble means within ~20% of paper |
| **7** | Performance and ergonomics | Numpy vectorisation for hot loops; CLI runner; multi-process Monte Carlo via `multiprocessing` | Single MC run < 30 min on 1 modern core |
| **8** | Optional extensions | Heterogeneous `Household` agents; networked banking; alternative climate boxes (DICE, FaIR) | — |

Milestones 1–6 are required to call the port "done"; 7 is a polish pass; 8 is the user's research surface — explicitly enabled by the OOP design.

---

## 7. Verification against the C++ original

Because the RNG streams differ, bit-equal output is not achievable. We instead require:

1. **Stylised-fact tests.** Pareto distribution of firm sizes; cyclical co-movement of investment, consumption, employment; persistent unemployment shocks; emissions–temperature lag.
2. **Ensemble-mean tracking.** For each canonical scenario, run 50 MC replicates and require the ensemble mean of the published indicators (warming, emissions, electrification, renewable share, GDP, unemployment, bankruptcy probability, fiscal cost) to lie within paper's 10th–90th percentile band.
3. **Sensitivity matches.** Direction-of-change tests: e.g. switching electrification mandate ON should reduce time-to-90%-electrification by approximately the gap visible in Fig. 3e. We codify "approximately" as 80% confidence that the Python ensemble's median crosses the threshold before the C++ ensemble's 90th percentile.
4. **A reference C++ run is precomputed once** (the `run_scenario_B/`, `output_B/`, `dsk_T2`, etc. already on disk are checked in as expected outputs). The verification notebook in `tests/reference/` loads both and plots them side-by-side.

---

## 8. Translation challenges and how we handle them

| Problem | C++ | Python plan |
|---|---|---|
| 1-based indexing | `g[T][N1][N2]` indexed 1..N1, 1..N2 | 0-based throughout; consistency enforced by tests |
| ~3000 globals in `dsk_globalvar.h` | Single namespace | Carried as attributes on `Simulation` or sector objects |
| 70+ behavioural flags | `const int flag_*` | Enums in `parameters.py`; non-default branches that are explicitly marked NOT RECOMMENDED in the C++ comments are **not ported in milestone 1–6**. They become future opt-in strategies. |
| Newmat `Matrix`/`RowVector` | Custom matrix library | `np.ndarray` |
| File I/O via `cout` and `ofstream` | Per-experiment text files | `parquet` via `pyarrow`; logging via `logging` module |
| Patent durations stored on firms | Integer countdown per firm | `Machine.patent_remaining` attribute; tested under `flagPAT > 0` mode |
| Output filenames generated by `GENFILE*` | 30+ near-duplicate functions | Single `output.OutputSink` class with named series |
| Italian comments (≈30% of code) | "Salario sussistenza", "Macchineria consegnata", "Calcola domanda di lavoro" | Translated in Appendix A; rendered as English docstrings in Python |
| Numerical Recipes `ran1`, `gasdev`, `bnldev`, `betadev` | Custom RNG | `numpy.random.Generator` |

---

## 9. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Behaviour drifts from C++ in milestone 3–4 (energy/climate coupling) | High | High | Build only after milestones 1–2 are gold; verify against `output_B/` files at each step |
| Performance unusably slow (e.g. > 4 h per MC run) | Medium | Medium | Vectorise sectors before declaring done; profile early; multiprocessing across MC |
| Climate-box numerical instability differs from C++ (Reveille iteration is fixed-point) | Medium | Medium | Reuse the C++ iteration tolerances; test against precomputed atmospheric/ocean carbon series |
| OOP overhead obscures stock-flow accounting | Medium | High | `_check_accounting()` hook every step; keep balance-sheet tests visible |
| Italian translations introduce semantic drift | Low | Medium | Appendix A is the canonical mapping; PRs that touch a renamed variable update the mapping |
| Scenario YAML diverges from C++ flag combinations | Low | Medium | Each scenario YAML is tagged with the C++ commit hash / file set it corresponds to |

---

## 10. Out of scope (for now)

- Climate damages on firms' productivity (`flag_shocks > 0`) — disabled in Wieners 2025.
- Hydrogen / biomass / negative-emissions abatement pathways — paper notes these as future work.
- Endogenous political economy / lobbying (paper Discussion §4).
- Households as individual agents (Section 3.10 keeps this as a future hook).
- The dskQE variant (`flag_dskQE` features) — initially keep on, verify, then expose as a strategy.
- The KS10 / KS13 / KS15 flag combinations preserved in the C++ for historical reasons — not exposed unless a user explicitly opts in.

---

## Appendix A — Bilingual name map (partial; to be completed during milestone 1)

| C++ | Italian gloss | Python |
|---|---|---|
| `N1` | Numero imprese industria machine tools | `n_capital_good_firms` |
| `N2` | Numero imprese industria manufatturiera | `n_consumption_good_firms` |
| `T` | Numero cicli temporali | `total_steps` |
| `MC` | Numero replicazioni Monte Carlo | `n_monte_carlo_runs` |
| `nu` | Parametro spesa R&D | `rd_intensity` |
| `xi` | Alloca spesa R&D tra innovazione e imitazione | `innovation_vs_imitation_share` |
| `o1, o11, o12` | Produttività spesa R&D innovazione | `rd_productivity_innovation_*` |
| `mi1`, `mu2` | Mark-up industria 1 / 2 | `markup_capital`, `markup_consumption` |
| `Gamma` | Regola numero nuovi clienti contattati | `brochure_outreach_rate` |
| `chi` | Replicator dynamics industria consumption good | `replicator_intensity` |
| `psi1`, `psi2`, `psi3` | Wage equation parameters | `wage_inflation_sens`, `wage_productivity_sens`, `wage_unemployment_sens` |
| `theta` | Scorte attese (fraction of demand) | `inventory_target_share` |
| `u` | Utilizzo capacità produttiva | `capacity_utilisation_target` |
| `b` | Pay-back | `payback_threshold` |
| `agemax` | (machine max age) | `machine_max_age` |
| `dim_mach` | Dimensione macchinario | `machine_size` |
| `wu` | Salario disoccupazione | `unemployment_replacement_rate` |
| `aliq`, `aliqb` | Aliquota imposta (income, bank) | `income_tax_rate`, `bank_profit_tax_rate` |
| `W1, W2` | Ricchezza netta sector 1 / 2 | `net_worth_capital_firms`, `net_worth_consumption_firms` |
| `S1, S2` | Sales | `sales_capital_firms`, `sales_consumption_firms` |
| `Q1, Q2` | Produzione | `output_capital`, `output_consumption` |
| `D1, D2` | Domanda | `demand_capital`, `demand_consumption` |
| `N` (matrix) | Scorte (inventories of cons.firms) | `inventories` |
| `f1, f2, fB` | Quota di mercato cap/cons/bank | `market_share_*` |
| `tao` | Generazione macchinario (vintage) | `machine_vintage` |
| `Anew`, `A1inn`, `A1imm` | Productivity of candidate technology | `tech_candidate_innovation`, `tech_candidate_imitation` |
| `A1p` | Productivity of production technique (cap firm) | `production_technique_productivity` |
| `A1p_en`, `A1p_ef`, `A1p_el` | EE, EF, electrification of technique | `energy_efficiency_*`, `environmental_cleanliness_*`, `electrification_fraction_*` |
| `K_ge`, `K_de` | green / dirty plant count | `n_green_plants`, `n_brown_plants` |
| `G_de`, `G_ge` | plant count by vintage | `brown_plants_by_vintage`, `green_plants_by_vintage` |
| `A_de` | thermal efficiency brown | `brown_thermal_efficiency` |
| `EM_de` | emission per fuel brown | `brown_emission_intensity` |
| `CF_ge`, `CF_de` | unit construction cost | `green_build_cost`, `brown_build_cost` |
| `c_en`, `pf` | energy unit cost, fossil-fuel price | `electricity_unit_cost`, `fossil_fuel_price` |
| `pf*(1+t_CO2)` | fuel price including tax | `fossil_fuel_price_with_tax` |
| `Cat`, `Con`, `Tmixed`, `Ton`, `biom`, `humm` | C-ROADS state | `atmospheric_carbon`, `ocean_carbon`, `surface_temperature`, `ocean_temperature`, `biospheric_carbon`, `humus_carbon` |
| `Tax`, `Deb`, `Def`, `GDPm`, `G` | macro aggregates | `tax_revenue`, `public_debt`, `public_deficit`, `nominal_gdp`, `government_spending` |
| `r`, `r_deb`, `r_depo`, `r_cbreserves` | rates | `policy_rate`, `lending_rate`, `deposit_rate`, `reserve_rate` |
| `LS`, `LD`, `U`, `w` | labour aggregates | `labour_supply`, `labour_demand`, `unemployment_rate`, `wage` |
| `Sub_ge`, `RnD_funds_En` | green-subsidy levers | `green_plant_subsidy`, `green_rd_subsidy` |
| `brown_invest_ban`, `brown_use_ban` | regulation timers | `brown_construction_ban_start`, `brown_use_ban_start` |
| `t_CO2_en`, `t_CO2_I1`, `t_CO2_I2` | carbon-tax rates | `carbon_tax_energy`, `carbon_tax_capital_sector`, `carbon_tax_consumption_sector` |
| `dim_mach` | machine size | `machine_size_units` |
| `agemax` | maximum machine age | `machine_max_age` |
| `b_a1`, `b_b1` | beta-distribution shape params for innovation | `innovation_beta_alpha`, `innovation_beta_beta` |

(Completed during milestone 1; PR template requires the table to be updated when a new C++ symbol is translated.)

---

## Appendix B — Open questions to resolve before milestone 1

1. **Time-step length** — confirm by running C++ baseline once and inspecting the emissions/GDP timestamps whether each step is annual or quarterly in the current version. The README and constants are ambiguous.
2. **`flag_dskQE` semantics** — is the QE machinery part of the canonical Wieners 2025 model or a separate variant? (`dsk_main.cpp` line 16 says baseline `=1`.)
3. **Stock-flow consistency tolerance** — what residual is the C++ model itself accepting? (Run `_check_accounting()` mentally during the C++ run and pick a tolerance from the observed drift.)
4. **Patent system** — `flagPAT=0` in the baseline; safe to omit until milestone 8.
5. **`gtemp[T][N1][N2]`** — does this 3-D tensor truly need to persist across years, or is it only used inside one step? (Affects whether `Machine` instances suffice.) Audit during milestone 1.
6. **Output schema** — fix a column list per series before writing code, to keep `parquet` writes stable across milestones.

---
