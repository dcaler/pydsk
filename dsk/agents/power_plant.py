from __future__ import annotations

from typing import TYPE_CHECKING

from dsk.agents.agent import Agent

if TYPE_CHECKING:
    from dsk.nation import Nation


class PowerPlant(Agent):
    """One vintage-group of electricity plants built in the same period.

    `count` is the number of physical plant units in this group (C++ G_ge(tt)
    or G_de(tt)).  Each instance represents one vintage entry in the plant fleet.
    """

    def __init__(
        self,
        nation: "Nation",
        vintage: int,
        count: int,
        building_cost: float,
    ) -> None:
        super().__init__(nation)
        self.vintage: int = vintage
        self.count: int = count
        # CF_ge / CF_de — inflation-adjusted each period by ENERGY()
        self.building_cost: float = building_cost

    def unit_cost(self, fuel_price: float, carbon_tax: float) -> float:
        """Variable production cost per unit of energy output."""
        raise NotImplementedError

    def inflation_adjust(self, factor: float) -> None:
        """Scale building_cost by cpi_now / cpi_last (C++ CF_*(tt) *= cpi(1)/cpi(2))."""
        self.building_cost *= factor

    def age(self, current_t: int) -> int:
        """Periods elapsed since this vintage was built."""
        return current_t - self.vintage


class GreenPlant(PowerPlant):
    """Renewable electricity plant — zero fuel cost, zero direct emissions.

    C++ analogues: G_ge(tt), CF_ge(tt), CS_ge(tt), CF_ge_full(tt).
    """

    def __init__(
        self,
        nation: "Nation",
        vintage: int,
        count: int,
        building_cost: float,
        subsidy_received: float = 0.0,
        full_building_cost: float = 0.0,
    ) -> None:
        super().__init__(nation, vintage, count, building_cost)
        self.subsidy_received: float = subsidy_received    # CS_ge(tt)
        self.full_building_cost: float = full_building_cost  # CF_ge_full(tt): actual paid

    def unit_cost(self, fuel_price: float, carbon_tax: float) -> float:
        """Green plants have zero variable production cost."""
        return 0.0

    def inflation_adjust(self, factor: float) -> None:
        super().inflation_adjust(factor)
        self.full_building_cost *= factor


class BrownPlant(PowerPlant):
    """Fossil-fuel electricity plant.

    C++ analogues per vintage tt:
      G_de(tt)    -> count
      A_de(tt)    -> thermal_inefficiency  (fuel per unit energy; lower = more efficient)
      EM_de(tt)   -> emission_intensity    (emissions per unit fuel)
      CF_de(tt)   -> building_cost
      G_de_act(tt)-> active_count          (plants not "replaced" by a green vintage)

    Unit production cost formula (C++ C_de(tt)):
        C_de = pf * A_de + t_CO2_en * EM_de * A_de
             = A_de * (fuel_price + carbon_tax * emission_intensity)
    """

    def __init__(
        self,
        nation: "Nation",
        vintage: int,
        count: int,
        building_cost: float,
        thermal_inefficiency: float,
        emission_intensity: float,
    ) -> None:
        super().__init__(nation, vintage, count, building_cost)
        self.thermal_inefficiency: float = thermal_inefficiency  # A_de(tt)
        self.emission_intensity: float = emission_intensity      # EM_de(tt)
        # Plants not yet "replaced" by green (G_de_act(tt)); starts equal to count.
        self.active_count: int = count

    def unit_cost(self, fuel_price: float, carbon_tax: float) -> float:
        """C++ C_de(tt) = pf * A_de + t_CO2_en * EM_de * A_de."""
        return self.thermal_inefficiency * (fuel_price + carbon_tax * self.emission_intensity)

    def fuel_per_unit_energy(self) -> float:
        """Fuel consumed per unit of electricity output (= A_de)."""
        return self.thermal_inefficiency

    def emissions_per_unit_energy(self) -> float:
        """Emissions per unit of electricity output (= EM_de * A_de)."""
        return self.emission_intensity * self.thermal_inefficiency
