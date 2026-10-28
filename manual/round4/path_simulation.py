"""
IMC Prosperity 4 — Manual Aether options: path simulation for strategy comparison.

Spec (from problem statement):
- GBM, drift 0 in the sense of risk-neutral / zero rate: dlnS = -0.5*sigma^2*dt + sigma*sqrt(dt)*Z
  (equivalently dS = sigma*S*dW with r=0)
- sigma annual = 2.51, 252 trading days/year, 4 steps per trading day
- Compare batch mean PnL over 100 paths (tournament scoring)
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy.special import erf


SIGMA = 2.51
DAYS_PER_YEAR = 252
STEPS_PER_DAY = 4
S0 = 50.0
WEEKS_2_DAYS = 10  # 2 weeks = 10 business days
WEEKS_3_DAYS = 15  # 3 weeks = 15 business days


def dt_one_step_years() -> float:
    return (1.0 / DAYS_PER_YEAR) / STEPS_PER_DAY


def simulate_paths(
    rng: np.random.Generator,
    n_paths: int,
    n_trading_days: int,
) -> np.ndarray:
    """
    Returns S of shape (n_paths, n_steps + 1) where n_steps = n_trading_days * STEPS_PER_DAY.
    Index 0 = S0, each block of STEPS_PER_DAY is one trading day.
    """
    n_steps = n_trading_days * STEPS_PER_DAY
    dt = dt_one_step_years()
    drift = -0.5 * SIGMA**2 * dt
    vol = SIGMA * math.sqrt(dt)

    Z = rng.standard_normal((n_paths, n_steps))
    inc = drift + vol * Z
    cum = np.cumsum(inc, axis=1)
    out = np.empty((n_paths, n_steps + 1))
    out[:, 0] = S0
    out[:, 1:] = S0 * np.exp(cum)
    return out


def bs_european_call_put(
    S: np.ndarray,
    K: float,
    tau_years: float,
    r: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized Black–Scholes C and P (no dividends). tau can be 0 -> intrinsic."""
    eps = 1e-14
    tau = np.maximum(tau_years, eps)
    sqrt_t = np.sqrt(tau)
    d1 = (np.log(S / K) + (r + 0.5 * SIGMA**2) * tau) / (SIGMA * sqrt_t)
    d2 = d1 - SIGMA * sqrt_t
    # standard normal CDF (scipy.special.erf is vectorized)
    def norm_cdf(x: np.ndarray) -> np.ndarray:
        return 0.5 * (1.0 + erf(x / math.sqrt(2.0)))

    Nd1 = norm_cdf(d1)
    Nd2 = norm_cdf(d2)
    Nmd1 = norm_cdf(-d1)
    Nmd2 = norm_cdf(-d2)
    disc = math.exp(-r * tau_years) if r != 0.0 else 1.0
    C = S * Nd1 - K * disc * Nd2
    P = K * disc * Nmd2 - S * Nmd1
    # intrinsic limit as tau -> 0
    if tau_years <= 0.0:
        C = np.maximum(S - K, 0.0)
        P = np.maximum(K - S, 0.0)
    return C, P


def pnl_chooser_arb(
    S: np.ndarray,
    K: float = 50.0,
) -> np.ndarray:
    """
    Sell CO at bid, buy C(3w) ask + P(2w) ask. Per-unit PnL in $.
    T1 = 10d, T2 = 15d. Chooser: at T1 pick side with higher BS continuation value.
    """
    cash0 = 22.20 - 12.05 - 9.75  # +0.40
    idx_T1 = WEEKS_2_DAYS * STEPS_PER_DAY
    idx_T2 = WEEKS_3_DAYS * STEPS_PER_DAY
    S1 = S[:, idx_T1]
    ST = S[:, idx_T2]

    tau_rem = (WEEKS_3_DAYS - WEEKS_2_DAYS) / DAYS_PER_YEAR  # 5/252
    C5, P5 = bs_european_call_put(S1, K, tau_rem, 0.0)
    choose_call = C5 >= P5

    long_put2 = np.maximum(K - S1, 0.0)
    long_call3 = np.maximum(ST - K, 0.0)
    short_co = np.where(choose_call, np.maximum(ST - K, 0.0), np.maximum(K - ST, 0.0))

    return cash0 + long_put2 + long_call3 - short_co


def pnl_short_binary(
    S: np.ndarray,
    strike: float = 40.0,
    payoff: float = 10.0,
    bid: float = 5.0,
) -> np.ndarray:
    idx_T = WEEKS_3_DAYS * STEPS_PER_DAY
    ST = S[:, idx_T]
    digital = (ST < strike).astype(float) * payoff
    return bid - digital


def pnl_short_ko_put(
    S: np.ndarray,
    K: float = 45.0,
    barrier: float = 45.0,
    bid: float = 0.15,
) -> np.ndarray:
    """Down-and-out put: dead if any S < barrier before expiry; else (K-S_T)+."""
    idx_T = WEEKS_3_DAYS * STEPS_PER_DAY
    alive = np.all(S[:, : idx_T + 1] >= barrier - 1e-12, axis=1)
    intrinsic = np.maximum(K - S[:, idx_T], 0.0)
    payoff_long = np.where(alive, intrinsic, 0.0)
    return bid - payoff_long


def batch_mean_scores(
    pnl_per_path: np.ndarray,
    batch_size: int = 100,
) -> np.ndarray:
    """Tournament-style: mean PnL over disjoint batches of `batch_size` paths."""
    n = pnl_per_path.size
    n_batches = n // batch_size
    pnl = pnl_per_path[: n_batches * batch_size].reshape(n_batches, batch_size)
    return pnl.mean(axis=1)


@dataclass
class StrategyResult:
    name: str
    mean_per_path: float
    std_per_path: float
    mean_batch100: float
    std_batch100: float
    p5_batch: float
    p95_batch: float


def run_strategies(
    n_paths: int = 500_000,
    seed: int = 42,
) -> list[StrategyResult]:
    rng = np.random.default_rng(seed)
    S = simulate_paths(rng, n_paths, WEEKS_3_DAYS)

    strategies: list[tuple[str, Callable[[np.ndarray], np.ndarray]]] = [
        ("A_chooser_arb", pnl_chooser_arb),
        ("B_short_binary_BP", pnl_short_binary),
        ("C_short_KO", pnl_short_ko_put),
        ("A+B+C_combined", lambda x: pnl_chooser_arb(x) + pnl_short_binary(x) + pnl_short_ko_put(x)),
        ("B_only_x50_scale", lambda x: 50.0 * pnl_short_binary(x)),
        ("A_x50", lambda x: 50.0 * pnl_chooser_arb(x)),
        (
            "full_ABC_x50_each",
            lambda x: 50.0 * (pnl_chooser_arb(x) + pnl_short_binary(x) + pnl_short_ko_put(x)),
        ),
    ]

    results: list[StrategyResult] = []
    for name, fn in strategies:
        p = fn(S)
        bm = batch_mean_scores(p, 100)
        results.append(
            StrategyResult(
                name=name,
                mean_per_path=float(p.mean()),
                std_per_path=float(p.std()),
                mean_batch100=float(bm.mean()),
                std_batch100=float(bm.std()),
                p5_batch=float(np.percentile(bm, 5)),
                p95_batch=float(np.percentile(bm, 95)),
            )
        )
    return results


def main() -> None:
    n = 500_000
    if len(sys.argv) > 1:
        n = int(sys.argv[1])
    print(f"Paths: {n}, sigma={SIGMA}, steps/day={STEPS_PER_DAY}")
    res = run_strategies(n_paths=n, seed=42)
    print("\nPer-path ($, 1 unit each leg for A/B/C; scaled rows as named):")
    for r in res:
        print(
            f"  {r.name:22s} E[path]={r.mean_per_path:+.6f}  sd={r.std_per_path:.4f}  "
            f"E[batch100]={r.mean_batch100:+.6f}  sd_batch={r.std_batch100:.4f}  "
            f"P5={r.p5_batch:+.4f} P95={r.p95_batch:+.4f}"
        )

    # Rank by expected batch score (proxy for tournament)
    ranked = sorted(res, key=lambda x: x.mean_batch100, reverse=True)
    print("\nRanked by E[mean over 100 paths]:")
    for i, r in enumerate(ranked, 1):
        print(f"  {i}. {r.name}")


if __name__ == "__main__":
    main()
