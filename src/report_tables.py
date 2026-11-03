"""Print the markdown tables used in README.md from the CSVs in results/."""
import argparse
import os

import pandas as pd


def k(x):
    a = abs(x)
    s = f"${a/1e6:.2f}M" if a >= 1e6 else (f"${a/1e3:.0f}k" if a >= 999.5 else f"${a:.0f}")
    return ("-" if x < 0 else "+") + s if x else "$0"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    a = ap.parse_args()
    r = a.results
    s = pd.read_csv(os.path.join(r, "summary_all_variants.csv"))
    yl = lambda y: f"{y} YTD" if y == 2026 else str(y)
    A = s[s.key == "D"].set_index("year")
    print("### main\n")
    print("| Year | NQ move* | Buy & hold 1 NQ | **Pyramid (as specified)** | Whipsaw stop-outs | Cost of stop-outs | P&L of units held at the end | Max contracts | Worst drawdown from peak |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for y, x in A.iterrows():
        print(f"| {yl(y)} | {x.price_chg_pct:+.1f}% | {k(x.buy_hold_1u_usd)} | **{k(x.total_pnl_usd)}** | {x.stopouts} | "
              f"{k(x.stopout_loss_usd)} | {k(x.held_units_pnl_usd)} | {x.max_units} | {k(x.max_drawdown_usd)} |")
    t = A.sum(numeric_only=True)
    print(f"| **Total** | | **{k(t.buy_hold_1u_usd)}** | **{k(t.total_pnl_usd)}** | {int(t.stopouts)} | {k(t.stopout_loss_usd)} | {k(t.held_units_pnl_usd)} | | |")
    print("\n### variants\n")
    keys = ["D", "E", "B", "A"]
    print("| Year | " + " | ".join(keys) + " | Buy & hold |")
    print("|---|" + "---:|" * (len(keys) + 1))
    piv = s.pivot(index="year", columns="key", values="total_pnl_usd")
    for y in piv.index:
        print(f"| {yl(y)} | " + " | ".join(k(piv.loc[y, c]) for c in keys) + f" | {k(A.loc[y, 'buy_hold_1u_usd'])} |")
    print("| **Total** | " + " | ".join(f"**{k(piv[c].sum())}**" for c in keys) + f" | **{k(A.buy_hold_1u_usd.sum())}** |")
    dd = s.pivot(index="year", columns="key", values="max_drawdown_usd")
    print("| Worst drawdown | " + " | ".join(k(dd[c].min()) for c in keys) + " | |")
    mu = s.pivot(index="year", columns="key", values="max_units")
    print("| Max contracts | " + " | ".join(str(int(mu[c].max())) for c in keys) + " | 1 |")
    print("\n### theory\n")
    th = pd.read_csv(os.path.join(r, "theory_check.csv"))
    print("| Year | Variant | Move from anchor | (log move)² | Realised variance | Edge ratio | Stop-outs predicted / actual | Ladder P&L predicted / actual |")
    print("|---|---|---:|---:|---:|---:|---:|---:|")
    for _, x in th.iterrows():
        print(f"| {yl(x.year)} | {x.variant} | {x.move_from_anchor_pct:+.1f}% | {x.trend_sq:.4f} | {x.realised_var:.4f} | "
              f"{x.edge_ratio:.2f} | {x.stopouts_pred} / {x.stopouts_actual} | {k(x.ladder_pnl_pred)} / {k(x.ladder_pnl_actual)} |")
    print("\n### step/stop (variant D)\n")
    ss = pd.read_csv(os.path.join(r, "sensitivity_step_stop.csv"))
    for core in (False,):
        x = ss[ss.core == core]
        tot = x.pivot_table(index=["step_pct", "stop_pct"], columns="year", values="total_pnl_usd", aggfunc="sum")
        dd = x.groupby(["step_pct", "stop_pct"]).max_drawdown_usd.min()
        so = x.groupby(["step_pct", "stop_pct"]).stopouts.sum()
        mu = x.groupby(["step_pct", "stop_pct"]).max_units.max()
        print("| Add every | Stop | " + " | ".join(yl(y) for y in tot.columns) + " | 5-yr total | Worst drawdown | Stop-outs (5 yrs) | Max contracts |")
        print("|---:|---:|" + "---:|" * (len(tot.columns) + 4))
        for (st, sp), row in tot.iterrows():
            b = "**" if (st, sp) == (1.0, 1.0) else ""
            print(f"| {b}{st:g}%{b} | {b}{sp:g}%{b} | " + " | ".join(k(v) for v in row.values) +
                  f" | {b}{k(row.sum())}{b} | {k(dd[(st, sp)])} | {so[(st, sp)]} | {mu[(st, sp)]} |")
    print("\n### cap\n")
    c = pd.read_csv(os.path.join(r, "sensitivity_max_units.csv"))
    c["cap"] = c["cap"].astype(str)
    tot = c.pivot_table(index="cap", columns="year", values="total_pnl_usd")
    dd = c.groupby("cap").max_drawdown_usd.min()
    order = ["5", "10", "20", "30", "none"]
    print("| Max contracts | " + " | ".join(yl(y) for y in tot.columns) + " | 5-yr total | Worst drawdown |")
    print("|---:|" + "---:|" * (len(tot.columns) + 2))
    for cap in order:
        row = tot.loc[cap]
        print(f"| {cap} | " + " | ".join(k(v) for v in row.values) + f" | {k(row.sum())} | {k(dd[cap])} |")
    print("\n### history\n")
    h = pd.read_csv(os.path.join(r, "history_estimate_stats.csv"))
    print("| Period | Strategy | Years positive | Median year | Mean year | Std dev | Mean / std | Worst year | Best year |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for _, x in h.iterrows():
        print(f"| {x.period} | {x.strategy} | {x.years_positive}/{x.years} | {x['median']:+.2f}× | {x['mean']:+.2f}× | "
              f"{x.stdev:.2f}× | {x.mean_over_stdev:.2f} | {x.worst:+.2f}× | {x.best:+.2f}× |")
    recovery_tables(r)
    long_tables(r)
    breakout_tables(r)
    variant_tables(r, "recovery30")
    sizing_tables(r)


def recovery_tables(r):
    """Markdown tables for the recovery-entry section of the README."""
    rd = os.path.join(r, "recovery")
    if not os.path.exists(os.path.join(rd, "summary_by_year.csv")):
        return
    yl = lambda y: f"{y} YTD" if y == 2026 else str(y)
    sb = pd.read_csv(os.path.join(rd, "summary_by_year.csv"))
    s = pd.read_csv(os.path.join(r, "summary_all_variants.csv"))
    D = s[s.key == "D"].set_index("year")
    R = sb[sb["mode"] == "restart"].set_index("year")
    C = sb[sb["mode"] == "continuous"].set_index("year")
    print("\n### recovery main\n")
    print("| Year | Recovery entries | Campaigns (hit +12% / cancelled) | Stop-outs | Max contracts | Time in market | Worst drawdown |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for y, x in R.iterrows():
        print(f"| {yl(y)} | **{k(x.pnl_usd)}** | {x.campaigns_started} ({x.hit_target} / {x.cancelled}) | "
              f"{x.stopouts} | {x.max_contracts} | {x.time_in_market_pct:.0f}% | {k(x.max_drawdown_usd)} |")
    print(f"| **Total** | **{k(R.pnl_usd.sum())}** | {R.campaigns_started.sum()} ({R.hit_target.sum()} / "
          f"{R.cancelled.sum()}) | {R.stopouts.sum()} | {R.max_contracts.max()} | | |")
    print("\n### recovery compare\n")
    print("| Year | Buy & hold 1 NQ | Pyramid from the January open (D) | **Recovery entries** | Recovery entries, run straight through |")
    print("|---|---:|---:|---:|---:|")
    for y in R.index:
        print(f"| {yl(y)} | {k(D.loc[y, 'buy_hold_1u_usd'])} | {k(D.loc[y, 'total_pnl_usd'])} | "
              f"**{k(R.loc[y, 'pnl_usd'])}** | {k(C.loc[y, 'pnl_usd'])} |")
    print(f"| **Total** | **{k(D.buy_hold_1u_usd.sum())}** | **{k(D.total_pnl_usd.sum())}** | "
          f"**{k(R.pnl_usd.sum())}** | **{k(C.pnl_usd.sum())}** |")
    sens = pd.read_csv(os.path.join(rd, "sensitivity.csv"))
    base = sens[(sens.param == "pullback") & (sens.value.astype(str) == "0.05")]
    for mode in ("restart", "continuous"):
        b = base[base["mode"] == mode].iloc[0]
        print(f"<!-- {mode}: worst drawdown {k(b.worst_drawdown)} -->")
    print("\n### recovery campaigns\n")
    cp = pd.read_csv(os.path.join(rd, "campaigns_restart.csv"), parse_dates=["start", "end"])
    print("| # | Wave: high -> low | Pullback | Entry (70% level) | Started | Ended | Outcome | Units bought / stopped | Max contracts | P&L |")
    print("|---:|---|---:|---:|---|---|---|---:|---:|---:|")
    for _, c in cp.iterrows():
        print(f"| {c.id} | {c.wave_high:,.0f} -> {c.wave_low:,.0f} | {c.pullback_pct:.1f}% | {c.start_price:,.0f} | "
              f"{c.start:%Y-%m-%d} | {c.end:%Y-%m-%d} | {c.outcome} | {c.entries} / {c.stopouts} | {c.max_units} | {k(c.pnl_usd)} |")
    print("\n### recovery sensitivity\n")
    lab = {"pullback": "Pullback that arms a wave", "retrace": "Entry retracement",
           "take_profit": "Take profit (reset)"}
    print("| Setting | Value | 2022 | 2023 | 2024 | 2025 | 2026 YTD | 5-yr total | Worst drawdown | Run straight through: total | Max contracts |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for (param, value), g in sens.groupby(["param", "value"], sort=False):
        rr = g[g["mode"] == "restart"].iloc[0]
        cc = g[g["mode"] == "continuous"].iloc[0]
        v = "none" if str(value) == "none" else f"{float(value)*100:g}%"
        isbase = (param, str(value)) in (("pullback", "0.05"), ("retrace", "0.7"), ("take_profit", "0.12"))
        bb = "**" if isbase else ""
        print(f"| {lab[param]} | {bb}{v}{bb} | " + " | ".join(k(rr[str(y)]) for y in (2022, 2023, 2024, 2025, 2026)) +
              f" | {bb}{k(rr.total)}{bb} | {k(rr.worst_drawdown)} | {k(cc.total)} | {rr.max_contracts} |")



def long_tables(r):
    """Markdown tables for the 2008-2026 section."""
    ld = os.path.join(r, "long")
    if not os.path.exists(os.path.join(ld, "variants.csv")):
        return
    yl = lambda y: f"{y} YTD" if int(y) == 2026 else str(y)
    sm = pd.read_csv(os.path.join(ld, "summary_by_year.csv")).set_index("year")
    ds = pd.read_csv(os.path.join(ld, "data_sources.csv")).set_index("year")
    cc = pd.read_csv(os.path.join(ld, "covered_calls.csv"))
    notional = ds.P0 * 20.0
    src = {"hourly NQ (HF)": "hourly", "HistData 1-min": "1-min", "Dukascopy 1-min": "1-min"}
    print("\n### long by year\n")
    print("| Year | NQ move | Bars | Buy & hold | Pyramid from January (D) | **Recovery entries** | Recovery, x one contract's January value | Campaigns (hit +12% / cancelled) | Max contracts |")
    print("|---|---:|---|---:|---:|---:|---:|---:|---:|")
    for y, x in sm.iterrows():
        print(f"| {yl(y)} | {x.nq_move_pct:+.0f}% | {src[x.source]} | {k(x.buy_hold_usd)} | {k(x.D_usd)} | **{k(x.recovery_usd)}** | "
              f"{x.recovery_usd / notional[y]:+.2f}x | {int(x.campaigns_started)} ({int(x.hit_target)} / {int(x.cancelled)}) | {int(x.max_contracts)} |")
    print(f"| **Total** | | | **{k(sm.buy_hold_usd.sum())}** | **{k(sm.D_usd.sum())}** | **{k(sm.recovery_usd.sum())}** | | "
          f"{int(sm.campaigns_started.sum())} ({int(sm.hit_target.sum())} / {int(sm.cancelled.sum())}) | |")
    # summary statistics in units of one contract's January value
    years = [str(y) for y in sm.index]
    def series_from_calls(strategy, overlay):
        row = cc[(cc.strategy == strategy) & (cc.overlay == overlay)].iloc[0]
        return pd.Series({int(y): row[y] for y in years}), row.worst_drawdown
    rec_dd = cc[(cc.strategy == "recovery") & (cc.overlay == "no calls")].iloc[0].worst_drawdown
    d_dd = cc[(cc.strategy.str.startswith("D")) & (cc.overlay == "no calls")].iloc[0].worst_drawdown
    rows = [("Buy & hold 1 contract", sm.buy_hold_usd, None),
            ("Pyramid from January (D)", sm.D_usd, d_dd),
            ("Recovery entries", sm.recovery_usd, rec_dd),
            ("Recovery entries, run straight through", sm.recovery_straight_through_usd, None)]
    for ov in ("sell 20-delta 7-day calls", "sell ATM 30-day calls"):
        s_, dd = series_from_calls("recovery", ov)
        rows.append((f"Recovery entries + {ov}", s_, dd))
    print("\n### long stats\n")
    print("| Strategy | 2008-2026 total | Winning years | Worst year | Best year | Average year | Average / std. dev. | Worst drawdown |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for name, ser, dd in rows:
        x = ser / notional
        full = x[x.index < 2026]
        print(f"| {name} | {k(ser.sum())} | {int((ser > 0).sum())} of {len(ser)} | {x.min():+.2f}x | {x.max():+.2f}x | "
              f"{x.mean():+.2f}x | {x.mean() / x.std():.2f} | {'' if dd is None else k(dd)} |")
    print("\n### long variants\n")
    v = pd.read_csv(os.path.join(ld, "variants.csv"))
    print("| Variant | 2008-2026 total | Losing years | Worst year | Worst drawdown | Campaigns (hit +12%) | Stop-outs | Max contracts |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for _, x in v.iterrows():
        b = "**" if x.variant.startswith("base") else ""
        print(f"| {b}{x.variant}{b} | {b}{k(x.total)}{b} | {x.losing_years} | {k(x.worst_year)} | {k(x.worst_drawdown)} | "
              f"{x.campaigns} ({x.hit_target}) | {x.stopouts} | {x.max_contracts} |")
    print("\n### long calls\n")
    print("| Overlay | Recovery entries: total | change | worst drawdown | Pyramid from January (D): total | change | worst drawdown |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    rec0 = cc[(cc.strategy == "recovery") & (cc.overlay == "no calls")].iloc[0].total
    d0 = cc[(cc.strategy.str.startswith("D")) & (cc.overlay == "no calls")].iloc[0].total
    for ov in ("no calls", "sell ATM 30-day calls", "sell 20-delta 30-day calls", "sell ATM 7-day calls", "sell 20-delta 7-day calls"):
        a_ = cc[(cc.strategy == "recovery") & (cc.overlay == ov)].iloc[0]
        b_ = cc[(cc.strategy.str.startswith("D")) & (cc.overlay == ov)].iloc[0]
        ch = lambda t, t0: "" if ov == "no calls" else k(t - t0)
        print(f"| {ov} | {k(a_.total)} | {ch(a_.total, rec0)} | {k(a_.worst_drawdown)} | {k(b_.total)} | {ch(b_.total, d0)} | {k(b_.worst_drawdown)} |")
    sp = os.path.join(ld, "covered_calls_sensitivity.csv")
    if os.path.exists(sp):
        cs = pd.read_csv(sp)
        print("\n### long calls sensitivity\n")
        print("| Calls sold | ATM vol 0.8 x VXN | 0.9 x VXN (base) | 1.0 x VXN | Flatter skew | Steeper skew | 3% spread cost |")
        print("|---|---:|---:|---:|---:|---:|---:|")
        for calls, g in cs.groupby("calls", sort=False):
            def val(ratio, skew, cost):
                m = g[(g["atm_vol_as_share_of_vxn"] == ratio) & (g["skew"] == skew) & (g["spread_cost_share"] == cost)]
                return k(m.option_pnl_usd.iloc[0])
            print(f"| {calls} | {val(0.8, 0.6, 0.01)} | {val(0.9, 0.6, 0.01)} | {val(1.0, 0.6, 0.01)} | "
                  f"{val(0.9, 0.3, 0.01)} | {val(0.9, 1.0, 0.01)} | {val(0.9, 0.6, 0.03)} |")
    hv = pd.read_csv(os.path.join(ld, "hourly_vs_minute.csv"))
    print("\n### long hourly check\n")
    print("| Year | Recovery, 1-min bars | Recovery, hourly bars | Pyramid from January, 1-min | Pyramid from January, hourly |")
    print("|---|---:|---:|---:|---:|")
    for _, x in hv.iterrows():
        print(f"| {x.year} | {k(x.recovery_1min)} | {k(x.recovery_hourly)} | {k(x.D_1min)} | {k(x.D_hourly)} |")
    print(f"| **2011-2022** | **{k(hv.recovery_1min.sum())}** | **{k(hv.recovery_hourly.sum())}** | **{k(hv.D_1min.sum())}** | **{k(hv.D_hourly.sum())}** |")



def breakout_tables(r):
    bd = os.path.join(r, "breakout")
    if not os.path.exists(os.path.join(bd, "variants.csv")):
        return
    yl = lambda y: f"{y} YTD" if int(y) == 2026 else str(y)
    sm = pd.read_csv(os.path.join(bd, "summary_by_year.csv")).set_index("year")
    v = pd.read_csv(os.path.join(bd, "variants.csv"))
    years = [str(y) for y in sm.index]
    print("\n### breakout by year\n")
    print("| Year | **Breakout as specified** | Campaigns (hit +5% / cancelled) | Stop-outs | Max contracts | Recovery entries | Buy & hold |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for y, x in sm.iterrows():
        print(f"| {yl(y)} | **{k(x.pnl_usd)}** | {int(x.campaigns_started)} ({int(x.hit_target)} / {int(x.cancelled)}) | "
              f"{int(x.stopouts)} | {int(x.max_contracts)} | {k(x.recovery_usd)} | {k(x.buy_hold_usd)} |")
    print(f"| **Total** | **{k(sm.pnl_usd.sum())}** | {int(sm.campaigns_started.sum())} ({int(sm.hit_target.sum())} / "
          f"{int(sm.cancelled.sum())}) | {int(sm.stopouts.sum())} | | **{k(sm.recovery_usd.sum())}** | **{k(sm.buy_hold_usd.sum())}** |")
    print("\n### breakout variants\n")
    print("| Variant | 2008-2026 total | Sum of years, x January value | Losing years | Worst year | Worst drawdown | Campaigns (hit target) | Stop-outs | Max contracts |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    notional = sm.notional_usd
    for _, x in v.iterrows():
        xs = sum(x[y] / notional[int(y)] for y in years)
        b = "**" if x.variant.startswith("base") else ""
        print(f"| {b}{x.variant}{b} | {b}{k(x.total)}{b} | {xs:+.2f}x | {x.losing_years} | {k(x.worst_year)} | "
              f"{k(x.worst_drawdown)} | {x.campaigns} ({x.hit_target}) | {x.stopouts} | {x.max_contracts} |")
    gp = os.path.join(bd, "grid_pullback_target.csv")
    if os.path.exists(gp):
        g = pd.read_csv(gp)
        print("\n### breakout grid\n")
        tps = sorted(g.target_pct.unique())
        print("| Pullback before the breakout | " + " | ".join(f"Target +{t:g}%" for t in tps) + " |")
        print("|---|" + "---:|" * len(tps))
        for pb, gg in g.groupby("pullback_pct"):
            cells = []
            for t in tps:
                x = gg[gg.target_pct == t].iloc[0]
                cells.append(f"{k(x.total)} ({k(x.total_2008_2015)} / {k(x.total_2016_2026)})")
            print(f"| {pb:g}% | " + " | ".join(cells) + " |")
    hv = pd.read_csv(os.path.join(bd, "hourly_vs_minute.csv"))
    print("\n### breakout hourly check\n")
    print(f"2011-2022, breakout as specified: 1-minute bars {k(hv.breakout_1min.sum())}, hourly bars {k(hv.breakout_hourly.sum())}")



def variant_tables(r, name):
    vd = os.path.join(r, name)
    if not os.path.exists(os.path.join(vd, "neighbors.csv")):
        return
    yl = lambda y: f"{y} YTD" if int(y) == 2026 else str(y)
    sm = pd.read_csv(os.path.join(vd, "summary_by_year.csv")).set_index("year")
    n = sm.notional_usd
    print(f"\n### {name} by year\n")
    print("| Year | NQ move | **Entry at 30%** | Campaigns (hit +12% / cancelled) | Stop-outs | Max contracts | Entry at 70% (previous base) | Buy & hold |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for y, x in sm.iterrows():
        print(f"| {yl(y)} | {x.nq_move_pct:+.0f}% | **{k(x.pnl_usd)}** | {int(x.campaigns_started)} ({int(x.hit_target)} / "
              f"{int(x.cancelled)}) | {int(x.stopouts)} | {int(x.max_contracts)} | {k(x.recovery_70pct_usd)} | {k(x.buy_hold_usd)} |")
    print(f"| **Total** | | **{k(sm.pnl_usd.sum())}** | {int(sm.campaigns_started.sum())} ({int(sm.hit_target.sum())} / "
          f"{int(sm.cancelled.sum())}) | {int(sm.stopouts.sum())} | | **{k(sm.recovery_70pct_usd.sum())}** | **{k(sm.buy_hold_usd.sum())}** |")
    print(f"| x one contract's January value, summed | | {(sm.pnl_usd / n).sum():+.2f}x | | | | "
          f"{(sm.recovery_70pct_usd / n).sum():+.2f}x | {(sm.buy_hold_usd / n).sum():+.2f}x |")
    nb = pd.read_csv(os.path.join(vd, "neighbors.csv"))
    lv = pd.read_csv(os.path.join(r, "long", "variants.csv"))
    ys = [str(y) for y in sm.index]
    entries = []
    for _, x in nb.iterrows():
        pct = 30.0 if x.setting.startswith("this variant") else float(x.setting.split()[-1]) * 100
        entries.append((pct, x))
    for name_, pct in (("entry at 61.8% retracement", 61.8), ("base: 5% pullback, 70% entry, +12% reset", 70.0),
                       ("entry at 80% retracement", 80.0)):
        entries.append((pct, lv[lv.variant == name_].iloc[0]))
    print(f"\n### {name} neighbors\n")
    print("| Entry at | 2008-2026 total | Level-adjusted sum (x January value) | 2008-2021 | 2022-2026 | Losing years | Worst drawdown | Campaigns (hit +12%) |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for pct, x in sorted(entries, key=lambda t: t[0]):
        la = sum(x[y] / n[int(y)] for y in ys)
        early = sum(x[y] for y in ys if int(y) <= 2021)
        recent = sum(x[y] for y in ys if int(y) >= 2022)
        b = "**" if pct == 30.0 else ""
        tag = " (this test)" if pct == 30.0 else (" (previous base)" if pct == 70.0 else "")
        print(f"| {b}{pct:g}%{tag}{b} | {b}{k(x.total)}{b} | {la:+.2f}x | {k(early)} | {k(recent)} | {x.losing_years} | "
              f"{k(x.worst_drawdown)} | {x.campaigns} ({x.hit_target}) |")
    print(f"| Buy & hold | {k(sm.buy_hold_usd.sum())} | {(sm.buy_hold_usd / n).sum():+.2f}x | "
          f"{k(sm.buy_hold_usd[sm.index <= 2021].sum())} | {k(sm.buy_hold_usd[sm.index >= 2022].sum())} | | | |")
    cc = pd.read_csv(os.path.join(vd, "covered_calls.csv"))
    print(f"\n### {name} calls\n")
    print("| Overlay | ATM vol 0.8 x VXN | 0.9 x VXN (base) | 1.0 x VXN | Worst drawdown (base) |")
    print("|---|---:|---:|---:|---:|")
    b = cc[cc.overlay == "no calls"].iloc[0]
    print(f"| No calls | | {k(b.total)} | | {k(b.worst_drawdown)} |")
    for ov in ("sell 20-delta 30-day calls", "sell 20-delta 7-day calls"):
        g = cc[cc.overlay == ov]
        cell = lambda v: (lambda x: f"{k(x.total)} ({k(x.option_pnl)})")(g[g.vol_vs_vxn.astype(float) == v].iloc[0])
        dd = g[g.vol_vs_vxn.astype(float) == 0.9].iloc[0].worst_drawdown
        print(f"| {ov[0].upper() + ov[1:]} | {cell(0.8)} | {cell(0.9)} | {cell(1.0)} | {k(dd)} |")



def sizing_tables(r):
    sd = os.path.join(r, "sizing")
    if not os.path.exists(os.path.join(sd, "calmar_100k_per_unit.csv")):
        return
    d = pd.read_csv(os.path.join(sd, "calmar_100k_per_unit.csv"))
    meta = pd.read_csv(os.path.join(sd, "meta.csv")).iloc[0]
    ys = [str(y) for y in range(2008, 2027)]
    d["mean_std"] = d[ys].mean(axis=1) / d[ys].std(axis=1)
    print("\n### sizing ranking\n")
    print("| Version | Average profit per year | Worst drawdown | When | Calmar | Yearly avg / std. dev. | Worst year | Losing years | Max units held |")
    print("|---|---:|---:|---|---:|---:|---:|---:|---:|")
    for _, x in d.iterrows():
        when = f"{pd.Timestamp(x.dd_peak):%d %b %Y} – {pd.Timestamp(x.dd_trough):%d %b %Y}"
        print(f"| {x.version} | {k(x.avg_per_year)} | {k(x.max_drawdown)} | {when} | **{x.calmar:.2f}** | {x.mean_std:.2f} | "
              f"{k(x.worst_year)} | {int(x.losing_years)} of 19 | {int(x.max_units)} |")
    print("\n### sizing by year\n")
    top = ["Pyramid from the January open (D)", "Recovery 70%, reset +20%", "Recovery, entry 61.8%",
           "Buy & hold ($100k each January)"]
    hdr = ["Pyramid from January (D)", "Recovery 70%, reset +20%", "Recovery 61.8%, reset +12%", "Buy & hold"]
    print("| Year | " + " | ".join(hdr) + " |")
    print("|---|" + "---:|" * len(hdr))
    for y in ys:
        print(f"| {y if y != '2026' else '2026 YTD'} | " + " | ".join(k(d[d.version == t].iloc[0][y]) for t in top) + " |")
    f = meta.mnq_notional_usd / meta.unit_usd
    pick = ["Pyramid from the January open (D)", "Recovery 70%, reset +20%", "Recovery 61.8%, reset +20%",
            "Recovery, entry 61.8%", "Recovery, entry 70% (base)", "Breakout, 8% pullback, +4% target",
            "Buy & hold ($100k each January)"]
    print("\n### sizing capital\n")
    print(f"(1 unit = 1 MNQ = ${meta.mnq_notional_usd:,.0f} of NQ at {meta.last_nq_price:,.2f})\n")
    print("| Version | Worst drawdown | Max MNQ held | Account if worst drawdown = 50% | Account if = 33% | Average profit per year | Yearly return on the 33% account |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for name in pick:
        x = d[d.version == name].iloc[0]
        dd = -x.max_drawdown * f
        print(f"| {name} | -${dd/1e3:,.0f}k | {int(x.max_units)} | ${2*dd/1e3:,.0f}k | ${3*dd/1e3:,.0f}k | "
              f"+${x.avg_per_year*f/1e3:,.0f}k | {x.avg_per_year*f/(3*dd)*100:.0f}% |")


if __name__ == "__main__":
    main()
