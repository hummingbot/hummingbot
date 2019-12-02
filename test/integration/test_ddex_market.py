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
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent,
    WalletEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    WalletWrappedEthEvent,
    WalletUnwrappedEthEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    TradeType,
    TradeFee
)
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.market.ddex.ddex_market import DDEXMarket
from hummingbot.market.market_base import OrderType
from hummingbot.market.markets_recorder import MarketsRecorder
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType
)
from hummingbot.model.trade_fill import TradeFill
from hummingbot.wallet.ethereum.ethereum_chain import EthereumChain
from hummingbot.wallet.ethereum.web3_wallet import Web3Wallet

s_decimal_0 = Decimal(0)


class DDEXMarketUnitTest(unittest.TestCase):
    market_events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.WithdrawAsset,
        MarketEvent.OrderFilled,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled
    ]

    wallet_events: List[WalletEvent] = [
        WalletEvent.WrappedEth,
        WalletEvent.UnwrappedEth
    ]

    wallet: Web3Wallet
    market: DDEXMarket
    market_logger: EventLogger
    wallet_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.wallet = Web3Wallet(private_key=conf.web3_test_private_key_ddex,
                                backend_urls=conf.test_ddex_web3_provider_list,
                                erc20_token_addresses=[conf.test_ddex_erc20_token_address_1,
                                                       conf.test_ddex_erc20_token_address_2,
                                                       conf.test_ddex_erc20_token_address_3,
                                                       ],
                                chain=EthereumChain.MAIN_NET)
        cls.market: DDEXMarket = DDEXMarket(wallet=cls.wallet,
                                            ethereum_rpc_url=conf.test_ddex_web3_provider_list[0],
                                            order_book_tracker_data_source_type=OrderBookTrackerDataSourceType.EXCHANGE_API,
                                            trading_pairs=["HOT-WETH", "WETH-SAI"])
        print("Initializing DDEX market... ")
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
        self.db_path: str = realpath(join(__file__, "../ddex_test.sqlite"))
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

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
        weth_trade_fee: TradeFee = self.market.get_fee("ZRX", "WETH", OrderType.LIMIT, TradeType.BUY, Decimal(10000), Decimal(1))
        self.assertGreater(weth_trade_fee.percent, 0)
        self.assertEqual(len(weth_trade_fee.flat_fees), 1)
        self.assertEqual(weth_trade_fee.flat_fees[0][0], "WETH")
        dai_trade_fee: TradeFee = self.market.get_fee("WETH", "SAI", OrderType.MARKET, TradeType.BUY, Decimal(10000))
        self.assertGreater(dai_trade_fee.percent, 0)
        self.assertEqual(len(dai_trade_fee.flat_fees), 1)
        self.assertEqual(dai_trade_fee.flat_fees[0][0], "SAI")

    def test_get_wallet_balances(self):
        balances = self.market.get_all_balances()
        self.assertGreaterEqual((balances["ETH"]), s_decimal_0)
        self.assertGreaterEqual((balances["WETH"]), s_decimal_0)

    def test_get_available_balances(self):
        balance = self.market.get_available_balance("ETH")
        self.assertGreaterEqual(balance, s_decimal_0)

    def test_list_orders(self):
        [orders] = self.run_parallel(self.market.list_orders())
        self.assertGreaterEqual(len(orders), 0)

    def test_list_locked_balances(self):
        [locked_balances] = self.run_parallel(self.market.list_locked_balances())
        self.assertGreaterEqual(len(locked_balances), s_decimal_0)

    @unittest.skipUnless(any("test_bad_orders_are_not_tracked" in arg for arg in sys.argv),
                         "bad_orders_are_not_tracked test requires manual action.")
    def test_bad_orders_are_not_tracked(self):
        # Should fail due to insufficient balance
        order_id = self.market.buy("WETH-SAI", Decimal("10000"), OrderType.LIMIT, Decimal(1))
        self.assertEqual(self.market.in_flight_orders.get(order_id), None)

    def test_cancel_order(self):
        trading_pair = "HOT-WETH"
        bid_price: Decimal = self.market.get_price(trading_pair, True)
        amount = 2000

        # Intentionally setting invalid price to prevent getting filled
        client_order_id = self.market.buy(trading_pair, amount, OrderType.LIMIT, bid_price * Decimal("0.7"))
        self.market.cancel(trading_pair, client_order_id)
        [order_cancelled_event] = self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
        order_cancelled_event: OrderCancelledEvent = order_cancelled_event

        self.run_parallel(asyncio.sleep(6.0))
        self.assertEqual(0, len(self.market.limit_orders))
        self.assertEqual(client_order_id, order_cancelled_event.order_id)

    def test_place_limit_buy_and_sell(self):
        self.assertGreater(self.market.get_balance("WETH"), Decimal("0.1"))
        self.assertGreater(self.market.get_balance("HOT"), 2000)

        # Try to buy 2000 HOT from the exchange, and watch for completion event.
        trading_pair = "HOT-WETH"
        bid_price: Decimal = self.market.get_price(trading_pair, True)
        amount: Decimal = 2000
        buy_order_id: str = self.market.buy(trading_pair, amount, OrderType.LIMIT, bid_price * Decimal("0.7"))
        [buy_order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        exchange_order_id: str = self.market.in_flight_orders.get(buy_order_id).exchange_order_id
        buy_order = self.run_parallel(self.market.get_order(exchange_order_id))
        self.assertEqual(buy_order[0].get('id'), exchange_order_id)
        self.assertEqual(buy_order_id, buy_order_created_event.order_id)
        self.market.cancel(trading_pair, buy_order_id)
        [_] = self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

        # Try to sell back the same amount of HOT to the exchange, and watch for completion event.
        ask_price: Decimal = self.market.get_price(trading_pair, False)
        sell_order_id: str = self.market.sell(trading_pair, amount, OrderType.LIMIT, ask_price * Decimal("1.5"))
        [sell_order_created_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))
        exchange_order_id: str = self.market.in_flight_orders.get(sell_order_id).exchange_order_id
        sell_order = self.run_parallel(self.market.get_order(exchange_order_id))
        self.assertEqual(sell_order[0].get('id'), exchange_order_id)
        self.assertEqual(sell_order_id, sell_order_created_event.order_id)
        self.market.cancel(trading_pair, sell_order_id)
        [_] = self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

    @unittest.skipUnless(any("test_limit_buy_and_sell_get_matched" in arg for arg in sys.argv),
                         "test_limit_buy_and_sell_get_matched test requires manual action.")
    def test_limit_buy_and_sell_get_matched(self):
        self.assertGreater(self.market.get_balance("WETH"), Decimal("0.01"))

        # Try to buy 0.01 WETH worth of HOT from the exchange, and watch for completion event.
        current_price: Decimal = self.market.get_price("HOT-WETH", True)
        amount: Decimal = 2000
        quantized_amount: Decimal = self.market.quantize_order_amount("HOT-WETH", amount)
        order_id = self.market.buy("HOT-WETH", amount, OrderType.LIMIT, Decimal(current_price))
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        order_filled_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                       if isinstance(t, OrderFilledEvent)]

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in order_filled_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("HOT", order_completed_event.base_asset)
        self.assertEqual("WETH", order_completed_event.quote_asset)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

        # Try to sell back the same amount of HOT to the exchange, and watch for completion event.
        current_price: Decimal = self.market.get_price("HOT-WETH", False)
        amount = Decimal(order_completed_event.base_asset_amount)
        quantized_amount = order_completed_event.base_asset_amount
        order_id = self.market.sell("HOT-WETH", amount, OrderType.LIMIT, current_price)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        order_completed_event: SellOrderCompletedEvent = order_completed_event
        order_filled_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                       if isinstance(t, OrderFilledEvent)]

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in order_filled_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("HOT", order_completed_event.base_asset)
        self.assertEqual("WETH", order_completed_event.quote_asset)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                        for event in self.market_logger.event_log]))

    def test_market_buy_and_sell(self):
        self.assertGreater(self.market.get_balance("SAI"), Decimal("40"))

        market_symbol: str = "WETH-SAI"
        amount: Decimal = Decimal("0.1")  # Min order size is 0.05 WETH
        quantized_amount: Decimal = self.market.quantize_order_amount(market_symbol, amount)

        order_id = self.market.buy(market_symbol, amount, OrderType.MARKET)

        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        order_filled_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                       if isinstance(t, OrderFilledEvent)]

        self.assertTrue(all([evt.order_type == OrderType.MARKET for evt in order_filled_events]))
        self.assertEqual(order_id, order_completed_event.order_id)

        # This is because some of the tokens are deducted in the trading fees.
        self.assertTrue(
            quantized_amount > order_completed_event.base_asset_amount > quantized_amount * Decimal("0.85")
        )
        self.assertEqual("WETH", order_completed_event.base_asset)
        self.assertEqual("SAI", order_completed_event.quote_asset)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

        # Try to sell back the same amount of HOT to the exchange, and watch for completion event.
        amount = Decimal(order_completed_event.base_asset_amount)
        quantized_amount: Decimal = self.market.quantize_order_amount(market_symbol, amount)
        order_id = self.market.sell(market_symbol, amount, OrderType.MARKET)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        order_completed_event: SellOrderCompletedEvent = order_completed_event
        order_filled_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                       if isinstance(t, OrderFilledEvent)]

        self.assertTrue(all([evt.order_type == OrderType.MARKET for evt in order_filled_events]))
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("WETH", order_completed_event.base_asset)
        self.assertEqual("SAI", order_completed_event.quote_asset)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))

    @unittest.skipUnless(any("test_wrap_eth" in arg for arg in sys.argv), "Wrap Eth test requires manual action.")
    def test_wrap_eth(self):
        amount_to_wrap = Decimal("0.01")
        tx_hash = self.wallet.wrap_eth(amount_to_wrap)
        [tx_completed_event] = self.run_parallel(self.wallet_logger.wait_for(WalletWrappedEthEvent))
        tx_completed_event: WalletWrappedEthEvent = tx_completed_event

        self.assertEqual(tx_hash, tx_completed_event.tx_hash)
        self.assertEqual(amount_to_wrap, tx_completed_event.amount)
        self.assertEqual(self.wallet.address, tx_completed_event.address)

    @unittest.skipUnless(any("test_unwrap_eth" in arg for arg in sys.argv), "Unwrap Eth test requires manual action.")
    def test_unwrap_eth(self):
        amount_to_unwrap = Decimal("0.01")
        tx_hash = self.wallet.unwrap_eth(amount_to_unwrap)
        [tx_completed_event] = self.run_parallel(self.wallet_logger.wait_for(WalletUnwrappedEthEvent))
        tx_completed_event: WalletUnwrappedEthEvent = tx_completed_event

        self.assertEqual(tx_hash, tx_completed_event.tx_hash)
        self.assertEqual(amount_to_unwrap, tx_completed_event.amount)
        self.assertEqual(self.wallet.address, tx_completed_event.address)

    def test_cancel_all_happy_case(self):
        trading_pair = "HOT-WETH"
        bid_price: Decimal = self.market.get_price(trading_pair, True)
        ask_price: Decimal = self.market.get_price(trading_pair, False)
        amount = 2000

        self.assertGreater(self.market.get_balance("WETH"), Decimal("0.02"))
        self.assertGreater(self.market.get_balance("HOT"), amount)

        # Intentionally setting invalid price to prevent getting filled
        self.market.buy(trading_pair, amount, OrderType.LIMIT, bid_price * Decimal("0.7"))
        self.market.sell(trading_pair, amount, OrderType.LIMIT, ask_price * Decimal("1.5"))

        [cancellation_results] = self.run_parallel(self.market.cancel_all(10))
        self.assertGreater(len(cancellation_results), 0)
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    def test_cancel_all_failure_case(self):
        trading_pair = "HOT-WETH"
        bid_price: Decimal = self.market.get_price(trading_pair, True)
        ask_price: Decimal = self.market.get_price(trading_pair, False)
        # order submission should fail due to insufficient balance
        amount = Decimal(200000)

        self.assertLess(self.market.get_balance("WETH"), 100)
        self.assertLess(self.market.get_balance("HOT"), amount)

        self.market.buy(trading_pair, amount, OrderType.LIMIT, bid_price * Decimal("0.7"))
        self.market.sell(trading_pair, amount, OrderType.LIMIT, ask_price * Decimal("1.5"))

        [cancellation_results] = self.run_parallel(self.market.cancel_all(10))
        self.assertGreater(len(cancellation_results), 0)
        for cr in cancellation_results:
            self.assertEqual(cr.success, False)

    def test_orders_saving_and_restoration(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        trading_pair: str = "WETH-SAI"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            self.assertEqual(0, len(self.market.tracking_states))

            # Try to put limit buy order for 0.1 ETH, and watch for order creation event.
            current_bid_price: Decimal = self.market.get_price(trading_pair, True)
            bid_price: Decimal = current_bid_price * Decimal("0.8")
            quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price)

            amount: Decimal = Decimal("0.1")
            quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

            order_id = self.market.buy(trading_pair, quantized_amount, OrderType.LIMIT, quantize_bid_price)
            [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
            order_created_event: BuyOrderCreatedEvent = order_created_event
            self.assertEqual(order_id, order_created_event.order_id)

            # Verify tracking states
            self.assertEqual(1, len(self.market.tracking_states))
            self.assertEqual(order_id, list(self.market.tracking_states.keys())[0])

            # Verify orders from recorder
            recorded_orders: List[Order] = recorder.get_orders_for_config_and_market(config_path, self.market)
            self.assertEqual(1, len(recorded_orders))
            self.assertEqual(order_id, recorded_orders[0].id)

            # Verify saved market states
            saved_market_states: MarketState = recorder.get_market_states(config_path, self.market)
            self.assertIsNotNone(saved_market_states)
            self.assertIsInstance(saved_market_states.saved_state, dict)
            self.assertGreater(len(saved_market_states.saved_state), 0)

            # Close out the current market and start another market.
            self.clock.remove_iterator(self.market)
            for event_tag in self.market_events:
                self.market.remove_listener(event_tag, self.market_logger)

            self.market: DDEXMarket = DDEXMarket(
                wallet=self.wallet,
                ethereum_rpc_url=conf.test_ddex_web3_provider_list[0],
                order_book_tracker_data_source_type=OrderBookTrackerDataSourceType.EXCHANGE_API,
                trading_pairs=[trading_pair]
            )
            for event_tag in self.market_events:
                self.market.add_listener(event_tag, self.market_logger)
            recorder.stop()
            recorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
            recorder.start()
            saved_market_states = recorder.get_market_states(config_path, self.market)
            self.clock.add_iterator(self.market)
            self.assertEqual(0, len(self.market.limit_orders))
            self.assertEqual(0, len(self.market.tracking_states))
            self.market.restore_tracking_states(saved_market_states.saved_state)
            self.assertEqual(1, len(self.market.limit_orders))
            self.assertEqual(1, len(self.market.tracking_states))

            # Cancel the order and verify that the change is saved.
            self.market.cancel(trading_pair, order_id)
            self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
            order_id = None
            self.assertEqual(0, len(self.market.limit_orders))
            self.assertEqual(1, len(self.market.tracking_states))
            saved_market_states = recorder.get_market_states(config_path, self.market)
            self.assertEqual(1, len(saved_market_states.saved_state))
        finally:
            if order_id is not None:
                self.market.cancel(trading_pair, order_id)
                self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            os.unlink(self.db_path)

    def test_order_fill_record(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        trading_pair: str = "WETH-SAI"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            # Try to buy 0.1 WETH from the exchange, and watch for completion event.
            amount: Decimal = Decimal("0.1")
            order_id = self.market.buy(trading_pair, amount)
            [buy_order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))

            # Reset the logs
            self.market_logger.clear()

            # Try to sell back the same amount of WETH to the exchange, and watch for completion event.
            amount = buy_order_completed_event.base_asset_amount
            order_id = self.market.sell(trading_pair, amount)
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
            if order_id is not None:
                self.market.cancel(trading_pair, order_id)
                self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            os.unlink(self.db_path)


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
