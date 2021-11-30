from typing import (
    List,
    Optional,
    Tuple,
)
from decimal import Decimal

from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher
from hummingbot.core.event.events import TradeType

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.triangular_arbitrage.model.arbitrage import (TriangularArbitrage, Node, Edge)
from hummingbot.strategy.triangular_arbitrage.triangular_arbitrage import TriangularArbitrageStrategy
from hummingbot.strategy.triangular_arbitrage.triangular_arbitrage_config_map import triangular_arbitrage_config_map
from hummingbot.strategy.triangular_arbitrage.triangular_arbitrage_calculation import TriangularArbitrageCalculator
from hummingbot.strategy.triangular_arbitrage.optimizer.order_book_preprocessor import OrderBookPreprocessor

trading_pair_fetcher: TradingPairFetcher = TradingPairFetcher.get_instance()


def validate_trading_pair(market, trading_pair):
    if trading_pair_fetcher.ready:
        trading_pairs = trading_pair_fetcher.trading_pairs.get(market, [])
        if len(trading_pairs) == 0:
            return False
        elif trading_pair not in trading_pairs:
            return False
        else:
            return True


def infer_market_trading_pair(market, source, target) -> Optional[str]:
    source_to_target = f"{source}-{target}"
    target_to_source = f"{target}-{source}"
    retval = (None, None)
    if validate_trading_pair(market, source_to_target):
        retval = (source_to_target, "forward")
    elif validate_trading_pair(market, target_to_source):
        retval = (target_to_source, "backward")
    return retval


def start(self):
    try:
        exchange = triangular_arbitrage_config_map.get("exchange").value.lower()

        target_currency = triangular_arbitrage_config_map.get("target_currency").value
        target_node = target_currency
        first_aux_currency = triangular_arbitrage_config_map.get("first_aux_currency").value
        left_node = first_aux_currency
        second_aux_currency = triangular_arbitrage_config_map.get("second_aux_currency").value
        right_node = second_aux_currency

        replacement_left_source_currency = triangular_arbitrage_config_map.get("replacement_source_currency_on_left_edge").value
        if replacement_left_source_currency is None:
            replacement_left_source_currency = target_currency

        replacement_left_target_currency = triangular_arbitrage_config_map.get("replacement_target_currency_on_left_edge").value
        if replacement_left_target_currency is None:
            replacement_left_target_currency = first_aux_currency

        replacement_bottom_source_currency = triangular_arbitrage_config_map.get("replacement_source_currency_on_bottom_edge").value
        if replacement_bottom_source_currency is None:
            replacement_bottom_source_currency = first_aux_currency

        replacement_bottom_target_currency = triangular_arbitrage_config_map.get("replacement_target_currency_on_bottom_edge").value
        if replacement_bottom_target_currency is None:
            replacement_bottom_target_currency = second_aux_currency

        replacement_right_source_currency = triangular_arbitrage_config_map.get("replacement_source_currency_on_right_edge").value
        if replacement_right_source_currency is None:
            replacement_right_source_currency = second_aux_currency

        replacement_right_target_currency = triangular_arbitrage_config_map.get("replacement_target_currency_on_right_edge").value
        if replacement_right_target_currency is None:
            replacement_right_target_currency = target_currency

        raw_primary_trading_pair, direction_p = infer_market_trading_pair(exchange, replacement_left_source_currency, replacement_left_target_currency)
        if raw_primary_trading_pair is None:
            source_to_target = f"{replacement_left_source_currency}-{replacement_left_target_currency}"
            target_to_source = f"{replacement_left_target_currency}-{replacement_left_source_currency}"
            self.logger().warning(f"Neither {source_to_target} nor {target_to_source} is a recognized trading pair on {exchange}")
        raw_secondary_trading_pair, direction_s = infer_market_trading_pair(exchange, replacement_bottom_source_currency, replacement_bottom_target_currency)
        if raw_secondary_trading_pair is None:
            source_to_target = f"{replacement_bottom_source_currency}-{replacement_bottom_target_currency}"
            target_to_source = f"{replacement_bottom_target_currency}-{replacement_bottom_source_currency}"
            self.logger().warning(f"Neither {source_to_target} nor {target_to_source} is a recognized trading pair on {exchange}")
        raw_tertiary_trading_pair, direction_t = infer_market_trading_pair(exchange, replacement_right_source_currency, replacement_right_target_currency)
        if raw_tertiary_trading_pair is None:
            source_to_target = f"{replacement_right_source_currency}-{replacement_right_target_currency}"
            target_to_source = f"{replacement_right_target_currency}-{replacement_right_source_currency}"
            self.logger().warning(f"Neither {source_to_target} nor {target_to_source} is a recognized trading pair on {exchange}")
        primary_market = exchange
        secondary_market = exchange
        tertiary_market = exchange

        min_profitability = triangular_arbitrage_config_map.get("min_profitability").value / Decimal("100")
        fee_override = triangular_arbitrage_config_map.get("fee_override").value

        try:
            primary_trading_pair: str = raw_primary_trading_pair
            secondary_trading_pair: str = raw_secondary_trading_pair
            tertiary_trading_pair: str = raw_tertiary_trading_pair
            primary_assets: Tuple[str, str] = self._initialize_market_assets(primary_market, [primary_trading_pair])[0]
            secondary_assets: Tuple[str, str] = self._initialize_market_assets(secondary_market,
                                                                               [secondary_trading_pair])[0]
            tertiary_assets: Tuple[str, str] = self._initialize_market_assets(tertiary_market,
                                                                              [tertiary_trading_pair])[0]
        except ValueError as e:
            self._notify(str(e))
            return

        market_names: List[Tuple[str, List[str]]] = [(primary_market, [primary_trading_pair]),
                                                     (secondary_market, [secondary_trading_pair]),
                                                     (tertiary_market, [tertiary_trading_pair])]
        self._initialize_markets(market_names)
        self.assets = set(primary_assets + secondary_assets + tertiary_assets)
        primary_data = [self.markets[primary_market], primary_trading_pair] + list(primary_assets)
        secondary_data = [self.markets[secondary_market], secondary_trading_pair] + list(secondary_assets)
        tertiary_data = [self.markets[tertiary_market], tertiary_trading_pair] + list(tertiary_assets)
        self.market_trading_pair_tuples = [MarketTradingPairTuple(*primary_data), MarketTradingPairTuple(*secondary_data), MarketTradingPairTuple(*tertiary_data)]

        # Setup Arbitrage triangle from configuration
        # Counter-clockwise direction from top node
        primary_trade_type = TradeType.SELL if direction_p == "forward" else TradeType.BUY
        secondary_trade_type = TradeType.SELL if direction_s == "forward" else TradeType.BUY
        tertiary_trade_type = TradeType.SELL if direction_t == "forward" else TradeType.BUY

        primary_market_id = 0
        secondary_market_id = primary_market_id if primary_market == secondary_market else 1
        if tertiary_market == primary_market:
            tertiary_market_id = primary_market_id
        elif tertiary_market == secondary_market:
            tertiary_market_id = 1
        else:
            tertiary_market_id = 2

        arbitrage_ccw = TriangularArbitrage(
            top = Node(target_node),
            left = Node(left_node),
            right = Node(right_node),
            left_edge = Edge(primary_market_id, primary_trading_pair, primary_trade_type, Decimal(0), Decimal(0), fee=fee_override),
            cross_edge = Edge(secondary_market_id, secondary_trading_pair, secondary_trade_type, Decimal(0), Decimal(0), fee=fee_override),
            right_edge = Edge(tertiary_market_id, tertiary_trading_pair, tertiary_trade_type, Decimal(0), Decimal(0), fee=fee_override)
        )

        inverse_primary_trade_type = TradeType.BUY if primary_trade_type == TradeType.SELL else TradeType.SELL
        inverse_secondary_trade_type = TradeType.BUY if secondary_trade_type == TradeType.SELL else TradeType.SELL
        inverse_tertiary_trade_type = TradeType.BUY if tertiary_trade_type == TradeType.SELL else TradeType.SELL

        arbitrage_cw = TriangularArbitrage(
            top = Node(target_node),
            left = Node(left_node),
            right = Node(right_node),
            left_edge = Edge(primary_market_id, primary_trading_pair, inverse_primary_trade_type, Decimal(0), Decimal(0), fee=fee_override),
            cross_edge = Edge(secondary_market_id, secondary_trading_pair, inverse_secondary_trade_type, Decimal(0), Decimal(0), fee=fee_override),
            right_edge = Edge(tertiary_market_id, tertiary_trading_pair, inverse_tertiary_trade_type, Decimal(0), Decimal(0), fee=fee_override),
            direction = 1
        )

        preprocessor = OrderBookPreprocessor(arbitrage_ccw)

        triangular_arbitrage_calculator = TriangularArbitrageCalculator(
            target_node=target_node,
            left_node=left_node,
            right_node=right_node,
            primary_market=primary_market,
            secondary_market=secondary_market,
            tertiary_market=tertiary_market,
            primary_trading_pair=primary_trading_pair,
            secondary_trading_pair=secondary_trading_pair,
            tertiary_trading_pair=tertiary_trading_pair,
            min_profitability=min_profitability,
            fee_override=fee_override,
            arbitrage_ccw = arbitrage_ccw,
            arbitrage_cw = arbitrage_cw,
            preprocessor=preprocessor
        )

        self.strategy = TriangularArbitrageStrategy(market_pairs=self.market_trading_pair_tuples,
                                                    min_profitability=min_profitability,
                                                    triangular_arbitrage_calculator=triangular_arbitrage_calculator,
                                                    logging_options=TriangularArbitrageStrategy.OPTION_LOG_ALL,
                                                    )
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Error during initialization.", exc_info=True)
