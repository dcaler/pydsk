# How the model runs (architecture)

This page is the map. It shows what objects exist, how one simulated year is
executed, and — crucially — **where each piece of behaviour lives**, so that when you
want to change something you know exactly which method to open. If you only read one
page before extending the model, read this one.

## The big picture

```
Simulation                      ← top-level driver; owns the clock
 ├─ global_params               ← GlobalParameters (economy-wide settings)
 ├─ climate                     ← ClimateSystem (shared CO₂ / temperature)
 ├─ trade_network               ← TradeNetwork (off in one-nation runs)
 ├─ output_sink                 ← OutputSink (collects result rows → parquet)
 └─ nations: list[Nation]
     └─ Nation                  ← one economy; runs the phases
         ├─ capital_good_sector       (AgentSet of CapitalGoodFirm)   — sector 1
         ├─ consumption_good_sector   (AgentSet of ConsumptionGoodFirm) — sector 2
         ├─ banking_sector            (AgentSet of Bank)
         ├─ labour_market             (singleton)
         ├─ household_sector          (singleton)
         ├─ government                (singleton)
         ├─ central_bank              (singleton)
         ├─ electricity_producer      (green + brown power-plant fleets)
         ├─ climate_policy            (active policy instruments)
         └─ accounting                (stock-flow consistency checks)
```

Two ideas organise everything:

1. **The `Simulation` owns time; the `Nation` owns behaviour.** `Simulation.step()`
   advances one year and, for each nation, calls three phase methods. Essentially
   all of the economics lives on `Nation` and the agents it holds.
2. **Agents come in two flavours.** Firms and banks are *many*, held in
   **`AgentSet`** collections you can iterate. Everything there's one of — the
   government, central bank, labour market, household sector, electricity producer —
   is a **singleton** object on the `Nation`.

## The Simulation object

`Simulation` (`dsk/simulation.py`) is small and worth knowing by heart:

```python
sim.step()        # advance exactly one year (the heart of the model)
sim.run(n)        # call step() n times
sim.t             # years completed so far (0 on a fresh sim)
sim.flush(dir)    # write the output sink to parquet, return {table: path}
```

`sim.step()` does three things, in order, for the whole world:

```python
def step(self):
    t = self.t + 1                       # 1-indexed year (C++ convention)
    for nation in self.nations:
        nation.production_phase(t)       # ── PHASE 1
    # … TRADE seam (only if enabled) …
    for nation in self.nations:
        nation.dynamics_phase(t)         # ── PHASE 2
    # … CLIMATE seam (emissions → climate → damages) …
    for nation in self.nations:
        nation.closeout_phase(t)         # ── PHASE 3
    self.t += 1
```

So a year is **production → (trade) → dynamics → (climate) → closeout**. The two
parenthesised *seams* are where nations interact with each other and with the planet;
in the one-nation experiments trade is a no-op and climate is a single shared module.

!!! note "Years are 1-indexed inside the model"
    `sim.t` counts from 0 for Python convenience, but every nation method receives
    `t = sim.t + 1`. The model's first economic year is `t = 1`. Several routines
    have a `t == 1` initialisation branch, so this matters if you call phase methods
    yourself.

## The three phases

Each phase is a method on `Nation` that simply calls a sequence of sub-steps **in the
exact order of the original model**. Here is what each one does and the method that
implements it — this table *is* your index of "where things happen."

### Phase 1 — `production_phase(t)`

Firms decide, borrow, build, produce, and burn energy.

| Order | Sub-step (Nation method) | What happens |
|------:|--------------------------|--------------|
| 1 | `set_climate_policy(t)` | **activate policy instruments for this year** and propagate their rates |
| 2 | `compute_bank_client_net_worth()` | banks total up their clients' net worth |
| 3 | `deliver_machines()` | machines ordered last year arrive and join firms' capital |
| 4 | `determine_total_credit()` | each bank computes how much it can lend |
| 5 | `compute_bonds_demand()` | banks set bond demand (dskQE) |
| 6 | `compute_max_credit_per_firm()` | rank firms; set per-firm credit ceilings |
| 7 | `distribute_brochures()` | capital-good firms advertise machines to clients |
| 8 | `plan_investment(t)` | sector-2 firms form expectations, plan output & investment |
| 9 | `allocate_credit_to_demand(t)` | banks grant loans; firms finalise production & orders |
| 10 | `produce_machines()` | sector-1 firms build the ordered machines; hire labour |
| 11 | `electricity_producer.aggregate_demand(...)` | sum firms' electricity demand |
| 12 | `compute_industrial_emissions()` | sector-1/2 process emissions |
| 13 | `run_electricity_market(t)` | dispatch power plants; set the electricity price |
| 14 | `compute_market_shares()` | update sector-2 market shares from competitiveness |

### Phase 2 — `dynamics_phase(t)`

The books are settled: profits, taxes, the budget, monetary policy, entry/exit, R&D.

| Order | Sub-step (Nation method) | What happens |
|------:|--------------------------|--------------|
| 1 | `realise_profits_and_taxes(t)` | sales, profits, government budget, consumer demand, inventories |
| 2 | `update_banks()` | banks realise profit, pay dividends, may fail |
| 3 | `bailout_failed_banks()` | government recapitalises failed banks |
| 4 | `aggregate_macro_indicators(t)` | compute GDP, unemployment, price indices, wage |
| 5 | `set_policy_rate()` | central bank applies the Taylor rule |
| 6 | `process_entry_and_exit()` | dead firms leave; entrants replace them |
| 7 | `advance_technology(t)` | R&D: innovation and imitation update productivities |

### Phase 3 — `closeout_phase(t)`

Apply climate damage, **save the year's results**, and roll state forward.

| Order | Sub-step (Nation method) | What happens |
|------:|--------------------------|--------------|
| 1 | `apply_climate_shocks()` | temperature damages hit the economy |
| 2 | `save_outputs(t)` | **write this year's row to the output sink** |
| 3 | `update_state_for_next_period()` | shift "current" values into "previous" slots |
| 4 | `_retire_old_plants(t)` | scrap end-of-life power plants |

!!! tip "Reading this table is the whole trick"
    Want to change how firms invest? → `plan_investment` / the sector-2 firm.
    Change the tax rule? → `realise_profits_and_taxes` and `government.compute_budget`.
    Record a new number? → `save_outputs`. Do something **every year**? → wrap
    `step()` or override a phase (see [Extending](extending.md)). The phase tables
    above are the address book.

## Agents and how to reach them

The "many" agents live in `AgentSet` collections. An `AgentSet` is iterable and has a
small, Mesa-style helper API:

```python
nation = sim.nations[0]

for firm in nation.consumption_good_sector:      # iterate
    ...

alive = nation.consumption_good_sector.select(lambda f: f.is_alive)   # filter → new set
prices = nation.consumption_good_sector.get("price")                  # → numpy array
nation.consumption_good_sector.do("some_method", arg)                 # call on each
len(nation.banking_sector)                                            # count
```

The singletons are just attributes you read and write directly:

```python
nation.government.debt
nation.central_bank.policy_rate
nation.labour_market.unemployment_rate
nation.electricity_producer.electricity_price
```

Each agent class documents its own state with descriptive attribute names (and the
original C++ symbol in a comment). Open the file for the agent you care about:

| Agent | File |
|-------|------|
| Capital-good firm (sector 1) | `dsk/agents/capital_good_firm.py` |
| Consumption-good firm (sector 2) | `dsk/agents/consumption_good_firm.py` |
| Bank | `dsk/agents/bank.py` |
| Government | `dsk/agents/government.py` |
| Central bank | `dsk/agents/central_bank.py` |
| Household sector | `dsk/agents/household.py` |
| Electricity producer | `dsk/agents/electricity_producer.py` |

## How data flows between steps

Within a year, the sub-steps communicate by **writing onto the agents and the
nation**. A firm's `production` set in phase 1 is read by `realise_profits_and_taxes`
in phase 2; the nation's aggregate `gdp_nominal` set in phase 2 is read by
`save_outputs` in phase 3.

Between years, `update_state_for_next_period()` (closeout step 3) copies each
"current" value into its "previous" slot — e.g. `cpi` → `cpi_prev`,
`firm.net_worth` → `firm.net_worth_prev`. Code that needs *last year's* value reads
the `*_prev` attribute. This is the model's memory, and it is why you should make
per-step changes **inside the phase structure** rather than mutating state at random
times: the `_prev` shift assumes the year ran in order.

## Stock-flow consistency

`nation.accounting` (`NationalAccounts`) exposes per-year consistency checks — real
flows balance (production = consumption + investment + inventory change) and each
bank's balance sheet closes. They are useful guards when you change the financial
side of the model:

```python
nation.accounting.check_real_flows(tol=1e-6 * max(1.0, nation.gdp_nominal))
nation.accounting.check_balance_sheet(tol=1e-6)
```

---

**Next:** [Extending the model](extending.md) — the recipes for changing it.
