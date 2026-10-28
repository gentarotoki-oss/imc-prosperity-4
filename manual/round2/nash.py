"""Symmetric-Nash equilibrium for the Round-2 manual challenge.

Assuming every player uses the closed-form R*(z), S*(z) substitution (so only
z is a decision variable) and that other players' z values are drawn from
some CDF F, your realised Speed multiplier is

        m(z) = 0.1 + 0.8 * F(z)                 (rank share in a large field)

Your expected payoff is

        pi(z) = A(z) * [0.1 + 0.8 * F(z)]  -  50_000

where A(z) = K * ln(1 + R*(z)) * 0.07 * S*(z)  is strictly DECREASING in z
(both R* and S* decrease).

Symmetric Nash:  pi(z) = const for every z in the support of F.
Differentiating,  d/dz [A(z) H(z)] = 0  with  H(z)=0.1+0.8F(z)  →  A*H = C.

Boundary:   F(0)=0  ⇒  C = 0.1 * A(0)
            F(z*)=1 ⇒  A(z*) = A(0)/9

Closed form CDF on [0, z*]:
            F(z) = (1/8) * [ A(0)/A(z)  −  1 ]

and the equilibrium payoff for every player is 0.1 * A(0) − 50_000.
"""

from __future__ import annotations
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import brentq

BUDGET  = 50_000
LOG101  = np.log(101)
K       = 200_000 / LOG101


def opt_RS(z: float) -> tuple[float, float]:
    target = 101.0 - z
    if target <= 1.0:
        return 0.0, max(0.0, 100.0 - z)
    u = max(1.5, target / 3.0)
    for _ in range(60):
        lnu = np.log(u)
        h   = u * (1.0 + lnu) - target
        hp  = 2.0 + lnu
        u  -= h / hp
    return u - 1.0, 100.0 - z - (u - 1.0)


def A(z: float) -> float:
    R, S = opt_RS(z)
    if R <= 0 or S <= 0:
        return 0.0
    return K * np.log(1.0 + R) * 0.07 * S


A0 = A(0.0)
print(f"A(0) = {A0:,.1f}")

# solve A(z*) = A(0)/9
target = A0 / 9.0
zstar = brentq(lambda z: A(z) - target, 0.01, 99.99)
print(f"A({zstar:.3f}) = {A(zstar):,.1f}   (target {target:,.1f})")

# ------------------------------------------------------------------
print("\n=====================================================")
print("  SYMMETRIC MIXED-STRATEGY NASH EQUILIBRIUM")
print("=====================================================")
print(f"  support of F     : [0,  {zstar:.3f}] %")
print(f"  payoff for every player (constant across support)")
print(f"    gross : 0.1 * A(0) = {0.1*A0:,.1f}")
print(f"    net   : gross - 50,000 = {0.1*A0 - 50_000:,.1f}")
print()

# tabulate the NE CDF
print(f"  z%       F(z)      m(z)     R*(z)    S*(z)")
for z in [0, 5, 10, 20, 30, 40, 50, 60, 70, zstar]:
    Fz = (A0 / A(z) - 1.0) / 8.0 if A(z) > 0 else 1.0
    Fz = max(0.0, min(1.0, Fz))
    mz = 0.1 + 0.8 * Fz
    R, S = opt_RS(z)
    print(f"  {z:6.3f}  {Fz:6.3f}  {mz:6.3f}  {R:7.3f}  {S:7.3f}")


# ------------------------------------------------------------------
# Plot
zs = np.linspace(0.0, zstar, 400)
As = np.array([A(z) for z in zs])
Fs = np.clip((A0 / As - 1.0) / 8.0, 0.0, 1.0)
ms = 0.1 + 0.8 * Fs
Rs = np.array([opt_RS(z)[0] for z in zs])
Ss = np.array([opt_RS(z)[1] for z in zs])
# PDF via numerical derivative
pdf = np.gradient(Fs, zs)

fig, axes = plt.subplots(1, 3, figsize=(16, 5))

ax = axes[0]
ax.plot(zs, Fs, lw=2, color="C0", label="NE CDF F(z)")
ax.plot(zs, ms, lw=2, color="C3", label="m(z) = 0.1 + 0.8 F(z)")
ax.axvline(zstar, ls=":", color="gray", label=f"z* = {zstar:.2f}")
ax.set_xlabel("z (Speed %)")
ax.set_ylabel("F(z) or m(z)")
ax.set_title("Nash CDF and realised multiplier")
ax.legend()
ax.grid(alpha=0.3)

ax = axes[1]
ax.plot(zs, pdf, lw=2, color="C2")
ax.axvline(zstar, ls=":", color="gray")
ax.fill_between(zs, 0, pdf, alpha=0.25, color="C2")
ax.set_xlabel("z (Speed %)")
ax.set_ylabel("NE density f(z)")
ax.set_title("Equilibrium mixing density")
ax.grid(alpha=0.3)

ax = axes[2]
payoff = As * ms - BUDGET
ax.plot(zs, payoff, lw=2, color="C4")
ax.axhline(0.1 * A0 - BUDGET, ls="--", color="gray",
           label=f"constant NE payoff = {0.1*A0-BUDGET:,.0f}")
ax.set_xlabel("z")
ax.set_ylabel("net PnL")
ax.set_title("Check: payoff flat across support")
ax.legend()
ax.grid(alpha=0.3)

plt.suptitle("Round 2 Manual - Symmetric Nash Equilibrium", fontsize=14)
plt.tight_layout()
plt.savefig("manual_nash.png", dpi=130, bbox_inches="tight")
print(f"\nsaved: manual_nash.png")
