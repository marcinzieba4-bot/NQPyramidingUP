"""Event-driven backtest of an "add 1 unit every +1%, stop each unit -1%" pyramid.

Rules (defaults = the strategy as specified):
  * Start of the year: buy 1 unit at the first price (P0).
  * Grid levels L_k = P0 * (1 + step)^k.  Every time price trades UP through a
    level that has no open unit, buy 1 unit there (buy-stop order).  "After 1%
    up you increase by 1 unit" -> each new unit is 1% above the previous one.
  * Each added unit has its own protective stop at entry * (1 - stop).
    When hit, only that unit is sold.  If price later climbs back through the
    level, the unit is bought again (this is where whipsaw losses come from).
  * End of the period: everything still open is sold.

Two switches cover the parts the plain-English rule leaves open:
  core=True               the first unit is a core position with NO stop
                          (held Jan -> Dec).  core=False: the first unit is an
                          ordinary grid unit at level 0 with a 1% stop.
  ladder_below_start      False: add-ons only above the January start price.
                          True : add-ons on every +1% step at any price, incl.
                          rebounds from below the start price.

Fills (1-minute bars, conservative where ambiguous):
  * intrabar path: up bar  O -> L -> H -> C ; down bar  O -> H -> L -> C
  * stop / buy-stop crossed inside a bar  -> filled at the trigger price
  * market gaps through a trigger (bar opens beyond it) -> filled at the open
  * every fill pays `slippage` points against us + `commission` USD per side
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field, asdict

import numpy as np
import pandas as pd


@dataclass
class Config:
    step: float = 0.01              # add a unit after every +1% (geometric grid)
    stop: float = 0.01              # each added unit is stopped 1% below its entry
    core: bool = True               # first unit held all period, no stop
    ladder_below_start: bool = False
    slippage: float = 0.5           # NQ points per side (2 ticks)
    commission: float = 2.50        # USD per contract per side
    point_value: float = 20.0       # NQ = $20/pt (MNQ = $2/pt)
    max_ladder: int | None = None   # optional cap on simultaneously open add-ons
    name: str = ""

    def label(self):
        return self.name or (
            f"{'core' if self.core else 'nocore'}_"
            f"{'all' if self.ladder_below_start else 'above'}_"
            f"s{self.step*100:g}_x{self.stop*100:g}")


@dataclass
class Result:
    config: Config
    trades: pd.DataFrame
    equity: pd.Series                 # USD, marked at every 1-min close
    units: pd.Series                  # contracts held at every 1-min close
    stats: dict = field(default_factory=dict)


def run(bars: pd.DataFrame, cfg: Config) -> Result:
    """bars: DataFrame indexed by UTC timestamp with open/high/low/close (NQ pts).
    The first bar's open is the entry price P0; the last bar's close is the exit."""
    ts = bars.index
    O = bars["open"].to_numpy(float)
    H = bars["high"].to_numpy(float)
    L = bars["low"].to_numpy(float)
    C = bars["close"].to_numpy(float)
    n = len(O)
    pv, slip, comm = cfg.point_value, cfg.slippage, cfg.commission
    g = math.log1p(cfg.step)
    P0 = O[0]

    def lvl(k):
        return P0 * math.exp(g * k)

    def kidx(p):                       # highest k with L_k <= p
        k = math.floor(math.log(p / P0) / g)
        if lvl(k + 1) <= p:            # guard float rounding
            k += 1
        elif lvl(k) > p:
            k -= 1
        return k

    k_floor = -10**9 if cfg.ladder_below_start else (1 if cfg.core else 0)
    cap = cfg.max_ladder

    open_units: dict[int, list] = {}   # k -> [entry, stop, entry_i]
    heap: list = []                    # (-stop, k, entry_i) max-heap of stops
    trades = []
    cash = 0.0                         # realised USD incl. costs
    core_entry = None
    agg = [0, 0.0]                     # open ladder units: count, sum of entries

    def buy(k, fill, i):
        nonlocal cash
        stop_px = fill * (1.0 - cfg.stop)
        open_units[k] = [fill, stop_px, i]
        heapq.heappush(heap, (-stop_px, k, i))
        agg[0] += 1
        agg[1] += fill
        cash -= comm

    def sell(k, fill, i, reason):
        nonlocal cash
        entry, stop_px, ei = open_units.pop(k)
        agg[0] -= 1
        agg[1] -= entry
        pnl_pts = fill - entry
        cash += pnl_pts * pv - comm
        trades.append((k, ts[ei], entry, ts[i], fill, pnl_pts,
                       pnl_pts * pv - 2 * comm, reason))

    def run_stops(price, i, gap):
        # sell every unit whose stop is >= price (highest stop first)
        while heap:
            negs, k, ei = heap[0]
            u = open_units.get(k)
            if u is None or u[2] != ei:            # stale heap entry
                heapq.heappop(heap)
                continue
            s = -negs
            if s < price:
                break
            heapq.heappop(heap)
            fill = (price if gap else s) - slip
            sell(k, fill, i, "stop")

    def run_buys(p_from, p_to, i, gap):
        # buy every free level in (p_from, p_to]
        ka, kb = kidx(p_from), kidx(p_to)
        for k in range(max(ka + 1, k_floor), kb + 1):
            if cap is not None and agg[0] >= cap:
                break
            if k not in open_units:
                fill = (p_to if gap else lvl(k)) + slip
                buy(k, fill, i)

    # ---- initial position -------------------------------------------------
    if cfg.core:
        core_entry = P0 + slip
        cash -= comm
    else:
        buy(0, P0 + slip, 0)

    eq = np.empty(n)
    un = np.empty(n, dtype=np.int32)
    prev = O[0]
    for i in range(n):
        o, h, l, c = O[i], H[i], L[i], C[i]
        # gap / bar-to-bar jump
        if i > 0 and o != prev:
            if o < prev:
                run_stops(o, i, gap=True)
            else:
                run_buys(prev, o, i, gap=True)
        if c >= o:                       # O -> L -> H -> C
            if l < o:
                run_stops(l, i, gap=False)
            if h > l:
                run_buys(l, h, i, gap=False)
            if c < h:
                run_stops(c, i, gap=False)
        else:                            # O -> H -> L -> C
            if h > o:
                run_buys(o, h, i, gap=False)
            if l < h:
                run_stops(l, i, gap=False)
            if c > l:
                run_buys(l, c, i, gap=False)
        prev = c
        mtm = agg[0] * c - agg[1]
        if core_entry is not None:
            mtm += c - core_entry
        eq[i] = cash + mtm * pv
        un[i] = agg[0] + (1 if core_entry is not None else 0)

    # ---- close everything at the final close -------------------------------
    last = n - 1
    exit_px = C[last] - slip
    for k in sorted(open_units, reverse=True):
        sell(k, exit_px, last, "end")
    core_pnl_pts = None
    if core_entry is not None:
        core_pnl_pts = exit_px - core_entry
        cash += core_pnl_pts * pv - comm
        trades.append(("core", ts[0], core_entry, ts[last], exit_px, core_pnl_pts,
                       core_pnl_pts * pv - 2 * comm, "end"))
    eq[last] = cash

    tr = pd.DataFrame(trades, columns=["level", "entry_time", "entry", "exit_time",
                                       "exit", "pnl_pts", "pnl_usd", "reason"])
    equity = pd.Series(eq, index=ts, name="equity_usd")
    units = pd.Series(un, index=ts, name="units")
    res = Result(cfg, tr, equity, units)
    res.stats = summarize(res, bars)
    return res


def summarize(res: Result, bars: pd.DataFrame) -> dict:
    tr, eq, cfg = res.trades, res.equity, res.config
    P0, Pend = bars["open"].iloc[0], bars["close"].iloc[-1]
    core = tr[tr.level.astype(str) == "core"]
    lad = tr[tr.level.astype(str) != "core"]
    stops = lad[lad.reason == "stop"]
    held = lad[lad.reason == "end"]
    peak = eq.cummax()
    dd = eq - peak
    i_dd = dd.idxmin()
    bh = (Pend - P0) * cfg.point_value
    return {
        "variant": cfg.label(),
        "start": bars.index[0], "end": bars.index[-1],
        "P0": round(P0, 2), "P_end": round(Pend, 2),
        "price_chg_pct": round((Pend / P0 - 1) * 100, 2),
        "buy_hold_1u_usd": round(bh, 0),
        "total_pnl_usd": round(eq.iloc[-1], 0),
        "core_pnl_usd": round(core.pnl_usd.sum(), 0),
        "ladder_pnl_usd": round(lad.pnl_usd.sum(), 0),
        "ladder_entries": int(len(lad)),
        "stopouts": int(len(stops)),
        "stopout_loss_usd": round(stops.pnl_usd.sum(), 0),
        "stopout_avg_usd": round(stops.pnl_usd.mean(), 0) if len(stops) else 0.0,
        "winning_stopouts": int((stops.pnl_usd > 0).sum()),
        "units_held_at_end": int(len(held) + len(core)),
        "held_units_pnl_usd": round(held.pnl_usd.sum() + core.pnl_usd.sum(), 0),
        "max_units": int(res.units.max()),
        "max_notional_usd": round(float((res.units * bars["close"]).max() * cfg.point_value), 0),
        "max_drawdown_usd": round(dd.min(), 0),
        "max_dd_time": i_dd,
        "peak_equity_usd": round(peak.max(), 0),
        "min_equity_usd": round(eq.min(), 0),
        "pnl_vs_buy_hold_x": round(eq.iloc[-1] / bh, 2) if bh else np.nan,
    }


if __name__ == "__main__":
    # tiny self-checks on synthetic paths
    idx = pd.date_range("2024-01-02 14:30", periods=6, freq="min", tz="UTC")

    def mk(path):
        p = np.array(path, float)
        return pd.DataFrame({"open": p, "high": p, "low": p, "close": p}, index=idx[:len(p)])

    z = dict(slippage=0, commission=0, point_value=1)
    # straight up 3%: core + units at 101, 102.01, 103.0301
    r = run(mk([100, 101, 102.01, 103.0301, 103.0301]), Config(**z))
    assert r.stats["units_held_at_end"] == 4, r.stats
    exp = (103.0301 - 100) + (103.0301 - 101) + (103.0301 - 102.01) + 0
    assert abs(r.stats["total_pnl_usd"] - round(exp)) <= 1, (r.stats, exp)
    # whipsaw: up to 101 (buy), down to 99.98 (stop at 99.99), back to 101 (buy)
    r = run(mk([100, 101, 99.98, 101, 101]), Config(**z))
    assert r.stats["stopouts"] == 1 and r.stats["ladder_entries"] == 2, r.trades
    # no-core variant: first unit stopped at 99
    r = run(mk([100, 98.9, 98.0, 97.0]), Config(core=False, **z))
    assert r.stats["stopouts"] == 1 and r.stats["units_held_at_end"] == 0, r.trades
    print("self-checks passed")
