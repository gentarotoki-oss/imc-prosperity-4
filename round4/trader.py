"""
trader_round4_v6 — v3 のフレームを流用しつつ「sucker hunt」へ方針転換。

再解釈:
  Mark 49 seller_edge = -1.82  → 彼が売った直後 mid は +1.82 上がる
  Mark 22 seller_edge = -0.09  → 彼が売った直後 mid は +0.09 上がる
  Mark 49 buyer_edge  = -1.82  → 彼が買った直後 mid は -1.82 下がる
  → 「彼らの quote を **我々が take すれば** edge を取れる」と解釈する。

v3 / v4 / v5 の問題:
  v3 は Mark 22 price を fair から「除外」していた → 結果として彼の ask を
  take しなくなり edge を捨てていた (符号が逆)。

v6 の戦略 (候補G = sucker hunt MM):
  1) market_trades から Mark 49 / Mark 22 が直近 N tick 内に取引した
     price を product 別に蓄積 (sell 価格 / bid 価格それぞれ)。
  2) AnchorWallMMTrader._take_bad_prices で:
       - sell_orders[price] が sucker の sell 価格と一致する場合、
         take 閾値を fair-1 → fair + EXTRA まで緩める (積極 lift)。
       - buy_orders[price] が sucker の bid 価格と一致する場合、
         hit 閾値を fair+1 → fair - EXTRA まで緩める (積極 hit)。
  3) Mark 49: edge=1.82 → EXTRA=2 (fair+2 までの ask は買う)
     Mark 22: edge=0.09 → EXTRA=0 (fair でも買う、つまり flat take)
  4) v3 の EXCLUDE_ASK 機能は撤廃 (引数は残すが空セット)。
  5) MM 自体 (quote / spread) は v16 ベースで一切いじらない。
"""

from __future__ import annotations

import json
import math
from typing import Any

from datamodel import (
    Listing,
    Observation,
    Order,
    OrderDepth,
    ProsperityEncoder,
    Symbol,
    Trade,
    TradingState,
)


HYDROGEL_PACK = "HYDROGEL_PACK"
VELVETFRUIT_EXTRACT = "VELVETFRUIT_EXTRACT"
VEV_4000 = "VEV_4000"
VEV_4500 = "VEV_4500"
VEV_5000 = "VEV_5000"
VEV_5100 = "VEV_5100"
VEV_5200 = "VEV_5200"
VEV_5300 = "VEV_5300"
VEV_5400 = "VEV_5400"
VEV_5500 = "VEV_5500"
VEV_6000 = "VEV_6000"
VEV_6500 = "VEV_6500"

VELVETFRUIT_EXTRACT_VOUCHERS = [
    VEV_4000,
    VEV_4500,
    VEV_5000,
    VEV_5100,
    VEV_5200,
    VEV_5300,
    VEV_5400,
    VEV_5500,
    VEV_6000,
    VEV_6500,
]

VELVETFRUIT_EXTRACT_VOUCHER_STRIKES = {
    VEV_4000: 4000,
    VEV_4500: 4500,
    VEV_5000: 5000,
    VEV_5100: 5100,
    VEV_5200: 5200,
    VEV_5300: 5300,
    VEV_5400: 5400,
    VEV_5500: 5500,
    VEV_6000: 6000,
    VEV_6500: 6500,
}

POSITION_LIMITS = {
    HYDROGEL_PACK: 200,
    VELVETFRUIT_EXTRACT: 200,
    VEV_4000: 300,
    VEV_4500: 300,
    VEV_5000: 300,
    VEV_5100: 300,
    VEV_5200: 300,
    VEV_5300: 300,
    VEV_5400: 300,
    VEV_5500: 300,
    VEV_6000: 300,
    VEV_6500: 300,
}

FOLLOW_UNDERLYING_PRODUCTS = (
    VEV_5200,
    VEV_5300,
)
NEAR_ATM_PRODUCTS = ()
OVERVALUED_SHORT_PRODUCTS = ()


class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(
            self.to_json(
                [
                    self.compress_state(state, ""),
                    self.compress_orders(orders),
                    conversions,
                    "",
                    "",
                ]
            )
        )

        # We truncate state.traderData, trader_data, and self.logs to the same max. length to fit the log limit
        max_item_length = (self.max_log_length - base_length) // 3

        print(
            self.to_json(
                [
                    self.compress_state(state, self.truncate(state.traderData, max_item_length)),
                    self.compress_orders(orders),
                    conversions,
                    self.truncate(trader_data, max_item_length),
                    self.truncate(self.logs, max_item_length),
                ]
            )
        )

        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp,
            trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        compressed = []
        for listing in listings.values():
            compressed.append([listing.symbol, listing.product, listing.denomination])

        return compressed

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        compressed = {}
        for symbol, order_depth in order_depths.items():
            compressed[symbol] = [order_depth.buy_orders, order_depth.sell_orders]

        return compressed

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        compressed = []
        for arr in trades.values():
            for trade in arr:
                compressed.append(
                    [
                        trade.symbol,
                        trade.price,
                        trade.quantity,
                        trade.buyer,
                        trade.seller,
                        trade.timestamp,
                    ]
                )

        return compressed

    def compress_observations(self, observations: Observation) -> list[Any]:
        conversion_observations = {}
        for product, observation in observations.conversionObservations.items():
            conversion_observations[product] = [
                observation.bidPrice,
                observation.askPrice,
                observation.transportFees,
                observation.exportTariff,
                observation.importTariff,
                observation.sugarPrice,
                observation.sunlightIndex,
            ]

        return [observations.plainValueObservations, conversion_observations]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        compressed = []
        for arr in orders.values():
            for order in arr:
                compressed.append([order.symbol, order.price, order.quantity])

        return compressed

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        lo, hi = 0, min(len(value), max_length)
        out = ""

        while lo <= hi:
            mid = (lo + hi) // 2

            candidate = value[:mid]
            if len(candidate) < len(value):
                candidate += "..."

            encoded_candidate = json.dumps(candidate)

            if len(encoded_candidate) <= max_length:
                out = candidate
                lo = mid + 1
            else:
                hi = mid - 1

        return out


logger = Logger()


def append_rolling(history: list[float], value: float, window: int) -> None:
    history.append(value)
    if len(history) > window:
        del history[:-window]


def rolling_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def rolling_std(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = rolling_mean(values)
    variance = sum((value - mean) ** 2 for value in values) / (n - 1)
    return math.sqrt(variance)


def rolling_slope(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean_x = (n - 1) / 2
    mean_y = rolling_mean(values)
    numerator = sum((i - mean_x) * (value - mean_y) for i, value in enumerate(values))
    denominator = sum((i - mean_x) ** 2 for i in range(n))
    if denominator == 0:
        return 0.0
    return numerator / denominator


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class ProductState:
    def __init__(self, product: str, state: TradingState, trader_data: dict):
        self.product = product
        self.state = state
        self.trader_data = trader_data
        self.orders: list[Order] = []

        self.position_limit = POSITION_LIMITS[product]
        self.position = state.position.get(product, 0)

        self.order_depth: OrderDepth | None = state.order_depths.get(product)
        self.buy_orders = self._sorted_bids()
        self.sell_orders = self._sorted_asks()

        self.best_bid = max(self.buy_orders.keys()) if self.buy_orders else None
        self.best_ask = min(self.sell_orders.keys()) if self.sell_orders else None
        self.bid_wall = min(self.buy_orders.keys()) if self.buy_orders else None
        self.ask_wall = max(self.sell_orders.keys()) if self.sell_orders else None

        self.max_buy = self.position_limit - self.position
        self.max_sell = self.position_limit + self.position

    def _sorted_bids(self) -> dict[int, int]:
        if self.order_depth is None:
            return {}
        return dict(sorted(self.order_depth.buy_orders.items(), key=lambda x: x[0], reverse=True))

    def _sorted_asks(self) -> dict[int, int]:
        if self.order_depth is None:
            return {}
        return dict(sorted(self.order_depth.sell_orders.items(), key=lambda x: x[0]))

    def best_mid(self) -> float | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return (self.best_bid + self.best_ask) / 2

    def wall_mid(self) -> float | None:
        if self.bid_wall is None or self.ask_wall is None:
            return None
        return (self.bid_wall + self.ask_wall) / 2

    def buy(self, price: int, quantity: int) -> None:
        qty = max(0, min(int(quantity), self.max_buy))
        if qty <= 0:
            return
        self.orders.append(Order(self.product, int(price), qty))
        self.max_buy -= qty

    def sell(self, price: int, quantity: int) -> None:
        qty = max(0, min(int(quantity), self.max_sell))
        if qty <= 0:
            return
        self.orders.append(Order(self.product, int(price), -qty))
        self.max_sell -= qty


class BaseProductTrader(ProductState):
    pass


class AnchorWallMMTrader(BaseProductTrader):
    def __init__(
        self,
        product: str,
        state: TradingState,
        trader_data: dict,
        anchor: float,
        anchor_weight: float = 0.30,
        skew_factor: float = 2.0,
        excluded_ask_prices: set[int] | None = None,
        excluded_bid_prices: set[int] | None = None,
        sucker_ask_prices: dict[int, int] | None = None,
        sucker_bid_prices: dict[int, int] | None = None,
        target_position: int = 0,
    ):
        product_data = trader_data.setdefault(product, {})
        super().__init__(product, state, product_data)
        self.anchor = anchor
        self.anchor_weight = anchor_weight
        self.skew_factor = skew_factor
        # v6+: 目標 position。surface mean-revert 等から bias を受け取って、
        # skew を (position - target) ベースで計算 → 自然に target に寄る。
        self.target_position = int(target_position)
        # v3 互換: 除外引数は残すが v6 では使わない (空集合)。
        self.excluded_ask_prices: set[int] = excluded_ask_prices or set()
        self.excluded_bid_prices: set[int] = excluded_bid_prices or set()
        # v6 (候補G): sucker (Mark 49 / 22 等) の price → 追加 take 余裕。
        # ask 側の price がこの dict に入っていれば、take 閾値 fair-1 を
        # fair + extra まで緩める (= sucker の ask を貪欲に lift する)。
        # bid 側も同様 (vsell)。
        self.sucker_ask_prices: dict[int, int] = sucker_ask_prices or {}
        self.sucker_bid_prices: dict[int, int] = sucker_bid_prices or {}

    def run(self) -> list[Order]:
        if not self.buy_orders or not self.sell_orders:
            return self.orders
        fair = self._fair()
        self._take_bad_prices(fair)
        self._make_market(fair)
        return self.orders

    def _filtered_ask_wall(self) -> int:
        """除外価格を抜いた sell_orders から ask_wall を選ぶ。
        全部除外されてしまう場合は元の集合にフォールバック。"""
        candidates = {p: abs(q) for p, q in self.sell_orders.items() if p not in self.excluded_ask_prices}
        if not candidates:
            candidates = {p: abs(q) for p, q in self.sell_orders.items()}
        return max(candidates, key=candidates.get)

    def _filtered_bid_wall(self) -> int:
        candidates = {p: abs(q) for p, q in self.buy_orders.items() if p not in self.excluded_bid_prices}
        if not candidates:
            candidates = {p: abs(q) for p, q in self.buy_orders.items()}
        return max(candidates, key=candidates.get)

    def _fair(self) -> float:
        bid_wall = self._filtered_bid_wall()
        ask_wall = self._filtered_ask_wall()
        raw_mid = (bid_wall + ask_wall) / 2
        base_mid = raw_mid * (1.0 - self.anchor_weight) + self.anchor * self.anchor_weight
        # v6+: skew を (position - target_position) ベースに。target=0 なら従来挙動。
        skew = ((self.position - self.target_position) / self.position_limit) * self.skew_factor
        fair = base_mid - skew
        self.trader_data["raw_mid"] = raw_mid
        self.trader_data["fair"] = fair
        return fair

    def _take_bad_prices(self, fair: float) -> None:
        for price, qty in self.sell_orders.items():
            ask_qty = abs(qty)
            sucker_extra = self.sucker_ask_prices.get(int(price))
            if sucker_extra is not None and price <= fair + sucker_extra:
                # v6: sucker の ask は fair + extra まで貪欲 lift
                self.buy(price, ask_qty)
                self.trader_data.setdefault("sucker_lifts", 0)
                self.trader_data["sucker_lifts"] += ask_qty
            elif price <= fair - 1:
                self.buy(price, ask_qty)
            elif price <= fair and self.position < 0:
                self.buy(price, min(ask_qty, abs(self.position)))

        for price, qty in self.buy_orders.items():
            bid_qty = abs(qty)
            sucker_extra = self.sucker_bid_prices.get(int(price))
            if sucker_extra is not None and price >= fair - sucker_extra:
                # v6: sucker の bid は fair - extra まで貪欲 hit
                self.sell(price, bid_qty)
                self.trader_data.setdefault("sucker_hits", 0)
                self.trader_data["sucker_hits"] += bid_qty
            elif price >= fair + 1:
                self.sell(price, bid_qty)
            elif price >= fair and self.position > 0:
                self.sell(price, min(bid_qty, self.position))

    def _make_market(self, fair: float) -> None:
        if self.max_buy <= 0 and self.max_sell <= 0:
            return
        bid_wall = self._filtered_bid_wall()
        ask_wall = self._filtered_ask_wall()
        bid_price = bid_wall + 1
        ask_price = ask_wall - 1

        for price, qty in self.buy_orders.items():
            improved = price + 1
            if abs(qty) > 1 and improved < fair:
                bid_price = max(bid_price, improved)
                break
            if price < fair:
                bid_price = max(bid_price, price)
                break

        for price, qty in self.sell_orders.items():
            improved = price - 1
            if abs(qty) > 1 and improved > fair:
                ask_price = min(ask_price, improved)
                break
            if price > fair:
                ask_price = min(ask_price, price)
                break

        if bid_price >= ask_price:
            bid_price = int(fair) - 1
            ask_price = int(fair) + 1

        self.buy(int(bid_price), self.max_buy)
        self.sell(int(ask_price), self.max_sell)


def _sucker_prices_for(product: str, track: dict, edge_map: dict[str, int]) -> dict[int, int]:
    """汎用ヘルパ: cp track + trader→extra マップから price→extra を組む。"""
    out: dict[int, int] = {}
    product_track = track.get(product, {})
    for trader_name, extra in edge_map.items():
        for price in product_track.get(trader_name, ()):
            p = int(price)
            if p not in out or extra > out[p]:
                out[p] = int(extra)
    return out


HYDROGEL_SUCKER_SELL = {"Mark 49": 0, "Mark 22": 0}
HYDROGEL_SUCKER_BUY = {"Mark 49": 3}


class HydrogelPackTrader(AnchorWallMMTrader):
    def __init__(self, state: TradingState, trader_data: dict):
        cp_track = trader_data.get("__cp_track__", {})
        cp_bid_track = trader_data.get("__cp_bid_track__", {})
        sucker_asks = _sucker_prices_for(HYDROGEL_PACK, cp_track, HYDROGEL_SUCKER_SELL)
        sucker_bids = _sucker_prices_for(HYDROGEL_PACK, cp_bid_track, HYDROGEL_SUCKER_BUY)
        super().__init__(
            HYDROGEL_PACK,
            state,
            trader_data,
            anchor=10000.0,
            anchor_weight=0.40,
            skew_factor=2.0,
            sucker_ask_prices=sucker_asks,
            sucker_bid_prices=sucker_bids,
        )


class DirectionalTrader(BaseProductTrader):
    def __init__(self, product: str, state: TradingState, trader_data: dict):
        product_data = trader_data.setdefault(product, {})
        super().__init__(product, state, product_data)

    def small_market_make(
        self,
        max_spread: int,
        order_size: int,
        allow_buy: bool = True,
        allow_sell: bool = True,
    ) -> None:
        if self.best_bid is None or self.best_ask is None:
            return
        spread = self.best_ask - self.best_bid
        if spread <= 0 or spread > max_spread:
            return

        bid_price = self.best_bid + 1
        ask_price = self.best_ask - 1
        if bid_price >= ask_price:
            bid_price = self.best_bid
            ask_price = self.best_ask

        if allow_buy:
            self.buy(bid_price, order_size)
        if allow_sell:
            self.sell(ask_price, order_size)

    def trade_to_target(
        self,
        target_position: int,
        max_buy_price: int | None = None,
        min_sell_price: int | None = None,
    ) -> list[Order]:
        delta = target_position - self.position

        if delta > 0:
            remaining = delta
            for price, qty in self.sell_orders.items():
                if max_buy_price is not None and price > max_buy_price:
                    break
                buy_qty = min(remaining, abs(qty))
                self.buy(price, buy_qty)
                remaining -= buy_qty
                if remaining <= 0:
                    break
            if remaining > 0:
                bid_price = self._passive_bid(max_buy_price)
                if bid_price is not None:
                    self.buy(bid_price, remaining)

        elif delta < 0:
            remaining = abs(delta)
            for price, qty in self.buy_orders.items():
                if min_sell_price is not None and price < min_sell_price:
                    break
                sell_qty = min(remaining, abs(qty))
                self.sell(price, sell_qty)
                remaining -= sell_qty
                if remaining <= 0:
                    break
            if remaining > 0:
                ask_price = self._passive_ask(min_sell_price)
                if ask_price is not None:
                    self.sell(ask_price, remaining)

        return self.orders

    def _passive_bid(self, max_buy_price: int | None) -> int | None:
        if max_buy_price is None:
            if self.best_bid is not None:
                return self.best_bid + 1
            if self.best_ask is not None:
                return self.best_ask - 1
            return None
        if self.best_bid is None:
            return max_buy_price
        return min(self.best_bid + 1, max_buy_price)

    def _passive_ask(self, min_sell_price: int | None) -> int | None:
        if min_sell_price is None:
            if self.best_ask is not None:
                return self.best_ask - 1
            if self.best_bid is not None:
                return self.best_bid + 1
            return None
        if self.best_ask is None:
            return min_sell_price
        return max(self.best_ask - 1, min_sell_price)


class VelvetfruitOptionsTrader:
    UNDERLYING_FAIR = 5250
    ANCHOR_MM_CONFIG = {
        VELVETFRUIT_EXTRACT: {"anchor": 5250.0, "anchor_weight": 0.40, "skew_factor": 2.0},
        VEV_4000: {"anchor": 1250.0, "anchor_weight": 0.40, "skew_factor": 2.0},
        VEV_4500: {"anchor": 750.0, "anchor_weight": 0.30, "skew_factor": 2.0},
        VEV_5000: {"anchor": 252.0, "anchor_weight": 0.20, "skew_factor": 2.0},
        VEV_5100: {"anchor": 158.0, "anchor_weight": 0.15, "skew_factor": 2.0},
        # v6+: 深 OTM voucher。経験的 mid 平均を anchor、weight は低めで噪声に強く。
        VEV_5400: {"anchor": 13.0, "anchor_weight": 0.20, "skew_factor": 1.0},
        VEV_5500: {"anchor": 5.0, "anchor_weight": 0.50, "skew_factor": 1.0},
    }
    ENABLE_5200_PLUS_TRADING = True
    VOL_WINDOW = 200
    ENTRY_EDGE = 10
    AGGRESSIVE_EDGE = 15
    FULL_EDGE = 20
    MIN_ENTRY_EDGE = 8
    MAX_ENTRY_EDGE = 16
    ENTRY_SIGMA_MULT = 1.5
    FULL_EXTRA_MIN = 8
    FULL_EXTRA_SIGMA_MULT = 1.3
    MEAN_DRIFT_WEIGHT = 0.3
    MAX_ANCHOR_DRIFT = 8
    SLOPE_SIGMA_MULT = 3.2
    CRASH_SHORT_TARGET_FRACTION = 0.55
    VOUCHER_MM_MAX_SPREAD = 5
    VOUCHER_MM_ORDER_SIZE = 8
    NEAR_ATM_MM_MAX_SPREAD = 6
    NEAR_ATM_MM_ORDER_SIZE = 12
    NEAR_ATM_TARGET_MULTIPLIER = 1.25
    ENABLE_VOUCHER_MM = True
    ENABLE_VOUCHER_DIRECTIONAL = True
    ENABLE_OVERVALUED_SHORT = True

    # v16 residual-surface extension
    SURF_WINDOW = 220
    SURF_ENTRY_Z = 1.8
    SURF_MAX_Z = 3.8
    SURF_TARGET_FRACTION = 0.35       # FOLLOW (VEV_5200/5300) directional 用
    SURF_TARGET_FRACTION_MM = 0.10    # v6+: AnchorMM voucher 用 (控えめ)
    SURF_MM_PRODUCTS = ()             # surface bias を MM に適用する商品 (空 = 無効)
    QUOTE_BOOST_TRIGGER = 0.22
    BASE_TARGET_SCALE = 7.0

    def __init__(self, state: TradingState, trader_data: dict):
        self.state = state
        self.trader_data = trader_data
        self.orders: dict[str, list[Order]] = {}
        self.underlying_mid: float | None = None
        self.underlying_anchor = float(self.UNDERLYING_FAIR)
        self.underlying_diff = 0.0
        self.underlying_sigma = 0.0
        self.underlying_slope = 0.0
        self.underlying_slope_mean = 0.0
        self.underlying_slope_sigma = 0.0
        self.underlying_slope_z = 0.0
        self.entry_edge = float(self.ENTRY_EDGE)
        self.full_edge = float(self.FULL_EDGE)

    def _order_mid(self, product: str) -> float | None:
        od = self.state.order_depths.get(product)
        if od is None or not od.buy_orders or not od.sell_orders:
            return None
        best_bid = max(od.buy_orders.keys())
        best_ask = min(od.sell_orders.keys())
        return 0.5 * (best_bid + best_ask)

    def _pava_non_decreasing(self, values: list[float], weights: list[float]) -> list[float]:
        blocks: list[list[float | int]] = []
        for i, (v, w) in enumerate(zip(values, weights)):
            blocks.append([v, w, i, i])
            while len(blocks) >= 2 and blocks[-2][0] > blocks[-1][0]:
                v2, w2, s2, e2 = blocks.pop()
                v1, w1, s1, e1 = blocks.pop()
                nw = float(w1) + float(w2)
                nv = (float(v1) * float(w1) + float(v2) * float(w2)) / max(1e-12, nw)
                blocks.append([nv, nw, int(s1), int(e2)])

        out = [0.0] * len(values)
        for avg, _, start, end in blocks:
            for j in range(int(start), int(end) + 1):
                out[j] = float(avg)
        return out

    def _project_call_curve(self, strikes: list[float], prices: list[float]) -> list[float]:
        n = len(strikes)
        if n <= 2:
            return prices[:]

        dk = [max(1e-9, strikes[i + 1] - strikes[i]) for i in range(n - 1)]
        slopes = [(prices[i + 1] - prices[i]) / dk[i] for i in range(n - 1)]
        iso = self._pava_non_decreasing(slopes, dk)
        iso = [min(0.0, s) for s in iso]
        iso = self._pava_non_decreasing(iso, dk)
        iso = [min(0.0, s) for s in iso]

        prefix = [0.0]
        for i in range(n - 1):
            prefix.append(prefix[-1] + iso[i] * dk[i])
        a = sum(prices[i] - prefix[i] for i in range(n)) / n
        return [max(0.0, a + prefix[i]) for i in range(n)]

    def _zscore_from_history(self, key: str, value: float, window: int) -> float:
        history = self.trader_data.setdefault(key, [])
        if history:
            mu = rolling_mean(history)
            sigma = rolling_std(history)
            z = (value - mu) / sigma if sigma > 0 else 0.0
        else:
            z = 0.0
        append_rolling(history, value, window)
        return z

    def _surface_residual_z(self) -> dict[str, float]:
        """全 voucher について surface curve からの residual z-score を返す。
        v6+: 元は FOLLOW_UNDERLYING_PRODUCTS のみだったが MM 商品にも拡張。"""
        rows: list[tuple[float, str, float]] = []
        for product, strike in VELVETFRUIT_EXTRACT_VOUCHER_STRIKES.items():
            mid = self._order_mid(product)
            if mid is not None:
                rows.append((float(strike), product, mid))
        rows.sort(key=lambda x: x[0])

        z_by_product: dict[str, float] = {}
        if len(rows) < 5:
            return z_by_product

        strikes = [r[0] for r in rows]
        mids = [r[2] for r in rows]
        fitted = self._project_call_curve(strikes, mids)
        for (_, product, mid), fair in zip(rows, fitted):
            resid = mid - fair
            self.trader_data[f"surf_resid_{product}"] = resid
            key = f"surf_resid_hist_{product}"
            z_by_product[product] = self._zscore_from_history(key, resid, self.SURF_WINDOW)
        return z_by_product

    def _bias_from_z(self, z: float, limit: int) -> int:
        az = abs(z)
        if az <= self.SURF_ENTRY_Z:
            return 0
        strength = (az - self.SURF_ENTRY_Z) / max(1e-9, (self.SURF_MAX_Z - self.SURF_ENTRY_Z))
        strength = clamp(strength, 0.0, 1.0)
        qty = int(round(limit * self.SURF_TARGET_FRACTION * strength))
        if qty <= 0:
            return 0
        return -qty if z > 0 else qty

    def _bias_from_z_mm(self, z: float, limit: int) -> int:
        """v6+: AnchorMM 商品向けの控えめ版 (TARGET_FRACTION_MM 使用)。"""
        az = abs(z)
        if az <= self.SURF_ENTRY_Z:
            return 0
        strength = (az - self.SURF_ENTRY_Z) / max(1e-9, (self.SURF_MAX_Z - self.SURF_ENTRY_Z))
        strength = clamp(strength, 0.0, 1.0)
        qty = int(round(limit * self.SURF_TARGET_FRACTION_MM * strength))
        if qty <= 0:
            return 0
        return -qty if z > 0 else qty

    # v6 (候補G): sucker から取り上げる量。
    #   value = price がこの trader 由来と判明したときに、
    #           take 閾値を fair + extra まで緩める "extra" 値。
    # Mark 49: avg edge 1.82/unit → 安全に EXTRA=2 まで lift しても期待値 +
    # Mark 22: avg edge 0.09/unit → EXTRA=0 (fair 価格までならフラットで take)
    SUCKER_SELL_EDGE: dict[str, int] = {
        "Mark 49": 0,
        "Mark 22": 0,
        "Mark 14": 0,
    }
    SUCKER_BUY_EDGE: dict[str, int] = {
        "Mark 49": 0,
        "Mark 14": 0,
    }
    # 適用商品 (基本は ANCHOR_MM_CONFIG 全 product)
    SUCKER_PRODUCTS: tuple[str, ...] = (
        VELVETFRUIT_EXTRACT, VEV_4000, VEV_4500, VEV_5000, VEV_5100,
        VEV_5200, VEV_5300, VEV_5400, VEV_5500,
    )

    def run(self) -> dict[str, list[Order]]:
        cp_track = self.trader_data.setdefault("__cp_track__", {})
        cp_bid_track = self.trader_data.setdefault("__cp_bid_track__", {})

        # v6+: surface residual z-score を全 voucher について計算し、
        # AnchorMM 商品では target_position バイアスとして使う (mean-revert)。
        surf_z_all = self._surface_residual_z()

        for product, config in self.ANCHOR_MM_CONFIG.items():
            if product not in self.state.order_depths:
                continue
            sucker_asks = self._sucker_ask_prices(product, cp_track)
            sucker_bids = self._sucker_bid_prices(product, cp_bid_track)

            # v6+: SURF_MM_PRODUCTS にだけ surface mean-revert を適用。
            target_pos = 0
            if product in self.SURF_MM_PRODUCTS:
                z = surf_z_all.get(product, 0.0)
                target_pos = self._bias_from_z_mm(z, POSITION_LIMITS[product])
                self.trader_data[f"surf_z_{product}"] = z
                self.trader_data[f"surf_target_{product}"] = target_pos

            mm_trader = AnchorWallMMTrader(
                product, self.state, self.trader_data,
                sucker_ask_prices=sucker_asks,
                sucker_bid_prices=sucker_bids,
                target_position=target_pos,
                **config,
            )
            product_orders = mm_trader.run()
            if product_orders:
                self.orders[product] = product_orders

        if not self.ENABLE_5200_PLUS_TRADING:
            return self.orders

        underlying_target = self._underlying_target()
        if underlying_target is None:
            return self.orders

        # v6+: 既に AnchorMM ループで計算済みなので reuse (history 二重 append 防止)。
        surf_z = surf_z_all

        for product in FOLLOW_UNDERLYING_PRODUCTS:
            if product not in self.state.order_depths:
                continue
            voucher_trader = DirectionalTrader(product, self.state, self.trader_data)
            voucher_fair = voucher_trader.wall_mid()
            if voucher_fair is None:
                voucher_fair = voucher_trader.best_mid()
            if voucher_fair is None:
                continue

            base_target = int(round(self._scaled_target(product, underlying_target) * self.BASE_TARGET_SCALE))
            voucher_target = base_target
            if self.ENABLE_OVERVALUED_SHORT and product in OVERVALUED_SHORT_PRODUCTS:
                voucher_target = -POSITION_LIMITS[product]

            limit = POSITION_LIMITS[product]
            z = surf_z.get(product, 0.0)
            surf_bias = self._bias_from_z(z, limit)
            voucher_target = max(-limit, min(limit, voucher_target + surf_bias))

            self.trader_data[f"surf_z_{product}"] = z
            self.trader_data[f"surf_bias_{product}"] = surf_bias
            self.trader_data[f"base_target_{product}"] = base_target

            if self.ENABLE_VOUCHER_MM:
                allow_buy = voucher_target >= voucher_trader.position
                allow_sell = voucher_target <= voucher_trader.position
                max_spread = self.VOUCHER_MM_MAX_SPREAD
                order_size = self.VOUCHER_MM_ORDER_SIZE
                if product in NEAR_ATM_PRODUCTS:
                    max_spread = self.NEAR_ATM_MM_MAX_SPREAD
                    order_size = self.NEAR_ATM_MM_ORDER_SIZE
                voucher_trader.small_market_make(
                    max_spread=max_spread,
                    order_size=order_size,
                    allow_buy=allow_buy,
                    allow_sell=allow_sell,
                )

            max_buy_price = math.floor(voucher_fair)
            min_sell_price = math.ceil(voucher_fair)
            aggressive_edge = max(self.AGGRESSIVE_EDGE, self.entry_edge)
            if product in NEAR_ATM_PRODUCTS:
                aggressive_edge = self.entry_edge
            if abs(self.underlying_diff) >= aggressive_edge:
                max_buy_price += 1
                min_sell_price -= 1

            strength = abs(surf_bias) / max(1, limit)
            if strength >= self.QUOTE_BOOST_TRIGGER:
                if surf_bias > 0:
                    max_buy_price += 1
                elif surf_bias < 0:
                    min_sell_price -= 1

            # v6 拡張: voucher にも sucker hunt を適用。
            # voucher_target に従う通常 take の前に sucker price を貪欲に潰す。
            cp_track = self.trader_data.get("__cp_track__", {})
            cp_bid_track = self.trader_data.get("__cp_bid_track__", {})
            sucker_asks = self._sucker_ask_prices(product, cp_track)
            sucker_bids = self._sucker_bid_prices(product, cp_bid_track)
            self._voucher_sucker_take(voucher_trader, voucher_fair, sucker_asks, sucker_bids)

            voucher_trader.trade_to_target(
                voucher_target,
                max_buy_price=max_buy_price,
                min_sell_price=min_sell_price,
            )

            if voucher_trader.orders:
                self.orders[product] = voucher_trader.orders

        return self.orders

    def _underlying_target(self) -> int | None:
        trader = DirectionalTrader(VELVETFRUIT_EXTRACT, self.state, self.trader_data)
        mid = trader.best_mid()
        if mid is None:
            return None

        self._update_underlying_signal(mid)
        limit = POSITION_LIMITS[VELVETFRUIT_EXTRACT]
        diff = self.underlying_diff
        abs_diff = abs(diff)
        if abs_diff < self.entry_edge:
            return 0

        if self.underlying_slope_z <= -self.SLOPE_SIGMA_MULT:
            return -int(round(limit * self.CRASH_SHORT_TARGET_FRACTION))
        if self.underlying_slope_z >= self.SLOPE_SIGMA_MULT:
            return 0

        fraction = min((abs_diff - self.entry_edge) / (self.full_edge - self.entry_edge), 1.0)
        target = int(round(limit * fraction))
        if diff > 0:
            target *= -1
        return target

    def _update_underlying_signal(self, mid: float) -> None:
        history = self.trader_data.setdefault("underlying_mid_history", [])
        append_rolling(history, mid, self.VOL_WINDOW)
        mean = rolling_mean(history)
        sigma = rolling_std(history)
        slope = rolling_slope(history)

        anchor_drift = clamp(
            self.MEAN_DRIFT_WEIGHT * (mean - self.UNDERLYING_FAIR),
            -self.MAX_ANCHOR_DRIFT,
            self.MAX_ANCHOR_DRIFT,
        )
        entry_edge = clamp(
            self.ENTRY_SIGMA_MULT * sigma,
            self.MIN_ENTRY_EDGE,
            self.MAX_ENTRY_EDGE,
        )
        full_edge = entry_edge + max(self.FULL_EXTRA_MIN, self.FULL_EXTRA_SIGMA_MULT * sigma)

        self.underlying_mid = mid
        self.underlying_anchor = self.UNDERLYING_FAIR + anchor_drift
        self.underlying_diff = mid - self.underlying_anchor
        self.underlying_sigma = sigma
        self.underlying_slope = slope

        slope_history = self.trader_data.setdefault("underlying_slope_history", [])
        if slope_history:
            self.underlying_slope_mean = rolling_mean(slope_history)
            self.underlying_slope_sigma = rolling_std(slope_history)
        else:
            self.underlying_slope_mean = self.underlying_slope
            self.underlying_slope_sigma = 0.0

        if self.underlying_slope_sigma > 0:
            self.underlying_slope_z = (
                (self.underlying_slope - self.underlying_slope_mean) / self.underlying_slope_sigma
            )
        else:
            self.underlying_slope_z = 0.0
        append_rolling(slope_history, self.underlying_slope, self.VOL_WINDOW)

        self.entry_edge = entry_edge
        self.full_edge = full_edge
        self.trader_data["underlying_anchor"] = self.underlying_anchor
        self.trader_data["underlying_sigma"] = self.underlying_sigma
        self.trader_data["underlying_slope"] = self.underlying_slope
        self.trader_data["underlying_slope_mean"] = self.underlying_slope_mean
        self.trader_data["underlying_slope_sigma"] = self.underlying_slope_sigma
        self.trader_data["underlying_slope_z"] = self.underlying_slope_z
        self.trader_data["underlying_entry_edge"] = self.entry_edge
        self.trader_data["underlying_full_edge"] = self.full_edge

    def _scaled_target(self, product: str, underlying_target: int) -> int:
        underlying_limit = POSITION_LIMITS[VELVETFRUIT_EXTRACT]
        product_limit = POSITION_LIMITS[product]
        target = int(round(underlying_target * product_limit / underlying_limit))
        if product in NEAR_ATM_PRODUCTS:
            target = int(round(target * self.NEAR_ATM_TARGET_MULTIPLIER))
        return max(-product_limit, min(product_limit, target))

    def _sucker_ask_prices(self, product: str, cp_track: dict) -> dict[int, int]:
        """v6: sucker の sell 価格集合を返す (price → extra_take 値)。

        cp_track[product] = {trader_name: [price, ...]} の構造。
        SUCKER_SELL_EDGE で指定されたトレーダーが直近 N tick で売った
        全価格について、価格→extra マップを返す。
        同じ価格に複数 trader の値があれば最大値 (より積極的) を採用。
        """
        result: dict[int, int] = {}
        if product not in self.SUCKER_PRODUCTS:
            return result
        product_track = cp_track.get(product, {})
        for trader_name, extra in self.SUCKER_SELL_EDGE.items():
            for price in product_track.get(trader_name, ()):
                p = int(price)
                if p not in result or extra > result[p]:
                    result[p] = int(extra)
        return result

    def _sucker_bid_prices(self, product: str, cp_bid_track: dict) -> dict[int, int]:
        """v6: sucker の bid 価格集合を返す (price → extra_take 値)。"""
        result: dict[int, int] = {}
        if product not in self.SUCKER_PRODUCTS:
            return result
        product_track = cp_bid_track.get(product, {})
        for trader_name, extra in self.SUCKER_BUY_EDGE.items():
            for price in product_track.get(trader_name, ()):
                p = int(price)
                if p not in result or extra > result[p]:
                    result[p] = int(extra)
        return result

    def _voucher_sucker_take(
        self,
        voucher_trader: "DirectionalTrader",
        voucher_fair: float,
        sucker_asks: dict[int, int],
        sucker_bids: dict[int, int],
    ) -> None:
        """voucher 商品 (DirectionalTrader 経由) に sucker take を適用。

        通常 trade_to_target の前段で sucker price を貪欲に処理する。
        position_limit (max_buy/max_sell) は voucher_trader 側で管理されるので
        ここで先食いした分は trade_to_target の余力が自動的に減る。
        """
        if not sucker_asks and not sucker_bids:
            return
        for price, qty in voucher_trader.sell_orders.items():
            extra = sucker_asks.get(int(price))
            if extra is None:
                continue
            if price <= voucher_fair + extra:
                voucher_trader.buy(int(price), abs(qty))
        for price, qty in voucher_trader.buy_orders.items():
            extra = sucker_bids.get(int(price))
            if extra is None:
                continue
            if price >= voucher_fair - extra:
                voucher_trader.sell(int(price), abs(qty))


CP_TRACK_TTL_TICKS = 2000           # 直近 2000 tick の取引価格を保持
CP_SELL_TRACK_TRADERS = ("Mark 49", "Mark 22")  # sucker as seller
CP_BUY_TRACK_TRADERS = ("Mark 49",)             # sucker as buyer


def _purge_and_collect(raw: dict, now: int) -> dict:
    """price_map 構造から TTL 内の価格リスト dict を作る。"""
    out: dict = {}
    for product, by_trader in raw.items():
        product_track: dict = {}
        for trader_name, price_map in by_trader.items():
            valid_prices = [int(p) for p, ts in price_map.items() if now - ts <= CP_TRACK_TTL_TICKS]
            price_map_new = {p: ts for p, ts in price_map.items() if now - ts <= CP_TRACK_TTL_TICKS}
            by_trader[trader_name] = price_map_new
            if valid_prices:
                product_track[trader_name] = valid_prices
        if product_track:
            out[product] = product_track
    return out


def update_counterparty_track(state: TradingState, trader_data: dict) -> None:
    """前 tick の market_trades から sucker 取引価格を蓄積。

    sell 用: __cp_track_raw__[product][trader] = {price: last_ts}
    bid  用: __cp_bid_track_raw__[product][trader] = {price: last_ts}
    """
    raw_sell = trader_data.setdefault("__cp_track_raw__", {})
    raw_buy = trader_data.setdefault("__cp_bid_track_raw__", {})
    now = state.timestamp

    for product, trades in (state.market_trades or {}).items():
        if not trades:
            continue
        product_sell = raw_sell.setdefault(product, {})
        product_buy = raw_buy.setdefault(product, {})
        for tr in trades:
            seller = getattr(tr, "seller", None)
            buyer = getattr(tr, "buyer", None)
            if seller in CP_SELL_TRACK_TRADERS:
                product_sell.setdefault(seller, {})[str(int(tr.price))] = now
            if buyer in CP_BUY_TRACK_TRADERS:
                product_buy.setdefault(buyer, {})[str(int(tr.price))] = now

    trader_data["__cp_track__"] = _purge_and_collect(raw_sell, now)
    trader_data["__cp_bid_track__"] = _purge_and_collect(raw_buy, now)


class Trader:
    def run(self, state: TradingState) -> tuple[dict[Symbol, list[Order]], int, str]:
        orders: dict[Symbol, list[Order]] = {}
        conversions = 0
        try:
            trader_data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            trader_data = {}
        new_trader_data: dict = {}

        # 候補A: counterparty (Mark 22) の sell 価格を更新。
        # この後の戦略がこの track を参照して fair value 計算で除外する。
        update_counterparty_track(state, trader_data)
        new_trader_data["__cp_track_raw__"] = trader_data.get("__cp_track_raw__", {})
        new_trader_data["__cp_bid_track_raw__"] = trader_data.get("__cp_bid_track_raw__", {})
        # HydrogelPackTrader が __init__ で参照するので state に残しておく
        trader_data["__cp_track__"] = trader_data.get("__cp_track__", {})
        trader_data["__cp_bid_track__"] = trader_data.get("__cp_bid_track__", {})

        if HYDROGEL_PACK in state.order_depths:
            strategy = HydrogelPackTrader(state, trader_data)
            orders[HYDROGEL_PACK] = strategy.run()

        if VELVETFRUIT_EXTRACT in state.order_depths or any(
            voucher in state.order_depths for voucher in VELVETFRUIT_EXTRACT_VOUCHERS
        ):
            options_strategy = VelvetfruitOptionsTrader(state, trader_data)
            option_orders = options_strategy.run()
            orders.update(option_orders)
            new_trader_data.update(options_strategy.trader_data)

        trader_data_out = json.dumps(new_trader_data)
        logger.flush(state, orders, conversions, trader_data_out)
        return orders, conversions, trader_data_out