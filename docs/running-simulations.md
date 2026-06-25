# Running simulations

There are two ways to run pydsk: the **command line** (simplest) and the **Python
API** (for ensembles, custom analysis, and extension). Both load the same YAML
configuration.

## The command line

```bash
python -m dsk.cli run --simulation <SIM_YAML> --output <DIR>
```

| Argument | Meaning |
|----------|---------|
| `--simulation` | Path to a simulation YAML (see [Configuration](configuration.md)). |
| `--output` | Directory to write parquet results into (created if missing). |

The number of steps is taken from the config (`total_steps`, default 220). The
command writes one parquet file per output table — currently just `macro.parquet`.

Because the package declares a console entry point, you can also run it as:

```bash
dsk run --simulation configs/simulations/one_nation_baseline.yaml --output out/
```

(both forms are identical).

## The Python API

The command line is a thin wrapper over three calls. Use them directly when you want
to drive runs from a script or notebook:

```python
from dsk.io.config import load_simulation

sim = load_simulation("configs/simulations/one_nation_baseline.yaml")
sim.run(sim.global_params.total_steps)   # run all the steps
written = sim.flush("out/")              # write parquet, returns {table: Path}
```

`load_simulation()` does everything: reads the YAML, builds the parameter objects,
constructs the nation(s), wires up the random-number generators and the output sink,
and attaches any climate policies. You get back a ready-to-run
[`Simulation`](architecture.md#the-simulation-object).

Useful handles on the returned object:

```python
sim.global_params      # GlobalParameters dataclass (economy-wide settings)
sim.nations            # list[Nation] — usually length 1
sim.nations[0]         # the nation: agents, sectors, government, etc.
sim.t                  # steps completed so far
sim.step()             # advance exactly one year
sim.run(n)             # advance n years
sim.flush(dir)         # write and clear the output buffer
```

!!! tip "Step-by-step control"
    `sim.run(n)` is just `for _ in range(n): sim.step()`. If you want to *do
    something each year* — read a variable, inject a shock, log extra data — write
    your own loop around `sim.step()`. That is the gentlest extension point and it
    is covered in [Extending the model](extending.md#tier-1-a-custom-run-loop).

## Choosing a scenario

A "scenario" is just a simulation YAML. The shipped ones in
`configs/simulations/` mirror the experiments in the paper:

| File | What it is |
|------|------------|
| `one_nation_baseline.yaml` | No climate policy. The reference run. |
| `one_nation_Tc.yaml` | Constant ("critical") carbon tax, revenue to government. |
| `one_nation_T2.yaml`, `…_T2h`, `…_T2i` | Carbon-tax variants (different revenue uses). |
| `one_nation_BE.yaml`, `…_BCER`, `…_BCERT` | Subsidy / ban / combined packages. |
| `one_nation_TD2.yaml`, `…_TDh` | Exponentially growing carbon tax. |

To make your own, copy one and edit it — see
[Configuration](configuration.md#building-a-new-scenario).

## Monte-Carlo ensembles

A single run is one random draw. To average over randomness, run the **same**
scenario with several seeds and tag each run. The pattern (used by the reference
scripts in `tests/reference/one_nation/`) is:

```python
import pandas as pd
from dsk.io.config import load_simulation
from dsk.io.output_sink import OutputSink
from dsk.rng import make_master_rng, spawn_nation_rng

def run_one(seed: int, t_max: int) -> pd.DataFrame:
    sim = load_simulation("configs/simulations/one_nation_baseline.yaml")

    # Re-seed every nation from this run's master seed, and tag the run.
    master = make_master_rng(seed)
    for nation in sim.nations:
        nation.rng = spawn_nation_rng(master, nation.nation_id)
        nation._mc_run = seed          # fills the `mc_run` column in the output

    sim.run(t_max)
    return pd.DataFrame(sim.output_sink._rows["macro"])

frames = [run_one(seed, t_max=220) for seed in range(10)]
ensemble = pd.concat(frames, ignore_index=True)

# Mean GDP path across the 10 replicates:
mean_path = ensemble.groupby("t")["gdp_real"].mean()
```

Key points:

- **`nation._mc_run`** is written verbatim into the `mc_run` column of every output
  row, so you can group by it afterwards. Set it to the seed (or any run id).
- Each replicate gets an independent random stream from `spawn_nation_rng`, which is
  reproducible: the same seed always gives the same run.
- `sim.output_sink._rows["macro"]` is the in-memory list of result rows. You can read
  it directly (as above) or `sim.flush(dir)` it to parquet.

!!! note "Why not just change `master_seed` in the YAML?"
    You can — `master_seed` in the simulation YAML sets the default. But for an
    ensemble it is cleaner to load once and re-seed in a loop, so every replicate
    uses an identical configuration and only the random stream differs.

## Reading and analysing output

Results are **parquet** files: a fast, typed, columnar format that pandas reads
natively.

```python
import pandas as pd
df = pd.read_parquet("out/macro.parquet")
```

The table always carries three context columns — `mc_run`, `t`, `nation_id` — plus
the economic aggregates. Common moves:

```python
# one scenario, plot a series
df.plot(x="t", y="emissions_total")

# compare two scenarios
base = pd.read_parquet("out/macro.parquet").assign(scenario="baseline")
tax  = pd.read_parquet("out_Tc/macro.parquet").assign(scenario="carbon_tax")
both = pd.concat([base, tax])
both.pivot_table(index="t", columns="scenario", values="emissions_total").plot()

# ensemble: mean ± band
g = ensemble.groupby("t")["gdp_real"]
ax = g.mean().plot(label="mean")
ax.fill_between(g.mean().index, g.quantile(.1), g.quantile(.9), alpha=.2)
```

Every column is listed in the [Output reference](output-reference.md). To **add**
your own column or table, see
[Extending → new outputs](extending.md#recipe-add-a-new-output-variable).

---

**Next:** [Configuration](configuration.md) — what the YAML controls and the knobs
that matter most.
