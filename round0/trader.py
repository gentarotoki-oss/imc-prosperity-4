"""
Best-of-Both v3
===============
EMERALDS: v3 アグレッシブ MM (fair=10000, best+1 make, limit=80 フル)
TOMATOES: v2 wall_mid MM (take+make, limit=80 フル)
"""
import json
import math
from datamodel import OrderDepth, TradingState, Order

POS_LIMITS = {"EMERALDS": 80, "TOMATOES": 80}


class Trader:
    def run(self, state: TradingState):
        result = {}

        for product in state.order_depths:
            od = state.order_depths[product]
            pos = state.position.get(product, 0)
            limit = POS_LIMITS.get(product, 50)

            if product == "EMERALDS":
                result[product] = self._trade_emeralds(od, pos, limit)
            elif product == "TOMATOES":
                result[product] = self._trade_tomatoes(od, pos, limit)
            else:
                result[product] = []

        return result, 0, ""

    # ================================================================
    # EMERALDS: 固定 fair=10000、アグレッシブ MM (v3)
    # ================================================================
    def _trade_emeralds(self, od: OrderDepth, pos: int, limit: int) -> list[Order]:
        fair = 10000
        p = "EMERALDS"
        orders = []
        max_buy = limit - pos
        max_sell = limit + pos

        asks = {price: abs(v) for price, v in sorted(od.sell_orders.items())}
        bids = {price: v for price, v in sorted(od.buy_orders.items(), reverse=True)}

        if not bids or not asks:
            return []

        best_bid = max(bids)
        best_ask = min(asks)

        # ---- Take ----
        for ap, av in asks.items():
            if max_buy <= 0:
                break
            if ap < fair:
                v = min(av, max_buy)
                orders.append(Order(p, ap, v))
                max_buy -= v
            elif ap == fair and pos < 0:
                v = min(av, abs(pos), max_buy)
                orders.append(Order(p, ap, v))
                max_buy -= v

        for bp, bv in bids.items():
            if max_sell <= 0:
                break
            if bp > fair:
                v = min(bv, max_sell)
                orders.append(Order(p, bp, -v))
                max_sell -= v
            elif bp == fair and pos > 0:
                v = min(bv, pos, max_sell)
                orders.append(Order(p, bp, -v))
                max_sell -= v

        # ---- Make: best+1 / best-1 で板先頭、fair を跨がない ----
        my_bid = best_bid + 1
        if my_bid >= fair:
            my_bid = fair - 1

        my_ask = best_ask - 1
        if my_ask <= fair:
            my_ask = fair + 1

        if max_buy > 0:
            orders.append(Order(p, my_bid, max_buy))
        if max_sell > 0:
            orders.append(Order(p, my_ask, -max_sell))

        return orders

    # ================================================================
    # TOMATOES: wall_mid MM (v2 そのまま、limit=80 フル)
    # ================================================================
    def _trade_tomatoes(self, od: OrderDepth, pos: int, limit: int) -> list[Order]:
        p = "TOMATOES"
        orders = []
        max_buy = limit - pos
        max_sell = limit + pos

        buy_orders = {price: v for price, v in sorted(
            od.buy_orders.items(), reverse=True)}
        sell_orders = {price: abs(v) for price, v in sorted(
            od.sell_orders.items())}

        if not buy_orders or not sell_orders:
            return []

        bid_wall = min(buy_orders)
        ask_wall = max(sell_orders)
        wall_mid = (bid_wall + ask_wall) / 2

        # ---- Take ----
        for sp, sv in sell_orders.items():
            if max_buy <= 0:
                break
            if sp <= wall_mid - 1:
                v = min(sv, max_buy)
                orders.append(Order(p, sp, v))
                max_buy -= v
            elif sp <= wall_mid and pos < 0:
                v = min(sv, abs(pos), max_buy)
                orders.append(Order(p, sp, v))
                max_buy -= v

        for bp, bv in buy_orders.items():
            if max_sell <= 0:
                break
            if bp >= wall_mid + 1:
                v = min(bv, max_sell)
                orders.append(Order(p, bp, -v))
                max_sell -= v
            elif bp >= wall_mid and pos > 0:
                v = min(bv, pos, max_sell)
                orders.append(Order(p, bp, -v))
                max_sell -= v

        # ---- Make: overbid / underbid ----
        if max_buy > 0 or max_sell > 0:
            bid_price = bid_wall + 1
            ask_price = ask_wall - 1

            for bp, bv in buy_orders.items():
                overbid = bp + 1
                if bv > 1 and overbid < wall_mid:
                    bid_price = max(bid_price, overbid)
                    break
                elif bp < wall_mid:
                    bid_price = max(bid_price, bp)
                    break

            for sp, sv in sell_orders.items():
                underbid = sp - 1
                if sv > 1 and underbid > wall_mid:
                    ask_price = min(ask_price, underbid)
                    break
                elif sp > wall_mid:
                    ask_price = min(ask_price, sp)
                    break

            if max_buy > 0:
                orders.append(Order(p, int(bid_price), max_buy))
            if max_sell > 0:
                orders.append(Order(p, int(ask_price), -max_sell))

        return orders