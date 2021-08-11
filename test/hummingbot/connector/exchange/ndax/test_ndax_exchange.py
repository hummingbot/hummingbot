import asyncio
import json
import time
import pandas as pd

from decimal import Decimal
from typing import Any, Dict, List
from unittest import TestCase
from unittest.mock import AsyncMock, PropertyMock, patch

import hummingbot.connector.exchange.ndax.ndax_constants as CONSTANTS
from hummingbot.connector.exchange.ndax.ndax_exchange import NdaxExchange
from hummingbot.connector.exchange.ndax.ndax_in_flight_order import NdaxInFlightOrder
from hummingbot.connector.exchange.ndax.ndax_order_book import NdaxOrderBook
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.event.events import (
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    OrderType,
    TradeType,
)
from hummingbot.core.network_iterator import NetworkStatus


class NdaxExchangeTests(TestCase):
    # the level is required to receive logs from the data source loger
    level = 0

    start_timestamp: float = pd.Timestamp("2021-01-01", tz="UTC").timestamp()

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.ws_sent_messages = []
        self.ws_incoming_messages = asyncio.Queue()

        self.api_responses = asyncio.Queue()

        self.tracker_task = None
        self.exchange_task = None
        self.log_records = []
        self.resume_test_event = asyncio.Event()
        self._finalMessage = 'FinalDummyMessage'
        self._account_name = "hbot"

        self.exchange = NdaxExchange(ndax_uid='001',
                                     ndax_api_key='testAPIKey',
                                     ndax_secret_key='testSecret',
                                     ndax_account_name=self._account_name,
                                     trading_pairs=[self.trading_pair])

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._account_id = 1

    def tearDown(self) -> None:
        self.tracker_task and self.tracker_task.cancel()
        self.exchange_task and self.exchange_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    async def _get_next_received_message(self):
        message = await self.ws_incoming_messages.get()
        if json.loads(message) == self._finalMessage:
            self.resume_test_event.set()
        return message

    async def _get_next_api_response(self):
        message = await self.api_responses.get()
        return message

    def _create_ws_mock(self):
        ws = AsyncMock()
        ws.send.side_effect = lambda sent_message: self.ws_sent_messages.append(sent_message)
        ws.recv.side_effect = self._get_next_received_message
        return ws

    def _authentication_response(self, authenticated: bool) -> str:
        user = {"UserId": 492,
                "UserName": "hbot",
                "Email": "hbot@mailinator.com",
                "EmailVerified": True,
                "AccountId": 528,
                "OMSId": 1,
                "Use2FA": True}
        payload = {"Authenticated": authenticated,
                   "SessionToken": "74e7c5b0-26b1-4ca5-b852-79b796b0e599",
                   "User": user,
                   "Locked": False,
                   "Requires2FA": False,
                   "EnforceEnable2FA": False,
                   "TwoFAType": None,
                   "TwoFAToken": None,
                   "errormsg": None}
        message = {"m": 1,
                   "i": 1,
                   "n": CONSTANTS.AUTHENTICATE_USER_ENDPOINT_NAME,
                   "o": json.dumps(payload)}

        return json.dumps(message)

    def _set_mock_response(self, mock_api, status: int, json_data: Any, text_data: str = ""):
        self.api_responses.put_nowait(json_data)
        mock_api.return_value.status = status
        mock_api.return_value.json.side_effect = self._get_next_api_response
        mock_api.return_value.text = AsyncMock(return_value=text_data)

    def _add_successful_authentication_response(self):
        self.ws_incoming_messages.put_nowait(self._authentication_response(True))

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _simulate_reset_poll_notifier(self):
        self.exchange._poll_notifier.clear()

    def _simulate_ws_message_received(self, timestamp: float):
        self.exchange._user_stream_tracker._data_source._last_recv_time = timestamp

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_user_event_queue_error_is_logged(self, ws_connect_mock):
        ws_connect_mock.return_value = self._create_ws_mock()

        self.exchange_task = asyncio.get_event_loop().create_task(
            self.exchange._user_stream_event_listener())
        # Add the authentication response for the websocket
        self._add_successful_authentication_response()

        dummy_user_stream = AsyncMock()
        dummy_user_stream.get.side_effect = lambda: self._create_exception_and_unlock_test_with_event(
            Exception("Dummy test error"))
        self.exchange._user_stream_tracker._user_stream = dummy_user_stream

        # Add a dummy message for the websocket to read and include in the "messages" queue
        self.ws_incoming_messages.put_nowait(json.dumps('dummyMessage'))
        asyncio.get_event_loop().run_until_complete(self.resume_test_event.wait())
        self.resume_test_event.clear()

        try:
            self.exchange_task.cancel()
            asyncio.get_event_loop().run_until_complete(self.exchange_task)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

        self.assertTrue(self._is_logged('NETWORK', "Unknown error. Retrying after 1 seconds."))

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_user_event_queue_notifies_cancellations(self, ws_connect_mock):
        ws_connect_mock.return_value = self._create_ws_mock()

        self.tracker_task = asyncio.get_event_loop().create_task(
            self.exchange._user_stream_event_listener())
        # Add the authentication response for the websocket
        self._add_successful_authentication_response()

        dummy_user_stream = AsyncMock()
        dummy_user_stream.get.side_effect = lambda: self._create_exception_and_unlock_test_with_event(
            asyncio.CancelledError())
        self.exchange._user_stream_tracker._user_stream = dummy_user_stream

        # Add a dummy message for the websocket to read and include in the "messages" queue
        self.ws_incoming_messages.put_nowait(json.dumps('dummyMessage'))
        asyncio.get_event_loop().run_until_complete(self.resume_test_event.wait())
        self.resume_test_event.clear()

        with self.assertRaises(asyncio.CancelledError):
            asyncio.get_event_loop().run_until_complete(self.tracker_task)

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_exchange_logs_unknown_event_message(self, ws_connect_mock):
        payload = {}
        message = {"m": 3,
                   "i": 99,
                   "n": 'UnknownEndpoint',
                   "o": json.dumps(payload)}

        ws_connect_mock.return_value = self._create_ws_mock()

        self.exchange_task = asyncio.get_event_loop().create_task(
            self.exchange._user_stream_event_listener())
        self.tracker_task = asyncio.get_event_loop().create_task(
            self.exchange._user_stream_tracker.start())

        # Add the authentication response for the websocket
        self._add_successful_authentication_response()
        self.ws_incoming_messages.put_nowait(json.dumps(message))

        # Add a dummy message for the websocket to read and include in the "messages" queue
        self.ws_incoming_messages.put_nowait(json.dumps(self._finalMessage))

        # Wait until the connector finishes processing the message queue
        asyncio.get_event_loop().run_until_complete(self.resume_test_event.wait())
        self.resume_test_event.clear()

        self.assertTrue(self._is_logged('DEBUG', f"Unknown event received from the connector ({message})"))

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_account_position_event_updates_account_balances(self, ws_connect_mock):
        payload = {"OMSId": 1,
                   "AccountId": 5,
                   "ProductSymbol": "BTC",
                   "ProductId": 1,
                   "Amount": 10499.1,
                   "Hold": 2.1,
                   "PendingDeposits": 10,
                   "PendingWithdraws": 20,
                   "TotalDayDeposits": 30,
                   "TotalDayWithdraws": 40}
        message = {"m": 3,
                   "i": 2,
                   "n": CONSTANTS.ACCOUNT_POSITION_EVENT_ENDPOINT_NAME,
                   "o": json.dumps(payload)}

        ws_connect_mock.return_value = self._create_ws_mock()

        self.exchange_task = asyncio.get_event_loop().create_task(
            self.exchange._user_stream_event_listener())
        self.tracker_task = asyncio.get_event_loop().create_task(
            self.exchange._user_stream_tracker.start())

        # Add the authentication response for the websocket
        self._add_successful_authentication_response()
        self.ws_incoming_messages.put_nowait(json.dumps(message))

        # Add a dummy message for the websocket to read and include in the "messages" queue
        self.ws_incoming_messages.put_nowait(json.dumps(self._finalMessage))

        # Wait until the connector finishes processing the message queue
        asyncio.get_event_loop().run_until_complete(self.resume_test_event.wait())
        self.resume_test_event.clear()

        self.assertEqual(Decimal('10499.1'), self.exchange.get_balance('BTC'))
        self.assertEqual(Decimal('10499.1') - Decimal('2.1'), self.exchange.available_balances['BTC'])

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_order_event_with_cancel_status_cancels_in_flight_order(self, ws_connect_mock):
        payload = {
            "Side": "Sell",
            "OrderId": 9849,
            "Price": 35000,
            "Quantity": 1,
            "Instrument": 1,
            "Account": 4,
            "OrderType": "Limit",
            "ClientOrderId": 3,
            "OrderState": "Canceled",
            "ReceiveTime": 0,
            "OrigQuantity": 1,
            "QuantityExecuted": 0,
            "AvgPrice": 0,
            "ChangeReason": "NewInputAccepted"
        }
        message = {"m": 3,
                   "i": 2,
                   "n": CONSTANTS.ORDER_STATE_EVENT_ENDPOINT_NAME,
                   "o": json.dumps(payload)}

        ws_connect_mock.return_value = self._create_ws_mock()

        self.exchange.start_tracking_order(order_id="3",
                                           exchange_order_id="9849",
                                           trading_pair="BTC-USD",
                                           trade_type=TradeType.SELL,
                                           price=Decimal("35000"),
                                           amount=Decimal("1"),
                                           order_type=OrderType.LIMIT)

        inflight_order = self.exchange.in_flight_orders["3"]

        self.exchange_task = asyncio.get_event_loop().create_task(
            self.exchange._user_stream_event_listener())
        self.tracker_task = asyncio.get_event_loop().create_task(
            self.exchange._user_stream_tracker.start())

        # Add the authentication response for the websocket
        self._add_successful_authentication_response()
        self.ws_incoming_messages.put_nowait(json.dumps(message))

        # Add a dummy message for the websocket to read and include in the "messages" queue
        self.ws_incoming_messages.put_nowait(json.dumps(self._finalMessage))

        # Wait until the connector finishes processing the message queue
        asyncio.get_event_loop().run_until_complete(self.resume_test_event.wait())
        self.resume_test_event.clear()

        self.assertEqual("Canceled", inflight_order.last_state)
        self.assertTrue(inflight_order.is_cancelled)
        self.assertFalse(inflight_order.client_order_id in self.exchange.in_flight_orders)
        self.assertTrue(self._is_logged("INFO", f"Successfully cancelled order {inflight_order.client_order_id}"))
        self.assertEqual(1, len(self.exchange.event_logs))
        cancel_event = self.exchange.event_logs[0]
        self.assertEqual(OrderCancelledEvent, type(cancel_event))
        self.assertEqual(inflight_order.client_order_id, cancel_event.order_id)

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_order_event_with_rejected_status_makes_in_flight_order_fail(self, ws_connect_mock):
        payload = {
            "Side": "Sell",
            "OrderId": 9849,
            "Price": 35000,
            "Quantity": 1,
            "Instrument": 1,
            "Account": 4,
            "OrderType": "Limit",
            "ClientOrderId": 3,
            "OrderState": "Rejected",
            "ReceiveTime": 0,
            "OrigQuantity": 1,
            "QuantityExecuted": 0,
            "AvgPrice": 0,
            "ChangeReason": "OtherRejected"
        }
        message = {"m": 3,
                   "i": 2,
                   "n": CONSTANTS.ORDER_STATE_EVENT_ENDPOINT_NAME,
                   "o": json.dumps(payload)}

        ws_connect_mock.return_value = self._create_ws_mock()

        self.exchange.start_tracking_order(order_id="3",
                                           exchange_order_id="9849",
                                           trading_pair="BTC-USD",
                                           trade_type=TradeType.SELL,
                                           price=Decimal("35000"),
                                           amount=Decimal("1"),
                                           order_type=OrderType.LIMIT)

        inflight_order = self.exchange.in_flight_orders["3"]

        self.exchange_task = asyncio.get_event_loop().create_task(
            self.exchange._user_stream_event_listener())
        self.tracker_task = asyncio.get_event_loop().create_task(
            self.exchange._user_stream_tracker.start())

        # Add the authentication response for the websocket
        self._add_successful_authentication_response()
        self.ws_incoming_messages.put_nowait(json.dumps(message))

        # Add a dummy message for the websocket to read and include in the "messages" queue
        self.ws_incoming_messages.put_nowait(json.dumps(self._finalMessage))

        # Wait until the connector finishes processing the message queue
        asyncio.get_event_loop().run_until_complete(self.resume_test_event.wait())
        self.resume_test_event.clear()

        self.assertEqual("Rejected", inflight_order.last_state)
        self.assertTrue(inflight_order.is_failure)
        self.assertFalse(inflight_order.client_order_id in self.exchange.in_flight_orders)
        self.assertTrue(self._is_logged("INFO",
                                        f"The market order {inflight_order.client_order_id} "
                                        f"has failed according to order status event. "
                                        f"Reason: {payload['ChangeReason']}"))
        self.assertEqual(1, len(self.exchange.event_logs))
        failure_event = self.exchange.event_logs[0]
        self.assertEqual(MarketOrderFailureEvent, type(failure_event))
        self.assertEqual(inflight_order.client_order_id, failure_event.order_id)

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_trade_event_fills_and_completes_buy_in_flight_order(self, ws_connect_mock):
        payload = {
            "OMSId": 1,
            "TradeId": 213,
            "OrderId": 9848,
            "AccountId": 4,
            "ClientOrderId": 3,
            "InstrumentId": 1,
            "Side": "Buy",
            "Quantity": 1,
            "Price": 35000,
            "Value": 35000,
            "TradeTime": 635978008210426109,
            "ContraAcctId": 3,
            "OrderTradeRevision": 1,
            "Direction": "NoChange"
        }
        message = {"m": 3,
                   "i": 2,
                   "n": CONSTANTS.ORDER_TRADE_EVENT_ENDPOINT_NAME,
                   "o": json.dumps(payload)}

        ws_connect_mock.return_value = self._create_ws_mock()

        self.exchange.start_tracking_order(order_id="3",
                                           exchange_order_id="9848",
                                           trading_pair="BTC-USD",
                                           trade_type=TradeType.BUY,
                                           price=Decimal("35000"),
                                           amount=Decimal("1"),
                                           order_type=OrderType.LIMIT)

        inflight_order = self.exchange.in_flight_orders["3"]

        self.exchange_task = asyncio.get_event_loop().create_task(
            self.exchange._user_stream_event_listener())
        self.tracker_task = asyncio.get_event_loop().create_task(
            self.exchange._user_stream_tracker.start())

        # Add the authentication response for the websocket
        self._add_successful_authentication_response()
        self.ws_incoming_messages.put_nowait(json.dumps(message))

        # Add a dummy message for the websocket to read and include in the "messages" queue
        self.ws_incoming_messages.put_nowait(json.dumps(self._finalMessage))

        # Wait until the connector finishes processing the message queue
        asyncio.get_event_loop().run_until_complete(self.resume_test_event.wait())
        self.resume_test_event.clear()

        self.assertEqual("FullyExecuted", inflight_order.last_state)
        self.assertIn(payload["TradeId"], inflight_order.trade_id_set)
        self.assertEqual(Decimal(1), inflight_order.executed_amount_base)
        self.assertEqual(Decimal(35000), inflight_order.executed_amount_quote)
        self.assertEqual(inflight_order.executed_amount_base * Decimal("0.02"), inflight_order.fee_paid)

        self.assertFalse(inflight_order.client_order_id in self.exchange.in_flight_orders)
        self.assertTrue(self._is_logged("INFO", f"The {inflight_order.trade_type.name} order "
                                                f"{inflight_order.client_order_id} has completed "
                                                f"according to order status API"))
        self.assertEqual(2, len(self.exchange.event_logs))
        fill_event = self.exchange.event_logs[0]
        self.assertEqual(OrderFilledEvent, type(fill_event))
        self.assertEqual(inflight_order.client_order_id, fill_event.order_id)
        self.assertEqual(inflight_order.trading_pair, fill_event.trading_pair)
        self.assertEqual(inflight_order.trade_type, fill_event.trade_type)
        self.assertEqual(inflight_order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(35000), fill_event.price)
        self.assertEqual(Decimal(1), fill_event.amount)
        self.assertEqual(Decimal("0.02"), fill_event.trade_fee.percent)
        self.assertEqual(0, len(fill_event.trade_fee.flat_fees))
        self.assertEqual("213", fill_event.exchange_trade_id)
        buy_event = self.exchange.event_logs[1]
        self.assertEqual(inflight_order.client_order_id, buy_event.order_id)
        self.assertEqual(inflight_order.base_asset, buy_event.base_asset)
        self.assertEqual(inflight_order.quote_asset, buy_event.quote_asset)
        self.assertEqual(inflight_order.fee_asset, buy_event.fee_asset)
        self.assertEqual(inflight_order.executed_amount_base, buy_event.base_asset_amount)
        self.assertEqual(inflight_order.executed_amount_quote, buy_event.quote_asset_amount)
        self.assertEqual(inflight_order.fee_paid, buy_event.fee_amount)
        self.assertEqual(inflight_order.order_type, buy_event.order_type)
        self.assertEqual(inflight_order.exchange_order_id, buy_event.exchange_order_id)

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_trade_event_fills_and_completes_sell_in_flight_order(self, ws_connect_mock):
        payload = {
            "OMSId": 1,
            "TradeId": 213,
            "OrderId": 9848,
            "AccountId": 4,
            "ClientOrderId": 3,
            "InstrumentId": 1,
            "Side": "Sell",
            "Quantity": 1,
            "Price": 35000,
            "Value": 35000,
            "TradeTime": 635978008210426109,
            "ContraAcctId": 3,
            "OrderTradeRevision": 1,
            "Direction": "NoChange"
        }
        message = {"m": 3,
                   "i": 2,
                   "n": CONSTANTS.ORDER_TRADE_EVENT_ENDPOINT_NAME,
                   "o": json.dumps(payload)}

        ws_connect_mock.return_value = self._create_ws_mock()

        self.exchange.start_tracking_order(order_id="3",
                                           exchange_order_id="9848",
                                           trading_pair="BTC-USD",
                                           trade_type=TradeType.SELL,
                                           price=Decimal("35000"),
                                           amount=Decimal("1"),
                                           order_type=OrderType.LIMIT)

        inflight_order = self.exchange.in_flight_orders["3"]

        self.exchange_task = asyncio.get_event_loop().create_task(
            self.exchange._user_stream_event_listener())
        self.tracker_task = asyncio.get_event_loop().create_task(
            self.exchange._user_stream_tracker.start())

        # Add the authentication response for the websocket
        self._add_successful_authentication_response()
        self.ws_incoming_messages.put_nowait(json.dumps(message))

        # Add a dummy message for the websocket to read and include in the "messages" queue
        self.ws_incoming_messages.put_nowait(json.dumps(self._finalMessage))

        # Wait until the connector finishes processing the message queue
        asyncio.get_event_loop().run_until_complete(self.resume_test_event.wait())
        self.resume_test_event.clear()

        self.assertEqual("FullyExecuted", inflight_order.last_state)
        self.assertIn(payload["TradeId"], inflight_order.trade_id_set)
        self.assertEqual(Decimal(1), inflight_order.executed_amount_base)
        self.assertEqual(Decimal(35000), inflight_order.executed_amount_quote)
        self.assertEqual(inflight_order.executed_amount_base * inflight_order.executed_amount_quote * Decimal("0.02"),
                         inflight_order.fee_paid)

        self.assertFalse(inflight_order.client_order_id in self.exchange.in_flight_orders)
        self.assertTrue(self._is_logged("INFO", f"The {inflight_order.trade_type.name} order "
                                                f"{inflight_order.client_order_id} has completed "
                                                f"according to order status API"))
        self.assertEqual(2, len(self.exchange.event_logs))
        fill_event = self.exchange.event_logs[0]
        self.assertEqual(OrderFilledEvent, type(fill_event))
        self.assertEqual(inflight_order.client_order_id, fill_event.order_id)
        self.assertEqual(inflight_order.trading_pair, fill_event.trading_pair)
        self.assertEqual(inflight_order.trade_type, fill_event.trade_type)
        self.assertEqual(inflight_order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(35000), fill_event.price)
        self.assertEqual(Decimal(1), fill_event.amount)
        self.assertEqual(Decimal("0.02"), fill_event.trade_fee.percent)
        self.assertEqual(0, len(fill_event.trade_fee.flat_fees))
        self.assertEqual("213", fill_event.exchange_trade_id)
        buy_event = self.exchange.event_logs[1]
        self.assertEqual(inflight_order.client_order_id, buy_event.order_id)
        self.assertEqual(inflight_order.base_asset, buy_event.base_asset)
        self.assertEqual(inflight_order.quote_asset, buy_event.quote_asset)
        self.assertEqual(inflight_order.fee_asset, buy_event.fee_asset)
        self.assertEqual(inflight_order.executed_amount_base, buy_event.base_asset_amount)
        self.assertEqual(inflight_order.executed_amount_quote, buy_event.quote_asset_amount)
        self.assertEqual(inflight_order.fee_paid, buy_event.fee_amount)
        self.assertEqual(inflight_order.order_type, buy_event.order_type)
        self.assertEqual(inflight_order.exchange_order_id, buy_event.exchange_order_id)

    def test_tick_initial_tick_successful(self):
        start_ts: float = time.time() * 1e3

        self.exchange.tick(start_ts)
        self.assertEqual(start_ts, self.exchange._last_timestamp)
        self.assertTrue(self.exchange._poll_notifier.is_set())

    @patch("time.time")
    def test_tick_subsequent_tick_within_short_poll_interval(self, mock_ts):
        # Assumes user stream tracker has NOT been receiving messages, Hence SHORT_POLL_INTERVAL in use
        start_ts: float = self.start_timestamp
        next_tick: float = start_ts + (self.exchange.SHORT_POLL_INTERVAL - 1)

        mock_ts.return_value = start_ts
        self.exchange.tick(start_ts)
        self.assertEqual(start_ts, self.exchange._last_timestamp)
        self.assertTrue(self.exchange._poll_notifier.is_set())

        self._simulate_reset_poll_notifier()

        mock_ts.return_value = next_tick
        self.exchange.tick(next_tick)
        self.assertEqual(next_tick, self.exchange._last_timestamp)
        self.assertFalse(self.exchange._poll_notifier.is_set())

    @patch("time.time")
    def test_tick_subsequent_tick_exceed_short_poll_interval(self, mock_ts):
        # Assumes user stream tracker has NOT been receiving messages, Hence SHORT_POLL_INTERVAL in use
        start_ts: float = self.start_timestamp
        next_tick: float = start_ts + (self.exchange.SHORT_POLL_INTERVAL + 1)

        mock_ts.return_value = start_ts
        self.exchange.tick(start_ts)
        self.assertEqual(start_ts, self.exchange._last_timestamp)
        self.assertTrue(self.exchange._poll_notifier.is_set())

        self._simulate_reset_poll_notifier()

        mock_ts.return_value = next_tick
        self.exchange.tick(next_tick)
        self.assertEqual(next_tick, self.exchange._last_timestamp)
        self.assertTrue(self.exchange._poll_notifier.is_set())

    @patch("time.time")
    def test_tick_subsequent_tick_within_long_poll_interval(self, mock_time):

        start_ts: float = self.start_timestamp
        next_tick: float = start_ts + (self.exchange.LONG_POLL_INTERVAL - 1)

        mock_time.return_value = start_ts
        self.exchange.tick(start_ts)
        self.assertEqual(start_ts, self.exchange._last_timestamp)
        self.assertTrue(self.exchange._poll_notifier.is_set())

        # Simulate last message received 1 sec ago
        self._simulate_ws_message_received(next_tick - 1)
        self._simulate_reset_poll_notifier()

        mock_time.return_value = next_tick
        self.exchange.tick(next_tick)
        self.assertEqual(next_tick, self.exchange._last_timestamp)
        self.assertFalse(self.exchange._poll_notifier.is_set())

    @patch("time.time")
    def test_tick_subsequent_tick_exceed_long_poll_interval(self, mock_time):
        # Assumes user stream tracker has been receiving messages, Hence LONG_POLL_INTERVAL in use
        start_ts: float = self.start_timestamp
        next_tick: float = start_ts + (self.exchange.LONG_POLL_INTERVAL - 1)

        mock_time.return_value = start_ts
        self.exchange.tick(start_ts)
        self.assertEqual(start_ts, self.exchange._last_timestamp)
        self.assertTrue(self.exchange._poll_notifier.is_set())

        self._simulate_ws_message_received(start_ts)
        self._simulate_reset_poll_notifier()

        mock_time.return_value = next_tick
        self.exchange.tick(next_tick)
        self.assertEqual(next_tick, self.exchange._last_timestamp)
        self.assertTrue(self.exchange._poll_notifier.is_set())

    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_get_account_id(self, mock_api):
        account_id = 1
        mock_response = [{'OMSID': '1',
                          'AccountId': str(account_id),
                          'AccountName': self._account_name,
                          'AccountHandle': None,
                          'FirmId': None,
                          'FirmName': None,
                          'AccountType': 'Asset',
                          'FeeGroupId': '0',
                          'ParentID': '0',
                          'RiskType': 'Normal',
                          'VerificationLevel': '2',
                          'CreditTier': '0',
                          'FeeProductType': 'BaseProduct',
                          'FeeProduct': '0',
                          'RefererId': '328',
                          'LoyaltyProductId': '0',
                          'LoyaltyEnabled': False,
                          'PriceTier': '0',
                          'Frozen': False}]
        self._set_mock_response(mock_api, 200, mock_response)

        task = asyncio.get_event_loop().create_task(
            self.exchange._get_account_id()
        )
        resp = asyncio.get_event_loop().run_until_complete(task)
        self.assertEqual(resp, account_id)

    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_get_account_id_when_account_does_not_exist(self, mock_api):
        account_id = 1
        mock_response = [{'OMSID': '1',
                          'AccountId': str(account_id),
                          'AccountName': 'unexistent_name',
                          'AccountHandle': None,
                          'FirmId': None,
                          'FirmName': None,
                          'AccountType': 'Asset',
                          'FeeGroupId': '0',
                          'ParentID': '0',
                          'RiskType': 'Normal',
                          'VerificationLevel': '2',
                          'CreditTier': '0',
                          'FeeProductType': 'BaseProduct',
                          'FeeProduct': '0',
                          'RefererId': '328',
                          'LoyaltyProductId': '0',
                          'LoyaltyEnabled': False,
                          'PriceTier': '0',
                          'Frozen': False}]
        self._set_mock_response(mock_api, 200, mock_response)

        task = asyncio.get_event_loop().create_task(
            self.exchange._get_account_id()
        )
        resp = asyncio.get_event_loop().run_until_complete(task)

        self.assertTrue(self._is_logged('ERROR', f"There is no account named {self._account_name} "
                                                 f"associated with the current NDAX user"))
        self.assertIsNone(resp)

    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_update_balances(self, mock_api):

        self.assertEqual(0, len(self.exchange._account_balances))
        self.assertEqual(0, len(self.exchange._account_available_balances))

        # We force the account_id to avoid the account id resolution request
        self.exchange._account_id = 1

        mock_response: List[Dict[str, Any]] = [
            {
                "ProductSymbol": self.base_asset,
                "Amount": 10.0,
                "Hold": 5.0
            },
        ]

        self._set_mock_response(mock_api, 200, mock_response)

        self.exchange_task = asyncio.get_event_loop().create_task(
            self.exchange._update_balances()
        )
        asyncio.get_event_loop().run_until_complete(self.exchange_task)

        self.assertEqual(Decimal(str(10.0)), self.exchange.get_balance(self.base_asset))

    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_update_order_status(self, mock_order_status, mock_trade_history):

        # Simulates order being tracked
        order: NdaxInFlightOrder = NdaxInFlightOrder("0", "2628", self.trading_pair, OrderType.LIMIT, TradeType.SELL,
                                                     Decimal(str(41720.83)), Decimal("1"))
        self.exchange._in_flight_orders.update({
            order.client_order_id: order
        })
        self.assertTrue(1, len(self.exchange.in_flight_orders))

        # Add FullyExecuted GetOrderStatus API Response
        self._set_mock_response(mock_order_status, 200, {
            "Side": "Sell",
            "OrderId": 2628,
            "Price": 41720.830000000000000000000000,
            "Quantity": 0.0000000000000000000000000000,
            "DisplayQuantity": 0.0000000000000000000000000000,
            "Instrument": 5,
            "Account": 528,
            "AccountName": "hbot",
            "OrderType": "Limit",
            "ClientOrderId": 0,
            "OrderState": "FullyExecuted",
            "ReceiveTime": 1627380780887,
            "ReceiveTimeTicks": 637629775808866338,
            "LastUpdatedTime": 1627380783860,
            "LastUpdatedTimeTicks": 637629775838598558,
            "OrigQuantity": 1.0000000000000000000000000000,
            "QuantityExecuted": 1.0000000000000000000000000000,
            "GrossValueExecuted": 41720.830000000000000000000000,
            "ExecutableValue": 0.0000000000000000000000000000,
            "AvgPrice": 41720.830000000000000000000000,
            "CounterPartyId": 0,
            "ChangeReason": "Trade",
            "OrigOrderId": 2628,
            "OrigClOrdId": 0,
            "EnteredBy": 492,
            "UserName": "hbot",
            "IsQuote": False,
            "InsideAsk": 41720.830000000000000000000000,
            "InsideAskSize": 0.9329960000000000000000000000,
            "InsideBid": 41718.340000000000000000000000,
            "InsideBidSize": 0.0632560000000000000000000000,
            "LastTradePrice": 41720.830000000000000000000000,
            "RejectReason": "",
            "IsLockedIn": False,
            "CancelReason": "",
            "OrderFlag": "AddedToBook, RemovedFromBook",
            "UseMargin": False,
            "StopPrice": 0.0000000000000000000000000000,
            "PegPriceType": "Last",
            "PegOffset": 0.0000000000000000000000000000,
            "PegLimitOffset": 0.0000000000000000000000000000,
            "IpAddress": "103.6.151.12",
            "ClientOrderIdUuid": None,
            "OMSId": 1
        })

        # Add TradeHistory API Response
        self._set_mock_response(mock_trade_history, 200, [{
            "OMSId": 1,
            "ExecutionId": 245936,
            "TradeId": 252851,
            "OrderId": 2628,
            "AccountId": 528,
            "AccountName": "hbot",
            "SubAccountId": 0,
            "ClientOrderId": 0,
            "InstrumentId": 5,
            "Side": "Sell",
            "OrderType": "Limit",
            "Quantity": 1.0000000000000000000000000000,
            "RemainingQuantity": 0.0000000000000000000000000000,
            "Price": 41720.830000000000000000000000,
            "Value": 41720.830000000000000000000000,
            "CounterParty": "0",
            "OrderTradeRevision": 1,
            "Direction": "NoChange",
            "IsBlockTrade": False,
            "Fee": 834.4,
            "FeeProductId": 5,
            "OrderOriginator": 492,
            "UserName": "hbot",
            "TradeTimeMS": 1627380783859,
            "MakerTaker": "Maker",
            "AdapterTradeId": 0,
            "InsideBid": 41718.340000000000000000000000,
            "InsideBidSize": 0.0632560000000000000000000000,
            "InsideAsk": 41720.830000000000000000000000,
            "InsideAskSize": 0.9329960000000000000000000000,
            "IsQuote": False,
            "CounterPartyClientUserId": 0,
            "NotionalProductId": 2,
            "NotionalRate": 0.7953538608862469000000000000,
            "NotionalValue": 480.28818328452511800486539800,
            "NotionalHoldAmount": 0,
            "TradeTime": 637629775838593249
        }])

        # Simulate _trading_pair_id_map initialized.
        self.exchange._order_book_tracker.data_source._trading_pair_id_map.update({
            self.trading_pair: 5
        })

        self.exchange_task = asyncio.get_event_loop().create_task(self.exchange._update_order_status())
        asyncio.get_event_loop().run_until_complete(self.exchange_task)
        self.assertEqual(0, len(self.exchange.in_flight_orders))

    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_update_order_status_error_response(self, mock_api):

        # Simulates order being tracked
        order: NdaxInFlightOrder = NdaxInFlightOrder("0", "2628", self.trading_pair, OrderType.LIMIT, TradeType.SELL,
                                                     Decimal(str(41720.83)), Decimal("1"))
        self.exchange._in_flight_orders.update({
            order.client_order_id: order
        })
        self.assertTrue(1, len(self.exchange.in_flight_orders))

        # Add FullyExecuted GetOrderStatus API Response
        self._set_mock_response(mock_api, 200, {
            "Side": "Sell",
            "OrderId": 2628,
            "Price": 41720.830000000000000000000000,
            "Quantity": 0.0000000000000000000000000000,
            "DisplayQuantity": 0.0000000000000000000000000000,
            "Instrument": 5,
            "Account": 528,
            "AccountName": "hbot",
            "OrderType": "Limit",
            "ClientOrderId": 0,
            "OrderState": "Working",
            "ReceiveTime": 1627380780887,
            "ReceiveTimeTicks": 637629775808866338,
            "LastUpdatedTime": 1627380783860,
            "LastUpdatedTimeTicks": 637629775838598558,
            "OrigQuantity": 1.0000000000000000000000000000,
            "QuantityExecuted": 1.0000000000000000000000000000,
            "GrossValueExecuted": 41720.830000000000000000000000,
            "ExecutableValue": 0.0000000000000000000000000000,
            "AvgPrice": 41720.830000000000000000000000,
            "CounterPartyId": 0,
            "ChangeReason": "Trade",
            "OrigOrderId": 2628,
            "OrigClOrdId": 0,
            "EnteredBy": 492,
            "UserName": "hbot",
            "IsQuote": False,
            "InsideAsk": 41720.830000000000000000000000,
            "InsideAskSize": 0.9329960000000000000000000000,
            "InsideBid": 41718.340000000000000000000000,
            "InsideBidSize": 0.0632560000000000000000000000,
            "LastTradePrice": 41720.830000000000000000000000,
            "RejectReason": "",
            "IsLockedIn": False,
            "CancelReason": "",
            "OrderFlag": "AddedToBook, RemovedFromBook",
            "UseMargin": False,
            "StopPrice": 0.0000000000000000000000000000,
            "PegPriceType": "Last",
            "PegOffset": 0.0000000000000000000000000000,
            "PegLimitOffset": 0.0000000000000000000000000000,
            "IpAddress": "103.6.151.12",
            "ClientOrderIdUuid": None,
            "OMSId": 1
        })

        # Add TradeHistory API Response
        self._set_mock_response(mock_api, 200, {
            "result": False,
            "errormsg": "Invalid Request",
            "errorcode": 100,
            "detail": None
        })

        # Simulate _trading_pair_id_map initialized.
        self.exchange._order_book_tracker.data_source._trading_pair_id_map.update({
            self.trading_pair: 5
        })

        self.exchange_task = asyncio.get_event_loop().create_task(self.exchange._update_order_status())
        asyncio.get_event_loop().run_until_complete(self.exchange_task)
        self.assertEqual(1, len(self.exchange.in_flight_orders))

        self.assertEqual(0, len(self.exchange.in_flight_orders[order.client_order_id].trade_id_set))

    @patch("hummingbot.connector.exchange.ndax.ndax_exchange.NdaxExchange._update_balances", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.ndax.ndax_exchange.NdaxExchange._update_order_status", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.ndax.ndax_exchange.NdaxExchange.current_timestamp", new_callable=PropertyMock)
    def test_status_polling_loop(self, mock_ts, mock_update_order_status, mock_balances):
        mock_balances.return_value = None
        mock_update_order_status.return_value = None

        ts: float = time.time()
        mock_ts.return_value = ts
        self.exchange._current_timestamp = ts

        with self.assertRaises(asyncio.TimeoutError):
            self.exchange_task = asyncio.get_event_loop().create_task(
                self.exchange._status_polling_loop()
            )

            # Add small delay to ensure an API request is "called"
            asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.5))
            self.exchange._poll_notifier.set()

            asyncio.get_event_loop().run_until_complete(asyncio.wait_for(self.exchange_task, 2.0))

        self.assertEqual(ts, self.exchange._last_poll_timestamp)

    @patch("aiohttp.ClientSession.get")
    @patch("hummingbot.connector.exchange.ndax.ndax_exchange.NdaxExchange.current_timestamp", new_callable=PropertyMock)
    def test_status_polling_loop_cancels(self, mock_ts, mock_api):
        mock_api.side_effect = asyncio.CancelledError

        ts: float = time.time()
        mock_ts.return_value = ts
        self.exchange._current_timestamp = ts

        with self.assertRaises(asyncio.CancelledError):
            self.exchange_task = asyncio.get_event_loop().create_task(
                self.exchange._status_polling_loop()
            )
            # Add small delay to ensure _poll_notifier is set
            asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.5))
            self.exchange._poll_notifier.set()

            asyncio.get_event_loop().run_until_complete(self.exchange_task)

        self.assertEqual(0, self.exchange._last_poll_timestamp)

    @patch("hummingbot.connector.exchange.ndax.ndax_exchange.NdaxExchange._update_balances", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.ndax.ndax_exchange.NdaxExchange._update_order_status", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.ndax.ndax_exchange.NdaxExchange.current_timestamp", new_callable=PropertyMock)
    def test_status_polling_loop_exception_raised(self, mock_ts, mock_update_order_status, mock_balances):
        mock_balances.side_effect = lambda: self._create_exception_and_unlock_test_with_event(
            Exception("Dummy test error"))
        mock_update_order_status.side_effect = lambda: self._create_exception_and_unlock_test_with_event(
            Exception("Dummy test error"))

        ts: float = time.time()
        mock_ts.return_value = ts
        self.exchange._current_timestamp = ts

        self.exchange_task = asyncio.get_event_loop().create_task(
            self.exchange._status_polling_loop()
        )

        # Add small delay to ensure an API request is "called"
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.5))
        self.exchange._poll_notifier.set()

        asyncio.get_event_loop().run_until_complete(self.resume_test_event.wait())

        self.assertEqual(0, self.exchange._last_poll_timestamp)
        self._is_logged("ERROR", "Unexpected error while in status polling loop. Error: ")

    def test_format_trading_rules_success(self):
        instrument_info: List[Dict[str, Any]] = [{
            "Product1Symbol": self.base_asset,
            "Product2Symbol": self.quote_asset,
            "QuantityIncrement": 0.0000010000000000000000000000,
            "MinimumQuantity": 0.0001000000000000000000000000,
            "MinimumPrice": 15000.000000000000000000000000,
            "PriceIncrement": 0.0001,
        }
        ]

        result: Dict[str, TradingRule] = self.exchange._format_trading_rules(instrument_info)
        self.assertTrue(self.trading_pair in result)

    def test_format_trading_rules_failure(self):
        # Simulate invalid API response
        instrument_info: List[Dict[str, Any]] = [{}]

        result: Dict[str, TradingRule] = self.exchange._format_trading_rules(instrument_info)
        self.assertTrue(self.trading_pair not in result)
        self.assertTrue(self._is_logged("ERROR", "Error parsing the trading pair rule: {}. Skipping..."))

    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_update_trading_rules(self, mock_api):
        mock_response: List[Dict[str, Any]] = [
            {
                "Product1Symbol": self.base_asset,
                "Product2Symbol": self.quote_asset,
                "QuantityIncrement": 0.01,
                "MinimumQuantity": 0.0001,
                "MinimumPrice": 15000.0,
                "PriceIncrement": 0.0001,
            }
        ]

        self._set_mock_response(mock_api, 200, mock_response)

        task = asyncio.get_event_loop().create_task(
            self.exchange._update_trading_rules()
        )
        asyncio.get_event_loop().run_until_complete(task)

        self.assertTrue(self.trading_pair in self.exchange.trading_rules)

        trading_rule: TradingRule = self.exchange.trading_rules[self.trading_pair]
        self.assertEqual(trading_rule.min_order_size, Decimal(str(mock_response[0]["MinimumQuantity"])))
        self.assertEqual(trading_rule.min_price_increment, Decimal(str(mock_response[0]["PriceIncrement"])))
        self.assertEqual(trading_rule.min_base_amount_increment, Decimal(str(mock_response[0]["QuantityIncrement"])))

    @patch("hummingbot.connector.exchange.ndax.ndax_exchange.NdaxExchange._update_trading_rules",
           new_callable=AsyncMock)
    def test_trading_rules_polling_loop(self, mock_update):
        # No Side Effects expected
        mock_update.return_value = None
        with self.assertRaises(asyncio.TimeoutError):
            self.exchange_task = asyncio.get_event_loop().create_task(self.exchange._trading_rules_polling_loop())

            asyncio.get_event_loop().run_until_complete(
                asyncio.wait_for(self.exchange_task, 1.0)
            )

    @patch("hummingbot.connector.exchange.ndax.ndax_exchange.NdaxExchange._update_trading_rules",
           new_callable=AsyncMock)
    def test_trading_rules_polling_loop_cancels(self, mock_update):
        mock_update.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.exchange_task = asyncio.get_event_loop().create_task(
                self.exchange._trading_rules_polling_loop()
            )

            asyncio.get_event_loop().run_until_complete(self.exchange_task)

        self.assertEqual(0, self.exchange._last_poll_timestamp)

    @patch("hummingbot.connector.exchange.ndax.ndax_exchange.NdaxExchange._update_trading_rules",
           new_callable=AsyncMock)
    def test_trading_rules_polling_loop_exception_raised(self, mock_update):
        mock_update.side_effect = lambda: self._create_exception_and_unlock_test_with_event(
            Exception("Dummy test error"))

        self.exchange_task = asyncio.get_event_loop().create_task(
            self.exchange._trading_rules_polling_loop()
        )

        asyncio.get_event_loop().run_until_complete(self.resume_test_event.wait())

        self._is_logged("ERROR", "Unexpected error while fetching trading rules. Error: ")

    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_check_network_succeeds_when_ping_replies_pong(self, mock_api):
        mock_response = {"msg": "PONG"}
        self._set_mock_response(mock_api, 200, mock_response)

        result = asyncio.get_event_loop().run_until_complete(self.exchange.check_network())

        self.assertEqual(NetworkStatus.CONNECTED, result)

    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_check_network_fails_when_ping_does_not_reply_pong(self, mock_api):
        mock_response = {"msg": "NOT-PONG"}
        self._set_mock_response(mock_api, 200, mock_response)

        result = asyncio.get_event_loop().run_until_complete(self.exchange.check_network())
        self.assertEqual(NetworkStatus.NOT_CONNECTED, result)

        mock_response = {}
        self._set_mock_response(mock_api, 200, mock_response)

        result = asyncio.get_event_loop().run_until_complete(self.exchange.check_network())
        self.assertEqual(NetworkStatus.NOT_CONNECTED, result)

    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_check_network_fails_when_ping_returns_error_code(self, mock_api):
        mock_response = {"msg": "PONG"}
        self._set_mock_response(mock_api, 404, mock_response)

        result = asyncio.get_event_loop().run_until_complete(self.exchange.check_network())

        self.assertEqual(NetworkStatus.NOT_CONNECTED, result)

    def test_get_order_book_for_valid_trading_pair(self):
        dummy_order_book = NdaxOrderBook()
        self.exchange._order_book_tracker.order_books["BTC-USDT"] = dummy_order_book
        self.assertEqual(dummy_order_book, self.exchange.get_order_book("BTC-USDT"))

    def test_get_order_book_for_invalid_trading_pair_raises_error(self):
        self.assertRaisesRegex(ValueError,
                               "No order book exists for 'BTC-USDT'",
                               self.exchange.get_order_book,
                               "BTC-USDT")

    @patch("hummingbot.connector.exchange.ndax.ndax_exchange.NdaxExchange._create_order", new_callable=AsyncMock)
    def test_buy(self, mock_create):
        mock_create.side_effect = None
        order_details = [
            self.trading_pair,
            Decimal(1.0),
            Decimal(10.0),
            OrderType.LIMIT,
        ]

        # Note: BUY simply returns immediately with the client order id.
        order_id: str = self.exchange.buy(*order_details)

        # Order ID is simply a timestamp. The assertion below checks if it is created within 1 sec
        self.assertTrue((int(time.time() * 1e3) - int(order_id)) < 1 * 1e3)

    def test_sell(self):
        order_details = [
            self.trading_pair,
            Decimal(1.0),
            Decimal(10.0),
            OrderType.LIMIT,
        ]

        # Note: SELL simply returns immediately with the client order id.
        order_id: str = self.exchange.buy(*order_details)

        # Order ID is simply a timestamp. The assertion below checks if it is created within 1 sec
        self.assertTrue((int(time.time() * 1e3) - int(order_id)) < 1 * 1e3)

    @patch(
        "hummingbot.connector.exchange.ndax.ndax_api_order_book_data_source.NdaxAPIOrderBookDataSource.get_instrument_ids",
        new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    def test_create_limit_order(self, mock_post, mock_get_instrument_ids):
        mock_get_instrument_ids.return_value = {
            self.trading_pair: 5
        }

        expected_response = {
            "status": "Accepted",
            "errormsg": "",
            "OrderId": 123
        }

        self._set_mock_response(mock_post, 200, expected_response)

        self._simulate_trading_rules_initialized()

        order_details = [
            TradeType.BUY,
            str(1),
            self.trading_pair,
            Decimal(1.0),
            Decimal(10.0),
            OrderType.LIMIT,
        ]

        self.assertEqual(0, len(self.exchange.in_flight_orders))
        asyncio.get_event_loop().run_until_complete(
            self.exchange._create_order(*order_details)
        )

        self.assertEqual(1, len(self.exchange.in_flight_orders))
        self._is_logged("INFO",
                        f"Created {OrderType.LIMIT.name} {TradeType.BUY.name} order {123} for {Decimal(1.0)} {self.trading_pair}")

        tracked_order: NdaxInFlightOrder = self.exchange.in_flight_orders["1"]
        self.assertEqual(tracked_order.client_order_id, "1")
        self.assertEqual(tracked_order.exchange_order_id, "123")
        self.assertEqual(tracked_order.last_state, "Working")
        self.assertEqual(tracked_order.trading_pair, self.trading_pair)
        self.assertEqual(tracked_order.price, Decimal(10.0))
        self.assertEqual(tracked_order.amount, Decimal(1.0))
        self.assertEqual(tracked_order.trade_type, TradeType.BUY)

    @patch(
        "hummingbot.connector.exchange.ndax.ndax_api_order_book_data_source.NdaxAPIOrderBookDataSource.get_instrument_ids",
        new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    def test_create_market_order(self, mock_post, mock_get_instrument_ids):
        mock_get_instrument_ids.return_value = {
            self.trading_pair: 5
        }

        expected_response = {
            "status": "Accepted",
            "errormsg": "",
            "OrderId": 123
        }

        self._set_mock_response(mock_post, 200, expected_response)

        self._simulate_trading_rules_initialized()

        order_details = [
            TradeType.BUY,
            str(1),
            self.trading_pair,
            Decimal(1.0),
            None,
            OrderType.MARKET,
        ]

        self.assertEqual(0, len(self.exchange.in_flight_orders))
        asyncio.get_event_loop().run_until_complete(
            self.exchange._create_order(*order_details)
        )

        self.assertEqual(1, len(self.exchange.in_flight_orders))
        self._is_logged("INFO",
                        f"Created {OrderType.MARKET.name} {TradeType.BUY.name} order {123} for {Decimal(1.0)} {self.trading_pair}")

        tracked_order: NdaxInFlightOrder = self.exchange.in_flight_orders["1"]
        self.assertEqual(tracked_order.client_order_id, "1")
        self.assertEqual(tracked_order.exchange_order_id, "123")
        self.assertEqual(tracked_order.last_state, "Working")
        self.assertEqual(tracked_order.trading_pair, self.trading_pair)
        self.assertEqual(tracked_order.amount, Decimal(1.0))
        self.assertEqual(tracked_order.trade_type, TradeType.BUY)

    @patch(
        "hummingbot.connector.exchange.ndax.ndax_api_order_book_data_source.NdaxAPIOrderBookDataSource.get_instrument_ids",
        new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    def test_create_order_cancels(self, mock_post, mock_get_instrument_ids):
        mock_get_instrument_ids.return_value = {
            self.trading_pair: 5
        }

        mock_post.side_effect = asyncio.CancelledError

        self._simulate_trading_rules_initialized()

        order_details = [
            TradeType.BUY,
            str(1),
            self.trading_pair,
            Decimal(1.0),
            Decimal(10.0),
            OrderType.LIMIT,
        ]

        self.assertEqual(0, len(self.exchange.in_flight_orders))
        with self.assertRaises(asyncio.CancelledError):
            asyncio.get_event_loop().run_until_complete(
                self.exchange._create_order(*order_details)
            )

        # InFlightOrder is still 1 since we do not know exactly where did the Cancel occur.
        self.assertEqual(1, len(self.exchange.in_flight_orders))

    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    @patch(
        "hummingbot.connector.exchange.ndax.ndax_api_order_book_data_source.NdaxAPIOrderBookDataSource.get_instrument_ids",
        new_callable=AsyncMock)
    def test_create_order_below_min_order_size_exception_raised(self, mock_get_instrument_ids, mock_main_app):
        mock_get_instrument_ids.return_value = {
            self.trading_pair: 5
        }

        self._simulate_trading_rules_initialized()

        order_details = [
            TradeType.BUY,
            str(1),
            self.trading_pair,
            Decimal(str(0.0000001)),
            Decimal(10.0),
            OrderType.LIMIT,
        ]

        self.assertEqual(0, len(self.exchange.in_flight_orders))

        self.exchange_task = asyncio.get_event_loop().create_task(
            self.exchange._create_order(*order_details)
        )

        asyncio.get_event_loop().run_until_complete(self.exchange_task)

        self.assertEqual(0, len(self.exchange.in_flight_orders))
        self._is_logged("NETWORK", f"Error submitting {TradeType.BUY.name} {OrderType.LIMIT.name} order to NDAX")

    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    @patch(
        "hummingbot.connector.exchange.ndax.ndax_api_order_book_data_source.NdaxAPIOrderBookDataSource.get_instrument_ids",
        new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    def test_create_order_api_returns_error_exception_raised(self, mock_post, mock_get_instrument_ids, mock_main_app):
        mock_get_instrument_ids.return_value = {
            self.trading_pair: 5
        }

        expected_response = {
            "status": "Rejected",
            "errormsg": "Some Error Msg",
            "OrderId": 123
        }

        self._set_mock_response(mock_post, 200, expected_response)

        self._simulate_trading_rules_initialized()

        order_details = [
            TradeType.BUY,
            str(1),
            self.trading_pair,
            Decimal(1.0),
            Decimal(10.0),
            OrderType.LIMIT,
        ]

        self.assertEqual(0, len(self.exchange.in_flight_orders))
        asyncio.get_event_loop().run_until_complete(
            self.exchange._create_order(*order_details)
        )

        self.assertEqual(0, len(self.exchange.in_flight_orders))
        self._is_logged("NETWORK",
                        f"Error submitting {TradeType.BUY.name} {OrderType.LIMIT.name} order to NDAX")

    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    def test_execute_cancel_success(self, mock_cancel):
        order: NdaxInFlightOrder = NdaxInFlightOrder(
            client_order_id="0",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10.0),
            amount=Decimal(1.0))

        self.exchange._in_flight_orders.update({
            order.client_order_id: order
        })

        mock_response = {
            "result": True,
            "errormsg": None,
            "errorcode": 0,
            "detail": None
        }

        self._set_mock_response(mock_cancel, 200, mock_response)

        result = asyncio.new_event_loop().run_until_complete(
            self.exchange._execute_cancel(self.trading_pair, order.client_order_id)
        )

        self.assertEqual(result, order.client_order_id)

    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_execute_cancel_all_success(self, mock_get_request, mock_post_request):
        order: NdaxInFlightOrder = NdaxInFlightOrder(
            client_order_id="0",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10.0),
            amount=Decimal(1.0))

        self.exchange._in_flight_orders.update({
            order.client_order_id: order
        })

        # Simulate _trading_pair_id_map initialized.
        self.exchange._order_book_tracker.data_source._trading_pair_id_map.update({
            self.trading_pair: 5
        })

        mock_open_orders_response = [
            {
                "Side": "Buy",
                "OrderId": 123,
                "Price": 10.0,
                "Quantity": 1.0,
                "DisplayQuantity": 1.0,
                "Instrument": 5,
                "Account": 1,
                "OrderType": "Limit",
                "ClientOrderId": 0,
                "OrderState": "Working",
                "ReceiveTime": 0,
                "ReceiveTimeTicks": 0,
                "OrigQuantity": 1.0,
                "QuantityExecuted": 0.0,
                "AvgPrice": 0.0,
                "CounterPartyId": 0,
                "ChangeReason": "Unknown",
                "OrigOrderId": 0,
                "OrigClOrdId": 0,
                "EnteredBy": 0,
                "IsQuote": False,
                "InsideAsk": 0.0,
                "InsideAskSize": 0.0,
                "InsideBid": 0.0,
                "InsideBidSize": 0.0,
                "LastTradePrice": 0.0,
                "RejectReason": "",
                "IsLockedIn": False,
                "CancelReason": "",
                "OMSId": 1
            },
        ]
        self._set_mock_response(mock_get_request, 200, mock_open_orders_response)

        mock_response = {
            "result": True,
            "errormsg": None,
            "errorcode": 0,
            "detail": None
        }
        self._set_mock_response(mock_post_request, 200, mock_response)

        cancellation_results = asyncio.new_event_loop().run_until_complete(
            self.exchange.cancel_all(10)
        )

        self.assertEqual(1, len(cancellation_results))
        self.assertEqual("0", cancellation_results[0].order_id)
        self.assertTrue(cancellation_results[0].success)

    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    def test_execute_cancel_fail(self, mock_cancel, mock_main_app):
        order: NdaxInFlightOrder = NdaxInFlightOrder(
            client_order_id="0",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10.0),
            amount=Decimal(1.0))

        self.exchange._in_flight_orders.update({
            order.client_order_id: order
        })

        # Regardless of Response, the method returns the client_order_id
        # Actual cancellation verfication is done using WebSocket message or REST API.
        mock_response = {
            "result": False,
            "errormsg": "Invalid Request",
            "errorcode": 100,
            "detail": None
        }

        self._set_mock_response(mock_cancel, 200, mock_response)

        result = asyncio.new_event_loop().run_until_complete(
            self.exchange._execute_cancel(self.trading_pair, order.client_order_id)
        )

        self.assertIsNone(result)

    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    def test_execute_cancel_cancels(self, mock_cancel):
        order: NdaxInFlightOrder = NdaxInFlightOrder(
            client_order_id="0",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10.0),
            amount=Decimal(1.0))

        self.exchange._in_flight_orders.update({
            order.client_order_id: order
        })

        mock_cancel.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            asyncio.new_event_loop().run_until_complete(
                self.exchange._execute_cancel(self.trading_pair, order.client_order_id)
            )

    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    @patch("hummingbot.connector.exchange.ndax.ndax_exchange.NdaxExchange._api_request", new_callable=AsyncMock)
    def test_execute_cancel_exception_raised(self, mock_request, mock_main_app):
        order: NdaxInFlightOrder = NdaxInFlightOrder(
            client_order_id="0",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10.0),
            amount=Decimal(1.0))

        self.exchange._in_flight_orders.update({
            order.client_order_id: order
        })

        mock_request.side_effect = lambda: self._create_exception_and_unlock_test_with_event(
            Exception("Dummy test error"))

        asyncio.new_event_loop().run_until_complete(
            self.exchange._execute_cancel(self.trading_pair, order.client_order_id)
        )

        self._is_logged("ERROR", f"Failed to cancel order {order.client_order_id}")

    @patch("hummingbot.connector.exchange.ndax.ndax_exchange.NdaxExchange._execute_cancel", new_callable=AsyncMock)
    def test_cancel(self, mock_cancel):
        mock_cancel.return_value = None

        order: NdaxInFlightOrder = NdaxInFlightOrder(
            client_order_id="0",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10.0),
            amount=Decimal(1.0))

        self.exchange._in_flight_orders.update({
            order.client_order_id: order
        })

        # Note: BUY simply returns immediately with the client order id.
        return_val: str = self.exchange.cancel(self.trading_pair, order.client_order_id)

        # Order ID is simply a timestamp. The assertion below checks if it is created within 1 sec
        self.assertTrue(order.client_order_id, return_val)

    def test_ready_trading_required_all_ready(self):
        self.exchange._trading_required = True

        # Simulate all components initialized
        self.exchange._account_id = 1
        self.exchange._order_book_tracker._order_books_initialized.set()
        self.exchange._account_balances = {
            self.base_asset: Decimal(str(10.0))
        }
        self._simulate_trading_rules_initialized()
        self.exchange._user_stream_tracker.data_source._last_recv_time = 1

        self.assertTrue(self.exchange.ready)

    def test_ready_trading_required_not_ready(self):
        self.exchange._trading_required = True

        # Simulate all components but account_id not initialized
        self.exchange._account_id = None
        self.exchange._order_book_tracker._order_books_initialized.set()
        self.exchange._account_balances = {}
        self._simulate_trading_rules_initialized()
        self.exchange._user_stream_tracker.data_source._last_recv_time = 0

        self.assertFalse(self.exchange.ready)

    def test_ready_trading_not_required_ready(self):
        self.exchange._trading_required = False

        # Simulate all components but account_id not initialized
        self.exchange._account_id = None
        self.exchange._order_book_tracker._order_books_initialized.set()
        self.exchange._account_balances = {}
        self._simulate_trading_rules_initialized()
        self.exchange._user_stream_tracker.data_source._last_recv_time = 0

        self.assertTrue(self.exchange.ready)

    def test_ready_trading_not_required_not_ready(self):
        self.exchange._trading_required = False
        self.assertFalse(self.exchange.ready)

    def test_limit_orders(self):
        self.assertEqual(0, len(self.exchange.limit_orders))

        # Simulate orders being placed and tracked
        order: NdaxInFlightOrder = NdaxInFlightOrder(
            client_order_id="0",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10.0),
            amount=Decimal(1.0))

        self.exchange._in_flight_orders.update({
            order.client_order_id: order
        })

        self.assertEqual(1, len(self.exchange.limit_orders))

    def test_tracking_states_order_not_done(self):
        order: NdaxInFlightOrder = NdaxInFlightOrder(
            client_order_id="0",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10.0),
            amount=Decimal(1.0))

        order_json = order.to_json()

        self.exchange._in_flight_orders.update({
            order.client_order_id: order
        })

        self.assertEqual(1, len(self.exchange.tracking_states))
        self.assertEqual(order_json, self.exchange.tracking_states[order.client_order_id])

    def test_tracking_states_order_done(self):
        order: NdaxInFlightOrder = NdaxInFlightOrder(
            client_order_id="0",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10.0),
            amount=Decimal(1.0),
            initial_state="FullyExecuted"
        )

        self.exchange._in_flight_orders.update({
            order.client_order_id: order
        })

        self.assertEqual(0, len(self.exchange.tracking_states))

    def test_restore_tracking_states(self):
        order: NdaxInFlightOrder = NdaxInFlightOrder(
            client_order_id="0",
            exchange_order_id="123",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10.0),
            amount=Decimal(1.0))

        order_json = order.to_json()

        self.exchange.restore_tracking_states({order.client_order_id: order_json})

        self.assertEqual(1, len(self.exchange.in_flight_orders))
        self.assertEqual(str(self.exchange.in_flight_orders[order.client_order_id]), str(order))

    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_rest_api_limit_reached_error(self, mock_get_request):
        self._set_mock_response(mock_get_request, 200, {}, CONSTANTS.API_LIMIT_REACHED_ERROR_MESSAGE)

        with self.assertRaises(IOError) as exception_context:
            asyncio.new_event_loop().run_until_complete(
                self.exchange._api_request("GET", "/path")
            )

        self.assertTrue("Error: The exchange API request limit has been reached (original error 'TOO MANY REQUESTS')"
                        in f"{exception_context.exception}")
