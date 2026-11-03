"""Turn the 1-minute Nasdaq-100 CFD path into an NQ-futures-equivalent path.

NQ futures = cash index * (1 + basis).  The basis decays to zero into every
quarterly expiry and is re-established at each roll, so a trader who holds NQ
and rolls it earns the index move MINUS the financing carry (T-bill rate minus
dividend yield, ~4%/yr in 2023-24, ~0% in early 2022).  We model a rolled
(back-adjusted) NQ position as

    NQ(t) = K_y * S(t) - D(t),     D(t) = sum K_y * S * (r - q) * dt / 365

  S(t)  : 1-minute CFD mid price (tracks the cash Nasdaq-100)
  K_y   : NQ front-month / NDX ratio on the first day of year y (price level
          equals the real NQ contract on the start date)
  r     : 13-week T-bill yield (Yahoo ^IRX), q: Nasdaq-100 dividend yield 0.7%,
          plus a per-year financing spread calibrated so that the year's move
          equals the real rolled NQ contract (Yahoo NQ=F, roll jumps removed)
  D(t)  : accumulated carry in NQ points (subtracted, like a Panama roll adjust)

Point P&L of a unit is therefore the real P&L of an NQ position that is rolled
each quarter; the grid/stops are computed on this adjusted price.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

ET = "America/New_York"
DIV_YIELD = 0.007


def load_cfd(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df.set_index("ts").sort_index()


def load_yahoo(ydir: str, name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(ydir, f"{name}_1d.csv"))
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df["date"] = df["ts"].dt.tz_convert(ET).dt.normalize().dt.tz_localize(None)
    return df.set_index("date").sort_index()


def cfd_at_close(cfd: pd.DataFrame, dates) -> pd.Series:
    """CFD price at 16:00 ET (cash close) for each date (last bar <= 16:00)."""
    out = {}
    close = cfd["close"]
    for d in dates:
        t = pd.Timestamp(d).tz_localize(ET) + pd.Timedelta(hours=16)
        s = close.loc[:t.tz_convert("UTC")]
        if len(s) and (t.tz_convert("UTC") - s.index[-1]) < pd.Timedelta(minutes=30):
            out[d] = s.iloc[-1]
    return pd.Series(out)


def year_window(cfd, ndx, year, last_date=None):
    """First RTH open (9:30 ET) of the year's first session -> 16:00 ET close of
    the last December session (or of `last_date` for an unfinished year)."""
    days = ndx.index[(ndx.index.year == year)]
    if last_date is not None:
        days = days[days <= pd.Timestamp(last_date)]
    d0, d1 = days[0], days[-1]
    t0 = (d0.tz_localize(ET) + pd.Timedelta(hours=9, minutes=30)).tz_convert("UTC")
    t1 = (d1.tz_localize(ET) + pd.Timedelta(hours=16)).tz_convert("UTC")
    return d0, d1, t0, t1


def build_year(cfd, ndx, nqf, irx, year, last_date=None, carry=True, spread=0.0):
    d0, d1, t0, t1 = year_window(cfd, ndx, year, last_date)
    bars = cfd.loc[t0:t1 - pd.Timedelta(minutes=1), ["open", "high", "low", "close"]].copy()
    # K: NQ front-month / NDX ratio, median of first 3 sessions (both settle 16:00 ET)
    first = ndx.index[(ndx.index >= d0)][:3]
    K = float(np.median(nqf.loc[first, "close"].values / ndx.loc[first, "close"].values))
    # also align CFD to NDX level (CFD tracks the cash index, tiny offset)
    cfd_close = cfd_at_close(cfd, first)
    align = float(np.median(ndx.loc[cfd_close.index, "close"].values / cfd_close.values))
    scale = K * align
    out = bars * scale
    if carry:
        r = irx["close"].reindex(pd.DatetimeIndex(bars.index.tz_convert(ET).normalize()
                                                  .tz_localize(None)), method="ffill")
        rate = (r.values / 100.0) - DIV_YIELD + spread
        dt_days = np.diff(bars.index.values).astype("timedelta64[s]").astype(float) / 86400.0
        dt_days = np.concatenate([[0.0], dt_days])
        prev_close = np.concatenate([[out["close"].iloc[0]], out["close"].values[:-1]])
        D = np.cumsum(prev_close * rate * dt_days / 365.0)
        for col in ["open", "high", "low", "close"]:
            out[col] = out[col].values - D
        out["carry_pts"] = D
    meta = dict(year=year, first_day=d0.date(), last_day=d1.date(), K_basis=K,
                cfd_align=align, P0=out["open"].iloc[0], P_end=out["close"].iloc[-1],
                ndx_open=ndx.loc[d0, "open"], ndx_close=ndx.loc[d1, "close"],
                carry_pts=float(out["carry_pts"].iloc[-1]) if carry else 0.0, bars=len(out),
                carry_spread=spread)
    return out, meta
