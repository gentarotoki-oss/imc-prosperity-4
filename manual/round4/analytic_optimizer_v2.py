#!/usr/bin/env python3
"""Globally-optimal portfolio for the Round 4 manual challenge.

Formulation (MISOCP, solved by SCIP via cvxpy):

    variables: q_b, q_s in Z^12_+,  q = q_b - q_s,  t >= 0
    constraints:
        0 <= q_b <= LIMITS,  0 <= q_s <= LIMITS    (integer)
        t >= ||L^T q||_2                            (SOC, with cov = L L^T)
    objective (mean - lambda * std):
        maximize  (mu - ASKS) . q_b + (BIDS - mu) . q_s  -  lambda * t

Because ASK > BID, the bilinear cost (q_b * ASKS - q_s * BIDS) makes any
solution with q_b_i and q_s_i both positive strictly suboptimal -> no
big-M / disjunction needed. The model is a true MISOCP with at most
24 bounded integer variables, which SCIP solves to global optimum in
seconds.

We sweep lambda along the efficient frontier to expose the trade-off
between mean and tail (mean - 0.25*std, mean - 2.33*std/sqrt(100), ...)
and report the best portfolio by analytic 100-run 1% lower bound.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import cvxpy as cp
import numpy as np

from analytic_optimizer import (
    NAMES, BIDS, ASKS, LIMITS,
    TWO_WEEK_DAYS, THREE_WEEK_DAYS, DEFAULT_ELAPSED_DAYS,
    analytic_stats, eval_metrics,
)


def solve_misocp(mu: np.ndarray, cov: np.ndarray, lam: float, solver: str = "SCIP",
                 time_limit: float | None = None, verbose: bool = False) -> np.ndarray:
    """max  (mu-ASK).qb + (BID-mu).qs - lam * ||L^T (qb-qs)||_2,  qb,qs in Z+ <= LIMITS"""
    n = len(mu)
    # Stable factor: cov = L L^T (L is sqrt of psd cov via eigen, robust to tiny negative evals).
    w, V = np.linalg.eigh(cov)
    w = np.clip(w, 0.0, None)
    L = V * np.sqrt(w)  # n x n,  cov = L L^T  =>  std = ||L^T q||

    qb = cp.Variable(n, integer=True)
    qs = cp.Variable(n, integer=True)
    q = qb - qs
    cons = [qb >= 0, qs >= 0, qb <= LIMITS, qs <= LIMITS]

    buy_edge = mu - ASKS
    sell_edge = BIDS - mu
    mean_pnl = buy_edge @ qb + sell_edge @ qs

    if lam <= 0:
        objective = cp.Maximize(mean_pnl)
    else:
        t = cp.Variable(nonneg=True)
        cons.append(cp.SOC(t, L.T @ q))
        objective = cp.Maximize(mean_pnl - lam * t)

    prob = cp.Problem(objective, cons)
    kwargs = {"verbose": verbose}
    if solver == "SCIP" and time_limit is not None:
        kwargs["scip_params"] = {"limits/time": time_limit}
    prob.solve(solver=solver, **kwargs)
    if qb.value is None:
        raise RuntimeError(f"solver failed: status={prob.status}")
    return np.rint(qb.value - qs.value).astype(int)


def sharpe_dinkelbach(mu: np.ndarray, cov: np.ndarray, tol: float = 1e-4,
                      max_iter: int = 25, time_limit: float | None = 30.0) -> tuple[np.ndarray, float]:
    """Maximize mean / std via Dinkelbach: find gamma* with opt(mean - gamma*std)=0.

    Returns the q* with positive scaling that maximizes Sharpe (we then scale to limits)."""
    gamma_lo, gamma_hi = 0.0, 100.0
    best_q = None
    # First, find an upper bound: any feasible q with positive mean.
    q_pos = solve_misocp(mu, cov, lam=0.0, time_limit=time_limit)
    m = eval_metrics(q_pos, mu, cov)
    if m["mean"] <= 0 or m["std"] <= 1e-9:
        return q_pos, 0.0
    gamma = m["mean"] / m["std"]  # initial guess = current sharpe

    for _ in range(max_iter):
        q = solve_misocp(mu, cov, lam=gamma, time_limit=time_limit)
        mq = eval_metrics(q, mu, cov)
        residual = mq["mean"] - gamma * mq["std"]
        if residual < tol * max(1.0, abs(mq["mean"])):
            best_q = q
            break
        gamma = mq["mean"] / mq["std"] if mq["std"] > 1e-9 else gamma
        best_q = q
    return best_q, gamma


def write_report(path: Path, mu: np.ndarray, cov: np.ndarray,
                 frontier: list[tuple[float, np.ndarray, dict]], args) -> None:
    with path.open("w") as f:
        f.write("# Globally-Optimal Portfolio (MISOCP / SCIP)\n\n")
        f.write("## Inputs\n\n")
        f.write("| Field | Value |\n|---|---:|\n")
        f.write(f"| Elapsed days | {args.elapsed} |\n")
        f.write(f"| Remaining chooser / final days | {TWO_WEEK_DAYS - args.elapsed} / {THREE_WEEK_DAYS - args.elapsed} |\n")
        f.write(f"| Steps per day | {args.steps} |\n")
        f.write(f"| KO grid / order | {args.ko_grid} / {args.ko_order} |\n\n")

        f.write("## Fair Values\n\n")
        f.write("| Product | Bid | Ask | Fair | Buy edge | Sell edge |\n|---|---:|---:|---:|---:|---:|\n")
        for i, name in enumerate(NAMES):
            f.write(f"| {name} | {BIDS[i]:.4f} | {ASKS[i]:.4f} | {mu[i]:.4f} | "
                    f"{mu[i]-ASKS[i]:+.4f} | {BIDS[i]-mu[i]:+.4f} |\n")

        f.write("\n## Efficient Frontier (mean - lambda * std)\n\n")
        f.write("| lambda | Mean | Std | Sharpe | mean-0.25 std | 100-run 5% LB | 100-run 1% LB |\n")
        f.write("|---:|---:|---:|---:|---:|---:|---:|\n")
        for lam, _, m in frontier:
            f.write(f"| {lam:.4f} | {m['mean']:+.4f} | {m['std']:.4f} | {m['sharpe']:+.4f} | "
                    f"{m['u025']:+.4f} | {m['p5_100']:+.4f} | {m['p1_100']:+.4f} |\n")

        recommended = max(frontier, key=lambda it: (it[2]["p1_100"], it[2]["p5_100"]))
        f.write("\n## Recommended (max 100-run 1% LB)\n\n")
        lam, q, m = recommended
        f.write(f"- lambda = `{lam}`\n")
        f.write(f"- Mean: `{m['mean']:+.4f}`,  Std: `{m['std']:.4f}`,  Sharpe: `{m['sharpe']:+.4f}`\n")
        f.write(f"- 100-run 5% LB: `{m['p5_100']:+.4f}`,  1% LB: `{m['p1_100']:+.4f}`\n\n")

        f.write("## Positions per lambda\n\n")
        for lam, q, _ in frontier:
            f.write(f"### lambda = {lam}\n\n")
            f.write("| Product | Position |\n|---|---:|\n")
            any_pos = False
            for name, qty in zip(NAMES, q):
                if qty == 0:
                    continue
                any_pos = True
                f.write(f"| {name} | {'BUY' if qty > 0 else 'SELL'} {abs(int(qty))} |\n")
            if not any_pos:
                f.write("| FLAT | 0 |\n")
            f.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--elapsed", type=int, default=DEFAULT_ELAPSED_DAYS)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--quad-order", type=int, default=401)
    parser.add_argument("--quad-range", type=float, default=8.0)
    parser.add_argument("--ko-grid", type=int, default=8001)
    parser.add_argument("--ko-order", type=int, default=41)
    parser.add_argument("--lambdas", type=str,
                        default="0,0.001,0.005,0.01,0.02,0.05,0.1,0.2,0.5,1.0")
    parser.add_argument("--time-limit", type=float, default=60.0,
                        help="SCIP time limit per solve (seconds)")
    parser.add_argument("--solver", type=str, default="SCIP")
    parser.add_argument("--markdown", default="analytic_optimizer_v2_report.md")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    choice_days = TWO_WEEK_DAYS - args.elapsed
    final_days = THREE_WEEK_DAYS - args.elapsed
    if choice_days <= 0 or final_days <= 0:
        raise ValueError("elapsed leaves non-positive time")

    print("computing analytic mean/cov ...")
    mu, cov = analytic_stats(choice_days, final_days, args.steps,
                             args.quad_order, args.quad_range,
                             args.ko_grid, args.ko_order)
    print("done.")

    lambdas = [float(x) for x in args.lambdas.split(",") if x.strip()]
    frontier = []
    for lam in lambdas:
        print(f"solving MISOCP  lambda={lam} ...", flush=True)
        q = solve_misocp(mu, cov, lam, solver=args.solver,
                         time_limit=args.time_limit, verbose=args.verbose)
        m = eval_metrics(q, mu, cov)
        print(f"  mean={m['mean']:+.3f}  std={m['std']:.3f}  sharpe={m['sharpe']:+.3f}  "
              f"p1%LB={m['p1_100']:+.3f}")
        frontier.append((lam, q, m))

    # Also compute Sharpe-optimal via Dinkelbach
    print("solving max-Sharpe via Dinkelbach ...", flush=True)
    try:
        q_sh, gamma = sharpe_dinkelbach(mu, cov, time_limit=args.time_limit)
        m = eval_metrics(q_sh, mu, cov)
        print(f"  gamma*={gamma:.4f}  mean={m['mean']:+.3f}  std={m['std']:.3f}  "
              f"sharpe={m['sharpe']:+.3f}  p1%LB={m['p1_100']:+.3f}")
        frontier.append((float(f"{gamma:.4f}"), q_sh, m))
    except Exception as e:
        print(f"  Dinkelbach failed: {e}")

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
