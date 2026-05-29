from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from dsk.climate.climate_system import ClimateSystem
from dsk.nation import Nation
from dsk.parameters.global_parameters import GlobalParameters
from dsk.rng import (
    DeterministicGenerator,
    make_deterministic_rng,
    make_master_rng,
    spawn_nation_rng,
)
from dsk.trade.trade_network import TradeNetwork

if TYPE_CHECKING:
    from dsk.io.output_sink import OutputSink


class Simulation:
    """Top-level orchestrator.

    Owns the list of nations, the shared climate, and the trade network.
    Drives one period at a time through the production / trade / dynamics /
    climate / closeout phase structure defined in PORT_PLAN_v3 §4.

    Parameters
    ----------
    global_params : GlobalParameters
    nations : list[Nation]
        Pre-constructed Nation objects.  RNGs are assigned here.
    rng_seed : int
        Master seed for reproducible runs.
    """

    def __init__(
        self,
        global_params: GlobalParameters,
        nations: list[Nation],
        rng_seed: int = 0,
        rng_mode: str = "stochastic",
    ) -> None:
        if rng_mode not in {"stochastic", "deterministic"}:
            raise ValueError(
                f"rng_mode must be 'stochastic' or 'deterministic', got {rng_mode!r}"
            )

        self.global_params: GlobalParameters = global_params
        self.nations: list[Nation] = list(nations)
        self.t: int = 0
        self.rng_mode: str = rng_mode

        # Shared singletons
        self.climate: ClimateSystem = ClimateSystem(global_params)
        self.trade_network: TradeNetwork = TradeNetwork()

        # Assign per-nation RNGs and global params reference.  In
        # deterministic mode every nation gets its OWN
        # DeterministicGenerator so per-nation call counters do not
        # interfere with each other; the master seed is ignored.
        if rng_mode == "deterministic":
            for nation in self.nations:
                nation.rng = make_deterministic_rng()
                nation.gparams = global_params
        else:
            master = make_master_rng(rng_seed)
            for nation in self.nations:
                nation.rng = spawn_nation_rng(master, nation.nation_id)
                nation.gparams = global_params

        # Output sink — set to None here; wired in by load_simulation()
        self.output_sink: Optional["OutputSink"] = None

        # Emission buffer for the freqclim-period rolling window (C++ Emiss_TOT[1..freqclim]).
        # Stored as a list when freqclim>1; scalar shortcut when freqclim==1.  Each step,
        # step() refreshes the buffer to the sum of the last freqclim periods' emissions.
        self._emission_buffer: float = 0.0
        self._emission_window: list = []

        # Seed each nation's climate handle with the init state so save_outputs can read
        # Cat/Tmixed before the first CLIMATEBOX fire (t <= climate_start_step).  Matches the
        # C++ ymc baseline behaviour: pre-fire periods carry the 2020 init values verbatim.
        for nation in self.nations:
            nation.receive_climate_state(self.climate)

    # ------------------------------------------------------------------
    # Core loop
    # ------------------------------------------------------------------

    def step(self) -> None:
        """Advance the model by one period.

        ``self.t`` (the simulation's own counter) is 0-indexed for Python
        ergonomics: a fresh Simulation has ``self.t == 0``; after N calls
        to ``step`` it equals N.  Tests assert this property.

        Internally we pass ``self.t + 1`` to every nation method so that
        the per-period flow uses the **C++ 1-indexed period semantic**
        every Python docstring references (e.g. compute_desired_production
        _and_eid's `if t == 1: Kd = Qd` first-period special case, or
        government.collect_taxes' `if t == 1` init block).  Without this
        shift the very first economic period passes `t=0` and silently
        falls through to the generic branch — see
        planningDocs/M1_DEBUG_PLAN.md and the build-log entry for the
        deterministic-mode bug hunt that surfaced this.
        """
        t = self.t + 1  # 1-indexed period number, matches C++ convention

        # PRODUCTION PHASE — each nation independently
        for nation in self.nations:
            nation.production_phase(t)

        # SEAM 1 — TRADE (no-op until milestone 7)
        if self.trade_network.is_enabled(t):
            offers = [n.expose_trade_offer() for n in self.nations]
            assignments = self.trade_network.match(offers)
            for nation, assignment in zip(self.nations, assignments):
                nation.accept_trade_assignment(assignment)

        # DYNAMICS PHASE — each nation independently
        for nation in self.nations:
            nation.dynamics_phase(t)

        # SEAM 2 — CLIMATE
        # Mirror C++ CLIMATEBOX block (dsk_main.cpp:354-365):
        #   flag_clim_tech==1 && t > t_start_climbox && t % freqclim == 0
        # Emit buffering mirrors the Emiss_TOT rolling-window logic in module_climate.cpp:38-43:
        #   Emiss_yearly(1) = sum_{tt=1..freqclim} Emiss_TOT(tt)
        # i.e. the sum of the most recent freqclim periods' emissions, NOT a
        # cumulative total since simulation start.  When climate_start_step > 0
        # the box does not fire during spin-up but the same rolling window applies
        # at first fire — the gauge is calibrated against a single freqclim
        # window, not against the whole spin-up history.
        gp = self.global_params
        freqclim: int = int(gp.climate_call_frequency)
        total_emissions = sum(n.report_emissions() for n in self.nations)
        # Maintain a rolling window of length freqclim.  The buffer always
        # equals the sum of the last freqclim periods' emissions (or fewer
        # in the very first freqclim-1 periods when the window is still filling).
        if freqclim == 1:
            self._emission_buffer = total_emissions
        else:
            self._emission_window.append(total_emissions)
            if len(self._emission_window) > freqclim:
                self._emission_window.pop(0)
            self._emission_buffer = float(sum(self._emission_window))
        if (
            gp.enable_climate_tech == 1
            and t > gp.climate_start_step
            and t % freqclim == 0
        ):
            calib = self.climate.calibrate_emissions(self._emission_buffer)
            self.climate.step(calib)
            for nation in self.nations:
                nation.receive_climate_state(self.climate)

        # CLOSEOUT PHASE — each nation independently
        for nation in self.nations:
            nation.closeout_phase(t)

        self.t += 1

    def run(self, total_steps: int) -> None:
        """Run the simulation for `total_steps` periods."""
        for _ in range(total_steps):
            self.step()

    def flush(self, output_dir: "str | Path") -> dict:
        """Flush the output sink to *output_dir*; returns table_name → Path mapping."""
        if self.output_sink is None:
            return {}
        return self.output_sink.flush(output_dir)
