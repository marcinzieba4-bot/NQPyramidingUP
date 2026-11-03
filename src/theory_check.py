"""Compare backtest results with the closed-form approximation of the ladder.

For a 1%-grid ladder whose units are stopped one grid step below entry, the
open position is (almost) a function of price only, so by Ito / grid counting:

  number of stop-outs       ~ RV / (2 d^2)          d = ln(1.01), RV = realised
                                                     variance of ln(price) while
                                                     the ladder is active
  whipsaw cost              ~ stop-outs * d * P      (each costs ~1% of price)
  trend payoff (units held) =  sum_k (P_end - L_k)  over grid levels between the
                               anchor (January price for D, year low for B) and P_end
                            ~ P * ln(P_end/anchor)^2 / (2 d)

  => ladder P&L ~ P/(2d) * [ ln(P_end/anchor)^2 - RV ]

i.e. the ladder makes money only if the move from the anchor, squared, beats
the realised variance it had to sit through.
Usage: python3 -I src/theory_check.py --results results
"""
import argparse
import math
import os

import numpy as np
import pandas as pd

PV = 20.0
D = math.log(1.01)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    a = ap.parse_args()
    meta = pd.read_csv(os.path.join(a.results, "year_meta.csv")).set_index("year")
    summ = pd.read_csv(os.path.join(a.results, "summary_all_variants.csv"))
    rows = []
    for y, m in meta.iterrows():
        for key in ("D", "B"):
            px = pd.read_csv(os.path.join(a.results, "equity", f"{key}_{y}.csv"), index_col=0)["nq"]
            lr = np.log(px).diff().dropna()
            prev = px.shift(1).reindex(lr.index)
            if key == "D":      # grid anchored at the January price, unit 0 included
                anchor, k0 = m.P0, 0
                mask, active = prev > m.P0 * 0.99, px[px > m.P0 * 0.99]
            else:               # grid everywhere: units held = levels between year low and end
                anchor = px.min()
                k0 = math.ceil(math.log(anchor / m.P0) / D - 1e-9)
                mask, active = prev > 0, px
            rv = float((lr[mask] ** 2).sum())
            pbar = active.mean() if len(active) else m.P0
            k1 = math.floor(math.log(m.P_end / m.P0) / D + 1e-9)
            trend = sum(m.P_end - m.P0 * math.exp(D * k) for k in range(k0, k1 + 1)) * PV
            n_pred = rv / (2 * D * D)
            whip_pred = -n_pred * 0.01 * pbar * PV
            move = math.log(m.P_end / anchor) ** 2 * (m.P_end > anchor)
            s = summ[(summ.year == y) & (summ.key == key)].iloc[0]
            rows.append(dict(
                year=y, variant=key,
                move_from_anchor_pct=round((m.P_end / anchor - 1) * 100, 1),
                trend_sq=round(move, 4), realised_var=round(rv, 4),
                edge_ratio=round(move / rv, 2) if rv else np.nan,
                stopouts_pred=round(n_pred), stopouts_actual=int(s.stopouts),
                ladder_pnl_pred=round(trend + whip_pred, -3), ladder_pnl_actual=round(s.ladder_pnl_usd, -3),
            ))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(a.results, "theory_check.csv"), index=False)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
