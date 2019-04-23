#!/usr/bin/env python
import logging
from os.path import join, realpath
import sys;sys.path.insert(0, realpath(join(__file__, "../../")))

from wings.logger.struct_logger import METRICS_LOG_LEVEL

import asyncio
from decimal import Decimal
import time
from typing import List
import unittest

import conf
from wings.market.market_base import OrderType
from wings.market.coinbase_pro_market import CoinbaseProMarket
from wings.clock import (
    Clock,
    ClockMode
)
from wings.events import (
    MarketEvent,
    MarketReceivedAssetEvent,
    MarketWithdrawAssetEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    TradeFee
)
from wings.event_logger import EventLogger
from wings.wallet.web3_wallet import Web3Wallet
from wings.ethereum_chain import EthereumChain


logging.basicConfig(level=METRICS_LOG_LEVEL)


class CoinbaseProMarketUnitTest(unittest.TestCase):
    events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.WithdrawAsset,
        MarketEvent.OrderFilled,
        MarketEvent.OrderCancelled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated
    ]

    market: CoinbaseProMarket
    market_logger: EventLogger

    @classmethod
    def setUpClass(cls):
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: CoinbaseProMarket = CoinbaseProMarket(
            web3_url=conf.test_web3_provider_list[0],
            coinbase_pro_api_key=conf.coinbase_pro_api_key,
            coinbase_pro_secret_key=conf.coinbase_pro_secret_key,
            coinbase_pro_passphrase=conf.coinbase_pro_passphrase,
            symbols=["ETH-USDC", "ETH-USD"]
        )
        cls.wallet: Web3Wallet = Web3Wallet(private_key=conf.web3_private_key_coinbase_pro,
                                            backend_urls=conf.test_web3_provider_list,
                                            erc20_token_addresses=[conf.mn_weth_token_address,
                                                                   conf.mn_zerox_token_address],
                                            chain=EthereumChain.MAIN_NET)
        print("Initializing Coinbase Pro market... this will take about a minute.")
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.clock.add_iterator(cls.market)
        cls.clock.add_iterator(cls.wallet)
        cls.ev_loop.run_until_complete(cls.clock.run_til(time.time() + 1))
        cls.ev_loop.run_until_complete(cls.wait_til_ready())
        print("Ready.")

    @classmethod
    async def wait_til_ready(cls):
        while True:
            if cls.market.ready:
                break
            await asyncio.sleep(1.0)

    def setUp(self):
        self.market_logger = EventLogger()
        for event_tag in self.events:
            self.market.add_listener(event_tag, self.market_logger)

    def tearDown(self):
        for event_tag in self.events:
            self.market.remove_listener(event_tag, self.market_logger)
        self.market_logger = None

    async def run_parallel_async(self, *tasks):
        future: asyncio.Future = asyncio.ensure_future(asyncio.gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self.clock.run_til(next_iteration)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def test_get_fee(self):
        limit_fee: TradeFee = self.market.get_fee("ETH-USDC", OrderType.LIMIT, TradeType.BUY, 1, 1)
        self.assertGreater(limit_fee.percent, 0)
        self.assertEqual(len(limit_fee.flat_fees), 0)
        market_fee: TradeFee = self.market.get_fee("ETH-USDC", OrderType.MARKET, TradeType.BUY, 1)
        self.assertGreater(market_fee.percent, 0)
        self.assertEqual(len(market_fee.flat_fees), 0)

    def test_limit_buy(self):
        self.assertGreater(self.market.get_balance("ETH"), 0.1)
        symbol = "ETH-USDC"
        amount: float = 0.02
        quantized_amount: Decimal = self.market.quantize_order_amount(symbol, amount)

        current_bid_price: float = self.market.get_price(symbol, True)
        bid_price: float = current_bid_price + 0.05 * current_bid_price
        quantize_bid_price: Decimal = self.market.quantize_order_price(symbol, bid_price)

        order_id = self.market.buy(symbol, quantized_amount, OrderType.LIMIT, quantize_bid_price)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: float = sum(t.amount for t in trade_events)
        quote_amount_traded: float = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertAlmostEqual(float(quantized_amount), order_completed_event.base_asset_amount)
        self.assertEqual("ETH", order_completed_event.base_asset)
        self.assertEqual("USDC", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, float(order_completed_event.base_asset_amount))
        self.assertAlmostEqual(quote_amount_traded, float(order_completed_event.quote_asset_amount))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def test_limit_sell(self):
        symbol = "ETH-USDC"
        amount: float = 0.02
        quantized_amount: Decimal = self.market.quantize_order_amount(symbol, amount)
        current_ask_price: float = self.market.get_price(symbol, False)
        ask_price: float = current_ask_price - 0.05 * current_ask_price
        quantize_ask_price: Decimal = self.market.quantize_order_price(symbol, ask_price)

        order_id = self.market.sell(symbol, amount, OrderType.LIMIT, quantize_ask_price)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        order_completed_event: SellOrderCompletedEvent = order_completed_event
        trade_events = [t for t in self.market_logger.event_log if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertAlmostEqual(float(quantized_amount), order_completed_event.base_asset_amount)
        self.assertEqual("ETH", order_completed_event.base_asset)
        self.assertEqual("USDC", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, float(order_completed_event.base_asset_amount))
        self.assertAlmostEqual(quote_amount_traded, float(order_completed_event.quote_asset_amount))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    # NOTE that orders of non-USD pairs (including USDC pairs) are LIMIT only
    def test_market_buy(self):
        self.assertGreater(self.market.get_balance("ETH"), 0.1)
        symbol = "ETH-USD"
        amount: float = 0.02
        quantized_amount: Decimal = self.market.quantize_order_amount(symbol, amount)

        order_id = self.market.buy(symbol, quantized_amount, OrderType.MARKET, 0)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: float = sum(t.amount for t in trade_events)
        quote_amount_traded: float = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertAlmostEqual(float(quantized_amount), order_completed_event.base_asset_amount)
        self.assertEqual("ETH", order_completed_event.base_asset)
        self.assertEqual("USD", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, float(order_completed_event.base_asset_amount))
        self.assertAlmostEqual(quote_amount_traded, float(order_completed_event.quote_asset_amount))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    # NOTE that orders of non-USD pairs (including USDC pairs) are LIMIT only
    def test_market_sell(self):
        symbol = "ETH-USD"
        amount: float = 0.02
        quantized_amount: Decimal = self.market.quantize_order_amount(symbol, amount)

        order_id = self.market.sell(symbol, amount, OrderType.MARKET, 0)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        order_completed_event: SellOrderCompletedEvent = order_completed_event
        trade_events = [t for t in self.market_logger.event_log if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertAlmostEqual(float(quantized_amount), order_completed_event.base_asset_amount)
        self.assertEqual("ETH", order_completed_event.base_asset)
        self.assertEqual("USD", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, float(order_completed_event.base_asset_amount))
        self.assertAlmostEqual(quote_amount_traded, float(order_completed_event.quote_asset_amount))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def test_cancel_order(self):
        self.assertGreater(self.market.get_balance("ETH"), 10)
        symbol = "ETH-USDC"

        current_bid_price: float = self.market.get_price(symbol, True)
        amount: float = 10 / current_bid_price

        bid_price: float = current_bid_price - 0.1 * current_bid_price
        quantize_bid_price: Decimal = self.market.quantize_order_price(symbol, bid_price)
        quantized_amount: Decimal = self.market.quantize_order_amount(symbol, amount)

        client_order_id = self.market.buy(symbol, quantized_amount, OrderType.LIMIT, quantize_bid_price)
        self.market.cancel(symbol, client_order_id)
        [order_cancelled_event] = self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
        order_cancelled_event: OrderCancelledEvent = order_cancelled_event
        self.assertEqual(order_cancelled_event.order_id, client_order_id)

    def test_cancel_all(self):
        symbol = "ETH-USDC"
        bid_price: float = self.market.get_price(symbol, True) * 0.5
        ask_price: float = self.market.get_price(symbol, False) * 2
        amount: float = 10 / bid_price
        quantized_amount: Decimal = self.market.quantize_order_amount(symbol, amount)

        # Intentionally setting invalid price to prevent getting filled
        quantize_bid_price: Decimal = self.market.quantize_order_price(symbol, bid_price * 0.7)
        quantize_ask_price: Decimal = self.market.quantize_order_price(symbol, ask_price * 1.5)

        self.market.buy(symbol, quantized_amount, OrderType.LIMIT, quantize_bid_price)
        self.market.sell(symbol, quantized_amount, OrderType.LIMIT, quantize_ask_price)
        self.run_parallel(asyncio.sleep(1))
        [cancellation_results] = self.run_parallel(self.market.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    @unittest.skipUnless(any("test_list_orders" in arg for arg in sys.argv), "List order test requires manual action.")
    def test_list_orders(self):
        self.assertGreater(self.market.get_balance("ETH"), 0.1)
        symbol = "ETH-USDC"
        amount: float = 0.02
        quantized_amount: Decimal = self.market.quantize_order_amount(symbol, amount)

        current_bid_price: float = self.market.get_price(symbol, True)
        bid_price: float = current_bid_price + 0.05 * current_bid_price
        quantize_bid_price: Decimal = self.market.quantize_order_price(symbol, bid_price)

        self.market.buy(symbol, quantized_amount, OrderType.LIMIT, quantize_bid_price)
        self.run_parallel(asyncio.sleep(1))
        [order_details] = self.run_parallel(self.market.list_orders())
        self.assertGreaterEqual(len(order_details), 1)

        self.market_logger.clear()

    @unittest.skipUnless(any("test_deposit_eth" in arg for arg in sys.argv), "Deposit test requires manual action.")
    def test_deposit_eth(self):
        # Ensure the local wallet has enough balance for deposit testing.
        self.assertGreaterEqual(self.wallet.get_balance("ETH"), 0.02)

        # Deposit ETH to Binance, and wait.
        tracking_id: str = self.market.deposit(self.wallet, "ETH", 0.01)
        [received_asset_event] = self.run_parallel(
            self.market_logger.wait_for(MarketReceivedAssetEvent, timeout_seconds=1800)
        )
        received_asset_event: MarketReceivedAssetEvent = received_asset_event
        self.assertEqual("ETH", received_asset_event.asset_name)
        self.assertEqual(tracking_id, received_asset_event.tx_hash)
        self.assertEqual(self.wallet.address, received_asset_event.from_address)
        self.assertAlmostEqual(0.01, received_asset_event.amount_received)

    @unittest.skipUnless(any("test_deposit_zrx" in arg for arg in sys.argv), "Deposit test requires manual action.")
    def test_deposit_zrx(self):
        # Ensure the local wallet has enough balance for deposit testing.
        self.assertGreaterEqual(self.wallet.get_balance("ZRX"), 1)

        # Deposit ZRX to Coinbase Pro, and wait.
        tracking_id: str = self.market.deposit(self.wallet, "ZRX", 1)
        [received_asset_event] = self.run_parallel(
            self.market_logger.wait_for(MarketReceivedAssetEvent, timeout_seconds=1800)
        )
        received_asset_event: MarketReceivedAssetEvent = received_asset_event
        self.assertEqual("ZRX", received_asset_event.asset_name)
        self.assertEqual(tracking_id, received_asset_event.tx_hash)
        self.assertEqual(self.wallet.address, received_asset_event.from_address)
        self.assertEqual(1, received_asset_event.amount_received)

    @unittest.skipUnless(any("test_withdraw" in arg for arg in sys.argv), "Withdraw test requires manual action.")
    def test_withdraw(self):
        # Ensure the market account has enough balance for withdraw testing.
        self.assertGreaterEqual(self.market.get_balance("ZRX"), 1)

        # Withdraw ZRX from Coinbase Pro to test wallet.
        self.market.withdraw(self.wallet.address, "ZRX", 1)
        [withdraw_asset_event] = self.run_parallel(
            self.market_logger.wait_for(MarketWithdrawAssetEvent)
        )
        withdraw_asset_event: MarketWithdrawAssetEvent = withdraw_asset_event
        self.assertEqual(self.wallet.address, withdraw_asset_event.to_address)
        self.assertEqual("ZRX", withdraw_asset_event.asset_name)
        self.assertEqual(1, withdraw_asset_event.amount)
        self.assertEqual(withdraw_asset_event.fee_amount, 0)


if __name__ == "__main__":
    unittest.main()
