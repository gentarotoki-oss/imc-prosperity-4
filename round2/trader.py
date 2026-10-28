# trader_round2_v9.py — v8 系 ACO + best 基準メイク + 3 段スプレッド + Pepper 条件テイク
"""
v8 からの主な変更:

* **ACO メイク**: ``best_bid`` / ``best_ask`` 基準で在庫連動（壁+1 方式を廃止）。
* **テイク**: スプレッド **3 段階**（狭い / 中 / 広）でフェアからのマージン ``d`` を 1 / 2 / 3 に切替。
* **Pepper**: ask は ``best_bid + PEPPER_MAX_ABOVE_BID`` 以下の段だけテイク（高値掴み抑制）。
* **VWAP ブレンド・スキュー・MAF** は定数で調整（``_opt_v9_params.py`` でグリッド済みの値を書く）。

検証::

    python -m prosperity4bt trader_round2_v9.py 1 --no-out
    python -m prosperity4bt trader_round2_v9.py 2 --data wiki_round2_data --no-out
"""
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
        if not value:
            return ""
        lo, hi = 0, min(len(value), max_length)
        out = ""
        while lo <= hi:
            mid = (lo + hi) // 2
            candidate = value[:mid]
            if len(candidate) < len(value):
                candidate += "..."
            if len(json.dumps(candidate)) <= max_length:
                out = candidate
                lo = mid + 1
            else:
                hi = mid - 1
        return out


logger = Logger()

POS_LIMITS = {
    "ASH_COATED_OSMIUM": 80,
    "INTARIAN_PEPPER_ROOT": 80,
}

MARKET_ACCESS_FEE_BID = 2000

ACO_BLEND_RAW = 0.55
ACO_ANCHOR_PRICE = 10000.0
SKEW_FACTOR = 1.5
ACO_VWAP_BLEND = 0.12

# スプレッド best_ask - best_bid: ( <=MID → d=1 ], (MID, VW] → d=2 ], ( VW+ → d=3 ]
ACO_SPREAD_MID = 13
ACO_SPREAD_VERY_WIDE = 23

# Pepper: ask を叩くのは sp <= best_bid + この値 まで
PEPPER_MAX_ABOVE_BID = 0


class Trader:
    def bid(self) -> int:
        return MARKET_ACCESS_FEE_BID

    def run(self, state: TradingState):
        result: dict[str, list[Order]] = {}
        trader_data = ""

        for product in state.order_depths:
            od = state.order_depths[product]
            pos = state.position.get(product, 0)
            pos_limit = POS_LIMITS.get(product, 50)

            if product == "INTARIAN_PEPPER_ROOT":
                result[product] = self._trade_pepper(od, pos, pos_limit)
            elif product == "ASH_COATED_OSMIUM":
                result[product] = self._trade_aco(od, pos, pos_limit)
            else:
                result[product] = []

        logger.flush(state, result, 0, trader_data)
        return result, 0, trader_data

    @staticmethod
    def _vwap_mid(buy_orders: dict[int, int], sell_orders: dict[int, int]) -> float | None:
        bv = sum(buy_orders.values())
        sv = sum(sell_orders.values())
        if bv <= 0 or sv <= 0:
            return None
        vw_bid = sum(p * v for p, v in buy_orders.items()) / bv
        vw_ask = sum(p * v for p, v in sell_orders.items()) / sv
        return (vw_bid + vw_ask) / 2.0

    @staticmethod
    def _take_margins_from_spread(spread: int) -> tuple[int, int]:
        if spread > ACO_SPREAD_VERY_WIDE:
            return 3, 3
        if spread > ACO_SPREAD_MID:
            return 2, 2
        return 1, 1

    def _trade_aco(self, od: OrderDepth, pos: int, limit: int) -> list[Order]:
        product = "ASH_COATED_OSMIUM"
        orders: list[Order] = []
        max_buy = limit - pos
        max_sell = limit + pos

        buy_orders = {p: v for p, v in sorted(od.buy_orders.items(), reverse=True)}
        sell_orders = {p: abs(v) for p, v in sorted(od.sell_orders.items())}

        if not buy_orders or not sell_orders:
            return []

        bid_wall = max(buy_orders, key=buy_orders.get)
        ask_wall = max(sell_orders, key=sell_orders.get)
        best_bid = max(buy_orders)
        best_ask = min(sell_orders)
        spread = best_ask - best_bid
        d_buy, d_sell = self._take_margins_from_spread(spread)

        wall_mid_simple = (bid_wall + ask_wall) / 2.0
        vwap_m = self._vwap_mid(buy_orders, sell_orders)
        if vwap_m is None:
            raw_mid = wall_mid_simple
        else:
            vb = ACO_VWAP_BLEND
            raw_mid = vb * vwap_m + (1.0 - vb) * wall_mid_simple

        w = ACO_BLEND_RAW
        base_mid = (raw_mid * w) + (ACO_ANCHOR_PRICE * (1.0 - w))
        skew = (pos / limit) * SKEW_FACTOR
        wall_mid = base_mid - skew

        for sp, sv in sell_orders.items():
            if max_buy <= 0:
                break
            if sp <= wall_mid - d_buy:
                v = min(sv, max_buy)
                orders.append(Order(product, sp, v))
                max_buy -= v
            elif d_buy > 0 and sp <= wall_mid and pos < 0:
                v = min(sv, abs(pos), max_buy)
                orders.append(Order(product, sp, v))
                max_buy -= v

        for bp, bv in buy_orders.items():
            if max_sell <= 0:
                break
            if bp >= wall_mid + d_sell:
                v = min(bv, max_sell)
                orders.append(Order(product, bp, -v))
                max_sell -= v
            elif d_sell > 0 and bp >= wall_mid and pos > 0:
                v = min(bv, pos, max_sell)
                orders.append(Order(product, bp, -v))
                max_sell -= v

        if max_buy > 0 or max_sell > 0:
            buy_off = 1 if pos <= 0 else 0
            sell_off = 1 if pos >= 0 else 0
            bid_price = min(best_bid + buy_off, best_ask - 1)
            ask_price = max(best_ask - sell_off, best_bid + 1)
            if bid_price >= ask_price:
                bid_price = best_bid
                ask_price = best_ask
            if bid_price >= ask_price:
                bid_price = best_bid
                ask_price = min(best_ask, best_bid + 2)

            if max_buy > 0:
                orders.append(Order(product, int(bid_price), max_buy))
            if max_sell > 0:
                orders.append(Order(product, int(ask_price), -max_sell))

        return orders

    def _trade_pepper(self, od: OrderDepth, pos: int, limit: int) -> list[Order]:
        p = "INTARIAN_PEPPER_ROOT"
        orders: list[Order] = []

        buy_orders = {price: v for price, v in sorted(od.buy_orders.items(), reverse=True)}
        sell_orders = {price: abs(v) for price, v in sorted(od.sell_orders.items())}

        if not buy_orders or not sell_orders:
            return []

        best_bid = max(buy_orders)
        max_buy = limit - pos
        cap = best_bid + PEPPER_MAX_ABOVE_BID

        if pos >= limit:
            return []

        for sp, sv in sorted(sell_orders.items()):
            if max_buy <= 0:
                break
            if sp > cap:
                continue
            v = min(sv, max_buy)
            orders.append(Order(p, sp, v))
            max_buy -= v

        if max_buy > 0:
            orders.append(Order(p, best_bid + 1, max_buy))

        return orders
