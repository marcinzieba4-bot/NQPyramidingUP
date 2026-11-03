"""Print the markdown tables used in README.md from the CSVs in results/."""
import argparse
import os

import pandas as pd


def k(x):
    a = abs(x)
    s = f"${a/1e6:.2f}M" if a >= 1e6 else f"${a/1e3:.0f}k"
    return ("-" if x < 0 else "+") + s if x else "$0"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    a = ap.parse_args()
    r = a.results
    s = pd.read_csv(os.path.join(r, "summary_all_variants.csv"))
    yl = lambda y: f"{y} YTD" if y == 2026 else str(y)
    A = s[s.key == "A"].set_index("year")
    print("### main\n")
    print("| Year | NQ move* | Buy & hold 1 NQ | **Pyramid (as specified)** | Whipsaw stop-outs | Cost of stop-outs | P&L of units held at the end | Max contracts | Worst drawdown from peak |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for y, x in A.iterrows():
        print(f"| {yl(y)} | {x.price_chg_pct:+.1f}% | {k(x.buy_hold_1u_usd)} | **{k(x.total_pnl_usd)}** | {x.stopouts} | "
              f"{k(x.stopout_loss_usd)} | {k(x.held_units_pnl_usd)} | {x.max_units} | {k(x.max_drawdown_usd)} |")
    t = A.sum(numeric_only=True)
    print(f"| **Total** | | **{k(t.buy_hold_1u_usd)}** | **{k(t.total_pnl_usd)}** | {int(t.stopouts)} | {k(t.stopout_loss_usd)} | {k(t.held_units_pnl_usd)} | | |")
    print("\n### variants\n")
    keys = ["A", "D", "E", "B", "C"]
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
    print("\n### step/stop (core=True)\n")
    ss = pd.read_csv(os.path.join(r, "sensitivity_step_stop.csv"))
    for core in (True,):
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
    print("| Max add-ons | " + " | ".join(yl(y) for y in tot.columns) + " | 5-yr total | Worst drawdown |")
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


if __name__ == "__main__":
    main()
