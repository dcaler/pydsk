"""Green construction and R&D subsidy instruments.

Ports the building-subsidy and R&D-multiplier blocks of CLIMATE_POLICY()
(dsk_main.cpp:930-955 and :873-901 respectively) for the BCERT / CER scenario
family from Wieners 2025.

Two instruments are provided:

GreenConstructionSubsidy
    Sets ``ElectricityProducer.subsidy_per_plant`` (Sub_ge) and
    ``ElectricityProducer.max_subsidised_plants`` (NSubmax_ge) each period.
    ``plan_capacity_expansion`` reads these to reduce the effective cost of
    green plants via ``green_plant_cost()``.

    Formula (BCERT):
        Sub_ge = max(CF_ge - (CF_de + A_de * pf * payback) * y_subs, 0)
    Active while:
        (a) t >= t_start + 1, AND
        (b) CF_ge(t-1) < outer_ratio * (CF_de(t-1) + A_de(t-1)*pf*payback)
            [green not yet implausibly cheap — outer guard], AND
        (c) CF_ge(t) / payback > inner_thresh * (CF_de(t)/payback + A_de(t)*pf)
            [green still more expensive than brown per year — inner guard].
    Subsidy cap: NSubmax_ge = min(cap_fraction * (K_ge + K_de), max_cap_absolute).

GreenRDSubsidy
    Sets ``ElectricityProducer.govt_rd_all_multiplier`` (RnD_en_all_mult) so
    that ``do_rd()`` tops up green R&D by a fraction of total energy R&D:
        RD_gov_topup = (RD_en_ge + RD_en_de) * rd_topup_fraction
    BCERT value: rd_topup_fraction = 0.5 (government matches 50 % of total R&D).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dsk.nation import Nation


class GreenConstructionSubsidy:
    """Per-plant building subsidy for green electricity plants.

    Parameters
    ----------
    y_subs : float
        Fraction of the brown total cost (CF_de + A_de*pf*payback) used to set
        the subsidy floor.  0 = no subsidy; 1/3 = BCERT baseline.
    cap_fraction : float
        Maximum subsidised plants as a fraction of total installed capacity
        (K_ge + K_de).  0.05 = BCERT (5 %).
    max_cap_absolute : float
        Hard ceiling on subsidised-plant count (NSubmax_ge).
        50_000_000 = BCERT (effectively no limit in practice).
    outer_ratio : float
        Outer activation guard: subsidy suppressed when green build cost exceeds
        this multiple of the brown full lifecycle cost.  Default 40 (BCERT).
    inner_thresh : float
        Inner activation guard: subsidy active only while green annual cost /
        payback > inner_thresh * (brown annual cost).  Default 2/3 (BCERT).
        When green becomes cheap enough, the subsidy is no longer needed.
    t_start : int or None
        Override t_start_climbox.  None (default) reads from
        nation.gparams.climate_start_step at the first apply() call.
    subsidy_on : bool
        Master switch.  False keeps Sub_ge = 0 regardless of other conditions.
    """

    def __init__(
        self,
        y_subs: float = 1.0 / 3.0,
        cap_fraction: float = 0.05,
        max_cap_absolute: float = 50_000_000.0,
        outer_ratio: float = 40.0,
        inner_thresh: float = 2.0 / 3.0,
        t_start: int | None = None,
        subsidy_on: bool = True,
    ) -> None:
        self.y_subs = y_subs
        self.cap_fraction = cap_fraction
        self.max_cap_absolute = max_cap_absolute
        self.outer_ratio = outer_ratio
        self.inner_thresh = inner_thresh
        self._t_start = t_start
        self.subsidy_on = subsidy_on

        self._resolved_t_start: int | None = None

        # Previous-period frontier values (needed for outer activation guard).
        # Seeded with None; first meaningful read happens at t >= t_start + 2.
        self._prev_cf_ge: float | None = None
        self._prev_brown_full_cost: float | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_t_start(self, nation: "Nation") -> int:
        if self._resolved_t_start is None:
            if self._t_start is not None:
                self._resolved_t_start = self._t_start
            elif nation.gparams is not None:
                self._resolved_t_start = nation.gparams.climate_start_step
            else:
                self._resolved_t_start = 80
        return self._resolved_t_start

    @staticmethod
    def _brown_full_cost(cf_de: float, a_de: float, pf: float, payback: float) -> float:
        """CF_de + A_de * pf * payback_en — total brown lifecycle cost per plant."""
        return cf_de + a_de * pf * payback

    def compute_subsidy(
        self,
        cf_ge: float,
        cf_de: float,
        a_de: float,
        pf: float,
        payback: float,
        k_ge: float,
        k_de: float,
        t: int,
    ) -> tuple[float, float]:
        """Return (sub_ge, nsubmax_ge) for the current period.

        Pure formula — can be called independently of a Nation for unit tests.

        Parameters
        ----------
        cf_ge : float
            Current frontier green build cost (CF_ge(t)).
        cf_de : float
            Current frontier brown build cost (CF_de(t)).
        a_de : float
            Current frontier brown thermal inefficiency (A_de(t)).
        pf : float
            Fossil-fuel price.
        payback : float
            Green plant payback threshold (payback_en).
        k_ge : float
            Total green installed capacity (K_ge(2)).
        k_de : float
            Total brown installed capacity (K_de(2)).
        t : int
            Current model step (used for t_start guard only — caller must supply
            t_start via ``is_active`` or guard externally).

        Returns
        -------
        (sub_ge, nsubmax_ge) : tuple[float, float]
        """
        if not self.subsidy_on:
            return 0.0, 0.0

        brown_full = self._brown_full_cost(cf_de, a_de, pf, payback)

        # Inner condition: green still more expensive per year than brown
        green_annual = cf_ge / payback if payback > 0.0 else float("inf")
        brown_annual = cf_de / payback + a_de * pf if payback > 0.0 else float("inf")
        inner_ok = green_annual > self.inner_thresh * brown_annual

        # Outer condition: green not implausibly cheap already
        outer_ok = True
        if self._prev_cf_ge is not None and self._prev_brown_full_cost is not None:
            prev_bfc = self._prev_brown_full_cost
            outer_ok = (
                prev_bfc <= 0.0
                or self._prev_cf_ge < self.outer_ratio * prev_bfc
            )

        if not (inner_ok and outer_ok):
            return 0.0, 0.0

        sub_ge = max(cf_ge - brown_full * self.y_subs, 0.0)
        nsubmax_ge = min(self.cap_fraction * (k_ge + k_de), self.max_cap_absolute)
        return sub_ge, nsubmax_ge

    # ------------------------------------------------------------------
    # Instrument API
    # ------------------------------------------------------------------

    def is_active(self, t: int) -> bool:
        """Always True: activation logic lives inside apply() to share state."""
        return True

    def apply(self, nation: "Nation", t: int) -> None:
        """Set Sub_ge and NSubmax_ge on the nation's ElectricityProducer.

        Mirrors the building-subsidy block of CLIMATE_POLICY() in dsk_main.cpp.
        """
        t_start = self._resolve_t_start(nation)
        ep = nation.electricity_producer

        if t < t_start + 1 or not self.subsidy_on:
            ep.subsidy_per_plant = 0.0
            ep.max_subsidised_plants = 0.0
            # Still record current frontier values for next period's outer guard.
            self._update_prev(ep, nation.params.fossil_fuel_price,
                              nation.gparams.green_plant_payback_threshold)
            return

        pf = nation.params.fossil_fuel_price
        payback = nation.gparams.green_plant_payback_threshold
        cf_ge = ep.frontier_green_build_cost
        cf_de = ep.frontier_brown_build_cost
        a_de = ep.frontier_brown_thermal_ineff
        k_ge = float(ep.total_green_capacity)
        k_de = float(ep.total_brown_capacity)

        sub_ge, nsubmax_ge = self.compute_subsidy(
            cf_ge, cf_de, a_de, pf, payback, k_ge, k_de, t
        )

        ep.subsidy_per_plant = sub_ge
        ep.max_subsidised_plants = nsubmax_ge

        # Save for next period's outer guard.
        self._update_prev(ep, pf, payback)

    def _update_prev(
        self, ep, pf: float, payback: float
    ) -> None:
        self._prev_cf_ge = ep.frontier_green_build_cost
        cf_de = ep.frontier_brown_build_cost
        a_de = ep.frontier_brown_thermal_ineff
        self._prev_brown_full_cost = self._brown_full_cost(cf_de, a_de, pf, payback)


class GreenRDSubsidy:
    """Government R&D multiplier that tops up green energy R&D.

    Sets ``ElectricityProducer.govt_rd_all_multiplier`` (RnD_en_all_mult) so
    that ``do_rd()`` augments green R&D spending by a fraction of total
    energy R&D (RD_en_ge + RD_en_de):

        RD_gov_topup = (RD_en_ge + RD_en_de) * rd_topup_fraction

    The top-up is counted as a government expenditure and subtracted from
    the electricity producer's profit (``do_rd`` handles both).

    BCERT value: ``rd_topup_fraction = 0.5`` (C++ ``RnD_en_all_mult = 0.5*1``).

    Parameters
    ----------
    rd_topup_fraction : float
        Fraction of total energy R&D funded by the government.  0 = baseline
        no-op; 0.5 = BCERT.
    t_start : int or None
        Override t_start_climbox.  None reads from nation.gparams at first call.
    subsidy_on : bool
        Master switch.
    """

    def __init__(
        self,
        rd_topup_fraction: float = 0.5,
        t_start: int | None = None,
        subsidy_on: bool = True,
    ) -> None:
        self.rd_topup_fraction = rd_topup_fraction
        self._t_start = t_start
        self.subsidy_on = subsidy_on
        self._resolved_t_start: int | None = None

    def _resolve_t_start(self, nation: "Nation") -> int:
        if self._resolved_t_start is None:
            if self._t_start is not None:
                self._resolved_t_start = self._t_start
            elif nation.gparams is not None:
                self._resolved_t_start = nation.gparams.climate_start_step
            else:
                self._resolved_t_start = 80
        return self._resolved_t_start

    def is_active(self, t: int) -> bool:
        return True

    def apply(self, nation: "Nation", t: int) -> None:
        """Set govt_rd_all_multiplier on the ElectricityProducer.

        Mirrors the multiplicative R&D block of CLIMATE_POLICY() in dsk_main.cpp,
        lines 887-901 (BCERT: ``RnD_en_all_mult = 0.5``).
        """
        t_start = self._resolve_t_start(nation)
        ep = nation.electricity_producer

        if t >= t_start + 1 and self.subsidy_on:
            ep.govt_rd_all_multiplier = self.rd_topup_fraction
        else:
            ep.govt_rd_all_multiplier = 0.0
