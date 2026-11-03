"""Model estimate of the pyramid for every calendar year since 1986 (daily data).

There is no free 1-minute history before 2022, so this uses the closed-form
approximation that theory_check.py validates against the 1-minute backtest:

  trend payoff   = sum over 1% grid levels between anchor and year-end close of
                   (P_end - L_k)                  (exact for the held units)
  whipsaw cost   = RV / (2 d^2) stop-outs, each ~1% of price   (d = ln 1.01)

with RV = realised variance of daily log returns while the ladder is active
(price above the start for variant A; whole year for variant B).  Prices are the
Nasdaq-100 minus futures carry (13-week T-bill - 0.7% dividend yield), i.e. a
rolled NQ position.  Results are in multiples of one unit's January notional
(x 1.0 = the value of one contract at the start of the year).

Usage: python3 -I src/history_estimate.py --yahoo DATA/yahoo --results results
"""
import argparse
import math
import os

import numpy as np
import pandas as pd

D = math.log(1.01)
Q = 0.007


def load(path):
    df = pd.read_csv(path)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df["date"] = df["ts"].dt.tz_convert("America/New_York").dt.normalize().dt.tz_localize(None)
    return df.set_index("date")["close"].sort_index()


def ladder_estimate(p, anchor_px, P0, rv):
    """trend payoff of grid units between anchor and P_end, minus whipsaws,
    both in multiples of P0."""
    P_end = p.iloc[-1]
    k0 = 1 if anchor_px == P0 else math.ceil(math.log(anchor_px / P0) / D - 1e-9)
    k1 = math.floor(math.log(P_end / P0) / D + 1e-9)
    trend = sum(P_end - P0 * math.exp(D * k) for k in range(k0, k1 + 1))
    active = p[p > P0] if anchor_px == P0 else p
    pbar = active.mean() if len(active) else P0
    whip = rv / (2 * D * D) * 0.01 * pbar
    return trend / P0, -whip / P0, rv / (2 * D * D)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yahoo", required=True)
    ap.add_argument("--results", default="results")
    a = ap.parse_args()
    ndx = load(os.path.join(a.yahoo, "NDX_long_1d.csv"))
    irx = load(os.path.join(a.yahoo, "IRX_long_1d.csv")).reindex(ndx.index, method="ffill").bfill()

    rows = []
    for y in range(1986, 2027):
        prev = ndx[ndx.index.year == y - 1]
        cur = ndx[ndx.index.year == y]
        if prev.empty or cur.empty:
            continue
        P0 = prev.iloc[-1]                      # last close of previous year ~ Jan open
        raw = pd.concat([pd.Series([P0], index=[prev.index[-1]]), cur])
        # rolled-futures proxy for THIS year: subtract carry accumulated since Jan 1
        r = irx.reindex(raw.index, method="ffill").bfill().values
        days = np.diff(raw.index.values).astype("timedelta64[D]").astype(float)
        carry = raw.values[:-1] * (r[:-1] / 100 - Q) * days / 365
        p = raw - np.concatenate([[0.0], np.cumsum(carry)])
        lr = np.log(p).diff().dropna()
        above = (p.shift(1).reindex(lr.index) > P0)
        rv_all = float((lr ** 2).sum())
        rv_above = float((lr[above] ** 2).sum())
        P_end = p.iloc[-1]
        tA, wA, nA = ladder_estimate(p, P0, P0, rv_above)
        tB, wB, nB = ladder_estimate(p, p.min(), P0, rv_all)
        core = P_end / P0 - 1
        rows.append(dict(
            year=y if y < 2026 else "2026 YTD", nq_chg_pct=round(core * 100, 1),
            vol_pct=round(math.sqrt(rv_all * 252 / len(lr)) * 100, 1),
            edge_ratio_A=round(max(0.0, math.log(P_end / P0)) ** 2 / rv_above, 2) if rv_above else 0.0,
            whipsaws_A=round(nA), A_total_x=round(core + tA + wA, 2), A_ladder_x=round(tA + wA, 2),
            whipsaws_B=round(nB), B_total_x=round(tB + wB, 2),
            buy_hold_x=round(core, 2),
        ))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(a.results, "history_estimate_1986_2026.csv"), index=False)
    print(df.to_string(index=False))
    full = df[df.year.astype(str).str.len() == 4].copy()
    full["year"] = full["year"].astype(int)
    stats = []
    for period, sub in (("1986-2025", full), ("2000-2025", full[full.year >= 2000])):
        for k, label in (("A_total_x", "A pyramid as specified"),
                         ("A_ladder_x", "D-like: ladder only (no core)"),
                         ("B_total_x", "B add at any price"),
                         ("buy_hold_x", "buy & hold 1 contract")):
            v = sub[k]
            stats.append(dict(period=period, strategy=label, years=len(v),
                              years_positive=int((v > 0).sum()), median=round(v.median(), 2),
                              mean=round(v.mean(), 2), stdev=round(v.std(), 2),
                              mean_over_stdev=round(v.mean() / v.std(), 2),
                              worst=round(v.min(), 2), best=round(v.max(), 2)))
    st = pd.DataFrame(stats)
    st.to_csv(os.path.join(a.results, "history_estimate_stats.csv"), index=False)
    print(st.to_string(index=False))


if __name__ == "__main__":
    main()
