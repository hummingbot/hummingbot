#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))
import logging

import pandas as pd

from hummingsim.backtest.backtest_market import BacktestMarket
from hummingsim.backtest.binance_order_book_loader_v2 import BinanceOrderBookLoaderV2
from hummingsim.backtest.ddex_order_book_loader import DDEXOrderBookLoader
from hummingsim.backtest.bittrex_order_book_loader import BittrexOrderBookLoader
from hummingsim.backtest.huobi_order_book_loader import HuobiOrderBookLoader
from hummingsim.backtest.market import Market
from wings.clock import (
    ClockMode,
    Clock
)
from hummingsim.strategy.print_out_strategy import PrintOutStrategy, PrintOutStrategy2


def binance_printout():
    ethusdt_data: BinanceOrderBookLoaderV2 = BinanceOrderBookLoaderV2("ETHUSDT", "ETH", "USDT")
    eoseth_data: BinanceOrderBookLoaderV2 = BinanceOrderBookLoaderV2("EOSETH", "EOS", "ETH")
    trxeth_data: BinanceOrderBookLoaderV2 = BinanceOrderBookLoaderV2("TRXETH", "TRX", "ETH")
    market: Market = BacktestMarket()
    market.add_data(ethusdt_data, eoseth_data, trxeth_data)
    market.set_balance("ETH", 20.0)
    market.set_balance("EOS", 0.0)
    market.set_balance("TRX", 0.0)
    print("Beginning Balance:", market.get_all_balances())
    start: pd.Timestamp = pd.Timestamp("2018-12-03", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2018-12-04", tz="UTC")
    clock: Clock = Clock(ClockMode.BACKTEST, 600.0, start.timestamp(), end.timestamp())
    #clock: Clock = Clock(ClockMode.BACKTEST, 1.0, start.timestamp(), end.timestamp())

    print_out_strategy: PrintOutStrategy2 = PrintOutStrategy2(market)
    clock.add_iterator(market)
    clock.add_iterator(print_out_strategy)
    clock.backtest()

    print("End Balance:", market.get_all_balances())
    ethusdt_data.close()
    eoseth_data.close()
    trxeth_data.close()


def huobi_printout():
    ethusdt_data: HuobiOrderBookLoader = HuobiOrderBookLoader("ethusdt", "ETH", "USDT")
    eoseth_data: HuobiOrderBookLoader = HuobiOrderBookLoader("eoseth", "EOS", "ETH")
    trxeth_data: HuobiOrderBookLoader = HuobiOrderBookLoader("trxeth", "TRX", "ETH")
    market: Market = BacktestMarket()
    market.add_data(ethusdt_data, eoseth_data, trxeth_data)
    market.set_balance("ETH", 20.0)
    market.set_balance("EOS", 0.0)
    market.set_balance("TRX", 0.0)
    print("Beginning Balance:", market.get_all_balances())

    start: pd.Timestamp = pd.Timestamp("2018-12-09", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2018-12-10", tz="UTC")
    clock: Clock = Clock(ClockMode.BACKTEST, 600.0, start.timestamp(), end.timestamp())

    print_out_strategy: PrintOutStrategy2 = PrintOutStrategy2(market)
    clock.add_iterator(market)
    clock.add_iterator(print_out_strategy)
    clock.backtest()

    print("End Balance:", market.get_all_balances())
    ethusdt_data.close()
    eoseth_data.close()
    trxeth_data.close()


def bittrex_printout():
    ethusdt_data: BittrexOrderBookLoader = BittrexOrderBookLoader("USDT-ETH", "ETH", "USDT")
    trxeth_data: BittrexOrderBookLoader = BittrexOrderBookLoader("ETH-TRX", "TRX", "ETH")
    market: Market = BacktestMarket()
    market.add_data(trxeth_data)
    market.add_data(ethusdt_data)
    market.set_balance("ETH", 20.0)
    market.set_balance("TRX", 0.0)
    print("Beginning Balance:", market.get_all_balances())

    start: pd.Timestamp = pd.Timestamp("2018-12-11", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2018-12-12", tz="UTC")
    clock: Clock = Clock(ClockMode.BACKTEST, 600.0, start.timestamp(), end.timestamp())

    print_out_strategy: PrintOutStrategy2 = PrintOutStrategy2(market)
    clock.add_iterator(market)
    clock.add_iterator(print_out_strategy)
    clock.backtest()

    print("End Balance:", market.get_all_balances())
    ethusdt_data.close()
    trxeth_data.close()


def ddex_printout():
    wethdai_data: DDEXOrderBookLoader = DDEXOrderBookLoader("WETH-DAI", "WETH", "DAI")
    market: Market = BacktestMarket()
    market.add_data(wethdai_data)

    market.set_balance("ETH", 20.0)

    print("Beginning Balance:", market.get_all_balances())

    start: pd.Timestamp = pd.Timestamp("2018-12-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2018-12-02", tz="UTC")
    clock: Clock = Clock(ClockMode.BACKTEST, 600.0, start.timestamp(), end.timestamp())

    print_out_strategy: PrintOutStrategy2 = PrintOutStrategy2(market)
    clock.add_iterator(market)
    clock.add_iterator(print_out_strategy)
    clock.backtest()

    print("End Balance:", market.get_all_balances())

    wethdai_data.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    huobi_printout()

