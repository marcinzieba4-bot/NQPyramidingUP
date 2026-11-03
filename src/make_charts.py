"""Charts for the README (static PNG, light theme).
Usage: python3 -I src/make_charts.py --results results
"""
import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mt  # noqa: E402
import pandas as pd  # noqa: E402

SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
COL = {"A": "#2a78d6", "D": "#eb6834", "B": "#1baf7a", "BH": "#898781"}
NAME = {"A": "A  as specified (core unit, no stop)",
        "D": "D  first unit also stopped",
        "B": "B  add on every +1% at any price",
        "BH": "Buy & hold 1 contract"}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "grid.linestyle": "-", "axes.spines.top": False, "axes.spines.right": False,
    "font.family": "sans-serif", "font.size": 10, "axes.titlesize": 11,
    "axes.titleweight": "bold", "axes.titlelocation": "left",
})


def usd(x, _=None):
    a = abs(x)
    s = f"${a/1e6:.2f}M" if a >= 1e6 else (f"${a/1e3:.0f}K" if a >= 1e3 else f"${a:.0f}")
    return ("-" if x < 0 else "") + s


def usd_axis(x, _=None):
    a = abs(x)
    s = (f"${a/1e6:g}M" if a >= 1e6 else (f"${a/1e3:g}K" if a >= 1e3 else f"${a:.0f}"))
    return ("-" if x < 0 else "") + s


def yearly_bars(res, out):
    d = pd.read_csv(os.path.join(res, "summary_all_variants.csv"))
    years = sorted(d.year.unique())
    piv = d.pivot(index="year", columns="key", values="total_pnl_usd")
    bh = d[d.key == "A"].set_index("year")["buy_hold_1u_usd"]
    series = [("A", piv["A"]), ("D", piv["D"]), ("B", piv["B"]), ("BH", bh)]
    fig, ax = plt.subplots(figsize=(10, 5.4), dpi=150)
    w = 0.19
    for j, (k, s) in enumerate(series):
        xs = [i + (j - 1.5) * (w + 0.012) for i in range(len(years))]
        ax.bar(xs, s.values, width=w, color=COL[k], label=NAME[k], zorder=3)
        if k == "A":       # label only the strategy as specified
            for x, v in zip(xs, s.values):
                ax.annotate(usd(v), (x, v), xytext=(0, 4 if v >= 0 else -12),
                            textcoords="offset points", ha="center", fontsize=8.5, color=INK)
    ax.axhline(0, color=AXIS, lw=1, zorder=2)
    ax.set_xticks(range(len(years)))
    ax.set_xticklabels([f"{y}" + (" YTD*" if y == 2026 else "") for y in years], color=INK2)
    ax.yaxis.set_major_formatter(mt.FuncFormatter(usd_axis))
    ax.grid(axis="x", visible=False)
    ax.set_title("Net P&L per year, 1 unit = 1 NQ contract ($20/pt)   (MNQ: divide by 10)")
    lo, hi = ax.get_ylim()
    ax.set_ylim(lo, hi + (hi - lo) * 0.22)          # headroom for the legend row
    ax.legend(frameon=False, loc="upper left", ncol=2, fontsize=9)
    fig.text(0.01, 0.01, "*2026: Jan 2 - Nov 2, positions marked at the Nov 2 close. Costs: 0.5 pt slippage "
             "+ $2.50 commission per side.  Carry-adjusted (rolled NQ).", fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(os.path.join(out, "pnl_by_year.png"))
    plt.close(fig)


def anatomy(res, out, year):
    eqA = pd.read_csv(os.path.join(res, "equity", f"A_{year}.csv"), index_col=0, parse_dates=True)
    eqB = pd.read_csv(os.path.join(res, "equity", f"B_{year}.csv"), index_col=0, parse_dates=True)
    meta = pd.read_csv(os.path.join(res, "year_meta.csv")).set_index("year").loc[year]
    fig, axs = plt.subplots(3, 1, figsize=(10, 8.2), dpi=150, sharex=True,
                            gridspec_kw={"height_ratios": [1.15, 0.85, 1.15]})
    ax = axs[0]
    ax.plot(eqA.index, eqA.nq, color=INK2, lw=1.2)
    ax.axhline(meta.P0, color=MUTED, lw=1)
    ax.annotate(f"January start {meta.P0:,.0f}", (eqA.index[-1], meta.P0), xytext=(0, 4),
                textcoords="offset points", fontsize=8.5, color=INK2, ha="right")
    ax.set_title(f"{year}{' (YTD to Nov 2)' if year == 2026 else ''}:  NQ price (carry-adjusted, hourly)")
    ax.yaxis.set_major_formatter(mt.StrMethodFormatter("{x:,.0f}"))
    ax = axs[1]
    ax.step(eqA.index, eqA.units, where="post", color=COL["A"], lw=1.6, label=NAME["A"])
    ax.step(eqB.index, eqB.units, where="post", color=COL["B"], lw=1.6, label=NAME["B"])
    ax.set_title("Contracts held")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax = axs[2]
    ax.plot(eqA.index, eqA.equity_usd, color=COL["A"], lw=1.8, label=NAME["A"])
    ax.plot(eqB.index, eqB.equity_usd, color=COL["B"], lw=1.8, label=NAME["B"])
    ax.axhline(0, color=AXIS, lw=1)
    for e, k in ((eqA, "A"), (eqB, "B")):
        v = e.equity_usd.iloc[-1]
        ax.annotate(usd(v), (e.index[-1], v), xytext=(4, -3), textcoords="offset points",
                    fontsize=8.5, color=INK)
    ax.set_title("Cumulative P&L, 1 unit = 1 NQ contract (marked to market)")
    ax.yaxis.set_major_formatter(mt.FuncFormatter(usd_axis))
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    span = eqA.index[-1] - eqA.index[0]
    axs[2].set_xlim(eqA.index[0] - span * 0.01, eqA.index[-1] + span * 0.08)
    fig.tight_layout()
    fig.savefig(os.path.join(out, f"anatomy_{year}.png"))
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    a = ap.parse_args()
    out = os.path.join(a.results, "charts")
    os.makedirs(out, exist_ok=True)
    yearly_bars(a.results, out)
    for y in (2022, 2023, 2024, 2025, 2026):
        anatomy(a.results, out, y)
    print("charts written to", out)
