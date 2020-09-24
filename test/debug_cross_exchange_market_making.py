#!/usr/bin/env python

import sys
import os; sys.path.insert(0, os.path.realpath(os.path.join(__file__, "../../")))
import logging; logging.basicConfig(level=logging.DEBUG)
import pandas as pd
import hummingsim
from hummingsim.backtest.backtest_market import BacktestMarket
from hummingsim.backtest.binance_order_book_loader_v2 import BinanceOrderBookLoaderV2
from hummingsim.backtest.market import QuantizationParams
from hummingsim.backtest.market_config import (
    MarketConfig,
    AssetType
)
from hummingsim.backtest.ddex_order_book_loader import DDEXOrderBookLoader
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.strategy.cross_exchange_market_making import (
    CrossExchangeMarketMakingStrategy,
    CrossExchangeMarketPair,
)


def main():
    # Define the data cache path.
    hummingsim.set_data_path(os.path.join(os.environ["PWD"], "data"))

    # Define the parameters for the backtest.
    start = pd.Timestamp("2018-12-12", tz="UTC")
    end = pd.Timestamp("2019-01-12", tz="UTC")
    binance_trading_pair = ("ETHUSDT", "ETH", "USDT")
    ddex_trading_pair = ("WETH-DAI", "WETH", "DAI")

    binance_market = BacktestMarket()
    ddex_market = BacktestMarket()
    binance_market.config = MarketConfig(AssetType.BASE_CURRENCY, 0.001, AssetType.QUOTE_CURRENCY, 0.001, {})
    ddex_market.config = MarketConfig(AssetType.BASE_CURRENCY, 0.001, AssetType.QUOTE_CURRENCY, 0.001, {})
    binance_loader = BinanceOrderBookLoaderV2(*binance_trading_pair)
    ddex_loader = DDEXOrderBookLoader(*ddex_trading_pair)

    binance_market.add_data(binance_loader)
    ddex_market.add_data(ddex_loader)

    binance_market.set_quantization_param(QuantizationParams("ETHUSDT", 5, 3, 5, 3))
    ddex_market.set_quantization_param(QuantizationParams("WETH-DAI", 5, 3, 5, 3))

    market_pair = CrossExchangeMarketPair(*(
        [ddex_market] + list(ddex_trading_pair) + [binance_market] + list(binance_trading_pair)))

    strategy = CrossExchangeMarketMakingStrategy(
        [market_pair], 0.003,
        logging_options=
        CrossExchangeMarketMakingStrategy.OPTION_LOG_MAKER_ORDER_FILLED)

    clock = Clock(ClockMode.BACKTEST, start_time=start.timestamp(), end_time=end.timestamp())
    clock.add_iterator(binance_market)
    clock.add_iterator(ddex_market)
    clock.add_iterator(strategy)

    binance_market.set_balance("ETH", 10.0)
    binance_market.set_balance("USDT", 1000.0)
    ddex_market.set_balance("WETH", 10.0)
    ddex_market.set_balance("DAI", 1000.0)

    clock.backtest()
    binance_loader.close()
    ddex_loader.close()


if __name__ == "__main__":
    main()
