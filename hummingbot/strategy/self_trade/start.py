from datetime import timedelta
from decimal import Decimal
from typing import (
    List,
    Tuple,
)

from hummingbot.strategy.self_trade.self_trade import SelfTradeStrategy
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.self_trade.self_trade_config_map import self_trade_config_map
from hummingbot.strategy.self_trade.trade_band import TradeBand


def start(self):
    try:
        _min_order_amount = self_trade_config_map.get("min_order_amount").value
        _max_order_amount = self_trade_config_map.get("max_order_amount").value
        _time_delay = self_trade_config_map.get("time_delay").value
        market = self_trade_config_map.get("market").value.lower()
        raw_market_trading_pair = self_trade_config_map.get("market_trading_pair_tuple").value
        _trade_bands = self_trade_config_map.get("trade_bands").value
        _delta_price_changed_percent = self_trade_config_map.get("delta_price_changed_percent").value
        _percentage_of_acceptable_price_change = self_trade_config_map.get("percentage_of_acceptable_price_change").value
        use_only_oracle_price = self_trade_config_map.get("use_only_oracle_price").value

        cancel_order_wait_time = self_trade_config_map.get("cancel_order_wait_time").value

        try:
            trading_pairs: list = raw_market_trading_pair
            assets: [Tuple[str, str]] = list(
                map(lambda x: tuple(x), self._initialize_market_assets(market, trading_pairs)))
        except ValueError as e:
            self._notify(str(e))
            return

        market_names: List[Tuple[str, List[str]]] = [(market, trading_pairs)]

        self._initialize_wallet(token_trading_pairs=list(set(assets)))
        self._initialize_markets(market_names)
        self.assets = set(assets)

        market_infos = [
            MarketTradingPairTuple(
                self.markets[market],
                trading_pair,
                *trading_pair.split("-", 1)
            ) for trading_pair in trading_pairs
        ]
        self.market_trading_pair_tuples = market_infos

        strategy_logging_options = SelfTradeStrategy.OPTION_LOG_ALL

        min_order_amount = {}
        for key, value in dict(_min_order_amount).items():
            min_order_amount[key] = Decimal(str(value))

        max_order_amount = {}
        for key, value in dict(_max_order_amount).items():
            max_order_amount[key] = Decimal(str(value))

        delta_price_changed_percent = {}
        for key, value in dict(_delta_price_changed_percent).items():
            delta_price_changed_percent[key] = Decimal(str(value))

        percentage_of_acceptable_price_change = {}
        for key, value in dict(_percentage_of_acceptable_price_change).items():
            percentage_of_acceptable_price_change[key] = Decimal(str(value))

        time_delay = {}
        for key, value in dict(_time_delay).items():
            time_delay[key] = float(value)

        trade_bands = {}
        for key, value in dict(_trade_bands).items():
            trade_bands[key] = [
                TradeBand(time_interval=timedelta(hours=float(hours)).seconds, required_amount=Decimal(str(amount)))
                for hours, amount in value.items()
            ]

        self.strategy = SelfTradeStrategy(market_infos=market_infos,
                                          time_delay=time_delay,
                                          min_order_amount=min_order_amount,
                                          max_order_amount=max_order_amount,
                                          trade_bands=trade_bands,
                                          delta_price_changed_percent=delta_price_changed_percent,
                                          percentage_of_acceptable_price_change=percentage_of_acceptable_price_change,
                                          cancel_order_wait_time=cancel_order_wait_time,
                                          logging_options=strategy_logging_options,
                                          use_only_oracle_price=use_only_oracle_price)
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
