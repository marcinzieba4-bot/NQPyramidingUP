"""2008-2026 run of the recovery-entry pyramid, its variants and a covered-call overlay.

Usage:
    python3 -I src/run_long.py --dukascopy DATA/dukascopy/USATECHIDXUSD_1min_mid.csv.gz \
        --histdata DATA/histdata/NSXUSD_1min.csv.gz --hf DATA/hf_nasdaq60 --yahoo DATA/yahoo --out results
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from long_history import boundary_ratios, hf_year, load_segments  # noqa: E402
from nq_series import load_yahoo  # noqa: E402
from options_overlay import CallConfig, VolSurface, overlay  # noqa: E402
from pyramid_backtest import Config, run  # noqa: E402
from recovery_backtest import RecoveryConfig, run_segments  # noqa: E402
from run_recovery import drawdown, stats  # noqa: E402

YEARS = list(range(2008, 2027))

VARIANTS = [
    ("base: 5% pullback, 70% entry, +12% reset", {}),
    ("pullback 3%", dict(pullback=0.03)),
    ("pullback 8%", dict(pullback=0.08)),
    ("pullback 10%", dict(pullback=0.10)),
    ("entry at 50% retracement", dict(retrace=0.50)),
    ("entry at 61.8% retracement", dict(retrace=0.618)),
    ("entry at 80% retracement", dict(retrace=0.80)),
    ("reset at +8%", dict(take_profit=0.08)),
    ("reset at +16%", dict(take_profit=0.16)),
    ("reset at +20%", dict(take_profit=0.20)),
    ("no reset (hold to year end)", dict(take_profit=None)),
    ("stop 2% (add every 1%)", dict(stop=0.02)),
    ("add every 2%, stop 2%", dict(step=0.02, stop=0.02)),
    ("abandon after 10 stop-outs", dict(max_stopouts=10)),
    ("abandon after 60 days", dict(max_days=60)),
    ("single unit (no pyramid)", dict(max_units=1)),
]

CALLS = [
    ("sell ATM 30-day calls", CallConfig(strike="atm", days=30)),
    ("sell 20-delta 30-day calls", CallConfig(strike="delta", delta=0.20, days=30)),
    ("sell ATM 7-day calls", CallConfig(strike="atm", days=7)),
    ("sell 20-delta 7-day calls", CallConfig(strike="delta", delta=0.20, days=7)),
]


def yearly(res):
    return {y: float(v) for y, v in res["year_pnl"].items()}


def with_calls(res, segments, vs, ccfg):
    """add option P&L (booked when each unit is closed) to the strategy's results."""
    tr = res["trades"]
    opt = overlay(tr, segments, vs, ccfg)
    tr = tr.join(opt)
    by_year = tr.groupby(pd.to_datetime(tr.exit_time).dt.year)["option_pnl_usd"].sum()
    steps = tr.groupby("exit_time")["option_pnl_usd"].sum().sort_index()
    steps.index = pd.to_datetime(steps.index)
    eq = res["equity"] + steps.reindex(res["equity"].index, fill_value=0.0).cumsum()
    return by_year, eq, tr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dukascopy", required=True)
    ap.add_argument("--histdata", required=True)
    ap.add_argument("--hf", required=True)
    ap.add_argument("--yahoo", required=True)
    ap.add_argument("--out", default="results")
    a = ap.parse_args()
    out = os.path.join(a.out, "long")
    os.makedirs(out, exist_ok=True)
    t_start = time.time()

    segments, metas, ctx = load_segments(YEARS, a.dukascopy, a.histdata, a.hf, a.yahoo)
    ratios = boundary_ratios(metas)
    pd.DataFrame([dict(year=m["year"], source=m["source"], bars=m["bars"], P0=round(m["P0"], 2),
                       P_end=round(m["P_end"], 2), nq_move_pct=round((m["P_end"] / m["P0"] - 1) * 100, 1),
                       model_pts=round(m["model_pts"]), real_rolled_nq_pts=round(m["real_pts"]),
                       level_ratio_vs_prev=None if r is None else round(r, 4))
                  for m, r in zip(metas, ratios)]).to_csv(os.path.join(out, "data_sources.csv"), index=False)
    print(f"segments ready ({time.time()-t_start:.0f}s)", flush=True)

    # ---- context: pyramid from the January open (D) and buy & hold ----
    d_rows = []
    for bars, m in zip(segments, metas):
        st = run(bars, Config(core=False, ladder_below_start=False)).stats
        d_rows.append(dict(year=m["year"], buy_hold_usd=st["buy_hold_1u_usd"], D_usd=st["total_pnl_usd"],
                           D_max_dd_usd=st["max_drawdown_usd"], D_max_units=st["max_units"]))
    ctx_df = pd.DataFrame(d_rows).set_index("year")
    print(f"D done ({time.time()-t_start:.0f}s)", flush=True)

    # ---- recovery strategy: base in both modes ----
    base = RecoveryConfig()
    res_r = run_segments(segments, base, None)
    res_c = run_segments(segments, base, ratios)
    st_r = stats(res_r, segments).set_index("year")
    summary = ctx_df.join(pd.DataFrame({"recovery_usd": pd.Series(yearly(res_r)),
                                        "recovery_straight_through_usd": pd.Series(yearly(res_c))}))
    summary = summary.join(st_r.drop(columns=["pnl_usd"]))
    summary.insert(0, "source", [m["source"] for m in metas])
    summary.insert(1, "nq_move_pct", [round((m["P_end"] / m["P0"] - 1) * 100, 1) for m in metas])
    summary.round(0).to_csv(os.path.join(out, "summary_by_year.csv"))
    cp = res_r["campaigns"].copy()
    cp["days"] = (pd.to_datetime(cp.end) - pd.to_datetime(cp.start)).dt.total_seconds() / 86400
    cp.to_csv(os.path.join(out, "campaigns_restart.csv"), index=False, float_format="%.2f")
    res_r["trades"].to_csv(os.path.join(out, "trades_restart.csv"), index=False, float_format="%.2f")
    print(f"recovery base done ({time.time()-t_start:.0f}s): restart {sum(yearly(res_r).values()):,.0f}, "
          f"straight through {sum(yearly(res_c).values()):,.0f}", flush=True)

    # ---- hourly vs 1-minute check on 2011-2022 ----
    chk_years = list(range(2011, 2023))
    hf_segs = [hf_year(ctx["hf"], ctx["ndx"], ctx["nqf"], y, ctx["rolled"])[0][["open", "high", "low", "close"]]
               for y in chk_years]
    min_segs = [segments[YEARS.index(y)] for y in chk_years]
    rh, rm = run_segments(hf_segs, base, None), run_segments(min_segs, base, None)
    dh = [run(b, Config(core=False)).stats["total_pnl_usd"] for b in hf_segs]
    dm = [ctx_df.loc[y, "D_usd"] for y in chk_years]
    pd.DataFrame({"year": chk_years, "recovery_1min": [round(yearly(rm)[y]) for y in chk_years],
                  "recovery_hourly": [round(yearly(rh)[y]) for y in chk_years],
                  "D_1min": [round(v) for v in dm], "D_hourly": [round(v) for v in dh]}).to_csv(
        os.path.join(out, "hourly_vs_minute.csv"), index=False)
    print(f"hourly check done ({time.time()-t_start:.0f}s)", flush=True)

    # ---- covered calls on the recovery base (and on D for reference) ----
    vxn = load_yahoo(a.yahoo, "VXN")["close"]
    irx = ctx["irx"]["close"]
    call_rows, call_eq = [], {}
    for name, ccfg in CALLS:
        vs = VolSurface(vxn, irx, ccfg)
        by_year, eq, tr = with_calls(res_r, segments, vs, ccfg)
        row = dict(strategy="recovery", overlay=name)
        row.update({str(y): round(yearly(res_r)[y] + by_year.get(y, 0.0)) for y in YEARS})
        row.update(total=round(sum(yearly(res_r).values()) + by_year.sum()), option_pnl=round(by_year.sum()),
                   option_costs=round(tr.option_cost_usd.sum()), calls_sold=int(tr.calls_sold.sum()),
                   worst_drawdown=round(drawdown(eq)))
        call_rows.append(row)
        call_eq[name] = eq.resample("1D").last().dropna()
        print(f"  {name}: option P&L {by_year.sum():,.0f}", flush=True)
    base_row = dict(strategy="recovery", overlay="no calls")
    base_row.update({str(y): round(yearly(res_r)[y]) for y in YEARS})
    base_row.update(total=round(sum(yearly(res_r).values())), option_pnl=0, option_costs=0, calls_sold=0,
                    worst_drawdown=round(drawdown(res_r["equity"])))
    call_rows.insert(0, base_row)
    # D: per-year independent runs -> chain trades/equity for the overlay
    d_tr, d_eq, off = [], [], 0.0
    for bars in segments:
        r = run(bars, Config(core=False))
        d_tr.append(r.trades)
        d_eq.append(r.equity + off)
        off += r.equity.iloc[-1]
    d_res = dict(trades=pd.concat(d_tr, ignore_index=True), equity=pd.concat(d_eq))
    d_res["year_pnl"] = {m["year"]: ctx_df.loc[m["year"], "D_usd"] for m in metas}
    for name, ccfg in [("no calls", None)] + CALLS:
        row = dict(strategy="D (pyramid from January)", overlay=name)
        if ccfg is None:
            by_year, eq = pd.Series(dtype=float), d_res["equity"]
        else:
            by_year, eq, _ = with_calls(d_res, segments, VolSurface(vxn, irx, ccfg), ccfg)
        row.update({str(y): round(d_res["year_pnl"][y] + by_year.get(y, 0.0)) for y in YEARS})
        row.update(total=round(sum(d_res["year_pnl"].values()) + by_year.sum()),
                   option_pnl=round(by_year.sum()), worst_drawdown=round(drawdown(eq)))
        call_rows.append(row)
    pd.DataFrame(call_rows).to_csv(os.path.join(out, "covered_calls.csv"), index=False)
    eqs = pd.DataFrame({"recovery": res_r["equity"].resample("1D").last().dropna(),
                        "recovery_straight_through": res_c["equity"].resample("1D").last().dropna(),
                        "D": d_res["equity"].resample("1D").last().dropna(),
                        **{f"recovery + {k}": v for k, v in call_eq.items()}})
    bh, offb = [], 0.0
    for bars, m in zip(segments, metas):
        s = (bars["close"] - m["P0"]) * 20.0 + offb
        bh.append(s)
        offb = s.iloc[-1]
    eqs["buy_hold"] = pd.concat(bh).resample("1D").last()
    px = pd.concat([seg["close"] for seg in segments]).resample("1D").last()
    eqs["nq_level"] = px
    eqs.to_csv(os.path.join(out, "equity_daily.csv"), float_format="%.2f")
    print(f"calls done ({time.time()-t_start:.0f}s)", flush=True)

    # ---- variants (restart each January) ----
    rows = []
    for name, kw in VARIANTS:
        r = run_segments(segments, RecoveryConfig(**kw), None)
        c = r["campaigns"]
        row = dict(variant=name)
        row.update({str(y): round(v) for y, v in yearly(r).items()})
        yr = pd.Series(yearly(r))
        row.update(total=round(yr.sum()), worst_year=round(yr.min()), losing_years=int((yr < 0).sum()),
                   worst_drawdown=round(drawdown(r["equity"])), campaigns=len(c),
                   hit_target=int(c.outcome.str.contains("target").sum()) if len(c) else 0,
                   stopouts=int((r["trades"].reason == "stop").sum()), max_contracts=int(r["units"].max()))
        rows.append(row)
        print(f"  {name}: {row['total']:,} dd {row['worst_drawdown']:,} ({time.time()-t_start:.0f}s)", flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(out, "variants.csv"), index=False)
    print("done")


if __name__ == "__main__":
    main()
