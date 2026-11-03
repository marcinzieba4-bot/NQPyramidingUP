"""Run the NQ pyramid backtest for each calendar year 2022-2026 (2026 = YTD).

Usage:
    python3 -I src/run_backtests.py --cfd DATA/nas100_1min_mid.csv.gz --yahoo DATA/yahoo --out results
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nq_series import (load_inputs, build_year_calibrated, rolled_nq_points,  # noqa: E402
                       cfd_at_close, ET)
from pyramid_backtest import Config, run  # noqa: E402

YEARS = [2022, 2023, 2024, 2025, 2026]

VARIANTS = {
    "D": Config(core=False, ladder_below_start=False,
                name="D: as specified - every unit incl. the first stopped 1% below its entry; "
                     "units only at/above the January price"),
    "E": Config(core=False, ladder_below_start=False, max_ladder=10,
                name="E: D but never more than 10 contracts"),
    "B": Config(core=False, ladder_below_start=True,
                name="B: every unit stopped, buy on every +1% step at ANY price"),
    "A": Config(core=True, ladder_below_start=False,
                name="A: first unit held all year without a stop"),
}


def realized_var(bars: pd.DataFrame, P0: float, freq="60min"):
    """annualisation-free realised variance of log price over the window
    (total and the part accumulated while price was above the start)."""
    c = bars["close"].resample(freq).last().dropna()
    lr = np.log(c).diff().dropna()
    above = (c.shift(1).reindex(lr.index) > P0)
    return float((lr ** 2).sum()), float((lr[above] ** 2).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfd", required=True)
    ap.add_argument("--yahoo", required=True)
    ap.add_argument("--out", default="results")
    ap.add_argument("--quick", action="store_true", help="skip sensitivity grids")
    a = ap.parse_args()
    os.makedirs(os.path.join(a.out, "trades"), exist_ok=True)
    os.makedirs(os.path.join(a.out, "equity"), exist_ok=True)

    cfd, ndx, nqf, irx, last_date = load_inputs(a.cfd, a.yahoo)

    # ---------------- data validation ----------------
    dates = ndx.index[(ndx.index >= "2022-01-01") & (ndx.index <= last_date)]
    cc = cfd_at_close(cfd, dates)
    dev_bp = (cc / ndx.loc[cc.index, "close"] - 1) * 1e4
    corr = np.corrcoef(np.log(cc).diff()[1:], np.log(ndx.loc[cc.index, "close"]).diff()[1:])[0, 1]
    sess = (cfd.index.tz_convert(ET) + pd.Timedelta(hours=6)).normalize().tz_localize(None)
    g = cfd.groupby(sess).agg(h=("high", "max"), l=("low", "min"))
    j = g.join(nqf[["high", "low"]], how="inner")
    j = j[(j.index >= "2022-01-01")]
    rng_c, rng_n = (j.h / j.l - 1) * 100, (j.high / j.low - 1) * 100
    with open(os.path.join(a.out, "data_validation.md"), "w") as f:
        f.write("# Data validation (Dukascopy NAS100 CFD vs Yahoo NDX / NQ=F)\n\n")
        f.write(f"* 1-min bars used: {len(cfd):,} ({cfd.index[0]} -> {cfd.index[-1]})\n")
        f.write(f"* CFD at 16:00 ET vs official NDX close: median {dev_bp.median():+.1f} bp, "
                f"5-95% range {dev_bp.quantile(.05):+.1f} .. {dev_bp.quantile(.95):+.1f} bp (n={len(dev_bp)})\n")
        f.write(f"* Daily return correlation CFD vs NDX: {corr:.4f}\n")
        f.write(f"* Average daily high-low range: CFD {rng_c.mean():.3f}% vs NQ futures {rng_n.mean():.3f}% "
                f"(median difference {(rng_c - rng_n).median():+.3f} pp, n={len(j)})\n")

    rolled = rolled_nq_points(nqf, ndx)      # real rolled-NQ daily points (Yahoo NQ=F)
    carry_rows = []

    rows, meta_rows, sens_rows, cap_rows = [], [], [], []
    for y in YEARS:
        # financing spread calibrated so the model's year matches real rolled NQ
        bars, meta, check = build_year_calibrated(cfd, ndx, nqf, irx, y, last_date, rolled)
        carry_rows.append(check)
        rv_all, rv_above = realized_var(bars, meta["P0"])
        meta.update(rv_total=rv_all, rv_above_start=rv_above,
                    log_ret=math.log(meta["P_end"] / meta["P0"]))
        meta_rows.append(meta)
        print(f"{y}: {meta['first_day']} -> {meta['last_day']}  NQ {meta['P0']:.0f} -> {meta['P_end']:.0f}"
              f"  carry {meta['carry_pts']:.0f} pts  bars {meta['bars']}", flush=True)
        for key, cfg in VARIANTS.items():
            t = time.time()
            r = run(bars, cfg)
            s = dict(year=y, key=key, **r.stats)
            rows.append(s)
            r.trades.to_csv(os.path.join(a.out, "trades", f"{key}_{y}.csv"), index=False)
            daily = pd.DataFrame({"equity_usd": r.equity, "units": r.units, "nq": bars["close"]})
            # hourly snapshot for charts and the closed-form check
            hourly = daily.resample("60min").agg({"equity_usd": "last", "units": "last", "nq": "last"}).dropna()
            hourly.to_csv(os.path.join(a.out, "equity", f"{key}_{y}.csv"), float_format="%.2f")
            print(f"   {key} total {s['total_pnl_usd']:>12,.0f}  ladder {s['ladder_pnl_usd']:>12,.0f}"
                  f"  stopouts {s['stopouts']:4d}  maxU {s['max_units']:3d}  ({time.time()-t:.1f}s)", flush=True)

        if not a.quick:
            for core in (True, False):
                for step in (0.005, 0.01, 0.02, 0.03):
                    for stop in (0.005, 0.01, 0.02, 0.03):
                        cfg = Config(core=core, step=step, stop=stop)
                        st = run(bars, cfg).stats
                        sens_rows.append(dict(year=y, core=core, step_pct=step * 100,
                                              stop_pct=stop * 100, **{k: st[k] for k in (
                                                  "total_pnl_usd", "ladder_pnl_usd", "stopouts",
                                                  "max_units", "max_drawdown_usd", "min_equity_usd")}))
            for cap in (5, 10, 20, 30, None):
                st = run(bars, Config(core=False, max_ladder=cap)).stats
                cap_rows.append(dict(year=y, cap=cap if cap else "none", **{k: st[k] for k in (
                    "total_pnl_usd", "ladder_pnl_usd", "stopouts", "max_units",
                    "max_drawdown_usd", "min_equity_usd")}))

    with open(os.path.join(a.out, "data_validation.md"), "a") as f:
        f.write("\n## Carry model check: 1 NQ contract held first-day close -> last-day close (points)\n\n")
        f.write("| Year | Real rolled NQ (Yahoo NQ=F, roll jumps removed) | Model: T-bill - 0.7% only "
                "| Model calibrated (used) | Calibrated extra financing spread | Cash index (no carry) |\n")
        f.write("|---|---:|---:|---:|---:|---:|\n")
        for y, real, m0, model, spread, cash in carry_rows:
            f.write(f"| {y} | {real:,.0f} | {m0:,.0f} | {model:,.0f} | {spread*100:+.2f}%/yr | {cash:,.0f} |\n")
    pd.DataFrame(rows).to_csv(os.path.join(a.out, "summary_all_variants.csv"), index=False)
    pd.DataFrame(meta_rows).to_csv(os.path.join(a.out, "year_meta.csv"), index=False)
    if sens_rows:
        pd.DataFrame(sens_rows).to_csv(os.path.join(a.out, "sensitivity_step_stop.csv"), index=False)
        pd.DataFrame(cap_rows).to_csv(os.path.join(a.out, "sensitivity_max_units.csv"), index=False)
    print("done")


if __name__ == "__main__":
    main()
