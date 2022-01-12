#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))

import asyncio
import contextlib
from decimal import Decimal
import logging
import os
import time
import conf
from typing import (
    List,
    Optional
)
import unittest
import math
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    MarketEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    OrderType,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
    TradeType,
)
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.connector.exchange.liquid.liquid_exchange import LiquidExchange, Constants
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType
)
from hummingbot.model.trade_fill import TradeFill
from hummingbot.client.config.fee_overrides_config_map import fee_overrides_config_map
from hummingbot.core.mock_api.mock_web_server import MockWebServer
from test.connector.exchange.liquid.fixture_liquid import FixtureLiquid
from unittest import mock

logging.basicConfig(level=METRICS_LOG_LEVEL)
API_MOCK_ENABLED = conf.mock_api_enabled is not None and conf.mock_api_enabled.lower() in ['true', 'yes', '1']
API_KEY = "XXX" if API_MOCK_ENABLED else conf.liquid_api_key
API_SECRET = "YYY" if API_MOCK_ENABLED else conf.liquid_secret_key
API_HOST = "api.liquid.com"


class LiquidExchangeUnitTest(unittest.TestCase):
    events: List[MarketEvent] = [
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.OrderFilled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled,
        MarketEvent.OrderFailure
    ]

    market: LiquidExchange
    market_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        cls.ev_loop = asyncio.get_event_loop()

        if API_MOCK_ENABLED:
            cls.web_app = MockWebServer.get_instance()
            cls.web_app.add_host_to_mock(API_HOST, ["/products", "/currencies"])
            cls.web_app.start()
            cls.ev_loop.run_until_complete(cls.web_app.wait_til_started())
            cls._patcher = mock.patch("aiohttp.client.URL")
            cls._url_mock = cls._patcher.start()
            cls._url_mock.side_effect = cls.web_app.reroute_local
            cls.web_app.update_response("get", API_HOST, "/fiat_accounts", FixtureLiquid.FIAT_ACCOUNTS)
            cls.web_app.update_response("get", API_HOST, "/crypto_accounts",
                                        FixtureLiquid.CRYPTO_ACCOUNTS)
            cls.web_app.update_response("get", API_HOST, "/orders", FixtureLiquid.ORDERS_GET)
            cls._t_nonce_patcher = unittest.mock.patch(
                "hummingbot.connector.exchange.liquid.liquid_exchange.get_tracking_nonce")
            cls._t_nonce_mock = cls._t_nonce_patcher.start()
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: LiquidExchange = LiquidExchange(
            API_KEY, API_SECRET,
            poll_interval=5,
            trading_pairs=['CEL-ETH'],
        )
        # cls.ev_loop.run_until_complete(cls.market._update_balances())
        print("Initializing Liquid market... this will take about a minute.")
        cls.clock.add_iterator(cls.market)
        cls.stack: contextlib.ExitStack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_til_ready())
        print("Ready.")

    @classmethod
    def tearDownClass(cls) -> None:
        if API_MOCK_ENABLED:
            cls.web_app.stop()
            cls._patcher.stop()
            cls._t_nonce_patcher.stop()
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
        maker_buy_trade_fee: AddedToCostTradeFee = self.market.get_fee("BTC",
                                                                       "USD",
                                                                       OrderType.LIMIT_MAKER,
                                                                       TradeType.BUY,
                                                                       Decimal(1),
                                                                       Decimal(4000))
        self.assertGreater(maker_buy_trade_fee.percent, 0)
        self.assertEqual(len(maker_buy_trade_fee.flat_fees), 0)
        taker_buy_trade_fee: AddedToCostTradeFee = self.market.get_fee(
            "BTC", "USD", OrderType.LIMIT, TradeType.BUY, Decimal(1)
        )
        self.assertGreater(taker_buy_trade_fee.percent, 0)
        self.assertEqual(len(taker_buy_trade_fee.flat_fees), 0)
        sell_trade_fee: AddedToCostTradeFee = self.market.get_fee("BTC",
                                                                  "USD",
                                                                  OrderType.LIMIT_MAKER,
                                                                  TradeType.SELL,
                                                                  Decimal(1),
                                                                  Decimal(4000))
        self.assertGreater(sell_trade_fee.percent, 0)
        self.assertEqual(len(sell_trade_fee.flat_fees), 0)

    def test_fee_overrides_config(self):
        fee_overrides_config_map["liquid_taker_fee"].value = None
        taker_fee: AddedToCostTradeFee = self.market.get_fee("LINK", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1),
                                                             Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.001"), taker_fee.percent)
        fee_overrides_config_map["liquid_taker_fee"].value = Decimal('0.2')
        taker_fee: AddedToCostTradeFee = self.market.get_fee("LINK", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1),
                                                             Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.002"), taker_fee.percent)
        fee_overrides_config_map["liquid_maker_fee"].value = None
        maker_fee: AddedToCostTradeFee = self.market.get_fee("LINK",
                                                             "ETH",
                                                             OrderType.LIMIT_MAKER,
                                                             TradeType.BUY,
                                                             Decimal(1),
                                                             Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.001"), maker_fee.percent)
        fee_overrides_config_map["liquid_maker_fee"].value = Decimal('0.5')
        maker_fee: AddedToCostTradeFee = self.market.get_fee("LINK",
                                                             "ETH",
                                                             OrderType.LIMIT_MAKER,
                                                             TradeType.BUY,
                                                             Decimal(1),
                                                             Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.005"), maker_fee.percent)

    def place_order(self, is_buy, trading_pair, amount, order_type, price, nonce, order_resp, get_resp):
        order_id, exchange_id = None, None
        if API_MOCK_ENABLED:
            side = 'buy' if is_buy else 'sell'
            self._t_nonce_mock.return_value = nonce
            order_id = f"{side.lower()}-{trading_pair}-{str(nonce)}"
            resp = order_resp.copy()
            resp["client_order_id"] = order_id
            exchange_id = resp["id"]
            self.web_app.update_response("post", API_HOST, "/orders", resp)
        if is_buy:
            order_id = self.market.buy(trading_pair, amount, order_type, price)
        else:
            order_id = self.market.sell(trading_pair, amount, order_type, price)
        if API_MOCK_ENABLED:
            resp = get_resp.copy()
            resp["models"][-1]["client_order_id"] = order_id
            self.web_app.update_response("get", API_HOST, "/orders", resp)
        return order_id, exchange_id

    async def cancel_all_open_orders(self):
        listed_orders = await self.market.list_orders()
        live_orders = [o for o in listed_orders.get("models", []) if o["status"] == "live"]
        for order in live_orders:
            path_url = Constants.CANCEL_ORDER_URI.format(exchange_order_id=str(order["id"]))
            res = await self.market._api_request("put", path_url=path_url)
            print(res)

    def test_maintain_user_balances(self):
        # self.ev_loop.run_until_complete(self.cancel_all_open_orders())
        # return

        trading_pair = "CEL-ETH"
        base = trading_pair.split("-")[0]
        quote = trading_pair.split("-")[1]
        base_bal = self.market.get_available_balance(base)
        starting_quote_bal = self.market.get_available_balance(quote)
        print(f"{base} available: {base_bal}")
        print(f"starting quote available: {starting_quote_bal}")

        bid_price = self.market.get_price(trading_pair, False)
        buy_price = bid_price * Decimal("0.9")
        buy_price = self.market.quantize_order_price(trading_pair, buy_price)
        amount = Decimal("1")
        post_data = FixtureLiquid.BUY_MARKET_ORDER.copy()
        get_data = FixtureLiquid.ORDERS_UNFILLED.copy()
        if API_MOCK_ENABLED:
            resp = FixtureLiquid.CRYPTO_ACCOUNTS.copy()
            resp[0]["reserved_balance"] = float((buy_price * amount))
            self.web_app.update_response("get", API_HOST, "/crypto_accounts", resp)
        order_id_1, exchange_id_1 = self.place_order(True, "CEL-ETH", amount, OrderType.LIMIT, buy_price, 10001,
                                                     post_data, get_data)
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        print(f"order_created_event: {order_created_event}")
        self.assertEqual(order_id_1, order_created_event.order_id)

        # ToDo: the test from here on pass fine in real API test mode, for the API mocked we first need to fix
        # https://github.com/CoinAlpha/hummingbot/issues/2222
        if API_MOCK_ENABLED:
            return
        base_bal = self.market.get_available_balance(base)
        quote_bal = self.market.get_available_balance(quote)
        expected_quote_bal = starting_quote_bal - (buy_price * amount)
        self.assertAlmostEqual(quote_bal, expected_quote_bal, 5)
        print(f"{base} available: {base_bal}")
        print(f"{quote} available: {quote_bal}")

        self.run_parallel(asyncio.sleep(5))
        post_data = FixtureLiquid.BUY_MARKET_ORDER.copy()
        get_data = FixtureLiquid.ORDERS_UNFILLED.copy()
        get_data["models"].append(get_data["models"][0].copy())
        get_data["models"][0]["client_order_id"] = order_id_1
        get_data["models"][1]["id"] = get_data["models"][0]["id"] + 1
        if API_MOCK_ENABLED:
            resp = FixtureLiquid.CRYPTO_ACCOUNTS.copy()
            resp[0]["reserved_balance"] = float((2 * buy_price * amount))
            self.web_app.update_response("get", API_HOST, "/crypto_accounts", resp)
        order_id_2, exchange_id_2 = self.place_order(True, "CEL-ETH", amount, OrderType.LIMIT, buy_price, 10002,
                                                     post_data, get_data)
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        print(f"order_created_event: {order_created_event}")
        self.assertEqual(order_id_2, order_created_event.order_id)

        base_bal = self.market.get_available_balance(base)
        quote_bal = self.market.get_available_balance(quote)
        expected_quote_bal = starting_quote_bal - 2 * (buy_price * amount)
        self.assertAlmostEqual(quote_bal, expected_quote_bal, 5)
        print(f"{base} available: {base_bal}")
        print(f"{quote} available: {quote_bal}")

        if API_MOCK_ENABLED:
            order_cancel_resp = FixtureLiquid.SELL_LIMIT_ORDER_AFTER_CANCEL
            self.web_app.update_response("put", API_HOST, f"/orders/{str(exchange_id_2)}/cancel",
                                         order_cancel_resp)
            resp = FixtureLiquid.CRYPTO_ACCOUNTS.copy()
            resp[0]["reserved_balance"] = float((buy_price * amount))
            self.web_app.update_response("get", API_HOST, "/crypto_accounts", resp)
        self.market.cancel("CEL-ETH", order_id_2)
        self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
        quote_bal = self.market.get_available_balance(quote)
        expected_quote_bal = starting_quote_bal - 1 * (buy_price * amount)
        print(f"expected_quote_bal: {expected_quote_bal}")
        print(f"quote_bal: {quote_bal}")
        self.assertAlmostEqual(quote_bal, expected_quote_bal, 5)

        if API_MOCK_ENABLED:
            order_cancel_resp = FixtureLiquid.SELL_LIMIT_ORDER_AFTER_CANCEL
            self.web_app.update_response("put", API_HOST, f"/orders/{str(exchange_id_1)}/cancel",
                                         order_cancel_resp)

        [cancellation_results] = self.run_parallel(self.market.cancel_all(5))

    def test_limit_taker_buy_and_sell(self):
        self.assertGreater(self.market.get_balance("ETH"), Decimal("0.01"))

        current_price: Decimal = self.market.get_price("CEL-ETH", True)
        amount: Decimal = 1
        quantized_amount: Decimal = self.market.quantize_order_amount("CEL-ETH", amount)

        order_id, _ = self.place_order(True, "CEL-ETH", amount, OrderType.LIMIT, current_price, 10001,
                                       FixtureLiquid.BUY_MARKET_ORDER, FixtureLiquid.ORDERS_GET_AFTER_BUY)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: Decimal = sum(t.amount for t in trade_events)
        quote_amount_traded: Decimal = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("CEL", order_completed_event.base_asset)
        self.assertEqual("ETH", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))

        # Reset the logs
        self.market_logger.clear()

        # Try to sell back the same amount of CEL to the exchange, and watch for completion event.
        current_price: Decimal = self.market.get_price("CEL-ETH", False)
        amount = order_completed_event.base_asset_amount
        quantized_amount = order_completed_event.base_asset_amount
        order_id, _ = self.place_order(False, "CEL-ETH", amount, OrderType.LIMIT, current_price, 10002,
                                       FixtureLiquid.SELL_MARKET_ORDER, FixtureLiquid.ORDERS_GET_AFTER_MARKET_SELL)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        order_completed_event: SellOrderCompletedEvent = order_completed_event
        trade_events = [t for t in self.market_logger.event_log
                        if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("CEL", order_completed_event.base_asset)
        self.assertEqual("ETH", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))

    def test_limit_maker_rejections(self):
        if API_MOCK_ENABLED:
            return
        trading_pair = "CEL-ETH"

        # Try to put a buy limit maker order that is going to match, this should triggers order failure event.
        price: Decimal = self.market.get_price(trading_pair, True) * Decimal('1.02')
        price: Decimal = self.market.quantize_order_price(trading_pair, price)
        amount = self.market.quantize_order_amount(trading_pair, 1)

        order_id = self.market.buy(trading_pair, amount, OrderType.LIMIT_MAKER, price)
        [order_failure_event] = self.run_parallel(self.market_logger.wait_for(MarketOrderFailureEvent))
        self.assertEqual(order_id, order_failure_event.order_id)

        self.market_logger.clear()

        # Try to put a sell limit maker order that is going to match, this should triggers order failure event.
        price: Decimal = self.market.get_price(trading_pair, True) * Decimal('0.98')
        price: Decimal = self.market.quantize_order_price(trading_pair, price)
        amount = self.market.quantize_order_amount(trading_pair, 1)

        order_id = self.market.sell(trading_pair, amount, OrderType.LIMIT_MAKER, price)
        [order_failure_event] = self.run_parallel(self.market_logger.wait_for(MarketOrderFailureEvent))
        self.assertEqual(order_id, order_failure_event.order_id)

    def test_limit_makers_unfilled(self):
        trading_pair = "CEL-ETH"
        bid_price: Decimal = self.market.get_price(trading_pair, True)
        ask_price: Decimal = self.market.get_price(trading_pair, False)
        amount: Decimal = 1
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        # Intentionally setting invalid price to prevent getting filled
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price * Decimal("0.7"))
        quantize_ask_price: Decimal = self.market.quantize_order_price(trading_pair, ask_price * Decimal("1.5"))

        buy_order_id, buy_exchange_id = self.place_order(
            True, trading_pair, quantized_amount, OrderType.LIMIT_MAKER, quantize_bid_price,
            10001, FixtureLiquid.BUY_LIMIT_ORDER_BEFORE_CANCEL,
            FixtureLiquid.ORDERS_GET_AFTER_BUY
        )
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        self.assertEqual(buy_order_id, order_created_event.order_id)

        sell_order_id, sell_exchange_id = self.place_order(
            False, trading_pair, quantized_amount, OrderType.LIMIT_MAKER,
            quantize_ask_price, 10002, FixtureLiquid.SELL_LIMIT_ORDER_BEFORE_CANCEL,
            FixtureLiquid.ORDERS_GET_AFTER_MARKET_SELL
        )
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))
        self.assertEqual(sell_order_id, order_created_event.order_id)

        self.run_parallel(asyncio.sleep(1))
        if API_MOCK_ENABLED:
            order_cancel_resp = FixtureLiquid.SELL_LIMIT_ORDER_AFTER_CANCEL
            self.web_app.update_response("put", API_HOST, f"/orders/{str(buy_exchange_id)}/cancel",
                                         order_cancel_resp)
            order_cancel_resp = FixtureLiquid.BUY_LIMIT_ORDER_AFTER_CANCEL
            self.web_app.update_response("put", API_HOST, f"/orders/{str(sell_exchange_id)}/cancel",
                                         order_cancel_resp)
        [cancellation_results] = self.run_parallel(self.market.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    def test_cancel_all(self):
        trading_pair = "CEL-ETH"
        bid_price: Decimal = self.market.get_price(trading_pair, True)
        ask_price: Decimal = self.market.get_price(trading_pair, False)
        amount: Decimal = 1
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        # Intentionally setting invalid price to prevent getting filled
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price * Decimal("0.7"))
        quantize_ask_price: Decimal = self.market.quantize_order_price(trading_pair, ask_price * Decimal("1.5"))

        _, buy_exchange_id = self.place_order(True, trading_pair, quantized_amount, OrderType.LIMIT_MAKER, quantize_bid_price,
                                              10001, FixtureLiquid.BUY_LIMIT_ORDER_BEFORE_CANCEL,
                                              FixtureLiquid.ORDERS_GET_AFTER_BUY)
        _, sell_exchange_id = self.place_order(False, trading_pair, quantized_amount, OrderType.LIMIT_MAKER,
                                               quantize_ask_price, 10002, FixtureLiquid.SELL_LIMIT_ORDER_BEFORE_CANCEL,
                                               FixtureLiquid.ORDERS_GET_AFTER_MARKET_SELL)

        self.run_parallel(asyncio.sleep(1))
        if API_MOCK_ENABLED:
            order_cancel_resp = FixtureLiquid.SELL_LIMIT_ORDER_AFTER_CANCEL
            self.web_app.update_response("put", API_HOST, f"/orders/{str(buy_exchange_id)}/cancel",
                                         order_cancel_resp)
            order_cancel_resp = FixtureLiquid.BUY_LIMIT_ORDER_AFTER_CANCEL
            self.web_app.update_response("put", API_HOST, f"/orders/{str(sell_exchange_id)}/cancel",
                                         order_cancel_resp)
        [cancellation_results] = self.run_parallel(self.market.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    def test_orders_saving_and_restoration(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            self.assertEqual(0, len(self.market.tracking_states))

            # Try to put limit buy order for 0.005 ETH worth of CEL, and watch for order creation event.
            current_bid_price: Decimal = self.market.get_price("CEL-ETH", True)
            bid_price: Decimal = current_bid_price * Decimal("0.8")
            quantize_bid_price: Decimal = self.market.quantize_order_price("CEL-ETH", bid_price)

            amount: Decimal = 1
            quantized_amount: Decimal = self.market.quantize_order_amount("CEL-ETH", amount)

            order_id, buy_exchange_id = self.place_order(True, "CEL-ETH", quantized_amount, OrderType.LIMIT_MAKER,
                                                         quantize_bid_price, 10001, FixtureLiquid.ORDER_SAVE_RESTORE,
                                                         FixtureLiquid.ORDERS_GET_AFTER_BUY)
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

            self.market: LiquidExchange = LiquidExchange(
                API_KEY, API_SECRET,
                trading_pairs=['ETH-USD', 'CEL-ETH']
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
            if API_MOCK_ENABLED:
                order_cancel_resp = FixtureLiquid.ORDER_CANCEL_SAVE_RESTORE.copy()
                self.web_app.update_response("put", API_HOST, f"/orders/{str(buy_exchange_id)}/cancel",
                                             order_cancel_resp)
            self.market.cancel("CEL-ETH", order_id)
            self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
            order_id = None
            self.assertEqual(0, len(self.market.limit_orders))
            self.assertEqual(0, len(self.market.tracking_states))
            saved_market_states = recorder.get_market_states(config_path, self.market)
            self.assertEqual(0, len(saved_market_states.saved_state))
        finally:
            if order_id is not None:
                self.market.cancel("CEL-ETH", order_id)
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
            # Try to buy 1 CEL from the exchange, and watch for completion event.
            current_price: Decimal = self.market.get_price("CEL-ETH", True)
            amount: Decimal = 1
            order_id, _ = self.place_order(True, "CEL-ETH", amount, OrderType.LIMIT, current_price, 10001,
                                           FixtureLiquid.FILLED_BUY_LIMIT_ORDER, FixtureLiquid.ORDERS_GET_AFTER_LIMIT_BUY)
            [buy_order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))

            # Reset the logs
            self.market_logger.clear()

            # Try to sell back the same amount of CEL to the exchange, and watch for completion event.
            current_price: Decimal = self.market.get_price("CEL-ETH", False)
            amount = buy_order_completed_event.base_asset_amount
            order_id, _ = self.place_order(False, "CEL-ETH", amount, OrderType.LIMIT, current_price, 10002,
                                           FixtureLiquid.FILLED_SELL_LIMIT_ORDER, FixtureLiquid.ORDERS_GET_AFTER_LIMIT_SELL)
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
                self.market.cancel("CEL-ETH", order_id)
                self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            os.unlink(self.db_path)

    def test_update_last_prices(self):
        # This is basic test to see if order_book last_trade_price is initiated and updated.
        for order_book in self.market.order_books.values():
            for _ in range(5):
                self.ev_loop.run_until_complete(asyncio.sleep(1))
                print(order_book.last_trade_price)
                self.assertFalse(math.isnan(order_book.last_trade_price))


if __name__ == "__main__":
    logging.getLogger("hummingbot.core.event.event_reporter").setLevel(logging.WARNING)
    unittest.main()
