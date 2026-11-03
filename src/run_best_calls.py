"""The chosen version (recovery: 5% pullback, 70% entry, +20% reset, 1% step/stop) sized at
$100k of NQ per unit (no reinvestment), with and without 20-delta covered calls.

Calls are sold 1 per contract held (fractional, like the futures), priced with Black-76 from
VXN (options_overlay.py), with the option-price stress test at 0.8 / 0.9 / 1.0 x VXN.

Usage:
    python3 -I src/run_best_calls.py --dukascopy ... --histdata ... --hf ... --yahoo ... --out results
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from long_history import load_segments  # noqa: E402
from nq_series import load_yahoo  # noqa: E402
from options_overlay import CallConfig, VolSurface, overlay  # noqa: E402
from recovery_backtest import RecoveryConfig, run_segments  # noqa: E402

YEARS = list(range(2008, 2027))
CALLS = [("no calls", None),
         ("sell 20-delta 30-day calls", dict(strike="delta", delta=0.20, days=30)),
         ("sell 20-delta 7-day calls", dict(strike="delta", delta=0.20, days=7))]


def metrics(eq, year_pnl):
    peak = eq.cummax()
    dd = eq - peak
    t1 = dd.idxmin()
    t0 = eq.loc[:t1].idxmax()
    years = (eq.index[-1] - eq.index[0]).total_seconds() / (365.25 * 86400)
    yr = pd.Series(year_pnl)
    avg = yr.sum() / years
    return dict(total=yr.sum(), avg_per_year=avg, max_drawdown=dd.min(), dd_peak=t0.date(), dd_trough=t1.date(),
                calmar=avg / -dd.min(), yearly_mean_over_std=yr.mean() / yr.std(), worst_year=yr.min(),
                losing_years=int((yr < 0).sum()))


def main():
    ap = argparse.ArgumentParser()
    for k in ("dukascopy", "histdata", "hf", "yahoo"):
        ap.add_argument(f"--{k}", required=True)
    ap.add_argument("--out", default="results")
    ap.add_argument("--name", default="best_calls")
    ap.add_argument("--unit", type=float, default=100_000.0)
    ap.add_argument("--pullback", type=float, default=0.05)
    ap.add_argument("--retrace", type=float, default=0.70)
    ap.add_argument("--take-profit", type=float, default=0.20)
    a = ap.parse_args()
    out = os.path.join(a.out, a.name)
    os.makedirs(out, exist_ok=True)
    t0 = time.time()

    segments, metas, ctx = load_segments(YEARS, a.dukascopy, a.histdata, a.hf, a.yahoo)
    cfg = RecoveryConfig(pullback=a.pullback, retrace=a.retrace, take_profit=a.take_profit,
                         unit_notional=a.unit)
    res = run_segments(segments, cfg, None)
    tr = res["trades"]
    print(f"strategy done ({time.time()-t0:.0f}s): {cfg.label()}, ${a.unit:,.0f} per unit, "
          f"{len(tr)} unit trades", flush=True)
    vxn = load_yahoo(a.yahoo, "VXN")["close"]
    irx = ctx["irx"]["close"]

    rows, by_year, curves = [], {}, {}
    for name, kw in CALLS:
        for ratio in ((None,) if kw is None else (0.80, 0.90, 1.00)):
            if kw is None:
                eq, ypnl, opt_total, opt_cost, n_calls = res["equity"], dict(res["year_pnl"]), 0.0, 0.0, 0
            else:
                ccfg = CallConfig(vxn_to_atm=ratio, **kw)
                o = overlay(tr, segments, VolSurface(vxn, irx, ccfg), ccfg)
                usd = o.option_pnl_usd * tr.contracts                    # same size as the futures
                cost = o.option_cost_usd * tr.contracts
                exit_t = pd.to_datetime(tr.exit_time)
                yr_opt = usd.groupby(exit_t.dt.year).sum()
                ypnl = {y: res["year_pnl"][y] + yr_opt.get(y, 0.0) for y in YEARS}
                steps = usd.groupby(exit_t).sum().sort_index()
                eq = res["equity"] + steps.reindex(res["equity"].index, fill_value=0.0).cumsum()
                opt_total, opt_cost, n_calls = float(usd.sum()), float(cost.sum()), int(o.calls_sold.sum())
            m = metrics(eq, ypnl)
            label = name if kw is None else f"{name} @ {ratio:.1f} x VXN"
            rows.append(dict(version=label, overlay=name, vol_vs_vxn=ratio, option_pnl=opt_total,
                             option_costs=opt_cost, calls_sold=n_calls, **m))
            if kw is None or ratio == 0.90:
                by_year[name] = pd.Series(ypnl)
                curves[name] = eq.resample("1D").last().dropna()
            print(f"  {label:45s} avg/yr {m['avg_per_year']:>9,.0f}  max DD {m['max_drawdown']:>10,.0f}  "
                  f"Calmar {m['calmar']:.2f}  ({time.time()-t0:.0f}s)", flush=True)
    pd.DataFrame(rows).round(2).to_csv(os.path.join(out, "summary.csv"), index=False)
    pd.DataFrame(by_year).round(0).to_csv(os.path.join(out, "by_year.csv"), index_label="year")
    pd.DataFrame(curves).to_csv(os.path.join(out, "equity_daily.csv"), float_format="%.0f")
    tr.to_csv(os.path.join(out, "trades.csv"), index=False, float_format="%.4f")
    print("done")


if __name__ == "__main__":
    main()
