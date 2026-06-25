# Configuration

Everything about a run — economy size, behaviour, taxes, randomness, which policies
are active — is set in **YAML files**. You never have to edit Python to change a
parameter or build a scenario.

## The three layers

A run is described by a **simulation** file that points at a **global** file and one
or more **nation** files:

```
configs/
  simulations/
    one_nation_baseline.yaml   ← the entry point you pass to --simulation
  global/
    default.yaml               ← economy-wide settings and behavioural constants
  nations/
    baseline.yaml              ← per-nation settings (taxes, banks, wage rules…)
```

| Layer | Holds | Python object |
|-------|-------|---------------|
| **Simulation** | seed, which global/nation files to use, policies, trade, climate | wires up a `Simulation` |
| **Global** | size of the economy, R&D and innovation constants, credit rules, climate timing — things shared by all nations | `GlobalParameters` |
| **Nation** | taxes, number of banks, interest rate, wage rules — things a single country sets | `NationParameters` |

This split mirrors the model: global constants are common to everyone; fiscal and
monetary choices are national.

## The simulation file

```yaml
# configs/simulations/one_nation_baseline.yaml
master_seed: 42                    # reproducible randomness (see Fidelity & randomness)

global: ../global/default.yaml     # path is relative to THIS file

nations:
  - id: global                     # nation id (also tags every output row)
    config: ../nations/baseline.yaml
    policy: []                     # no climate policy in the baseline

trade:
  enabled: false                   # multi-nation trade (off in the one-nation runs)

climate:
  shared: true                     # all nations share one climate system
```

Fields:

- **`master_seed`** — integer seed for the random-number generator. Same seed →
  same run. You can also set `rng_mode: deterministic` here to switch off all
  randomness (see [Fidelity & randomness](fidelity-and-rng.md)).
- **`global`** — path to the global parameter file (relative to the simulation file).
- **`nations`** — a list. Each entry has an `id`, a `config` (nation YAML), and a
  `policy` list. The one-nation runs have a single nation with `id: global`.
- **`policy`** — a list of climate-policy instruments to switch on for that nation.
  Empty in the baseline; see [Adding policies](#adding-climate-policies) below.
- **`trade` / `climate`** — seams for multi-nation runs. In the shipped one-nation
  experiments, trade is off and climate is shared.

!!! info "Unknown keys are ignored, missing keys use defaults"
    The loader only reads keys that match a field on `GlobalParameters` /
    `NationParameters`. A typo or an extra key is silently skipped, and anything you
    don't specify falls back to the dataclass default. This makes the YAML files
    short — they only override what differs from the defaults.

## The parameter files

The global and nation YAMLs are flat lists of `name: value`. The **names are the
descriptive Python attribute names** — not the cryptic C++ symbols. For example:

```yaml
# configs/nations/baseline.yaml (excerpt)
n_banks: 10
unemployment_benefit_share: 0.7
tax_rate_firms_wages: 0.1
policy_rate: 0.02
taylor_rule_inflation_coef: 1.1
credit_multiplier: 0.16
s2_markup_init: 0.15
```

The full set of valid names is whatever appears on the two dataclasses:

- `dsk/parameters/global_parameters.py` — `GlobalParameters`
- `dsk/parameters/nation_parameters.py` — `NationParameters`

Both are organised into commented sections (`§1 Simulation Dimensions`, `§3 KS-Core
Behavioural Parameters`, `§4 Credit-Market Parameters`, …) so you can browse them
like a catalogue. Each field carries an inline comment with its meaning and its C++
name, if you ever need to cross-reference.

### The knobs you'll reach for most

These are the parameters most runs change. (Many more exist; this is the orientation
set, not the full list.)

**Size & length** — `GlobalParameters`:

| Name | Default | Meaning |
|------|---------|---------|
| `n1_capital_good_firms` | 100 | number of sector-1 (machine-building) firms |
| `n2_consumption_good_firms` | 400 | number of sector-2 (consumption-good) firms |
| `total_steps` | 220 | simulated years per run |
| `mc_runs` | 5 | Monte-Carlo replicates (used by ensemble harnesses) |
| `climate_start_step` | 80 | year the climate box starts feeding back |

**Fiscal & monetary** — `NationParameters`:

| Name | Default* | Meaning |
|------|----------|---------|
| `n_banks` | 10 | number of banks |
| `policy_rate` | 0.02 | central-bank base interest rate |
| `tax_rate_firms_wages` | 0.1 | tax rate on firm profits |
| `tax_rate_banks` | 0.1 | tax rate on bank profits |
| `unemployment_benefit_share` | 0.7 | unemployment benefit as a share of the wage |
| `taylor_rule_inflation_coef` | 1.1 | how hard the central bank leans on inflation |
| `credit_multiplier` | 0.16 | Basel-style cap linking bank equity to lending |

<small>*The "default" shown is the **baseline** value from
`configs/nations/baseline.yaml`, which is what the paper uses. The dataclass
fallback can differ — see the note in that file about C++ runtime overrides.</small>

**Behaviour** — `GlobalParameters` (a few examples):

| Name | Default | Meaning |
|------|---------|---------|
| `rd_budget_fraction` | 0.04 | share of sales firms spend on R&D |
| `inventory_target_fraction` | 0.1 | desired inventory as a share of expected demand |
| `capacity_utilization` | 0.75 | target utilisation that drives expansion investment |
| `machine_max_age` | 19 | age (years) at which machines are scrapped |
| `payback_threshold` | 200 | payback period below which firms replace machines |

## Building a new scenario

The fastest way is to copy an existing simulation file and change what you need:

```bash
cp configs/simulations/one_nation_baseline.yaml \
   configs/simulations/my_experiment.yaml
```

Then, for example, to run a **smaller, shorter** economy with a different seed,
override those keys. You have two clean options:

=== "Edit the parameter file"

    Make a new global file and point at it:

    ```yaml
    # configs/global/small.yaml   (copy of default.yaml with three edits)
    n1_capital_good_firms: 25
    n2_consumption_good_firms: 100
    total_steps: 120
    # … the rest as in default.yaml
    ```

    ```yaml
    # my_experiment.yaml
    master_seed: 7
    global: ../global/small.yaml
    nations:
      - id: global
        config: ../nations/baseline.yaml
        policy: []
    ```

=== "Override in Python"

    Load, tweak, run — no extra files:

    ```python
    from dsk.io.config import load_simulation
    sim = load_simulation("configs/simulations/one_nation_baseline.yaml")
    gp = sim.global_params
    gp.n1_capital_good_firms = 25
    gp.n2_consumption_good_firms = 100
    gp.total_steps = 120
    sim.run(gp.total_steps)
    sim.flush("out_small/")
    ```

    Handy for sweeps: loop over values of a parameter, run, and collect results.

## Adding climate policies

Policies are switched on in the **simulation** file, under a nation's `policy:` list.
Each entry names an instrument `type` and its settings:

```yaml
nations:
  - id: global
    config: ../nations/baseline.yaml
    policy:
      - type: CarbonTax
        schedule: constant          # or "exponential"
        base_rate: 0.6e-4
        revenue_use: [1.0, 0.0, 0.0, 0.0]   # all revenue to the government
      - type: GreenConstructionSubsidy
        y_subs: 0.333
      - type: BrownConstructionBan
        invest_ban_offset: 21
```

The built-in instrument types are:

| `type:` | Effect |
|---------|--------|
| `CarbonTax` | taxes emissions; constant or exponential schedule; routes revenue |
| `GreenConstructionSubsidy` | subsidises building green power plants |
| `GreenRDSubsidy` | tops up green-energy R&D |
| `BrownConstructionBan` | bans (and later scraps) fossil power plants |
| `ElectrificationMandate` | requires firms to electrify, with a fine for shortfalls |

The keys under each instrument are passed straight to that instrument's constructor,
so the available settings are exactly its parameters — read the class docstring in
`dsk/policy/<instrument>.py` (e.g. `CarbonTax` documents `schedule`, `base_rate`,
`growth_rate`, `revenue_use`, …).

To write a **brand-new** policy instrument, see
[Extending → new policy](extending.md#recipe-add-a-new-policy-instrument).

---

**Next:** [How the model runs](architecture.md) — the step loop and the agents,
which you need before extending anything.
