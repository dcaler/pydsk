from __future__ import annotations

from dsk.agent_set import AgentSet


class CapitalGoodSector(AgentSet):
    """Collection of CapitalGoodFirm agents with sector-level helpers.

    Sector-mean aggregates (p1m, c1m, A1m) are computed and stored here
    by Nation.deliver_machines() each period.
    Top-incumbent productivities (A1top, A1ptop) are recomputed by
    Nation.advance_technology() after TECHANGEND each period.
    """

    def __init__(self) -> None:
        super().__init__()
        # C++ p1m, c1m, A1m — sector means updated in MACH
        self.mean_price: float = 0.0           # p1m = mean(p1(2,i)) over N1 firms
        self.mean_unit_cost: float = 0.0       # c1m = mean(c1(i))
        self.mean_machine_labour_prod: float = 0.0  # A1m = mean(A1(i))
        # A1top(1), A1ptop(1) — best machine/process labour productivity among incumbents.
        # Read by TECHANGEND's norm-based imitation distance; written at the end of
        # each TECHANGEND. Initial value matches productivity_init (all firms = A0).
        self.A1_top: float = 1.0
        self.A1p_top: float = 1.0
        # Energy-axis frontier tops, used by next period's energy-aware imitation
        # Td norm (TECHANGEND 7796-7823). For energy need / env filth a LOWER value
        # is better, so the "top" is the MIN; for electrification, the MAX.
        # Initialised on first update_frontier(); seeded here at the A0 values.
        self.A1_en_top: float = 0.0
        self.A1p_en_top: float = 0.0
        self.A1_ef_top: float = 0.0
        self.A1p_ef_top: float = 0.0
        self.A1p_el_top: float = 0.0

    def update_sector_means(self) -> None:
        """Recompute p1m, c1m, A1m from current firm state.

        Called by Nation.deliver_machines() after per-firm price/cost update.
        C++ MACH(): p1m/=N1; c1m/=N1; A1m=A1.Sum()/N1r
        """
        agents = list(self)
        n = len(agents)
        if n == 0:
            return
        self.mean_price = sum(f.price_prev for f in agents) / n
        self.mean_unit_cost = sum(f.unit_cost for f in agents) / n
        self.mean_machine_labour_prod = sum(f.machine_labour_prod for f in agents) / n

    def update_frontier(self) -> None:
        """Recompute A1top, A1ptop over current firms.

        C++ TECHANGEND lines 7773-7800: A1top initialised from firm 1, then maxed
        across all firms. Used by next period's imitation Td norm.
        """
        agents = list(self)
        if not agents:
            return
        self.A1_top = agents[0].machine_labour_prod
        self.A1p_top = agents[0].process_labour_prod
        # Energy axes (C++ 7798-7822): EN/EF tops are MIN (lower is better),
        # electrification top is MAX. Seed from firm 0 then reduce/raise.
        self.A1_en_top = agents[0].current_technology.energy_efficiency
        self.A1p_en_top = agents[0].process_energy_need
        self.A1_ef_top = agents[0].current_technology.env_cleanliness
        self.A1p_ef_top = agents[0].process_env_filthiness
        self.A1p_el_top = agents[0].current_technology.electrification_fraction
        for f in agents:
            if f.machine_labour_prod > self.A1_top:
                self.A1_top = f.machine_labour_prod
            if f.process_labour_prod > self.A1p_top:
                self.A1p_top = f.process_labour_prod
            if f.current_technology.energy_efficiency < self.A1_en_top:
                self.A1_en_top = f.current_technology.energy_efficiency
            if f.process_energy_need < self.A1p_en_top:
                self.A1p_en_top = f.process_energy_need
            if f.current_technology.env_cleanliness < self.A1_ef_top:
                self.A1_ef_top = f.current_technology.env_cleanliness
            if f.process_env_filthiness < self.A1p_ef_top:
                self.A1p_ef_top = f.process_env_filthiness
            if f.current_technology.electrification_fraction > self.A1p_el_top:
                self.A1p_el_top = f.current_technology.electrification_fraction
