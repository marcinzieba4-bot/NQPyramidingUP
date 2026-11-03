"""Fixed-notional comparison of every version: 1 unit = $100k of NQ at the start of each run,
no reinvestment.  Ranks versions by Calmar (average yearly profit / worst drawdown).

With 1 NQ contract per unit (the earlier tables) the dollar size of a 1% move grew ~20x from
2009 to 2026 because the index did, so recent drawdowns dwarfed early profits.  Here every run
(each January for the all-year pyramid, each campaign for the recovery / breakout versions)
is sized so one unit is worth `--unit` dollars at its starting price; fractional contracts and
costs are scaled to match.

Usage:
    python3 -I src/run_sizing.py --dukascopy ... --histdata ... --hf ... --yahoo ... --out results
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from breakout_backtest import BreakoutConfig, run_breakout  # noqa: E402
from long_history import boundary_ratios, load_segments  # noqa: E402
from pyramid_backtest import Config, run  # noqa: E402
from recovery_backtest import RecoveryConfig, run_segments  # noqa: E402

YEARS = list(range(2008, 2027))
UNIT = 100_000.0

R = "recovery"
CANDIDATES = [
    ("Buy & hold ($100k each January)", "bh", {}),
    ("Pyramid from the January open (D)", "D", {}),
    ("Recovery, entry 20%", R, dict(retrace=0.20)),
    ("Recovery, entry 30%", R, dict(retrace=0.30)),
    ("Recovery, entry 40%", R, dict(retrace=0.40)),
    ("Recovery, entry 50%", R, dict(retrace=0.50)),
    ("Recovery, entry 61.8%", R, dict(retrace=0.618)),
    ("Recovery, entry 70% (base)", R, {}),
    ("Recovery, entry 80%", R, dict(retrace=0.80)),
    ("Recovery 70%, reset +16%", R, dict(take_profit=0.16)),
    ("Recovery 70%, reset +20%", R, dict(take_profit=0.20)),
    ("Recovery 70%, no reset", R, dict(take_profit=None)),
    ("Recovery 70%, 8% pullback", R, dict(pullback=0.08)),
    ("Recovery 61.8%, reset +16%", R, dict(retrace=0.618, take_profit=0.16)),
    ("Recovery 61.8%, reset +20%", R, dict(retrace=0.618, take_profit=0.20)),
    ("Recovery 50%, reset +20%", R, dict(retrace=0.50, take_profit=0.20)),
    ("Breakout as specified (3% / +5% / 0.5%)", "brk", {}),
    ("Breakout, 8% pullback, +4% target", "brk", dict(pullback=0.08, take_profit=0.04)),
]

_W = {}


def _init(paths):
    """worker: load the yearly segments once."""
    from run_breakout import level_factors, refs_for
    segments, metas, _ = load_segments([2007] + YEARS, *paths)
    ratios = boundary_ratios(metas)
    factors = level_factors(ratios)
    _W["segs"], _W["metas"] = segments[1:], metas[1:]
    _W["refs"] = {p: refs_for(segments, factors, p)[1:] for p in (0.03, 0.08)}


def _run(job):
    name, kind, kw = job
    segs, metas = _W["segs"], _W["metas"]
    t = time.time()
    camp_worst, units_max, in_mkt = np.nan, 1, np.nan
    if kind == "bh":
        parts, off, yp = [], 0.0, {}
        for b, m in zip(segs, metas):
            e = (b["close"] / m["P0"] - 1.0) * UNIT + off
            yp[m["year"]] = e.iloc[-1] - off
            off = e.iloc[-1]
            parts.append(e)
        eq = pd.concat(parts)
    elif kind == "D":
        parts, off, yp, umax = [], 0.0, {}, 0
        for b, m in zip(segs, metas):
            r = run(b, Config(core=False, ladder_below_start=False, unit_notional=UNIT))
            parts.append(r.equity + off)
            yp[m["year"]] = r.equity.iloc[-1]
            off += r.equity.iloc[-1]
            umax = max(umax, int(r.units.max()))
        eq, units_max = pd.concat(parts), umax
    else:
        if kind == R:
            res = run_segments(segs, RecoveryConfig(unit_notional=UNIT, **kw), None)
        else:
            cfg = BreakoutConfig(unit_notional=UNIT, **kw)
            res = run_breakout(segs, _W["refs"][cfg.pullback], cfg, None)
        eq, yp = res["equity"], {y: float(v) for y, v in res["year_pnl"].items()}
        units_max = int(res["units"].max())
        in_mkt = float((res["units"] > 0).mean()) * 100
        if len(res["campaigns"]):
            camp_worst = float(res["campaigns"].pnl_usd.min())
    peak = eq.cummax()
    dd = eq - peak
    t_low = dd.idxmin()
    t_peak = eq.loc[:t_low].idxmax()
    years = (eq.index[-1] - eq.index[0]).total_seconds() / (365.25 * 86400)
    yr = pd.Series(yp)
    row = dict(version=name, total=yr.sum(), avg_per_year=yr.sum() / years, max_drawdown=dd.min(),
               dd_peak=t_peak.date(), dd_trough=t_low.date(), worst_year=yr.min(), best_year=yr.max(),
               losing_years=int((yr < 0).sum()), early_2008_2021=yr[yr.index <= 2021].sum(),
               recent_2022_2026=yr[yr.index >= 2022].sum(), worst_campaign=camp_worst,
               max_units=units_max, time_in_market_pct=in_mkt)
    row["calmar"] = row["avg_per_year"] / -row["max_drawdown"] if row["max_drawdown"] < 0 else np.nan
    row.update({str(y): v for y, v in yp.items()})
    daily = eq.resample("1D").last().dropna()
    return row, name, daily, time.time() - t


def main():
    ap = argparse.ArgumentParser()
    for k in ("dukascopy", "histdata", "hf", "yahoo"):
        ap.add_argument(f"--{k}", required=True)
    ap.add_argument("--out", default="results")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    out = os.path.join(a.out, "sizing")
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    rows, curves = [], {}
    with ProcessPoolExecutor(a.workers, initializer=_init,
                             initargs=((a.dukascopy, a.histdata, a.hf, a.yahoo),)) as ex:
        for row, name, daily, secs in ex.map(_run, CANDIDATES):
            rows.append(row)
            curves[name] = daily
            print(f"{name:45s} avg/yr {row['avg_per_year']:>10,.0f}  max DD {row['max_drawdown']:>10,.0f}  "
                  f"Calmar {row['calmar']:.2f}  ({secs:.0f}s, {time.time()-t0:.0f}s total)", flush=True)
    from nq_series import load_yahoo
    nqf = load_yahoo(a.yahoo, "NQ_F")
    last = nqf.loc[:pd.Timestamp(max(curves[next(iter(curves))].index).date()), "close"].iloc[-1]
    pd.DataFrame([dict(unit_usd=UNIT, last_nq_price=last, mnq_notional_usd=last * 2.0,
                       nq_notional_usd=last * 20.0)]).to_csv(os.path.join(out, "meta.csv"), index=False)
    df = pd.DataFrame(rows).sort_values("calmar", ascending=False)
    df.round(2).to_csv(os.path.join(out, "calmar_100k_per_unit.csv"), index=False)
    pd.DataFrame(curves).to_csv(os.path.join(out, "equity_daily_100k_per_unit.csv"), float_format="%.0f")
    print("done")


if __name__ == "__main__":
    main()
