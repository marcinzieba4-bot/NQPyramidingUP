"""How much does the covered-call result depend on the option-price assumptions?

Re-prices the overlay on the recovery strategy's unit trades (results/long/trades_restart.csv)
with different implied-vol levels, skew and spread costs.

Usage:
    python3 -I src/calls_sensitivity.py --dukascopy ... --histdata ... --hf ... --yahoo ... --out results
"""
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from long_history import load_segments  # noqa: E402
from nq_series import load_yahoo  # noqa: E402
from options_overlay import CallConfig, VolSurface, overlay  # noqa: E402
from run_long import YEARS  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    for k in ("dukascopy", "histdata", "hf", "yahoo"):
        ap.add_argument(f"--{k}", required=True)
    ap.add_argument("--out", default="results")
    a = ap.parse_args()
    segments, metas, ctx = load_segments(YEARS, a.dukascopy, a.histdata, a.hf, a.yahoo)
    trades = pd.read_csv(os.path.join(a.out, "long", "trades_restart.csv"))
    vxn = load_yahoo(a.yahoo, "VXN")["close"]
    irx = ctx["irx"]["close"]
    rows = []
    grid = []
    for strike, days in (("delta", 7), ("delta", 30), ("atm", 7), ("atm", 30)):
        for ratio in (0.80, 0.90, 1.00):
            grid.append((strike, days, ratio, 0.6, 0.01))
        grid.append((strike, days, 0.90, 0.3, 0.01))
        grid.append((strike, days, 0.90, 1.0, 0.01))
        grid.append((strike, days, 0.90, 0.6, 0.03))
    for strike, days, ratio, skew, cost in grid:
        cfg = CallConfig(strike=strike, days=days, vxn_to_atm=ratio, skew=skew, cost_frac=cost)
        o = overlay(trades, segments, VolSurface(vxn, irx, cfg), cfg)
        rows.append(dict(calls=("20-delta" if strike == "delta" else "ATM") + f" {days}-day",
                         atm_vol_as_share_of_vxn=ratio, skew=skew, spread_cost_share=cost,
                         option_pnl_usd=round(o.option_pnl_usd.sum()),
                         gross_before_costs_usd=round(o.option_gross_usd.sum()),
                         costs_usd=round(o.option_cost_usd.sum())))
        print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(a.out, "long", "covered_calls_sensitivity.csv"), index=False)


if __name__ == "__main__":
    main()
