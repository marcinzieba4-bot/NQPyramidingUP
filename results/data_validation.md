# Data validation (Dukascopy NAS100 CFD vs Yahoo NDX / NQ=F)

* 1-min bars used: 1,660,214 (2021-12-27 00:00:00+00:00 -> 2026-11-02 23:59:00+00:00)
* CFD at 16:00 ET vs official NDX close: median -0.1 bp, 5-95% range -11.7 .. +13.5 bp (n=1204)
* Daily return correlation CFD vs NDX: 0.9970
* Average daily high-low range: CFD 2.030% vs NQ futures 2.055% (median difference -0.007 pp, n=1217)

## Carry model check: 1 NQ contract held first-day close -> last-day close (points)

| Year | Real rolled NQ (Yahoo NQ=F, roll jumps removed) | Model: T-bill - 0.7% only | Model calibrated (used) | Calibrated extra financing spread | Cash index (no carry) |
|---|---:|---:|---:|---:|---:|
| 2022 | -5,646 | -5,702 | -5,646 | -0.45%/yr | -5,562 |
| 2023 | 5,288 | 5,413 | 5,288 | +0.89%/yr | 5,963 |
| 2024 | 3,615 | 3,695 | 3,615 | +0.42%/yr | 4,468 |
| 2025 | 3,304 | 3,543 | 3,304 | +1.06%/yr | 4,274 |
| 2026 | 1,913 | 2,100 | 1,913 | +0.80%/yr | 2,784 |
