import asyncio
import time
from abc import ABC, abstractmethod
from decimal import Decimal
from queue import Queue
from typing import Any, Awaitable, Dict, List, Tuple, Type, Union
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.gateway.clob_spot.data_sources.gateway_clob_api_data_source_base import (
    GatewayCLOBAPIDataSourceBase,
)
from hummingbot.connector.gateway.common_types import CancelOrderResult, PlaceOrderResult
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.gateway.gateway_order_tracker import GatewayOrderTracker
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.trade_fee import (
    AddedToCostTradeFee,
    MakerTakerExchangeFeeRates,
    TokenAmount,
    TradeFeeBase,
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent, OrderBookDataSourceEvent
from hummingbot.core.network_iterator import NetworkStatus


class MockExchange(ExchangeBase):
    pass


class AbstractGatewayCLOBAPIDataSourceTests:
    """
    We need to create the abstract TestCase class inside another class not inheriting from TestCase to prevent test
    frameworks from discovering and tyring to run the abstract class
    """

    class GatewayCLOBAPIDataSourceTests(ABC, TestCase):
        # the level is required to receive logs from the data source logger
        level = 0

        base: str
        quote: str
        trading_pair: str
        account_id: str

        @property
        @abstractmethod
        def expected_buy_exchange_order_id(self) -> str:
            ...

        @property
        @abstractmethod
        def expected_sell_exchange_order_id(self) -> str:
            ...

        @property
        @abstractmethod
        def exchange_base(self) -> str:
            ...

        @property
        @abstractmethod
        def exchange_quote(self) -> str:
            ...

        @abstractmethod
        def build_api_data_source(self) -> GatewayCLOBAPIDataSourceBase:
            ...

        @abstractmethod
        def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
            ...

        @abstractmethod
        def get_trading_pairs_info_response(self) -> List[Dict[str, Any]]:
            ...

        @abstractmethod
        def get_order_status_response(
            self,
            timestamp: float,
            trading_pair: str,
            exchange_order_id: str,
            client_order_id: str,
            status: OrderState,
        ) -> List[Dict[str, Any]]:
            ...

        @abstractmethod
        def get_clob_ticker_response(self, trading_pair: str, last_traded_price: Decimal) -> List[Dict[str, Any]]:
            ...

        @abstractmethod
        def configure_account_balances_response(
            self,
            base_total_balance: Decimal,
            base_available_balance: Decimal,
            quote_total_balance: Decimal,
            quote_available_balance: Decimal,
        ):
            ...

        @abstractmethod
        def configure_empty_order_fills_response(self):
            ...

        @abstractmethod
        def configure_trade_fill_response(
            self,
            timestamp: float,
            exchange_order_id: str,
            price: Decimal,
            size: Decimal,
            fee: TradeFeeBase,
            trade_id: Union[str, int],
            is_taker: bool,
        ):
            ...

        @property
        def expected_min_price_increment(self):
            return Decimal("0.00001")

        @property
        def exchange_trading_pair(self) -> str:
            return self.exchange_symbol_for_tokens(self.base, self.quote)

        @property
        def expected_buy_client_order_id(self) -> str:
            return "someBuyClientOrderID"

        @property
        def expected_sell_client_order_id(self) -> str:
            return "someSellClientOrderID"

        @property
        def expected_buy_order_price(self) -> Decimal:
            return Decimal("10")

        @property
        def expected_sell_order_price(self) -> Decimal:
            return Decimal("11")

        @property
        def expected_buy_order_size(self) -> Decimal:
            return Decimal("2")

        @property
        def expected_sell_order_size(self) -> Decimal:
            return Decimal("3")

        @property
        def expected_base_total_balance(self) -> Decimal:
            return Decimal("10")

        @property
        def expected_base_available_balance(self) -> Decimal:
            return Decimal("9")

        @property
        def expected_quote_total_balance(self) -> Decimal:
            return Decimal("200")

        @property
        def expected_quote_available_balance(self) -> Decimal:
            return Decimal("150")

        @property
        def expected_last_traded_price(self) -> Decimal:
            return Decimal("9")

        @property
        def expected_fill_price(self) -> Decimal:
            return Decimal("3")

        @property
        def expected_fill_size(self) -> Decimal:
            return Decimal("4")

        @property
        def expected_fill_fee_token(self) -> str:
            return self.quote

        @property
        def expected_fill_fee_amount(self) -> Decimal:
            return Decimal("0.02")

        @property
        def expected_fill_fee(self) -> TradeFeeBase:
            return AddedToCostTradeFee(
                flat_fees=[TokenAmount(token=self.expected_fill_fee_token, amount=self.expected_fill_fee_amount)]
            )

        @property
        def expected_maker_taker_fee_rates(self) -> MakerTakerExchangeFeeRates:
            return MakerTakerExchangeFeeRates(
                maker=Decimal("0.001"),
                taker=Decimal("0.002"),
                maker_flat_fees=[],
                taker_flat_fees=[],
            )

        @property
        def expected_fill_trade_id(self) -> Union[str, int]:
            return "someTradeID"

        @property
        def expected_transaction_hash(self) -> str:
            return "0x7e5f4552091a69125d5dfcb7b8c2659029395bdf"  # noqa: mock

        @property
        def expected_total_balance(self) -> Decimal:
            return Decimal("20")

        @property
        def expected_available_balance(self) -> Decimal:
            return Decimal("19")

        @property
        def expected_event_counts_per_new_order(self) -> int:
            return 1

        @classmethod
        def setUpClass(cls) -> None:
            super().setUpClass()
            cls.base = "COIN"
            cls.quote = "ALPHA"
            cls.trading_pair = combine_to_hb_trading_pair(base=cls.base, quote=cls.quote)
            cls.account_id = "0xc7287236f64484b476cfbec0fd21bc49d85f8850c8885665003928a122041e18"  # noqa: mock

        def setUp(self) -> None:
            super().setUp()

            self.ev_loop = asyncio.get_event_loop()
            self.log_records = []
            self.initial_timestamp = 1669100347

            self.gateway_instance_mock_patch = patch(
                target=(
                    "hummingbot.connector.gateway.clob_spot.data_sources.gateway_clob_api_data_source_base"
                    ".GatewayHttpClient"
                ),
                autospec=True,
            )
            self.gateway_instance_mock = self.gateway_instance_mock_patch.start()
            self.gateway_instance_mock.get_instance.return_value = self.gateway_instance_mock
            self.order_status_response_queue = Queue()

            self.client_config_map = ClientConfigAdapter(hb_config=ClientConfigMap())
            self.connector = MockExchange(client_config_map=self.client_config_map)
            self.data_source = self.build_api_data_source()
            self.data_source.logger().setLevel(1)
            self.data_source.logger().addHandler(self)
            self.tracker = self.build_order_tracker(connector=self.connector)
            self.data_source.gateway_order_tracker = self.tracker

            self.order_updates_logger = EventLogger()
            self.snapshots_logger = EventLogger()

            self.data_source.add_listener(event_tag=MarketEvent.OrderUpdate, listener=self.order_updates_logger)
            self.data_source.add_listener(
                event_tag=OrderBookDataSourceEvent.SNAPSHOT_EVENT, listener=self.snapshots_logger
            )

            self.configure_trading_pairs_info_response()
            self.configure_orderbook_snapshot(
                timestamp=self.initial_timestamp, bids=[[10, 2], [9, 3]], asks=[[12, 4]]
            )

            self.async_run_with_timeout(coro=self.data_source.start())

            self.additional_data_sources_to_stop_on_tear_down = []
            self.async_tasks = []

        def tearDown(self) -> None:
            self.async_run_with_timeout(coro=self.data_source.stop())
            self.gateway_instance_mock_patch.stop()
            for data_source in self.additional_data_sources_to_stop_on_tear_down:
                self.async_run_with_timeout(coro=data_source.stop())
            for task in self.async_tasks:
                task.cancel()
            super().tearDown()

        @staticmethod
        def async_run_with_timeout(coro: Awaitable, timeout: float = 1):
            ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coro, timeout))
            return ret

        @staticmethod
        def build_order_tracker(connector: ExchangeBase) -> GatewayOrderTracker:
            return GatewayOrderTracker(connector=connector)

        def is_logged(self, log_level: str, message: str) -> bool:
            return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

        def handle(self, record):
            self.log_records.append(record)

        def configure_trading_pairs_info_response(self):
            markets = self.get_trading_pairs_info_response()
            mock_response = {
                "network": self.data_source.network,
                "timestamp": self.initial_timestamp,
                "latency": 2,
                "markets": markets,
            }
            self.gateway_instance_mock.get_clob_markets.return_value = mock_response

        def enqueue_order_status_response(
            self,
            timestamp: float,
            trading_pair: str,
            exchange_order_id: str,
            client_order_id: str,
            status: OrderState,
        ) -> asyncio.Event:
            orders = self.get_order_status_response(
                timestamp=timestamp,
                trading_pair=trading_pair,
                exchange_order_id=exchange_order_id,
                client_order_id=client_order_id,
                status=status,
            )
            mock_response = {
                "network": self.data_source.network,
                "timestamp": self.initial_timestamp,
                "latency": 2,
                "orders": orders,
            }
            update_delivered_event = asyncio.Event()

            self.order_status_response_queue.put(item=(mock_response, update_delivered_event))

            async def deliver_event(*_, **__):
                mock_response_, update_delivered_event_ = self.order_status_response_queue.get()
                update_delivered_event_.set()
                return mock_response_

            self.gateway_instance_mock.get_clob_order_status_updates.side_effect = deliver_event

            return update_delivered_event

        def enqueue_order_status_responses_for_batch_order_create(
            self, timestamp: float, orders: List[GatewayInFlightOrder], statuses: List[OrderState]
        ) -> asyncio.Event:
            assert len(orders) == len(statuses) != 0
            update_delivered_event = None
            for order, status in zip(orders, statuses):
                update_delivered_event = self.enqueue_order_status_response(
                    timestamp=timestamp,
                    trading_pair=order.trading_pair,
                    exchange_order_id=order.exchange_order_id,
                    client_order_id=order.client_order_id,
                    status=status,
                )
            return update_delivered_event  # returning the last event

        def enqueue_order_status_responses_for_batch_order_cancel(
            self, timestamp: float, orders: List[GatewayInFlightOrder], statuses: List[OrderState]
        ) -> asyncio.Event:
            return self.enqueue_order_status_responses_for_batch_order_create(
                timestamp=timestamp, orders=orders, statuses=statuses
            )

        def configure_check_network_success(self):
            self.gateway_instance_mock.ping_gateway.side_effect = None

        def configure_check_network_failure(self, exc: Type[Exception] = RuntimeError):
            self.gateway_instance_mock.ping_gateway.side_effect = exc

        def configure_orderbook_snapshot(
            self, timestamp: int, bids: List[List[float]], asks: List[List[float]], latency: float = 0
        ) -> Tuple[asyncio.Event, asyncio.Event]:
            snapshot_requested = asyncio.Event()
            snapshot_delivered = asyncio.Event()

            async def deliver_snapshot(*_, **__):
                snapshot_requested.set()
                if latency:
                    await asyncio.sleep(latency)
                snapshot_resp = self.get_orderbook_snapshot_response(
                    timestamp=timestamp, bids=bids, asks=asks
                )
                snapshot_delivered.set()
                return snapshot_resp

            self.gateway_instance_mock.get_clob_orderbook_snapshot.side_effect = deliver_snapshot

            return snapshot_requested, snapshot_delivered

        def configure_place_order_response(
            self,
            timestamp: float,
            transaction_hash: str,
            exchange_order_id: str,
            trade_type: TradeType,
            price: Decimal,
            size: Decimal,
        ):
            response = {
                "network": self.data_source.network,
                "timestamp": timestamp,
                "latency": 2,
                "txHash": transaction_hash,
            }
            self.gateway_instance_mock.clob_place_order.return_value = response

        def configure_place_order_failure_response(self):
            self.gateway_instance_mock.clob_place_order.return_value = {
                "network": self.data_source.network,
                "timestamp": self.initial_timestamp,
                "latency": 2,
                "txHash": None,
            }

        def configure_batch_order_create_response(
            self,
            timestamp: float,
            transaction_hash: str,
            created_orders: List[GatewayInFlightOrder],
        ):
            response = {
                "network": self.data_source.network,
                "timestamp": timestamp,
                "latency": 2,
                "txHash": transaction_hash,
            }
            self.gateway_instance_mock.clob_batch_order_modify.return_value = response

        def configure_cancel_order_response(self, timestamp: float, transaction_hash: str):
            response = {
                "network": self.data_source.network,
                "timestamp": timestamp,
                "latency": 2,
                "txHash": transaction_hash,
            }
            self.gateway_instance_mock.clob_cancel_order.return_value = response

        def configure_cancel_order_failure_response(self):
            self.gateway_instance_mock.clob_cancel_order.return_value = {
                "network": self.data_source.network,
                "timestamp": self.initial_timestamp,
                "latency": 2,
                "txHash": None,
            }

        def configure_batch_order_cancel_response(
            self,
            timestamp: float,
            transaction_hash: str,
            canceled_orders: List[GatewayInFlightOrder],
        ):
            response = {
                "network": self.data_source.network,
                "timestamp": timestamp,
                "latency": 2,
                "txHash": transaction_hash,
            }
            self.gateway_instance_mock.clob_batch_order_modify.return_value = response

        def configure_last_traded_price(self, trading_pair: str, last_traded_price: Decimal):
            ticker_response = self.get_clob_ticker_response(trading_pair=trading_pair,
                                                            last_traded_price=last_traded_price)
            response = {
                "network": self.data_source.network,
                "timestamp": self.initial_timestamp,
                "latency": 2,
                "markets": ticker_response,
            }
            self.gateway_instance_mock.get_clob_ticker.return_value = response

        def get_orderbook_snapshot_response(
            self, timestamp: int, bids: List[List[float]], asks: List[List[float]]
        ):
            return {
                "timestamp": timestamp,
                "network": self.data_source.network,
                "latency": 2,
                "buys": [
                    {"price": bid[0], "quantity": bid[1], "timestamp": timestamp * 1e3}
                    for bid in bids
                ],
                "sells": [
                    {"price": ask[0], "quantity": ask[1], "timestamp": timestamp * 1e3}
                    for ask in asks
                ],
            }

        @patch(
            "hummingbot.connector.gateway.clob_spot.data_sources.gateway_clob_api_data_source_base"
            ".GatewayCLOBAPIDataSourceBase._sleep",
            new_callable=AsyncMock,
        )
        def test_place_order(self, sleep_mock: AsyncMock):
            def sleep_mock_side_effect(delay):
                raise Exception

            sleep_mock.side_effect = sleep_mock_side_effect

            self.configure_place_order_response(
                timestamp=self.initial_timestamp,
                transaction_hash=self.expected_transaction_hash,
                exchange_order_id=self.expected_buy_exchange_order_id,
                trade_type=TradeType.BUY,
                price=self.expected_buy_order_price,
                size=self.expected_buy_order_size,
            )
            order = GatewayInFlightOrder(
                client_order_id=self.expected_buy_client_order_id,
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                creation_timestamp=self.initial_timestamp,
                price=self.expected_buy_order_price,
                amount=self.expected_buy_order_size,
            )
            exchange_order_id, misc_updates = self.async_run_with_timeout(
                coro=self.data_source.place_order(order=order)
            )

            self.assertEqual({"creation_transaction_hash": self.expected_transaction_hash}, misc_updates)

        def test_place_order_transaction_fails(self):
            self.configure_place_order_failure_response()
            order = GatewayInFlightOrder(
                client_order_id=self.expected_buy_client_order_id,
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                creation_timestamp=self.initial_timestamp,
                price=self.expected_buy_order_price,
                amount=self.expected_buy_order_size,
            )

            with self.assertRaises(ValueError):
                self.async_run_with_timeout(
                    coro=self.data_source.place_order(order=order)
                )

        @patch(
            "hummingbot.connector.gateway.clob_spot.data_sources.gateway_clob_api_data_source_base"
            ".GatewayCLOBAPIDataSourceBase._sleep",
            new_callable=AsyncMock,
        )
        def test_batch_order_create(self, sleep_mock: AsyncMock):
            def sleep_mock_side_effect(delay):
                raise Exception

            sleep_mock.side_effect = sleep_mock_side_effect

            buy_order_to_create = GatewayInFlightOrder(
                client_order_id=self.expected_buy_client_order_id,
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                creation_timestamp=self.initial_timestamp,
                price=self.expected_buy_order_price,
                amount=self.expected_buy_order_size,
                exchange_order_id=self.expected_buy_exchange_order_id,
            )
            sell_order_to_create = GatewayInFlightOrder(
                client_order_id=self.expected_sell_client_order_id,
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.SELL,
                creation_timestamp=self.initial_timestamp,
                price=self.expected_sell_order_price,
                amount=self.expected_sell_order_size,
                exchange_order_id=self.expected_sell_exchange_order_id,
            )
            orders_to_create = [buy_order_to_create, sell_order_to_create]
            self.configure_batch_order_create_response(
                timestamp=self.initial_timestamp,
                transaction_hash=self.expected_transaction_hash,
                created_orders=orders_to_create,
            )

            for order in orders_to_create:
                order.exchange_order_id = None  # the orders are new

            result: List[PlaceOrderResult] = self.async_run_with_timeout(
                coro=self.data_source.batch_order_create(orders_to_create=orders_to_create)
            )

            self.assertEqual(2, len(result))
            self.assertEqual(self.expected_buy_client_order_id, result[0].client_order_id)
            self.assertEqual({"creation_transaction_hash": self.expected_transaction_hash}, result[0].misc_updates)
            self.assertEqual(self.expected_sell_client_order_id, result[1].client_order_id)
            self.assertEqual({"creation_transaction_hash": self.expected_transaction_hash}, result[1].misc_updates)

        @patch(
            "hummingbot.connector.gateway.clob_spot.data_sources.gateway_clob_api_data_source_base"
            ".GatewayCLOBAPIDataSourceBase._sleep",
            new_callable=AsyncMock,
        )
        def test_cancel_order(self, sleep_mock: AsyncMock):
            order = GatewayInFlightOrder(
                client_order_id=self.expected_buy_client_order_id,
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                price=self.expected_buy_order_price,
                amount=self.expected_buy_order_size,
                creation_timestamp=self.initial_timestamp,
                exchange_order_id=self.expected_buy_exchange_order_id,
                creation_transaction_hash="someCreationHash",
            )
            self.data_source.gateway_order_tracker.start_tracking_order(order=order)
            self.configure_cancel_order_response(
                timestamp=self.initial_timestamp, transaction_hash=self.expected_transaction_hash
            )
            cancelation_success, misc_updates = self.async_run_with_timeout(
                coro=self.data_source.cancel_order(order=order)
            )

            self.assertTrue(cancelation_success)
            self.assertEqual({"cancelation_transaction_hash": self.expected_transaction_hash}, misc_updates)

        def test_cancel_order_transaction_fails(self):
            order = GatewayInFlightOrder(
                client_order_id=self.expected_buy_client_order_id,
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                price=self.expected_buy_order_price,
                amount=self.expected_buy_order_size,
                creation_timestamp=self.initial_timestamp,
                exchange_order_id=self.expected_buy_exchange_order_id,
                creation_transaction_hash="someCreationHash",
            )
            self.data_source.gateway_order_tracker.start_tracking_order(order=order)
            self.configure_cancel_order_failure_response()

            with self.assertRaises(ValueError):
                self.async_run_with_timeout(coro=self.data_source.cancel_order(order=order))

        @patch(
            "hummingbot.connector.gateway.clob_spot.data_sources.gateway_clob_api_data_source_base"
            ".GatewayCLOBAPIDataSourceBase._sleep",
            new_callable=AsyncMock,
        )
        def test_batch_order_cancel(self, sleep_mock: AsyncMock):
            buy_order_to_cancel = GatewayInFlightOrder(
                client_order_id=self.expected_buy_client_order_id,
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                price=self.expected_buy_order_price,
                amount=self.expected_buy_order_size,
                creation_timestamp=self.initial_timestamp,
                exchange_order_id=self.expected_buy_exchange_order_id,
                creation_transaction_hash=self.expected_transaction_hash,
            )
            sell_order_to_cancel = GatewayInFlightOrder(
                client_order_id=self.expected_sell_client_order_id,
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.SELL,
                price=self.expected_sell_order_price,
                amount=self.expected_sell_order_size,
                creation_timestamp=self.initial_timestamp,
                exchange_order_id=self.expected_sell_exchange_order_id,
                creation_transaction_hash=self.expected_transaction_hash,
            )
            self.data_source.gateway_order_tracker.start_tracking_order(order=buy_order_to_cancel)
            self.data_source.gateway_order_tracker.start_tracking_order(order=sell_order_to_cancel)
            orders_to_cancel = [buy_order_to_cancel, sell_order_to_cancel]
            self.configure_batch_order_cancel_response(
                timestamp=self.initial_timestamp,
                transaction_hash=self.expected_transaction_hash,
                canceled_orders=orders_to_cancel,
            )

            result: List[CancelOrderResult] = self.async_run_with_timeout(
                coro=self.data_source.batch_order_cancel(orders_to_cancel=orders_to_cancel)
            )

            self.assertEqual(2, len(result))
            self.assertEqual(buy_order_to_cancel.client_order_id, result[0].client_order_id)
            self.assertIsNone(result[0].exception)  # i.e. success
            self.assertEqual({"cancelation_transaction_hash": self.expected_transaction_hash}, result[0].misc_updates)
            self.assertEqual(sell_order_to_cancel.client_order_id, result[1].client_order_id)
            self.assertIsNone(result[1].exception)  # i.e. success
            self.assertEqual({"cancelation_transaction_hash": self.expected_transaction_hash}, result[1].misc_updates)

        def test_get_trading_rules(self):
            trading_rules = self.async_run_with_timeout(coro=self.data_source.get_trading_rules())

            self.assertEqual(2, len(trading_rules))
            self.assertIn(self.trading_pair, trading_rules)

            trading_rule: TradingRule = trading_rules[self.trading_pair]

            self.assertEqual(self.trading_pair, trading_rule.trading_pair)
            self.assertEqual(self.expected_min_price_increment, trading_rule.min_price_increment)

        def test_get_symbol_map(self):
            symbol_map = self.async_run_with_timeout(coro=self.data_source.get_symbol_map())

            self.assertIsInstance(symbol_map, bidict)
            self.assertEqual(2, len(symbol_map))
            self.assertIn(self.exchange_trading_pair, symbol_map)
            self.assertIn(self.trading_pair, symbol_map.inverse)

        def test_get_last_traded_price(self):
            self.configure_last_traded_price(
                trading_pair=self.trading_pair, last_traded_price=self.expected_last_traded_price
            )
            last_trade_price = self.async_run_with_timeout(
                coro=self.data_source.get_last_traded_price(trading_pair=self.trading_pair)
            )

            self.assertEqual(self.expected_last_traded_price, last_trade_price)

        def test_get_order_book_snapshot(self):
            self.configure_orderbook_snapshot(
                timestamp=self.initial_timestamp, bids=[[9, 1], [8, 2]], asks=[[11, 3]]
            )
            order_book_snapshot: OrderBookMessage = self.async_run_with_timeout(
                coro=self.data_source.get_order_book_snapshot(trading_pair=self.trading_pair)
            )

            self.assertEqual(self.initial_timestamp, order_book_snapshot.timestamp)
            self.assertEqual(2, len(order_book_snapshot.bids))
            self.assertEqual(9, order_book_snapshot.bids[0].price)
            self.assertEqual(1, order_book_snapshot.bids[0].amount)
            self.assertEqual(1, len(order_book_snapshot.asks))
            self.assertEqual(11, order_book_snapshot.asks[0].price)
            self.assertEqual(3, order_book_snapshot.asks[0].amount)

        def test_delivers_order_book_snapshot_events(self):
            self.async_run_with_timeout(self.data_source.stop())

            data_source = self.build_api_data_source()
            self.additional_data_sources_to_stop_on_tear_down.append(data_source)
            data_source.min_snapshots_update_interval = 0
            data_source.max_snapshots_update_interval = 0

            snapshots_logger = EventLogger()

            data_source.add_listener(
                event_tag=OrderBookDataSourceEvent.SNAPSHOT_EVENT, listener=snapshots_logger
            )

            _, snapshot_delivered = self.configure_orderbook_snapshot(
                timestamp=self.initial_timestamp, bids=[[9, 1], [8, 2]], asks=[[11, 3]]
            )

            self.async_run_with_timeout(coro=data_source.start())
            self.async_run_with_timeout(coro=snapshot_delivered.wait())

            self.assertEqual(1, len(snapshots_logger.event_log))

            snapshot_event: OrderBookMessage = snapshots_logger.event_log[0]

            self.assertEqual(self.initial_timestamp, snapshot_event.timestamp)
            self.assertEqual(2, len(snapshot_event.bids))
            self.assertEqual(9, snapshot_event.bids[0].price)
            self.assertEqual(1, snapshot_event.bids[0].amount)
            self.assertEqual(1, len(snapshot_event.asks))
            self.assertEqual(11, snapshot_event.asks[0].price)
            self.assertEqual(3, snapshot_event.asks[0].amount)

        def test_minimum_delay_between_requests_for_snapshot_events(self):
            self.async_run_with_timeout(self.data_source.stop())

            minimum_delay = 0.5

            data_source = self.build_api_data_source()
            self.additional_data_sources_to_stop_on_tear_down.append(data_source)
            data_source.min_snapshots_update_interval = minimum_delay
            data_source.max_snapshots_update_interval = minimum_delay + 1

            snapshots_logger = EventLogger()

            data_source.add_listener(
                event_tag=OrderBookDataSourceEvent.SNAPSHOT_EVENT, listener=snapshots_logger
            )

            # startup
            self.configure_orderbook_snapshot(
                timestamp=self.initial_timestamp, bids=[[10, 2]], asks=[]
            )
            self.async_run_with_timeout(coro=data_source.start())

            # first snapshot
            snapshot_requested, _ = self.configure_orderbook_snapshot(
                timestamp=self.initial_timestamp, bids=[[11, 3]], asks=[]
            )

            self.async_run_with_timeout(coro=snapshot_requested.wait())
            first_request_ts = time.time()

            # second snapshot
            snapshot_requested, snapshot_delivered = self.configure_orderbook_snapshot(
                timestamp=self.initial_timestamp, bids=[[12, 4]], asks=[]
            )
            self.async_run_with_timeout(coro=snapshot_requested.wait())
            second_request_ts = time.time()

            self.assertGreater(second_request_ts - first_request_ts, minimum_delay)

            self.async_run_with_timeout(coro=snapshot_delivered.wait())

            snapshot_event: OrderBookMessage = snapshots_logger.event_log[-1]

            self.assertEqual(12, snapshot_event.bids[0].price)
            self.assertEqual(4, snapshot_event.bids[0].amount)
            self.assertFalse(
                self.is_logged(
                    log_level="WARNING",
                    message=f"Snapshot update took longer than {self.data_source.max_snapshots_update_interval}.",
                )
            )

        def test_maximum_delay_between_requests_for_snapshot_events(self):
            self.async_run_with_timeout(self.data_source.stop())

            maximum_delay = 0.1

            data_source = self.build_api_data_source()
            self.additional_data_sources_to_stop_on_tear_down.append(data_source)
            data_source.min_snapshots_update_interval = 0
            data_source.max_snapshots_update_interval = maximum_delay

            snapshots_logger = EventLogger()

            data_source.add_listener(
                event_tag=OrderBookDataSourceEvent.SNAPSHOT_EVENT, listener=snapshots_logger
            )

            # startup
            self.configure_orderbook_snapshot(
                timestamp=self.initial_timestamp, bids=[[10, 2]], asks=[]
            )
            self.async_run_with_timeout(coro=data_source.start())

            # first snapshot
            snapshot_requested, slow_snapshot_delivered = self.configure_orderbook_snapshot(
                timestamp=self.initial_timestamp + 1, bids=[[11, 3]], asks=[], latency=maximum_delay * 2
            )

            first_request_ts = time.time()
            self.async_run_with_timeout(coro=snapshot_requested.wait())

            # second snapshot
            snapshot_requested, quick_snapshot_delivered = self.configure_orderbook_snapshot(
                timestamp=self.initial_timestamp + 2, bids=[[12, 4]], asks=[]
            )
            self.async_run_with_timeout(coro=snapshot_requested.wait(), timeout=maximum_delay * 2)
            second_request_ts = time.time()

            self.assertLess(second_request_ts - first_request_ts, maximum_delay * 1.1)
            self.assertGreater(second_request_ts - first_request_ts, maximum_delay * 0.9)

            self.async_run_with_timeout(coro=quick_snapshot_delivered.wait())

            snapshot_event: OrderBookMessage = snapshots_logger.event_log[-1]

            self.assertEqual(12, snapshot_event.bids[0].price)
            self.assertEqual(4, snapshot_event.bids[0].amount)

            self.async_run_with_timeout(coro=slow_snapshot_delivered.wait())

            self.assertTrue(
                self.is_logged(
                    log_level="WARNING",
                    message=f"Snapshot update took longer than {data_source.max_snapshots_update_interval}.",
                )
            )

        def test_get_account_balances(self):
            self.configure_account_balances_response(
                base_total_balance=self.expected_base_total_balance,
                base_available_balance=self.expected_base_available_balance,
                quote_total_balance=self.expected_quote_total_balance,
                quote_available_balance=self.expected_quote_available_balance,
            )

            sub_account_balances = self.async_run_with_timeout(coro=self.data_source.get_account_balances())

            self.assertEqual(self.expected_base_total_balance, sub_account_balances[self.base]["total_balance"])
            self.assertEqual(self.expected_base_available_balance, sub_account_balances[self.base]["available_balance"])
            self.assertEqual(self.expected_quote_total_balance, sub_account_balances[self.quote]["total_balance"])
            self.assertEqual(
                self.expected_quote_available_balance, sub_account_balances[self.quote]["available_balance"]
            )

        def test_get_order_status_update(self):
            creation_transaction_hash = "0x7cb2eafc389349f86da901cdcbfd9119425a2ea84d61c17b6ded778b6fd2g81d"  # noqa: mock
            in_flight_order = GatewayInFlightOrder(
                client_order_id=self.expected_buy_client_order_id,
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                creation_timestamp=self.initial_timestamp,
                price=self.expected_buy_order_price,
                amount=self.expected_buy_order_size,
                creation_transaction_hash=creation_transaction_hash,
                exchange_order_id=self.expected_buy_exchange_order_id,
            )
            self.enqueue_order_status_response(
                timestamp=self.initial_timestamp + 1,
                trading_pair=in_flight_order.trading_pair,
                exchange_order_id=self.expected_buy_exchange_order_id,
                client_order_id=in_flight_order.client_order_id,
                status=OrderState.PARTIALLY_FILLED,
            )

            status_update: OrderUpdate = self.async_run_with_timeout(
                coro=self.data_source.get_order_status_update(in_flight_order=in_flight_order)
            )

            self.assertEqual(self.trading_pair, status_update.trading_pair)
            self.assertEqual(self.initial_timestamp + 1, status_update.update_timestamp)
            self.assertEqual(OrderState.PARTIALLY_FILLED, status_update.new_state)
            self.assertEqual(in_flight_order.client_order_id, status_update.client_order_id)
            self.assertEqual(self.expected_buy_exchange_order_id, status_update.exchange_order_id)

        def test_get_all_order_fills_no_fills(self):
            expected_order_id = "0x6ba1eafc389349f86da901cdcbfd9119425a2ea84d61c17b6ded778b6fd2f70c"  # noqa: mock
            self.configure_empty_order_fills_response()
            in_flight_order = GatewayInFlightOrder(
                client_order_id="someOrderId",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.SELL,
                creation_timestamp=self.initial_timestamp - 10,
                price=self.expected_sell_order_price,
                amount=self.expected_sell_order_size,
                exchange_order_id=expected_order_id,
            )

            trade_updates = self.async_run_with_timeout(
                coro=self.data_source.get_all_order_fills(in_flight_order=in_flight_order)
            )

            self.assertEqual(0, len(trade_updates))

        def test_get_all_order_fills(self):
            expected_fill_ts = self.initial_timestamp + 10
            self.configure_trade_fill_response(
                timestamp=expected_fill_ts,
                exchange_order_id=self.expected_sell_exchange_order_id,
                price=self.expected_fill_price,
                size=self.expected_fill_size,
                fee=self.expected_fill_fee,
                trade_id=self.expected_fill_trade_id,
                is_taker=True,
            )
            in_flight_order = GatewayInFlightOrder(
                client_order_id=self.expected_sell_client_order_id,
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.SELL,
                creation_timestamp=self.initial_timestamp - 10,
                price=self.expected_sell_order_price,
                amount=self.expected_sell_order_size,
                exchange_order_id=self.expected_sell_exchange_order_id,
            )

            trade_updates: List[TradeUpdate] = self.async_run_with_timeout(
                coro=self.data_source.get_all_order_fills(in_flight_order=in_flight_order)
            )

            self.assertEqual(1, len(trade_updates))

            trade_update = trade_updates[0]

            self.assertEqual(self.expected_fill_trade_id, trade_update.trade_id)
            self.assertEqual(self.expected_sell_client_order_id, trade_update.client_order_id)
            self.assertEqual(self.expected_sell_exchange_order_id, trade_update.exchange_order_id)
            self.assertEqual(self.trading_pair, trade_update.trading_pair)
            self.assertEqual(expected_fill_ts, trade_update.fill_timestamp)
            self.assertEqual(self.expected_fill_price, trade_update.fill_price)
            self.assertEqual(self.expected_fill_size, trade_update.fill_base_amount)
            self.assertEqual(self.expected_fill_size * self.expected_fill_price, trade_update.fill_quote_amount)
            self.assertEqual(self.expected_fill_fee, trade_update.fee)
            self.assertTrue(trade_update.is_taker)

        def test_check_network_status(self):
            self.configure_check_network_failure()

            status = self.async_run_with_timeout(coro=self.data_source.check_network_status())

            self.assertEqual(NetworkStatus.NOT_CONNECTED, status)

            self.configure_check_network_success()

            status = self.async_run_with_timeout(coro=self.data_source.check_network_status())

            self.assertEqual(NetworkStatus.CONNECTED, status)

        def test_get_trading_fees(self):
            all_trading_fees = self.async_run_with_timeout(coro=self.data_source.get_trading_fees())

            self.assertIn(self.trading_pair, all_trading_fees)

            pair_trading_fees: MakerTakerExchangeFeeRates = all_trading_fees[self.trading_pair]

            self.assertEqual(self.expected_maker_taker_fee_rates, pair_trading_fees)

        def test_delivers_balance_events(self):
            if self.data_source.real_time_balance_update:
                raise NotImplementedError
