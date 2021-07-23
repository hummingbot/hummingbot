import asyncio
import json
from decimal import Decimal
from unittest import TestCase
from unittest.mock import AsyncMock, patch

import hummingbot.connector.exchange.ndax.ndax_constants as CONSTANTS
from hummingbot.connector.exchange.ndax.ndax_exchange import NdaxExchange
from hummingbot.core.event.events import (
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderType,
    TradeType, OrderFilledEvent,
)


class NdaxExchangeTests(TestCase):
    # the level is required to receive logs from the data source loger
    level = 0

    def setUp(self) -> None:
        super().setUp()
        self.ws_sent_messages = []
        self.ws_incoming_messages = asyncio.Queue()
        self.tracker_task = None
        self.exchange_task = None
        self.log_records = []
        self.resume_test_event = asyncio.Event()
        self._finalMessage = 'FinalDummyMessage'

        self.exchange = NdaxExchange(uid='001',
                                     api_key='testAPIKey',
                                     secret_key='testSecret')

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)

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

    def _add_successful_authentication_response(self):
        self.ws_incoming_messages.put_nowait(self._authentication_response(True))

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

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
        self.assertEqual((0.0, []), fill_event.trade_fee)
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
