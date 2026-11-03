"""Covered-call overlay for the pyramid: sell 1 call against every NQ contract held.

There is no free history of NQ option prices, so calls are priced with Black-76
(options on futures) from the Nasdaq-100 volatility index:

  ATM implied vol      = 0.90 x VXN (VXN is a 30-day variance-swap level, which sits
                          above ATM vol because of the skew)
  skew                  sigma(K) = sigma_ATM - 0.6 x ln(K / F)   (about -3 vol points for
                          a 30-day 20-delta call), floored at 40% of ATM
  VXN / T-bill rate     previous trading day's close (no look-ahead)

Mechanics, per contract:
  * when a contract is bought, sell 1 call: ATM (K = F) or the strike with 20 delta;
    expiry 30 or 7 calendar days
  * when the contract is sold (stop, +12% exit, year end), buy the call back at its
    Black-76 value at that moment
  * if the call expires while the contract is still held, it settles at intrinsic
    value and a new call is sold (roll)
  * costs per option trade: max(0.5 pt, 1% of premium) of spread + $2.50 commission
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

ET = "America/New_York"


@dataclass
class CallConfig:
    strike: str = "atm"          # "atm" or "delta"
    delta: float = 0.20
    days: int = 30
    vxn_to_atm: float = 0.90
    skew: float = 0.6            # vol points per 100% log-moneyness (0.6 -> -0.6 pts per 1% OTM)
    min_cost_pts: float = 0.5
    cost_frac: float = 0.01
    commission: float = 2.50
    point_value: float = 20.0

    def label(self):
        k = "ATM" if self.strike == "atm" else f"{self.delta*100:.0f}-delta"
        return f"sell {k} {self.days}-day calls"


def _ncdf(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def black76_call(F, K, T, r, sig):
    if T <= 0:
        return max(F - K, 0.0)
    sv = sig * math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * sv * sv) / sv
    return math.exp(-r * T) * (F * _ncdf(d1) - K * _ncdf(d1 - sv))


def black76_delta(F, K, T, r, sig):
    sv = sig * math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * sv * sv) / sv
    return math.exp(-r * T) * _ncdf(d1)


class VolSurface:
    def __init__(self, vxn: pd.Series, irx: pd.Series, cfg: CallConfig):
        self.vxn, self.irx, self.cfg = vxn.sort_index(), irx.sort_index(), cfg

    def _prev(self, s, ts):
        d = ts.tz_convert(ET).normalize().tz_localize(None)
        i = s.index.searchsorted(d, side="left") - 1      # strictly before today
        return float(s.iloc[max(i, 0)])

    def atm(self, ts):
        return self.cfg.vxn_to_atm * self._prev(self.vxn, ts) / 100.0

    def rate(self, ts):
        return self._prev(self.irx, ts) / 100.0

    def sigma(self, ts, F, K):
        a = self.atm(ts)
        return max(0.4 * a, a - self.cfg.skew * math.log(K / F))


def strike_for(F, T, r, vs: VolSurface, ts, cfg: CallConfig):
    if cfg.strike == "atm":
        return F
    lo, hi = F, F * 3.0                                    # delta falls as K rises
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if black76_delta(F, mid, T, r, vs.sigma(ts, F, mid)) > cfg.delta:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def overlay(trades: pd.DataFrame, segments: list, vs: VolSurface, cfg: CallConfig):
    """Option P&L per unit trade.  trades: rows with entry_time, entry, exit_time, exit
    (prices in the same yearly NQ series as `segments`)."""
    closes = pd.concat([seg["close"] for seg in segments])
    closes = closes[~closes.index.duplicated()]
    pv = cfg.point_value
    out = []
    for t in trades.itertuples():
        t0, t1 = pd.Timestamp(t.entry_time), pd.Timestamp(t.exit_time)
        F, ts = float(t.entry), t0
        pnl_pts, cost_usd, n_sold, settled = 0.0, 0.0, 0, 0.0
        while True:
            T = cfg.days / 365.0
            r = vs.rate(ts)
            K = strike_for(F, T, r, vs, ts, cfg)
            prem = black76_call(F, K, T, r, vs.sigma(ts, F, K))
            n_sold += 1
            cost_usd += (max(cfg.min_cost_pts, cfg.cost_frac * prem)) * pv + cfg.commission
            expiry = ts + pd.Timedelta(days=cfg.days)
            if expiry < t1:                                  # expires while the unit is held: roll
                i = closes.index.searchsorted(expiry)
                if i >= len(closes) or closes.index[i] >= t1:
                    F_exp = float(t.exit)
                    expiry = t1
                else:
                    F_exp = float(closes.iloc[i])
                    expiry = closes.index[i]
                intrinsic = max(F_exp - K, 0.0)
                pnl_pts += prem - intrinsic
                settled += intrinsic
                F, ts = F_exp, expiry
                if expiry >= t1:
                    break
                continue
            tau = max((t1 - ts).total_seconds() / 86400.0, 0.0)
            remaining = max(cfg.days - tau, 0.0) / 365.0
            F1 = float(t.exit)
            back = black76_call(F1, K, remaining, vs.rate(t1), vs.sigma(t1, F1, K))
            cost_usd += (max(cfg.min_cost_pts, cfg.cost_frac * back)) * pv + cfg.commission
            pnl_pts += prem - back
            break
        out.append((t.Index, pnl_pts * pv - cost_usd, pnl_pts * pv, cost_usd, n_sold))
    res = pd.DataFrame(out, columns=["trade", "option_pnl_usd", "option_gross_usd",
                                     "option_cost_usd", "calls_sold"]).set_index("trade")
    return res


if __name__ == "__main__":
    # Black-76 sanity checks
    F, T, r = 20000.0, 30 / 365, 0.04
    c = black76_call(F, F, T, r, 0.20)
    approx = 0.4 * F * 0.20 * math.sqrt(T) * math.exp(-r * T)     # ATM ~ 0.4 F sigma sqrt(T)
    assert abs(c - approx) / approx < 0.01, (c, approx)
    assert abs(black76_delta(F, F, T, r, 0.20) - 0.51) < 0.01
    vxn = pd.Series([22.0], index=[pd.Timestamp("2024-01-01")])
    irx = pd.Series([4.0], index=[pd.Timestamp("2024-01-01")])
    vs = VolSurface(vxn, irx, CallConfig(strike="delta"))
    ts = pd.Timestamp("2024-03-01 15:00", tz="UTC")
    K = strike_for(F, T, r, vs, ts, CallConfig(strike="delta"))
    d = black76_delta(F, K, T, r, vs.sigma(ts, F, K))
    assert abs(d - 0.20) < 1e-3 and K > F, (K, d)
    print(f"self-checks passed: ATM 30d call {c:.0f} pts ({c/F*100:.2f}% of F); "
          f"20-delta strike {K:,.0f} (+{(K/F-1)*100:.1f}%), "
          f"premium {black76_call(F, K, T, r, vs.sigma(ts, F, K)):.0f} pts")
