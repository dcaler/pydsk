from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from dsk.agent_set import AgentSet

if TYPE_CHECKING:
    from dsk.parameters.global_parameters import GlobalParameters


class ConsumptionGoodSector(AgentSet):
    """Collection of ConsumptionGoodFirm agents with sector-level helpers."""

    def update_market_shares(self, gparams: "GlobalParameters") -> None:
        """Replicator dynamics on consumption-good firms (COMPET2).

        C++ dsk_main.cpp COMPET2() lines 4933-5044.

        Vectorised: f_new = f_old * (1 + chi * (E - Em2) / Em2)
        where Em2 = weighted mean competitiveness (lag-1 share weights).

        Two normalisation passes (matching C++):
        1. Before Em2: rescale all three share periods to sum-to-1,
           correcting for firms that died since the last call.
        2. After replicator + exit floor: renormalise so current
           shares sum to 1 again.
        """
        chi    = gparams.replicator_strength           # C++ chi    = -1
        omega1 = gparams.competitiveness_price_weight  # C++ omega1 = 1
        omega2 = gparams.competitiveness_demand_weight # C++ omega2 = 1
        exit2  = gparams.s2_exit_market_share_floor    # C++ exit2  = 0.00001
        flag_entry = gparams.entry_random_copy_scope   # C++ flagENTRY = 0

        if len(self) == 0:
            return

        # --- Mean price p2m and mean unfulfilled demand l2m ---
        # C++ lines 4938-4965
        if flag_entry < 2:
            # flagENTRY=0 (baseline): include all firms in the means
            p2m = self.get("price").sum() / len(self)
            l2m = self.get("unfilled_demand").sum() / len(self)
        else:
            # flagENTRY>=2: exclude new entrants (Ke(j)>0) from means
            incumbents = [f for f in self._agents if not f.is_new_entrant]
            n2eff = len(incumbents)
            if n2eff == 0:
                return
            p2m = sum(f.price for f in incumbents) / n2eff
            l2m = sum(f.unfilled_demand for f in incumbents) / n2eff

        # Guard: avoid 0/0 when all unfulfilled demands are 0 (t=1)
        p2m_safe = p2m if p2m != 0.0 else 1.0
        l2m_safe = l2m if l2m != 0.0 else 1.0

        # --- Competitiveness E2(j) = -omega1*p2(j)/p2m - omega2*l2(j)/l2m ---
        # C++ line 4971. E is non-positive: lower price/unfilled demand → higher E.
        prices = self.get("price")
        ufds   = self.get("unfilled_demand")
        E2 = -omega1 * prices / p2m_safe - omega2 * ufds / l2m_safe
        self.set("competitiveness", E2)

        # --- First normalisation (C++ lines 4967-4991) ---
        # Rescale all three periods of market share to correct for dead firms,
        # then compute weighted mean competitiveness Em2 using lag-1 shares.
        f1 = self.get("market_share")
        f2 = self.get("market_share_prev")
        f3 = self.get("market_share_prev_prev")

        ftot1 = f1.sum()
        ftot2 = f2.sum()
        ftot3 = f3.sum()

        if ftot1 <= 0.0 or ftot2 <= 0.0:
            return  # all firms dead or market has collapsed

        f1 = f1 / ftot1
        f2 = f2 / ftot2
        if ftot3 > 0.0:
            f3 = f3 / ftot3

        # Mean competitiveness weighted by normalised lag-1 shares
        # C++ line 4984: Em2(1) += E2(1,j)*f2(2,j)
        Em2 = (E2 * f2).sum()

        if Em2 == 0.0:
            # All firms equally competitive; no share change
            self.set("market_share",          f1)
            self.set("market_share_prev",     f2)
            self.set("market_share_prev_prev", f3)
            return

        # --- Replicator update (C++ lines 4997-5020) ---
        # f_new = f2_normalised * (1 + chi*(E2 - Em2)/Em2)
        f_new = f2 * (1.0 + chi * (E2 - Em2) / Em2)

        # New entrants get zero share when flagENTRY >= 2 (C++ lines 4999-5003)
        if flag_entry >= 2:
            is_entrant = np.array(
                [f.is_new_entrant for f in self._agents], dtype=bool
            )
            f_new[is_entrant] = 0.0
            f2[is_entrant]    = 0.0
            f3[is_entrant]    = 0.0

        # Exit floor: zero all three periods for firms below exit2 (C++ lines 5009-5015)
        below_floor = f_new < exit2
        f_new[below_floor] = 0.0
        f2[below_floor]    = 0.0
        f3[below_floor]    = 0.0

        # --- Second (final) normalisation (C++ lines 5025-5031) ---
        ftot1_new = f_new.sum()
        ftot2_new = f2.sum()
        ftot3_new = f3.sum()

        if ftot1_new <= 0.0:
            return  # all firms exited — catastrophic collapse

        f_new = f_new / ftot1_new
        if ftot2_new > 0.0:
            f2 = f2 / ftot2_new
        if ftot3_new > 0.0:
            f3 = f3 / ftot3_new

        self.set("market_share",          f_new)
        self.set("market_share_prev",     f2)
        self.set("market_share_prev_prev", f3)
