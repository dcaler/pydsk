import itertools
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dsk.nation import Nation

_id_counter = itertools.count(1)


class Agent:
    """Base class for all DSK agents.

    Attributes
    ----------
    unique_id : int
        Auto-incremented, globally unique across all agent instances in a run.
    nation : Nation
        Back-reference to the containing Nation (set at construction time).
    """

    def __init__(self, nation: "Nation") -> None:
        self.unique_id: int = next(_id_counter)
        self.nation: "Nation" = nation
