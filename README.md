# NQ "pyramid up" backtest, 2022 to 2026

**The strategy tested.** Each January, buy 1 unit of NQ. Every time price rises another 1%, add 1 unit. **Every unit, including the first, has its own stop 1% below its entry.** The idea: accept many small whipsaw losses in exchange for a very large position (and profit) if the market trends up. Each calendar year runs from the January open to the December close: 2022, 2023, 2024, 2025, and 2026 to date.

All dollar figures are for **1 unit = 1 NQ contract ($20 per point)**. **For MNQ, divide every dollar figure by 10.** Figures are net of costs (0.5 pt slippage plus $2.50 commission per contract per side). The 2026 run stops at the **November 2, 2026** close (year to date).

## The answer

![P&L by year](results/charts/pnl_by_year.png)

**Strategy as specified (variant D):** every unit has a 1% stop, and units are bought at the January price and at every +1% level above it. A stopped unit is bought again when price climbs back through its level.

| Year | NQ move* | Buy & hold 1 NQ | **Pyramid (as specified)** | Whipsaw stop-outs | Cost of stop-outs | P&L of units held at the end | Max contracts | Worst drawdown from peak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2022 | -33.8% | -$111k | **-$7k** | 2 | -$7k | $0 | 2 | -$11k |
| 2023 | +45.9% | +$102k | **+$1.67M** | 160 | -$435k | +$2.10M | 39 | -$1.34M |
| 2024 | +20.7% | +$70k | **+$175k** | 142 | -$539k | +$714k | 25 | -$912k |
| 2025 | +14.8% | +$63k | **+$23k** | 96 | -$453k | +$476k | 19 | -$824k |
| 2026 YTD | +6.4% | +$33k | **-$633k** | 130 | -$750k | +$117k | 19 | -$1.41M |
| **Total** | | **+$157k** | **+$1.23M** | 530 | -$2.18M | +$3.41M | | |

\*NQ move is for a rolled front-month NQ position (index move minus futures financing), from the open of the first January session to the close of the last December session.

**In short:** over 2022 to November 2026, the pyramid made **+$1.23M per 1-NQ unit (+$123k with MNQ)**. Holding one contract made +$157k. But one year produced all of the profit: **2023, with +$1.67M**. The other years went like this:

- **2022 lost only $7k.** The first unit was stopped on January 4 and NQ never came back to the January price.
- **2024 and 2025 made little**: +$175k and +$23k, small next to their $0.8M to $0.9M drawdowns.
- **2026 so far is -$633k.** The pyramid was at its largest (19 contracts at the October 6 high) when NQ fell about 11% by November 2. At its June peak, 2026 had been **+$770k**.

Profitable years still came with drawdowns of **$0.8M to $1.3M per NQ unit**.

## Conclusions you can use

1. **The strategy is a bet on trend strength against volatility, and the break-even point can be calculated.** The pyramid makes money only when **(log move above the January price)² > realised variance accumulated while it was active**. In plain terms: the year has to finish more than about one annual volatility above the January price. For NQ that is roughly **+18% to +25%** before the pyramid pays anything. The "edge ratio" was 4.43 in 2023 (a big win), 1.16 in 2024 and 0.93 in 2025 (about break-even), and 0.15 in 2026 so far (a large loss). The formula predicts the backtest closely (table in [Why it behaves like this](#why-it-behaves-like-this)).
2. **Budget the whipsaws as the price you pay for the position.** The expected number of stop-outs is about **realised variance ÷ (2 × step²)**. That works out to 95 to 160 per year whenever NQ trades around or above the January price. Each one costs about 1% of the NQ price: about $2.7k per NQ contract in 2023 and about $5.8k in 2026, at higher index levels. That is **$0.43M to $0.75M per year per NQ unit (MNQ: $43k to $75k)**. You pay it whether or not the trend comes.
3. **All of the profit comes from units still open at the end; every stopped unit is a loss.** The result therefore depends heavily on where the year ends relative to the path. 2026 went from +$770k in June to -$633k by November 2. Treat the year-end date as a random draw, and do not size the strategy as if you will exit at the top.
4. **Size for the drawdown, not for "1 unit".** The position grows by about 1 contract per 1% of rally: 39 contracts and about $12.8M of NQ notional at the 2023 peak, per unit. Even winning years dropped $0.8M to $1.3M from their peaks, and 2024 at one point stood $313k below its starting equity. **With 1 unit = 1 MNQ, plan for drawdowns of about $80k to $140k.**
5. **The step size is a leverage dial, not an edge.** Halving the step roughly doubles the profit, the drawdown and the maximum position. The ratio of total P&L to worst drawdown is about 0.85 to 1.25 for 0.5%, 1%, 2% and 3% steps alike, and each year keeps its sign (2025 stays near zero in every setting). Pick the step that fits your risk budget: 2% steps carry about half the risk of 1% steps. **Stop width barely matters.** A 3% stop instead of 1% changed the 5-year total by about +11% with 3.4 times fewer trades, so wider stops cost less and need less management.
6. **A cap on the pyramid helped (variant E), with a caveat.** Variant E never holds more than 10 contracts. It made **+$1.26M with a worst drawdown of -$756k**, versus +$1.23M and -$1.41M without the cap. Its 2026 loss so far is -$72k instead of -$633k. The cost is upside in a very strong trend year: 2023 made +$0.83M instead of +$1.67M. The caveat: I chose the cap after seeing these 5 years, so treat it as a sensible risk control rather than a proven improvement.
7. **Do not re-buy below the January price without a trend filter (variant B).** In B, once the first unit is stopped, a unit is bought on every +1% bounce at any price. It had the largest total (+$3.48M), because it caught the whole April 2025 rebound (+$2.50M that year). It also **lost $1.29M in 2022, from 505 whipsaws in a volatile bear market**, and its worst drawdown was -$2.2M.
8. **Long-run reality check (model estimate, 1986 to 2025).** The strategy as specified would have been profitable in only **19 of 40 years** (13 of 26 since 2000), with a median year near zero. Its mean result was strongly positive (+1.3 to +2.3 times one contract's January value per year), driven by rare huge trend years: 1991, 1995 to 1996, 1998 to 1999, 2003, 2009, 2013, 2017, 2019 to 2020, and 2023. **Per unit of risk it was about the same as buy and hold** (mean/std 0.35 to 0.37 versus 0.36 to 0.50). It does not add edge. It turns a long-NQ view into a lottery-like payoff: frequent moderate losses and occasional very large wins. Use it when you specifically want that skew and expect a strong trend year, not as an all-weather system.

## Variants (same data, same costs)

| Year | D as specified | E = D, max 10 contracts | B re-buys below January price | A first unit not stopped | Buy & hold |
|---|---:|---:|---:|---:|---:|
| 2022 | -$7k | -$7k | -$1.29M | -$114k | -$111k |
| 2023 | +$1.67M | +$829k | +$1.98M | +$1.67M | +$102k |
| 2024 | +$175k | +$304k | +$398k | +$179k | +$70k |
| 2025 | +$23k | +$205k | +$2.50M | +$61k | +$63k |
| 2026 YTD | -$633k | -$72k | -$107k | -$608k | +$33k |
| **Total** | **+$1.23M** | **+$1.26M** | **+$3.48M** | **+$1.19M** | **+$157k** |
| Worst drawdown | -$1.41M | -$756k | -$2.20M | -$1.41M | |
| Max contracts | 39 | 10 | 46 | 39 | 1 |

* **D (as specified):** every unit has a 1% stop. Units are bought at the January price and at every +1% level above it. A stopped unit is bought again if price climbs back through its level.
* **E:** same as D, but never more than 10 contracts open.
* **B:** same stops, but a unit is bought on every +1% step at any price, including rebounds from below the January price.
* **A:** the first unit is held all year with no stop (only the added units have stops). This was my first reading of the rule. In 2022 it lost the full buy-and-hold amount, -$114k.

Trade logs: `results/trades/<variant>_<year>.csv`. Hourly equity and contracts held: `results/equity/`. All statistics: `results/summary_all_variants.csv`.

## Year by year

Each chart shows NQ, the contracts held, and cumulative P&L for D (as specified) and B (re-buys below the January price).

**2022 (NQ -33.8%).** On January 3 the first unit was bought at 16,387. On January 4, a +1% move added a second unit at 16,551, and later that day both were stopped at -1% (about -$3.3k each). NQ never came back to the January price (the best it did afterwards was about 2.4% below it), so no unit was bought again: **-$7k**. B kept buying every 1% bounce in the falling, volatile market and was stopped 505 times: -$1.29M.
![2022](results/charts/anatomy_2022.png)

**2023 (NQ +45.9%).** This is the case the strategy is built for: a steady trend at about 18% volatility. The pyramid reached 39 contracts. 160 whipsaws cost $435k, but the units still held made $2.10M. Even so, the August to October correction took $1.34M off the peak.
![2023](results/charts/anatomy_2023.png)

**2024 (NQ +20.7%).** A good year for the index but a choppy one, including the July and August selloff. 142 whipsaws (-$539k) against +$714k from the units still held gave a result of +$175k, just above break-even.
![2024](results/charts/anatomy_2024.png)

**2025 (NQ +14.8%).** NQ chopped around its January price in January and February, so the first unit was stopped and bought back 8 times. The tariff crash then took NQ about 24% below that price, and D held nothing from late February until NQ climbed back to the January price. The first unit was bought for the last time on June 3, and the pyramid was built on the way up from there. The result was +$23k. B, which also buys below the January price, caught the whole V-shaped rebound: +$2.50M.
![2025](results/charts/anatomy_2025.png)

**2026 to November 2 (NQ +6.4%).** NQ chopped around its January price in January and early February (the first unit was stopped five times, and bought for the last time on April 14), dipped about 10% below it in March, rallied to about 19% above the January price by June, chopped between roughly 27,000 and 31,000, made its high on October 6 (+20%), then fell about 11% by November 2. That produced 130 whipsaws at high price levels (about $5.8k each) against only +6% of net trend: -$633k, after having been +$770k in June. The year is not over.
![2026](results/charts/anatomy_2026.png)

## Why it behaves like this

In variant D, the number of open units is (almost exactly) a function of price: one per 1% level between the January price and the current price. That makes the pyramid a convex, option-like position. Its cost is paid through whipsaws: each time price falls through a level and climbs back, you lose about 1%. Counting grid crossings (equivalently, applying Itô's formula) gives:

```
stop-outs     ≈ RV / (2·d²)                    d = ln(1.01), RV = realised variance of ln(price)
                                               while the ladder is active
whipsaw cost  ≈ stop-outs × 1% × price
trend payoff  = Σ (P_end − L_k) over levels between anchor and P_end  ≈ price × ln(P_end/anchor)² / (2d)

ladder P&L    ≈ price / (2d) × [ ln(P_end/anchor)²  −  RV ]
```

The anchor is the January price for D, and the year's low for B. The **edge ratio** is ln-move² ÷ RV: above 1 the pyramid makes money, below 1 it loses. Checked against the 1-minute backtest:

| Year | Variant | Move from anchor | (log move)² | Realised variance | Edge ratio | Stop-outs predicted / actual | Ladder P&L predicted / actual |
|---|---|---:|---:|---:|---:|---:|---:|
| 2022 | D | -33.8% | 0.0000 | 0.0003 | 0.00 | 2 / 2 | -$5k / -$7k |
| 2022 | B | +3.6% | 0.0012 | 0.1003 | 0.01 | 507 / 505 | -$1.28M / -$1.29M |
| 2023 | D | +45.9% | 0.1425 | 0.0321 | 4.43 | 162 / 160 | +$1.65M / +$1.67M |
| 2023 | B | +50.3% | 0.1658 | 0.0331 | 5.01 | 167 / 166 | +$1.85M / +$1.98M |
| 2024 | D | +20.7% | 0.0354 | 0.0305 | 1.16 | 154 / 142 | +$133k / +$175k |
| 2024 | B | +24.1% | 0.0466 | 0.0308 | 1.51 | 156 / 144 | +$278k / +$398k |
| 2025 | D | +14.8% | 0.0189 | 0.0205 | 0.93 | 103 / 96 | -$1k / +$23k |
| 2025 | B | +50.2% | 0.1653 | 0.0584 | 2.83 | 295 / 262 | +$2.33M / +$2.50M |
| 2026 YTD | D | +6.4% | 0.0039 | 0.0260 | 0.15 | 131 / 130 | -$629k / -$633k |
| 2026 YTD | B | +19.8% | 0.0326 | 0.0365 | 0.89 | 184 / 180 | -$210k / -$107k |

(RV here is the sum of squared 60-minute log returns, counted while the pyramid can hold units: above the first unit's stop for D, all year for B.) Practical consequences:

* **Watch the ratio during the year.** Track (ln(P/P0))² against the realised variance accumulated so far. If price spends months grinding around a level, the stop-out count keeps rising while the trend term does not.
* **Changing the step does not change the sign of the result.** The trend payoff and the whipsaw cost both scale with 1/step, so a different step size does not turn a losing year into a winning one.
* **There is no free lunch.** On a driftless market the two terms cancel in expectation, which is the classic "stop-loss / start-gain" paradox. Whatever edge exists comes from NQ's upward drift, which buy and hold also captures.

## Sensitivity: step and stop size (variant D)

| Add every | Stop | 2022 | 2023 | 2024 | 2025 | 2026 YTD | 5-yr total | Worst drawdown | Stop-outs (5 yrs) | Max contracts |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.5% | 0.5% | -$8k | +$3.28M | +$230k | +$65k | -$1.22M | +$2.36M | -$2.73M | 2090 | 78 |
| 0.5% | 1% | -$13k | +$3.32M | +$286k | +$64k | -$1.22M | +$2.44M | -$2.79M | 1024 | 78 |
| 0.5% | 2% | -$20k | +$3.43M | +$289k | +$48k | -$1.22M | +$2.52M | -$2.88M | 491 | 78 |
| 0.5% | 3% | -$30k | +$3.53M | +$313k | +$89k | -$1.19M | +$2.71M | -$2.85M | 305 | 78 |
| 1% | 0.5% | -$5k | +$1.63M | +$109k | +$79k | -$614k | +$1.20M | -$1.40M | 1045 | 38 |
| **1%** | **1%** | -$7k | +$1.67M | +$175k | +$23k | -$633k | **+$1.23M** | -$1.41M | 530 | 39 |
| 1% | 2% | -$13k | +$1.74M | +$154k | +$37k | -$635k | +$1.29M | -$1.48M | 252 | 39 |
| 1% | 3% | -$20k | +$1.79M | +$161k | +$51k | -$624k | +$1.36M | -$1.48M | 158 | 39 |
| 2% | 0.5% | -$3k | +$813k | +$112k | +$28k | -$291k | +$659k | -$708k | 517 | 19 |
| 2% | 1% | -$3k | +$866k | +$123k | -$1k | -$290k | +$695k | -$711k | 264 | 20 |
| 2% | 2% | -$7k | +$883k | +$99k | +$18k | -$287k | +$706k | -$742k | 129 | 20 |
| 2% | 3% | -$10k | +$910k | +$110k | +$16k | -$288k | +$739k | -$737k | 82 | 20 |
| 3% | 0.5% | -$3k | +$601k | +$92k | +$37k | -$211k | +$515k | -$497k | 347 | 14 |
| 3% | 1% | -$3k | +$602k | +$93k | +$34k | -$206k | +$520k | -$496k | 175 | 14 |
| 3% | 2% | -$7k | +$638k | +$85k | +$48k | -$154k | +$610k | -$483k | 76 | 14 |
| 3% | 3% | -$10k | +$625k | +$85k | +$9k | -$172k | +$538k | -$507k | 54 | 14 |

The year-by-year pattern (2023 big, 2024 and 2025 small, 2026 negative) is the same for every step and stop. Only the scale changes.

**Cap on contracts held at once (variant D, 1%/1%):**

| Max contracts | 2022 | 2023 | 2024 | 2025 | 2026 YTD | 5-yr total | Worst drawdown |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | -$7k | +$467k | +$242k | +$118k | +$35k | +$855k | -$386k |
| 10 | -$7k | +$829k | +$304k | +$205k | -$72k | +$1.26M | -$756k |
| 20 | -$7k | +$1.38M | +$221k | +$23k | -$633k | +$984k | -$1.41M |
| 30 | -$7k | +$1.64M | +$175k | +$23k | -$633k | +$1.20M | -$1.41M |
| none | -$7k | +$1.67M | +$175k | +$23k | -$633k | +$1.23M | -$1.41M |

With a cap, once price is far above the last level you are allowed to buy, the strategy holds a fixed block of contracts with no whipsaws at the top. That helped in the choppy years (2024 to 2026) and cost upside in the clean trend year (2023).

## 40-year context (model estimate, not a tick-level backtest)

Free 1-minute data only goes back to 2022 here, so `src/history_estimate.py` applies the formula above to daily Nasdaq-100 data from 1986 to 2025. Carry is the T-bill rate minus 0.7%, reset each January, with no extra financing spread. For 2022 to 2026 that formula gives the same sign as the 1-minute backtest in every year. For variant D it is within about ±0.8 of one contract's January value per year; for B the misses are larger, up to 1.8 in 2025. Treat it as a rough base rate. Results are in **multiples of one contract's January value** (×1.0 = one contract's value at the start of the year):

| Period | Strategy | Years positive | Median year | Mean year | Std dev | Mean / std | Worst year | Best year |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1986-2025 | D as specified (every unit stopped) | 19/40 | -0.04× | +2.28× | 6.45× | 0.35 | -4.97× | +29.76× |
| 1986-2025 | A first unit without a stop | 19/40 | -0.08× | +2.32× | 6.45× | 0.36 | -5.02× | +29.76× |
| 1986-2025 | B add at any price | 24/40 | +0.48× | +2.32× | 8.24× | 0.28 | -16.24× | +29.76× |
| 1986-2025 | buy & hold 1 contract | 31/40 | +0.15× | +0.16× | 0.31× | 0.50 | -0.43× | +0.97× |
| 2000-2025 | D as specified (every unit stopped) | 13/26 | +0.03× | +1.34× | 3.62× | 0.37 | -4.97× | +10.06× |
| 2000-2025 | A first unit without a stop | 13/26 | +0.02× | +1.38× | 3.65× | 0.38 | -5.02× | +10.27× |
| 2000-2025 | B add at any price | 16/26 | +0.72× | +1.11× | 6.86× | 0.16 | -16.24× | +17.14× |
| 2000-2025 | buy & hold 1 contract | 19/26 | +0.16× | +0.11× | 0.29× | 0.36 | -0.43× | +0.54× |

Per-year values are in `results/history_estimate_1986_2026.csv`. The worst year for D was 2000: the index rose about 20% above its January level, built a pyramid, then crashed. B's worst year was also 2000, at -16×, from buying every bounce down. In bear years such as 2008 and 2022, D lost almost nothing, because the first unit is stopped early and price never returns to the January level.

## Rules exactly as tested

1. **Start:** at the 09:30 ET open of the first January session, buy 1 unit with a stop 1% below its entry.
2. **Levels:** L_k = P0 × 1.01^k (k = 0, 1, 2, ...). Each level is 1% above the previous one, so "after +1%" is always measured from the previous unit's entry. Buy-stop orders sit at every level that has no open unit. In D and E, levels exist only at and above the January price; in B they exist everywhere.
3. **Stops:** each unit is sold at its entry × 0.99. When that happens, only that unit is closed. If price climbs back through its level, the unit is bought again. There is at most one unit per level. If everything has been stopped, D buys again only when price climbs back to the January price.
4. **End:** sell everything at the 16:00 ET close of the last December session (Dec 30, 2022; Dec 29, 2023; Dec 31, 2024; Dec 31, 2025). For 2026, positions are valued at the Nov 2, 2026 close.
5. **Execution:** 1-minute bars. An up bar is assumed to trade open → low → high → close, a down bar open → high → low → close. Stops and buy-stops fill at their trigger price plus 0.5 pt slippage. If a gap jumps over a trigger (weekend, overnight, news), the fill is at the gap open: for example, the weekend tariff gap of Feb 2, 2025 cost 2.8% instead of 1% on one unit. Commission is $2.50 per contract per side. Stops are live 23 hours a day, as on CME Globex.

## Data and method

* **Price path:** 1-minute bid and ask candles of the Dukascopy Nasdaq-100 CFD (`USATECHIDXUSD`), converted to mid prices: 1.66M bars from Dec 27, 2021 to Nov 2, 2026. Free intraday NQ history going back to 2022 is not available. The CFD trades nearly 24 hours like NQ and tracks the index closely, per [`results/data_validation.md`](results/data_validation.md):
  * 16:00 ET price versus the official NDX close: median -0.1 bp.
  * Daily return correlation: 0.997.
  * Average daily high-low range: 2.03% versus 2.06% for NQ futures.
  * The largest 1-minute moves line up with real events (CPI releases, the April 2025 tariff shocks, the 2026-03-23 spike that also appears in NQ futures).
* **NQ conversion:** each year, prices are scaled to the NQ front-month level on the first day. Futures financing carry is then subtracted: the 13-week T-bill rate minus a 0.7% dividend yield, plus a per-year spread calibrated so that each year's move equals the **real rolled NQ contract** (Yahoo NQ=F with roll jumps removed). The calibrated spreads are -0.45% (2022), +0.89%, +0.42%, +1.06% and +0.80% per year. Without the carry adjustment, the cash index would overstate NQ's yearly gain by about 700 to 970 points in 2023 to 2026.
* **What this means in practice:** P&L is the P&L of an NQ position rolled every quarter. If you trade it live, roll every open unit at the quarterly roll and shift its stop by the roll spread.

## Reproduce

```bash
pip install -r requirements.txt
```

```bash
python3 src/fetch_dukascopy.py --out data/dukascopy --start 2021-12-27 --end 2026-11-02
```

```bash
python3 src/fetch_yahoo.py --out data/yahoo
```

```bash
python3 src/run_backtests.py --cfd data/dukascopy/USATECHIDXUSD_1min_mid.csv.gz --yahoo data/yahoo --out results
```

```bash
python3 src/theory_check.py --results results && python3 src/history_estimate.py --yahoo data/yahoo --results results
```

```bash
python3 src/make_charts.py --results results && python3 src/report_tables.py --results results
```

The Dukascopy download (about 3,500 small files) throttles. The script retries and resumes from its cache. The engine self-test runs with `python3 src/pyramid_backtest.py`.

## Files

| Path | What |
|---|---|
| `src/pyramid_backtest.py` | Event-driven engine: grid, per-unit stops, fills, costs, equity curve; self-tests |
| `src/nq_series.py` | CFD to NQ-equivalent conversion: level scaling and calibrated carry |
| `src/run_backtests.py` | Runs every year and variant, plus the step/stop and cap sensitivity grids |
| `src/theory_check.py` | Closed-form prediction versus backtest |
| `src/history_estimate.py` | 1986 to 2025 model estimate from daily data |
| `src/make_charts.py`, `src/report_tables.py` | Charts and README tables |
| `src/fetch_dukascopy.py`, `src/build_bars.py`, `src/fetch_yahoo.py` | Data download and decoding |
| `results/` | All CSV outputs, trade logs, hourly equity curves, charts, data validation |

*Backtests are hypothetical. Real fills during fast markets and gaps can be worse than modelled, futures margin requirements change, and past trend years do not predict future ones.*
