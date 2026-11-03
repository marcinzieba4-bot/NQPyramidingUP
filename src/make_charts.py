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
COL = {"D": "#2a78d6", "E": "#eb6834", "B": "#1baf7a", "BH": "#898781"}
NAME = {"D": "D  as specified (every unit stopped 1% below entry)",
        "E": "E  same, never more than 10 contracts",
        "B": "B  also re-buys every +1% below the January price",
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
    bh = d[d.key == "D"].set_index("year")["buy_hold_1u_usd"]
    series = [("D", piv["D"]), ("E", piv["E"]), ("B", piv["B"]), ("BH", bh)]
    fig, ax = plt.subplots(figsize=(10, 5.4), dpi=150)
    w = 0.19
    for j, (k, s) in enumerate(series):
        xs = [i + (j - 1.5) * (w + 0.012) for i in range(len(years))]
        ax.bar(xs, s.values, width=w, color=COL[k], label=NAME[k], zorder=3)
        if k == "D":       # label only the strategy as specified
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
    eqA = pd.read_csv(os.path.join(res, "equity", f"D_{year}.csv"), index_col=0, parse_dates=True)
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
    ax.step(eqA.index, eqA.units, where="post", color=COL["D"], lw=1.6, label=NAME["D"])
    ax.step(eqB.index, eqB.units, where="post", color=COL["B"], lw=1.6, label=NAME["B"])
    ax.set_title("Contracts held")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax = axs[2]
    ax.plot(eqA.index, eqA.equity_usd, color=COL["D"], lw=1.8, label=NAME["D"])
    ax.plot(eqB.index, eqB.equity_usd, color=COL["B"], lw=1.8, label=NAME["B"])
    ax.axhline(0, color=AXIS, lw=1)
    for e, k in ((eqA, "D"), (eqB, "B")):
        v = e.equity_usd.iloc[-1]
        ax.annotate(usd(v), (e.index[-1], v), xytext=(4, -3), textcoords="offset points",
                    fontsize=8.5, color=INK)
    ax.set_title("Cumulative P&L, 1 unit = 1 NQ contract (marked to market)")
    ax.yaxis.set_major_formatter(mt.FuncFormatter(usd_axis))
    ax.legend(frameon=False, fontsize=8.5, loc="best")
    span = eqA.index[-1] - eqA.index[0]
    axs[2].set_xlim(eqA.index[0] - span * 0.01, eqA.index[-1] + span * 0.08)
    fig.tight_layout()
    fig.savefig(os.path.join(out, f"anatomy_{year}.png"))
    plt.close(fig)


OUTCOME = {"+12% target": ("#0ca30c", "reached +12% (profit taken)"),
           "cancelled (new low)": ("#d03b3b", "cancelled: selloff made a new low"),
           "closed at year end": ("#898781", "closed at year end / still open"),
           "open at end": ("#898781", "closed at year end / still open")}


def recovery_chart(res, out):
    rdir = os.path.join(res, "recovery")
    eqR = pd.read_csv(os.path.join(rdir, "equity_hourly_restart.csv"), index_col=0, parse_dates=True)
    eqC = pd.read_csv(os.path.join(rdir, "equity_hourly_continuous.csv"), index_col=0, parse_dates=True)
    cp = pd.read_csv(os.path.join(rdir, "campaigns_restart.csv"), parse_dates=["start", "end"])
    meta = pd.read_csv(os.path.join(res, "year_meta.csv")).set_index("year")
    # all-year pyramid (D) and buy & hold, chained across years
    d_parts, bh_parts, off_d, off_bh = [], [], 0.0, 0.0
    for y in meta.index:
        e = pd.read_csv(os.path.join(res, "equity", f"D_{y}.csv"), index_col=0, parse_dates=True)
        d_parts.append(e.equity_usd + off_d)
        bh = (e.nq - meta.loc[y, "P0"]) * 20.0
        bh_parts.append(bh + off_bh)
        off_d += e.equity_usd.iloc[-1]
        off_bh += bh.iloc[-1]
    eqD, eqBH = pd.concat(d_parts), pd.concat(bh_parts)

    fig, axs = plt.subplots(3, 1, figsize=(11, 8.6), dpi=150, sharex=True,
                            gridspec_kw={"height_ratios": [1.3, 0.7, 1.2]})
    ax = axs[0]
    ax.plot(eqR.index, eqR.nasdaq100, color=INK2, lw=1.0, zorder=3)
    seen = set()
    for _, c in cp.iterrows():
        col, lab = OUTCOME[c.outcome]
        ax.axvspan(c.start, c.end, color=col, alpha=0.16, lw=0,
                   label=None if lab in seen else lab, zorder=1)
        seen.add(lab)
        ax.plot([c.start], [eqR.nasdaq100.asof(c.start)], "o", ms=5, color=col,
                mec=SURFACE, mew=1.2, zorder=4)
    ax.set_title("Nasdaq-100 (hourly) with each recovery campaign shaded; dot = entry at the 70% level")
    ax.yaxis.set_major_formatter(mt.StrMethodFormatter("{x:,.0f}"))
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax = axs[1]
    ax.step(eqR.index, eqR.units, where="post", color=COL["D"], lw=1.3)
    ax.set_title("Contracts held: recovery entries (restart each January)")
    ax = axs[2]
    lines = [(eqR, "equity_usd", COL["D"], "Recovery entries (restart each January)"),
             (eqC, "equity_usd", COL["E"], "Recovery entries (run straight through)"),
             (eqD.to_frame("v"), "v", COL["B"], "D  pyramid from the January open"),
             (eqBH.to_frame("v"), "v", COL["BH"], "Buy & hold 1 contract")]
    for df, col, color, lab in lines:
        ax.plot(df.index, df[col], color=color, lw=1.6, label=lab)
        ax.annotate(usd(df[col].iloc[-1]), (df.index[-1], df[col].iloc[-1]), xytext=(4, -3),
                    textcoords="offset points", fontsize=8.5, color=INK)
    ax.axhline(0, color=AXIS, lw=1)
    ax.set_title("Cumulative P&L since Jan 2022, 1 unit = 1 NQ contract")
    ax.yaxis.set_major_formatter(mt.FuncFormatter(usd_axis))
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    span = eqR.index[-1] - eqR.index[0]
    axs[2].set_xlim(eqR.index[0] - span * 0.01, eqR.index[-1] + span * 0.07)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "recovery_2022_2026.png"))
    plt.close(fig)


def long_charts(res, out):
    ld = os.path.join(res, "long")
    s = pd.read_csv(os.path.join(ld, "summary_by_year.csv")).set_index("year")
    eq = pd.read_csv(os.path.join(ld, "equity_daily.csv"), index_col=0, parse_dates=True)
    cp = pd.read_csv(os.path.join(ld, "campaigns_restart.csv"), parse_dates=["start", "end"])
    # yearly bars
    fig, ax = plt.subplots(figsize=(12, 5.2), dpi=150)
    yrs = list(s.index)
    w = 0.27
    series = [("recovery_usd", COL["D"], "Recovery entries (5% pullback, 70% entry, +12% reset)"),
              ("D_usd", COL["B"], "D  pyramid from the January open"),
              ("buy_hold_usd", COL["BH"], "Buy & hold 1 contract")]
    for j, (col, color, lab) in enumerate(series):
        ax.bar([i + (j - 1) * (w + 0.02) for i in range(len(yrs))], s[col].values, width=w,
               color=color, label=lab, zorder=3)
    ax.axhline(0, color=AXIS, lw=1, zorder=2)
    ax.set_xticks(range(len(yrs)))
    ax.set_xticklabels([f"{y}" if y < 2026 else "2026\nYTD" for y in yrs], fontsize=8.5, color=INK2)
    ax.yaxis.set_major_formatter(mt.FuncFormatter(usd_axis))
    ax.grid(axis="x", visible=False)
    ax.set_title("Net P&L per year 2008-2026, 1 unit = 1 NQ contract  (MNQ: divide by 10)")
    lo, hi = ax.get_ylim()
    ax.set_ylim(lo, hi + (hi - lo) * 0.18)
    ax.legend(frameon=False, loc="upper left", ncol=2, fontsize=8.5)
    fig.text(0.01, 0.01, "2008-2010 simulated on hourly NQ bars; 2011-2026 on 1-minute bars. "
             "Each year starts fresh in January.", fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(os.path.join(out, "long_pnl_by_year.png"))
    plt.close(fig)
    # cumulative
    fig, axs = plt.subplots(2, 1, figsize=(12, 7.6), dpi=150, sharex=True,
                            gridspec_kw={"height_ratios": [1.0, 1.25]})
    ax = axs[0]
    ax.plot(eq.index, eq.nq_level, color=INK2, lw=0.9, zorder=3)
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(mt.StrMethodFormatter("{x:,.0f}"))
    ax.yaxis.set_minor_formatter(mt.NullFormatter())
    seen = set()
    for _, c in cp.iterrows():
        col, lab = OUTCOME.get(c.outcome, ("#898781", "closed at year end / still open"))
        if c.outcome.startswith("abandoned"):
            col, lab = "#898781", "closed at year end / still open"
        ax.axvspan(c.start, c.end, color=col, alpha=0.18, lw=0, label=None if lab in seen else lab, zorder=1)
        seen.add(lab)
    ax.set_title("NQ (log scale) with each recovery campaign shaded")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax = axs[1]
    lines = [("D", COL["B"], "D  pyramid from the January open"),
             ("recovery + sell 20-delta 7-day calls", COL["E"], "Recovery entries + sell 20-delta 7-day calls"),
             ("recovery", COL["D"], "Recovery entries"),
             ("buy_hold", COL["BH"], "Buy & hold 1 contract")]
    for col, color, lab in lines:            # final value in the legend (end labels would collide)
        if col in eq:
            v = eq[col].dropna()
            ax.plot(v.index, v.values, color=color, lw=1.5, label=f"{lab}:  {usd(v.iloc[-1])}")
    ax.axhline(0, color=AXIS, lw=1)
    ax.set_title("Cumulative P&L since Jan 2008, 1 unit = 1 NQ contract")
    ax.yaxis.set_major_formatter(mt.FuncFormatter(usd_axis))
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    axs[0].yaxis.set_major_locator(mt.LogLocator(base=10, subs=(1.0, 2.0, 5.0)))
    span = eq.index[-1] - eq.index[0]
    axs[1].set_xlim(eq.index[0] - span * 0.01, eq.index[-1] + span * 0.01)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "long_2008_2026.png"))
    plt.close(fig)


def breakout_chart(res, out):
    v = pd.read_csv(os.path.join(res, "breakout", "variants.csv")).set_index("variant")
    s = pd.read_csv(os.path.join(res, "breakout", "summary_by_year.csv")).set_index("year")
    years = [y for y in s.index]
    cols = [str(y) for y in years]
    base = v.index[0]
    lines = [(v.loc[base, cols].astype(float), COL["D"], "Breakout as specified (3% pullback, +5% target, 0.5% step)"),
             (v.loc["target +3%", cols].astype(float), COL["E"], "Breakout, +3% target"),
             (v.loc["5% pullback", cols].astype(float), "#eda100", "Breakout, 5% pullback"),
             (s["recovery_usd"].astype(float), COL["B"], "Recovery entries (5% pullback, 70% entry, +12% reset)"),
             (s["buy_hold_usd"].astype(float), COL["BH"], "Buy & hold 1 contract")]
    fig, ax = plt.subplots(figsize=(11, 5.6), dpi=150)
    for ser, color, lab in lines:
        cum = pd.Series(ser.values, index=years).cumsum()
        ax.plot(years, cum.values, color=color, lw=1.8, marker="o", ms=3.5,
                label=f"{lab}:  {usd(cum.iloc[-1])}")
    ax.axhline(0, color=AXIS, lw=1)
    ax.set_xticks(years)
    ax.set_xticklabels([str(y) if y < 2026 else "2026\nYTD" for y in years], fontsize=8.5, color=INK2)
    ax.grid(axis="x", visible=False)
    ax.yaxis.set_major_formatter(mt.FuncFormatter(usd_axis))
    ax.set_title("Cumulative P&L through each year, 2008-2026, 1 unit = 1 NQ contract")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    fig.text(0.01, 0.01, "Each year starts fresh in January. 2026 = to Nov 2. The pyramid from the January open "
             "(+$4.40M) is left out to keep the scale readable.", fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(os.path.join(out, "breakout_2008_2026.png"))
    plt.close(fig)


def variant_chart(res, name, title, out):
    vd = os.path.join(res, name)
    eq = pd.read_csv(os.path.join(vd, "equity_daily.csv"), index_col=0, parse_dates=True)
    led = pd.read_csv(os.path.join(res, "long", "equity_daily.csv"), index_col=0, parse_dates=True)
    fig, ax = plt.subplots(figsize=(11, 5.6), dpi=150)
    lines = [(eq["variant + sell 20-delta 7-day calls"], COL["E"], f"{title} + sell 20-delta 7-day calls"),
             (eq["variant"], COL["D"], title),
             (eq["variant + sell 20-delta 30-day calls"], "#eda100", f"{title} + sell 20-delta 30-day calls"),
             (led["recovery"], COL["B"], "Recovery entries at 70% (previous base)"),
             (led["buy_hold"], COL["BH"], "Buy & hold 1 contract")]
    order = sorted(lines, key=lambda t: -t[0].dropna().iloc[-1])      # legend in end-value order
    for ser, color, lab in order:
        v = ser.dropna()
        ax.plot(v.index, v.values, color=color, lw=1.5, label=f"{lab}:  {usd(v.iloc[-1])}")
    ax.axhline(0, color=AXIS, lw=1)
    ax.yaxis.set_major_formatter(mt.FuncFormatter(usd_axis))
    ax.set_title("Cumulative P&L since Jan 2008, 1 unit = 1 NQ contract  (MNQ: divide by 10)")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    fig.text(0.01, 0.01, "Each year starts fresh in January; 2026 = to Nov 2. Calls priced with Black-76 at "
             "0.9 x VXN (base assumption); option P&L booked when each contract is closed.",
             fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(os.path.join(out, f"{name}_2008_2026.png"))
    plt.close(fig)


def sizing_chart(res, out):
    sd = os.path.join(res, "sizing")
    eq = pd.read_csv(os.path.join(sd, "equity_daily_100k_per_unit.csv"), index_col=0, parse_dates=True)
    lines = [("Pyramid from the January open (D)", COL["B"]),
             ("Recovery 70%, reset +20%", COL["E"]),
             ("Recovery, entry 61.8%", COL["D"]),
             ("Recovery, entry 70% (base)", "#6250d6"),
             ("Buy & hold ($100k each January)", COL["BH"])]
    worst = pd.read_csv(os.path.join(sd, "calmar_100k_per_unit.csv")).set_index("version")["max_drawdown"]
    esc = lambda t: t.replace("$", r"\$")          # keep matplotlib from reading $...$ as math
    fig, axs = plt.subplots(2, 1, figsize=(11, 8.2), dpi=150, sharex=True,
                            gridspec_kw={"height_ratios": [1.3, 1.0]})
    for col, color in lines:
        v = eq[col].dropna()
        axs[0].plot(v.index, v.values, color=color, lw=1.5, label=esc(f"{col}:  {usd(v.iloc[-1])}"))
        dd = v - v.cummax()
        axs[1].plot(dd.index, dd.values, color=color, lw=1.3,
                    label=esc(f"{col}: worst {usd(worst[col])}"))
    for ax in axs:
        ax.axhline(0, color=AXIS, lw=1)
        ax.yaxis.set_major_formatter(mt.FuncFormatter(lambda x, _: esc(usd_axis(x))))
        ax.legend(frameon=False, fontsize=8.5, loc="upper left" if ax is axs[0] else "lower left")
    axs[0].set_title(esc("Cumulative P&L per $100k unit (each run sized at $100k of NQ, no reinvestment)"))
    axs[1].set_title(esc("Drawdown from the previous peak, per $100k unit (daily closes; worst value from 1-minute data)"))
    fig.text(0.01, 0.01, esc("1 unit = $100k of NQ at the start of each run (about 1.8 MNQ at today's price). "
             "Each year starts fresh in January; 2026 = to Nov 2."), fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(os.path.join(out, "sizing_100k_per_unit.png"))
    plt.close(fig)


def best_calls_chart(res, out):
    bd = os.path.join(res, "best_calls")
    eq = pd.read_csv(os.path.join(bd, "equity_daily.csv"), index_col=0, parse_dates=True)
    sz = pd.read_csv(os.path.join(res, "sizing", "equity_daily_100k_per_unit.csv"), index_col=0, parse_dates=True)
    sm = pd.read_csv(os.path.join(bd, "summary.csv")).set_index("version")
    esc = lambda t: t.replace("$", r"\$")
    lines = [("sell 20-delta 7-day calls", COL["E"], "Recovery 70% / +20% + sell 20-delta 7-day calls",
              "sell 20-delta 7-day calls @ 0.9 x VXN"),
             ("sell 20-delta 30-day calls", "#eda100", "Recovery 70% / +20% + sell 20-delta 30-day calls",
              "sell 20-delta 30-day calls @ 0.9 x VXN"),
             ("no calls", COL["D"], "Recovery 70% / +20%, no calls", "no calls")]
    fig, axs = plt.subplots(2, 1, figsize=(11, 8.0), dpi=150, sharex=True,
                            gridspec_kw={"height_ratios": [1.3, 1.0]})
    for col, color, lab, key in lines:
        v = eq[col].dropna()
        axs[0].plot(v.index, v.values, color=color, lw=1.5,
                    label=esc(f"{lab}:  {usd(v.iloc[-1])}, Calmar {sm.loc[key, 'calmar']:.2f}"))
        dd = v - v.cummax()
        axs[1].plot(dd.index, dd.values, color=color, lw=1.3,
                    label=esc(f"{lab}: worst {usd(sm.loc[key, 'max_drawdown'])}"))
    bh = sz["Buy & hold ($100k each January)"].dropna()
    bh_calmar = pd.read_csv(os.path.join(res, "sizing", "calmar_100k_per_unit.csv")).set_index("version").loc[
        "Buy & hold ($100k each January)", "calmar"]
    axs[0].plot(bh.index, bh.values, color=COL["BH"], lw=1.3,
                label=esc(f"Buy & hold:  {usd(bh.iloc[-1])}, Calmar {bh_calmar:.2f}"))
    for ax in axs:
        ax.axhline(0, color=AXIS, lw=1)
        ax.yaxis.set_major_formatter(mt.FuncFormatter(lambda x, _: esc(usd_axis(x))))
        ax.legend(frameon=False, fontsize=8.5, loc="upper left" if ax is axs[0] else "lower left")
    axs[0].set_title(esc("Cumulative P&L per $100k unit, no reinvestment (calls priced at 0.9 x VXN)"))
    axs[1].set_title(esc("Drawdown from the previous peak, per $100k unit (daily closes; worst value from 1-minute data)"))
    fig.text(0.01, 0.01, esc("1 call sold per contract held; Black-76 from VXN with skew; option P&L booked when each "
             "contract is closed. Weekly NQ options did not exist before ~2013."), fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(os.path.join(out, "best_calls_100k_per_unit.png"))
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
    if os.path.exists(os.path.join(a.results, "recovery", "campaigns_restart.csv")):
        recovery_chart(a.results, out)
    if os.path.exists(os.path.join(a.results, "long", "equity_daily.csv")):
        long_charts(a.results, out)
    if os.path.exists(os.path.join(a.results, "breakout", "variants.csv")):
        breakout_chart(a.results, out)
    if os.path.exists(os.path.join(a.results, "recovery30", "equity_daily.csv")):
        variant_chart(a.results, "recovery30", "Recovery entries at 30%", out)
    if os.path.exists(os.path.join(a.results, "sizing", "equity_daily_100k_per_unit.csv")):
        sizing_chart(a.results, out)
    if os.path.exists(os.path.join(a.results, "best_calls", "equity_daily.csv")):
        best_calls_chart(a.results, out)
    print("charts written to", out)
