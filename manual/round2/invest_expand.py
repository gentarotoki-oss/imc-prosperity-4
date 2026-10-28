"""
Round 2 Manual Challenge: "Invest & Expand"

Problem
-------
Budget: 50,000 XIRECs (allocate percentages R, S, z across 3 pillars).
Constraints: R, S, z in [0, 100], R + S + z <= 100.

PnL = Research(R) * Scale(S) * Speed(z) - BudgetUsed
    where BudgetUsed = (R+S+z)/100 * 50_000

Pillars:
  Research(R) = 200_000 * ln(1+R) / ln(101)      (concave, big upside)
  Scale(S)    = 7 * S / 100                       (linear)
  Speed(z)    = rank-based multiplier in [0.1, 0.9]
                depends on COMPETITORS' investments -> game-theoretic.

Since Speed depends on what others do, we solve the problem under several
candidate beliefs about the competitor distribution and report all of them.

Approach:
 1) coarse grid search (1% step) -> starting point
 2) SLSQP refinement               -> sub-percent accuracy
 3) print allocation & PnL for every speed model

Usage:
  python invest_expand.py
"""

from __future__ import annotations
import numpy as np
from scipy.optimize import minimize

BUDGET = 50_000          # total XIRECs at stake
LOG101 = np.log(101)

# ---------- Pillars ----------

def research(x: float) -> float:
    return 200_000.0 * np.log(1.0 + x) / LOG101

def scale(y: float) -> float:
    return 7.0 * y / 100.0


# ---------- Speed models ----------
# Each maps z in [0,100] to a multiplier in [0.1, 0.9].
# Interpretation: q(z) = fraction of competitors we beat at investment z.
# Multiplier = 0.1 + 0.8 * q(z).

def _mix(q: float) -> float:
    q = float(np.clip(q, 0.0, 1.0))
    return 0.1 + 0.8 * q

def speed_uniform(z: float) -> float:
    """Competitors ~ Uniform[0, 100]. Simplest prior."""
    return _mix(z / 100.0)

def speed_low_competition(z: float) -> float:
    """Most competitors under-invest in Speed (exponential, mean=15).
       -> even modest z gets a high rank."""
    q = 1.0 - np.exp(-z / 15.0)
    return _mix(q)

def speed_high_competition(z: float) -> float:
    """Most competitors over-invest in Speed (convex CDF).
       -> you need a lot to rank high."""
    q = (z / 100.0) ** 2
    return _mix(q)

def speed_peak_33(z: float) -> float:
    """Competitors' Speed bids peak around 33% (people try to 'balance' 1/3-1/3-1/3).
       CDF modelled as Beta(2,4) on [0,100]."""
    from math import comb
    # Beta(2,4) CDF = I_x(2,4) = 1 - (1-x)^4 * (1 + 4x/(1-x))  ... use numeric integration
    x = z / 100.0
    # Closed form: regularized incomplete beta B(2,4).
    # F(x) = x^2 (10 - 20x + 15x^2 - 4x^3)  (from integrating 20 x (1-x)^3)
    q = x * x * (10 - 20 * x + 15 * x * x - 4 * x ** 3)
    return _mix(q)

def speed_bimodal(z: float) -> float:
    """Half the field invests ~0, the other half invests ~60.
       Stepwise: z<60 beats only the 0-group (q=0.5), z>=60 beats all (q=1.0)."""
    if z <= 0:
        q = 0.0
    elif z < 60:
        q = 0.5
    else:
        q = 1.0
    return _mix(q)

SPEED_MODELS = {
    "uniform[0,100]  (neutral prior)":             speed_uniform,
    "exp mean=15     (low competition)":           speed_low_competition,
    "convex z^2      (high competition)":          speed_high_competition,
    "Beta(2,4)*100   (peak ~33%, realistic?)":     speed_peak_33,
    "bimodal 0/60    (half skip, half invest)":    speed_bimodal,
}


# ---------- PnL ----------

def pnl(R: float, S: float, z: float, speed_fn) -> float:
    total = R + S + z
    if total > 100.0 + 1e-9 or min(R, S, z) < -1e-9:
        return -1e18
    gross = research(R) * scale(S) * speed_fn(z)
    cost = total / 100.0 * BUDGET
    return gross - cost


# ---------- Solvers ----------

def grid_search(speed_fn, step: float = 1.0):
    best_val = -np.inf
    best_xyz = (0.0, 0.0, 0.0)
    grid = np.arange(0.0, 100.0 + 1e-9, step)
    for R in grid:
        for S in grid:
            if R + S > 100.0 + 1e-9:
                break
            zmax = 100.0 - R - S
            # differentiating wrt z only affects Speed; scan the full row
            for z in grid:
                if z > zmax + 1e-9:
                    break
                v = pnl(R, S, z, speed_fn)
                if v > best_val:
                    best_val = v
                    best_xyz = (R, S, z)
    return best_val, best_xyz


def refine_scipy(speed_fn, x0):
    def neg(x):
        return -pnl(x[0], x[1], x[2], speed_fn)
    cons = [{"type": "ineq", "fun": lambda x: 100.0 - x[0] - x[1] - x[2]}]
    bnds = [(0.0, 100.0)] * 3
    res = minimize(neg, np.asarray(x0, dtype=float),
                   method="SLSQP", bounds=bnds, constraints=cons,
                   options={"ftol": 1e-9, "maxiter": 500})
    return -res.fun, tuple(res.x)


def solve(speed_fn):
    # coarse -> refine
    coarse_val, coarse_xyz = grid_search(speed_fn, step=1.0)
    fine_val, fine_xyz = refine_scipy(speed_fn, coarse_xyz)
    if fine_val < coarse_val:      # SLSQP can fail silently; fall back to grid
        fine_val, fine_xyz = coarse_val, coarse_xyz
    # also try from several random starts in case of local optima
    rng = np.random.default_rng(0)
    for _ in range(12):
        x0 = rng.uniform(0.0, 40.0, size=3)   # keep sum realistic
        v, x = refine_scipy(speed_fn, x0)
        if v > fine_val:
            fine_val, fine_xyz = v, x
    return fine_val, fine_xyz


# ---------- Reporting ----------

def report(name: str, speed_fn):
    val, (R, S, z) = solve(speed_fn)
    used_pct = R + S + z
    gross = research(R) * scale(S) * speed_fn(z)
    cost = used_pct / 100.0 * BUDGET
    print(f"\n--- speed model: {name} ---")
    print(f"  R = {R:6.2f}%     Research(R) = {research(R):>11,.1f}")
    print(f"  S = {S:6.2f}%     Scale(S)    = {scale(S):>11.4f}")
    print(f"  z = {z:6.2f}%     Speed(z)    = {speed_fn(z):>11.4f}")
    print(f"  budget used  = {used_pct:6.2f}%  ->  {cost:>10,.0f} XIRECs")
    print(f"  gross PnL    = {gross:>12,.0f}")
    print(f"  net  PnL     = {val:>12,.0f}")
    return R, S, z, val


def main():
    print("=" * 74)
    print(f"  Round 2 Manual Challenge - 'Invest & Expand'")
    print(f"  budget = {BUDGET:,} XIRECs   |   PnL = R(R) * S(S) * Speed(z) - used%")
    print("=" * 74)

    summary = []
    for name, fn in SPEED_MODELS.items():
        R, S, z, val = report(name, fn)
        summary.append((name, R, S, z, val))

    print("\n" + "=" * 74)
    print("  Summary")
    print("=" * 74)
    print(f"  {'speed model':42s}  {'R%':>6s} {'S%':>6s} {'z%':>6s}  {'netPnL':>10s}")
    for name, R, S, z, val in summary:
        print(f"  {name:42s}  {R:6.2f} {S:6.2f} {z:6.2f}  {val:>10,.0f}")

    # Robust recommendation: pick the allocation that performs best on AVERAGE
    # across all speed models (minimax-lite: trade worst-case vs mean).
    print("\n" + "=" * 74)
    print("  Robust choice (average PnL across all speed models)")
    print("=" * 74)

    def avg_pnl(x):
        R, S, z = x
        return float(np.mean([pnl(R, S, z, fn) for fn in SPEED_MODELS.values()]))

    best_avg = -np.inf
    best_xyz = None
    # seed with each model's optimum + a few random starts
    seeds = [(R, S, z) for (_, R, S, z, _) in summary]
    rng = np.random.default_rng(1)
    for _ in range(20):
        seeds.append(tuple(rng.uniform(0, 40, 3)))
    for x0 in seeds:
        def neg(x): return -avg_pnl(x)
        cons = [{"type": "ineq", "fun": lambda x: 100.0 - x.sum()}]
        res = minimize(neg, np.asarray(x0, dtype=float), method="SLSQP",
                       bounds=[(0.0, 100.0)] * 3, constraints=cons,
                       options={"ftol": 1e-9, "maxiter": 500})
        if -res.fun > best_avg:
            best_avg = -res.fun
            best_xyz = tuple(res.x)
    R, S, z = best_xyz
    print(f"  R = {R:6.2f}%     S = {S:6.2f}%     z = {z:6.2f}%")
    print(f"  used = {R+S+z:.2f}%   avg netPnL across models = {best_avg:,.0f}")
    print(f"  per-model:")
    for name, fn in SPEED_MODELS.items():
        print(f"    {name:42s} -> {pnl(R, S, z, fn):>10,.0f}")


# =====================================================================
# Additional analyses to tame the Speed uncertainty
# =====================================================================

def optimal_RS_given_z_and_m(z: float, m: float):
    """Given a fixed Speed multiplier m and Speed-budget z, find the
       (R, S) that maximises PnL subject to R + S <= 100 - z.
       Returns (R, S, pnl)."""
    budget_left = 100.0 - z
    def neg(x):
        R, S = x
        if R < 0 or S < 0 or R + S > budget_left + 1e-9:
            return 1e18
        gross = research(R) * scale(S) * m
        cost = (R + S + z) / 100.0 * BUDGET
        return -(gross - cost)
    best = (-np.inf, (0.0, 0.0))
    rng = np.random.default_rng(2)
    for seed in list(rng.uniform(0, budget_left / 2, size=(10, 2))) + [(budget_left / 4, budget_left / 2)]:
        res = minimize(neg, seed, method="SLSQP",
                       bounds=[(0.0, budget_left), (0.0, budget_left)],
                       constraints=[{"type": "ineq",
                                     "fun": lambda x, b=budget_left: b - x[0] - x[1]}],
                       options={"ftol": 1e-9, "maxiter": 400})
        if -res.fun > best[0]:
            best = (-res.fun, tuple(res.x))
    (R, S) = best[1]
    return R, S, best[0]


def speed_sensitivity_table():
    """For several candidate z allocations, show the PnL envelope as the
       realised Speed multiplier m varies.  This directly answers
       'what if my Speed ends up being X?'."""
    zs = [0, 10, 20, 30, 40, 50, 70]
    ms = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    print("\n" + "=" * 86)
    print("  Speed sensitivity: PnL given a fixed Speed investment z and realised multiplier m")
    print("  (R, S are re-optimised for each (z, m) pair)")
    print("=" * 86)
    header = "    z% |" + "".join(f"   m={m:.1f}   " for m in ms)
    print(header)
    print("   -----+" + "-" * (len(header) - 9))
    for z in zs:
        row = f"   {z:4d} |"
        for m in ms:
            R, S, v = optimal_RS_given_z_and_m(z, m)
            row += f" {v:>9,.0f}"
        print(row)

    # break-even m for each z: smallest m making PnL >= 0
    print("\n  Break-even Speed multiplier m* (smallest m with optimal R,S giving PnL>=0):")
    for z in zs:
        lo, hi = 0.0, 1.0
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            _, _, v = optimal_RS_given_z_and_m(z, mid)
            if v >= 0:
                hi = mid
            else:
                lo = mid
        print(f"     z = {z:3d}%  ->  m* = {hi:.3f}")


def minimax_over_speed():
    """Choose (R, S, z) maximising the WORST-case PnL across an adversarial
       choice of realised Speed multiplier m in [0.1, 0.9].
       Because PnL is linear in m, worst case is m=0.1 whenever the
       Research*Scale term is positive -- so this degenerates to solving
       the fixed-m=0.1 problem.  We also report expected PnL under
       m ~ Uniform[0.1, 0.9] for reference."""
    print("\n" + "=" * 74)
    print("  Min-max allocation (robust against ANY Speed realisation)")
    print("=" * 74)
    # m=0.1 worst case: optimal R, S given m=0.1, z free but z>0 only hurts
    # (since z costs budget and does not affect m here).
    best = (-np.inf, None)
    for z in np.arange(0, 80.001, 1.0):
        R, S, v = optimal_RS_given_z_and_m(z, 0.1)
        if v > best[0]:
            best = (v, (R, S, z))
    (R, S, z) = best[1]
    print(f"  worst-case (m=0.1): R={R:.2f}%  S={S:.2f}%  z={z:.2f}%  PnL={best[0]:,.0f}")

    # expected under m ~ Uniform[0.1, 0.9] (E[m]=0.5), linear in m
    best = (-np.inf, None)
    for z in np.arange(0, 80.001, 1.0):
        R, S, v = optimal_RS_given_z_and_m(z, 0.5)
        if v > best[0]:
            best = (v, (R, S, z))
    (R, S, z) = best[1]
    print(f"  mean-case  (m=0.5): R={R:.2f}%  S={S:.2f}%  z={z:.2f}%  PnL={best[0]:,.0f}")


# =====================================================================
# CLOSED-FORM: given z (Speed %), return optimal (R, S)
# =====================================================================
# Derivation:
#   max  K*ln(1+R) * 0.07*S * m  -  500*(R+S+z)
#   s.t. R + S = 100 - z       (budget binding; interior optimum is worse)
#
#   Let u = 1+R, B = 100-z. Substituting S = B-R into the objective and
#   setting dg/dR = 0 gives
#
#           u * (1 + ln u)  =  B + 1  =  101 - z
#
#   Note: R* depends ONLY on z. Not on m, not on K.  The Speed multiplier
#   just scales the final PnL.
# =====================================================================

def optimal_RS_from_z(z: float) -> tuple[float, float]:
    """Given Speed budget z% in [0, 100], return (R%, S%) that maximise PnL
       using the whole remaining budget (R + S = 100 - z).
       Uses Newton iteration on u*(1+ln u) = 101 - z."""
    target = 101.0 - z
    if target <= 1.0:           # z >= 100 -> no budget left
        return 0.0, max(0.0, 100.0 - z)

    # Newton iteration on h(u) = u*(1+ln u) - target
    # h'(u) = 2 + ln u
    u = max(1.5, target / 3.0)  # rough seed
    for _ in range(40):
        lnu = np.log(u)
        h  = u * (1.0 + lnu) - target
        hp = 2.0 + lnu
        u -= h / hp
        if u < 1.0 + 1e-12:
            u = 1.0 + 1e-12
    R = u - 1.0
    S = 100.0 - z - R
    if S < 0:                   # edge case, z near 100
        S = 0.0; R = 100.0 - z
    return R, S


def closed_form_table():
    print("\n" + "=" * 74)
    print("  Closed-form optimal (R, S) as a function of z")
    print("  (note: independent of the Speed multiplier m!)")
    print("=" * 74)
    print(f"  {'z%':>5s}  {'R%':>6s}  {'S%':>6s}  {'u=1+R':>7s}  check: u(1+ln u) vs 101-z")
    for z in range(0, 101, 5):
        R, S = optimal_RS_from_z(z)
        u = 1.0 + R
        lhs = u * (1.0 + np.log(u))
        rhs = 101.0 - z
        print(f"  {z:>5d}  {R:>6.3f}  {S:>6.3f}  {u:>7.3f}  {lhs:>8.3f}  vs  {rhs:>6.1f}")


if __name__ == "__main__":
    main()
    speed_sensitivity_table()
    minimax_over_speed()
    closed_form_table()
