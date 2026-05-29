"""Brown electricity-plant construction ban instrument.

Ports the brown-invest-ban block of CLIMATE_POLICY() (dsk_main.cpp:958-977
for the basecode; files_BCERT/0_dsk_main.cpp:964-985 for the BCERT scenario).

Sets ``ElectricityProducer.brown_invest_ban_year`` and
``ElectricityProducer.brown_use_ban_year`` each period.  Both variables are
already read by ``plan_capacity_expansion()`` (to block new builds and compute
the payback deadline) and by the year-end scrapping loop (to scrap all brown
plants when use is banned).

C++ semantics (BCERT):
    Before announcement (t < t_start + invest_announce_offset):
        brown_invest_ban = 5*T   (far future → no restriction)
    After announcement:
        brown_invest_ban = t_start + invest_ban_offset

    brown_invest_ban = min(brown_invest_ban, brown_use_ban)
    (No point building what you can't use.)

The baseline does not add this instrument; the EP initialiser already sets both
ban years to ``5 * total_steps``.  Adding the instrument with BCERT defaults
replicates the ban-active trajectory.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dsk.nation import Nation


class BrownConstructionBan:
    """Ban on building (and optionally using) new brown electricity plants.

    Parameters
    ----------
    invest_ban_offset : int
        Years after ``climate_start_step`` when brown investment is forbidden.
        BCERT: 21.  Use a very large number (e.g. ``5*T``) to disable.
    use_ban_offset : int or None
        Years after ``climate_start_step`` when brown plant *use* is forbidden.
        ``None`` (default) → ``5 * total_steps + 26`` (effectively never in
        any realistic run), matching the BCERT C++ ``t_start+26+T*5``.
    invest_announce_offset : int
        Years after ``climate_start_step`` when the investment ban is first
        "announced".  Before this timestep, ``brown_invest_ban_year`` is set
        to the far-future ``5*T`` sentinel.  BCERT: 1.
    use_announce_offset : int
        Corresponding announcement offset for the use ban.  BCERT: 11 (same
        as the basecode default, so effectively the use ban is not announced
        within the normal run horizon).
    ban_on : bool
        Master switch.  ``False`` → both ban years remain at ``5*T`` (no-op).
    t_start : int or None
        Override ``nation.gparams.climate_start_step`` if supplied.  Useful
        for unit tests that want to avoid building a full nation.
    """

    def __init__(
        self,
        invest_ban_offset: int = 21,
        use_ban_offset: int | None = None,
        invest_announce_offset: int = 1,
        use_announce_offset: int = 11,
        ban_on: bool = True,
        t_start: int | None = None,
    ) -> None:
        self.invest_ban_offset = invest_ban_offset
        self.use_ban_offset = use_ban_offset  # None → resolved at apply() time
        self.invest_announce_offset = invest_announce_offset
        self.use_announce_offset = use_announce_offset
        self.ban_on = ban_on
        self._t_start = t_start

    # ------------------------------------------------------------------
    # ClimatePolicy protocol
    # ------------------------------------------------------------------

    def is_active(self, t: int) -> bool:
        return True

    def apply(self, nation: "Nation", t: int) -> None:
        ep = nation.electricity_producer
        T = nation.gparams.total_steps
        t_start = self._t_start if self._t_start is not None else nation.gparams.climate_start_step
        use_offset = self.use_ban_offset if self.use_ban_offset is not None else (5 * T + 26)

        if not self.ban_on:
            ep.brown_invest_ban_year = 5 * T
            ep.brown_use_ban_year = 5 * T
            return

        # Investment ban year: not-yet-announced → far future
        invest_ban = (
            5 * T if t < t_start + self.invest_announce_offset
            else t_start + self.invest_ban_offset
        )

        # Use ban year: not-yet-announced → far future
        use_ban = (
            5 * T if t < t_start + self.use_announce_offset
            else t_start + use_offset
        )

        # Enforce: no point investing in something you cannot operate
        invest_ban = min(invest_ban, use_ban)

        ep.brown_invest_ban_year = invest_ban
        ep.brown_use_ban_year = use_ban
