"""Decode cached Dukascopy day files (BID+ASK) into one mid-price 1-min CSV.
Usage: python3 -I src/build_bars.py --raw DATA_DIR/raw --out DATA_DIR/NAS100_1min_mid.csv.gz [--start ...] [--end ...]
"""
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_dukascopy import decode  # noqa: E402


def build(raw, start, end, sym="USATECHIDXUSD"):
    frames, missing = [], []
    for d in pd.date_range(start, end, freq="D"):
        fb = os.path.join(raw, f"{sym}_BID_{d:%Y%m%d}.bi5")
        fa = os.path.join(raw, f"{sym}_ASK_{d:%Y%m%d}.bi5")
        if not (os.path.exists(fb) and os.path.exists(fa)):
            missing.append(d.date())
            continue
        b, k = decode(fb, d.date()), decode(fa, d.date())
        if b is None or k is None:
            continue
        m = b.merge(k, on="ts", suffixes=("_b", "_a"))
        m = m[(m.v_b > 0) | (m.v_a > 0)]          # drop padded closed-market minutes
        if m.empty:
            continue
        frames.append(pd.DataFrame({
            "ts": m.ts,
            "open": (m.o_b + m.o_a) / 2, "high": (m.h_b + m.h_a) / 2,
            "low": (m.l_b + m.l_a) / 2, "close": (m.c_b + m.c_a) / 2,
            "spread": m.c_a - m.c_b,
        }))
    bars = pd.concat(frames, ignore_index=True).sort_values("ts")
    return bars, missing


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--start", default="2021-12-27")
    ap.add_argument("--end", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    a = ap.parse_args()
    bars, missing = build(a.raw, a.start, a.end)
    bars.to_csv(a.out, index=False, float_format="%.3f")
    print(f"{len(bars):,} bars {bars.ts.iloc[0]} -> {bars.ts.iloc[-1]}; missing days: {len(missing)} {missing[:10]}")
