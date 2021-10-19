from decimal import Decimal
from typing import (
    List,
    Tuple,
)

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.stones_with_payback.order_levels import OrderLevel
from hummingbot.strategy.stones_with_payback.stones_with_payback import StonesWithPaybackStrategy
from hummingbot.strategy.stones_with_payback.stones_with_payback_config_map import stones_with_payback_config_map


def start(self):
    try:
        market = stones_with_payback_config_map.get("market").value.lower()
        payback_market = stones_with_payback_config_map.get("payback_market").value.lower()

        raw_market_trading_pair = stones_with_payback_config_map.get("market_trading_pair_tuple").value

        time_delay = stones_with_payback_config_map.get("time_delay").value
        _total_buy_order_amount = stones_with_payback_config_map.get("total_buy_order_amount").value
        _total_sell_order_amount = stones_with_payback_config_map.get("total_sell_order_amount").value
        _buy_order_levels = stones_with_payback_config_map.get("buy_order_levels").value
        _sell_order_levels = stones_with_payback_config_map.get("sell_order_levels").value
        _payback_infos = stones_with_payback_config_map.get("payback_info").value

        try:
            trading_pairs: list = raw_market_trading_pair
            assets: [Tuple[str, str]] = list(map(lambda x: tuple(x), self._initialize_market_assets(market, trading_pairs)))
            payback_trading_pairs = list(_payback_infos.values())
            payback_assets: [Tuple[str, str]] = list(map(lambda x: tuple(x), self._initialize_market_assets(payback_market, payback_trading_pairs)))
        except ValueError as e:
            self._notify(str(e))
            return

        market_names: List[Tuple[str, List[str]]] = [(market, trading_pairs)]
        payback_market_names: List[Tuple[str, List[str]]] = [(payback_market, payback_trading_pairs)]

        self._initialize_wallet(token_trading_pairs=list(set(assets + payback_assets)))
        self._initialize_markets(market_names + payback_market_names)
        self.assets = set(assets + payback_assets)

        market_infos = [
            MarketTradingPairTuple(
                self.markets[market],
                trading_pair,
                *trading_pair.split("-", 1)
            ) for trading_pair in trading_pairs
        ]

        payback_info = dict()
        for market_info in market_infos:
            _payback_info = _payback_infos.get(market_info.trading_pair)
            if _payback_info is not None:
                payback_info[market_info] = MarketTradingPairTuple(
                    self.markets[payback_market],
                    _payback_info,
                    *_payback_info.split("-", 1)
                )

        self.market_trading_pair_tuples = market_infos + list(payback_info.values())

        buy_order_levels = []
        for pair, levels in _buy_order_levels.items():
            for number, level in levels.items():
                buy_order_levels.append(
                    OrderLevel(
                        number=number,
                        market=self.markets[market],
                        trading_pair=pair,
                        min_percentage_price_change=Decimal(str(level['min_percentage_price_change'])),
                        max_percentage_price_change=Decimal(str(level['max_percentage_price_change'])),
                        min_order_amount=Decimal(str(level['min_order_amount'])),
                        max_order_amount=Decimal(str(level['max_order_amount'])),
                        percentage_of_liquidity=Decimal(str(level['percentage_of_liquidity'])),
                        is_buy=True,
                    )
                )
        sell_order_levels = []
        for pair, levels in _sell_order_levels.items():
            for number, level in levels.items():
                sell_order_levels.append(
                    OrderLevel(
                        number=number,
                        market=self.markets[market],
                        trading_pair=pair,
                        min_percentage_price_change=Decimal(str(level['min_percentage_price_change'])),
                        max_percentage_price_change=Decimal(str(level['max_percentage_price_change'])),
                        min_order_amount=Decimal(str(level['min_order_amount'])),
                        max_order_amount=Decimal(str(level['max_order_amount'])),
                        percentage_of_liquidity=Decimal(str(level['percentage_of_liquidity'])),
                        is_buy=False
                    )
                )

        strategy_logging_options = StonesWithPaybackStrategy.OPTION_LOG_ALL

        total_buy_order_amount = {}
        for key, value in dict(_total_buy_order_amount).items():
            total_buy_order_amount[key] = Decimal(str(value))

        total_sell_order_amount = {}
        for key, value in dict(_total_sell_order_amount).items():
            total_sell_order_amount[key] = Decimal(str(value))

        self.strategy = StonesWithPaybackStrategy(
            market_infos=market_infos,
            time_delay=time_delay,
            logging_options=strategy_logging_options,
            total_buy_order_amount=total_buy_order_amount,
            total_sell_order_amount=total_sell_order_amount,
            buy_order_levels=buy_order_levels,
            sell_order_levels=sell_order_levels,
            payback_info=payback_info
        )
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
