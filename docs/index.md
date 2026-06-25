# pydsk — User Manual

**pydsk** is a Python implementation of the **DSK** (*Dystopian Schumpeter meeting
Keynes*) agent-based model — a macroeconomic model with an explicit energy sector
and climate feedback, used to study decarbonisation policy. It is a faithful port
of the C++ model of Wieners, Lamperti, Dosi & Roventini (2026, *Nature
Sustainability*).

The goal of pydsk is to make that model **easy to run, read, and modify** — the
things the original C++ makes hard. This manual is written for two readers at once:

- **The researcher** who wants to run scenarios, change parameters, and analyse
  results — and who is comfortable running Python but is *not* a software engineer.
- **The extender** who wants to add new behaviour: a new policy, a new decision
  rule, a new output, or a brand-new kind of agent.

Wherever the two diverge, the page says so. You do **not** need to read the C++ to
use pydsk.

---

## What the model does (in one paragraph)

Each simulation step is one **year**. Capital-good firms (sector 1) do R&D and
build machines; consumption-good firms (sector 2) buy those machines, hire labour,
produce goods, and sell them to households; banks lend to firms; a government taxes,
pays unemployment benefits, and issues bonds; a central bank sets the interest rate.
An electricity producer dispatches green and brown power plants to meet the firms'
energy demand, which generates emissions, which feed a climate module, which feeds
damages back onto the economy. Climate **policies** (carbon taxes, green subsidies,
bans, mandates) can be switched on to study transitions.

If you want the economics in depth, read the paper. This manual is about the
**software**.

---

## Pick your path

<div class="grid cards" markdown>

- :material-rocket-launch: **[Getting started](getting-started.md)**
  Install pydsk and run your first simulation in five minutes.

- :material-play-circle: **[Running simulations](running-simulations.md)**
  The command line, the Python API, scenarios, Monte-Carlo ensembles, and reading
  results.

- :material-tune: **[Configuration](configuration.md)**
  How the YAML config works and what every important knob does.

- :material-sitemap: **[How the model runs](architecture.md)**
  The step loop, the phases, the agents, and how data flows between them. **Read
  this before extending anything.**

- :material-puzzle: **[Extending the model](extending.md)**
  The core of pydsk's value. *"If you want an agent to do something every step,
  this is the page."* New behaviours, policies, outputs, and agents.

- :material-table: **[Output reference](output-reference.md)**
  Every column pydsk writes, and what it means.

- :material-check-decagram: **[Fidelity & randomness](fidelity-and-rng.md)**
  Deterministic mode, the golden-output regression check, and how to change the
  model without silently breaking C++ fidelity.

</div>

---

## A 30-second taste

```bash
pip install -e .
python -m dsk.cli run \
    --simulation configs/simulations/one_nation_baseline.yaml \
    --output out/
```

That runs the 220-year baseline and writes `out/macro.parquet` — one row per year,
with GDP, unemployment, emissions, the interest rate, and ~40 other aggregates.
Load it with pandas:

```python
import pandas as pd
df = pd.read_parquet("out/macro.parquet")
df.plot(x="t", y="unemployment_rate")
```

That's the whole loop: **configure → run → read a parquet**. Everything else in this
manual is detail and extension.
