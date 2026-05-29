from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Technology:
    """Immutable value object representing the technology embodied in one machine type.

    One instance per CapitalGoodFirm per period (the technology currently on offer)
    plus short-lived candidate instances generated during innovation and imitation.

    C++ analogues (dsk_globalvar.h, N1-indexed RowVectors):
      labour_productivity      → A1[i]
      energy_efficiency        → A1_en[i]  (energy efficiency of machine in sector-2 use)
      env_cleanliness          → A1_ef[i]  (C++ calls this "env filth"; convention: higher = cleaner here)
      electrification_fraction → A1p_el[i] (fraction of sector-1 production process that is electrified)
    """

    labour_productivity: float = 1.0
    energy_efficiency: float = 1.0
    env_cleanliness: float = 1.0
    electrification_fraction: float = 0.0
