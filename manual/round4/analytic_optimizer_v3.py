#!/usr/bin/env python3
"""Globally-optimal portfolio (v3): cell-based DP for KO + MISOCP.

Replaces the Gauss-Hermite + np.interp DP in analytic_optimizer.ko_cross_moments
with a cell-based Markov-chain DP (mass-preserving, barrier-aligned).
Then runs the same MISOCP frontier as v2.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import cvxpy as cp
import numpy as np
from scipy.special import ndtr

from analytic_optimizer import (
    NAMES, BIDS, ASKS, LIMITS,
    TWO_WEEK_DAYS, THREE_WEEK_DAYS, DEFAULT_ELAPSED_DAYS,
    S0, SIGMA, TRADING_DAYS,
    payoff_non_ko, non_ko_moments, exact_non_ko_means,
    eval_metrics,
)
from analytic_optimizer_v2 import solve_misocp, sharpe_dinkelbach


# ---------- cell-based DP ---------- #

def live_log_grid(s0, barrier, sigma, days, trading_days, grid_size):
    log_barrier = math.log(barrier)
    total_std = sigma * math.sqrt(days / trading_days)
    hi = math.log(s0) + 8.0 * total_std
    boundaries = np.linspace(log_barrier, hi, grid_size + 1)
    centers = 0.5 * (boundaries[:-1] + boundaries[1:])
    return centers, np.exp(centers), boundaries[1] - boundaries[0]


def transition_kernel(dx, drift, vol, cutoff_sigma=10.0):
    radius = int(math.ceil((abs(drift) + cutoff_sigma * vol) / dx + 0.5))
    offsets = np.arange(-radius, radius + 1, dtype=np.int64)
    lower = (offsets - 0.5) * dx
    upper = (offsets + 0.5) * dx
    probs = ndtr((upper - drift) / vol) - ndtr((lower - drift) / vol)
    keep = probs > 1e-18
    return offsets[keep], probs[keep]


def backward_cell_dp(values, steps, dx, drift, vol, cutoff_sigma=10.0):
    squeeze = values.ndim == 1
    out = values[:, None].copy() if squeeze else values.copy()
    n = out.shape[0]
    offsets, probs = transition_kernel(dx, drift, vol, cutoff_sigma)
    for _ in range(steps):
        acc = np.zeros_like(out)
        for offset, prob in zip(offsets, probs):
            if offset >= n or offset <= -n:
                continue
            if offset >= 0:
                acc[: n - offset] += prob * out[offset:]
            else:
                acc[-offset:] += prob * out[: n + offset]
        out = acc
    return out[:, 0] if squeeze else out


def interp_at_log_s0(values, x_grid, s0):
    x0 = math.log(s0)
    pos = (x0 - x_grid[0]) / (x_grid[1] - x_grid[0])
    if pos <= 0:
        return values[0] if values.ndim == 1 else values[0, :]
    if pos >= len(x_grid) - 1:
        return values[-1] if values.ndim == 1 else values[-1, :]
    i = int(pos)
    frac = pos - i
    return values[i] * (1.0 - frac) + values[i + 1] * frac


# ---------- KO cross-moments via cell DP ---------- #

def ko_cross_moments_cell(choice_days, final_days, steps_per_day, grid_size):
    steps = final_days * steps_per_day
    choice_step = choice_days * steps_per_day
    dt = 1.0 / (TRADING_DAYS * steps_per_day)
    drift = -0.5 * SIGMA * SIGMA * dt
    vol = SIGMA * math.sqrt(dt)

    x_grid, s_grid, dx = live_log_grid(S0, 35.0, SIGMA, final_days, TRADING_DAYS, grid_size)

    # Above-barrier grid; below-barrier mass = knocked out (value 0). Since the
    # grid starts at log(barrier), every cell here is "alive". The transition
    # kernel that lands below x_grid[0] is naturally truncated by the n-bound
    # check inside backward_cell_dp -> mass leaving downward is implicitly 0
    # (correct KO behavior).

    ko_payoff = np.maximum(45 - s_grid, 0.0)
    final_pay = payoff_non_ko(s_grid, s_grid)  # (n, 11)

    # Terminal columns: [ko, ko^2, ko*(7 non-choice non-binary final pays),
    #                    ko*binary(40), ko*call50_choice_proxy, ko*put50_choice_proxy]
    terminal = np.empty((grid_size, 12))
    terminal[:, 0] = ko_payoff
    terminal[:, 1] = ko_payoff * ko_payoff
    for j in range(7):
        terminal[:, 2 + j] = ko_payoff * final_pay[:, j]
    terminal[:, 9] = ko_payoff * final_pay[:, 10]              # binary40 cross
    terminal[:, 10] = ko_payoff * np.maximum(s_grid - 50, 0.0) # for chooser construction
    terminal[:, 11] = ko_payoff * np.maximum(50 - s_grid, 0.0) # for chooser construction

    initial = backward_cell_dp(terminal, steps, dx, drift, vol)
    at_initial = interp_at_log_s0(initial, x_grid, S0)

    cross = np.empty(11)
    cross[:7] = at_initial[2:9]   # KO * (S, P50_3w, C50_3w, P35_3w, P40_3w, P45_3w, C60_3w)
    cross[10] = at_initial[9]     # KO * binary40
    ko_mean = float(at_initial[0])
    ko_second = float(at_initial[1])

    # 2w cross terms via two-stage backward (final->choice, then choice->0)
    to_choice = backward_cell_dp(terminal, steps - choice_step, dx, drift, vol)
    choice_terminal = np.empty((grid_size, 3))
    # E[KO * P50_2w | x_choice]: at choice time, P50_2w = (50-S)+, multiply by E[KO|x_choice]
    choice_terminal[:, 0] = np.maximum(50 - s_grid, 0.0) * to_choice[:, 0]
    choice_terminal[:, 1] = np.maximum(s_grid - 50, 0.0) * to_choice[:, 0]
    # Chooser cross: pick max(call, put) at choice time, weighted by E[KO|x_choice]
    choice_terminal[:, 2] = np.where(s_grid >= 50, to_choice[:, 10], to_choice[:, 11])
    choice_initial = backward_cell_dp(choice_terminal, choice_step, dx, drift, vol)
    choice_at_initial = interp_at_log_s0(choice_initial, x_grid, S0)
    cross[7] = choice_at_initial[0]
    cross[8] = choice_at_initial[1]
    cross[9] = choice_at_initial[2]

    return ko_mean, cross, ko_second


def analytic_stats_v3(choice_days, final_days, steps_per_day, quad_order, quad_range, ko_grid):
    quad_mean11, second11 = non_ko_moments(choice_days, final_days, quad_order, quad_range)
    mean11 = exact_non_ko_means(choice_days, final_days)
    ko_mean, ko_cross, ko_second = ko_cross_moments_cell(
        choice_days, final_days, steps_per_day, ko_grid
    )
    mean = np.zeros(12)
    moment_mean = np.zeros(12)
    second = np.zeros((12, 12))
    mean[:11] = mean11
    mean[11] = ko_mean
    moment_mean[:11] = quad_mean11
    moment_mean[11] = ko_mean
    second[:11, :11] = second11
    second[11, :11] = ko_cross
    second[:11, 11] = ko_cross
    second[11, 11] = ko_second
    cov = second - np.outer(moment_mean, moment_mean)
    cov = 0.5 * (cov + cov.T)
    return mean, cov


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--elapsed", type=int, default=DEFAULT_ELAPSED_DAYS)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--quad-order", type=int, default=401)
    parser.add_argument("--quad-range", type=float, default=8.0)
    parser.add_argument("--ko-grid", type=int, default=4001)
    parser.add_argument("--ko-order", type=int, default=0, help="unused (cell DP)")
    parser.add_argument("--lambdas", type=str,
                        default="0,0.005,0.01,0.02,0.05,0.1,0.15,0.2,0.3,0.5")
    parser.add_argument("--time-limit", type=float, default=60.0)
    parser.add_argument("--solver", type=str, default="SCIP")
    parser.add_argument("--markdown", default="analytic_optimizer_v3_report.md")
    args = parser.parse_args()

    choice_days = TWO_WEEK_DAYS - args.elapsed
    final_days = THREE_WEEK_DAYS - args.elapsed

    print("computing analytic mean/cov (cell-based KO DP) ...")
    mu, cov = analytic_stats_v3(choice_days, final_days, args.steps,
                                args.quad_order, args.quad_range, args.ko_grid)
    print(f"  KO fair = {mu[11]:.6f}")
    print(f"  All fairs:")
    for n, v in zip(NAMES, mu):
        print(f"    {n:14s} {v:8.4f}  buy_edge={v-ASKS[NAMES.index(n)]:+.4f}  "
              f"sell_edge={BIDS[NAMES.index(n)]-v:+.4f}")

    lambdas = [float(x) for x in args.lambdas.split(",") if x.strip()]
    frontier = []
    for lam in lambdas:
        print(f"solving MISOCP  lambda={lam} ...", flush=True)
        q = solve_misocp(mu, cov, lam, solver=args.solver, time_limit=args.time_limit)
        m = eval_metrics(q, mu, cov)
        print(f"  mean={m['mean']:+.3f}  std={m['std']:.3f}  sharpe={m['sharpe']:+.3f}  "
              f"p1%LB={m['p1_100']:+.3f}  p5%LB={m['p5_100']:+.3f}")
        frontier.append((lam, q, m))

    print("Dinkelbach (max Sharpe) ...", flush=True)
    try:
        q_sh, gamma = sharpe_dinkelbach(mu, cov, time_limit=args.time_limit)
        m = eval_metrics(q_sh, mu, cov)
        print(f"  gamma*={gamma:.4f}  mean={m['mean']:+.3f}  std={m['std']:.3f}  "
              f"sharpe={m['sharpe']:+.3f}  p1%LB={m['p1_100']:+.3f}")
        frontier.append((float(f"{gamma:.4f}"), q_sh, m))
    except Exception as e:
        print(f"  Dinkelbach failed: {e}")

    # Write report (reuse v2 writer)
    from analytic_optimizer_v2 import write_report
    write_report(Path(args.markdown), mu, cov, frontier, args)

    print(f"\nmarkdown_report={args.markdown}")
    recommended = max(frontier, key=lambda it: (it[2]["p1_100"], it[2]["p5_100"]))
    lam, q, m = recommended
    print(f"\n=== Recommended (lambda={lam}, max 1% LB) ===")
    print(f"mean={m['mean']:+.3f}  std={m['std']:.3f}  sharpe={m['sharpe']:+.3f}")
    print(f"5% LB={m['p5_100']:+.3f}  1% LB={m['p1_100']:+.3f}")
    for name, qty in zip(NAMES, q):
        if qty > 0:
            print(f"  BUY  {int(qty):>4d}  {name}")
        elif qty < 0:
            print(f"  SELL {int(-qty):>4d}  {name}")


if __name__ == "__main__":
    main()
