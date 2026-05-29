from __future__ import annotations

import numpy as np

from dsk.agents.technology import Technology


class MachineStock:
    """Numpy-backed vintage × supplier capital stock for a ConsumptionGoodFirm.

    All arrays are indexed [vintage_row, supplier_idx] where vintage_row is a compact
    index assigned in order of first appearance (not the absolute period number).
    Use `vintage_keys`, `row_for`, and `count_at` to bridge between period numbers and
    internal row indices.

    Mirrors the C++ g[T][N1][N2] tensor sliced for a fixed consumer firm j:
      count                    ← g[tt-1][i-1][j-1]
      labour_productivity      ← A(tt, i) at delivery time
      energy_efficiency        ← A_en(tt, i) at delivery time
      env_cleanliness          ← A_ef(tt, i) at delivery time
      electrification_fraction ← A_el(tt, i) at delivery time
      age                      ← age[tt-1][i-1][j-1]

    The C++ T dimension was a worst-case bound. Here, rows are added only as new
    vintages appear (one row per period in which machines are first received).
    """

    def __init__(self, n_suppliers: int) -> None:
        self._n_suppliers = n_suppliers
        self._vintage_keys: list[int] = []
        self._vintage_to_row: dict[int, int] = {}

        shape = (0, n_suppliers)
        self.count = np.zeros(shape, dtype=float)
        self.labour_productivity = np.zeros(shape, dtype=float)
        self.energy_efficiency = np.zeros(shape, dtype=float)
        self.env_cleanliness = np.zeros(shape, dtype=float)
        self.electrification_fraction = np.zeros(shape, dtype=float)
        self.age = np.zeros(shape, dtype=float)

    # ------------------------------------------------------------------
    # Vintage management
    # ------------------------------------------------------------------

    def _ensure_vintage(self, vintage_key: int) -> int:
        """Return the row index for vintage_key, appending a zero row if absent."""
        if vintage_key in self._vintage_to_row:
            return self._vintage_to_row[vintage_key]
        row = len(self._vintage_keys)
        self._vintage_keys.append(vintage_key)
        self._vintage_to_row[vintage_key] = row
        zero_row = np.zeros((1, self._n_suppliers), dtype=float)
        self.count = np.vstack([self.count, zero_row])
        self.labour_productivity = np.vstack([self.labour_productivity, zero_row])
        self.energy_efficiency = np.vstack([self.energy_efficiency, zero_row])
        self.env_cleanliness = np.vstack([self.env_cleanliness, zero_row])
        self.electrification_fraction = np.vstack([self.electrification_fraction, zero_row])
        self.age = np.vstack([self.age, zero_row])
        return row

    @property
    def vintage_keys(self) -> list[int]:
        """Period keys present in this stock, in order of first insertion."""
        return list(self._vintage_keys)

    def row_for(self, vintage_key: int) -> int | None:
        """Internal row index for vintage_key, or None if this vintage is absent."""
        return self._vintage_to_row.get(vintage_key)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_machines(
        self,
        vintage_key: int,
        supplier_idx: int,
        count: float,
        technology: Technology,
        age: float = 0.0,
    ) -> None:
        """Accumulate `count` machines into slot (vintage_key, supplier_idx).

        Technology properties are written (overwriting any prior value for the slot —
        safe since the same supplier delivers the same technology within one period).
        Age overwrites the slot's current age, matching the C++ initialisation pattern
        where age[tt-1][i-1][j-1] is reassigned on each g[...] increment.

        C++: g[0][i-1][j-1]++;  age[0][i-1][j-1] = age0;  (INITIALIZE loop)
        """
        row = self._ensure_vintage(vintage_key)
        self.count[row, supplier_idx] += count
        self.labour_productivity[row, supplier_idx] = technology.labour_productivity
        self.energy_efficiency[row, supplier_idx] = technology.energy_efficiency
        self.env_cleanliness[row, supplier_idx] = technology.env_cleanliness
        self.electrification_fraction[row, supplier_idx] = technology.electrification_fraction
        self.age[row, supplier_idx] = age

    def remove_machines(self, vintage_key: int, supplier_idx: int) -> None:
        """Zero out count and age for slot (vintage_key, supplier_idx).

        Used for scrapping: g[tt-1][i-1][j-1] = 0;  age[tt-1][i-1][j-1] = 0;
        """
        if vintage_key in self._vintage_to_row:
            row = self._vintage_to_row[vintage_key]
            self.count[row, supplier_idx] = 0.0
            self.age[row, supplier_idx] = 0.0

    # ------------------------------------------------------------------
    # Aggregates
    # ------------------------------------------------------------------

    def count_at(self, vintage_key: int, supplier_idx: int) -> float:
        """Machine count for a specific (vintage, supplier) pair."""
        if vintage_key not in self._vintage_to_row:
            return 0.0
        return float(self.count[self._vintage_to_row[vintage_key], supplier_idx])

    def total_machines(self) -> float:
        """Total machine count across all vintages and suppliers (= n_mach in C++)."""
        return float(self.count.sum())

    def effective_labour_productivity(self) -> float:
        """Harmonic mean of labour_productivity weighted by machine count.

        C++ formula (dsk_main.cpp ~2453):
          A2(j) += 1/A(tt,i) * g[tt-1][i-1][j-1] / n_mach   [then invert]
          A2(j) = 1 / A2(j)

        Returns 0.0 if no machines are present.
        """
        n_mach = self.total_machines()
        if n_mach <= 0.0:
            return 0.0
        mask = (self.count > 0) & (self.labour_productivity > 0)
        inv_prod = np.zeros_like(self.count)
        np.divide(self.count, self.labour_productivity, where=mask, out=inv_prod)
        weighted_inv = inv_prod.sum() / n_mach
        return 0.0 if weighted_inv <= 0.0 else 1.0 / weighted_inv

    def effective_energy_need(self) -> float:
        """Arithmetic weighted mean of energy_efficiency (= energy need) by machine count.

        C++ A2_en(j): sum_tt_i [A_en(tt,i) * g[...] / n_mach]

        Returns 0.0 if no machines are present.
        """
        n_mach = self.total_machines()
        if n_mach <= 0.0:
            return 0.0
        return float((self.energy_efficiency * self.count).sum() / n_mach)

    def unit_cost_from_wage(
        self,
        wage: float,
        elec_price: float = 0.0,
        carbon_tax_s2: float = 0.0,
    ) -> float:
        """Weighted average unit production cost using the cost_sect2 formula.

        C(tt,i) = wage/A + A_en*c_en + A_ef*t_CO2_I2
        c2(j) = sum_tt_i [C(tt,i) * g[...] / n_mach]

        C++ dsk_main.cpp MACH() DSK17 path (flag_clim_tech==1):
          C(tt,i) = cost_sect2(w, A(tt,i), A_en(tt,i), c_en(2), A_ef(tt,i), t_CO2_I2)
          c2(1,j) += C(tt,i)*g[tt-1][i-1][j-1]/n_mach(j)

        With energy terms zero (default), reduces to the KS15 formula C = wage/A.
        """
        n_mach = self.total_machines()
        if n_mach <= 0.0:
            return 0.0
        mask = (self.count > 0) & (self.labour_productivity > 0)
        cost_times_count = np.zeros_like(self.count)
        # Labour cost component: wage / A * count
        np.divide(wage * self.count, self.labour_productivity, where=mask, out=cost_times_count)
        # Energy cost component: A_en * c_en * count
        if elec_price != 0.0:
            cost_times_count += self.energy_efficiency * self.count * elec_price
        # Process emission cost: A_ef * t_CO2_I2 * count
        if carbon_tax_s2 != 0.0:
            cost_times_count += self.env_cleanliness * self.count * carbon_tax_s2
        return float(cost_times_count.sum() / n_mach)

    def increment_ages(self) -> None:
        """Add 1 to age of every slot with at least one machine.

        C++: age[tt-1][i-1][j-1]++  for all (tt,i) where gtemp[...] > 0  (UPDATE)
        """
        self.age[self.count > 0] += 1.0
