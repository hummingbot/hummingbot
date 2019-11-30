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
    Dict,
    Optional
)
import unittest
from unittest.mock import patch

from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.data_type.user_stream_tracker import UserStreamTrackerDataSourceType
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketWithdrawAssetEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    OrderType,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
    TradeFee,
    TradeType,
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.market.liquid.liquid_market import (
    LiquidMarket,
    LiquidTime,
    liquid_client_module
)
from hummingbot.market.deposit_info import DepositInfo
from hummingbot.market.markets_recorder import MarketsRecorder
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType
)
from hummingbot.model.trade_fill import TradeFill
from hummingbot.wallet.ethereum.mock_wallet import MockWallet

MAINNET_RPC_URL = "http://mainnet-rpc.mainnet:8545"
logging.basicConfig(level=METRICS_LOG_LEVEL)


class LquidMarketUnitTest(unittest.TestCase):
    events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.WithdrawAsset,
        MarketEvent.OrderFilled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled
    ]

    market: LiquidMarket
    market_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        global MAINNET_RPC_URL

        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: LiquidMarket = LiquidMarket(
            conf.liquid_api_key, conf.liquid_secret_key,
            order_book_tracker_data_source_type=OrderBookTrackerDataSourceType.EXCHANGE_API,
            user_stream_tracker_data_source_type=UserStreamTrackerDataSourceType.EXCHANGE_API,
            trading_pairs=["ZRXETH", "IOSTETH"]
        )
        print("Initializing Liquid market... this will take about a minute.")
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.clock.add_iterator(cls.market)
        cls.stack: contextlib.ExitStack = contextlib.ExitStack()
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
        self.db_path: str = realpath(join(__file__, "../liquid_test.sqlite"))
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

        self.market_logger = EventLogger()
        for event_tag in self.events:
            self.market.add_listener(event_tag, self.market_logger)

    def tearDown(self):
        for event_tag in self.events:
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
        maker_buy_trade_fee: TradeFee = self.market.get_fee("BTC", "USDT", OrderType.LIMIT, TradeType.BUY, Decimal(1), Decimal(4000))
        self.assertGreater(maker_buy_trade_fee.percent, 0)
        self.assertEqual(len(maker_buy_trade_fee.flat_fees), 0)
        taker_buy_trade_fee: TradeFee = self.market.get_fee("BTC", "USDT", OrderType.MARKET, TradeType.BUY, Decimal(1))
        self.assertGreater(taker_buy_trade_fee.percent, 0)
        self.assertEqual(len(taker_buy_trade_fee.flat_fees), 0)
        sell_trade_fee: TradeFee = self.market.get_fee("BTC", "USDT", OrderType.LIMIT, TradeType.SELL, Decimal(1), Decimal(4000))
        self.assertGreater(sell_trade_fee.percent, 0)
        self.assertEqual(len(sell_trade_fee.flat_fees), 0)

    def test_buy_and_sell(self):
        self.assertGreater(self.market.get_balance("ETH"), Decimal("0.1"))

        # Try to buy 0.02 ETH worth of ZRX from the exchange, and watch for completion event.
        current_price: Decimal = self.market.get_price("ZRXETH", True)
        amount: Decimal = Decimal("0.02") / current_price
        quantized_amount: Decimal = self.market.quantize_order_amount("ZRXETH", amount)
        order_id = self.market.buy("ZRXETH", amount)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: Decimal = sum(t.amount for t in trade_events)
        quote_amount_traded: Decimal = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.MARKET for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("ZRX", order_completed_event.base_asset)
        self.assertEqual("ETH", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))

        # Reset the logs
        self.market_logger.clear()

        # Try to sell back the same amount of ZRX to the exchange, and watch for completion event.
        amount = order_completed_event.base_asset_amount
        quantized_amount = order_completed_event.base_asset_amount
        order_id = self.market.sell("ZRXETH", amount)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        order_completed_event: SellOrderCompletedEvent = order_completed_event
        trade_events = [t for t in self.market_logger.event_log
                        if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.MARKET for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("ZRX", order_completed_event.base_asset)
        self.assertEqual("ETH", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))

    def test_limit_buy_and_sell(self):
        self.assertGreater(self.market.get_balance("ETH"), Decimal("0.1"))

        # Try to put limit buy order for 0.02 ETH worth of ZRX, and watch for completion event.
        current_bid_price: Decimal = self.market.get_price("ZRXETH", True)
        bid_price: Decimal = current_bid_price + Decimal("0.05") * current_bid_price
        quantize_bid_price: Decimal = self.market.quantize_order_price("ZRXETH", bid_price)

        amount: Decimal = Decimal("0.02") / bid_price
        quantized_amount: Decimal = self.market.quantize_order_amount("ZRXETH", amount)

        order_id = self.market.buy("ZRXETH", quantized_amount, OrderType.LIMIT, quantize_bid_price)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: Decimal = sum(t.amount for t in trade_events)
        quote_amount_traded: Decimal = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("ZRX", order_completed_event.base_asset)
        self.assertEqual("ETH", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))

        # Reset the logs
        self.market_logger.clear()

        # Try to put limit sell order for 0.02 ETH worth of ZRX, and watch for completion event.
        current_ask_price: Decimal = self.market.get_price("ZRXETH", False)
        ask_price: Decimal = current_ask_price - Decimal("0.05") * current_ask_price
        quantize_ask_price: Decimal = self.market.quantize_order_price("ZRXETH", ask_price)

        amount = order_completed_event.base_asset_amount
        quantized_amount = order_completed_event.base_asset_amount

        order_id = self.market.sell("ZRXETH", quantized_amount, OrderType.LIMIT, quantize_ask_price)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        order_completed_event: SellOrderCompletedEvent = order_completed_event
        trade_events = [t for t in self.market_logger.event_log
                        if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("ZRX", order_completed_event.base_asset)
        self.assertEqual("ETH", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))

    def test_deposit_info(self):
        [deposit_info] = self.run_parallel(
            self.market.get_deposit_info("BNB")
        )
        deposit_info: DepositInfo = deposit_info
        self.assertIsInstance(deposit_info, DepositInfo)
        self.assertGreater(len(deposit_info.address), 0)
        self.assertGreater(len(deposit_info.extras), 0)
        self.assertTrue("addressTag" in deposit_info.extras)
        self.assertEqual("BNB", deposit_info.extras["asset"])

    @unittest.skipUnless(any("test_withdraw" in arg for arg in sys.argv), "Withdraw test requires manual action.")
    def test_withdraw(self):
        # ZRX_ABI contract file can be found in
        # https://etherscan.io/address/0xe41d2489571d322189246dafa5ebde1f4699f498#code
        with open(realpath(join(__file__, "../../../data/ZRXABI.json"))) as fd:
            zrx_abi: str = fd.read()

        local_wallet: MockWallet = MockWallet(conf.web3_test_private_key_a,
                                              conf.test_web3_provider_list[0],
                                              {"0xE41d2489571d322189246DaFA5ebDe1F4699F498": zrx_abi},
                                              chain_id=1)

        # Ensure the market account has enough balance for withdraw testing.
        self.assertGreaterEqual(self.market.get_balance("ZRX"), Decimal('10'))

        # Withdraw ZRX from Liquid to test wallet.
        self.market.withdraw(local_wallet.address, "ZRX", Decimal('10'))
        [withdraw_asset_event] = self.run_parallel(
            self.market_logger.wait_for(MarketWithdrawAssetEvent)
        )
        withdraw_asset_event: MarketWithdrawAssetEvent = withdraw_asset_event
        self.assertEqual(local_wallet.address, withdraw_asset_event.to_address)
        self.assertEqual("ZRX", withdraw_asset_event.asset_name)
        self.assertEqual(Decimal('10'), withdraw_asset_event.amount)
        self.assertGreater(withdraw_asset_event.fee_amount, Decimal(0))

    def test_cancel_all(self):
        trading_pair = "ZRXETH"
        bid_price: Decimal = self.market.get_price(trading_pair, True)
        ask_price: Decimal = self.market.get_price(trading_pair, False)
        amount: Decimal = Decimal("0.02") / bid_price
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        # Intentionally setting invalid price to prevent getting filled
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price * Decimal("0.7"))
        quantize_ask_price: Decimal = self.market.quantize_order_price(trading_pair, ask_price * Decimal("1.5"))

        self.market.buy(trading_pair, quantized_amount, OrderType.LIMIT, quantize_bid_price)
        self.market.sell(trading_pair, quantized_amount, OrderType.LIMIT, quantize_ask_price)

        self.run_parallel(asyncio.sleep(1))
        [cancellation_results] = self.run_parallel(self.market.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    def test_order_price_precision(self):
        # As of the day this test was written, the min order size (base) is 1 IOST, the min order size (quote) is
        # 0.01 ETH, and order step size is 1 IOST.
        trading_pair = "IOSTETH"
        bid_price: Decimal = self.market.get_price(trading_pair, True)
        ask_price: Decimal = self.market.get_price(trading_pair, False)
        mid_price: Decimal = (bid_price + ask_price) / 2
        amount: Decimal = Decimal("0.02") / mid_price
        liquid_client = self.market.liquid_client

        # Make sure there's enough balance to make the limit orders.
        self.assertGreater(self.market.get_balance("ETH"), Decimal("0.1"))
        self.assertGreater(self.market.get_balance("IOST"), amount * 2)

        # Intentionally set some prices with too many decimal places s.t. they
        # need to be quantized. Also, place them far away from the mid-price s.t. they won't
        # get filled during the test.
        bid_price: Decimal = mid_price * Decimal("0.3333192292111341")
        ask_price: Decimal = mid_price * Decimal("3.4392431474884933")

        # This is needed to get around the min quote amount limit.
        bid_amount: Decimal = Decimal("0.02") / bid_price

        # Test bid order
        bid_order_id: str = self.market.buy(
            trading_pair,
            Decimal(bid_amount),
            OrderType.LIMIT,
            Decimal(bid_price)
        )

        # Wait for the order created event and examine the order made
        [order_created_event] = self.run_parallel(
            self.market_logger.wait_for(BuyOrderCreatedEvent, timeout_seconds=10)
        )
        order_data: Dict[str, any] = liquid_client.get_order(
            symbol=trading_pair,
            origClientOrderId=bid_order_id
        )
        quantized_bid_price: Decimal = self.market.quantize_order_price(trading_pair, Decimal(bid_price))
        bid_size_quantum: Decimal = self.market.get_order_size_quantum(trading_pair, Decimal(bid_amount))
        self.assertEqual(quantized_bid_price, Decimal(order_data["price"]))
        self.assertTrue(Decimal(order_data["origQty"]) % bid_size_quantum == 0)

        # Test ask order
        ask_order_id: str = self.market.sell(
            trading_pair,
            Decimal(amount),
            OrderType.LIMIT,
            Decimal(ask_price)
        )

        # Wait for the order created event and examine and order made
        [order_created_event] = self.run_parallel(
            self.market_logger.wait_for(SellOrderCreatedEvent, timeout_seconds=10)
        )
        order_data = liquid_client.get_order(
            symbol=trading_pair,
            origClientOrderId=ask_order_id
        )
        quantized_ask_price: Decimal = self.market.quantize_order_price(trading_pair, Decimal(ask_price))
        quantized_ask_size: Decimal = self.market.quantize_order_amount(trading_pair, Decimal(amount))
        self.assertEqual(quantized_ask_price, Decimal(order_data["price"]))
        self.assertEqual(quantized_ask_size, Decimal(order_data["origQty"]))

        # Cancel all the orders
        [cancellation_results] = self.run_parallel(self.market.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    def test_server_time_offset(self):
        time_obj: LiquidTime = liquid_client_module.time
        old_check_interval: float = time_obj.SERVER_TIME_OFFSET_CHECK_INTERVAL
        time_obj.SERVER_TIME_OFFSET_CHECK_INTERVAL = 1.0
        time_obj.stop()
        time_obj.start()

        try:
            with patch("hummingbot.market.liquid.liquid_time.time") as market_time:
                def delayed_time():
                    return time.time() - 30.0
                market_time.time = delayed_time
                self.run_parallel(asyncio.sleep(3.0))
                time_offset = LiquidTime.get_instance().time_offset_ms
                # check if it is less than 5% off
                self.assertTrue(time_offset > 10000)
                self.assertTrue(abs(time_offset - 30.0 * 1e3) < 1.5 * 1e3)
        finally:
            time_obj.SERVER_TIME_OFFSET_CHECK_INTERVAL = old_check_interval
            time_obj.stop()
            time_obj.start()

    def test_orders_saving_and_restoration(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            self.assertEqual(0, len(self.market.tracking_states))

            # Try to put limit buy order for 0.02 ETH worth of ZRX, and watch for order creation event.
            current_bid_price: Decimal = self.market.get_price("ZRXETH", True)
            bid_price: Decimal = current_bid_price * Decimal("0.8")
            quantize_bid_price: Decimal = self.market.quantize_order_price("ZRXETH", bid_price)

            amount: Decimal = Decimal("0.02") / bid_price
            quantized_amount: Decimal = self.market.quantize_order_amount("ZRXETH", amount)

            order_id = self.market.buy("ZRXETH", quantized_amount, OrderType.LIMIT, quantize_bid_price)
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
            for event_tag in self.events:
                self.market.remove_listener(event_tag, self.market_logger)
            self.market: LiquidMarket = LiquidMarket(
                liquid_api_key=conf.liquid_api_key,
                liquid_api_secret=conf.liquid_api_secret,
                order_book_tracker_data_source_type=OrderBookTrackerDataSourceType.EXCHANGE_API,
                user_stream_tracker_data_source_type=UserStreamTrackerDataSourceType.EXCHANGE_API,
                trading_pairs=["ZRXETH", "IOSTETH"]
            )
            for event_tag in self.events:
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
            self.market.cancel("ZRXETH", order_id)
            self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
            order_id = None
            self.assertEqual(0, len(self.market.limit_orders))
            self.assertEqual(0, len(self.market.tracking_states))
            saved_market_states = recorder.get_market_states(config_path, self.market)
            self.assertEqual(0, len(saved_market_states.saved_state))
        finally:
            if order_id is not None:
                self.market.cancel("ZRXETH", order_id)
                self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            os.unlink(self.db_path)

    def test_order_fill_record(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            # Try to buy 0.02 ETH worth of ZRX from the exchange, and watch for completion event.
            current_price: Decimal = self.market.get_price("ZRXETH", True)
            amount: Decimal = Decimal("0.02") / current_price
            order_id = self.market.buy("ZRXETH", amount)
            [buy_order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))

            # Reset the logs
            self.market_logger.clear()

            # Try to sell back the same amount of ZRX to the exchange, and watch for completion event.
            amount = buy_order_completed_event.base_asset_amount
            order_id = self.market.sell("ZRXETH", amount)
            [sell_order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))

            # Query the persisted trade logs
            trade_fills: List[TradeFill] = recorder.get_trades_for_config(config_path)
            self.assertGreaterEqual(len(trade_fills), 2)
            buy_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "BUY"]
            sell_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "SELL"]
            self.assertGreaterEqual(len(buy_fills), 1)
            self.assertGreaterEqual(len(sell_fills), 1)

            order_id = None

        finally:
            if order_id is not None:
                self.market.cancel("ZRXETH", order_id)
                self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            os.unlink(self.db_path)


if __name__ == "__main__":
    logging.getLogger("hummingbot.core.event.event_reporter").setLevel(logging.WARNING)
    unittest.main()
