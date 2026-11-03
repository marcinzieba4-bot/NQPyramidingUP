"""2008-2026 run of the 1-year-high breakout pyramid (see breakout_backtest.py).

Usage:
    python3 -I src/run_breakout.py --dukascopy ... --histdata ... --hf ... --yahoo ... --out results
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from breakout_backtest import BreakoutConfig, daily_references, run_breakout, session_days  # noqa: E402
from long_history import boundary_ratios, hf_year, load_segments  # noqa: E402
from run_recovery import drawdown  # noqa: E402

YEARS = list(range(2008, 2027))

VARIANTS = [
    ("base: 3% pullback, +5% target, 0.5% step, 0.5% stop", {}),
    ("stop 1% (step 0.5%)", dict(stop=0.01)),
    ("step 1%, stop 1%", dict(step=0.01, stop=0.01)),
    ("target +3%", dict(take_profit=0.03)),
    ("target +8%", dict(take_profit=0.08)),
    ("target +12%", dict(take_profit=0.12)),
    ("5% pullback", dict(pullback=0.05)),
    ("no target (hold to year end)", dict(take_profit=None)),
]


def level_factors(ratios):
    """factor_i so that price_i x factor_i is in the last segment's scale."""
    f = [1.0]
    for r in reversed(ratios[1:]):
        f.append(f[-1] * r)
    return list(reversed(f))


def refs_for(segments, factors, pullback):
    linked = daily_references(segments, factors, pullback)
    out = []
    for seg, f in zip(segments, factors):
        days = np.unique(session_days(seg.index))
        out.append({int(d): (linked[int(d)][0] / f, linked[int(d)][1]) for d in days if int(d) in linked})
    return out


def stats(res, years):
    eq, un, cp, tr = res["equity"], res["units"], res["campaigns"], res["trades"]
    rows = []
    for y in years:
        e, u = eq[eq.index.year == y], un[un.index.year == y]
        c = cp[pd.to_datetime(cp.start).dt.year == y] if len(cp) else cp
        t = tr[pd.to_datetime(tr.exit_time).dt.year == y]
        rows.append(dict(year=y, pnl_usd=round(res["year_pnl"][y]), campaigns_started=len(c),
                         hit_target=int((c.outcome == "target").sum()) if len(c) else 0,
                         cancelled=int(c.outcome.str.startswith("cancelled").sum()) if len(c) else 0,
                         stopouts=int((t.reason == "stop").sum()), max_contracts=int(u.max()),
                         time_in_market_pct=round(float((u > 0).mean()) * 100, 1)))
    return pd.DataFrame(rows).set_index("year")


def main():
    ap = argparse.ArgumentParser()
    for k in ("dukascopy", "histdata", "hf", "yahoo"):
        ap.add_argument(f"--{k}", required=True)
    ap.add_argument("--out", default="results")
    ap.add_argument("--grid", action="store_true", help="only run the pullback x target grid")
    a = ap.parse_args()
    out = os.path.join(a.out, "breakout")
    os.makedirs(out, exist_ok=True)
    t0 = time.time()

    all_years = [2007] + YEARS                     # 2007 only as 1-year-high history
    segments, metas, ctx = load_segments(all_years, a.dukascopy, a.histdata, a.hf, a.yahoo)
    ratios = boundary_ratios(metas)
    factors = level_factors(ratios)
    segs, ratios_y = segments[1:], [None] + ratios[2:]
    refs = {p: refs_for(segments, factors, p)[1:] for p in (0.03, 0.05, 0.08)}
    print(f"segments and references ready ({time.time()-t0:.0f}s)", flush=True)
    if a.grid:
        rows = []
        for pb in (0.03, 0.05, 0.08):
            for tp in (0.02, 0.03, 0.04, 0.05):
                r = run_breakout(segs, refs[pb], BreakoutConfig(pullback=pb, take_profit=tp), None)
                yr = pd.Series({y: float(v) for y, v in r["year_pnl"].items()})
                c = r["campaigns"]
                rows.append(dict(pullback_pct=pb * 100, target_pct=tp * 100, total=round(yr.sum()),
                                 total_2008_2015=round(yr[yr.index <= 2015].sum()),
                                 total_2016_2026=round(yr[yr.index >= 2016].sum()),
                                 losing_years=int((yr < 0).sum()), worst_drawdown=round(drawdown(r["equity"])),
                                 campaigns=len(c), hit_target=int((c.outcome == "target").sum()) if len(c) else 0))
                print(rows[-1], flush=True)
        pd.DataFrame(rows).to_csv(os.path.join(out, "grid_pullback_target.csv"), index=False)
        return

    base = BreakoutConfig()
    res_r = run_breakout(segs, refs[0.03], base, None)
    res_c = run_breakout(segs, refs[0.03], base, ratios_y)
    st = stats(res_r, YEARS)
    st["straight_through_usd"] = pd.Series({y: round(v) for y, v in res_c["year_pnl"].items()})
    long = pd.read_csv(os.path.join(a.out, "long", "summary_by_year.csv")).set_index("year")
    st = st.join(long[["buy_hold_usd", "D_usd", "recovery_usd"]])
    st["notional_usd"] = [round(m["P0"] * 20.0) for m in metas[1:]]
    st.to_csv(os.path.join(out, "summary_by_year.csv"))
    cp = res_r["campaigns"].copy()
    cp["days"] = (pd.to_datetime(cp.end) - pd.to_datetime(cp.start)).dt.total_seconds() / 86400
    cp.to_csv(os.path.join(out, "campaigns_restart.csv"), index=False, float_format="%.2f")
    res_r["trades"].to_csv(os.path.join(out, "trades_restart.csv"), index=False, float_format="%.2f")
    print(f"base done ({time.time()-t0:.0f}s): restart {sum(res_r['year_pnl'].values()):,.0f} "
          f"dd {drawdown(res_r['equity']):,.0f}; straight through {sum(res_c['year_pnl'].values()):,.0f} "
          f"dd {drawdown(res_c['equity']):,.0f}", flush=True)
    eqs = pd.DataFrame({"breakout": res_r["equity"].resample("1D").last().dropna(),
                        "breakout_straight_through": res_c["equity"].resample("1D").last().dropna()})
    led = pd.read_csv(os.path.join(a.out, "long", "equity_daily.csv"), index_col=0, parse_dates=True)
    eqs = eqs.join(led[["recovery", "D", "buy_hold", "nq_level"]], how="outer")
    eqs.to_csv(os.path.join(out, "equity_daily.csv"), float_format="%.2f")

    # hourly vs 1-minute bars for the same rules, 2011-2022 (2010 as history)
    chk = list(range(2010, 2023))
    hseg = [hf_year(ctx["hf"], ctx["ndx"], ctx["nqf"], y, ctx["rolled"]) for y in chk]
    hbars = [b[["open", "high", "low", "close"]] for b, _ in hseg]
    hratios = boundary_ratios([m for _, m in hseg])
    hrefs = refs_for(hbars, level_factors(hratios), 0.03)
    rh = run_breakout(hbars[1:], hrefs[1:], base, None)
    pd.DataFrame({"year": chk[1:], "breakout_1min": [round(res_r["year_pnl"][y]) for y in chk[1:]],
                  "breakout_hourly": [round(rh["year_pnl"][y]) for y in chk[1:]]}).to_csv(
        os.path.join(out, "hourly_vs_minute.csv"), index=False)
    print(f"hourly check done ({time.time()-t0:.0f}s)", flush=True)

    rows = []
    for name, kw in VARIANTS:
        cfg = BreakoutConfig(**kw)
        r = res_r if not kw else run_breakout(segs, refs[cfg.pullback], cfg, None)
        c = r["campaigns"]
        yr = pd.Series({y: float(v) for y, v in r["year_pnl"].items()})
        row = dict(variant=name)
        row.update({str(y): round(v) for y, v in yr.items()})
        row.update(total=round(yr.sum()), losing_years=int((yr < 0).sum()), worst_year=round(yr.min()),
                   worst_drawdown=round(drawdown(r["equity"])), campaigns=len(c),
                   hit_target=int((c.outcome == "target").sum()) if len(c) else 0,
                   stopouts=int((r["trades"].reason == "stop").sum()), max_contracts=int(r["units"].max()))
        rows.append(row)
        print(f"  {name}: {row['total']:,} dd {row['worst_drawdown']:,} ({time.time()-t0:.0f}s)", flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(out, "variants.csv"), index=False)
    print("done")


if __name__ == "__main__":
    main()
