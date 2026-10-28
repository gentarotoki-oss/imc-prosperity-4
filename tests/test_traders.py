"""
Smoke tests for every round's trader on randomly generated order books.

Each test feeds a trader a few hundred ticks of synthetic books, random
positions and random market trades, passing traderData back each tick, and
checks that it never sends orders that could breach a position limit. The
exchange rejects all of a product's orders when they could, so this is the
bug that costs the most.
"""

from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path

import pytest
from prosperity4bt import datamodel
from prosperity4bt.datamodel import Listing, Observation, OrderDepth, Trade, TradingState

ROOT = Path(__file__).resolve().parents[1]

# The traders import `datamodel` as a top-level module, as on the exchange.
sys.modules.setdefault("datamodel", datamodel)

VOUCHER_STRIKES = [4000, 4500, 5000, 5100, 5200, 5300, 5400, 5500, 6000, 6500]
ROUND3_PRODUCTS = {
    "HYDROGEL_PACK": (10_000, 200),
    "VELVETFRUIT_EXTRACT": (5_250, 200),
    **{f"VEV_{k}": (max(5_250 - k, 0) + 10, 300) for k in VOUCHER_STRIKES},
}


def load_trader(round_dir: str):
    path = ROOT / round_dir / "trader.py"
    spec = importlib.util.spec_from_file_location(f"{round_dir}_trader", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def round5_products(module) -> dict[str, tuple[int, int]]:
    """Every product constant defined in the round 5 trader, priced around 10,000 with limit 10."""
    names = [v for k, v in vars(module).items() if isinstance(v, str) and k == v and k.isupper()]
    return {name: (10_000, 10) for name in names}


def make_book(rng: random.Random, fair: float) -> OrderDepth:
    depth = OrderDepth()
    half_spread = rng.randint(1, 8)
    bid, ask = int(fair) - half_spread, int(fair) + half_spread
    # occasionally leave one side empty, as happens in the real books
    if rng.random() > 0.05:
        for i in range(rng.randint(1, 3)):
            depth.buy_orders[bid - i] = rng.randint(1, 30)
    if rng.random() > 0.05:
        for i in range(rng.randint(1, 3)):
            depth.sell_orders[ask + i] = -rng.randint(1, 30)
    return depth


def simulate(trader, products: dict[str, tuple[int, int]], ticks: int = 300, seed: int = 0) -> None:
    rng = random.Random(seed)
    fairs = {p: float(price) for p, (price, _) in products.items()}
    trader_data = ""
    bots = ["Mark 01", "Mark 22", "Mark 49", "SUBMISSION"]

    for tick in range(ticks):
        timestamp = tick * 100
        for p in fairs:
            fairs[p] = max(1.0, fairs[p] + rng.gauss(0, 2))

        positions = {p: rng.randint(-limit, limit) for p, (_, limit) in products.items()}
        market_trades = {
            p: [Trade(p, int(fairs[p]), rng.randint(1, 5), rng.choice(bots), rng.choice(bots), timestamp - 100)]
            for p in products
            if rng.random() < 0.2
        }
        state = TradingState(
            traderData=trader_data,
            timestamp=timestamp,
            listings={p: Listing(p, p, "XIRECS") for p in products},
            order_depths={p: make_book(rng, fairs[p]) for p in products},
            own_trades={},
            market_trades=market_trades,
            position=positions,
            observations=Observation({}, {}),
        )

        orders, conversions, trader_data = trader.run(state)

        assert isinstance(trader_data, str)
        for product, product_orders in orders.items():
            limit = products[product][1]
            pos = positions[product]
            buys = sum(o.quantity for o in product_orders if o.quantity > 0)
            sells = -sum(o.quantity for o in product_orders if o.quantity < 0)
            assert buys <= limit - pos, f"t={timestamp} {product}: buys {buys} with position {pos}/{limit}"
            assert sells <= limit + pos, f"t={timestamp} {product}: sells {sells} with position {pos}/{limit}"
            for o in product_orders:
                assert isinstance(o.price, int), f"{product}: non-integer price {o.price!r}"


@pytest.mark.parametrize(
    "round_dir, products",
    [
        ("round0", {"EMERALDS": (10_000, 80), "TOMATOES": (5_000, 80)}),
        ("round1", {"ASH_COATED_OSMIUM": (10_000, 80), "INTARIAN_PEPPER_ROOT": (12_000, 80)}),
        ("round2", {"ASH_COATED_OSMIUM": (10_000, 80), "INTARIAN_PEPPER_ROOT": (12_000, 80)}),
        ("round3", ROUND3_PRODUCTS),
        ("round4", ROUND3_PRODUCTS),
    ],
)
def test_trader_respects_position_limits(round_dir, products, capsys):
    simulate(load_trader(round_dir).Trader(), products)


def test_round5_trader_respects_position_limits(capsys):
    module = load_trader("round5")
    products = round5_products(module)
    assert len(products) == 50
    simulate(module.Trader(), products)


def test_example_respects_position_limits(capsys):
    spec = importlib.util.spec_from_file_location("example", ROOT / "examples" / "simple_market_maker.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    simulate(module.Trader(), {"ASH_COATED_OSMIUM": (10_000, 80)})
