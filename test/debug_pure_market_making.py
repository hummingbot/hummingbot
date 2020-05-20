#!/usr/bin/env python

import sys, os; sys.path.insert(0, os.path.realpath(os.path.join(__file__, "../../")))
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
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.strategy.pure_market_making import (
    PureMarketMakingStrategy,
    PureMarketPair,
)


def main():
    # Define the data cache path.
    hummingsim.set_data_path(os.path.join(os.environ["PWD"], "data"))

    # Define the parameters for the backtest.
    start = pd.Timestamp("2019-01-01", tz="UTC")
    end = pd.Timestamp("2019-01-02", tz="UTC")
    binance_trading_pair = ("ETHUSDT", "ETH", "USDT")

    binance_market = BacktestMarket()
    binance_market.config = MarketConfig(AssetType.BASE_CURRENCY, 0.001, AssetType.QUOTE_CURRENCY, 0.001, {})
    binance_loader = BinanceOrderBookLoaderV2(*binance_trading_pair)

    binance_market.add_data(binance_loader)

    binance_market.set_quantization_param(QuantizationParams("ETHUSDT", 5, 3, 5, 3))

    market_pair = PureMarketPair(*([binance_market] + list(binance_trading_pair)))
    strategy = PureMarketMakingStrategy([market_pair],
                                        order_size = 50000,
                                        bid_place_threshold = 0.003,
                                        ask_place_threshold = 0.003,
                                        logging_options = PureMarketMakingStrategy.OPTION_LOG_ALL)

    clock = Clock(ClockMode.BACKTEST, tick_size=60,
                  start_time=start.timestamp(), end_time=end.timestamp() )
    clock.add_iterator(binance_market)
    clock.add_iterator(strategy)

    binance_market.set_balance("ETH", 100000.0)
    binance_market.set_balance("USDT", 100000000.0)

    current = start.timestamp()
    step = 60

    while current <= end.timestamp():

        current += step
        clock.backtest_til(current)
        print("clock ticked")



    binance_loader.close()



if __name__ == "__main__":
    main()