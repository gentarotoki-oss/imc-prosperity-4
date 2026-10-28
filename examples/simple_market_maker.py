"""
The simplest strategy that makes money in Prosperity: market making around a
known fair value.

ASH_COATED_OSMIUM (round 1) trades around 10,000 all day. The strategy:
  1. Take: buy any ask below 10,000 and sell into any bid above 10,000.
  2. Make: post a bid just above the best bid and an ask just below the best
     ask, as long as they stay on the right side of fair value.
  3. Respect the position limit: never send orders that could take the
     position past ±80.

Every fill is bought below fair or sold above fair, so each one is a small
expected profit.

Run:
  python -m prosperity4bt examples/simple_market_maker.py 1
"""

from datamodel import Order, OrderDepth, TradingState

PRODUCT = "ASH_COATED_OSMIUM"
FAIR = 10_000
LIMIT = 80


class Trader:
    def run(self, state: TradingState):
        orders: dict[str, list[Order]] = {}
        if PRODUCT in state.order_depths:
            position = state.position.get(PRODUCT, 0)
            orders[PRODUCT] = self.market_make(state.order_depths[PRODUCT], position)
        return orders, 0, ""

    def market_make(self, depth: OrderDepth, position: int) -> list[Order]:
        orders = []
        can_buy = LIMIT - position   # how much more we may buy
        can_sell = LIMIT + position  # how much more we may sell

        # 1. Take mispriced orders. Sell volumes are negative in OrderDepth.
        for price, volume in sorted(depth.sell_orders.items()):
            if price < FAIR and can_buy > 0:
                qty = min(-volume, can_buy)
                orders.append(Order(PRODUCT, price, qty))
                can_buy -= qty
        for price, volume in sorted(depth.buy_orders.items(), reverse=True):
            if price > FAIR and can_sell > 0:
                qty = min(volume, can_sell)
                orders.append(Order(PRODUCT, price, -qty))
                can_sell -= qty

        # 2. Quote one tick inside the book, but never past fair value.
        if depth.buy_orders and depth.sell_orders:
            bid = min(max(depth.buy_orders) + 1, FAIR - 1)
            ask = max(min(depth.sell_orders) - 1, FAIR + 1)
            if can_buy > 0:
                orders.append(Order(PRODUCT, bid, can_buy))
            if can_sell > 0:
                orders.append(Order(PRODUCT, ask, -can_sell))

        return orders
