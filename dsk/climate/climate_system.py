"""Global C-ROADS climate box.

Port of the C++ ``CLIMATEBOX`` and ``UPDATECLIMATE`` functions in
``Code/Wieners_2025-main_slim/basecode/modules/module_climate.cpp`` (rewritten
by Claudia Wieners, Oct 2019, after the C-ROADS model of Sterman et al.).

The model carries a small box-model state:

* atmospheric carbon ``Cat`` (GtC)
* a ``ndep``-layer ocean carbon column ``Con`` (GtC per layer)
* a ``ndep``-layer ocean heat column ``Hon`` (J / m² of ocean surface)
* the ocean-layer temperatures ``Ton`` (K above pre-industrial) derived from heat
* biosphere carbon ``biom`` and humus carbon ``humm`` (GtC)
* the surface (mixed-layer) temperature anomaly ``Tmixed`` (K above pre-ind.)

``step(yearly_emissions)`` advances the box one climate time step
(``dt_climate_years``).  The argument is the **calibrated** annual emission flux
in GtC — i.e. C++ ``Emiss_yearly_calib(1)``.  Translating the raw DSK-model
emissions into that calibrated GtC flux (the "FIX THE EMISSIONS" block at the
top of ``CLIMATEBOX``) is a model-coupling concern handled by
:meth:`calibrate_emissions`; the Simulation seam wires it together in Task 4.2.

The C++ uses Newmat vectors indexed ``(1)`` = current period and ``(2)`` =
previous period, with a separate ``UPDATECLIMATE`` that copies ``(1)→(2)`` at
the end of each step.  Here a single :meth:`step` reads the stored
previous-period state, computes the new current-period values, exposes them
(``surface_temperature`` / ``atmospheric_carbon``), and then folds the new
values back into the stored state ready for the next call.
"""

from __future__ import annotations

import math
from typing import Optional

from dsk.parameters.global_parameters import GlobalParameters


class ClimateSystem:
    """Discrete-time C-ROADS carbon-cycle + energy-balance climate box."""

    def __init__(self, global_params: Optional[GlobalParameters] = None) -> None:
        gp = global_params if global_params is not None else GlobalParameters()
        self.gparams: GlobalParameters = gp

        # --- constants (named per dsk_constant.h) ------------------------
        self.ndep: int = int(gp.n_ocean_layers)
        self.dtclim: float = float(gp.dt_climate_years)
        self.niterclim: int = int(gp.n_climate_iterations)
        self.laydep: list[float] = [float(d) for d in gp.ocean_layer_depths_m]

        # ocean / atmosphere carbon exchange
        self.rev0: float = float(gp.reveille_factor_default)
        self.revC: float = float(gp.reveille_concentration_sensitivity)
        self.Conref: float = float(gp.ocean_carbon_upper_ref)
        self.ConrefT: float = float(gp.ocean_carbon_upper_ref_T_sensitivity)
        self.eddydif: float = float(gp.eddy_diffusion_m2_per_year)
        self.Cat0: float = float(gp.atmos_carbon_pre_ind)

        # biosphere
        self.NPP0: float = float(gp.npp_reference)
        self.fertil: float = float(gp.fertilization_effect)
        self.heatstress: float = float(gp.heatstress_effect_on_npp)
        self.humfrac: float = float(gp.humus_fraction_of_decay)
        self.biotime: float = float(gp.biosphere_decay_time_years)
        self.humtime: float = float(gp.humus_decay_time_years)

        # radiation / temperature
        self.forCO2: float = float(gp.radiative_forcing_co2_w_per_m2)
        # outrad = 1.23 * 3.015 / climsens; the stored parameter is the value
        # for the default climate sensitivity (climsens = 3.015 -> outrad = 1.23).
        self.outrad: float = float(gp.outgoing_radiation_w_per_m2_per_k)
        self.otherforcefac: float = float(gp.non_co2_forcing_factor)
        self.seasurf: float = float(gp.sea_surface_fraction)
        self.heatcap: float = float(gp.water_heat_capacity_j_per_m3)
        self.secyr: float = float(gp.seconds_per_year)
        self.include_non_co2_forcing: int = int(gp.include_non_co2_forcing)

        # --- initial state ----------------------------------------------
        # flag_nonCO2_force selects the init set (2010 vs 2020) AND whether
        # the radiative forcing is scaled by otherforcefac.  Baseline = 1
        # (2020 start, non-CO2 forcing included).
        if self.include_non_co2_forcing == 0:
            cat0 = gp.atmos_carbon_init_2010
            con0 = gp.ocean_carbon_init_2010
            hon0 = gp.ocean_heat_init_2010
            ton0 = gp.ocean_temp_init_2010
            tmix0 = gp.t_mixed_init_2010
            biom0 = gp.biosphere_carbon_init_2010
            humm0 = gp.humus_carbon_init_2010
        else:
            cat0 = gp.atmos_carbon_init_2020
            con0 = gp.ocean_carbon_init_2020
            hon0 = gp.ocean_heat_init_2020
            ton0 = gp.ocean_temp_init_2020
            tmix0 = gp.t_mixed_init_2020
            biom0 = gp.biosphere_carbon_init_2020
            humm0 = gp.humus_carbon_init_2020

        # stored previous-period ("(2)") state
        self._cat: float = float(cat0)
        self._biom: float = float(biom0)
        self._humm: float = float(humm0)
        self._tmixed: float = float(tmix0)
        self._con: list[float] = [float(c) for c in con0]
        self._hon: list[float] = [float(h) for h in hon0]
        self._ton: list[float] = [float(t) for t in ton0]

        # current-period exposed values (before any step == init values).
        # Attribute names follow planningDocs/NAME_MAP.md (climate.* rows).
        self.atmospheric_carbon: float = self._cat
        self.surface_temperature: float = self._tmixed
        self.ocean_carbon_per_layer: list[float] = list(self._con)
        self.ocean_heat_per_layer: list[float] = list(self._hon)
        self.ocean_temperature_per_layer: list[float] = list(self._ton)
        self.biosphere_carbon: float = self._biom
        self.humus_carbon: float = self._humm

        # emissions calibration gauge (see calibrate_emissions)
        self._emiss_gauge: Optional[float] = None
        self._emiss_calib_prev: float = float(gp.emissions_first_year_gtc)
        self.emissions_first_year_gtc: float = float(gp.emissions_first_year_gtc)

        # UPDATECLIMATE: previous-step temperature exposed for SHOCKS.
        # Mirrors C++ Tmixed(2) at the point SHOCKS runs (before UPDATECLIMATE folds
        # Tmixed(1)→Tmixed(2)).  Set to _tmixed at the START of each step() call.
        self.previous_surface_temperature: float = self._tmixed

        # Tanomaly history buffer — size freqclim+1, 0-based list with [0] unused (1-indexed
        # convention from C++).  Tanomaly(1) == surface_temperature; slots 2..freqclim+1 store
        # prior values shifted by UPDATECLIMATE.  Only used by flag_shocks==9 Nordhaus damage.
        freqclim: int = int(gp.climate_call_frequency)
        self._tanomaly_history: list = [float(tmix0)] * (freqclim + 2)
        self._freqclim: int = freqclim

    # ------------------------------------------------------------------
    # Emissions calibration (CLIMATEBOX "FIX THE EMISSIONS" block)
    # ------------------------------------------------------------------

    def calibrate_emissions(self, model_emissions: float) -> float:
        """Scale raw DSK-model emissions to the calibrated GtC flux.

        Mirrors the first block of the C++ ``CLIMATEBOX``: on the first call the
        gauge is pinned to the current model-emission level and the calibrated
        flux equals ``emissions_first_year_gtc * dtclim``; thereafter the
        calibrated flux tracks the *relative* change of the model emissions
        since the gauge year, scaled to the reference year's true global GtC::

            g_rate = model_emissions / gauge
            calib  = emissions_first_year_gtc * g_rate

        ``model_emissions`` is C++ ``Emiss_yearly(1)`` (the sum over ``freqclim``
        economic steps).  Returns the calibrated annual emission flux in GtC,
        suitable to pass to :meth:`step`.
        """
        if self._emiss_gauge is None:
            self._emiss_gauge = float(model_emissions)
            calib = self.emissions_first_year_gtc * self.dtclim
        else:
            gauge = self._emiss_gauge if self._emiss_gauge != 0.0 else 1.0
            g_rate = float(model_emissions) / gauge
            calib = self.emissions_first_year_gtc * g_rate
        self._emiss_calib_prev = calib
        return calib

    # ------------------------------------------------------------------
    # The C-ROADS step
    # ------------------------------------------------------------------

    def step(self, yearly_emissions: float) -> None:
        """Advance the climate one ``dt_climate_years`` step.

        ``yearly_emissions`` is the calibrated annual emission flux in GtC
        (C++ ``Emiss_yearly_calib(1)``).
        """
        # Capture pre-step temperature for SHOCKS (= C++ Tmixed(2) at SHOCKS time).
        self.previous_surface_temperature = self._tmixed

        dt = self.dtclim
        ndep = self.ndep
        laydep = self.laydep

        cat_prev = self._cat
        biom_prev = self._biom
        humm_prev = self._humm
        tmixed_prev = self._tmixed
        con_prev = self._con
        hon_prev = self._hon

        # 2) ATMOSPHERE-BIOSPHERE CARBON EXCHANGE (+ EMISSIONS)
        npp = (
            self.NPP0
            * (1.0 + self.fertil * math.log(cat_prev / self.Cat0))
            * (1.0 + self.heatstress * tmixed_prev)
            * dt
        )
        humrelease = humm_prev / self.humtime * dt
        biorelease = biom_prev / self.biotime * (1.0 - self.humfrac) * dt

        dcat1 = yearly_emissions + humrelease + biorelease - npp
        cat1 = cat_prev + dcat1  # preliminary Cat, before ocean uptake

        biom_cur = biom_prev + npp - biom_prev / self.biotime * dt
        humm_cur = (
            humm_prev
            + biom_prev / self.biotime * self.humfrac * dt
            - humm_prev / self.humtime * dt
        )

        # 3) MIXING CARBON BETWEEN OCEAN LAYERS (eddy diffusion)
        # flux[f] between layer f and f+1 (0-based), f = 0..ndep-2
        fluxC = [0.0] * (ndep - 1)
        for f in range(ndep - 1):
            fluxC[f] = (
                self.eddydif
                * (con_prev[f] / laydep[f] - con_prev[f + 1] / laydep[f + 1])
                / ((laydep[f + 1] + laydep[f]) / 2.0)
                * dt
            )

        con_cur = [0.0] * ndep
        con1 = con_prev[0] - fluxC[0]  # preliminary top-layer C (before atm. exch.)
        for k in range(1, ndep - 1):  # middle layers get their final value here
            con_cur[k] = con_prev[k] + fluxC[k - 1] - fluxC[k]
        con_cur[ndep - 1] = con_prev[ndep - 1] + fluxC[ndep - 2]

        # 4) OCEAN-ATMOSPHERE CARBON EXCHANGE (the nasty iterative bit)
        ctot1 = con1 + cat1
        cat_cur = self._equilibrate_atmosphere_ocean(ctot1, cat1, tmixed_prev)
        con_cur[0] = ctot1 - cat_cur  # final top-layer ocean carbon

        # 5) RADIATION AND SURFACE-TEMPERATURE CHANGE
        fco2 = self.forCO2 * math.log(cat_cur / self.Cat0)
        if self.include_non_co2_forcing == 0:
            fin = fco2
        else:
            fin = fco2 * self.otherforcefac
        fout = self.outrad * tmixed_prev

        fluxH = [0.0] * (ndep - 1)
        for f in range(ndep - 1):
            fluxH[f] = (
                self.eddydif
                * (hon_prev[f] / laydep[f] - hon_prev[f + 1] / laydep[f + 1])
                / ((laydep[f + 1] + laydep[f]) / 2.0)
                * dt
            )

        hon_cur = [0.0] * ndep
        ton_cur = [0.0] * ndep
        # top layer: diffusion + radiative input
        hon_cur[0] = hon_prev[0] - fluxH[0] + (fin - fout) * self.secyr / self.seasurf * dt
        ton_cur[0] = hon_cur[0] / laydep[0] / self.heatcap
        tmixed_cur = ton_cur[0]  # surface temp = mixed (top) layer temp
        for k in range(1, ndep - 1):
            hon_cur[k] = hon_prev[k] + fluxH[k - 1] - fluxH[k]
            ton_cur[k] = hon_cur[k] / laydep[k] / self.heatcap
        hon_cur[ndep - 1] = hon_prev[ndep - 1] + fluxH[ndep - 2]
        ton_cur[ndep - 1] = hon_cur[ndep - 1] / laydep[ndep - 1] / self.heatcap

        # --- expose current-period values --------------------------------
        self.atmospheric_carbon = cat_cur
        self.surface_temperature = tmixed_cur
        self.ocean_carbon_per_layer = con_cur
        self.ocean_heat_per_layer = hon_cur
        self.ocean_temperature_per_layer = ton_cur
        self.biosphere_carbon = biom_cur
        self.humus_carbon = humm_cur

        # --- UPDATECLIMATE part 1: fold current -> previous ---------------
        self._cat = cat_cur
        self._tmixed = tmixed_cur
        self._biom = biom_cur
        self._humm = humm_cur
        self._con = con_cur
        self._hon = hon_cur
        self._ton = ton_cur

        # --- UPDATECLIMATE part 2: shift Tanomaly history buffer ----------
        # C++ UPDATECLIMATE: for j=1..freqclim: Tanomaly(freqclim+2-j) = Tanomaly(freqclim+1-j)
        # This shifts slots 1..freqclim into 2..freqclim+1 (1-indexed).
        # Tanomaly(1) == surface_temperature stays at tmixed_cur (set by CLIMATEBOX).
        freq = self._freqclim
        for j in range(1, freq + 1):
            self._tanomaly_history[freq + 2 - j] = self._tanomaly_history[freq + 1 - j]
        self._tanomaly_history[1] = tmixed_cur

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _upper_ocean_equilibrium(self, cat: float, tmixed_prev: float) -> float:
        """Equilibrium upper-ocean carbon for a given atmospheric carbon.

        The Revelle (buffer) factor depends on concentration::

            revelle = rev0 + revC * ln(Cat / Cat0)
            Con_up  = Conref * (1 - ConrefT * Tmixed) * (Cat / Cat0) ** (1 / revelle)
        """
        ratio = cat / self.Cat0
        revelle = self.rev0 + self.revC * math.log(ratio)
        return (
            self.Conref
            * (1.0 - self.ConrefT * tmixed_prev)
            * math.pow(ratio, 1.0 / revelle)
        )

    def _equilibrate_atmosphere_ocean(
        self, ctot1: float, cat1: float, tmixed_prev: float
    ) -> float:
        """Redistribute the conserved atmosphere + upper-ocean carbon to equilibrium.

        Holds ``Ctot1 = Cat + Con_upper`` fixed and solves for the ``Cat`` at
        which ``Con_upper`` equals its equilibrium value, using the secant-style
        iteration from the C++ ``CLIMATEBOX`` (classical Newton fails because the
        function is awkward to differentiate).  The loop runs at most
        ``niterclim - 1`` updates; the result is the last ``Cax`` (slot
        ``niterclim``), or an early-converged value (residual < 1e-10).
        """
        niter = self.niterclim
        # 1-based arrays to mirror the C++ Newmat ColumnVectors exactly.
        cax = [0.0] * (niter + 1)
        cay = [0.0] * (niter + 1)
        caxx = [0.0] * (niter + 1)
        cayy = [0.0] * (niter + 1)
        caa = [0.0] * (niter + 1)

        cax[1] = cat1
        cay[1] = ctot1 - cax[1] - self._upper_ocean_equilibrium(cax[1], tmixed_prev)
        caxx[1] = cax[1] + 1.5 * cay[1]
        cayy[1] = ctot1 - caxx[1] - self._upper_ocean_equilibrium(caxx[1], tmixed_prev)
        caa[1] = (cayy[1] - cay[1]) / (caxx[1] - cax[1])

        i = 1
        while i <= niter - 1:
            cax[i + 1] = cax[i] - cay[i] / caa[i]
            cay[i + 1] = (
                ctot1
                - cax[i + 1]
                - self._upper_ocean_equilibrium(cax[i + 1], tmixed_prev)
            )
            if abs(cay[i + 1]) < 1e-10:
                cax[niter] = cax[i + 1]
                break
            caxx[i + 1] = cax[i + 1] - 2.0 * cay[i] / caa[i]
            cayy[i + 1] = (
                ctot1
                - caxx[i + 1]
                - self._upper_ocean_equilibrium(caxx[i + 1], tmixed_prev)
            )
            caa[i + 1] = (cayy[i + 1] - cay[i + 1]) / (caxx[i + 1] - cax[i + 1])
            i += 1

        return cax[niter]

    # ------------------------------------------------------------------
    @property
    def temperature_anomaly(self) -> float:
        """Surface temperature anomaly (K above pre-industrial)."""
        return self.surface_temperature
