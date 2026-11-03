"""Download HistData.com 1-minute bars (free, yearly zip files) and convert them to
one CSV with UTC timestamps in the same layout as fetch_dukascopy.py.

HistData says its quotes are stamped in EST without daylight saving (UTC-5), but
the NSXUSD stamps actually move to UTC-4 during European summer time; to_utc()
handles that (verified month by month against Dukascopy UTC data, 2022-2025).
NSXUSD is a Nasdaq-100 index CFD quote; usable history starts in Nov 2010.

Usage:
    python3 -I src/fetch_histdata.py --out DATA_DIR/histdata --start 2010 --end 2025
"""
import argparse
import io
import os
import re
import time
import zipfile

import pandas as pd
import requests

PAGE = "https://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/{sym}/{year}"
GET = "https://www.histdata.com/get.php"


def fetch_year(session, sym, year, raw_dir):
    path = os.path.join(raw_dir, f"{sym.upper()}_{year}.zip")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    page = PAGE.format(sym=sym.lower(), year=year)
    for attempt in range(5):
        try:
            r = session.get(page, timeout=60)
            r.raise_for_status()
            tk = re.search(r'name="tk" id="tk" value="([^"]+)"', r.text).group(1)
            z = session.post(GET, timeout=180, headers={"Referer": page}, data={
                "tk": tk, "date": str(year), "datemonth": str(year), "platform": "ASCII",
                "timeframe": "M1", "fxpair": sym.upper()})
            z.raise_for_status()
            zipfile.ZipFile(io.BytesIO(z.content))           # raises if not a zip
            with open(path + ".tmp", "wb") as f:
                f.write(z.content)
            os.replace(path + ".tmp", path)
            return path
        except Exception as e:  # throttling / transient errors
            last = e
            time.sleep(3 * 2 ** attempt)
    raise RuntimeError(f"{sym} {year}: {last}")


def read_year(path):
    z = zipfile.ZipFile(path)
    name = [n for n in z.namelist() if n.endswith(".csv")][0]
    df = pd.read_csv(z.open(name), sep=";", header=None,
                     names=["t", "open", "high", "low", "close", "v"])
    local = pd.to_datetime(df["t"], format="%Y%m%d %H%M%S")
    df["ts"] = to_utc(local)
    return df[["ts", "open", "high", "low", "close"]]


def eu_dst_bounds(year):
    """European summer time: last Sunday of March 01:00 UTC -> last Sunday of October 01:00 UTC."""
    def last_sunday(month):
        d = pd.Timestamp(year, month, 31 if month in (3, 10) else 30)
        return d - pd.Timedelta(days=(d.dayofweek + 1) % 7)
    return (last_sunday(3) + pd.Timedelta(hours=1), last_sunday(10) + pd.Timedelta(hours=1))


def to_utc(local):
    """HistData documents its clock as EST (UTC-5) without DST, but checked against
    Dukascopy (UTC) the NSXUSD stamps are UTC-4 during *European* summer time
    (last Sunday of March -> last Sunday of October): convert accordingly."""
    utc = local + pd.Timedelta(hours=5)
    shift = pd.Series(0, index=local.index)
    for y in range(utc.dt.year.min(), utc.dt.year.max() + 1):
        a, b = eu_dst_bounds(y)
        shift[(utc >= a) & (utc < b)] = 1
    return (utc - pd.to_timedelta(shift, unit="h")).dt.tz_localize("UTC")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--sym", default="NSXUSD")
    ap.add_argument("--start", type=int, default=2010)
    ap.add_argument("--end", type=int, default=2025)
    a = ap.parse_args()
    raw = os.path.join(a.out, "raw")
    os.makedirs(raw, exist_ok=True)
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    frames = []
    for y in range(a.start, a.end + 1):
        p = fetch_year(s, a.sym, y, raw)
        df = read_year(p)
        print(y, len(df), df.ts.iloc[0], df.ts.iloc[-1], flush=True)
        frames.append(df)
        time.sleep(1)
    bars = pd.concat(frames).drop_duplicates("ts").sort_values("ts")
    out = os.path.join(a.out, f"{a.sym.upper()}_1min.csv.gz")
    bars.to_csv(out, index=False, float_format="%.3f")
    print("wrote", out, len(bars))


if __name__ == "__main__":
    main()
