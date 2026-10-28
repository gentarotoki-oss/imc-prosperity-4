#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path

import numpy as np
from numpy.polynomial.hermite import hermgauss
from scipy.stats import multivariate_normal, norm


S0 = 50.0
SIGMA = 2.51
TRADING_DAYS = 252
TWO_WEEK_DAYS = 10
THREE_WEEK_DAYS = 15
DEFAULT_ELAPSED_DAYS = 0


PRODUCTS = [
    ("AC", "underlying", 49.975, 50.025),
    ("AC_50_P", "put", 12.00, 12.05),
    ("AC_50_C", "call", 12.00, 12.05),
    ("AC_35_P", "put", 4.33, 4.35),
    ("AC_40_P", "put", 6.50, 6.55),
    ("AC_45_P", "put", 9.05, 9.10),
    ("AC_60_C", "call", 8.80, 8.85),
    ("AC_50_P_2", "put", 9.70, 9.75),
    ("AC_50_C_2", "call", 9.70, 9.75),
    ("AC_50_CO", "chooser", 22.20, 22.30),
    ("AC_40_BP", "binary_put", 5.00, 5.10),
    ("AC_45_KO", "ko_put", 0.150, 0.175),
]


def yearfrac(days: int) -> float:
    return days / TRADING_DAYS


def bs_call_put(strike: float, days: int) -> tuple[float, float]:
    t = yearfrac(days)
    if t <= 0:
        return max(S0 - strike, 0.0), max(strike - S0, 0.0)
    vol_t = SIGMA * math.sqrt(t)
    d1 = (math.log(S0 / strike) + 0.5 * SIGMA * SIGMA * t) / vol_t
    d2 = d1 - vol_t
    call = S0 * norm.cdf(d1) - strike * norm.cdf(d2)
    put = strike * norm.cdf(-d2) - S0 * norm.cdf(-d1)
    return call, put


def binary_put(strike: float, payout: float, days: int) -> float:
    t = yearfrac(days)
    if t <= 0:
        return payout if S0 < strike else 0.0
    vol_t = SIGMA * math.sqrt(t)
    z = (math.log(strike / S0) + 0.5 * SIGMA * SIGMA * t) / vol_t
    return payout * norm.cdf(z)


def bivn_prob(upper_x: float, upper_y: float, mean: np.ndarray, cov: np.ndarray) -> float:
    return float(multivariate_normal(mean=mean, cov=cov, allow_singular=False).cdf([upper_x, upper_y]))


def chooser_price(strike: float, choice_days: int, final_days: int) -> float:
    tc = yearfrac(choice_days)
    tt = yearfrac(final_days)
    if tc <= 0:
        call, put = bs_call_put(strike, final_days)
        return call if S0 >= strike else put

    a = math.log(strike)
    mean = np.array([
        math.log(S0) - 0.5 * SIGMA * SIGMA * tc,
        math.log(S0) - 0.5 * SIGMA * SIGMA * tt,
    ])
    cov = np.array([
        [SIGMA * SIGMA * tc, SIGMA * SIGMA * tc],
        [SIGMA * SIGMA * tc, SIGMA * SIGMA * tt],
    ])
    tilted_mean = mean + cov[:, 1]
    s_forward = math.exp(mean[1] + 0.5 * cov[1, 1])

    p_x_lt = norm.cdf((a - mean[0]) / math.sqrt(cov[0, 0]))
    p_y_lt = norm.cdf((a - mean[1]) / math.sqrt(cov[1, 1]))
    p_ll = bivn_prob(a, a, mean, cov)
    p_x_ge_y_ge = 1.0 - p_x_lt - p_y_lt + p_ll

    tilted_p_x_lt = norm.cdf((a - tilted_mean[0]) / math.sqrt(cov[0, 0]))
    tilted_p_y_lt = norm.cdf((a - tilted_mean[1]) / math.sqrt(cov[1, 1]))
    tilted_p_ll = bivn_prob(a, a, tilted_mean, cov)
    e_ll = s_forward * tilted_p_ll
    e_x_ge_y_ge = s_forward * (1.0 - tilted_p_x_lt - tilted_p_y_lt + tilted_p_ll)

    call_side = e_x_ge_y_ge - strike * p_x_ge_y_ge
    put_side = strike * p_ll - e_ll
    return call_side + put_side


def discrete_ko_put_dp(
    strike: float,
    barrier: float,
    days: int,
    steps_per_day: int,
    grid_size: int,
    gh_order: int,
) -> float:
    steps = days * steps_per_day
    dt = 1.0 / (TRADING_DAYS * steps_per_day)
    drift = -0.5 * SIGMA * SIGMA * dt
    vol = SIGMA * math.sqrt(dt)
    total_std = SIGMA * math.sqrt(yearfrac(days))
    center = math.log(S0)
    lo = min(math.log(barrier) - 0.5, center - 8.0 * total_std)
    hi = center + 8.0 * total_std
    x_grid = np.linspace(lo, hi, grid_size)
    s_grid = np.exp(x_grid)
    value = np.maximum(strike - s_grid, 0.0)
    value[x_grid < math.log(barrier)] = 0.0

    gh_x, gh_w = hermgauss(gh_order)
    z_nodes = math.sqrt(2.0) * gh_x
    weights = gh_w / math.sqrt(math.pi)
    log_barrier = math.log(barrier)

    for _ in range(steps):
        acc = np.zeros_like(value)
        for z, w in zip(z_nodes, weights):
            next_x = x_grid + drift + vol * z
            next_v = np.interp(next_x, x_grid, value, left=0.0, right=value[-1])
            next_v[next_x < log_barrier] = 0.0
            acc += w * next_v
        value = acc
    return float(np.interp(math.log(S0), x_grid, value))


def price_all(elapsed_days: int, steps_per_day: int, grid_size: int, gh_order: int) -> list[dict]:
    choice_days = TWO_WEEK_DAYS - elapsed_days
    final_days = THREE_WEEK_DAYS - elapsed_days
    if choice_days <= 0 or final_days <= 0:
        raise ValueError("elapsed_days leaves non-positive time to expiry")

    call50_3w, put50_3w = bs_call_put(50, final_days)
    call35_3w, put35_3w = bs_call_put(35, final_days)
    call40_3w, put40_3w = bs_call_put(40, final_days)
    call45_3w, put45_3w = bs_call_put(45, final_days)
    call60_3w, put60_3w = bs_call_put(60, final_days)
    call50_2w, put50_2w = bs_call_put(50, choice_days)

    prices = {
        "AC": S0,
        "AC_50_P": put50_3w,
        "AC_50_C": call50_3w,
        "AC_35_P": put35_3w,
        "AC_40_P": put40_3w,
        "AC_45_P": put45_3w,
        "AC_60_C": call60_3w,
        "AC_50_P_2": put50_2w,
        "AC_50_C_2": call50_2w,
        "AC_50_CO": chooser_price(50, choice_days, final_days),
        "AC_40_BP": binary_put(40, 10, final_days),
        "AC_45_KO": discrete_ko_put_dp(45, 35, final_days, steps_per_day, grid_size, gh_order),
    }

    rows = []
    for name, kind, bid, ask in PRODUCTS:
        fair = prices[name]
        rows.append({
            "product": name,
            "type": kind,
            "bid": bid,
            "ask": ask,
            "fair": fair,
            "buy_edge": fair - ask,
            "sell_edge": bid - fair,
        })
    return rows


def write_markdown(path: Path, rows: list[dict], args: argparse.Namespace) -> None:
    with path.open("w") as f:
        f.write("# Analytic / DP Option Prices\n\n")
        f.write("## Inputs\n\n")
        f.write("| Field | Value |\n|---|---:|\n")
        f.write(f"| S0 | {S0} |\n")
        f.write(f"| Sigma | {SIGMA} |\n")
        f.write(f"| Steps per day | {args.steps} |\n")
        f.write(f"| Elapsed days | {args.elapsed} |\n")
        f.write(f"| Remaining chooser days | {TWO_WEEK_DAYS - args.elapsed} |\n")
        f.write(f"| Remaining final days | {THREE_WEEK_DAYS - args.elapsed} |\n")
        f.write(f"| KO grid size | {args.ko_grid} |\n")
        f.write(f"| KO Gauss-Hermite order | {args.gh_order} |\n\n")

        f.write("## Prices\n\n")
        f.write("| Product | Type | Bid | Ask | Fair | Buy edge | Sell edge |\n")
        f.write("|---|---|---:|---:|---:|---:|---:|\n")
        for row in rows:
            f.write(
                f"| {row['product']} | {row['type']} | {row['bid']:.6f} | {row['ask']:.6f} | "
                f"{row['fair']:.6f} | {row['buy_edge']:.6f} | {row['sell_edge']:.6f} |\n"
            )
        f.write("\n## Notes\n\n")
        f.write("- Vanilla and binary prices use closed-form lognormal formulas with zero drift.\n")
        f.write("- Chooser uses the bivariate normal distribution of `log S_choice` and `log S_final`.\n")
        f.write("- KO put uses deterministic backward DP with Gauss-Hermite integration on the official discrete monitoring grid.\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--elapsed", type=int, default=DEFAULT_ELAPSED_DAYS)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--ko-grid", type=int, default=8001)
    parser.add_argument("--gh-order", type=int, default=41)
    parser.add_argument("--markdown", default="analytic_prices.md")
    parser.add_argument("--json", default="")
    args = parser.parse_args()

    rows = price_all(args.elapsed, args.steps, args.ko_grid, args.gh_order)
    write_markdown(Path(args.markdown), rows, args)
    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=2))

    print(f"markdown_report={args.markdown}")
    print("| Product | Fair | Buy edge | Sell edge |")
    print("|---|---:|---:|---:|")
    for row in rows:
        print(f"| {row['product']} | {row['fair']:.6f} | {row['buy_edge']:.6f} | {row['sell_edge']:.6f} |")


if __name__ == "__main__":
    main()
