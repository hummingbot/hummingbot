#!/usr/bin/env python

import sys, os; sys.path.insert(0, os.path.realpath(os.path.join(__file__, "../../")))
import logging; logging.basicConfig(level=logging.DEBUG)

import pandas as pd

import hummingsim
from hummingbot.strategy.pure_market_making import ConstantMultipleSpreadPricingDelegate, StaggeredMultipleSizeSizingDelegate
from hummingsim.backtest.backtest_market import BacktestMarket
from hummingsim.backtest.binance_order_book_loader_v2 import BinanceOrderBookLoaderV2
from hummingsim.backtest.market import QuantizationParams
from hummingbot.strategy.pure_market_making.data_types import *
from hummingsim.backtest.market_config import (
    MarketConfig,
    AssetType
)
from hummingsim.backtest.ddex_order_book_loader import DDEXOrderBookLoader
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.strategy.pure_market_making import (
    PureMarketMakingStrategyV2,
    PureMarketPair,
)


def main():
    # Define the data cache path.
    hummingsim.set_data_path(os.path.join(os.environ["PWD"], "data"))

    # Define the parameters for the backtest.
    start = pd.Timestamp("2019-01-01", tz="UTC")
    end = pd.Timestamp("2019-01-02", tz="UTC")
    binance_symbol = ("ETHUSDT", "ETH", "USDT")
    #ddex_symbol = ("WETH-DAI", "WETH", "DAI")
    equal_strategy_sizing_delegate = StaggeredMultipleSizeSizingDelegate(order_start_size=1.0,
                                                                              order_step_size=0,
                                                                              number_of_orders=5)
    staggered_strategy_sizing_delegate = StaggeredMultipleSizeSizingDelegate(order_start_size=1.0,
                                                                                  order_step_size=0.5,
                                                                                  number_of_orders=5)

    binance_market = BacktestMarket()
    ddex_market = BacktestMarket()
    binance_market.config = MarketConfig(AssetType.BASE_CURRENCY, 0.001, AssetType.QUOTE_CURRENCY, 0.001, {})
    ddex_market.config = MarketConfig(AssetType.BASE_CURRENCY, 0.001, AssetType.QUOTE_CURRENCY, 0.001, {})
    binance_loader = BinanceOrderBookLoaderV2(*binance_symbol)
    #ddex_loader = DDEXOrderBookLoader(*ddex_symbol)

    binance_market.add_data(binance_loader)
    #ddex_market.add_data(ddex_loader)

    binance_market.set_quantization_param(QuantizationParams("ETHUSDT", 5, 3, 5, 3))
    #ddex_market.set_quantization_param(QuantizationParams("WETH-DAI", 5, 3, 5, 3))

    market_pair = MarketInfo(market=binance_market, symbol="ETHUSDT", base_currency="ETH", quote_currency="USDT")
    strategy: PureMarketMakingStrategyV2 = PureMarketMakingStrategyV2(
        [market_pair],
        legacy_order_size=50000,
        legacy_bid_spread=0.003,
        legacy_ask_spread=0.003,
        cancel_order_wait_time=45
    )

    clock = Clock(ClockMode.BACKTEST, tick_size=60,
                  start_time=start.timestamp(), end_time=end.timestamp() )
    clock.add_iterator(binance_market)
    #clock.add_iterator(ddex_market)
    clock.add_iterator(strategy)

    binance_market.set_balance("ETH", 100000.0)
    binance_market.set_balance("USDT", 100000000.0)
    ddex_market.set_balance("WETH", 100000.0)
    ddex_market.set_balance("DAI", 1000.0)

    current = start.timestamp()
    step = 60

    while current <= end.timestamp():

        current += step
        clock.backtest_til(current)
        print("clock ticked")



    binance_loader.close()
    #ddex_loader.close()


if __name__ == "__main__":
    main()
