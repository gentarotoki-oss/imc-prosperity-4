#!/usr/bin/env python3
import argparse
import math
from pathlib import Path

import numpy as np
from numpy.polynomial.hermite import hermgauss
from numpy.polynomial.legendre import leggauss

from analytic_pricer import binary_put, bs_call_put, chooser_price


S0 = 50.0
SIGMA = 2.51
TRADING_DAYS = 252
TWO_WEEK_DAYS = 10
THREE_WEEK_DAYS = 15
DEFAULT_ELAPSED_DAYS = 0

NAMES = [
    "AC",
    "AC_50_P",
    "AC_50_C",
    "AC_35_P",
    "AC_40_P",
    "AC_45_P",
    "AC_60_C",
    "AC_50_P_2",
    "AC_50_C_2",
    "AC_50_CO",
    "AC_40_BP",
    "AC_45_KO",
]
BIDS = np.array([49.975, 12.00, 12.00, 4.33, 6.50, 9.05, 8.80, 9.70, 9.70, 22.20, 5.00, 0.150])
ASKS = np.array([50.025, 12.05, 12.05, 4.35, 6.55, 9.10, 8.85, 9.75, 9.75, 22.30, 5.10, 0.175])
LIMITS = np.array([200, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 500], dtype=int)
AC = 0
KO = 11


def yearfrac(days: int) -> float:
    return days / TRADING_DAYS


def payoff_non_ko(s_choice: np.ndarray, s_final: np.ndarray) -> np.ndarray:
    p = np.empty((s_final.size, 11))
    p[:, 0] = s_final
    p[:, 1] = np.maximum(50 - s_final, 0.0)
    p[:, 2] = np.maximum(s_final - 50, 0.0)
    p[:, 3] = np.maximum(35 - s_final, 0.0)
    p[:, 4] = np.maximum(40 - s_final, 0.0)
    p[:, 5] = np.maximum(45 - s_final, 0.0)
    p[:, 6] = np.maximum(s_final - 60, 0.0)
    p[:, 7] = np.maximum(50 - s_choice, 0.0)
    p[:, 8] = np.maximum(s_choice - 50, 0.0)
    p[:, 9] = np.where(s_choice >= 50, np.maximum(s_final - 50, 0.0), np.maximum(50 - s_final, 0.0))
    p[:, 10] = np.where(s_final < 40, 10.0, 0.0)
    return p


def non_ko_moments(choice_days: int, final_days: int, order: int, z_range: float) -> tuple[np.ndarray, np.ndarray]:
    tc = yearfrac(choice_days)
    tf = yearfrac(final_days)
    dt2 = tf - tc
    gl_x, gl_w = leggauss(order)
    z = z_range * gl_x
    w = gl_w * z_range * np.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)

    z1, z2 = np.meshgrid(z, z, indexing="ij")
    ww = np.outer(w, w).reshape(-1)
    x_choice = math.log(S0) - 0.5 * SIGMA * SIGMA * tc + SIGMA * math.sqrt(tc) * z1.reshape(-1)
    x_final = x_choice - 0.5 * SIGMA * SIGMA * dt2 + SIGMA * math.sqrt(dt2) * z2.reshape(-1)
    pay = payoff_non_ko(np.exp(x_choice), np.exp(x_final))
    mean = ww @ pay
    second = pay.T @ (pay * ww[:, None])
    return mean, second


def exact_non_ko_means(choice_days: int, final_days: int) -> np.ndarray:
    call50_3w, put50_3w = bs_call_put(50, final_days)
    _, put35_3w = bs_call_put(35, final_days)
    _, put40_3w = bs_call_put(40, final_days)
    _, put45_3w = bs_call_put(45, final_days)
    call60_3w, _ = bs_call_put(60, final_days)
    call50_2w, put50_2w = bs_call_put(50, choice_days)
    return np.array([
        S0,
        put50_3w,
        call50_3w,
        put35_3w,
        put40_3w,
        put45_3w,
        call60_3w,
        put50_2w,
        call50_2w,
        chooser_price(50, choice_days, final_days),
        binary_put(40, 10, final_days),
    ])


def interp_at_s0(values: np.ndarray, x_grid: np.ndarray) -> np.ndarray:
    x0 = math.log(S0)
    pos = (x0 - x_grid[0]) / (x_grid[1] - x_grid[0])
    i = int(np.clip(pos, 0, len(x_grid) - 2))
    frac = pos - i
    return values[i] * (1.0 - frac) + values[i + 1] * frac


def backward_dp(
    values: np.ndarray,
    x_grid: np.ndarray,
    steps: int,
    z_nodes: np.ndarray,
    weights: np.ndarray,
    drift: float,
    vol: float,
    log_barrier: float,
) -> np.ndarray:
    out = values.copy()
    dx = x_grid[1] - x_grid[0]
    n = len(x_grid)
    for _ in range(steps):
        acc = np.zeros_like(out)
        for z, w in zip(z_nodes, weights):
            nx = x_grid + drift + vol * z
            pos = (nx - x_grid[0]) / dx
            idx = np.floor(pos).astype(np.int64)
            frac = pos - idx
            idx_clip = np.clip(idx, 0, n - 2)
            interp = out[idx_clip] * (1.0 - frac[:, None]) + out[idx_clip + 1] * frac[:, None]
            interp[nx < x_grid[0]] = 0.0
            interp[nx > x_grid[-1]] = out[-1]
            interp[nx < log_barrier] = 0.0
            acc += w * interp
        out = acc
    return out


def ko_cross_moments(
    choice_days: int,
    final_days: int,
    steps_per_day: int,
    grid_size: int,
    gh_order: int,
) -> tuple[float, np.ndarray, float]:
    steps = final_days * steps_per_day
    choice_step = choice_days * steps_per_day
    dt = 1.0 / (TRADING_DAYS * steps_per_day)
    drift = -0.5 * SIGMA * SIGMA * dt
    vol = SIGMA * math.sqrt(dt)
    total_std = SIGMA * math.sqrt(yearfrac(final_days))
    center = math.log(S0)
    barrier = math.log(35.0)
    lo = min(barrier - 0.75, center - 8.0 * total_std)
    hi = center + 8.0 * total_std
    x_grid = np.linspace(lo, hi, grid_size)
    s_grid = np.exp(x_grid)

    gh_x, gh_w = hermgauss(gh_order)
    z_nodes = math.sqrt(2.0) * gh_x
    weights = gh_w / math.sqrt(math.pi)

    ko = np.maximum(45 - s_grid, 0.0)
    ko[x_grid < barrier] = 0.0
    final_pay = payoff_non_ko(s_grid, s_grid)

    terminal = np.empty((grid_size, 12))
    terminal[:, 0] = ko
    terminal[:, 1] = ko * ko
    for j in range(7):
        terminal[:, 2 + j] = ko * final_pay[:, j]
    terminal[:, 9] = ko * final_pay[:, 10]
    terminal[:, 10] = ko * np.maximum(s_grid - 50, 0.0)
    terminal[:, 11] = ko * np.maximum(50 - s_grid, 0.0)

    initial_values = backward_dp(terminal, x_grid, steps, z_nodes, weights, drift, vol, barrier)
    at_initial = interp_at_s0(initial_values, x_grid)

    cross = np.empty(11)
    cross[:7] = at_initial[2:9]
    cross[10] = at_initial[9]
    ko_mean = float(at_initial[0])
    ko_second = float(at_initial[1])

    to_choice = backward_dp(terminal, x_grid, steps - choice_step, z_nodes, weights, drift, vol, barrier)
    choice_terminal = np.empty((grid_size, 3))
    choice_terminal[:, 0] = np.maximum(50 - s_grid, 0.0) * to_choice[:, 0]
    choice_terminal[:, 1] = np.maximum(s_grid - 50, 0.0) * to_choice[:, 0]
    choice_terminal[:, 2] = np.where(s_grid >= 50, to_choice[:, 10], to_choice[:, 11])
    choice_initial = backward_dp(choice_terminal, x_grid, choice_step, z_nodes, weights, drift, vol, barrier)
    choice_at_initial = interp_at_s0(choice_initial, x_grid)
    cross[7] = choice_at_initial[0]
    cross[8] = choice_at_initial[1]
    cross[9] = choice_at_initial[2]
    return ko_mean, cross, ko_second


def analytic_stats(choice_days: int, final_days: int, steps_per_day: int, quad_order: int, quad_range: float, ko_grid: int, ko_order: int):
    quad_mean11, second11 = non_ko_moments(choice_days, final_days, quad_order, quad_range)
    mean11 = exact_non_ko_means(choice_days, final_days)
    ko_mean, ko_cross, ko_second = ko_cross_moments(choice_days, final_days, steps_per_day, ko_grid, ko_order)
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


def trading_cost(q: np.ndarray) -> float:
    return float(np.where(q >= 0, q * ASKS, q * BIDS).sum())


def eval_metrics(q: np.ndarray, mu: np.ndarray, cov: np.ndarray) -> dict:
    mean = float(mu @ q - trading_cost(q))
    std = math.sqrt(max(float(q @ cov @ q), 0.0))
    return {
        "mean": mean,
        "std": std,
        "sharpe": mean / std if std > 1e-12 else 0.0,
        "u025": mean - 0.25 * std,
        "p5_100": mean - 1.65 * std / 10,
        "p1_100": mean - 2.33 * std / 10,
    }


OBJECTIVE_LABELS = {
    "mean": "mean",
    "u0165": "mean_minus_0.165_std",
    "u025": "mean_minus_0.25_std",
    "sharpe": "sharpe",
}


def objective_score(name: str, q: np.ndarray, mu: np.ndarray, cov: np.ndarray) -> float:
    m = eval_metrics(q, mu, cov)
    if name == "mean":
        return m["mean"]
    if name == "u0165":
        return m["mean"] - 0.165 * m["std"]
    if name == "u025":
        return m["u025"]
    if name == "sharpe":
        return m["sharpe"] if m["mean"] > 0 and m["std"] > 1e-12 else -1e100 + m["mean"]
    raise ValueError(name)


def scan_ac(q: np.ndarray, score_fn, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    best = q.copy()
    best_score = score_fn(best)
    for ac in range(int(lo[AC]), int(hi[AC]) + 1):
        trial = best.copy()
        trial[AC] = ac
        value = score_fn(trial)
        if value > best_score:
            best = trial
            best_score = value
    return best


def local_search(q0: np.ndarray, score_fn, lo: np.ndarray, hi: np.ndarray, max_passes: int) -> np.ndarray:
    q = np.rint(np.clip(q0, lo, hi)).astype(int)
    q = scan_ac(q, score_fn, lo, hi)
    best = score_fn(q)
    for step in (100, 50, 20, 10, 5, 2, 1):
        improved = True
        passes = 0
        while improved and passes < max_passes:
            passes += 1
            improved = False
            for i in range(len(q)):
                if lo[i] == hi[i]:
                    continue
                for d in (step, -step):
                    trial = q.copy()
                    trial[i] = int(np.clip(trial[i] + d, lo[i], hi[i]))
                    if trial[i] == q[i]:
                        continue
                    trial = scan_ac(trial, score_fn, lo, hi)
                    value = score_fn(trial)
                    if value > best + 1e-10:
                        q = trial
                        best = value
                        improved = True
    return q


def seeds(mu: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> list[np.ndarray]:
    out = [np.zeros(12)]
    buy_edge = mu - ASKS
    sell_edge = BIDS - mu
    greedy = np.zeros(12)
    for i in range(12):
        if buy_edge[i] > max(0.0, sell_edge[i]):
            greedy[i] = hi[i]
        elif sell_edge[i] > max(0.0, buy_edge[i]):
            greedy[i] = lo[i]
    out.extend([greedy, np.rint(greedy / 2), np.rint(greedy / 5)])
    return out


def optimize(objective: str, mu: np.ndarray, cov: np.ndarray, lo: np.ndarray, hi: np.ndarray, max_passes: int) -> np.ndarray:
    if objective == "mean":
        buy_edge = mu - ASKS
        sell_edge = BIDS - mu
        q = np.zeros(12, dtype=int)
        q[buy_edge > np.maximum(0.0, sell_edge)] = hi[buy_edge > np.maximum(0.0, sell_edge)]
        q[sell_edge > np.maximum(0.0, buy_edge)] = lo[sell_edge > np.maximum(0.0, buy_edge)]
        return q

    score_fn = lambda q: objective_score(objective, q, mu, cov)
    best_q = None
    best_score = -float("inf")
    for seed in seeds(mu, lo, hi):
        q = local_search(seed, score_fn, lo, hi, max_passes)
        value = score_fn(q)
        if value > best_score:
            best_q = q
            best_score = value
    return best_q


def write_markdown(path: Path, mu: np.ndarray, cov: np.ndarray, results: list[tuple[str, np.ndarray, dict]], args) -> None:
    with path.open("w") as f:
        f.write("# Analytic / DP Optimizer Report\n\n")
        f.write("## Inputs\n\n")
        f.write("| Field | Value |\n|---|---:|\n")
        f.write(f"| Elapsed days | {args.elapsed} |\n")
        f.write(f"| Remaining chooser days | {TWO_WEEK_DAYS - args.elapsed} |\n")
        f.write(f"| Remaining final days | {THREE_WEEK_DAYS - args.elapsed} |\n")
        f.write(f"| Steps per day | {args.steps} |\n")
        f.write(f"| Non-KO quadrature order | {args.quad_order} |\n")
        f.write(f"| Non-KO normal range | +/-{args.quad_range} sigma |\n")
        f.write(f"| KO grid size | {args.ko_grid} |\n")
        f.write(f"| KO quadrature order | {args.ko_order} |\n")
        f.write(f"| Local-search max passes per step | {args.max_passes} |\n\n")

        f.write("## Fair Values\n\n")
        f.write("| Product | Bid | Ask | Fair | Buy edge | Sell edge |\n|---|---:|---:|---:|---:|---:|\n")
        for i, name in enumerate(NAMES):
            f.write(f"| {name} | {BIDS[i]:.6f} | {ASKS[i]:.6f} | {mu[i]:.6f} | {mu[i] - ASKS[i]:.6f} | {BIDS[i] - mu[i]:.6f} |\n")

        f.write("\n## Result Summary\n\n")
        f.write("| Objective | Mean | Std | Sharpe | mean - 0.25 std | 100-run 5% LB | 100-run 1% LB |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|\n")
        for objective, _, m in results:
            label = OBJECTIVE_LABELS[objective]
            f.write(f"| {label} | {m['mean']:.6f} | {m['std']:.6f} | {m['sharpe']:.6f} | {m['u025']:.6f} | {m['p5_100']:.6f} | {m['p1_100']:.6f} |\n")

        recommended = max(results, key=lambda item: (item[2]["p1_100"], item[2]["p5_100"]))
        f.write("\n## Recommended\n\n")
        f.write("Selected by highest analytic `100-run 1% LB`, with `100-run 5% LB` as tie-breaker.\n\n")
        f.write(f"- Objective: `{OBJECTIVE_LABELS[recommended[0]]}`\n")
        f.write(f"- Mean: `{recommended[2]['mean']:.6f}`\n")
        f.write(f"- Std: `{recommended[2]['std']:.6f}`\n")
        f.write(f"- 100-run 5% LB: `{recommended[2]['p5_100']:.6f}`\n")
        f.write(f"- 100-run 1% LB: `{recommended[2]['p1_100']:.6f}`\n\n")

        f.write("## Positions\n\n")
        for objective, q, _ in results:
            f.write(f"### {OBJECTIVE_LABELS[objective]}\n\n")
            f.write("| Product | Position |\n|---|---:|\n")
            any_position = False
            for name, qty in zip(NAMES, q):
                if qty == 0:
                    continue
                any_position = True
                f.write(f"| {name} | {'BUY' if qty > 0 else 'SELL'} {abs(int(qty))} |\n")
            if not any_position:
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
    parser.add_argument("--max-passes", type=int, default=4)
    parser.add_argument("--markdown", default="analytic_optimizer_report.md")
    args = parser.parse_args()

    choice_days = TWO_WEEK_DAYS - args.elapsed
    final_days = THREE_WEEK_DAYS - args.elapsed
    if choice_days <= 0 or final_days <= 0:
        raise ValueError("elapsed leaves non-positive time")

    mu, cov = analytic_stats(choice_days, final_days, args.steps, args.quad_order, args.quad_range, args.ko_grid, args.ko_order)
    lo = -LIMITS
    hi = LIMITS
    results = []
    for objective in ("mean", "u0165", "u025", "sharpe"):
        q = optimize(objective, mu, cov, lo, hi, args.max_passes)
        results.append((objective, q, eval_metrics(q, mu, cov)))

    write_markdown(Path(args.markdown), mu, cov, results, args)
    print(f"markdown_report={args.markdown}")
    recommended = max(results, key=lambda item: (item[2]["p1_100"], item[2]["p5_100"]))
    print(f"recommended={OBJECTIVE_LABELS[recommended[0]]}")
    for name, qty in zip(NAMES, recommended[1]):
        if qty > 0:
            print(f"BUY {int(qty)} {name}")
        elif qty < 0:
            print(f"SELL {int(-qty)} {name}")


if __name__ == "__main__":
    main()
