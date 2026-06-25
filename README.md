# pydsk — DSK climate–macro agent-based model (Python)

An object-oriented Python implementation of the **DSK** (*Dystopian Schumpeter
meeting Keynes*) economic agent-based model — a macro model with an explicit energy
sector and climate feedback, used to study decarbonisation policy. It is a faithful
port of the C++ model of Wieners (2026), built to be **far easier to run, read, and
extend** than the original.

## Documentation

📖 **A full user manual lives in [`docs/`](docs/index.md)** — written for researchers
running scenarios *and* for developers extending the model. Start here:

| If you want to… | Read |
|-----------------|------|
| Install and run your first simulation | [Getting started](docs/getting-started.md) |
| Use the CLI / Python API, run ensembles, read results | [Running simulations](docs/running-simulations.md) |
| Understand the YAML config and the parameters | [Configuration](docs/configuration.md) |
| Learn the step loop and where each behaviour lives | [How the model runs](docs/architecture.md) |
| **Change the model** — hooks, policies, outputs, new agents | [Extending the model](docs/extending.md) |
| Look up an output column | [Output reference](docs/output-reference.md) |
| Understand reproducibility & C++ fidelity | [Fidelity & randomness](docs/fidelity-and-rng.md) |

The manual is plain Markdown (renders on GitHub) and also builds into a browsable
site with MkDocs:

```bash
pip install -e ".[docs]"
mkdocs serve          # live preview at http://127.0.0.1:8000
```

## Installation

```bash
pip install -e .
```

Requires Python 3.10+. Runtime dependencies (numpy, scipy, pandas, pyarrow, pyyaml)
install automatically.

## Quick start

```bash
python -m dsk.cli run \
    --simulation configs/simulations/one_nation_baseline.yaml \
    --output out/
```

This runs the 220-year baseline and writes `out/macro.parquet` (one row per year).
Read it with pandas:

```python
import pandas as pd
df = pd.read_parquet("out/macro.parquet")
df.plot(x="t", y="unemployment_rate")
```

Policy scenarios from the paper (carbon taxes, subsidies, bans, mandates) ship in
`configs/simulations/` — just point `--simulation` at a different file. See the
[manual](docs/index.md) for everything else.

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -q
```

A green suite means your build reproduces the reference model exactly (see
[Fidelity & randomness](docs/fidelity-and-rng.md)).

## Reference

This port reproduces the model of:

> Wieners, C., Lamperti, F., Dosi, G., & Roventini, A. (2026). Policies for rapid
> decarbonization with steady economic transition and employment creation.
> *Nature Sustainability*, **9**(1), 117–129.

The C++ baseline code is © 2025 Claudia Wieners, Francesco Lamperti, Giovanni Dosi
and Andrea Roventini. The third-party paper PDFs are not redistributed in this
repository.
