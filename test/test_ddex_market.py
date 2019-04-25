#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

import conf
import time
import asyncio
import logging
from decimal import Decimal
import unittest
from typing import List
from wings.clock import Clock, ClockMode
from wings.market.ddex_market import DDEXMarket
from wings.ethereum_chain import EthereumChain
from wings.events import (
    MarketEvent,
    WalletEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    WalletWrappedEthEvent,
    WalletUnwrappedEthEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    OrderFilledEvent,
    TradeType,
    TradeFee
)
from wings.event_logger import EventLogger
from wings.market.market_base import OrderType
from wings.order_book_tracker import OrderBookTrackerDataSourceType
from wings.wallet.web3_wallet import Web3Wallet


class DDEXMarketUnitTest(unittest.TestCase):
    market_events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.WithdrawAsset,
        MarketEvent.OrderFilled,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated
    ]

    wallet_events: List[WalletEvent] = [
        WalletEvent.WrappedEth,
        WalletEvent.UnwrappedEth
    ]

    wallet: Web3Wallet
    market: DDEXMarket
    market_logger: EventLogger
    wallet_logger: EventLogger

    @classmethod
    def setUpClass(cls):
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.wallet = Web3Wallet(private_key=conf.web3_test_private_key_ddex,
                                backend_urls=conf.test_ddex_web3_provider_list,
                                erc20_token_addresses=[conf.test_ddex_erc20_token_address_1,
                                                       conf.test_ddex_erc20_token_address_2],
                                chain=EthereumChain.MAIN_NET)
        cls.market: DDEXMarket = DDEXMarket(wallet=cls.wallet, web3_url=conf.test_ddex_web3_provider_list[0],
                                            order_book_tracker_data_source_type=
                                            OrderBookTrackerDataSourceType.EXCHANGE_API,
                                            symbols=["HOT-WETH"])
        print("Initializing DDEX market... ")
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.clock.add_iterator(cls.wallet)
        cls.clock.add_iterator(cls.market)
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
        self.wallet_logger = EventLogger()
        for event_tag in self.market_events:
            self.market.add_listener(event_tag, self.market_logger)
        for event_tag in self.wallet_events:
            self.wallet.add_listener(event_tag, self.wallet_logger)

    def tearDown(self):
        for event_tag in self.market_events:
            self.market.remove_listener(event_tag, self.market_logger)
        self.market_logger = None
        for event_tag in self.wallet_events:
            self.wallet.remove_listener(event_tag, self.wallet_logger)
        self.wallet_logger = None

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
        weth_trade_fee: TradeFee = self.market.get_fee("ZRX-WETH", OrderType.LIMIT, TradeType.BUY, 10000, 1)
        self.assertGreater(weth_trade_fee.percent, 0)
        self.assertEqual(len(weth_trade_fee.flat_fees), 1)
        self.assertEqual(weth_trade_fee.flat_fees[0][0], "WETH")
        dai_trade_fee: TradeFee = self.market.get_fee("WETH-DAI", OrderType.MARKET, TradeType.BUY, 10000)
        self.assertGreater(dai_trade_fee.percent, 0)
        self.assertEqual(len(dai_trade_fee.flat_fees), 1)
        self.assertEqual(dai_trade_fee.flat_fees[0][0], "DAI")

    def test_get_wallet_balances(self):
        balances = self.market.get_all_balances()
        self.assertGreaterEqual((balances["ETH"]), 0)
        self.assertGreaterEqual((balances["WETH"]), 0)

    def test_list_orders(self):
        [orders] = self.run_parallel(self.market.list_orders())
        self.assertGreaterEqual(len(orders), 0)

    def test_list_locked_balances(self):
        [locked_balances] = self.run_parallel(self.market.list_locked_balances())
        self.assertGreaterEqual(len(locked_balances), 0)

    @unittest.skipUnless(any("test_bad_orders_are_not_tracked" in arg for arg in sys.argv),
                         "bad_orders_are_not_tracked test requires manual action.")
    def test_bad_orders_are_not_tracked(self):
        # Should fail due to insufficient balance
        order_id = self.market.buy("WETH-DAI", 10000, OrderType.LIMIT, 1)
        self.assertEqual(self.market.in_flight_orders.get(order_id), None)

    def test_cancel_order(self):
        symbol = "HOT-WETH"
        bid_price: float = self.market.get_price(symbol, True)
        amount = 0.02 / bid_price

        # Intentionally setting invalid price to prevent getting filled
        client_order_id = self.market.buy(symbol, amount, OrderType.LIMIT, bid_price * 0.7)
        self.market.cancel(symbol, client_order_id)
        self.run_parallel(asyncio.sleep(5))
        self.assertEqual(self.market.in_flight_orders.get(client_order_id), None)

    def test_place_limit_buy_and_sell(self):
        self.assertGreater(self.market.get_balance("WETH"), 0.01)

        # Try to buy 0.01 WETH worth of HOT from the exchange, and watch for completion event.
        symbol = "HOT-WETH"
        bid_price: float = self.market.get_price(symbol, True)
        amount: float = 0.01 / bid_price
        buy_order_id: str = self.market.buy(symbol, amount, OrderType.LIMIT, bid_price * 0.7)
        self.run_parallel(asyncio.sleep(3))
        exchange_order_id: str = self.market.in_flight_orders.get(buy_order_id).exchange_order_id
        buy_order = self.run_parallel(self.market.get_order(exchange_order_id))
        self.assertEqual(buy_order[0].get('id'), exchange_order_id)
        self.market.cancel(symbol, buy_order_id)

        # Try to sell back the same amount of HOT to the exchange, and watch for completion event.
        ask_price: float = self.market.get_price(symbol, False)
        sell_order_id: str = self.market.sell(symbol, amount, OrderType.LIMIT, ask_price * 1.5)
        self.run_parallel(asyncio.sleep(3))
        exchange_order_id: str = self.market.in_flight_orders.get(sell_order_id).exchange_order_id
        sell_order = self.run_parallel(self.market.get_order(exchange_order_id))
        self.assertEqual(sell_order[0].get('id'), exchange_order_id)
        self.market.cancel(symbol, sell_order_id)

    @unittest.skipUnless(any("test_limit_buy_and_sell_get_matched" in arg for arg in sys.argv),
                         "test_limit_buy_and_sell_get_matched test requires manual action.")
    def test_limit_buy_and_sell_get_matched(self):
        self.assertGreater(self.market.get_balance("WETH"), 0.01)

        # Try to buy 0.01 WETH worth of HOT from the exchange, and watch for completion event.
        current_price: float = self.market.get_price("HOT-WETH", True)
        amount: float = 0.01 / current_price
        quantized_amount: Decimal = self.market.quantize_order_amount("HOT-WETH", amount)
        order_id = self.market.buy("HOT-WETH", amount, OrderType.LIMIT, current_price)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        order_filled_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in order_filled_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(float(quantized_amount), order_completed_event.base_asset_amount)
        self.assertEqual("HOT", order_completed_event.base_asset)
        self.assertEqual("WETH", order_completed_event.quote_asset)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                         for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

        # Try to sell back the same amount of HOT to the exchange, and watch for completion event.
        current_price: float = self.market.get_price("HOT-WETH", False)
        amount = float(order_completed_event.base_asset_amount)
        quantized_amount = order_completed_event.base_asset_amount
        order_id = self.market.sell("HOT-WETH", amount, OrderType.LIMIT, current_price)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        order_completed_event: SellOrderCompletedEvent = order_completed_event
        order_filled_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in order_filled_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(float(quantized_amount), order_completed_event.base_asset_amount)
        self.assertEqual("HOT", order_completed_event.base_asset)
        self.assertEqual("WETH", order_completed_event.quote_asset)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                        for event in self.market_logger.event_log]))

    def test_market_buy_and_sell(self):
        self.assertGreater(self.market.get_balance("WETH"), 0.01)

        amount: float = 30
        quantized_amount: Decimal = self.market.quantize_order_amount("HOT-WETH", amount)
        order_id = self.market.buy("HOT-WETH", amount, OrderType.MARKET)

        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        order_filled_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                       if isinstance(t, OrderFilledEvent)]

        self.assertTrue([evt.order_type == OrderType.MARKET for evt in order_filled_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(float(quantized_amount), order_completed_event.base_asset_amount)
        self.assertEqual("HOT", order_completed_event.base_asset)
        self.assertEqual("WETH", order_completed_event.quote_asset)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                         for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

        # Try to sell back the same amount of HOT to the exchange, and watch for completion event.
        amount = float(order_completed_event.base_asset_amount)
        quantized_amount = order_completed_event.base_asset_amount
        order_id = self.market.sell("HOT-WETH", amount, OrderType.MARKET)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        order_completed_event: SellOrderCompletedEvent = order_completed_event
        order_filled_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                       if isinstance(t, OrderFilledEvent)]

        self.assertTrue([evt.order_type == OrderType.MARKET for evt in order_filled_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(float(quantized_amount), order_completed_event.base_asset_amount)
        self.assertEqual("HOT", order_completed_event.base_asset)
        self.assertEqual("WETH", order_completed_event.quote_asset)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                         for event in self.market_logger.event_log]))

    @unittest.skipUnless(any("test_wrap_eth" in arg for arg in sys.argv), "Wrap Eth test requires manual action.")
    def test_wrap_eth(self):
        amount_to_wrap = 0.01
        tx_hash = self.wallet.wrap_eth(amount_to_wrap)
        [tx_completed_event] = self.run_parallel(self.wallet_logger.wait_for(WalletWrappedEthEvent))
        tx_completed_event: WalletWrappedEthEvent = tx_completed_event

        self.assertEqual(tx_hash, tx_completed_event.tx_hash)
        self.assertEqual(amount_to_wrap, tx_completed_event.amount)
        self.assertEqual(self.wallet.address, tx_completed_event.address)

    @unittest.skipUnless(any("test_unwrap_eth" in arg for arg in sys.argv), "Unwrap Eth test requires manual action.")
    def test_unwrap_eth(self):
        amount_to_unwrap = 0.01
        tx_hash = self.wallet.unwrap_eth(amount_to_unwrap)
        [tx_completed_event] = self.run_parallel(self.wallet_logger.wait_for(WalletUnwrappedEthEvent))
        tx_completed_event: WalletUnwrappedEthEvent = tx_completed_event

        self.assertEqual(tx_hash, tx_completed_event.tx_hash)
        self.assertEqual(amount_to_unwrap, tx_completed_event.amount)
        self.assertEqual(self.wallet.address, tx_completed_event.address)

    def test_cancel_all_happy_case(self):
        symbol = "HOT-WETH"
        bid_price: float = self.market.get_price(symbol, True)
        ask_price: float = self.market.get_price(symbol, False)
        amount = 0.02 / bid_price

        self.assertGreater(self.market.get_balance("WETH"), 0.02)
        self.assertGreater(self.market.get_balance("HOT"), amount)

        # Intentionally setting invalid price to prevent getting filled
        self.market.buy(symbol, amount, OrderType.LIMIT, bid_price * 0.7)
        self.market.sell(symbol, amount, OrderType.LIMIT, ask_price * 1.5)

        [cancellation_results] = self.run_parallel(self.market.cancel_all(10))
        print(cancellation_results)
        self.assertGreater(len(cancellation_results), 0)
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    def test_cancel_all_failure_case(self):
        symbol = "HOT-WETH"
        bid_price: float = self.market.get_price(symbol, True)
        ask_price: float = self.market.get_price(symbol, False)
        # order submission should fail due to insufficient balance
        amount = 100 / bid_price

        self.assertLess(self.market.get_balance("WETH"), 100)
        self.assertLess(self.market.get_balance("HOT"), amount)

        self.market.buy(symbol, amount, OrderType.LIMIT, bid_price * 0.7)
        self.market.sell(symbol, amount, OrderType.LIMIT, ask_price * 1.5)

        [cancellation_results] = self.run_parallel(self.market.cancel_all(10))
        print(cancellation_results)
        self.assertGreater(len(cancellation_results), 0)
        for cr in cancellation_results:
            self.assertEqual(cr.success, False)


def main():
    logging.basicConfig(level=logging.ERROR)
    unittest.main()


if __name__ == "__main__":
    main()
