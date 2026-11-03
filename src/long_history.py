"""Yearly NQ-equivalent price segments for 2008-2026 from three intraday sources.

  2008-2010  hourly NQ futures bars (Hugging Face "Sjdsafari/Nasdaq_60min_2007_to_2023":
             an additively roll-adjusted NQ series stamped in Tehran time at bar end).
             Point changes equal a rolled NQ position, so each year is simply shifted to
             the real NQ front-month level on its first day.
  2011-2021  HistData NSXUSD 1-minute (Nasdaq-100 CFD), same treatment as Dukascopy:
             scaled to the NQ level and carry-calibrated to the real rolled NQ move.
  2022-2026  Dukascopy USATECHIDXUSD 1-minute (as in the main backtest).
"""
from __future__ import annotations

import os
from io import StringIO

import numpy as np
import pandas as pd

from nq_series import (ET, build_year_calibrated, load_cfd, load_yahoo, rolled_nq_points,
                       year_window)

HF_COLS = "Id,TimeStamp,Open,Close,High,Low,Volume,Ask,Bid,IsFirst,TotalTick,LastPrice,Side".split(",")


def source_for(year):
    return "hourly NQ (HF)" if year <= 2010 else ("HistData 1-min" if year <= 2021 else "Dukascopy 1-min")


def load_hf60(hf_dir):
    p1 = pd.read_csv(os.path.join(hf_dir, "part_p1.csv"))
    p2 = pd.read_csv(StringIO(open(os.path.join(hf_dir, "part_p2.csv")).read()), header=None, names=HF_COLS)
    df = pd.concat([p1, p2], ignore_index=True)
    local_end = pd.to_datetime(df.TimeStamp, format="%m/%d/%Y %I:%M:%S %p")
    end = local_end.dt.tz_localize("Asia/Tehran", ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
    bars = pd.DataFrame({"open": df.Open.values, "high": df.High.values, "low": df.Low.values,
                         "close": df.Close.values}, index=end - pd.Timedelta(hours=1))
    bars = bars[bars.index.notna()]
    return bars[~bars.index.duplicated()].sort_index()


def hf_year(hf, ndx, nqf, year, rolled, last_date=None):
    d0, d1, t0, t1 = year_window(hf, ndx, year, last_date)
    bars = hf.loc[t0 - pd.Timedelta(minutes=30): t1 - pd.Timedelta(minutes=1)].copy()
    c16 = (d0.tz_localize(ET) + pd.Timedelta(hours=16)).tz_convert("UTC")
    at_close = hf["close"].loc[:c16 - pd.Timedelta(minutes=1)].iloc[-1]   # bar ending 16:00 ET
    offset = at_close - nqf.loc[d0, "close"]
    bars -= offset
    yr = rolled[(rolled.index >= d0) & (rolled.index <= d1)]
    c_last = bars["close"].iloc[-1]
    meta = dict(year=year, first_day=d0.date(), last_day=d1.date(), source=source_for(year),
                P0=bars["open"].iloc[0], P_end=c_last, ndx_open=ndx.loc[d0, "open"],
                ndx_close=ndx.loc[d1, "close"], bars=len(bars),
                model_pts=c_last - (at_close - offset), real_pts=yr.pts.iloc[1:].sum())
    return bars, meta


def load_segments(years, dukascopy_csv, histdata_csv, hf_dir, yahoo_dir):
    ndx = load_yahoo(yahoo_dir, "NDX")
    nqf = load_yahoo(yahoo_dir, "NQ_F")
    irx = load_yahoo(yahoo_dir, "IRX")
    rolled = rolled_nq_points(nqf, ndx)
    duk = load_cfd(dukascopy_csv)
    last_date = min(ndx.index[-1], duk.index[-1].tz_convert(ET).normalize().tz_localize(None))
    hist = load_cfd(histdata_csv) if any(2011 <= y <= 2021 for y in years) else None
    hf = load_hf60(hf_dir) if any(y <= 2010 for y in years) else None
    segments, metas = [], []
    for y in years:
        if y <= 2010:
            bars, meta = hf_year(hf, ndx, nqf, y, rolled)
        else:
            src = hist if y <= 2021 else duk
            bars, meta, check = build_year_calibrated(src, ndx, nqf, irx, y, last_date, rolled)
            meta.update(source=source_for(y), real_pts=check[1], model_pts=check[3])
        segments.append(bars[["open", "high", "low", "close"]])
        metas.append(meta)
    return segments, metas, dict(ndx=ndx, nqf=nqf, irx=irx, hf=hf, rolled=rolled, last_date=last_date)


def boundary_ratios(metas):
    """Level jump between consecutive yearly series (new front-month basis, carry reset).
    Same CFD source on both sides: exact (scale_new / scale_old, net of the old year's
    carry), as in run_recovery.py.  Otherwise measured against the cash index:
    (P0 / NDX open of the new year) / (P_end / NDX close of the old year)."""
    out = [None]
    for prev, cur in zip(metas[:-1], metas[1:]):
        if prev["source"] == cur["source"] and "K_basis" in prev:
            s = cur["P0"] / (cur["K_basis"] * cur["cfd_align"])
            out.append(cur["P0"] / (prev["K_basis"] * prev["cfd_align"] * s - prev["carry_pts"]))
        else:
            out.append((cur["P0"] / cur["ndx_open"]) / (prev["P_end"] / prev["ndx_close"]))
    return out
