#!/usr/bin/env python
import faulthandler; faulthandler.enable()
import sys
import os; sys.path.insert(0, os.path.realpath(os.path.join(__file__, "../../")))
import logging; logging.basicConfig(level=logging.INFO)
import pandas as pd
import hummingsim
from hummingsim.backtest.backtest_market import BacktestMarket
from hummingsim.backtest.binance_order_book_loader_v2 import BinanceOrderBookLoaderV2
from hummingsim.backtest.ddex_order_book_loader import DDEXOrderBookLoader
from hummingsim.backtest.market import QuantizationParams
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingsim.backtest.market_config import (
    MarketConfig,
    AssetType
)
from hummingbot.strategy.arbitrage import (
    ArbitrageStrategy,
    ArbitrageMarketPair
)

# Define the data cache path.
hummingsim.set_data_path(os.path.join(os.environ["PWD"], "data"))

# Define the parameters for the backtest.
start = pd.Timestamp("2018-12-21-00:29:06", tz="UTC")
end = pd.Timestamp("2019-12-24-00:43:00", tz="UTC")
binance_trading_pair = ("ETHUSDT", "ETH", "USDT")
ddex_trading_pair = ("WETH-DAI", "WETH", "DAI")


binance_market = BacktestMarket()
ddex_market = BacktestMarket()
binance_loader = BinanceOrderBookLoaderV2(*binance_trading_pair)
ddex_loader = DDEXOrderBookLoader(*ddex_trading_pair)


binance_market.config = MarketConfig(AssetType.BASE_CURRENCY, 0.001, AssetType.QUOTE_CURRENCY, 0.001, {})
ddex_market.config = MarketConfig(AssetType.BASE_CURRENCY, 0.001, AssetType.QUOTE_CURRENCY, 0.001, {})

binance_market.add_data(binance_loader)
ddex_market.add_data(ddex_loader)

binance_market.set_quantization_param(QuantizationParams("ETHUSDT", 5, 3, 5, 3))
ddex_market.set_quantization_param(QuantizationParams("WETH-DAI", 5, 3, 5, 3))

market_pair1 = ArbitrageMarketPair(*([ddex_market] + list(ddex_trading_pair) + [binance_market] + list(binance_trading_pair)))

strategy = ArbitrageStrategy([market_pair1], 0.025,
                             logging_options=ArbitrageStrategy.OPTION_LOG_CREATE_ORDER)

clock = Clock(ClockMode.BACKTEST, start_time=start.timestamp(), end_time=end.timestamp())
clock.add_iterator(binance_market)
clock.add_iterator(ddex_market)
clock.add_iterator(strategy)


binance_market.set_balance("ETH", 100.0)
binance_market.set_balance("USDT", 10000.0)
ddex_market.set_balance("WETH", 100.0)
ddex_market.set_balance("DAI", 10000.0)

clock.backtest_til(start.timestamp() + 1)

ddex_weth_price = ddex_market.get_price("WETH-DAI", False)
binance_eth_price = binance_market.get_price("ETHUSDT", False)
start_ddex_portfolio_value = ddex_market.get_balance("DAI") + ddex_market.get_balance("WETH") * ddex_weth_price
start_binance_portfolio_value = binance_market.get_balance("USDT") + binance_market.get_balance("ETH") * binance_eth_price
print(f"start DDEX portfolio value: {start_ddex_portfolio_value}\n"
      f"start Binance portfolio value: {start_binance_portfolio_value}")

clock.backtest_til(end.timestamp())

ddex_weth_price = ddex_market.get_price("WETH-DAI", False)
binance_eth_price = binance_market.get_price("ETHUSDT", False)
ddex_portfolio_value = ddex_market.get_balance("DAI") + ddex_market.get_balance("WETH") * ddex_weth_price
binance_portfolio_value = binance_market.get_balance("USDT") + binance_market.get_balance("ETH") * binance_eth_price
print(f"DDEX portfolio value: {ddex_portfolio_value}\nBinance portfolio value: {binance_portfolio_value}\n")
print(f"DDEX balances: {ddex_market.get_all_balances()}\nBinance balances: {binance_market.get_all_balances()}")

print(f"start DDEX portfolio value: {start_ddex_portfolio_value}\n"
      f"start Binance portfolio value: {start_binance_portfolio_value}")

print(f"Profit DDEX {ddex_portfolio_value/start_ddex_portfolio_value}\n"
      f"Profit Binance {binance_portfolio_value/start_binance_portfolio_value}\n"
      f"Profit Total "
      f"{(ddex_portfolio_value + binance_portfolio_value)/(start_ddex_portfolio_value + start_binance_portfolio_value)}")
