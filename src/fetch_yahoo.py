"""Daily (and recent hourly) Yahoo Finance data used to (a) anchor the CFD path
to real NQ futures price levels, (b) estimate futures carry, (c) validate.

Usage: python3 -I src/fetch_yahoo.py --out DATA_DIR
"""
import argparse
import os
import time

import pandas as pd
import requests

CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}"


def chart(sym, interval, start=None, end=None, rng=None):
    params = {"interval": interval, "includePrePost": "true"}
    if rng:
        params["range"] = rng
    else:
        params["period1"] = int(pd.Timestamp(start, tz="UTC").timestamp())
        params["period2"] = int(pd.Timestamp(end, tz="UTC").timestamp())
    for attempt in range(5):
        r = requests.get(CHART.format(sym=sym), params=params,
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        if r.ok:
            break
        time.sleep(2 ** attempt)
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    df = pd.DataFrame({
        "ts": pd.to_datetime(res["timestamp"], unit="s", utc=True),
        "open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"],
        "volume": q.get("volume"),
    }).dropna(subset=["close"])
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--start", default="2021-12-01")
    ap.add_argument("--end", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    end = (pd.Timestamp(a.end) + pd.Timedelta(days=2)).strftime("%Y-%m-%d")
    for sym, name in [("NQ=F", "NQ_F"), ("^NDX", "NDX"), ("^IRX", "IRX")]:
        df = chart(sym, "1d", a.start, end)
        df.to_csv(os.path.join(a.out, f"{name}_1d.csv"), index=False)
        print(name, "1d", len(df), df.ts.iloc[0].date(), df.ts.iloc[-1].date())
    # long daily history for the 1986-2025 model estimate (history_estimate.py)
    for sym, name in [("^NDX", "NDX_long"), ("^IRX", "IRX_long")]:
        df = chart(sym, "1d", "1985-01-01", end)
        df.to_csv(os.path.join(a.out, f"{name}_1d.csv"), index=False)
        print(name, "1d", len(df), df.ts.iloc[0].date(), df.ts.iloc[-1].date())
    # recent hourly NQ futures for intraday path validation (Yahoo keeps ~730d)
    df = chart("NQ=F", "60m", rng="730d")
    df.to_csv(os.path.join(a.out, "NQ_F_60m.csv"), index=False)
    print("NQ_F 60m", len(df), df.ts.iloc[0], df.ts.iloc[-1])


if __name__ == "__main__":
    main()
