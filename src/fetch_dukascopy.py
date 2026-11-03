"""Download 1-minute BID+ASK candles for the Dukascopy Nasdaq-100 CFD
(USATECHIDXUSD) and build one mid-price 1-minute bar file.

Dukascopy's free datafeed is used because free *intraday* NQ futures history
going back to 2022 is not available; the CFD trades ~23h/day like NQ and tracks
the Nasdaq-100 tick by tick.  Price levels are rescaled / carry-adjusted to NQ
futures later (see build_nq_series.py).

Usage:
    python3 -I src/fetch_dukascopy.py --out DATA_DIR --start 2021-12-27 --end 2026-11-03
"""
import argparse
import datetime as dt
import lzma
import os
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests

URL = "https://datafeed.dukascopy.com/datafeed/{sym}/{y:04d}/{m0:02d}/{d:02d}/{side}_candles_min_1.bi5"
REC = struct.Struct(">5i1f")          # time_offset, open, close, low, high, volume
SCALE = 1000.0                         # USATECHIDXUSD prices are int/1000


def fetch_day(session, sym, day, side, raw_dir):
    path = os.path.join(raw_dir, f"{sym}_{side}_{day:%Y%m%d}.bi5")
    if os.path.exists(path):
        return path
    url = URL.format(sym=sym, y=day.year, m0=day.month - 1, d=day.day, side=side)
    for attempt in range(6):
        try:
            r = session.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 404:
                open(path, "wb").close()
                return path
            r.raise_for_status()
            tmp = path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(r.content)
            os.replace(tmp, path)
            return path
        except Exception as e:  # network hiccup -> back off
            time.sleep(2 ** attempt)
            last = e
    raise RuntimeError(f"failed {url}: {last}")


def decode(path, day):
    blob = open(path, "rb").read()
    if not blob:
        return None
    raw = lzma.decompress(blob, format=lzma.FORMAT_AUTO)
    n = len(raw) // REC.size
    arr = np.frombuffer(raw[: n * REC.size], dtype=np.dtype([
        ("t", ">i4"), ("o", ">i4"), ("c", ">i4"), ("l", ">i4"), ("h", ">i4"), ("v", ">f4")]))
    base = pd.Timestamp(day, tz="UTC")
    df = pd.DataFrame({
        "ts": base + pd.to_timedelta(arr["t"].astype(np.int64), unit="s"),
        "o": arr["o"] / SCALE, "h": arr["h"] / SCALE,
        "l": arr["l"] / SCALE, "c": arr["c"] / SCALE,
        "v": arr["v"].astype(np.float64),
    })
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--sym", default="USATECHIDXUSD")
    ap.add_argument("--start", default="2021-12-27")
    ap.add_argument("--end", default=dt.date.today().isoformat())
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()

    raw_dir = os.path.join(a.out, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    days = pd.date_range(a.start, a.end, freq="D")
    jobs = [(d.date(), s) for d in days for s in ("BID", "ASK")]
    sess = requests.Session()
    t0 = time.time()
    failed = []
    for rnd in range(4):                       # Dukascopy throttles (503): retry rounds
        todo = [(d, s) for d, s in jobs if not os.path.exists(
            os.path.join(raw_dir, f"{a.sym}_{s}_{d:%Y%m%d}.bi5"))]
        if not todo:
            break
        failed = []
        with ThreadPoolExecutor(max(1, a.workers >> rnd)) as ex:
            futs = {ex.submit(fetch_day, sess, a.sym, d, s, raw_dir): (d, s) for d, s in todo}
            for i, f in enumerate(futs, 1):
                try:
                    f.result()
                except Exception as e:
                    failed.append(futs[f])
                if i % 400 == 0:
                    print(f"round {rnd}: {i}/{len(futs)} files  {time.time()-t0:.0f}s", flush=True)
        time.sleep(30 * bool(failed))
    if failed:
        print(f"WARNING: {len(failed)} day files could not be downloaded: {failed[:10]}")

    frames = []
    for d in days:
        fb = os.path.join(raw_dir, f"{a.sym}_BID_{d:%Y%m%d}.bi5")
        fa = os.path.join(raw_dir, f"{a.sym}_ASK_{d:%Y%m%d}.bi5")
        if not (os.path.exists(fb) and os.path.exists(fa)):
            continue
        b, k = decode(fb, d.date()), decode(fa, d.date())
        if b is None or k is None:
            continue
        m = b.merge(k, on="ts", suffixes=("_b", "_a"))
        # Dukascopy pads closed-market minutes with zero-volume flat candles: drop them
        m = m[(m.v_b > 0) | (m.v_a > 0)]
        if m.empty:
            continue
        frames.append(pd.DataFrame({
            "ts": m.ts,
            "open": (m.o_b + m.o_a) / 2, "high": (m.h_b + m.h_a) / 2,
            "low": (m.l_b + m.l_a) / 2, "close": (m.c_b + m.c_a) / 2,
            "spread": (m.c_a - m.c_b),
        }))
    bars = pd.concat(frames, ignore_index=True).sort_values("ts")
    out = os.path.join(a.out, f"{a.sym}_1min_mid.csv.gz")
    bars.to_csv(out, index=False, float_format="%.3f")
    print(f"wrote {out}: {len(bars):,} bars {bars.ts.iloc[0]} -> {bars.ts.iloc[-1]}")


if __name__ == "__main__":
    sys.exit(main())
