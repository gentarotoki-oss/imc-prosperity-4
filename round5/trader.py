"""
AUTO-GENERATED FILE.
Do not edit directly.
Generated: 2026-04-29 23:11:03
"""

from __future__ import annotations

import json
from typing import Dict, List
from json import JSONEncoder
import jsonpickle
from typing import Any

# ===== BEGIN common/constants.py =====
GALAXY_SOUNDS_DARK_MATTER = "GALAXY_SOUNDS_DARK_MATTER"
GALAXY_SOUNDS_BLACK_HOLES = "GALAXY_SOUNDS_BLACK_HOLES"
GALAXY_SOUNDS_PLANETARY_RINGS = "GALAXY_SOUNDS_PLANETARY_RINGS"
GALAXY_SOUNDS_SOLAR_WINDS = "GALAXY_SOUNDS_SOLAR_WINDS"
GALAXY_SOUNDS_SOLAR_FLAMES = "GALAXY_SOUNDS_SOLAR_FLAMES"
SLEEP_POD_SUEDE = "SLEEP_POD_SUEDE"
SLEEP_POD_LAMB_WOOL = "SLEEP_POD_LAMB_WOOL"
SLEEP_POD_POLYESTER = "SLEEP_POD_POLYESTER"
SLEEP_POD_NYLON = "SLEEP_POD_NYLON"
SLEEP_POD_COTTON = "SLEEP_POD_COTTON"
MICROCHIP_CIRCLE = "MICROCHIP_CIRCLE"
MICROCHIP_OVAL = "MICROCHIP_OVAL"
MICROCHIP_SQUARE = "MICROCHIP_SQUARE"
MICROCHIP_RECTANGLE = "MICROCHIP_RECTANGLE"
MICROCHIP_TRIANGLE = "MICROCHIP_TRIANGLE"
PEBBLES_XS = "PEBBLES_XS"
PEBBLES_S = "PEBBLES_S"
PEBBLES_M = "PEBBLES_M"
PEBBLES_L = "PEBBLES_L"
PEBBLES_XL = "PEBBLES_XL"
ROBOT_VACUUMING = "ROBOT_VACUUMING"
ROBOT_MOPPING = "ROBOT_MOPPING"
ROBOT_DISHES = "ROBOT_DISHES"
ROBOT_LAUNDRY = "ROBOT_LAUNDRY"
ROBOT_IRONING = "ROBOT_IRONING"
UV_VISOR_YELLOW = "UV_VISOR_YELLOW"
UV_VISOR_AMBER = "UV_VISOR_AMBER"
UV_VISOR_ORANGE = "UV_VISOR_ORANGE"
UV_VISOR_RED = "UV_VISOR_RED"
UV_VISOR_MAGENTA = "UV_VISOR_MAGENTA"
TRANSLATOR_SPACE_GRAY = "TRANSLATOR_SPACE_GRAY"
TRANSLATOR_ASTRO_BLACK = "TRANSLATOR_ASTRO_BLACK"
TRANSLATOR_ECLIPSE_CHARCOAL = "TRANSLATOR_ECLIPSE_CHARCOAL"
TRANSLATOR_GRAPHITE_MIST = "TRANSLATOR_GRAPHITE_MIST"
TRANSLATOR_VOID_BLUE = "TRANSLATOR_VOID_BLUE"
PANEL_1X2 = "PANEL_1X2"
PANEL_2X2 = "PANEL_2X2"
PANEL_1X4 = "PANEL_1X4"
PANEL_2X4 = "PANEL_2X4"
PANEL_4X4 = "PANEL_4X4"
OXYGEN_SHAKE_MORNING_BREATH = "OXYGEN_SHAKE_MORNING_BREATH"
OXYGEN_SHAKE_EVENING_BREATH = "OXYGEN_SHAKE_EVENING_BREATH"
OXYGEN_SHAKE_MINT = "OXYGEN_SHAKE_MINT"
OXYGEN_SHAKE_CHOCOLATE = "OXYGEN_SHAKE_CHOCOLATE"
OXYGEN_SHAKE_GARLIC = "OXYGEN_SHAKE_GARLIC"
SNACKPACK_CHOCOLATE = "SNACKPACK_CHOCOLATE"
SNACKPACK_VANILLA = "SNACKPACK_VANILLA"
SNACKPACK_PISTACHIO = "SNACKPACK_PISTACHIO"
SNACKPACK_STRAWBERRY = "SNACKPACK_STRAWBERRY"
SNACKPACK_RASPBERRY = "SNACKPACK_RASPBERRY"

POSITION_LIMITS = 10
# ===== END common/constants.py =====

# ===== BEGIN datamodel.py =====
Time = int
Symbol = str
Product = str
Position = int
UserId = str
ObservationValue = int


class Listing:

    def __init__(self, symbol: Symbol, product: Product, denomination: Product):
        self.symbol = symbol
        self.product = product
        self.denomination = denomination
        
                 
class ConversionObservation:

    def __init__(self, bidPrice: float, askPrice: float, transportFees: float, exportTariff: float, importTariff: float, sunlight: float, humidity: float):
        self.bidPrice = bidPrice
        self.askPrice = askPrice
        self.transportFees = transportFees
        self.exportTariff = exportTariff
        self.importTariff = importTariff
        self.sugarPrice = sugarPrice
        self.sunlightIndex = sunlightIndex
        

class Observation:

    def __init__(self, plainValueObservations: Dict[Product, ObservationValue], conversionObservations: Dict[Product, ConversionObservation]) -> None:
        self.plainValueObservations = plainValueObservations
        self.conversionObservations = conversionObservations
        
    def __str__(self) -> str:
        return "(plainValueObservations: " + jsonpickle.encode(self.plainValueObservations) + ", conversionObservations: " + jsonpickle.encode(self.conversionObservations) + ")"
     

class Order:

    def __init__(self, symbol: Symbol, price: int, quantity: int) -> None:
        self.symbol = symbol
        self.price = price
        self.quantity = quantity

    def __str__(self) -> str:
        return "(" + self.symbol + ", " + str(self.price) + ", " + str(self.quantity) + ")"

    def __repr__(self) -> str:
        return "(" + self.symbol + ", " + str(self.price) + ", " + str(self.quantity) + ")"
    

class OrderDepth:

    def __init__(self):
        self.buy_orders: Dict[int, int] = {}
        self.sell_orders: Dict[int, int] = {}


class Trade:

    def __init__(self, symbol: Symbol, price: int, quantity: int, buyer: UserId=None, seller: UserId=None, timestamp: int=0) -> None:
        self.symbol = symbol
        self.price: int = price
        self.quantity: int = quantity
        self.buyer = buyer
        self.seller = seller
        self.timestamp = timestamp

    def __str__(self) -> str:
        return "(" + self.symbol + ", " + self.buyer + " << " + self.seller + ", " + str(self.price) + ", " + str(self.quantity) + ", " + str(self.timestamp) + ")"

    def __repr__(self) -> str:
        return "(" + self.symbol + ", " + self.buyer + " << " + self.seller + ", " + str(self.price) + ", " + str(self.quantity) + ", " + str(self.timestamp) + ")"


class TradingState(object):

    def __init__(self,
                 traderData: str,
                 timestamp: Time,
                 listings: Dict[Symbol, Listing],
                 order_depths: Dict[Symbol, OrderDepth],
                 own_trades: Dict[Symbol, List[Trade]],
                 market_trades: Dict[Symbol, List[Trade]],
                 position: Dict[Product, Position],
                 observations: Observation):
        self.traderData = traderData
        self.timestamp = timestamp
        self.listings = listings
        self.order_depths = order_depths
        self.own_trades = own_trades
        self.market_trades = market_trades
        self.position = position
        self.observations = observations
        
    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True)

    
class ProsperityEncoder(JSONEncoder):

        def default(self, o):
            return o.__dict__
# ===== END datamodel.py =====

# ===== BEGIN logger.py =====
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


class Trader:
    def run(self, state: TradingState) -> tuple[dict[Symbol, list[Order]], int, str]:
        result = {}
        conversions = 0
        trader_data = ""

        # TODO: Add logic

        logger.flush(state, result, conversions, trader_data)
        return result, conversions, trader_data
# ===== END logger.py =====

# ===== BEGIN strategies/round5.py =====
LONG = 1
SHORT = -1
POSITION_LIMIT = 10

ROUND5_DIRECTIONS = {
    GALAXY_SOUNDS_BLACK_HOLES: LONG,
    MICROCHIP_OVAL: SHORT,
    PEBBLES_XS: SHORT,
    PEBBLES_S: SHORT,
    UV_VISOR_AMBER: SHORT,
    PANEL_2X4: LONG,
    OXYGEN_SHAKE_GARLIC: LONG,
    UV_VISOR_RED: LONG,
}


DIRECTIONAL_MAX_STEP = 3
DIRECTIONAL_TAKE_EDGE = 1

TREND_FAST_ALPHA = 0.20
TREND_SLOW_ALPHA = 0.05
TREND_THRESHOLD = 1.5

TREND_QUOTE_EDGE = 2
TREND_TAKE_EDGE = 2
INVENTORY_SKEW = 0.2
MM_MOMENTUM_THRESHOLD = 900
MM_MOMENTUM_FAIR_SHIFT = 2

RELATIVE_THRESHOLD = 0
SNACK_RELATIVE_MAX_STEP = 10
PEBBLE_RELATIVE_MAX_STEP = 2
PEBBLE_SPREAD_MOMENTUM_THRESHOLD = 300


SNACK_PRODUCTS = [
    SNACKPACK_CHOCOLATE,
    SNACKPACK_PISTACHIO,
    SNACKPACK_RASPBERRY,
    SNACKPACK_STRAWBERRY,
    SNACKPACK_VANILLA,
]

PEBBLE_PRODUCTS = [
    PEBBLES_L,
    PEBBLES_M,
    PEBBLES_S,
    PEBBLES_XL,
    PEBBLES_XS,
]

class Round5ProductTrader:
    def __init__(
        self,
        product: str,
        direction: int | None,
        direction_limit: int,
        relative_direction: int | None,
        relative_max_step: int,
        state: TradingState,
        trader_data: dict,
    ):
        self.product = product
        self.direction = direction
        self.direction_limit = direction_limit
        self.relative_direction = relative_direction
        self.relative_max_step = relative_max_step
        self.state = state
        self.trader_data = trader_data
        self.orders: list[Order] = []
        self.depth = state.order_depths.get(product)
        self.position = state.position.get(product, 0)

        self.limit = POSITION_LIMIT
        self.max_buy = self.limit - self.position
        self.max_sell = self.limit + self.position

    def run(self) -> list[Order]:
        if self.depth is None:
            return self.orders

        if self.direction is not None:
            target = self.direction * self.direction_limit
            self._trade_to_target(target, max_step=DIRECTIONAL_MAX_STEP)

        if self.relative_direction is not None:
            target = self.relative_direction * self.limit
            self._trade_to_target(target, max_step=self.relative_max_step)

        if self.direction is None and self.relative_direction is None:
            self._market_make()

        return self.orders

    def _trade_to_target(self, target: int, max_step: int) -> None:
        target = max(-self.limit, min(self.limit, target))
        delta = max(-max_step, min(max_step, target - self.position))
        if delta == 0:
            return

        buy_orders = self.depth.buy_orders
        sell_orders = self.depth.sell_orders
        if not buy_orders or not sell_orders:
            return

        best_bid = max(buy_orders)
        best_ask = min(sell_orders)
        fair = (best_bid + best_ask) / 2

        if delta > 0:
            remaining = delta
            for price, volume in sorted(sell_orders.items()):
                if price <= fair + DIRECTIONAL_TAKE_EDGE:
                    quantity = min(remaining, abs(volume))
                    self._buy(price, quantity)
                    remaining -= quantity
                    if remaining <= 0:
                        return
                else:
                    break

            if remaining > 0:
                price = self._passive_bid()
                if price is not None:
                    self._buy(price, remaining)

        else:
            remaining = -delta
            for price, volume in sorted(buy_orders.items(), reverse=True):
                if price >= fair - DIRECTIONAL_TAKE_EDGE:
                    quantity = min(remaining, abs(volume))
                    self._sell(price, quantity)
                    remaining -= quantity
                    if remaining <= 0:
                        return
                else:
                    break

            if remaining > 0:
                price = self._passive_ask()
                if price is not None:
                    self._sell(price, remaining)

    def _market_make(self) -> None:
        buy_orders = self.depth.buy_orders
        sell_orders = self.depth.sell_orders
        if not buy_orders or not sell_orders:
            return

        sorted_bids = sorted(buy_orders.items(), reverse=True)
        sorted_asks = sorted(sell_orders.items())

        bid_wall = sorted_bids[-1][0]
        ask_wall = sorted_asks[-1][0]

        fair = (bid_wall + ask_wall) / 2
        fair -= INVENTORY_SKEW * self.position

        best_mid = (sorted_bids[0][0] + sorted_asks[0][0]) / 2
        trend = self._trend_state(best_mid)
        open_momentum = self._open_momentum_state(best_mid)
        if open_momentum == trend:
            fair += MM_MOMENTUM_FAIR_SHIFT * open_momentum

        buy_take_edge = TREND_TAKE_EDGE if trend < 0 else 1
        sell_take_edge = TREND_TAKE_EDGE if trend > 0 else 1

        for price, volume in sorted_asks:
            if price <= fair - buy_take_edge:
                self._buy(price, abs(volume))

        for price, volume in sorted_bids:
            if price >= fair + sell_take_edge:
                self._sell(price, abs(volume))

        bid_price = bid_wall + 1
        ask_price = ask_wall - 1

        if bid_price >= ask_price:
            bid_price = int(fair) - 1
            ask_price = int(fair) + 1

        if trend < 0:
            bid_price = min(bid_price, int(fair - TREND_QUOTE_EDGE))
        elif trend > 0:
            ask_price = max(ask_price, int(fair + TREND_QUOTE_EDGE + 0.999999))

        self._buy(bid_price, self.max_buy)
        self._sell(ask_price, self.max_sell)

    def _open_momentum_state(self, mid: float) -> int:
        open_data = self.trader_data.setdefault("open_mid", {})
        open_mid = open_data.setdefault(self.product, mid)
        move = mid - open_mid

        if move > MM_MOMENTUM_THRESHOLD:
            return LONG
        if move < -MM_MOMENTUM_THRESHOLD:
            return SHORT
        return 0

    def _trend_state(self, mid: float) -> int:
        trend_data = self.trader_data.setdefault("trend", {})
        product_data = trend_data.setdefault(self.product, {})

        fast = product_data.get("fast", mid)
        slow = product_data.get("slow", mid)

        fast += TREND_FAST_ALPHA * (mid - fast)
        slow += TREND_SLOW_ALPHA * (mid - slow)

        product_data["fast"] = fast
        product_data["slow"] = slow

        diff = fast - slow
        if diff > TREND_THRESHOLD:
            return 1
        if diff < -TREND_THRESHOLD:
            return -1
        return 0

    def _passive_bid(self) -> int | None:
        buy_orders = self.depth.buy_orders
        sell_orders = self.depth.sell_orders

        best_bid = max(buy_orders) if buy_orders else None
        best_ask = min(sell_orders) if sell_orders else None

        if best_bid is None:
            return None if best_ask is None else best_ask - 1
        if best_ask is None:
            return best_bid + 1

        if best_bid + 1 < best_ask:
            return best_bid + 1
        return best_bid

    def _passive_ask(self) -> int | None:
        buy_orders = self.depth.buy_orders
        sell_orders = self.depth.sell_orders

        best_bid = max(buy_orders) if buy_orders else None
        best_ask = min(sell_orders) if sell_orders else None

        if best_ask is None:
            return None if best_bid is None else best_bid + 1
        if best_bid is None:
            return best_ask - 1

        if best_bid + 1 < best_ask:
            return best_ask - 1
        return best_ask

    def _buy(self, price: int, quantity: int) -> None:
        quantity = min(int(quantity), self.max_buy)
        if quantity <= 0:
            return

        self.orders.append(Order(self.product, int(price), quantity))
        self.max_buy -= quantity

    def _sell(self, price: int, quantity: int) -> None:
        quantity = min(int(quantity), self.max_sell)
        if quantity <= 0:
            return

        self.orders.append(Order(self.product, int(price), -quantity))
        self.max_sell -= quantity


class Round5Trader:
    def __init__(self, state: TradingState, trader_data: dict | None = None):
        self.state = state
        self.trader_data = trader_data if trader_data is not None else {}

    def run(self) -> dict[str, list[Order]]:
        orders: dict[str, list[Order]] = {}

        mids = self._get_mids()
        relative_directions = self._relative_directions(mids)

        for product in self.state.order_depths:
            direction, direction_limit = self._direction_for_product(product, mids, relative_directions)

            product_orders = Round5ProductTrader(
                product=product,
                direction=direction,
                direction_limit=direction_limit,
                relative_direction=relative_directions.get(product),
                relative_max_step=self._relative_max_step(product),
                state=self.state,
                trader_data=self.trader_data,
            ).run()

            if product_orders:
                orders[product] = product_orders

        return orders

    def _direction_for_product(
        self,
        product: str,
        mids: dict[str, float],
        relative_directions: dict[str, int],
    ) -> tuple[int | None, int]:
        direction = ROUND5_DIRECTIONS.get(product)
        if direction is not None:
            return direction, POSITION_LIMIT
        return None, 0

    def _get_mids(self) -> dict[str, float]:
        mids = {}

        for product, depth in self.state.order_depths.items():
            if not depth.buy_orders or not depth.sell_orders:
                continue

            best_bid = max(depth.buy_orders)
            best_ask = min(depth.sell_orders)
            mids[product] = (best_bid + best_ask) / 2

        return mids

    def _relative_max_step(self, product: str) -> int:
        if product in SNACK_PRODUCTS:
            return SNACK_RELATIVE_MAX_STEP
        if product in PEBBLE_PRODUCTS:
            return PEBBLE_RELATIVE_MAX_STEP
        return PEBBLE_RELATIVE_MAX_STEP

    def _relative_directions(self, mids: dict[str, float]) -> dict[str, int]:
        directions: dict[str, int] = {}

        if all(p in mids for p in [SNACKPACK_CHOCOLATE, SNACKPACK_VANILLA]):
            spread = mids[SNACKPACK_CHOCOLATE] - mids[SNACKPACK_VANILLA]

            if spread > RELATIVE_THRESHOLD:
                directions[SNACKPACK_CHOCOLATE] = SHORT
                directions[SNACKPACK_VANILLA] = LONG
            elif spread < -RELATIVE_THRESHOLD:
                directions[SNACKPACK_CHOCOLATE] = LONG
                directions[SNACKPACK_VANILLA] = SHORT

        if all(p in mids for p in [SNACKPACK_PISTACHIO, SNACKPACK_STRAWBERRY, SNACKPACK_RASPBERRY]):
            basket = (mids[SNACKPACK_PISTACHIO] + mids[SNACKPACK_STRAWBERRY]) / 2
            spread = mids[SNACKPACK_RASPBERRY] - basket

            if spread > RELATIVE_THRESHOLD:
                directions[SNACKPACK_RASPBERRY] = SHORT
                directions[SNACKPACK_PISTACHIO] = LONG
                directions[SNACKPACK_STRAWBERRY] = LONG
            elif spread < -RELATIVE_THRESHOLD:
                directions[SNACKPACK_RASPBERRY] = LONG
                directions[SNACKPACK_PISTACHIO] = SHORT
                directions[SNACKPACK_STRAWBERRY] = SHORT

        if all(p in mids for p in [PEBBLES_L, PEBBLES_M, PEBBLES_S, PEBBLES_XL]):
            others = (mids[PEBBLES_L] + mids[PEBBLES_M] + mids[PEBBLES_S]) / 3
            spread = mids[PEBBLES_XL] - others

            open_spreads = self.trader_data.setdefault("open_spread", {})
            open_spread = open_spreads.setdefault("PEBBLES_XL_LMS", spread)
            spread_move = spread - open_spread

            if spread_move > PEBBLE_SPREAD_MOMENTUM_THRESHOLD:
                directions[PEBBLES_XL] = LONG
                directions[PEBBLES_L] = SHORT
                directions[PEBBLES_M] = SHORT
                directions[PEBBLES_S] = SHORT
            elif spread_move < -PEBBLE_SPREAD_MOMENTUM_THRESHOLD:
                directions[PEBBLES_XL] = SHORT
                directions[PEBBLES_L] = LONG
                directions[PEBBLES_M] = LONG
                directions[PEBBLES_S] = LONG

        return directions

    def export_state(self) -> dict:
        return self.trader_data
# ===== END strategies/round5.py =====

# ===== BEGIN trader.py =====
class Trader:
    """各商品の戦略クラスを呼び出し、注文と内部状態を集約する。"""

    def run(self, state: TradingState):
        """現在の市場状態から各戦略の注文を生成して返す。"""
        orders = {}
        conversions = 0

        try:
            # 前回ティックから引き継いだ内部状態を復元する。
            trader_data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            trader_data = {}

        new_trader_data = {}

        round5_strategy = Round5Trader(state, trader_data)
        orders.update(round5_strategy.run())
        new_trader_data.update(round5_strategy.export_state())

        trader_data_out = json.dumps(new_trader_data)

        logger.flush(state, orders, conversions, trader_data_out)
        return orders, conversions, trader_data_out
# ===== END trader.py =====
