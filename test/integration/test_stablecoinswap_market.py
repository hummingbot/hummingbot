#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

import asyncio
import conf
import contextlib
from decimal import Decimal
import logging
import os
import time
from typing import (
    List,
    Optional
)
import unittest

from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent,
    WalletEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    WalletWrappedEthEvent,
    WalletUnwrappedEthEvent,
    OrderCancelledEvent,
    OrderExpiredEvent,
    OrderFilledEvent,
    TradeType,
    TradeFee,
)
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger import NETWORK
from hummingbot.market.market_base import OrderType
from hummingbot.market.markets_recorder import MarketsRecorder
from hummingbot.market.stablecoinswap.stablecoinswap_market import StablecoinswapMarket
import hummingbot.market.stablecoinswap.stablecoinswap_contracts as stablecoinswap_contracts
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType
)
from hummingbot.model.trade_fill import TradeFill
from hummingbot.wallet.ethereum.web3_wallet import Web3Wallet
from hummingbot.wallet.ethereum.web3_wallet_backend import EthereumChain

s_decimal_0 = Decimal(0)


class StablecoinswapMarketUnitTest(unittest.TestCase):
    market_events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled,
        MarketEvent.OrderExpired,
        MarketEvent.OrderFilled,
        MarketEvent.WithdrawAsset,
    ]

    wallet: Web3Wallet
    market: StablecoinswapMarket
    market_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.wallet = Web3Wallet(private_key=conf.web3_private_key_stablecoinswap,
                                backend_urls=conf.test_web3_provider_list,
                                erc20_token_addresses=[
                                    stablecoinswap_contracts.DAI_ADDRESS,
                                    stablecoinswap_contracts.USDC_ADDRESS
                                    ],
                                chain=EthereumChain.MAIN_NET)
        cls.market: StablecoinswapMarket = StablecoinswapMarket(
            wallet=cls.wallet,
            ethereum_rpc_url=conf.test_web3_provider_list[0],
            symbols=["DAI-USDC"]
        )
        print("Initializing Stablecoinswap market... ")
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.clock.add_iterator(cls.wallet)
        cls.clock.add_iterator(cls.market)
        cls.stack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_til_ready())
        print("Ready.")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stack.close()

    @classmethod
    async def wait_til_ready(cls):
        while True:
            now = time.time()
            next_iteration = now // 1.0 + 1
            if cls.market.ready:
                break
            else:
                await cls._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)

    def setUp(self):
        self.db_path: str = realpath(join(__file__, "../stablecoinswap_test.sqlite"))
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

        self.market_logger = EventLogger()
        for event_tag in self.market_events:
            self.market.add_listener(event_tag, self.market_logger)

    def tearDown(self):
        for event_tag in self.market_events:
            self.market.remove_listener(event_tag, self.market_logger)
        self.market_logger = None

    async def run_parallel_async(self, *tasks):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def test_get_fee(self):
        taker_buy_trade_fee: TradeFee = self.market.get_fee("DAI", "USDC", OrderType.MARKET, TradeType.BUY, Decimal(20))
        self.assertEqual(taker_buy_trade_fee.percent, Decimal('0.001'))
        self.assertEqual(len(taker_buy_trade_fee.flat_fees), 1)
        self.assertEqual(taker_buy_trade_fee.flat_fees[0][0], "ETH")

    def test_get_wallet_balances(self):
        balances = self.market.get_all_balances()
        self.assertGreaterEqual((balances["DAI"]), s_decimal_0)
        self.assertGreaterEqual((balances["USDC"]), s_decimal_0)

    def test_market_sell(self):
        amount: Decimal = Decimal("2.53")
        quantized_amount: Decimal = self.market.quantize_order_amount("DAI-USDC", amount)
        order_id = self.market.sell("DAI-USDC", amount, OrderType.MARKET)

        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        order_completed_event: SellOrderCompletedEvent = order_completed_event
        order_filled_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                       if isinstance(t, OrderFilledEvent)]

        self.assertTrue([evt.order_type == OrderType.MARKET for evt in order_filled_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("DAI", order_completed_event.base_asset)
        self.assertEqual("USDC", order_completed_event.quote_asset)
        self.market_logger.clear()

    def test_market_buy(self):
        amount: Decimal = Decimal("2.5354")
        quantized_amount: Decimal = self.market.quantize_order_amount("DAI-USDC", amount)
        order_id = self.market.buy("DAI-USDC", amount, OrderType.MARKET)

        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        order_filled_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                       if isinstance(t, OrderFilledEvent)]

        self.assertTrue([evt.order_type == OrderType.MARKET for evt in order_filled_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(quantized_amount.quantize(Decimal("0.001")),
                order_completed_event.base_asset_amount.quantize(
                    Decimal("0.001")))
        self.assertEqual("DAI", order_completed_event.base_asset)
        self.assertEqual("USDC", order_completed_event.quote_asset)
        self.market_logger.clear()

    def test_order_fill_record(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        symbol: str = "DAI-USDC"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            # Try to buy 0.5 DAI worth of USDC, and watch for completion event.
            current_price: Decimal = self.market.get_price(symbol, True)
            amount: Decimal = Decimal("0.5") / current_price
            order_id = self.market.buy(symbol, amount)
            [buy_order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))

            # Reset the logs
            self.market_logger.clear()

            # Try to sell back the same amount of DAI to the exchange, and watch for completion event.
            amount = Decimal(buy_order_completed_event.base_asset_amount)
            order_id = self.market.sell(symbol, amount)
            [sell_order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))

            # Query the persisted trade logs
            trade_fills: List[TradeFill] = recorder.get_trades_for_config(config_path)
            self.assertEqual(2, len(trade_fills))
            buy_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "BUY"]
            sell_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "SELL"]
            self.assertEqual(1, len(buy_fills))
            self.assertEqual(1, len(sell_fills))

            order_id = None

        finally:
            recorder.stop()
            os.unlink(self.db_path)


def main():
    logging.basicConfig(level=NETWORK)
    unittest.main()


if __name__ == "__main__":
    main()

