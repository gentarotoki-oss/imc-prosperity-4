# Globally-Optimal Portfolio (MISOCP / SCIP)

## Inputs

| Field | Value |
|---|---:|
| Elapsed days | 0 |
| Remaining chooser / final days | 10 / 15 |
| Steps per day | 4 |
| KO grid / order | 4001 / 0 |

## Fair Values

| Product | Bid | Ask | Fair | Buy edge | Sell edge |
|---|---:|---:|---:|---:|---:|
| AC | 49.9750 | 50.0250 | 50.0000 | -0.0250 | -0.0250 |
| AC_50_P | 12.0000 | 12.0500 | 12.0269 | -0.0231 | -0.0269 |
| AC_50_C | 12.0000 | 12.0500 | 12.0269 | -0.0231 | -0.0269 |
| AC_35_P | 4.3300 | 4.3500 | 4.3361 | -0.0139 | -0.0061 |
| AC_40_P | 6.5000 | 6.5500 | 6.5095 | -0.0405 | -0.0095 |
| AC_45_P | 9.0500 | 9.1000 | 9.0889 | -0.0111 | -0.0389 |
| AC_60_C | 8.8000 | 8.8500 | 8.7918 | -0.0582 | +0.0082 |
| AC_50_P_2 | 9.7000 | 9.7500 | 9.8707 | +0.1207 | -0.1707 |
| AC_50_C_2 | 9.7000 | 9.7500 | 9.8707 | +0.1207 | -0.1707 |
| AC_50_CO | 22.2000 | 22.3000 | 21.8977 | -0.4023 | +0.3023 |
| AC_40_BP | 5.0000 | 5.1000 | 4.7679 | -0.3321 | +0.2321 |
| AC_45_KO | 0.1500 | 0.1750 | 0.2061 | +0.0311 | -0.0561 |

## Efficient Frontier (mean - lambda * std)

| lambda | Mean | Std | Sharpe | mean-0.25 std | 100-run 5% LB | 100-run 1% LB |
|---:|---:|---:|---:|---:|---:|---:|
| 0.1000 | +13.7124 | 73.9943 | +0.1853 | -4.7862 | +1.5033 | -3.5283 |
| 0.1500 | +12.8008 | 66.0487 | +0.1938 | -3.7114 | +1.9028 | -2.5885 |
| 0.2000 | +9.4621 | 47.1947 | +0.2005 | -2.3366 | +1.6750 | -1.5343 |
| 0.2005 | +9.2473 | 46.1232 | +0.2005 | -2.2835 | +1.6370 | -1.4994 |

## Recommended (max 100-run 1% LB)

- lambda = `0.2005`
- Mean: `+9.2473`,  Std: `46.1232`,  Sharpe: `+0.2005`
- 100-run 5% LB: `+1.6370`,  1% LB: `-1.4994`

## Positions per lambda

### lambda = 0.1

| Product | Position |
|---|---:|
| AC_50_P | BUY 4 |
| AC_50_C | BUY 6 |
| AC_35_P | SELL 49 |
| AC_45_P | BUY 50 |
| AC_50_P_2 | BUY 4 |
| AC_50_C_2 | BUY 1 |
| AC_50_CO | SELL 6 |
| AC_40_BP | SELL 50 |
| AC_45_KO | BUY 25 |

### lambda = 0.15

| Product | Position |
|---|---:|
| AC_50_P | BUY 3 |
| AC_50_C | BUY 4 |
| AC_35_P | SELL 50 |
| AC_45_P | BUY 50 |
| AC_50_P_2 | BUY 3 |
| AC_50_C_2 | BUY 1 |
| AC_50_CO | SELL 4 |
| AC_40_BP | SELL 50 |
| AC_45_KO | BUY 17 |

### lambda = 0.2

| Product | Position |
|---|---:|
| AC | BUY 2 |
| AC_50_C | BUY 1 |
| AC_35_P | SELL 44 |
| AC_45_P | BUY 47 |
| AC_60_C | SELL 1 |
| AC_50_P_2 | BUY 1 |
| AC_50_CO | SELL 2 |
| AC_40_BP | SELL 40 |
| AC_45_KO | BUY 10 |

### lambda = 0.2005

| Product | Position |
|---|---:|
| AC | BUY 2 |
| AC_50_C | BUY 1 |
| AC_35_P | SELL 43 |
| AC_45_P | BUY 46 |
| AC_60_C | SELL 1 |
| AC_50_P_2 | BUY 1 |
| AC_50_CO | SELL 2 |
| AC_40_BP | SELL 39 |
| AC_45_KO | BUY 10 |

