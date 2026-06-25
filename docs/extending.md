# Extending the model

This is the page pydsk exists for. The C++ model is hard to change; pydsk is built so
that adding behaviour is a small, local edit. This page is a set of **recipes**,
ordered from least to most invasive. Each one tells you *where* to put code and *why
there*.

Before you start, make sure you've skimmed [How the model runs](architecture.md) —
especially the **phase tables**, which tell you which method owns which behaviour.

!!! warning "One rule that saves you later"
    pydsk reproduces the C++ model **bit-for-bit** in deterministic mode, and the
    test suite enforces it. Any change that alters numbers will (correctly) break the
    golden-output test. That's a feature: it tells you the moment your change affects
    results. When you *intend* to change behaviour, regenerate the golden fixtures on
    purpose. See [Fidelity & randomness](fidelity-and-rng.md#i-changed-behaviour-on-purpose-now-what).

---

## "I want an agent to do something every step"

This is the most common request, so it leads. There are three tiers, from a no-touch
wrapper to a proper in-model phase. Pick the lowest tier that does what you need.

### Tier 1 — a custom run loop

If you want to **observe or nudge** the model each year — log an extra variable,
inject a shock, stop early on a condition — don't touch the model at all. Drive it
yourself:

```python
from dsk.io.config import load_simulation

sim = load_simulation("configs/simulations/one_nation_baseline.yaml")
nation = sim.nations[0]

history = []
for year in range(1, 221):
    sim.step()                                   # run the whole year

    # --- your per-step code here ---
    history.append({
        "t": year,
        "u": nation.labour_market.unemployment_rate,
        "n_alive": sum(f.is_alive for f in nation.consumption_good_sector),
    })

    # example shock: at year 100, halve every firm's net worth
    if year == 100:
        for firm in nation.consumption_good_sector:
            firm.net_worth *= 0.5
```

This runs **after** each fully-completed year, so the state you read is end-of-year
and consistent. It is the safest extension point: you can't corrupt the phase order
because you only act between years.

**Use this when** your behaviour is "watch the model and occasionally poke it."

### Tier 2 — inject a step *inside* a phase (subclass `Nation`)

If your behaviour must run **at a specific point within the year** — say, after firms
plan but before banks lend — subclass `Nation` and override the relevant phase,
calling `super()` and inserting your step:

```python
from dsk.nation import Nation

class MyNation(Nation):
    def production_phase(self, t: int) -> None:
        self.set_climate_policy(t)
        self.compute_bank_client_net_worth()
        self.deliver_machines()
        self.determine_total_credit()
        self.compute_bonds_demand()
        self.compute_max_credit_per_firm()
        self.distribute_brochures()
        self.plan_investment(t)

        self.my_extra_step(t)          # ← your new sub-step, in the exact spot

        self.allocate_credit_to_demand(t)
        self.produce_machines()
        self.electricity_producer.aggregate_demand(
            t, self.capital_good_sector, self.consumption_good_sector
        )
        self.compute_industrial_emissions()
        self.run_electricity_market(t)
        self.compute_market_shares()

    def my_extra_step(self, t: int) -> None:
        # e.g. a windfall tax on the most profitable firms before they borrow
        for firm in self.consumption_good_sector:
            if firm.gross_operating_margin > 0:
                firm.net_worth -= 0.01 * firm.gross_operating_margin
```

Copy the body of the phase from `dsk/nation.py` and slot your call where it belongs.
The sub-step order matters (it's the model's logic), so insert, don't reorder.

To actually use `MyNation`, build the simulation with it. The simplest route is to
construct nations yourself rather than via `load_simulation`, or load normally and
swap behaviour in. A minimal hand-built run:

```python
import numpy as np
from dsk.parameters.global_parameters import GlobalParameters
from dsk.parameters.nation_parameters import NationParameters
from dsk.simulation import Simulation
from dsk.io.output_sink import OutputSink

gp = GlobalParameters()
nation = MyNation("global", params=NationParameters())
sim = Simulation(gp, [nation], rng_seed=42)
sim.output_sink = OutputSink()
nation.sink = sim.output_sink
nation.initialise_from_parameters(gp)
sim.run(gp.total_steps)
sim.flush("out/")
```

!!! tip "If you only need it after the year, prefer Tier 1"
    Overriding a phase means keeping its body in sync with the original. Only reach
    for Tier 2 when the *timing within the year* genuinely matters.

### Tier 3 — add a behaviour to an agent

If the new behaviour is conceptually part of what an agent *is* (e.g. firms now also
hold a cash buffer and adjust it), add a method to the agent class and call it from
the right phase. Put the state in the agent's `__init__`, the logic in a new method,
and the call in the phase (via Tier 2):

```python
# in dsk/agents/consumption_good_firm.py, ConsumptionGoodFirm.__init__:
self.cash_buffer_target = 0.0

# a new method on the firm:
def update_cash_buffer(self, gparams):
    self.cash_buffer_target = 0.1 * max(0.0, self.sales)
```

Then call it from a phase (`MyNation.my_extra_step` iterating the sector). This keeps
firm logic on the firm, which is how the rest of the codebase is organised.

---

## Recipe: replace a decision rule

Many behaviours are isolated in a single, well-named method — *demand expectations*,
*investment*, *scrapping*, *pricing*. To change one rule without touching the rest,
subclass the agent and override that method.

Example — make firms expect a 5 % demand increase instead of last year's demand:

```python
from dsk.agents.consumption_good_firm import ConsumptionGoodFirm

class OptimisticFirm(ConsumptionGoodFirm):
    def form_demand_expectation(self, t: int) -> None:
        super().form_demand_expectation(t)       # sets self.expected_demand
        self.expected_demand *= 1.05             # then tilt it
```

Good methods to target on the **sector-2 firm** (`consumption_good_firm.py`):

| Method | The rule it encodes |
|--------|---------------------|
| `form_demand_expectation` | how a firm forecasts demand |
| `compute_desired_production_and_eid` | desired output and expansion investment |
| `plan_substitution_investment` | which machines to scrap and replace |
| `plan_investment_order` | applying credit limits and sizing the machine order |
| `realise_profit` | sales, profit, debt service, inventories |
| `receive_machines` | pricing/markup update when new machines arrive |

To make the model *use* your subclass, construct firms of that class when building the
nation (the firm-creation loop lives in `Nation.initialise_from_parameters` and in the
test/reference builders). For a one-off study, the cleanest approach is a small custom
builder that adds `OptimisticFirm`s instead of `ConsumptionGoodFirm`s.

!!! note "Why overriding beats editing in place"
    Subclassing leaves the verified baseline untouched, so you can A/B your variant
    against it and the fidelity tests still describe the original. Edit the base class
    directly only when you mean to change the model *for everyone*.

---

## Recipe: add a new policy instrument

Climate policies are self-contained objects with a tiny interface, registered by name
so they can be switched on from YAML. Adding one is three steps.

**1. Write the instrument.** It needs `is_active(t)` and `apply(nation, t)`:

```python
# dsk/policy/consumption_tax.py
from __future__ import annotations

class ConsumptionTax:
    """A flat tax on household consumption, active from a given year."""

    def __init__(self, rate: float = 0.05, start_year: int = 80):
        self.rate = rate
        self.start_year = start_year

    def is_active(self, t: int) -> bool:
        return t >= self.start_year

    def apply(self, nation, t: int) -> None:
        # runs during production_phase step 1 (set_climate_policy → climate_policy.apply)
        nation.consumption_budget_nominal *= (1.0 - self.rate)
```

The contract is exactly what the existing instruments implement (see
`dsk/policy/carbon_tax.py` for a fully worked example, including constructor
parameters that map to YAML keys, and how revenue is routed to the government).

**2. Register it** so YAML can name it. Add one line to the registry in
`dsk/policy/climate_policy.py`:

```python
from dsk.policy.consumption_tax import ConsumptionTax

_INSTRUMENT_REGISTRY = {
    # … existing entries …
    "ConsumptionTax": ConsumptionTax,
}
```

**3. Switch it on** in a simulation file — the keys under `type` become constructor
arguments:

```yaml
nations:
  - id: global
    config: ../nations/baseline.yaml
    policy:
      - type: ConsumptionTax
        rate: 0.05
        start_year: 80
```

That's it. `ClimatePolicy.apply(t)` (called first thing each year in
`set_climate_policy`) will activate your instrument whenever `is_active(t)` is true.

!!! info "Where in the year does a policy act?"
    Instruments run at **production_phase step 1**, before firms plan or borrow, so a
    policy can set rates/limits the rest of the year reacts to. If you need an effect
    later in the year (e.g. on realised profits), have the instrument set a flag/rate
    on the nation and read it in the relevant phase method.

---

## Recipe: add a new output variable

Outputs are written once a year in `Nation.save_outputs` (closeout step 2) by calling
`self.sink.record(...)`. To record a new number, add a keyword to that call:

```python
# in dsk/nation.py, Nation.save_outputs, inside self.sink.record("macro", …):
self.sink.record(
    "macro",
    mc_run=self._mc_run,
    t=t,
    nation_id=self.nation_id,
    gdp_real=gdp_real,
    # … existing columns …
    mean_firm_debt=sum(f.debt for f in self.consumption_good_sector) / max(1, len(self.consumption_good_sector)),
)
```

The new column appears automatically in `macro.parquet`. The output sink takes
**arbitrary keyword fields** — no schema to update.

To record a **whole new table** (e.g. a per-firm panel), call `record` with a
different `table_name`; it becomes its own parquet file on `flush`:

```python
for j, firm in enumerate(self.consumption_good_sector):
    self.sink.record(
        "firms",                         # → firms.parquet
        mc_run=self._mc_run, t=t, nation_id=self.nation_id,
        firm_id=j, production=firm.production, price=firm.price,
    )
```

If you'd rather not edit the core, you can also build any panel you like from a
**Tier-1 loop** (above), reading agent state after each `sim.step()` and assembling a
DataFrame yourself — no model edit at all.

See the [Output reference](output-reference.md) for the existing columns.

---

## Recipe: add a new agent type or sector

This is the largest change. The pattern that the existing agents follow:

1. **Create the agent class** in `dsk/agents/` (or a sector collection in
   `dsk/sectors/`). Subclass `Agent` for a single entity; subclass `AgentSet` for a
   collection with aggregate helpers (see `banking_sector.py` for a model to copy).
2. **Give it state in `__init__`** with descriptive names, and an
   `initialise_from_parameters(...)` method that sets starting values.
3. **Hold it on the `Nation`.** Add `self.my_sector = MySector()` in `Nation.__init__`
   and initialise it in `Nation.initialise_from_parameters`.
4. **Wire its behaviour into the phases.** Decide which phase each action belongs to
   and call it from `production_phase` / `dynamics_phase` / `closeout_phase` (in
   practice, via a Tier-2 subclass while you prototype, then folded into `Nation`
   once it's stable).
5. **Roll its state forward** in `update_state_for_next_period` if it has
   "previous-year" memory.
6. **Record its outputs** in `save_outputs`.

Because every existing agent already follows this shape, the closest template to what
you're building is usually the best thing to copy. For a collection of identical
agents, copy `banking_sector.py`; for a singleton, copy `government.py`.

---

## Where each kind of change goes — quick index

| You want to change… | Go to |
|---------------------|-------|
| Something **every year** (observe/shock) | Tier-1 custom loop |
| Something at a **specific point in the year** | Tier-2 `Nation` subclass |
| How a **firm decides** (expectations, investment, pricing, scrapping) | override the method on the firm class |
| **Taxes / budget / bonds** | `realise_profits_and_taxes`, `government.compute_budget` |
| **Interest-rate rule** | `central_bank.apply_taylor_rule` / `set_policy_rate` |
| **Credit / lending** | `allocate_credit_to_demand`, `bank.py` |
| **Energy dispatch / plants** | `electricity_producer.py`, `run_electricity_market` |
| **A new policy lever** | new instrument + registry (recipe above) |
| **A recorded number** | `save_outputs` (recipe above) |
| **A parameter's value** | the YAML — no code (see [Configuration](configuration.md)) |
| **A whole new agent/sector** | new class + wire into `Nation` (recipe above) |

---

**Next:** [Output reference](output-reference.md) — what every recorded column means.
