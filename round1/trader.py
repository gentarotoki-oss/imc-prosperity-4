import json
from typing import Any
from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState

class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(self.to_json([self.compress_state(state, ""), self.compress_orders(orders), conversions, "", ""]))
        max_item_length = (self.max_log_length - base_length) // 3
        print(self.to_json([
            self.compress_state(state, self.truncate(state.traderData, max_item_length)),
            self.compress_orders(orders), conversions,
            self.truncate(trader_data, max_item_length),
            self.truncate(self.logs, max_item_length),
        ]))
        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [state.timestamp, trader_data, self.compress_listings(state.listings),
                self.compress_order_depths(state.order_depths), self.compress_trades(state.own_trades),
                self.compress_trades(state.market_trades), state.position, self.compress_observations(state.observations)]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        return [[l.symbol, l.product, l.denomination] for l in listings.values()]

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        return {s: [od.buy_orders, od.sell_orders] for s, od in order_depths.items()}

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        return [[t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp] for arr in trades.values() for t in arr]

    def compress_observations(self, observations: Observation) -> list[Any]:
        co = {}
        for p, o in observations.conversionObservations.items():
            co[p] = [o.bidPrice, o.askPrice, o.transportFees, o.exportTariff, o.importTariff, o.sugarPrice, o.sunlightIndex]
        return [observations.plainValueObservations, co]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        return [[o.symbol, o.price, o.quantity] for arr in orders.values() for o in arr]

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        if not value: return ""
        lo, hi = 0, min(len(value), max_length)
        out = ""
        while lo <= hi:
            mid = (lo + hi) // 2
            candidate = value[:mid]
            if len(candidate) < len(value): candidate += "..."
            if len(json.dumps(candidate)) <= max_length: out = candidate; lo = mid + 1
            else: hi = mid - 1
        return out


logger = Logger()

POS_LIMITS = {
    "ASH_COATED_OSMIUM": 80,
    "INTARIAN_PEPPER_ROOT": 80,
}

SELL_PHASE_START = 990000


class Trader:
    def run(self, state: TradingState):
        result = {}
        trader_data = ""

        for product in state.order_depths:
            od = state.order_depths[product]
            pos = state.position.get(product, 0)
            pos_limit = POS_LIMITS.get(product, 50)

            if product == "ASH_COATED_OSMIUM":
                result[product] = self._trade_aco(product, od, pos, pos_limit)
            elif product == "INTARIAN_PEPPER_ROOT":
                result[product] = self._trade_pepper_buy_hold(od, pos, pos_limit, state.timestamp)
            else:
                result[product] = []

        logger.flush(state, result, 0, trader_data)
        return result, 0, trader_data

    # ================================================================
    # ACO: v7 wall_mid MM (proven best in prosperity4bt)
    # ================================================================
    def _trade_aco(self, product, od, pos, limit):
        orders = []
        max_buy = limit - pos
        max_sell = limit + pos

        buy_orders = {p: v for p, v in sorted(od.buy_orders.items(), reverse=True)}
        sell_orders = {p: abs(v) for p, v in sorted(od.sell_orders.items())}

        if not buy_orders or not sell_orders:
            return []

        bid_wall = min(buy_orders)
        ask_wall = max(sell_orders)
        wall_mid = (bid_wall + ask_wall) / 2

        for sp, sv in sell_orders.items():
            if max_buy <= 0: break
            if sp <= wall_mid - 1:
                v = min(sv, max_buy); orders.append(Order(product, sp, v)); max_buy -= v
            elif sp <= wall_mid and pos < 0:
                v = min(sv, abs(pos), max_buy); orders.append(Order(product, sp, v)); max_buy -= v

        for bp, bv in buy_orders.items():
            if max_sell <= 0: break
            if bp >= wall_mid + 1:
                v = min(bv, max_sell); orders.append(Order(product, bp, -v)); max_sell -= v
            elif bp >= wall_mid and pos > 0:
                v = min(bv, pos, max_sell); orders.append(Order(product, bp, -v)); max_sell -= v

        if max_buy > 0 or max_sell > 0:
            bid_price = bid_wall + 1
            ask_price = ask_wall - 1
            for bp, bv in buy_orders.items():
                ob = bp + 1
                if bv > 1 and ob < wall_mid: bid_price = max(bid_price, ob); break
                elif bp < wall_mid: bid_price = max(bid_price, bp); break
            for sp, sv in sell_orders.items():
                ub = sp - 1
                if sv > 1 and ub > wall_mid: ask_price = min(ask_price, ub); break
                elif sp > wall_mid: ask_price = min(ask_price, sp); break
            if max_buy > 0: orders.append(Order(product, int(bid_price), max_buy))
            if max_sell > 0: orders.append(Order(product, int(ask_price), -max_sell))

        return orders

    # ================================================================
    # INTARIAN_PEPPER_ROOT: 買い持ち戦略
    # ================================================================
    def _trade_pepper_buy_hold(self, od, pos, limit, timestamp):
        p = "INTARIAN_PEPPER_ROOT"
        orders = []

        buy_orders = {price: v for price, v in sorted(od.buy_orders.items(), reverse=True)}
        sell_orders = {price: abs(v) for price, v in sorted(od.sell_orders.items())}

        if not buy_orders or not sell_orders:
            return []

        best_bid = max(buy_orders)
        best_ask = min(sell_orders)

        max_buy = limit - pos
        max_sell = limit + pos

        if timestamp >= SELL_PHASE_START:
            return []

        else:
            if pos >= limit:
                return []

            for sp, sv in sell_orders.items():
                if max_buy <= 0: break
                v = min(sv, max_buy)
                orders.append(Order(p, sp, v))
                max_buy -= v

            if max_buy > 0:
                orders.append(Order(p, best_bid + 1, max_buy))

        return orders
