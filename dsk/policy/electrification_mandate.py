"""Electrification-fraction mandate instrument.

Ports the electrification-regulation block of CLIMATE_POLICY()
(basecode dsk_main.cpp:980-1000; files_BCERT/0_dsk_main.cpp:988-1008).

Sets two per-period enforcement variables on the nation:

* ``elfrac_reg_now``  — current enforcement level (C++ ``elfrac_reg_now``).
  Firms that fall short of this fraction pay a fine, applied multiplicatively
  inside ``cost_sect1()`` (``dsk_cost_sect1.cpp``).

* ``elfrac_reg_exp``  — expected future level (C++ ``elfrac_reg_exp``).
  Announced ``react_window`` periods before enforcement.  Capital-good firms
  use this for technology-selection decisions inside TECHANGEND so that they
  can start preparing before the fine is actually charged.

C++ parameter mapping
---------------------
``elfrac_reg_val = 1.0``       → ``mandate_value``
``elfrac_reg_fine = 10.0``     → ``fine_rate``
``elfrac_reg_start``           → ``t_start + enforcement_offset``
``elfrac_reg_react = 20``      → ``react_window``

Baseline behaviour
------------------
The instrument is NOT added to ``ClimatePolicy`` in the baseline scenario.
The three nation attributes stay at their ``__init__`` defaults (0.0), so
no fine is ever charged.  To activate (BCERT scenario): use
``enforcement_offset = 31`` and register with ``ClimatePolicy``.

C++ basecode default (baseline OFF)::

    elfrac_reg_start = t_start_climbox + 31 + T*5
                     # T*5 pushes it far enough into the future to be unreachable

C++ BCERT (ON)::

    elfrac_reg_start = t_start_climbox + 31   # (T*0 multiplier)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dsk.nation import Nation


class ElectrificationMandate:
    """Electrification-fraction regulation: fine firms below the mandated level.

    Parameters
    ----------
    mandate_value : float
        Required electrification fraction (0–1).  ``elfrac_reg_val = 1.0``
        in C++ (= full electrification required).
    fine_rate : float
        Multiplicative fine scale.  ``elfrac_reg_fine = 10.0`` in C++.
        Cost multiplier = 1 + (elfrac_deficit + ...) * fine_rate.
    enforcement_offset : int
        Years after ``t_start`` when the mandate is enforced.
        BCERT: 31.  Baseline: 31 + 5*T (effectively never).
    react_window : int
        How many years in advance of enforcement the mandate is "announced"
        (``elfrac_reg_react = 20`` in C++).  Firms may react to
        ``elfrac_reg_exp`` during TECHANGEND before the fine is charged.
    mandate_on : bool
        Master switch.  ``False`` → all elfrac nation variables stay 0.0.
    t_start : int or None
        Override for ``nation.gparams.climate_start_step``.  Useful for
        unit tests that need to trigger the mandate without building a full
        nation.
    """

    def __init__(
        self,
        mandate_value: float = 1.0,
        fine_rate: float = 10.0,
        enforcement_offset: int = 31,
        react_window: int = 20,
        mandate_on: bool = True,
        t_start: int | None = None,
    ) -> None:
        self.mandate_value = mandate_value
        self.fine_rate = fine_rate
        self.enforcement_offset = enforcement_offset
        self.react_window = react_window
        self.mandate_on = mandate_on
        self._t_start = t_start

    # ------------------------------------------------------------------
    # ClimatePolicy protocol
    # ------------------------------------------------------------------

    def is_active(self, t: int) -> bool:
        return True

    def apply(self, nation: "Nation", t: int) -> None:
        """Set elfrac regulation state on the nation for period *t*.

        Called from ClimatePolicy.apply() at the start of production_phase().

        Side effects
        ------------
        Writes ``nation.elfrac_reg_now``, ``nation.elfrac_reg_exp``, and
        ``nation.elfrac_reg_fine``.  These are read by:

        * ``CapitalGoodFirm.update_price_and_cost()`` — to charge the
          current-period fine via ``cost_sect1()``.
        * ``CapitalGoodFirm.advance_technology()`` — to evaluate expected
          future costs during tech adoption decisions (TECHANGEND) and to
          trigger the emergency R&D split.
        """
        if not self.mandate_on:
            nation.elfrac_reg_now = 0.0
            nation.elfrac_reg_exp = 0.0
            nation.elfrac_reg_fine = 0.0
            return

        t_start = (
            self._t_start
            if self._t_start is not None
            else nation.gparams.climate_start_step
        )
        elfrac_reg_start = t_start + self.enforcement_offset

        # C++ lines 997-1000:
        #   if (t >= elfrac_reg_start)        elfrac_reg_now = elfrac_reg_val
        #   if (t >= elfrac_reg_start - react) elfrac_reg_exp = elfrac_reg_val
        nation.elfrac_reg_now = (
            self.mandate_value if t >= elfrac_reg_start else 0.0
        )
        nation.elfrac_reg_exp = (
            self.mandate_value
            if t >= elfrac_reg_start - self.react_window
            else 0.0
        )
        nation.elfrac_reg_fine = self.fine_rate
