# Getting started

This page takes you from a clean machine to a finished simulation you can plot.

## 1. Requirements

- **Python 3.10 or newer.** Check with `python --version`.
- That's it. pydsk's runtime dependencies (numpy, scipy, pandas, pyarrow, pyyaml)
  install automatically in the next step.

!!! tip "Not a Python person?"
    A *virtual environment* is just a private sandbox for one project's packages so
    they don't clash with anything else. You create it once and "activate" it each
    session. The commands below do exactly that — copy them as-is.

## 2. Install

From the `code/` directory (the one containing `pyproject.toml`):

```bash
# create and activate a private environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# install pydsk in "editable" mode (so your edits take effect immediately)
pip install -e .
```

Editable mode (`-e`) means the package points at this source tree: if you later
change the code, you do **not** need to reinstall. That is the mode you want while
extending the model.

To also install the test tools or the documentation tools:

```bash
pip install -e ".[dev]"     # pytest etc.
pip install -e ".[docs]"    # mkdocs + theme, to build this manual locally
```

## 3. Run your first simulation

```bash
python -m dsk.cli run \
    --simulation configs/simulations/one_nation_baseline.yaml \
    --output out/
```

You'll see something like:

```
Running 220 steps...
Flushing outputs to out/...
✓ Wrote 1 parquet file(s)
  - macro.parquet (… bytes)
```

That ran the **baseline** scenario for 220 years and wrote a single results file,
`out/macro.parquet`.

!!! note "How long does it take?"
    The baseline (100 capital-good firms, 400 consumption-good firms, 220 steps)
    runs in well under a minute on a laptop. Bigger economies and Monte-Carlo
    ensembles take longer — see [Running simulations](running-simulations.md).

## 4. Look at the results

`macro.parquet` is a table with one row per year. Open it with pandas:

```python
import pandas as pd

df = pd.read_parquet("out/macro.parquet")
print(df.columns.tolist())          # ~45 aggregate columns
print(df[["t", "gdp_real", "unemployment_rate", "emissions_total"]].head())
```

Plot a time series:

```python
import matplotlib.pyplot as plt

df.plot(x="t", y="unemployment_rate")
plt.show()
```

Every column is documented in the [Output reference](output-reference.md).

## 5. Run a policy scenario

The baseline has no climate policy. To run, say, a constant carbon tax, just point
at a different simulation file:

```bash
python -m dsk.cli run \
    --simulation configs/simulations/one_nation_Tc.yaml \
    --output out_Tc/
```

The shipped `configs/simulations/` folder contains the scenarios from the paper
(carbon-tax variants, subsidies, mandates, bans). [Running
simulations](running-simulations.md) explains how to compare them, and
[Configuration](configuration.md) explains how to build your own.

## 6. (Optional) Confirm your install is correct

pydsk ships with a deterministic regression check: in *deterministic mode* the model
produces **bit-identical** output every run, and the repository stores a "golden"
copy of that output. Reproduce it and compare:

```bash
python -m pytest tests/ -q          # full test suite
```

A green suite means your environment reproduces the reference model exactly. See
[Fidelity & randomness](fidelity-and-rng.md) for what this guarantees.

---

**Next:** [Running simulations](running-simulations.md) — the command line, the
Python API, ensembles, and analysis.
