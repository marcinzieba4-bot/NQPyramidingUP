"""Run one recovery-entry variant on 2008-2026, with neighbours and a 20-delta call overlay.

Example (entry at the 30% retracement, 1% step, +12% reset):
    python3 -I src/run_variant.py --name recovery30 --retrace 0.30 \
        --neighbors retrace=0.2,0.4,0.5,0.7 \
        --dukascopy ... --histdata ... --hf ... --yahoo ... --out results

Outputs go to results/<name>/: yearly summary (with buy & hold, the pyramid from January
and the 70% recovery base for context), campaigns, trades, neighbours, covered calls and
their option-price stress test.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from long_history import boundary_ratios, load_segments  # noqa: E402
from nq_series import load_yahoo  # noqa: E402
from options_overlay import CallConfig, VolSurface  # noqa: E402
from recovery_backtest import RecoveryConfig, run_segments  # noqa: E402
from run_long import YEARS, with_calls  # noqa: E402
from run_recovery import drawdown, stats  # noqa: E402

CALLS = [("sell 20-delta 30-day calls", dict(strike="delta", delta=0.20, days=30)),
         ("sell 20-delta 7-day calls", dict(strike="delta", delta=0.20, days=7))]


def totals(res):
    yr = pd.Series({y: float(v) for y, v in res["year_pnl"].items()})
    c = res["campaigns"]
    return dict(total=round(yr.sum()), losing_years=int((yr < 0).sum()), worst_year=round(yr.min()),
                worst_drawdown=round(drawdown(res["equity"])), campaigns=len(c),
                hit_target=int(c.outcome.str.contains("target").sum()) if len(c) else 0,
                stopouts=int((res["trades"].reason == "stop").sum()), max_contracts=int(res["units"].max()))


def main():
    ap = argparse.ArgumentParser()
    for k in ("dukascopy", "histdata", "hf", "yahoo"):
        ap.add_argument(f"--{k}", required=True)
    ap.add_argument("--out", default="results")
    ap.add_argument("--name", required=True)
    ap.add_argument("--pullback", type=float, default=0.05)
    ap.add_argument("--retrace", type=float, default=0.70)
    ap.add_argument("--take-profit", type=float, default=0.12)
    ap.add_argument("--step", type=float, default=0.01)
    ap.add_argument("--stop", type=float, default=0.01)
    ap.add_argument("--neighbors", default="", help='e.g. "retrace=0.2,0.4,0.5"')
    a = ap.parse_args()
    out = os.path.join(a.out, a.name)
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    base_kw = dict(pullback=a.pullback, retrace=a.retrace, take_profit=a.take_profit, step=a.step, stop=a.stop)
    cfg = RecoveryConfig(**base_kw)

    segments, metas, ctx = load_segments(YEARS, a.dukascopy, a.histdata, a.hf, a.yahoo)
    ratios = boundary_ratios(metas)
    print(f"segments ready ({time.time()-t0:.0f}s); variant: {cfg.label()}", flush=True)

    res = run_segments(segments, cfg, None)
    res_c = run_segments(segments, cfg, ratios)
    st = stats(res, segments).set_index("year")
    st.insert(1, "straight_through_usd", [round(res_c["year_pnl"][y]) for y in st.index])
    long = pd.read_csv(os.path.join(a.out, "long", "summary_by_year.csv")).set_index("year")
    st = st.join(long[["nq_move_pct", "buy_hold_usd", "D_usd", "recovery_usd"]].rename(
        columns={"recovery_usd": "recovery_70pct_usd"}))
    st["notional_usd"] = [round(m["P0"] * 20.0) for m in metas]
    st.to_csv(os.path.join(out, "summary_by_year.csv"))
    cp = res["campaigns"].copy()
    cp["days"] = (pd.to_datetime(cp.end) - pd.to_datetime(cp.start)).dt.total_seconds() / 86400
    cp.to_csv(os.path.join(out, "campaigns_restart.csv"), index=False, float_format="%.2f")
    res["trades"].to_csv(os.path.join(out, "trades_restart.csv"), index=False, float_format="%.2f")
    t_r, t_c = totals(res), totals(res_c)
    print(f"variant done ({time.time()-t0:.0f}s): restart {t_r['total']:,} dd {t_r['worst_drawdown']:,}; "
          f"straight through {t_c['total']:,} dd {t_c['worst_drawdown']:,}", flush=True)

    # covered calls (20-delta), with the option-price stress test
    vxn = load_yahoo(a.yahoo, "VXN")["close"]
    irx = ctx["irx"]["close"]
    rows = [dict(overlay="no calls", vol_vs_vxn="", **{str(y): round(res["year_pnl"][y]) for y in YEARS},
                 total=t_r["total"], option_pnl=0, worst_drawdown=t_r["worst_drawdown"])]
    eq_daily = {"variant": res["equity"].resample("1D").last().dropna()}
    for name, kw in CALLS:
        for ratio in (0.80, 0.90, 1.00):
            ccfg = CallConfig(vxn_to_atm=ratio, **kw)
            by_year, eq, tr = with_calls(res, segments, VolSurface(vxn, irx, ccfg), ccfg)
            rows.append(dict(overlay=name, vol_vs_vxn=ratio,
                             **{str(y): round(res["year_pnl"][y] + by_year.get(y, 0.0)) for y in YEARS},
                             total=round(t_r["total"] + by_year.sum()), option_pnl=round(by_year.sum()),
                             worst_drawdown=round(drawdown(eq))))
            if ratio == 0.90:
                eq_daily[f"variant + {name}"] = eq.resample("1D").last().dropna()
            print(f"  {name} @ {ratio} x VXN: option P&L {by_year.sum():,.0f} ({time.time()-t0:.0f}s)", flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(out, "covered_calls.csv"), index=False)
    pd.DataFrame(eq_daily).to_csv(os.path.join(out, "equity_daily.csv"), float_format="%.2f")

    # neighbours (restart each January)
    nrows = [dict(setting=f"this variant ({cfg.label()})", **t_r,
                  **{str(y): round(res["year_pnl"][y]) for y in YEARS})]
    if a.neighbors:
        param, vals = a.neighbors.split("=")
        for v in vals.split(","):
            kw = dict(base_kw, **{param: float(v)})
            r = run_segments(segments, RecoveryConfig(**kw), None)
            nrows.append(dict(setting=f"{param} {float(v):g}", **totals(r),
                              **{str(y): round(r["year_pnl"][y]) for y in YEARS}))
            print(f"  {param}={v}: {nrows[-1]['total']:,} dd {nrows[-1]['worst_drawdown']:,} "
                  f"({time.time()-t0:.0f}s)", flush=True)
    pd.DataFrame(nrows).to_csv(os.path.join(out, "neighbors.csv"), index=False)
    print("done")


if __name__ == "__main__":
    main()
