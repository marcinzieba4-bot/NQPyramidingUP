"""Backtest the recovery-entry pyramid (see recovery_backtest.py) on 2022-2026.

The swing logic needs history across year-ends, so the main run is continuous
from the first 2022 session to Nov 2 2026, with P&L attributed to calendar years.
At each year boundary the NQ-equivalent series switches to the next year's
calibrated level; the open state is carried over like a futures roll.

Usage:
    python3 -I src/run_recovery.py --cfd DATA/USATECHIDXUSD_1min_mid.csv.gz --yahoo DATA/yahoo --out results
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nq_series import load_inputs, build_year_calibrated, rolled_nq_points  # noqa: E402
from recovery_backtest import RecoveryConfig, run_segments  # noqa: E402

YEARS = [2022, 2023, 2024, 2025, 2026]


def boundary_ratios(segments, metas):
    """r such that next-year level = r x previous-year level at the same instant."""
    ratios = [None]
    for prev, cur in zip(metas[:-1], metas[1:]):
        p_new = cur["P0"]                                   # first open, new-year scale
        s = p_new / (cur["K_basis"] * cur["cfd_align"])     # CFD price at that instant
        p_old = prev["K_basis"] * prev["cfd_align"] * s - prev["carry_pts"]
        ratios.append(p_new / p_old)
    return ratios


def drawdown(eq):
    return float((eq - eq.cummax()).min())


def stats(res, segments):
    eq, un, cp = res["equity"], res["units"], res["campaigns"]
    rows = []
    for bars in segments:
        y = bars.index[0].year
        e = eq[eq.index.year == y]
        u = un[un.index.year == y]
        c = cp[pd.to_datetime(cp.start).dt.year == y] if len(cp) else cp
        t = res["trades"]
        t = t[pd.to_datetime(t.exit_time).dt.year == y]
        rows.append(dict(
            year=y, pnl_usd=round(res["year_pnl"][y]),
            campaigns_started=len(c),
            hit_target=int((c.outcome == "+12% target").sum()) if len(c) else 0,
            cancelled=int((c.outcome == "cancelled (new low)").sum()) if len(c) else 0,
            stopouts=int((t.reason == "stop").sum()),
            max_contracts=int(u.max()),
            time_in_market_pct=round(float((u > 0).mean()) * 100, 1),
            max_drawdown_usd=round(drawdown(pd.concat([pd.Series([e.iloc[0] - res['year_pnl'][y]]), e])
                                            if len(e) else e)),
        ))
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfd", required=True)
    ap.add_argument("--yahoo", required=True)
    ap.add_argument("--out", default="results")
    ap.add_argument("--quick", action="store_true", help="skip the sensitivity grid")
    a = ap.parse_args()
    out = os.path.join(a.out, "recovery")
    os.makedirs(out, exist_ok=True)

    cfd, ndx, nqf, irx, last_date = load_inputs(a.cfd, a.yahoo)
    rolled = rolled_nq_points(nqf, ndx)
    segments, metas = [], []
    for y in YEARS:
        bars, meta, _ = build_year_calibrated(cfd, ndx, nqf, irx, y, last_date, rolled)
        segments.append(bars[["open", "high", "low", "close"]])
        metas.append(meta)
    ratios = boundary_ratios(segments, metas)
    print("year-boundary level ratios:", [None if r is None else round(r, 4) for r in ratios])

    base = RecoveryConfig()
    modes = {"restart": None, "continuous": ratios}     # restart = fresh each January (main)
    cum = np.cumprod([1.0] + [r for r in ratios[1:]][::-1])[::-1]   # level factor -> 2026 scale
    px = pd.concat([seg["close"] * f for seg, f in zip(segments, cum)])
    pd.DataFrame({"year": YEARS, "level_factor_to_2026_scale": cum}).to_csv(
        os.path.join(out, "level_factors.csv"), index=False)
    all_stats = []
    for mode, rr in modes.items():
        res = run_segments(segments, base, rr)
        st = stats(res, segments)
        st.insert(0, "mode", mode)
        all_stats.append(st)
        print(mode); print(st.to_string(index=False))
        print(f"  total {sum(res['year_pnl'].values()):,.0f}  worst drawdown {drawdown(res['equity']):,.0f}")
        cp = res["campaigns"].copy()
        cp["days"] = (pd.to_datetime(cp.end) - pd.to_datetime(cp.start)).dt.total_seconds() / 86400
        cp.to_csv(os.path.join(out, f"campaigns_{mode}.csv"), index=False, float_format="%.2f")
        res["trades"].to_csv(os.path.join(out, f"trades_{mode}.csv"), index=False, float_format="%.2f")
        hourly = pd.DataFrame({"equity_usd": res["equity"], "units": res["units"], "nq_linked": px,
                               "nasdaq100": cfd["close"].reindex(px.index)})
        hourly = hourly.resample("60min").agg({"equity_usd": "last", "units": "max",
                                               "nq_linked": "last", "nasdaq100": "last"}).dropna()
        hourly.to_csv(os.path.join(out, f"equity_hourly_{mode}.csv"), float_format="%.2f")
    pd.concat(all_stats).to_csv(os.path.join(out, "summary_by_year.csv"), index=False)

    if not a.quick:
        grid = [("pullback", v) for v in (0.03, 0.05, 0.08, 0.10)] + \
               [("retrace", v) for v in (0.50, 0.618, 0.70, 0.80)] + \
               [("take_profit", v) for v in (0.08, 0.12, 0.16, 0.20, None)]
        rows = []
        for param, v in grid:
            cfg = RecoveryConfig(**{param: v})
            for mode, rr in modes.items():
                r = run_segments(segments, cfg, rr)
                c = r["campaigns"]
                row = dict(mode=mode, param=param, value="none" if v is None else v)
                row.update({str(y): round(r["year_pnl"][y]) for y in YEARS})
                row.update(total=round(sum(r["year_pnl"].values())),
                           worst_drawdown=round(drawdown(r["equity"])), campaigns=len(c),
                           hit_target=int(c.outcome.str.contains("target").sum()) if len(c) else 0,
                           max_contracts=int(r["units"].max()))
                rows.append(row)
                print(mode, param, v, row["total"], row["worst_drawdown"], flush=True)
        pd.DataFrame(rows).to_csv(os.path.join(out, "sensitivity.csv"), index=False)
    print("done")


if __name__ == "__main__":
    main()
