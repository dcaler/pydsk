from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dsk.nation import Nation

from dsk.policy.carbon_tax import CarbonTax
from dsk.policy.green_subsidy import GreenConstructionSubsidy, GreenRDSubsidy
from dsk.policy.brown_ban import BrownConstructionBan
from dsk.policy.electrification_mandate import ElectrificationMandate

_INSTRUMENT_REGISTRY: dict[str, type] = {
    "CarbonTax": CarbonTax,
    "GreenConstructionSubsidy": GreenConstructionSubsidy,
    "GreenRDSubsidy": GreenRDSubsidy,
    "BrownConstructionBan": BrownConstructionBan,
    "ElectrificationMandate": ElectrificationMandate,
}


class ClimatePolicy:
    """Container for climate-policy instruments (CarbonTax, GreenSubsidy, BrownBan, etc.).

    Instruments are added via `add_instrument`. `apply(t)` activates all instruments
    that are active at step t.
    """

    def __init__(self, nation: "Nation") -> None:
        self.nation = nation
        self._instruments: list = []

    def add_instrument(self, instrument) -> None:
        self._instruments.append(instrument)

    def apply(self, t: int) -> None:
        for instrument in self._instruments:
            if instrument.is_active(t):
                instrument.apply(self.nation, t)

    @classmethod
    def from_config(cls, cfg: list, nation: "Nation") -> "ClimatePolicy":
        """Build a ClimatePolicy from a list of instrument spec dicts.

        Each element of *cfg* must have a ``type`` key naming one of the
        registered instrument classes; all remaining keys are passed as kwargs
        to the instrument constructor.

        Example::

            cfg = [
                {"type": "CarbonTax", "schedule": "constant", "base_rate": 3.3e-4},
                {"type": "BrownConstructionBan", "invest_ban_offset": 21},
                {"type": "GreenConstructionSubsidy", "y_subs": 0.333},
                {"type": "GreenRDSubsidy", "rd_topup_fraction": 0.5},
                {"type": "ElectrificationMandate", "enforcement_offset": 31},
            ]
            policy = ClimatePolicy.from_config(cfg, nation)
        """
        policy = cls(nation)
        for spec in cfg:
            spec = dict(spec)
            instrument_type = spec.pop("type")
            if instrument_type not in _INSTRUMENT_REGISTRY:
                raise ValueError(f"Unknown policy instrument type: {instrument_type!r}")
            instrument_cls = _INSTRUMENT_REGISTRY[instrument_type]
            policy.add_instrument(instrument_cls(**spec))
        return policy
