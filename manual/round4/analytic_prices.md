# Analytic / DP Option Prices

## Inputs

| Field | Value |
|---|---:|
| S0 | 50.0 |
| Sigma | 2.51 |
| Steps per day | 4 |
| Elapsed days | 0 |
| Remaining chooser days | 10 |
| Remaining final days | 15 |
| KO grid size | 8001 |
| KO Gauss-Hermite order | 41 |

## Prices

| Product | Type | Bid | Ask | Fair | Buy edge | Sell edge |
|---|---|---:|---:|---:|---:|---:|
| AC | underlying | 49.975000 | 50.025000 | 50.000000 | -0.025000 | -0.025000 |
| AC_50_P | put | 12.000000 | 12.050000 | 12.026949 | -0.023051 | -0.026949 |
| AC_50_C | call | 12.000000 | 12.050000 | 12.026949 | -0.023051 | -0.026949 |
| AC_35_P | put | 4.330000 | 4.350000 | 4.336146 | -0.013854 | -0.006146 |
| AC_40_P | put | 6.500000 | 6.550000 | 6.509540 | -0.040460 | -0.009540 |
| AC_45_P | put | 9.050000 | 9.100000 | 9.088900 | -0.011100 | -0.038900 |
| AC_60_C | call | 8.800000 | 8.850000 | 8.791792 | -0.058208 | 0.008208 |
| AC_50_P_2 | put | 9.700000 | 9.750000 | 9.870709 | 0.120709 | -0.170709 |
| AC_50_C_2 | call | 9.700000 | 9.750000 | 9.870709 | 0.120709 | -0.170709 |
| AC_50_CO | chooser | 22.200000 | 22.300000 | 21.897659 | -0.402341 | 0.302341 |
| AC_40_BP | binary_put | 5.000000 | 5.100000 | 4.767945 | -0.332055 | 0.232055 |
| AC_45_KO | ko_put | 0.150000 | 0.175000 | 0.208550 | 0.033550 | -0.058550 |

## Notes

- Vanilla and binary prices use closed-form lognormal formulas with zero drift.
- Chooser uses the bivariate normal distribution of `log S_choice` and `log S_final`.
- KO put uses deterministic backward DP with Gauss-Hermite integration on the official discrete monitoring grid.
