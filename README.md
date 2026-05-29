# DSK Python Port

An object-oriented Python implementation of the Dosi-Schumpeterian-Keynes (DSK) economic agent-based model, based on the C++ baseline by Wieners (2025).

## Installation

```bash
pip install -e .
```

## Quick Start

```bash
python -m dsk.cli run --simulation configs/simulations/one_nation_baseline.yaml --output out/
```

## Documentation

See `planningDocs/PORT_PLAN_v3.md` for the architecture and build plan.

## Testing

```bash
pytest tests/ -q
```

## Reference

This port reproduces the model of:

> Wieners, C., Lamperti, F., Dosi, G., & Roventini, A. (2026). Policies for rapid
> decarbonization with steady economic transition and employment creation.
> *Nature Sustainability*, **9**(1), 117–129.

The C++ baseline code is © 2025 Claudia Wieners, Francesco Lamperti, Giovanni
Dosi and Andrea Roventini. The third-party paper PDFs are not redistributed in
this repository.
