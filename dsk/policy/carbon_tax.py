"""Carbon-tax policy instrument.

Ports the carbon-tax block of CLIMATE_POLICY() in dsk_main.cpp:708, lines 718–818.

Two schedules are supported:
  'constant'    — inflation-adjusted flat rate (Tc scenario in Wieners 2025):
                  rate(t) = (cpi(t) / cpi_ref) * base_rate
                  where cpi_ref is the CPI recorded at t=2 (C++ cpi_old(3)).
  'exponential' — exponential growth (TD2 / Nordhaus-style):
                  rate(t) = base_rate * exp(growth_rate * (t - (t_start + 2)))

When applied at each time step the instrument also updates the fossil-fuel price:
    pf(t) = pf(t-1) * (cpi(t-1) / cpi(t-2)) * 1.004
(inflation-corrected + 0.4 %/yr real growth, C++ line 720).
This update runs regardless of whether the carbon tax itself is active,
mirroring the unconditional structure of CLIMATE_POLICY().
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dsk.nation import Nation

SECTOR_S1 = "s1"
SECTOR_S2 = "s2"
SECTOR_ENERGY = "energy"


class CarbonTax:
    """Carbon-tax instrument with constant or exponential schedule.

    Parameters
    ----------
    schedule : str
        'constant' (default) or 'exponential'.
    base_rate : float
        For 'constant': the nominal annual rate (TAX_RATE = 3.3e-4 in C++ baseline).
        For 'exponential': the rate at t = t_start + 2 (X_0).
    growth_rate : float
        Annual growth factor for 'exponential' schedule; ignored for 'constant'.
        E.g. 0.09 for 9 %/yr.
    base_rate_s2 : float
        Rate for sector-2 firms (default 0; sector-2 firms use no fossil fuel
        in the baseline, making this tax irrelevant until process emissions are
        enabled).
    tax_on : bool
        If False all rates are zero (TAX_ON=0 in C++).
    t_start : int or None
        Override for t_start_climbox. When None (default) the value is taken
        from nation.gparams.climate_start_step at the first apply() call.
    revenue_use : list of float, optional
        Four-element weight vector specifying how CO2 tax revenue is allocated:
          [0] → government budget (Tax)
          [1] → household unemployment benefit (G, C++ t_CO2_use(2))
          [2] → energy-sector R&D fund (C++ t_CO2_use(3), RnD_funds_En)
          [3] → capital-good-sector R&D fund (C++ t_CO2_use(4), RnD_funds_S1)
        Weights are normalised to sum to 1 (mirrors C++ normalisation at line 836).
        Default [1, 0, 0, 0]: all revenue enters the government fiscal account.
        Makefile scenario definitions:
          B/Tc/T2  → [1, 0, 0, 0]  (TCO2_1=1, all to gov budget)
          T2h      → [0, 1, 0, 0]  (TCO2_2=1, all to households)
          T2i      → [0, 0, 0, 1]  (TCO2_4=1, all to S1 R&D)
    """

    def __init__(
        self,
        schedule: str = "constant",
        base_rate: float = 3.3e-4,
        growth_rate: float = 0.0,
        base_rate_s2: float = 0.0,
        tax_on: bool = True,
        t_start: int | None = None,
        revenue_use: list | None = None,
    ) -> None:
        self.schedule = schedule
        self.base_rate = base_rate
        self.growth_rate = growth_rate
        self.base_rate_s2 = base_rate_s2
        self.tax_on = tax_on
        self._t_start = t_start

        # Normalise revenue_use weights to sum to 1 (C++ lines 828-836).
        raw = list(revenue_use) if revenue_use is not None else [1.0, 0.0, 0.0, 0.0]
        total = sum(raw) or 1.0
        self.revenue_use: list[float] = [w / total for w in raw]

        # CPI recorded at t=2 — the nominal anchor for the constant schedule.
        # C++ cpi_old(3): set once at t=2 and never updated.
        self._cpi_ref: float | None = None

        # t_start_climbox resolved from the nation on first apply().
        self._resolved_t_start: int | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_active(self, t: int) -> bool:
        """Always True: the instrument runs each period (fuel price update is unconditional)."""
        return True

    def rate_for(self, sector: str, t: int, cpi_ratio: float = 1.0) -> float:
        """Compute the carbon tax rate for *sector* at step *t*.

        This is a pure formula that can be called independently of the nation
        (useful for unit tests).

        Parameters
        ----------
        sector : 's1', 's2', or 'energy'
        t : model step
        cpi_ratio : cpi_current / cpi_ref
            Used by the 'constant' schedule to inflation-adjust the rate.
            Ignored by 'exponential'. Default 1.0 (no adjustment).

        Returns
        -------
        float
            Carbon tax rate, floored at 0.
        """
        t_start = self._resolved_t_start if self._resolved_t_start is not None else (self._t_start or 80)

        if t <= t_start or not self.tax_on:
            return 0.0

        base = self.base_rate_s2 if sector == SECTOR_S2 else self.base_rate

        if self.schedule == "constant":
            return max(0.0, cpi_ratio * base)

        if self.schedule == "exponential":
            t0 = t_start + 2
            return max(0.0, base * math.exp(self.growth_rate * (t - t0)))

        return max(0.0, base)

    def apply(self, nation: "Nation", t: int) -> None:
        """Apply the carbon tax and fuel price update for period *t*.

        Called from ClimatePolicy.apply() at the start of production_phase().

        Side effects
        ------------
        - Captures cpi_ref at t=2 (once only).
        - Updates nation.params.fossil_fuel_price for t > 3.
        - Writes carbon tax rates into nation.government and nation.
        """
        # ── Resolve t_start once ────────────────────────────────────────
        if self._resolved_t_start is None:
            if self._t_start is not None:
                self._resolved_t_start = self._t_start
            elif nation.gparams is not None:
                self._resolved_t_start = nation.gparams.climate_start_step
            else:
                self._resolved_t_start = 80  # safe fallback

        # ── Capture CPI reference at t=2 (C++ cpi_old(3)) ──────────────
        # At the start of period 2, nation.cpi holds the CPI from period 1.
        if t == 2 and self._cpi_ref is None:
            self._cpi_ref = nation.cpi

        # ── Fuel price: inflation + 0.4%/yr real growth (C++ line 720) ─
        # Guard t > 3: same as C++ to avoid initialisation noise.
        # At start of period t:
        #   nation.cpi     = CPI computed at end of t-1
        #   nation.cpi_prev = CPI computed at end of t-2
        if t > 3 and nation.cpi_prev > 0.0:
            nation.params.fossil_fuel_price *= (nation.cpi / nation.cpi_prev) * 1.004

        # ── Carbon tax rates ─────────────────────────────────────────────
        t_start = self._resolved_t_start

        if t <= t_start or not self.tax_on:
            rate_s1 = 0.0
            rate_s2 = 0.0
            rate_en = 0.0
        else:
            cpi_ref = self._cpi_ref if self._cpi_ref is not None else 1.0
            cpi_ratio = nation.cpi / cpi_ref if cpi_ref > 0.0 else 1.0

            rate_s1 = self.rate_for(SECTOR_S1, t, cpi_ratio)
            rate_s2 = self.rate_for(SECTOR_S2, t, cpi_ratio)
            rate_en = self.rate_for(SECTOR_ENERGY, t, cpi_ratio)

        # Push rates to nation state (both redundant paths exist from pre-M5 work)
        nation.carbon_tax_rate_s1 = rate_s1
        nation.carbon_tax_rate_s2 = rate_s2
        gov = nation.government
        gov.carbon_tax_rate_industry1 = rate_s1
        gov.carbon_tax_rate_industry2 = rate_s2
        gov.carbon_tax_rate_energy = rate_en

        # Push revenue-use weights so Government.compute_budget can route CO2 revenue.
        # C++ CLIMATE_POLICY lines 828-836: t_CO2_use(j) normalised and stored globally.
        gov.revenue_use = self.revenue_use
