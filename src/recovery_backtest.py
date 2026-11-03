"""Recovery pyramid: run the 1% pyramid only when NQ climbs out of a >= 5% pullback.

Rules (defaults):
  1. Track the swing high H: the highest price since the last reset.
  2. Once price is >= 5% below H, a wave is armed; track the wave low L (the
     lowest price since).
  3. Starting point P0 = L + 70% x (H - L).  When price climbs back to P0, buy
     1 unit (buy-stop).  From there the same pyramid as the main strategy: +1 unit
     at every +1% level above P0 (P0 x 1.01^k), each unit stopped 1% below its own
     entry and bought again if price climbs back through its level.
  4. Cancel: if price falls below the wave low L (the selloff extends), the
     campaign ends (every unit has been stopped by then); L moves to the new low
     and the new 70% retracement level becomes the new starting point.
  5. Reset: when price reaches P0 x 1.12 (+12% from the starting point), sell
     everything there (limit order) and start over: wait for a new >= 5% pullback
     from the next swing high.

Fills follow pyramid_backtest.py: 1-minute bars, intrabar path O-L-H-C (up bar)
or O-H-L-C (down bar), stops and buy-stops at their trigger price plus slippage,
gaps through a trigger at the open; the +12% exit is a limit order (no slippage,
a gap above it fills at the open).
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

SEEK, ARMED, ACTIVE = "seek", "armed", "active"


@dataclass
class RecoveryConfig:
    pullback: float = 0.05            # minimum pullback from the swing high that arms a wave
    retrace: float = 0.70             # entry when price retraces this fraction of the wave
    take_profit: float | None = 0.12  # sell everything at +12% from the starting point (None = never)
    step: float = 0.01                # add a unit every +1%
    stop: float = 0.01                # each unit stopped 1% below its entry
    slippage: float = 0.5             # NQ points per side on stop / market fills
    commission: float = 2.50          # USD per contract per side
    point_value: float = 20.0         # NQ = $20/pt (MNQ = $2/pt)
    max_units: int | None = None      # optional cap on contracts held at once
    max_stopouts: int | None = None   # optional: abandon a campaign after this many stop-outs
    max_days: float | None = None     # optional: abandon a campaign after this many days

    def label(self):
        tp = "none" if self.take_profit is None else f"{self.take_profit*100:g}%"
        return (f"pullback {self.pullback*100:g}%, retrace {self.retrace*100:g}%, "
                f"take profit {tp}, step {self.step*100:g}%, stop {self.stop*100:g}%")


class RecoveryPyramid:
    def __init__(self, cfg: RecoveryConfig, first_price: float):
        self.cfg = cfg
        self.g = math.log1p(cfg.step)
        self.state = SEEK
        self.H = first_price
        self.L = None
        self.P0 = None
        self.units: dict[int, dict] = {}
        self.heap: list = []
        self.uid = 0
        self.n_units = 0
        self.sum_basis = 0.0
        self.cash = 0.0
        self.trades: list = []
        self.campaigns: list = []
        self.camp = None
        self.prev = first_price

    # ---------------- grid helpers ----------------
    def lvl(self, k):
        return self.P0 * math.exp(self.g * k)

    def kidx(self, p):                 # highest k with L_k <= p
        k = math.floor(math.log(p / self.P0) / self.g)
        if self.lvl(k + 1) <= p:
            k += 1
        elif self.lvl(k) > p:
            k -= 1
        return k

    def target(self):
        tp = self.cfg.take_profit
        return math.inf if tp is None else self.P0 * (1.0 + tp)

    # ---------------- orders ----------------
    def _buy(self, k, fill, ts):
        stop = fill * (1.0 - self.cfg.stop)
        self.uid += 1
        self.units[k] = dict(entry=fill, stop=stop, basis=fill, banked=0.0, ets=ts, uid=self.uid)
        heapq.heappush(self.heap, (-stop, k, self.uid))
        self.n_units += 1
        self.sum_basis += fill
        self.cash -= self.cfg.commission
        c = self.camp
        c["entries"] += 1
        c["max_units"] = max(c["max_units"], self.n_units)

    def _sell(self, k, fill, ts, reason):
        u = self.units.pop(k)
        self.n_units -= 1
        self.sum_basis -= u["basis"]
        pv, comm = self.cfg.point_value, self.cfg.commission
        self.cash += (fill - u["basis"]) * pv - comm
        pnl = u["banked"] + (fill - u["basis"]) * pv - 2 * comm
        self.trades.append((self.camp["id"], k, u["ets"], u["entry"], ts, fill, pnl, reason))
        if reason == "stop":
            self.camp["stopouts"] += 1

    def _run_stops(self, price, ts, gap):
        slip = self.cfg.slippage
        while self.heap:
            negs, k, uid = self.heap[0]
            u = self.units.get(k)
            if u is None or u["uid"] != uid:          # stale entry
                heapq.heappop(self.heap)
                continue
            s = -negs
            if s < price:
                break
            heapq.heappop(self.heap)
            self._sell(k, (price if gap else s) - slip, ts, "stop")

    def _buy_levels(self, a, top, ts, gap, gap_px):
        """buy every free level k >= 0 with a < L_k <= top (and below the target)."""
        tgt = self.target()
        cap = self.cfg.max_units
        for k in range(max(self.kidx(a) + 1, 0), self.kidx(top) + 1):
            lv = self.lvl(k)
            if lv >= tgt or (cap is not None and self.n_units >= cap):
                break
            if k not in self.units:
                self._buy(k, (gap_px if gap else lv) + self.cfg.slippage, ts)

    def _close_all(self, fill, ts, reason):
        for k in sorted(self.units, reverse=True):
            self._sell(k, fill, ts, reason)

    # ---------------- campaigns ----------------
    def _start(self, ts, fill):
        self.state = ACTIVE
        self.camp = dict(id=len(self.campaigns) + 1, start=ts, wave_high=self.H, wave_low=self.L,
                         pullback_pct=(1 - self.L / self.H) * 100, start_price=self.P0,
                         target=self.target(), cash0=self.cash, entries=0, stopouts=0, max_units=0)
        self._buy(0, fill, ts)

    def _end(self, ts, outcome):
        c = self.camp
        c.update(end=ts, outcome=outcome, pnl_usd=self.cash - c.pop("cash0"))
        self.campaigns.append(c)
        self.camp = None

    # ---------------- price moves ----------------
    def _up(self, a, b, ts, gap):
        if self.state == SEEK:
            if b > self.H:
                self.H = b
            return
        if self.state == ARMED:
            T = self.L + self.cfg.retrace * (self.H - self.L)
            if b < T:
                return
            self.P0 = T
            self._start(ts, (b if gap else T) + self.cfg.slippage)
            a = T
        # ACTIVE
        if b > self.H:
            self.H = b
        tgt = self.target()
        hit = b >= tgt
        if not (gap and hit):
            self._buy_levels(a, min(b, tgt), ts, gap, b)
        if hit:                                          # +12%: take profit and reset
            self._close_all(b if gap else tgt, ts, "target")
            self._end(ts, "+12% target")
            self.state = SEEK
            self.H = b

    def _down(self, a, b, ts, gap):
        if self.state == SEEK:
            if b <= self.H * (1.0 - self.cfg.pullback):
                self.state = ARMED
                self.L = b
            return
        if self.state == ARMED:
            if b < self.L:
                self.L = b
            return
        # ACTIVE
        self._run_stops(b, ts, gap)
        if b < self.L:                                   # selloff extended: cancel, re-anchor
            self._close_all(b - self.cfg.slippage, ts, "cancel")
            self._end(ts, "cancelled (new low)")
            self.state = ARMED
            self.L = b
        elif self.cfg.max_stopouts is not None and self.camp["stopouts"] >= self.cfg.max_stopouts:
            self._abandon(b, ts, "abandoned (stop-out limit)")

    def _abandon(self, price, ts, outcome):
        """give up on the campaign: sell what is left, wait for a fresh 5% pullback."""
        self._close_all(price - self.cfg.slippage, ts, "abandon")
        self._end(ts, outcome)
        self.state = SEEK
        self.H = price

    def bar(self, ts, o, h, l, c):
        if (self.camp is not None and self.cfg.max_days is not None
                and (ts - self.camp["start"]).total_seconds() > self.cfg.max_days * 86400):
            self._abandon(o, ts, "abandoned (time stop)")
        if o != self.prev:                               # gap / bar-to-bar jump
            if o > self.prev:
                self._up(self.prev, o, ts, True)
            else:
                self._down(self.prev, o, ts, True)
        if c >= o:                                       # O -> L -> H -> C
            if l < o:
                self._down(o, l, ts, False)
            if h > l:
                self._up(l, h, ts, False)
            if c < h:
                self._down(h, c, ts, False)
        else:                                            # O -> H -> L -> C
            if h > o:
                self._up(o, h, ts, False)
            if l < h:
                self._down(h, l, ts, False)
            if c > l:
                self._up(l, c, ts, False)
        self.prev = c

    def equity(self, price):
        return self.cash + (self.n_units * price - self.sum_basis) * self.cfg.point_value

    def rescale(self, r):
        """Year boundary in a continuous run: the next year's NQ series sits at a
        different level (new front-month basis, carry reset).  Treat it like a
        futures roll: bank open P&L, multiply every price level by r."""
        pv = self.cfg.point_value
        for u in self.units.values():
            booked = (self.prev - u["basis"]) * pv
            u["banked"] += booked
            self.cash += booked
            u["basis"] = self.prev * r
            u["entry"] *= r
            u["stop"] *= r
        self.sum_basis = sum(u["basis"] for u in self.units.values())
        self.heap = [(-u["stop"], k, u["uid"]) for k, u in self.units.items()]
        heapq.heapify(self.heap)
        self.H *= r
        if self.L is not None:
            self.L *= r
        if self.P0 is not None:
            self.P0 *= r
        self.prev *= r

    def finish(self, ts, price, outcome="open at end"):
        """Close everything at `price` (market) and log the running campaign."""
        if self.camp is not None:
            self._close_all(price - self.cfg.slippage, ts, "end")
            self._end(ts, outcome)


def run_segments(segments, cfg: RecoveryConfig, ratios=None):
    """Run one strategy instance over consecutive yearly bar segments.
    ratios[i] rescales the state before segment i (continuous mode); pass None
    to run every segment as an independent year instead (fresh start each January,
    everything closed at the December close)."""
    eq_parts, unit_parts, year_pnl, trades, camps = [], [], {}, [], []
    eng, offset = None, 0.0
    for i, bars in enumerate(segments):
        O, Hh, Ll, C = (bars[c].to_numpy(float) for c in ("open", "high", "low", "close"))
        ts = bars.index
        if eng is None or ratios is None:
            if eng is not None:                          # independent years: bank and restart
                offset += eng.cash
                trades += eng.trades
                camps += eng.campaigns
            eng = RecoveryPyramid(cfg, O[0])
        else:
            eng.rescale(ratios[i])
        start_eq = eng.equity(eng.prev)
        eq = np.empty(len(O))
        un = np.empty(len(O), dtype=np.int32)
        for j in range(len(O)):
            eng.bar(ts[j], O[j], Hh[j], Ll[j], C[j])
            eq[j] = eng.equity(C[j])
            un[j] = eng.n_units
        last = i == len(segments) - 1
        if ratios is None or last:
            eng.finish(ts[-1], C[-1], "open at end" if last else "closed at year end")
            eq[-1] = eng.equity(C[-1])
        year_pnl[ts[0].year] = eq[-1] - start_eq
        eq_parts.append(pd.Series(eq + offset, index=ts))
        unit_parts.append(pd.Series(un, index=ts))
    trades += eng.trades
    camps += eng.campaigns
    tr = pd.DataFrame(trades, columns=["campaign", "level", "entry_time", "entry", "exit_time",
                                       "exit", "pnl_usd", "reason"])
    cp = pd.DataFrame(camps)
    if len(cp):
        cp["id"] = range(1, len(cp) + 1)
    return dict(equity=pd.concat(eq_parts), units=pd.concat(unit_parts), year_pnl=year_pnl,
                trades=tr, campaigns=cp)


if __name__ == "__main__":
    idx = pd.date_range("2024-01-02 14:30", periods=8, freq="min", tz="UTC")
    z = dict(slippage=0, commission=0, point_value=1)

    def bars(rows):
        return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx[:len(rows)])

    # 1) 6% pullback 100 -> 94, entry at 98.2, pyramid to the +12% target
    r = run_segments([bars([(100, 100, 100, 100), (100, 100, 94, 94), (94, 110, 94, 110)])],
                     RecoveryConfig(**z))
    P0, tgt = 98.2, 98.2 * 1.12
    exp = sum(tgt - P0 * 1.01 ** k for k in range(12))
    c = r["campaigns"].iloc[0]
    assert c.outcome == "+12% target" and abs(c.start_price - P0) < 1e-9, c
    assert abs(c.pnl_usd - exp) < 1e-6 and c.max_units == 12, (c.pnl_usd, exp, c.max_units)
    # 2) cancel: entry 98.2, unit stopped at 97.218, new low 93 -> new start 97.9
    r = run_segments([bars([(100, 100, 100, 100), (100, 100, 94, 94), (94, 99, 94, 99),
                            (99, 99, 93, 93), (93, 98, 93, 98)])], RecoveryConfig(**z))
    cp = r["campaigns"]
    assert list(cp.outcome) == ["cancelled (new low)", "open at end"], cp
    assert abs(cp.pnl_usd.iloc[0] - (98.2 * 0.99 - 98.2)) < 1e-9
    assert abs(cp.start_price.iloc[1] - (93 + 0.7 * 7)) < 1e-9
    # 3) a 4.8% dip never arms a wave
    r = run_segments([bars([(100, 104, 96, 104), (104, 104, 99, 99)])], RecoveryConfig(**z))
    assert r["campaigns"].empty and r["trades"].empty
    # 4) stop-out limit: after 1 stop-out the campaign is abandoned (no re-entry at 98.2)
    r = run_segments([bars([(100, 100, 100, 100), (100, 100, 94, 94), (94, 99, 94, 99),
                            (99, 99, 96, 96), (96, 99, 96, 99)])], RecoveryConfig(max_stopouts=1, **z))
    assert list(r["campaigns"].outcome) == ["abandoned (stop-out limit)"], r["campaigns"]
    assert len(r["trades"]) == 1
    # 5) unit cap: only 3 contracts even though price runs to the target
    r = run_segments([bars([(100, 100, 100, 100), (100, 100, 94, 94), (94, 110, 94, 110)])],
                     RecoveryConfig(max_units=3, **z))
    assert r["campaigns"].iloc[0].max_units == 3
    print("self-checks passed")
