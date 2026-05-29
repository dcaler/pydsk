from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dsk.nation import Nation


@dataclass
class TradeOffer:
    """Per-nation export supply and import demand for one step."""

    nation_id: str = ""
    excess_supply: float = 0.0
    unmet_demand: float = 0.0
