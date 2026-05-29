"""Unit tests for Task 1.10: COMPET2 replicator dynamics.

Acceptance criteria:
  1. Market shares sum to 1 after update.
  2. Firm with above-average competitiveness gains share.
"""
from __future__ import annotations

import pytest
import numpy as np

from dsk.parameters.global_parameters import GlobalParameters
from dsk.sectors.consumption_good_sector import ConsumptionGoodSector


# ---------------------------------------------------------------------------
# Minimal stub firm — only the attributes COMPET2 reads/writes are required.
# ---------------------------------------------------------------------------

class StubFirm:
    """Lightweight stand-in for ConsumptionGoodFirm for unit testing COMPET2."""

    def __init__(
        self,
        price: float,
        unfilled_demand: float,
        market_share: float,
        market_share_prev: float = None,
        market_share_prev_prev: float = None,
        is_new_entrant: bool = False,
    ) -> None:
        self.price                  = price
        self.unfilled_demand        = unfilled_demand
        self.market_share           = market_share
        self.market_share_prev      = market_share if market_share_prev is None else market_share_prev
        self.market_share_prev_prev = market_share if market_share_prev_prev is None else market_share_prev_prev
        self.competitiveness        = 0.0
        self.is_new_entrant         = is_new_entrant
        self.is_alive               = True


def _make_sector(*firms: StubFirm) -> ConsumptionGoodSector:
    sector = ConsumptionGoodSector()
    for f in firms:
        sector.add(f)
    return sector


def _gparams(**overrides) -> GlobalParameters:
    gp = GlobalParameters()
    for k, v in overrides.items():
        setattr(gp, k, v)
    return gp


# ---------------------------------------------------------------------------
# Acceptance criterion 1: shares sum to 1
# ---------------------------------------------------------------------------

class TestMarketSharesSumToOne:
    def test_equal_initial_shares_sum_to_one(self):
        """With equal prices, replicator leaves equal shares; sum=1."""
        n = 5
        share = 1.0 / n
        firms = [StubFirm(price=1.0, unfilled_demand=0.0, market_share=share) for _ in range(n)]
        sector = _make_sector(*firms)
        sector.update_market_shares(_gparams())
        total = sum(f.market_share for f in sector)
        assert abs(total - 1.0) < 1e-10

    def test_unequal_prices_sum_to_one(self):
        """After replicator with different prices, shares still sum to 1."""
        prices = [0.8, 1.0, 1.2, 1.5, 0.6]
        n = len(prices)
        share = 1.0 / n
        firms = [StubFirm(price=p, unfilled_demand=0.0, market_share=share) for p in prices]
        sector = _make_sector(*firms)
        sector.update_market_shares(_gparams())
        total = sum(f.market_share for f in sector)
        assert abs(total - 1.0) < 1e-10

    def test_sum_to_one_with_nonzero_unfilled_demand(self):
        """Sum=1 holds when unfilled_demand is non-zero."""
        prices = [1.0, 1.2, 0.9]
        ufd    = [0.0, 2.0, 1.0]
        n      = len(prices)
        share  = 1.0 / n
        firms  = [
            StubFirm(price=p, unfilled_demand=u, market_share=share)
            for p, u in zip(prices, ufd)
        ]
        sector = _make_sector(*firms)
        sector.update_market_shares(_gparams())
        total = sum(f.market_share for f in sector)
        assert abs(total - 1.0) < 1e-10

    def test_sum_to_one_with_unequal_initial_shares(self):
        """Sum=1 holds when initial shares are unequal (e.g., after deaths)."""
        # Firms have unequal shares that don't sum to 1 (as if some died).
        # The first normalisation in COMPET2 rescales them.
        shares  = [0.3, 0.2, 0.1]  # sum=0.6, not 1
        prices  = [1.0, 1.1, 0.9]
        firms   = [
            StubFirm(price=p, unfilled_demand=0.0, market_share=s)
            for p, s in zip(prices, shares)
        ]
        sector = _make_sector(*firms)
        sector.update_market_shares(_gparams())
        total = sum(f.market_share for f in sector)
        assert abs(total - 1.0) < 1e-10


# ---------------------------------------------------------------------------
# Acceptance criterion 2: above-average competitiveness gains share
# ---------------------------------------------------------------------------

class TestAboveAverageGainsShare:
    """C++ chi = -1.  E2(j) = -omega1*p(j)/p_mean.  Firm with lowest price
    has the highest (least-negative) E, i.e. above-average competitiveness,
    and should gain market share."""

    def _three_firm_sector(self) -> tuple[ConsumptionGoodSector, StubFirm, StubFirm, StubFirm]:
        # prices [0.8, 1.0, 1.2] → mean=1.0
        # E: -0.8 (highest), -1.0 (mean), -1.2 (lowest)
        share = 1.0 / 3.0
        f_low  = StubFirm(price=0.8, unfilled_demand=0.0, market_share=share)
        f_mid  = StubFirm(price=1.0, unfilled_demand=0.0, market_share=share)
        f_high = StubFirm(price=1.2, unfilled_demand=0.0, market_share=share)
        sector = _make_sector(f_low, f_mid, f_high)
        return sector, f_low, f_mid, f_high

    def test_low_price_firm_gains_share(self):
        sector, f_low, f_mid, f_high = self._three_firm_sector()
        initial_share_low = f_low.market_share
        sector.update_market_shares(_gparams())
        assert f_low.market_share > initial_share_low, (
            "Firm with below-average price (above-average competitiveness) "
            "should gain market share."
        )

    def test_high_price_firm_loses_share(self):
        sector, f_low, f_mid, f_high = self._three_firm_sector()
        initial_share_high = f_high.market_share
        sector.update_market_shares(_gparams())
        assert f_high.market_share < initial_share_high, (
            "Firm with above-average price (below-average competitiveness) "
            "should lose market share."
        )

    def test_average_price_firm_unchanged(self):
        """Mid-price firm is at Em2 → its share stays constant (pre-normalisation).
        After normalisation the change is negligible."""
        sector, f_low, f_mid, f_high = self._three_firm_sector()
        initial_share_mid = f_mid.market_share
        sector.update_market_shares(_gparams())
        # Due to renormalisation there can be a tiny deviation; tolerance = 1e-10.
        assert abs(f_mid.market_share - initial_share_mid) < 1e-10

    def test_share_ordering_preserved(self):
        """After update: low-price firm has the largest share."""
        sector, f_low, f_mid, f_high = self._three_firm_sector()
        sector.update_market_shares(_gparams())
        assert f_low.market_share > f_mid.market_share > f_high.market_share


# ---------------------------------------------------------------------------
# Competitiveness is stored on each firm
# ---------------------------------------------------------------------------

class TestCompetitivenessStored:
    def test_competitiveness_set_on_firms(self):
        """After update, each firm holds its E2 value."""
        share = 1.0 / 3.0
        firms = [
            StubFirm(price=0.8, unfilled_demand=0.0, market_share=share),
            StubFirm(price=1.0, unfilled_demand=0.0, market_share=share),
            StubFirm(price=1.2, unfilled_demand=0.0, market_share=share),
        ]
        sector = _make_sector(*firms)
        sector.update_market_shares(_gparams())
        # Prices [0.8, 1.0, 1.2], p2m=1.0, omega1=1 → E = [-0.8, -1.0, -1.2]
        expected = [-0.8, -1.0, -1.2]
        for firm, exp in zip(sector, expected):
            assert abs(firm.competitiveness - exp) < 1e-10

    def test_unfilled_demand_affects_competitiveness(self):
        """A firm with positive unfilled demand has lower competitiveness."""
        share = 0.5
        f_no_ufd  = StubFirm(price=1.0, unfilled_demand=0.0, market_share=share)
        f_has_ufd = StubFirm(price=1.0, unfilled_demand=1.0, market_share=share)
        sector = _make_sector(f_no_ufd, f_has_ufd)
        sector.update_market_shares(_gparams())
        # f_no_ufd: l2(j)=0, l2m=0.5 → term=-omega2*0/0.5=0 → E=-omega1*1/1=-1
        # f_has_ufd: l2(j)=1, l2m=0.5 → term=-omega2*1/0.5=-2 → E=-1-2=-3
        assert f_no_ufd.competitiveness > f_has_ufd.competitiveness


# ---------------------------------------------------------------------------
# Exit floor
# ---------------------------------------------------------------------------

class TestExitFloor:
    def test_firm_below_floor_gets_zero_share(self):
        """A firm whose replicator output < exit2 gets market_share=0."""
        gp = _gparams(
            replicator_strength=-5.0,          # exaggerate for fast exit
            s2_exit_market_share_floor=0.1,    # high floor to trigger exit
        )
        # One very high price firm should drop below exit floor.
        f_good = StubFirm(price=1.0, unfilled_demand=0.0, market_share=0.5)
        f_bad  = StubFirm(price=5.0, unfilled_demand=0.0, market_share=0.5)
        sector = _make_sector(f_good, f_bad)
        sector.update_market_shares(gp)
        # f_bad has a much lower competitiveness; with chi=-5 it should exit.
        assert f_bad.market_share == 0.0

    def test_surviving_firm_holds_all_share_after_exit(self):
        """After one firm exits via floor, remaining firm gets share=1."""
        gp = _gparams(
            replicator_strength=-5.0,
            s2_exit_market_share_floor=0.1,
        )
        f_good = StubFirm(price=1.0, unfilled_demand=0.0, market_share=0.5)
        f_bad  = StubFirm(price=5.0, unfilled_demand=0.0, market_share=0.5)
        sector = _make_sector(f_good, f_bad)
        sector.update_market_shares(gp)
        total = sum(f.market_share for f in sector)
        assert abs(total - 1.0) < 1e-10


# ---------------------------------------------------------------------------
# First-period edge case: all l2(j)=0 → should not crash; shares change
# only due to prices.
# ---------------------------------------------------------------------------

class TestFirstPeriodEdgeCase:
    def test_zero_unfilled_demand_does_not_crash(self):
        """At t=1, l2(j)=0 for all j; COMPET2 must not raise and shares sum to 1."""
        share = 0.25
        firms = [
            StubFirm(price=0.9, unfilled_demand=0.0, market_share=share),
            StubFirm(price=1.0, unfilled_demand=0.0, market_share=share),
            StubFirm(price=1.1, unfilled_demand=0.0, market_share=share),
            StubFirm(price=1.2, unfilled_demand=0.0, market_share=share),
        ]
        sector = _make_sector(*firms)
        sector.update_market_shares(_gparams())
        total = sum(f.market_share for f in sector)
        assert abs(total - 1.0) < 1e-10

    def test_equal_prices_and_zero_ufd_shares_unchanged(self):
        """If all prices and l2 are equal, Em2 equals E for every firm,
        the replicator produces zero change, and shares are unchanged."""
        share = 1.0 / 4.0
        firms = [StubFirm(price=1.0, unfilled_demand=0.0, market_share=share) for _ in range(4)]
        sector = _make_sector(*firms)
        sector.update_market_shares(_gparams())
        for f in sector:
            assert abs(f.market_share - share) < 1e-10
