"""Breakout pyramid: start when NQ beats its 1-year high after a pullback of >= 3%.

Rules (defaults):
  1. Reference: the 1-year high H (highest price of the previous 365 days, on the
     rolled NQ price path, history before January included).
  2. Setup: price has been at least 3% below H since H was made.
  3. Entry: when price then trades above H, buy 1 unit at H (buy-stop).  Starting
     point P0 = H.
  4. Pyramid: +1 unit every +0.5% above P0 (P0 x 1.005^k); each unit stopped 0.5%
     below its own entry and bought again if price climbs back through its level.
  5. Target: at P0 x 1.05 sell everything (limit) and start over: a new 3% pullback
     from the 1-year high is needed before the next entry.
  6. Cancel: if price falls 3% below the (1-year) high again before the target, sell
     what is left; the next break of the 1-year high is the new starting point.

Fills, costs and year handling are those of recovery_backtest.py.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nq_series import ET  # noqa: E402
from recovery_backtest import ACTIVE, ARMED, SEEK, RecoveryPyramid  # noqa: E402


@dataclass
class BreakoutConfig:
    pullback: float = 0.03
    take_profit: float | None = 0.05
    step: float = 0.005
    stop: float = 0.005
    lookback_days: int = 365
    slippage: float = 0.5
    commission: float = 2.50
    point_value: float = 20.0
    max_units: int | None = None
    max_stopouts: int | None = None      # (interface of RecoveryPyramid; unused)
    max_days: float | None = None
    unit_notional: float | None = None

    def label(self):
        tp = "none" if self.take_profit is None else f"{self.take_profit*100:g}%"
        return (f"1-year-high breakout after {self.pullback*100:g}% pullback, target {tp}, "
                f"step {self.step*100:g}%, stop {self.stop*100:g}%")


def session_days(index):
    """trading-session date (session opens 18:00 ET the evening before) as int day number."""
    d = (index.tz_convert(ET) + pd.Timedelta(hours=6)).normalize().tz_localize(None)
    return (d.values.astype("datetime64[D]").astype(np.int64))


def daily_references(segments, factors, pullback, lookback_days=365):
    """For every session day: the 1-year high of the *previous* days and whether price has
    been >= pullback below it since it was made.  Computed on the chain-linked series
    (segment prices x factor), returned in linked units: {day: (H_prev, pulled_back)}."""
    frames = []
    for seg, f in zip(segments, factors):
        d = session_days(seg.index)
        g = pd.DataFrame({"d": d, "h": seg["high"].values * f, "l": seg["low"].values * f})
        frames.append(g.groupby("d").agg(h=("h", "max"), l=("l", "min")))
    daily = pd.concat(frames).groupby(level=0).agg(h=("h", "max"), l=("l", "min")).sort_index()
    days, hi, lo = daily.index.values, daily.h.values, daily.l.values
    out, start = {}, 0
    for i in range(len(days)):
        while days[start] < days[i] - lookback_days:
            start += 1
        if i == start:
            continue
        w = hi[start:i]
        j = start + int(len(w) - 1 - np.argmax(w[::-1]))      # latest day with the max
        H = hi[j]
        pb = bool(i > j + 1 and lo[j + 1:i].min() <= H * (1 - pullback))
        out[int(days[i])] = (float(H), pb)
    return out


class BreakoutPyramid(RecoveryPyramid):
    def __init__(self, cfg: BreakoutConfig, first_price, H0, pb0):
        super().__init__(cfg, first_price)
        self.H = H0
        self.state = ARMED if pb0 else SEEK
        self.day = None

    def new_day(self, H_prev, pb_prev):
        if self.state == ACTIVE:
            return
        if H_prev < self.H * (1 - 1e-9):          # an old high left the 1-year window
            self.H = H_prev
            self.state = ARMED if pb_prev else SEEK
        elif pb_prev:
            self.state = ARMED

    def _start(self, ts, fill):
        self._size_run()
        self.state = ACTIVE
        self.camp = dict(id=len(self.campaigns) + 1, start=ts, breakout_level=self.P0,
                         target=self.target(), cash0=self.cash, entries=0, stopouts=0, max_units=0)
        self._buy(0, fill, ts)

    def _up(self, a, b, ts, gap):
        if self.state != ACTIVE:
            if b <= self.H:
                return
            if self.state == SEEK:                 # new high without a prior 3% pullback
                self.H = b
                return
            self.P0 = self.H                       # ARMED and breaking the 1-year high
            self._start(ts, (b if gap else self.P0) + self.cfg.slippage)
            a = self.P0
        if b > self.H:
            self.H = b
        tgt = self.target()
        hit = b >= tgt
        if not (gap and hit):
            self._buy_levels(a, min(b, tgt), ts, gap, b)
        if hit:
            self._close_all(b if gap else tgt, ts, "target")
            self._end(ts, "target")
            self.state = SEEK
            self.H = max(self.H, b)

    def _down(self, a, b, ts, gap):
        lvl = self.H * (1.0 - self.cfg.pullback)
        if self.state == SEEK:
            if b <= lvl:
                self.state = ARMED
            return
        if self.state == ARMED:
            return
        self._run_stops(b, ts, gap)
        if b <= lvl:                               # new 3% pullback: cancel
            self._close_all((b if gap else lvl) - self.cfg.slippage, ts, "cancel")
            self._end(ts, "cancelled (new pullback)")
            self.state = ARMED


def run_breakout(segments, refs_by_year, cfg: BreakoutConfig, ratios=None):
    """refs_by_year[i]: {day: (H_prev, pulled_back)} in segment i's own price scale."""
    eq_parts, unit_parts, year_pnl, trades, camps = [], [], {}, [], []
    eng, offset = None, 0.0
    for i, bars in enumerate(segments):
        O, Hh, Ll, C = (bars[c].to_numpy(float) for c in ("open", "high", "low", "close"))
        ts, days, refs = bars.index, session_days(bars.index), refs_by_year[i]
        H0, pb0 = refs[int(days[0])]
        if eng is None or ratios is None:
            if eng is not None:
                offset += eng.cash
                trades += eng.trades
                camps += eng.campaigns
            eng = BreakoutPyramid(cfg, O[0], H0, pb0)
        else:
            eng.rescale(ratios[i])
        start_eq = eng.equity(eng.prev)
        eq = np.empty(len(O))
        un = np.empty(len(O), dtype=np.int32)
        for j in range(len(O)):
            if days[j] != eng.day:
                eng.day = days[j]
                ref = refs.get(int(days[j]))
                if ref is not None:
                    eng.new_day(*ref)
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
                                       "exit", "pnl_usd", "reason", "contracts"])
    cp = pd.DataFrame(camps)
    if len(cp):
        cp["id"] = range(1, len(cp) + 1)
    return dict(equity=pd.concat(eq_parts), units=pd.concat(unit_parts), year_pnl=year_pnl,
                trades=tr, campaigns=cp)


if __name__ == "__main__":
    z = dict(slippage=0, commission=0, point_value=1)
    idx = pd.date_range("2024-03-04 15:00", periods=6, freq="1D", tz="UTC")

    def bars(rows):
        return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx[:len(rows)])

    def refs_for(b, H0, pb0):
        return {int(d): (H0, pb0) for d in session_days(b.index)}

    # 1) armed (pulled back), breaks 100 -> pyramid 0.5% steps to the +5% target at 105
    b = bars([(98, 98, 98, 98), (98, 106, 98, 106)])
    r = run_breakout([b], [refs_for(b, 100.0, True)], BreakoutConfig(**z))
    c = r["campaigns"].iloc[0]
    exp = sum(105 - 100 * 1.005 ** k for k in range(10))
    assert c.outcome == "target" and c.max_units == 10 and abs(c.pnl_usd - exp) < 1e-6, (c, exp)
    # 2) not pulled back: a new high only moves the reference, no trade
    b = bars([(99, 99, 99, 99), (99, 106, 99, 106)])
    r = run_breakout([b], [refs_for(b, 100.0, False)], BreakoutConfig(**z))
    assert r["campaigns"].empty
    # 3) breakout then a new 3% pullback from the high cancels; next break re-enters at the high
    b = bars([(98, 98, 98, 98), (98, 101, 98, 101), (101, 101, 97.9, 97.9), (97.9, 101.5, 97.9, 101.5)])
    days = session_days(b.index)
    refs = {int(days[0]): (100.0, True), int(days[1]): (100.0, True),
            int(days[2]): (101.0, False), int(days[3]): (101.0, True)}   # as daily_references would give
    r = run_breakout([b], [refs], BreakoutConfig(**z))
    cp = r["campaigns"]
    assert list(cp.outcome)[:1] == ["cancelled (new pullback)"], cp
    assert abs(cp.breakout_level.iloc[1] - 101.0) < 1e-9, cp
    # 4) daily_references: window max of previous days and the pullback flag
    seg = pd.DataFrame({"open": [100, 103, 99, 101], "high": [100, 103, 99, 101], "low": [100, 103, 99, 101],
                        "close": [100, 103, 99, 101]}, index=idx[:4])
    ref = daily_references([seg], [1.0], 0.03)
    d = session_days(seg.index)
    assert ref[int(d[1])] == (100.0, False) and ref[int(d[2])] == (103.0, False)
    assert ref[int(d[3])] == (103.0, True), ref       # 99 <= 0.97 * 103
    print("self-checks passed")
