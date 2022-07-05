import asyncio
import functools
import json as json_pckg
import time
from collections import namedtuple
from decimal import Decimal
from typing import Any, Awaitable, Callable, Dict, Optional
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.ftx_perpetual.ftx_perpetual_derivative import FtxPerpetualDerivative
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent, OrderType, PositionAction, TradeType
from hummingbot.core.network_iterator import NetworkStatus

FTX_API_ENDPOINT = "https://ftx.com/api"

request_res = namedtuple("request_res", "text")


def execute_buy_success(url, json, headers):
    mock_response: Dict[str, Any] = {
        # Truncated responses
        "success": True,
        "result": {
            "id": 1
        }
    }
    res = request_res(json_pckg.dumps(mock_response))

    return res


def execute_buy_fail(url, json, headers):
    mock_response: Dict[str, Any] = {
        # Truncated responses
        "success": False,
        "result": {
            "msg": "FAIL"
        }
    }
    res = request_res(json_pckg.dumps(mock_response))

    return res


class FtxPerpetualDerivativeUnitTests(TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "USD"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.symbol = f"{cls.base_asset}{cls.quote_asset}"
        cls.listen_key = "TEST_LISTEN_KEY"

    def setUp(self) -> None:
        super().setUp()

        self.log_records = []
        self.test_task: Optional[asyncio.Task] = None
        self.resume_test_event = asyncio.Event()
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())

        self.exchange = FtxPerpetualDerivative(
            client_config_map=self.client_config_map,
            ftx_perpetual_api_key="testAPIKey",
            ftx_perpetual_secret_key="testSecret",
            trading_pairs=[self.trading_pair, "BTC-USD"],
        )

        self.exchange._set_current_timestamp(400000)
        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)

        self._initialize_event_loggers()
        self.async_run_with_timeout(self.exchange._update_trading_rules())

    def tearDown(self) -> None:
        self.test_task and self.test_task.cancel()
        super().tearDown()

    def _initialize_event_loggers(self):
        self.buy_order_completed_logger = EventLogger()
        self.sell_order_completed_logger = EventLogger()
        self.order_filled_logger = EventLogger()

        events_and_loggers = [
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
            (MarketEvent.SellOrderCompleted, self.sell_order_completed_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger)]

        for event, logger in events_and_loggers:
            self.exchange.add_listener(event, logger)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _return_calculation_and_set_done_event(self, calculation: Callable, *args, **kwargs):
        if self.resume_test_event.is_set():
            raise asyncio.CancelledError
        self.resume_test_event.set()
        return calculation(*args, **kwargs)

    def test_order_fill_event(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="38065410",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            leverage=1,
            position_action="OPEN"
        )

        order = self.exchange.in_flight_orders.get("OID1")

        partial_fill = {
            'id': 103744440814,
            'clientId': 'OID1',
            'market': 'COINALPHA-PERP',
            'type': 'limit',
            'side': 'buy',
            'price': Decimal('10050.0'),
            'size': Decimal('1'),
            'status': 'open',
            'filledSize': Decimal('0.5'),
            'remainingSize': Decimal('0.5'),
            'reduceOnly': False,
            'liquidation': False,
            'avgFillPrice': Decimal('10050.0'),
            'postOnly': True,
            'ioc': False,
            'createdAt': '2021-12-10T15:33:57.882329+00:00'
        }

        message = {
            "channel": "orders",
            "type": "update",
            "data": partial_fill,
        }

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: message)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]

        self.assertEqual(Decimal("0.0007"), fill_event.trade_fee.percent)

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))

        complete_fill = {
            'id': 103744440814,
            'clientId': 'OID1',
            'market': 'COINALPHA-PERP',
            'type': 'limit',
            'side': 'buy',
            'price': Decimal('10050.0'),
            'size': Decimal('1'),
            'status': 'closed',
            'filledSize': Decimal('0.5'),
            'remainingSize': Decimal('0.0'),
            'reduceOnly': False,
            'liquidation': False,
            'avgFillPrice': Decimal('10050.0'),
            'postOnly': True,
            'ioc': False,
            'createdAt': '2021-12-10T15:33:57.882329+00:00'
        }

        message["data"] = complete_fill

        self.resume_test_event = asyncio.Event()
        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: message)

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(1, len(self.order_filled_logger.event_log))

        # Complete events are not produced by fill notifivations, only by order updates
        self.assertFalse(self._is_logged(
            "INFO",
            f"The market buy order {order.client_order_id} has completed according to user stream."
        ))

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))

    def test_order_complete_event(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="38065410",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            leverage=1,
            position_action="OPEN"
        )

        update_data = {
            'id': 103744440814,
            'clientId': 'OID1',
            'market': 'COINALPHA-PERP',
            'type': 'limit',
            'side': 'sell',
            'price': Decimal('10050.0'),
            'size': Decimal('1'),
            'status': 'closed',
            'filledSize': Decimal('1'),
            'remainingSize': Decimal('0.0'),
            'reduceOnly': False,
            'liquidation': False,
            'avgFillPrice': Decimal('10050.0'),
            'postOnly': True,
            'ioc': False,
            'createdAt': '2021-12-10T15:33:57.882329+00:00'
        }

        update_message = {
            "channel": "orders",
            "type": "update",
            "data": update_data,
        }

        mock_user_stream = AsyncMock()
        # We simulate the case when the order update arrives before the order fill
        mock_user_stream.get.side_effect = [update_message, asyncio.CancelledError()]

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        try:
            self.async_run_with_timeout(self.test_task)
        except asyncio.CancelledError:
            pass

        self.assertEqual(1, len(self.sell_order_completed_logger.event_log))

    def test_order_cancel_event(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="38065410",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            leverage=1,
            position_action="OPEN"
        )

        update_data = {
            'id': 103744440814,
            'clientId': 'OID1',
            'market': 'COINALPHA-PERP',
            'type': 'limit',
            'side': 'sell',
            'price': Decimal('10050.0'),
            'size': Decimal('1'),
            'status': 'closed',
            'filledSize': Decimal('0.0'),
            'remainingSize': Decimal('1.0'),
            'reduceOnly': False,
            'liquidation': False,
            'avgFillPrice': Decimal('10050.0'),
            'postOnly': True,
            'ioc': False,
            'createdAt': '2021-12-10T15:33:57.882329+00:00'
        }

        update_message = {
            "channel": "orders",
            "type": "update",
            "data": update_data,
        }
        mock_user_stream = AsyncMock()
        # We simulate the case when the order update arrives before the order fill
        mock_user_stream.get.side_effect = [update_message, asyncio.CancelledError()]

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        try:
            self.async_run_with_timeout(self.test_task)
        except asyncio.CancelledError:
            pass
        order = self.exchange.in_flight_orders.get("OID1")

        self.assertEqual(order, None)

    @aioresponses()
    def test_update_balances(self, mock_api):
        url = f"{FTX_API_ENDPOINT}/wallet/balances"
        mock_response: Dict[str, Any] = {
            # Truncated responses
            "result": [
                {
                    "coin": "USD",
                    "availableWithoutBorrow": 10.0,
                    "total": 10.0
                }
            ]
        }

        mock_api.get(url, status=200, body=json_pckg.dumps(mock_response))
        self.async_run_with_timeout(self.exchange._update_balances())
        self.assertEqual(self.exchange._account_available_balances['USD'], Decimal('10.0'))

    def test_update_trading_rules(self):
        self.async_run_with_timeout(self.exchange._update_trading_rules())
        self.assertTrue(len(self.exchange._trading_rules) > 0)
        quant_amount = self.exchange.quantize_order_amount('BTC-USD', Decimal('0.00001'), Decimal('10000'))
        self.assertEqual(quant_amount, Decimal('0'))
        quant_price = self.exchange.get_order_price_quantum('BTC-USD', Decimal('1'))
        self.assertEqual(quant_price, Decimal('1.0'))
        quant_amount = self.exchange.get_order_size_quantum('BTC-USD', Decimal('0.00001'))
        self.assertEqual(quant_amount, Decimal('0.0001'))

    def test_supported_order_types(self):
        order_types = self.exchange.supported_order_types()
        self.assertTrue(len(order_types) > 0)

    @aioresponses()
    def test_update_order_status(self, mock_api):
        self.exchange._last_poll_timestamp = 0
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="38065410",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            leverage=1,
            position_action="OPEN"
        )
        url = f"{FTX_API_ENDPOINT}/orders/by_client_id/OID1"
        mock_response: Dict[str, Any] = {
            # Truncated responses
            "result": {
                'id': 103744440814,
                'clientId': 'OID1',
                'market': 'COINALPHA-PERP',
                'type': 'limit',
                'side': 'sell',
                'price': 10050.0,
                'size': 1,
                'status': 'closed',
                'filledSize': 1.0,
                'remainingSize': 0.0,
                'reduceOnly': False,
                'liquidation': False,
                'avgFillPrice': 10050.0,
                'postOnly': True,
                'ioc': False,
                'createdAt': '2021-12-10T15:33:57.882329+00:00'
            }
        }
        mock_api.get(url, status=200, body=json_pckg.dumps(mock_response))
        self.async_run_with_timeout(self.exchange._update_order_status())
        order = self.exchange.in_flight_orders.get("OID1")
        self.assertTrue(order is None)

    @aioresponses()
    def test_get_funding_rates(self, mock_api):
        url_1 = f"{FTX_API_ENDPOINT}/futures/COINALPHA-PERP/stats"
        mock_response_1: Dict[str, Any] = {
            # Truncated responses
            "result": {
                "nextFundingTime": '2021-12-10T15:33:57.882329+00:00',
                "nextFundingRate": 0.01
            }
        }
        mock_api.get(url_1, status=200, body=json_pckg.dumps(mock_response_1))
        url_2 = f"{FTX_API_ENDPOINT}/futures/COINALPHA-PERP"
        mock_response_2: Dict[str, Any] = {
            # Truncated responses
            "result": {
                "mark": 100,
                "index": 100
            }
        }
        mock_api.get(url_2, status=200, body=json_pckg.dumps(mock_response_2))
        url_3 = f"{FTX_API_ENDPOINT}/futures/BTC-PERP/stats"
        mock_response_3: Dict[str, Any] = {
            # Truncated responses
            "result": {
                "nextFundingTime": '2021-12-10T15:33:57.882329+00:00',
                "nextFundingRate": 0.01
            }
        }
        mock_api.get(url_3, status=200, body=json_pckg.dumps(mock_response_3))
        url_4 = f"{FTX_API_ENDPOINT}/futures/BTC-PERP"
        mock_response_4: Dict[str, Any] = {
            # Truncated responses
            "result": {
                "mark": 100,
                "index": 100
            }
        }
        mock_api.get(url_4, status=200, body=json_pckg.dumps(mock_response_4))
        self.async_run_with_timeout(self.exchange._update_funding_rates())
        self.assertEqual(self.exchange.get_funding_info("COINALPHA-USD").index_price, Decimal('100'))

    @aioresponses()
    def test_set_leverage(self, mock_api):
        url = f"{FTX_API_ENDPOINT}/account/leverage"
        mock_response: Dict[str, Any] = {
            # Truncated responses
            "result": [
                {
                    "status": "success"
                }
            ]
        }
        mock_api.post(url, status=200, body=json_pckg.dumps(mock_response))
        self.async_run_with_timeout(self.exchange._set_leverage("COINALPHA-USD", 2))
        self.assertEqual(self.exchange._leverage['COINALPHA-USD'], 2)

    @aioresponses()
    def test_update_positions(self, mock_api):
        url = f"{FTX_API_ENDPOINT}/positions?showAvgPrice=true"
        mock_response: Dict[str, Any] = {
            # Truncated responses
            "result": [
                {
                    "future": "COINALPHA-PERP",
                    "side": "buy",
                    "netSize": 1.0,
                    "unrealizedPnl": 0.0,
                    "recentAverageOpenPrice": 100.0
                }
            ]
        }
        mock_api.get(url, status=200, body=json_pckg.dumps(mock_response))
        self.async_run_with_timeout(self.exchange._update_positions())
        self.assertTrue(len(self.exchange._account_positions) > 0)
        url = f"{FTX_API_ENDPOINT}/positions?showAvgPrice=true"
        mock_response: Dict[str, Any] = {
            # Truncated responses
            "result": [
                {
                    "future": "COINALPHA-PERP",
                    "side": "buy",
                    "netSize": 0.0,
                    "unrealizedPnl": 0.0,
                    "recentAverageOpenPrice": 100.0
                }
            ]
        }
        mock_api.get(url, status=200, body=json_pckg.dumps(mock_response))
        self.async_run_with_timeout(self.exchange._update_positions())
        self.assertTrue(len(self.exchange._account_positions) == 0)

    @aioresponses()
    def test_buy(self, mock_api):
        url = f"{FTX_API_ENDPOINT}/orders"
        mock_response: Dict[str, Any] = {
            # Truncated responses
            "result": [
                {
                    "success": True,
                    "result": {
                        "id": 1
                    }
                }
            ]
        }
        mock_api.post(url, status=200, body=json_pckg.dumps(mock_response))
        order_id = self.exchange.buy(
            trading_pair="BTC-USD",
            amount=Decimal('10'),
            order_type=OrderType.LIMIT,
            price=Decimal('100'),
            position_action=PositionAction.OPEN
        )
        self.assertEqual(order_id[0:8], 'FTX-PERP')

    @patch('requests.post', side_effect=execute_buy_success)
    def test_execute_buy(self, mock_post):
        self.async_run_with_timeout(
            self.exchange.execute_buy(
                order_id="OID1",
                trading_pair="BTC-USD",
                amount=Decimal('10'),
                order_type=OrderType.LIMIT,
                price=Decimal('100'),
                position_action=PositionAction.OPEN
            )
        )
        order = self.exchange._in_flight_orders.get("OID1")
        self.assertEqual(order.exchange_order_id, '1')

    @patch('requests.post', side_effect=execute_buy_success)
    def test_execute_market_buy(self, mock_post):
        self.async_run_with_timeout(
            self.exchange.execute_buy(
                order_id="OID1",
                trading_pair="BTC-USD",
                amount=Decimal('10'),
                order_type=OrderType.MARKET,
                price=None,
                position_action=PositionAction.OPEN
            )
        )
        order = self.exchange._in_flight_orders.get("OID1")
        self.assertEqual(order.exchange_order_id, '1')

    @patch('requests.post', side_effect=execute_buy_fail)
    def test_execute_buy_fail(self, mock_post):
        self.async_run_with_timeout(
            self.exchange.execute_buy(
                order_id="OID1",
                trading_pair="BTC-USD",
                amount=Decimal('10'),
                order_type=OrderType.LIMIT,
                price=Decimal('100'),
                position_action=PositionAction.OPEN
            )
        )
        order = self.exchange._in_flight_orders.get("OID1")
        self.assertEqual(order, None)

    @patch('requests.post', side_effect=execute_buy_success)
    def test_execute_sell(self, mock_post):
        self.async_run_with_timeout(
            self.exchange.execute_sell(
                order_id="OID1",
                trading_pair="BTC-USD",
                amount=Decimal('10'),
                order_type=OrderType.LIMIT,
                price=Decimal('100'),
                position_action=PositionAction.OPEN
            )
        )
        order = self.exchange._in_flight_orders.get("OID1")
        self.assertEqual(order.exchange_order_id, '1')

    @patch('requests.post', side_effect=execute_buy_success)
    def test_execute_market_sell(self, mock_post):
        self.async_run_with_timeout(
            self.exchange.execute_sell(
                order_id="OID1",
                trading_pair="BTC-USD",
                amount=Decimal('10'),
                order_type=OrderType.MARKET,
                price=None,
                position_action=PositionAction.OPEN
            )
        )
        order = self.exchange._in_flight_orders.get("OID1")
        self.assertEqual(order.exchange_order_id, '1')

    @patch('requests.post', side_effect=execute_buy_fail)
    def test_execute_sell_fail(self, mock_post):
        self.async_run_with_timeout(
            self.exchange.execute_sell(
                order_id="OID1",
                trading_pair="BTC-USD",
                amount=Decimal('10'),
                order_type=OrderType.LIMIT,
                price=Decimal('100'),
                position_action=PositionAction.OPEN
            )
        )
        order = self.exchange._in_flight_orders.get("OID1")
        self.assertEqual(order, None)

    @aioresponses()
    def test_sell(self, mock_api):
        url = f"{FTX_API_ENDPOINT}/orders"
        mock_response: Dict[str, Any] = {
            # Truncated responses
            "result": [
                {
                    "success": True,
                    "result": {
                        "id": 1
                    }
                }
            ]
        }
        mock_api.post(url, status=200, body=json_pckg.dumps(mock_response))
        order_id = self.exchange.sell(
            trading_pair="BTC-USD",
            amount=Decimal('10'),
            order_type=OrderType.LIMIT,
            price=Decimal('100'),
            position_action=PositionAction.OPEN
        )
        self.assertEqual(order_id[0:8], 'FTX-PERP')

    @aioresponses()
    def test_execute_cancel(self, mock_api):
        url = f"{FTX_API_ENDPOINT}/orders/by_client_id/OID1"
        mock_response: Dict[str, Any] = {
            # Truncated responses
            "success": True,
            "result": {
                "id": 1
            }
        }
        mock_api.delete(url, status=200, body=json_pckg.dumps(mock_response))
        order_id = self.async_run_with_timeout(
            self.exchange.execute_cancel(
                trading_pair="BTC-USD",
                order_id="OID1"
            )
        )
        self.assertEqual(order_id, "OID1")

    @aioresponses()
    def test_execute_cancel_fail(self, mock_api):
        url = f"{FTX_API_ENDPOINT}/orders/by_client_id/OID1"
        mock_response: Dict[str, Any] = {
            # Truncated responses
            "success": False,
            "error": "Bad Error Report"
        }
        mock_api.delete(url, status=200, body=json_pckg.dumps(mock_response))
        order_id = self.async_run_with_timeout(
            self.exchange.execute_cancel(
                trading_pair="COINALPHA-USD",
                order_id="OID1"
            )
        )
        self.assertEqual(order_id, "OID1")

    @aioresponses()
    @patch("hummingbot.connector.derivative.ftx_perpetual.ftx_perpetual_derivative.FtxPerpetualDerivative.logger", side_effect=None)
    def test_execute_cancel_error(self, mock_api, mock_logger):
        url = f"{FTX_API_ENDPOINT}/orders/by_client_id/OID1"
        mock_response: Dict[str, Any] = {
            # Truncated responses
            "success_not_in_response": False,
            "error": "Bad Error Report"
        }
        mock_api.delete(url, status=200, body=json_pckg.dumps(mock_response))
        try:
            order_id = self.async_run_with_timeout(
                self.exchange.execute_cancel(
                    trading_pair="COINALPHA-USD",
                    order_id="OID1"
                )
            )
        except Exception:
            pass
        self.assertEqual(order_id, None)

    @aioresponses()
    def test_cancel_all(self, mock_api):
        for order_id, _ in self.exchange._in_flight_orders.copy().items():
            self.exchange.stop_tracking_order(order_id)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="38065410",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            price=Decimal("10000"),
            amount=Decimal("1"),
            leverage=1,
            position_action="OPEN"
        )
        url = f"{FTX_API_ENDPOINT}/orders/by_client_id/OID1"
        mock_response: Dict[str, Any] = {
            # Truncated responses
            "success": True,
            "result": {
                "id": 1
            }
        }
        mock_api.delete(url, status=200, body=json_pckg.dumps(mock_response))
        cancellations = self.async_run_with_timeout(
            self.exchange.cancel_all(
                1
            )
        )
        self.assertEqual(len(cancellations), 1)

    @aioresponses()
    def test_sell_fail(self, mock_api):
        for order_id, _ in self.exchange._in_flight_orders.copy().items():
            self.exchange.stop_tracking_order(order_id)
        url = f"{FTX_API_ENDPOINT}/orders"
        mock_response: Dict[str, Any] = {
            # Truncated responses
            "result": [
                {
                    "success": False,
                    "result": {
                        "msg": "FAIL!"
                    }
                }
            ]
        }
        mock_api.post(url, status=200, body=json_pckg.dumps(mock_response))
        self.exchange.sell(
            trading_pair="BTC-USD",
            amount=Decimal('10'),
            order_type=OrderType.LIMIT,
            price=Decimal('100'),
            position_action=PositionAction.OPEN
        )
        self.assertEqual(len(self.exchange.in_flight_orders), 0)

    def test_name(self):
        self.assertEqual(self.exchange.name, "ftx_perpetual")

    def test_auth(self):
        self.assertEqual(self.exchange.ftx_perpetual_auth.api_key, "testAPIKey")

    def test_order_books(self):
        self.assertEqual(self.exchange.order_books, {})

    def test_ready(self):
        self.assertFalse(self.exchange.ready)

    def test_limit_orders(self):
        for order_id, _ in self.exchange._in_flight_orders.copy().items():
            self.exchange.stop_tracking_order(order_id)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="38065410",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            leverage=1,
            position_action="OPEN"
        )
        self.assertEqual(len(self.exchange.limit_orders), 1)

    def test_tick(self):
        self.exchange.tick(time.time())
        self.assertTrue(self.exchange._last_timestamp > 0)

    def test_restore_tracking_states(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="38065410",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            leverage=1,
            position_action="OPEN"
        )
        states = self.exchange.tracking_states
        self.exchange.stop_tracking_order("OID1")
        self.exchange.restore_tracking_states(states)
        self.assertTrue('OID1' in self.exchange.in_flight_orders)

    def test_get_order_book_fail(self):
        try:
            self.exchange.get_order_book("COINALPHA-USD")
        except Exception as e:
            self.assertEqual(str(e), "No order book exists for 'COINALPHA-USD'.")

    def test_did_timeout_tx(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="38065410",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            leverage=1,
            position_action="OPEN"
        )
        self.exchange.did_timeout_tx("OID1")

    @aioresponses()
    def test_check_network(self, mock_api):
        url = f"{FTX_API_ENDPOINT}/wallet/balances"
        mock_response: Dict[str, Any] = {
            # Truncated responses
            "result": [
                {
                    "coin": "USD",
                    "availableWithoutBorrow": 10.0,
                    "total": 10.0
                }
            ]
        }
        mock_api.get(url, status=200, body=json_pckg.dumps(mock_response))
        connected = self.async_run_with_timeout(
            self.exchange.check_network()
        )
        self.assertEqual(connected, NetworkStatus.CONNECTED)

    @aioresponses()
    def test_check_network_fail(self, mock_api):
        url = f"{FTX_API_ENDPOINT}/wallet/balances"
        mock_response = {"status": "error"}
        mock_api.get(url, status=400, body=json_pckg.dumps(mock_response))
        connected = self.async_run_with_timeout(
            self.exchange.check_network()
        )
        self.assertEqual(connected, NetworkStatus.NOT_CONNECTED)

    def test_start_network(self):
        self.async_run_with_timeout(
            self.exchange.start_network()
        )

    def test_get_fee(self):
        fee = self.exchange.get_fee(
            "COINALPHA",
            "USD",
            OrderType.LIMIT,
            TradeType.BUY,
            Decimal('10'),
            Decimal('100')
        )
        self.assertEqual(fee.flat_fees, [])
