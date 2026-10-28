"""
Plots cumulative backtest PnL per round from prosperity4bt output logs.

  python -m prosperity4bt round1/trader.py 1 --out logs/r1.log    # one log per round: r0.log ... r5.log
  python scripts/plot_backtests.py logs docs/backtest_pnl.png
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

TITLES = {
    0: "Tutorial",
    1: "Round 1",
    2: "Round 2",
    3: "Round 3",
    4: "Round 4",
    5: "Round 5",
}
TOP_PRODUCTS = 3


def read_activities(path: Path) -> pd.DataFrame:
    text = path.read_text(encoding="utf-8")
    start = text.index("Activities log:") + len("Activities log:")
    end = text.index("Trade History:", start)
    df = pd.read_csv(io.StringIO(text[start:end].strip()), sep=";")
    # When one side of the book is empty the log reports mid_price 0 and marks
    # the position at 0; treat those ticks as missing and carry the last value.
    df.loc[df["mid_price"].fillna(0) <= 0, "profit_and_loss"] = float("nan")
    df["profit_and_loss"] = df.groupby(["day", "product"])["profit_and_loss"].ffill().fillna(0.0)
    return df[["day", "timestamp", "product", "profit_and_loss"]]


def cumulative_pnl(df: pd.DataFrame) -> pd.DataFrame:
    """PnL per product on one continuous axis across days (PnL restarts each day in the log)."""
    wide = df.pivot_table(index=["day", "timestamp"], columns="product", values="profit_and_loss").sort_index()
    out = []
    carry = pd.Series(0.0, index=wide.columns)
    for _, day in wide.groupby(level="day"):
        out.append(day + carry)
        carry = carry + day.iloc[-1]
    return pd.concat(out).reset_index(drop=True)


def main() -> None:
    logs, dest = Path(sys.argv[1]), Path(sys.argv[2])
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    for ax, (n, title) in zip(axes.flat, TITLES.items()):
        log = logs / f"r{n}.log"
        if not log.exists():
            ax.set_visible(False)
            continue
        df = read_activities(log)
        pnl = cumulative_pnl(df)
        x = pd.RangeIndex(len(pnl))

        ax.plot(x, pnl.sum(axis=1) / 1e3, color="black", lw=1.6, label="total")
        top = pnl.iloc[-1].sort_values(ascending=False).index[:TOP_PRODUCTS]
        for product in top:
            ax.plot(x, pnl[product] / 1e3, lw=1, label=product)
        rest = pnl.columns.difference(top)
        if len(rest) > 0:
            ax.plot(x, pnl[rest].sum(axis=1) / 1e3, lw=1, ls="--", color="grey",
                    label=f"other {len(rest)} products")

        n_days = df["day"].nunique()
        for d in range(1, n_days):
            ax.axvline(len(pnl) * d / n_days, color="lightgrey", lw=0.8)
        ax.set_title(f"{title} ({n_days} days)")
        ax.set_xticks([])
        ax.set_ylabel("PnL (thousand XIRECs)")
        ax.legend(fontsize=7, loc="upper left")

    fig.suptitle("Backtest PnL by round (in-sample)")
    fig.tight_layout()
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=110)
    print(f"wrote {dest}")


if __name__ == "__main__":
    main()
