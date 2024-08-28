import asyncio
import unittest
from decimal import Decimal
from test.hummingbot.connector.gateway.clob_spot.data_sources.injective.injective_mock_utils import InjectiveClientMock
from typing import Awaitable, Dict, List, Mapping
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.client.config.fee_overrides_config_map import init_fee_overrides_config
from hummingbot.client.config.trade_fee_schema_loader import TradeFeeSchemaLoader
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.connector.gateway.clob_spot.data_sources.injective.injective_api_data_source import (
    InjectiveAPIDataSource,
)
from hummingbot.connector.gateway.clob_spot.gateway_clob_spot import GatewayCLOBSPOT
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.clock import Clock
from hummingbot.core.clock_mode import ClockMode
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    SellOrderCreatedEvent,
)
from hummingbot.core.network_iterator import NetworkStatus


class GatewayCLOBSPOTTest(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0
    base_asset: str
    quote_asset: str
    trading_pair: str
    inj_trading_pair: str
    wallet_address: str
    clock_tick_size: float

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.base_asset, quote=cls.quote_asset)
        cls.inj_trading_pair = combine_to_hb_trading_pair(base="INJ", quote=cls.quote_asset)
        cls.wallet_address = "someWalletAddress"
        cls.clock_tick_size = 1

    def setUp(self) -> None:
        super().setUp()

        self.log_records = []
        self.async_tasks: List[asyncio.Task] = []

        self.start_timestamp = 1669100347689
        self.clob_data_source_mock = InjectiveClientMock(
            initial_timestamp=self.start_timestamp,
            sub_account_id=self.wallet_address,
            base=self.base_asset,
            quote=self.quote_asset,
        )
        self.clob_data_source_mock.start()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        connector_spec = {
            "chain": "someChain",
            "network": "mainnet",
            "wallet_address": self.wallet_address,
        }
        api_data_source = InjectiveAPIDataSource(
            trading_pairs=[self.trading_pair],
            connector_spec=connector_spec,
            client_config_map=client_config_map,
        )
        self.exchange = GatewayCLOBSPOT(
            client_config_map=client_config_map,
            api_data_source=api_data_source,
            connector_name="injective",
            chain="injective",
            network="mainnet",
            address=self.wallet_address,
            trading_pairs=[self.trading_pair],
        )

        self.end_timestamp = self.start_timestamp + self.exchange.LONG_POLL_INTERVAL + 1
        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)
        self.clock.add_iterator(iterator=self.exchange)

        api_data_source.logger().setLevel(1)
        api_data_source.logger().addHandler(self)
        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._order_tracker.logger().setLevel(1)
        self.exchange._order_tracker.logger().addHandler(self)

        self.initialize_event_loggers()

        self.async_run_with_timeout(coroutine=self.exchange.start_network())

    def tearDown(self) -> None:
        for task in self.async_tasks:
            task.cancel()
        self.clob_data_source_mock.stop()
        self.async_run_with_timeout(coroutine=self.exchange.stop_network())
        super().tearDown()

    @property
    def expected_supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    @property
    def expected_exchange_order_id(self) -> str:
        return "0x6df823e0adc0d4811e8d25d7380c1b45e43b16b0eea6f109cc1fb31d31aeddc7"  # noqa: mock

    @property
    def expected_transaction_hash(self) -> str:
        return "0xc7287236f64484b476cfbec0fd21bc49d85f8850c8885665003928a122041e18"  # noqa: mock

    @property
    def expected_trade_id(self) -> str:
        return "19889401_someTradeId"

    @property
    def expected_latest_price(self) -> float:
        return 100

    @property
    def expected_trading_rule(self) -> TradingRule:
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=self.clob_data_source_mock.min_quantity_tick_size,
            min_price_increment=self.clob_data_source_mock.min_price_tick_size,
            min_base_amount_increment=self.clob_data_source_mock.min_quantity_tick_size,
            min_quote_amount_increment=self.clob_data_source_mock.min_price_tick_size,
        )

    @property
    def expected_order_price(self) -> Decimal:
        return Decimal("10_000")

    @property
    def expected_order_size(self) -> Decimal:
        return Decimal("2")

    @property
    def expected_partial_fill_size(self) -> Decimal:
        return self.expected_order_size / 2

    @property
    def expected_full_fill_fee(self) -> TradeFeeBase:
        expected_fee = self.clob_data_source_mock.maker_fee_rate * self.expected_order_price
        return AddedToCostTradeFee(
            flat_fees=[TokenAmount(token=self.quote_asset, amount=expected_fee)]
        )

    @property
    def expected_partial_fill_fee(self) -> TradeFeeBase:
        expected_fee = self.clob_data_source_mock.maker_fee_rate * self.expected_partial_fill_size
        return AddedToCostTradeFee(
            flat_fees=[TokenAmount(token=self.quote_asset, amount=expected_fee)]
        )

    def handle(self, record):
        self.log_records.append(record)

    def is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def is_logged_that_starts_with(self, log_level: str, message_starts_with: str):
        return any(
            record.levelname == log_level and record.getMessage().startswith(message_starts_with)
            for record in self.log_records
        )

    @staticmethod
    def async_run_with_timeout(coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def initialize_event_loggers(self):
        self.buy_order_completed_logger = EventLogger()
        self.buy_order_created_logger = EventLogger()
        self.order_cancelled_logger = EventLogger()
        self.order_failure_logger = EventLogger()
        self.order_filled_logger = EventLogger()
        self.sell_order_completed_logger = EventLogger()
        self.sell_order_created_logger = EventLogger()

        events_and_loggers = [
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
            (MarketEvent.BuyOrderCreated, self.buy_order_created_logger),
            (MarketEvent.OrderCancelled, self.order_cancelled_logger),
            (MarketEvent.OrderFailure, self.order_failure_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger),
            (MarketEvent.SellOrderCompleted, self.sell_order_completed_logger),
            (MarketEvent.SellOrderCreated, self.sell_order_created_logger)]

        for event, logger in events_and_loggers:
            self.exchange.add_listener(event, logger)

    @staticmethod
    def expected_initial_status_dict() -> Dict[str, bool]:
        return {
            "symbols_mapping_initialized": False,
            "order_books_initialized": False,
            "account_balance": False,
            "trading_rule_initialized": False,
            "user_stream_initialized": False,
            "api_data_source_initialized": False,
        }

    @staticmethod
    def expected_initialized_status_dict() -> Dict[str, bool]:
        return {
            "symbols_mapping_initialized": True,
            "order_books_initialized": True,
            "account_balance": True,
            "trading_rule_initialized": True,
            "user_stream_initialized": True,
            "api_data_source_initialized": True,
        }

    def place_buy_order(self, size: Decimal = Decimal("100"), price: Decimal = Decimal("10_000")):
        order_id = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=size,
            order_type=OrderType.LIMIT,
            price=price,
        )
        return order_id

    def place_sell_order(self, size: Decimal = Decimal("100"), price: Decimal = Decimal("10_000")):
        order_id = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=size,
            order_type=OrderType.LIMIT,
            price=price,
        )
        return order_id

    def test_supported_order_types(self):
        supported_types = self.exchange.supported_order_types()
        self.assertEqual(self.expected_supported_order_types, supported_types)

    def test_restore_tracking_states_only_registers_open_orders(self):
        orders = []
        orders.append(GatewayInFlightOrder(
            client_order_id="11",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
        ))
        orders.append(GatewayInFlightOrder(
            client_order_id="12",
            exchange_order_id="22",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.CANCELED
        ))
        orders.append(GatewayInFlightOrder(
            client_order_id="13",
            exchange_order_id="23",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        ))
        orders.append(GatewayInFlightOrder(
            client_order_id="14",
            exchange_order_id="24",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FAILED
        ))

        tracking_states = {order.client_order_id: order.to_json() for order in orders}

        self.exchange.restore_tracking_states(tracking_states)

        self.assertIn("11", self.exchange.in_flight_orders)
        self.assertNotIn("12", self.exchange.in_flight_orders)
        self.assertNotIn("13", self.exchange.in_flight_orders)
        self.assertNotIn("14", self.exchange.in_flight_orders)

    def test_all_trading_pairs(self):
        self.exchange._set_trading_pair_symbol_map(None)

        all_trading_pairs = self.async_run_with_timeout(coroutine=self.exchange.all_trading_pairs())

        self.assertEqual(2, len(all_trading_pairs))
        self.assertIn(self.trading_pair, all_trading_pairs)
        self.assertIn(self.inj_trading_pair, all_trading_pairs)

    def test_get_last_trade_prices(self):
        fee = AddedToCostTradeFee(flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("0.001"))])
        self.clob_data_source_mock.configure_spot_trades_response_to_request_without_exchange_order_id(
            timestamp=self.start_timestamp,
            price=Decimal(self.expected_latest_price),
            size=Decimal("2"),
            maker_fee=fee,
            taker_fee=fee,
        )

        latest_prices: Dict[str, float] = self.async_run_with_timeout(
            self.exchange.get_last_traded_prices(trading_pairs=[self.trading_pair])
        )

        self.assertEqual(1, len(latest_prices))
        self.assertEqual(self.expected_latest_price, latest_prices[self.trading_pair])

    def test_check_network_success(self):
        self.clob_data_source_mock.configure_check_network_success()

        network_status = self.async_run_with_timeout(coroutine=self.exchange.check_network(), timeout=2)

        self.assertEqual(NetworkStatus.CONNECTED, network_status)

    def test_check_network_failure(self):
        self.clob_data_source_mock.configure_check_network_failure()

        network_status = self.async_run_with_timeout(coroutine=self.exchange.check_network(), timeout=2)

        self.assertEqual(NetworkStatus.NOT_CONNECTED, network_status)

    def test_check_network_raises_cancel_exception(self):
        self.clob_data_source_mock.configure_check_network_failure(exc=asyncio.CancelledError)

        with self.assertRaises(expected_exception=asyncio.CancelledError):
            self.async_run_with_timeout(coroutine=self.exchange.check_network())

    def test_init_trading_pair_symbol_map(self):
        symbol_map = self.async_run_with_timeout(coroutine=self.exchange.trading_pair_symbol_map())

        self.assertIsInstance(symbol_map, Mapping)
        self.assertEqual(2, len(symbol_map))
        self.assertIn(self.clob_data_source_mock.exchange_trading_pair, symbol_map)
        self.assertIn(self.trading_pair, symbol_map.inverse)
        self.assertIn(self.inj_trading_pair, symbol_map.inverse)

    def test_initial_status_dict(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        connector_spec = {
            "chain": "someChain",
            "network": "mainnet",
            "wallet_address": self.wallet_address,
        }
        api_data_source = InjectiveAPIDataSource(
            trading_pairs=[self.trading_pair],
            connector_spec=connector_spec,
            client_config_map=client_config_map,
        )
        exchange = GatewayCLOBSPOT(
            client_config_map=client_config_map,
            api_data_source=api_data_source,
            connector_name="injective",
            chain="cosmos",
            network="mainnet",
            address=self.wallet_address,
            trading_pairs=[self.trading_pair],
        )

        status_dict = exchange.status_dict

        expected_initial_dict = self.expected_initial_status_dict()

        self.assertEqual(expected_initial_dict, status_dict)
        self.assertFalse(exchange.ready)

    @patch("hummingbot.core.data_type.order_book_tracker.OrderBookTracker._sleep")
    def test_full_initialization_and_de_initialization(self, _: AsyncMock):
        self.clob_data_source_mock.configure_trades_response_no_trades()
        self.clob_data_source_mock.configure_get_account_balances_response(
            base_total_balance=Decimal("10"),
            base_available_balance=Decimal("9"),
            quote_total_balance=Decimal("200"),
            quote_available_balance=Decimal("150"),
        )

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        connector_spec = {
            "chain": "someChain",
            "network": "mainnet",
            "wallet_address": self.wallet_address,
        }
        api_data_source = InjectiveAPIDataSource(
            trading_pairs=[self.trading_pair],
            connector_spec=connector_spec,
            client_config_map=client_config_map,
        )
        exchange = GatewayCLOBSPOT(
            client_config_map=client_config_map,
            api_data_source=api_data_source,
            connector_name="injective",
            chain="cosmos",
            network="mainnet",
            address=self.wallet_address,
            trading_pairs=[self.trading_pair],
        )

        self.assertEqual(0, len(exchange.trading_fees))

        self.async_run_with_timeout(coroutine=exchange.start_network())

        self.clock.add_iterator(exchange)
        self.clock.backtest_til(self.start_timestamp + exchange.SHORT_POLL_INTERVAL)
        self.clob_data_source_mock.run_until_all_items_delivered()

        status_dict = exchange.status_dict

        expected_initial_dict = self.expected_initialized_status_dict()

        self.assertEqual(expected_initial_dict, status_dict)
        self.assertTrue(exchange.ready)
        self.assertNotEqual(0, len(exchange.trading_fees))
        self.assertIn(self.trading_pair, exchange.trading_fees)

        trading_fees_data = exchange.trading_fees[self.trading_pair]
        service_provider_rebate = Decimal("1") - self.clob_data_source_mock.service_provider_fee
        expected_maker_fee = self.clob_data_source_mock.maker_fee_rate * service_provider_rebate
        expected_taker_fee = self.clob_data_source_mock.taker_fee_rate * service_provider_rebate

        self.assertEqual(expected_maker_fee, trading_fees_data.maker)
        self.assertEqual(expected_taker_fee, trading_fees_data.taker)

    def test_update_trading_rules(self):
        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        trading_rule: TradingRule = self.exchange.trading_rules[self.trading_pair]

        self.assertTrue(self.trading_pair in self.exchange.trading_rules)
        self.assertEqual(repr(self.expected_trading_rule), repr(trading_rule))

        trading_rule_with_default_values = TradingRule(trading_pair=self.trading_pair)

        # The following element can't be left with the default value because that breaks quantization in Cython
        self.assertNotEqual(trading_rule_with_default_values.min_base_amount_increment,
                            trading_rule.min_base_amount_increment)
        self.assertNotEqual(trading_rule_with_default_values.min_price_increment,
                            trading_rule.min_price_increment)

    def test_create_buy_limit_order_successfully(self):
        self.exchange._set_current_timestamp(self.start_timestamp)
        self.clob_data_source_mock.configure_place_order_response(
            timestamp=self.start_timestamp,
            transaction_hash=self.expected_transaction_hash,
            exchange_order_id=self.expected_exchange_order_id,
            trade_type=TradeType.BUY,
            price=self.expected_order_price,
            size=self.expected_order_size,
        )

        order_id = self.place_buy_order()
        self.clob_data_source_mock.run_until_all_items_delivered()
        order = self.exchange._order_tracker.active_orders[order_id]

        self.clob_data_source_mock.configure_order_status_update_response(
            timestamp=self.start_timestamp + 1,
            creation_transaction_hash=self.expected_transaction_hash,
            order=order,
        )

        self.clob_data_source_mock.run_until_all_items_delivered()

        self.assertIn(order_id, self.exchange.in_flight_orders)

        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(str(self.expected_exchange_order_id), create_event.exchange_order_id)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Created {OrderType.LIMIT.name} {TradeType.BUY.name} order {order_id} for "
                f"{Decimal('100.000')} {self.trading_pair} at {Decimal('10000.00000')}."
            )
        )

    def test_create_sell_limit_order_successfully(self):
        self.exchange._set_current_timestamp(self.start_timestamp)
        self.clob_data_source_mock.configure_place_order_response(
            timestamp=self.start_timestamp,
            transaction_hash=self.expected_transaction_hash,
            exchange_order_id=self.expected_exchange_order_id,
            trade_type=TradeType.BUY,
            price=self.expected_order_price,
            size=self.expected_order_size,
        )

        order_id = self.place_sell_order()
        self.clob_data_source_mock.run_until_all_items_delivered()
        order = self.exchange._order_tracker.active_orders[order_id]

        self.clob_data_source_mock.configure_order_status_update_response(
            timestamp=self.start_timestamp + 1,
            creation_transaction_hash=self.expected_transaction_hash,
            order=order,
        )

        self.clob_data_source_mock.run_until_all_items_delivered()

        self.assertIn(order_id, self.exchange.in_flight_orders)

        create_event: SellOrderCreatedEvent = self.sell_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(str(self.expected_exchange_order_id), create_event.exchange_order_id)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Created {OrderType.LIMIT.name} {TradeType.SELL.name} order {order_id} for "
                f"{Decimal('100.000')} {self.trading_pair} at {Decimal('10000.00000')}."
            )
        )

    def test_create_order_fails_and_raises_failure_event(self):
        self.exchange._set_current_timestamp(self.start_timestamp)

        self.clob_data_source_mock.configure_place_order_fails_response(exception=RuntimeError("some error"))

        order_id = self.place_buy_order(
            size=self.expected_order_size, price=self.expected_order_price
        )

        self.clob_data_source_mock.run_until_place_order_called()

        self.assertNotIn(order_id, self.exchange.in_flight_orders)

        self.assertEquals(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual(order_id, failure_event.order_id)

        self.assertTrue(
            expr=self.is_logged_that_starts_with(
                log_level="NETWORK",
                message_starts_with=(
                    f"Error submitting buy LIMIT order to {self.exchange.name_cap} for"
                )
            )
        )
        self.assertTrue(
            expr=self.is_logged(
                log_level="INFO",
                message=(
                    f"Order {order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                    f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
                    f"client_order_id='{order_id}', exchange_order_id=None, misc_updates=None)"
                )
            )
        )

    def test_create_order_fails_when_trading_rule_error_and_raises_failure_event(self):
        self.exchange._set_current_timestamp(self.start_timestamp)

        self.clob_data_source_mock.configure_place_order_fails_response(exception=RuntimeError("some error"))

        order_id_for_invalid_order = self.place_buy_order(
            size=Decimal("0.0001"), price=Decimal("0.0001")
        )
        # The second order is used only to have the event triggered and avoid using timeouts for tests
        order_id = self.place_buy_order()
        self.clob_data_source_mock.run_until_place_order_called()

        self.assertNotIn(order_id_for_invalid_order, self.exchange.in_flight_orders)
        self.assertNotIn(order_id, self.exchange.in_flight_orders)

        self.assertEquals(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual(order_id_for_invalid_order, failure_event.order_id)

        self.assertTrue(
            self.is_logged(
                "WARNING",
                "Buy order amount 0.0001 is lower than the minimum order "
                "size 0.001. The order will not be created, increase the "
                "amount to be higher than the minimum order size."
            )
        )
        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Order {order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='{order_id}', exchange_order_id=None, misc_updates=None)"
            )
        )

    def test_cancel_order_successfully(self):
        self.exchange._set_current_timestamp(self.start_timestamp)

        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=self.expected_exchange_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=self.expected_order_price,
            amount=self.expected_order_size,
            order_type=OrderType.LIMIT,
        )

        self.assertIn("11", self.exchange.in_flight_orders)
        order: GatewayInFlightOrder = self.exchange.in_flight_orders["11"]

        self.clob_data_source_mock.configure_cancel_order_response(
            timestamp=self.start_timestamp, transaction_hash=self.expected_transaction_hash
        )

        self.exchange.cancel(trading_pair=order.trading_pair, client_order_id=order.client_order_id)
        self.clob_data_source_mock.run_until_cancel_order_called()

        if self.exchange.is_cancel_request_in_exchange_synchronous:
            self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
            self.assertTrue(order.is_cancelled)
            cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
            self.assertEqual(order.client_order_id, cancel_event.order_id)

            self.assertTrue(
                self.is_logged(
                    "INFO",
                    f"Successfully canceled order {order.client_order_id}."
                )
            )
        else:
            self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
            self.assertTrue(order.is_pending_cancel_confirmation)

        self.assertEqual(self.expected_transaction_hash, order.cancel_tx_hash)

    def test_cancel_order_raises_failure_event_when_request_fails(self):
        self.exchange._set_current_timestamp(self.start_timestamp)

        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=self.expected_exchange_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=self.expected_order_price,
            amount=self.expected_order_size,
            order_type=OrderType.LIMIT,
        )

        self.assertIn("11", self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders["11"]

        self.clob_data_source_mock.configure_cancel_order_fails_response(exception=RuntimeError("some error"))

        self.exchange.cancel(trading_pair=self.trading_pair, client_order_id="11")
        self.clob_data_source_mock.run_until_cancel_order_called()

        self.assertEquals(0, len(self.order_cancelled_logger.event_log))
        self.assertTrue(any(log.msg.startswith(f"Failed to cancel order {order.client_order_id}")
                            for log in self.log_records))

    def test_cancel_two_orders_with_cancel_all_and_one_fails(self):
        self.exchange._set_current_timestamp(self.start_timestamp)

        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=self.expected_exchange_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=self.expected_order_price,
            amount=self.expected_order_size,
            order_type=OrderType.LIMIT,
        )

        self.assertIn("11", self.exchange.in_flight_orders)
        order1 = self.exchange.in_flight_orders["11"]

        self.exchange.start_tracking_order(
            order_id="12",
            exchange_order_id="5",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("11000"),
            amount=Decimal("90"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("12", self.exchange.in_flight_orders)
        order2 = self.exchange.in_flight_orders["12"]

        self.clob_data_source_mock.configure_one_success_one_failure_order_cancelation_responses(
            success_timestamp=self.start_timestamp,
            success_transaction_hash=self.expected_transaction_hash,
            failure_exception=RuntimeError("some error"),
        )

        cancellation_results = self.async_run_with_timeout(self.exchange.cancel_all(10))

        self.assertEqual(2, len(cancellation_results))
        self.assertIn(CancellationResult(order1.client_order_id, True), cancellation_results)
        self.assertIn(CancellationResult(order2.client_order_id, False), cancellation_results)

    def test_batch_order_cancel(self):
        self.exchange._set_current_timestamp(self.start_timestamp)

        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=self.expected_exchange_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=self.expected_order_price,
            amount=self.expected_order_size,
            order_type=OrderType.LIMIT,
        )
        self.exchange.start_tracking_order(
            order_id="12",
            exchange_order_id=self.expected_exchange_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=self.expected_order_price,
            amount=self.expected_order_size,
            order_type=OrderType.LIMIT,
        )

        buy_order_to_cancel: InFlightOrder = self.exchange.in_flight_orders["11"]
        sell_order_to_cancel: InFlightOrder = self.exchange.in_flight_orders["12"]
        orders_to_cancel = [buy_order_to_cancel, sell_order_to_cancel]

        self.clob_data_source_mock.configure_batch_order_cancel_response(
            timestamp=self.start_timestamp,
            transaction_hash="somehash",
            canceled_orders=orders_to_cancel,
        )

        self.exchange.batch_order_cancel(orders_to_cancel=self.exchange.limit_orders)

        self.clob_data_source_mock.run_until_all_items_delivered()

        self.assertIn(buy_order_to_cancel.client_order_id, self.exchange.in_flight_orders)
        self.assertIn(sell_order_to_cancel.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(buy_order_to_cancel.is_pending_cancel_confirmation)
        self.assertTrue(sell_order_to_cancel.is_pending_cancel_confirmation)

    def test_batch_order_create(self):
        self.exchange._set_current_timestamp(self.start_timestamp)

        buy_order_to_create = LimitOrder(
            client_order_id="",
            trading_pair=self.trading_pair,
            is_buy=True,
            base_currency=self.base_asset,
            quote_currency=self.quote_asset,
            price=Decimal("10"),
            quantity=Decimal("2"),
        )
        sell_order_to_create = LimitOrder(
            client_order_id="",
            trading_pair=self.trading_pair,
            is_buy=False,
            base_currency=self.base_asset,
            quote_currency=self.quote_asset,
            price=Decimal("11"),
            quantity=Decimal("3"),
        )
        orders_to_create = [buy_order_to_create, sell_order_to_create]

        orders: List[LimitOrder] = self.exchange.batch_order_create(orders_to_create=orders_to_create)

        buy_order_to_create_in_flight = GatewayInFlightOrder(
            client_order_id=orders[0].client_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            creation_timestamp=self.start_timestamp,
            price=orders[0].price,
            amount=orders[0].quantity,
            exchange_order_id="someEOID0",
        )
        sell_order_to_create_in_flight = GatewayInFlightOrder(
            client_order_id=orders[1].client_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            creation_timestamp=self.start_timestamp,
            price=orders[1].price,
            amount=orders[1].quantity,
            exchange_order_id="someEOID1",
        )
        orders_to_create_in_flight = [buy_order_to_create_in_flight, sell_order_to_create_in_flight]
        self.clob_data_source_mock.configure_batch_order_create_response(
            timestamp=self.start_timestamp,
            transaction_hash="somehash",
            created_orders=orders_to_create_in_flight,
        )

        self.assertEqual(2, len(orders))

        self.clob_data_source_mock.run_until_all_items_delivered()

        self.assertIn(buy_order_to_create_in_flight.client_order_id, self.exchange.in_flight_orders)
        self.assertIn(sell_order_to_create_in_flight.client_order_id, self.exchange.in_flight_orders)

        buy_create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_create_event.timestamp)
        self.assertEqual(self.trading_pair, buy_create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, buy_create_event.type)
        self.assertEqual(buy_order_to_create_in_flight.amount, buy_create_event.amount)
        self.assertEqual(buy_order_to_create_in_flight.price, buy_create_event.price)
        self.assertEqual(buy_order_to_create_in_flight.client_order_id, buy_create_event.order_id)
        self.assertEqual(buy_order_to_create_in_flight.exchange_order_id, buy_create_event.exchange_order_id)
        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Created {OrderType.LIMIT.name} {TradeType.BUY.name}"
                f" order {buy_order_to_create_in_flight.client_order_id} for "
                f"{buy_create_event.amount} {self.trading_pair} at {buy_create_event.price}."
            )
        )

    def test_update_balances(self):
        expected_base_total_balance = Decimal("100")
        expected_base_available_balance = Decimal("90")
        expected_quote_total_balance = Decimal("10")
        expected_quote_available_balance = Decimal("8")
        self.clob_data_source_mock.configure_get_account_balances_response(
            base_total_balance=expected_base_total_balance,
            base_available_balance=expected_base_available_balance,
            quote_total_balance=expected_quote_total_balance,
            quote_available_balance=expected_quote_available_balance,
        )

        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(expected_base_available_balance, available_balances[self.base_asset])
        self.assertEqual(expected_quote_available_balance, available_balances[self.quote_asset])
        self.assertEqual(expected_base_total_balance, total_balances[self.base_asset])
        self.assertEqual(expected_quote_total_balance, total_balances[self.quote_asset])

        expected_base_total_balance = Decimal("100")
        expected_base_available_balance = Decimal("90")
        expected_quote_total_balance = Decimal("0")
        expected_quote_available_balance = Decimal("0")
        self.clob_data_source_mock.configure_get_account_balances_response(
            base_total_balance=expected_base_total_balance,
            base_available_balance=expected_base_available_balance,
            quote_total_balance=expected_quote_total_balance,
            quote_available_balance=expected_quote_available_balance,
        )

        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertNotIn(self.quote_asset, available_balances)
        self.assertNotIn(self.quote_asset, total_balances)
        self.assertEqual(expected_base_available_balance, available_balances[self.base_asset])
        self.assertEqual(expected_base_total_balance, total_balances[self.base_asset])

    def test_update_order_status_when_filled(self):
        self.exchange._set_current_timestamp(self.start_timestamp)

        creation_transaction_hash = "someHash"
        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=self.expected_order_price,
            amount=self.expected_order_size,
        )
        order: GatewayInFlightOrder = self.exchange.in_flight_orders["11"]
        order.creation_transaction_hash = creation_transaction_hash

        self.clob_data_source_mock.configure_order_status_update_response(
            timestamp=self.start_timestamp,
            creation_transaction_hash=creation_transaction_hash,
            order=order,
            filled_size=self.expected_order_size,
        )

        self.clob_data_source_mock.configure_trades_response_with_exchange_order_id(
            timestamp=self.start_timestamp,
            exchange_order_id=self.expected_exchange_order_id,
            price=self.expected_order_price,
            size=self.expected_order_size,
            fee=self.expected_full_fill_fee,
            trade_id=self.expected_trade_id,
        )

        self.async_run_with_timeout(self.exchange._update_order_status())
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.clob_data_source_mock.run_until_all_items_delivered()

        self.async_run_with_timeout(order.wait_until_completely_filled())
        self.assertTrue(order.is_done)

        self.assertTrue(order.is_filled)

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[-1]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(order.price, fill_event.price)
        self.assertEqual(order.amount, fill_event.amount)
        self.assertEqual(self.expected_full_fill_fee, fill_event.trade_fee)

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(order.amount, buy_event.base_asset_amount)
        self.assertEqual(order.amount * order.price, buy_event.quote_asset_amount)
        self.assertEqual(order.order_type, buy_event.order_type)
        self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self.is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

    def test_update_order_status_when_canceled(self):
        self.exchange._set_current_timestamp(self.start_timestamp)

        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=self.expected_exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=self.expected_order_price,
            amount=self.expected_order_size,
        )
        order = self.exchange.in_flight_orders["11"]

        self.clob_data_source_mock.configure_order_status_update_response(
            timestamp=self.start_timestamp, order=order, is_canceled=True
        )

        self.async_run_with_timeout(self.exchange._update_order_status())

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)
        self.assertEqual(order.exchange_order_id, cancel_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self.is_logged("INFO", f"Successfully canceled order {order.client_order_id}.")
        )

    def test_update_order_status_when_cancel_transaction_minted(self):
        self.exchange._set_current_timestamp(self.start_timestamp)

        creation_transaction_hash = "someHash"
        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=self.expected_order_price,
            amount=self.expected_order_size,
        )
        order: GatewayInFlightOrder = self.exchange.in_flight_orders["11"]
        order.creation_transaction_hash = creation_transaction_hash
        order.cancel_tx_hash = self.expected_transaction_hash

        self.assertEqual(OrderState.PENDING_CREATE, order.current_state)

        self.clob_data_source_mock.configure_order_status_update_response(
            timestamp=self.start_timestamp + 1,
            order=order,
            creation_transaction_hash=creation_transaction_hash,
            cancelation_transaction_hash=self.expected_transaction_hash,
            is_canceled=True,
        )

        self.clob_data_source_mock.run_until_all_items_delivered()

        self.assertEqual(OrderState.CANCELED, order.current_state)
        self.assertEqual(self.expected_transaction_hash, order.cancel_tx_hash)

        buy_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual("11", buy_event.order_id)
        self.assertEqual(self.expected_exchange_order_id, buy_event.exchange_order_id)

    def test_update_order_status_when_order_has_not_changed(self):
        self.exchange._set_current_timestamp(self.start_timestamp)

        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=self.expected_order_price,
            amount=self.expected_order_size,
        )
        order: InFlightOrder = self.exchange.in_flight_orders["11"]

        self.clob_data_source_mock.configure_order_status_update_response(
            timestamp=self.start_timestamp,
            order=order,
            filled_size=Decimal("0"),
        )

        self.assertTrue(order.is_open)

        self.async_run_with_timeout(self.exchange._update_order_status())

        self.assertTrue(order.is_open)
        self.assertFalse(order.is_filled)
        self.assertFalse(order.is_done)

    def test_update_order_status_when_request_fails_marks_order_as_not_found(self):
        self.exchange._set_current_timestamp(self.start_timestamp)

        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=self.expected_order_price,
            amount=self.expected_order_size,
        )
        order: InFlightOrder = self.exchange.in_flight_orders["11"]

        self.clob_data_source_mock.configure_order_status_update_response(
            timestamp=self.start_timestamp, order=order, is_failed=True
        )

        self.async_run_with_timeout(self.exchange._update_order_status())

        self.assertTrue(order.is_open)
        self.assertFalse(order.is_filled)
        self.assertFalse(order.is_done)

        self.assertEqual(1, self.exchange._order_tracker._order_not_found_records[order.client_order_id])

    def test_update_order_status_when_order_has_not_changed_and_one_partial_fill(self):
        self.exchange._set_current_timestamp(self.start_timestamp)

        creation_transaction_hash = "someHash"
        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=self.expected_order_price,
            amount=self.expected_order_size,
        )
        order: GatewayInFlightOrder = self.exchange.in_flight_orders["11"]
        order.creation_transaction_hash = creation_transaction_hash
        order.order_fills[creation_transaction_hash] = None  # tod prevent creation transaction request

        self.clob_data_source_mock.configure_order_status_update_response(
            timestamp=self.start_timestamp, order=order, filled_size=self.expected_partial_fill_size
        )
        self.clob_data_source_mock.configure_trades_response_with_exchange_order_id(
            timestamp=self.start_timestamp + 1,
            exchange_order_id=order.exchange_order_id,
            price=order.price,
            size=self.expected_partial_fill_size,
            fee=self.expected_partial_fill_fee,
            trade_id=self.expected_trade_id,
        )

        self.assertTrue(order.is_open)

        self.async_run_with_timeout(self.exchange._update_order_status())

        self.assertTrue(order.is_open)
        self.assertEqual(OrderState.PARTIALLY_FILLED, order.current_state)

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(self.expected_order_price, fill_event.price)
        self.assertEqual(self.expected_partial_fill_size, fill_event.amount)
        self.assertEqual(self.expected_partial_fill_fee, fill_event.trade_fee)

    def test_update_order_status_when_filled_correctly_processed_even_when_trade_fill_update_fails(self):
        self.exchange._set_current_timestamp(self.start_timestamp)

        creation_transaction_hash = "someHash"
        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=self.expected_order_price,
            amount=self.expected_order_size,
        )
        order: GatewayInFlightOrder = self.exchange.in_flight_orders["11"]
        order.creation_transaction_hash = creation_transaction_hash

        self.clob_data_source_mock.configure_order_status_update_response(
            timestamp=self.start_timestamp,
            order=order,
            creation_transaction_hash=creation_transaction_hash,
            filled_size=order.amount,
        )
        self.clob_data_source_mock.configure_trades_response_fails()

        # Since the trade fill update will fail we need to manually set the event
        # to allow the ClientOrderTracker to process the last status update
        order.completely_filled_event.set()
        self.async_run_with_timeout(self.exchange._update_order_status())
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(order.wait_until_completely_filled())

        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_done)

        self.assertEqual(0, len(self.order_filled_logger.event_log))

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(Decimal(0), buy_event.base_asset_amount)
        self.assertEqual(Decimal(0), buy_event.quote_asset_amount)
        self.assertEqual(order.order_type, buy_event.order_type)
        self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self.is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

    def test_update_order_status_when_order_partially_filled_and_cancelled(self):
        self.exchange._set_current_timestamp(self.start_timestamp)

        creation_transaction_hash = "someHash"
        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=self.expected_order_price,
            amount=self.expected_order_size,
        )
        order: GatewayInFlightOrder = self.exchange.in_flight_orders["11"]
        order.creation_transaction_hash = creation_transaction_hash
        order.order_fills[creation_transaction_hash] = None  # to prevent creation transaction request

        self.clob_data_source_mock.configure_order_status_update_response(
            timestamp=self.start_timestamp, order=order, filled_size=self.expected_partial_fill_size
        )
        self.clob_data_source_mock.configure_trades_response_with_exchange_order_id(
            timestamp=self.start_timestamp,
            exchange_order_id=order.exchange_order_id,
            price=order.price,
            size=self.expected_partial_fill_size,
            fee=self.expected_partial_fill_fee,
            trade_id=self.expected_trade_id,
        )

        self.assertTrue(order.is_open)

        self.clock.backtest_til(self.start_timestamp + self.clock.tick_size * 1)
        self.clob_data_source_mock.run_until_all_items_delivered()

        self.assertTrue(order.is_open)
        self.assertEqual(OrderState.PARTIALLY_FILLED, order.current_state)

        order_partially_filled_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(order.client_order_id, order_partially_filled_event.order_id)
        self.assertEqual(order.trading_pair, order_partially_filled_event.trading_pair)
        self.assertEqual(order.trade_type, order_partially_filled_event.trade_type)
        self.assertEqual(order.order_type, order_partially_filled_event.order_type)
        self.assertEqual(self.expected_trade_id, order_partially_filled_event.exchange_trade_id)
        self.assertEqual(self.expected_order_price, order_partially_filled_event.price)
        self.assertEqual(self.expected_partial_fill_size, order_partially_filled_event.amount)
        self.assertEqual(self.expected_partial_fill_fee, order_partially_filled_event.trade_fee)
        self.assertEqual(self.exchange.current_timestamp, order_partially_filled_event.timestamp)

        self.clob_data_source_mock.configure_order_status_update_response(
            timestamp=self.start_timestamp,
            order=order,
            filled_size=self.expected_partial_fill_size,
            is_canceled=True,
        )

        self.async_run_with_timeout(self.exchange._update_order_status(), timeout=2)

        self.assertTrue(order.is_cancelled)
        self.assertEqual(OrderState.CANCELED, order.current_state)

    def test_user_stream_update_for_new_order(self):
        self.exchange._set_current_timestamp(self.start_timestamp)
        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=self.expected_order_price,
            amount=self.expected_order_size,
        )
        order = self.exchange.in_flight_orders["11"]

        self.clob_data_source_mock.configure_order_stream_event_for_in_flight_order(
            timestamp=self.start_timestamp, in_flight_order=order, filled_size=Decimal("0"),
        )

        self.clob_data_source_mock.run_until_all_items_delivered()

        event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, event.timestamp)
        self.assertEqual(order.order_type, event.type)
        self.assertEqual(order.trading_pair, event.trading_pair)
        self.assertEqual(order.amount, event.amount)
        self.assertEqual(order.price, event.price)
        self.assertEqual(order.client_order_id, event.order_id)
        self.assertEqual(order.exchange_order_id, event.exchange_order_id)
        self.assertTrue(order.is_open)

        tracked_order: InFlightOrder = list(self.exchange.in_flight_orders.values())[0]

        self.assertTrue(self.is_logged("INFO", tracked_order.build_order_created_message()))

    def test_user_stream_update_for_canceled_order(self):
        self.exchange._set_current_timestamp(self.start_timestamp)
        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=self.expected_order_price,
            amount=self.expected_order_size,
        )
        order = self.exchange.in_flight_orders["11"]

        self.clob_data_source_mock.configure_order_stream_event_for_in_flight_order(
            timestamp=self.start_timestamp, in_flight_order=order, is_canceled=True
        )
        self.clob_data_source_mock.run_until_all_items_delivered()

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)
        self.assertEqual(order.exchange_order_id, cancel_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_cancelled)
        self.assertTrue(order.is_done)

        self.assertTrue(
            self.is_logged("INFO", f"Successfully canceled order {order.client_order_id}.")
        )

    def test_user_stream_update_for_order_full_fill(self):
        self.exchange._set_current_timestamp(self.start_timestamp)
        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=self.expected_order_price,
            amount=self.expected_order_size,
        )
        order = self.exchange.in_flight_orders["11"]

        self.clob_data_source_mock.configure_order_stream_event_for_in_flight_order(
            timestamp=self.start_timestamp,
            in_flight_order=order,
            filled_size=self.expected_order_size,
        )
        self.clob_data_source_mock.configure_trade_stream_event(
            timestamp=self.start_timestamp,
            price=self.expected_order_price,
            size=self.expected_order_size,
            maker_fee=self.expected_full_fill_fee,
            taker_fee=self.expected_full_fill_fee,
            exchange_order_id=self.expected_exchange_order_id,
            taker_trade_id=self.expected_trade_id,
        )

        self.clob_data_source_mock.run_until_all_items_delivered()
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(order.wait_until_completely_filled())

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(order.price, fill_event.price)
        self.assertEqual(order.amount, fill_event.amount)
        expected_fee = self.expected_full_fill_fee
        self.assertEqual(expected_fee, fill_event.trade_fee)

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(order.amount, buy_event.base_asset_amount)
        self.assertEqual(order.amount * fill_event.price, buy_event.quote_asset_amount)
        self.assertEqual(order.order_type, buy_event.order_type)
        self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_done)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

    def test_user_stream_update_for_partially_cancelled_order(self):
        self.exchange._set_current_timestamp(self.start_timestamp)
        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=self.expected_order_price,
            amount=self.expected_order_size,
        )
        order: InFlightOrder = self.exchange.in_flight_orders["11"]

        self.clob_data_source_mock.configure_order_stream_event_for_in_flight_order(
            timestamp=self.start_timestamp, in_flight_order=order
        )
        self.clob_data_source_mock.configure_order_stream_event_for_in_flight_order(
            timestamp=self.start_timestamp + 1, in_flight_order=order, filled_size=self.expected_partial_fill_size
        )
        self.clob_data_source_mock.configure_trade_stream_event(
            timestamp=self.start_timestamp + 1,
            price=self.expected_order_price,
            size=self.expected_partial_fill_size,
            maker_fee=self.expected_partial_fill_fee,
            taker_fee=self.expected_partial_fill_fee,
            exchange_order_id=self.expected_exchange_order_id,
            taker_trade_id=self.expected_trade_id,
        )
        self.clob_data_source_mock.configure_order_stream_event_for_in_flight_order(
            timestamp=self.start_timestamp + 2,
            in_flight_order=order,
            filled_size=self.expected_partial_fill_size,
            is_canceled=True,
        )

        self.clob_data_source_mock.run_until_all_items_delivered()

        order_created_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, order_created_event.timestamp)
        self.assertEqual(order.order_type, order_created_event.type)
        self.assertEqual(order.trading_pair, order_created_event.trading_pair)
        self.assertEqual(order.amount, order_created_event.amount)
        self.assertEqual(order.price, order_created_event.price)
        self.assertEqual(order.client_order_id, order_created_event.order_id)
        self.assertEqual(order.exchange_order_id, order_created_event.exchange_order_id)

        self.assertTrue(self.is_logged("INFO", order.build_order_created_message()))

        order_partially_filled_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(order.order_type, order_partially_filled_event.order_type)
        self.assertEqual(order.trading_pair, order_partially_filled_event.trading_pair)
        self.assertEqual(self.expected_trade_id, order_partially_filled_event.exchange_trade_id)
        self.assertEqual(self.expected_order_price, order_partially_filled_event.price)
        self.assertEqual(self.expected_partial_fill_size, order_partially_filled_event.amount)
        self.assertEqual(order.client_order_id, order_partially_filled_event.order_id)

        self.assertTrue(
            self.is_logged_that_starts_with(
                log_level="INFO",
                message_starts_with=f"The {order.trade_type.name.upper()} order {order.client_order_id} amounting to ",
            )
        )

        order_partially_cancelled_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(order.client_order_id, order_partially_cancelled_event.order_id)
        self.assertEqual(order.exchange_order_id, order_partially_cancelled_event.exchange_order_id)
        self.assertEqual(self.exchange.current_timestamp, order_partially_cancelled_event.timestamp)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Successfully canceled order {order.client_order_id}."
            )
        )

        self.assertTrue(order.is_cancelled)

    def test_user_stream_balance_update(self):
        if self.exchange.real_time_balance_update:
            target_total_balance = Decimal("15")
            target_available_balance = Decimal("10")
            self.clob_data_source_mock.configure_account_quote_balance_stream_event(
                timestamp=self.start_timestamp,
                total_balance=target_total_balance,
                available_balance=target_available_balance,
            )

            self.clob_data_source_mock.run_until_all_items_delivered()

            self.assertEqual(target_total_balance, self.exchange.get_balance(self.quote_asset))
            self.assertEqual(target_available_balance, self.exchange.available_balances[self.quote_asset])

    def test_user_stream_logs_errors(self):
        self.clob_data_source_mock.configure_faulty_base_balance_stream_event(timestamp=self.start_timestamp)
        self.clob_data_source_mock.run_until_all_items_delivered()

        self.assertTrue(self.is_logged("INFO", "Restarting account balances stream."))

    def test_lost_order_included_in_order_fills_update_and_not_in_order_status_update(self):
        self.exchange._set_current_timestamp(self.start_timestamp)

        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=self.expected_order_price,
            amount=self.expected_order_size,
        )
        order: InFlightOrder = self.exchange.in_flight_orders["11"]

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id)
            )

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        self.clob_data_source_mock.configure_order_status_update_response(
            timestamp=self.start_timestamp,
            order=order,
            creation_transaction_hash=self.expected_transaction_hash,
        )
        self.clob_data_source_mock.configure_trades_response_with_exchange_order_id(
            timestamp=self.start_timestamp,
            exchange_order_id=self.expected_exchange_order_id,
            price=self.expected_order_price,
            size=self.expected_order_size,
            fee=self.expected_full_fill_fee,
            trade_id=self.expected_trade_id,
        )

        self.clock.backtest_til(self.start_timestamp + self.exchange.SHORT_POLL_INTERVAL)
        self.async_run_with_timeout(order.wait_until_completely_filled())

        self.assertTrue(order.is_done)
        self.assertTrue(order.is_failure)

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[-1]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(order.price, fill_event.price)
        self.assertEqual(order.amount, fill_event.amount)
        self.assertEqual(self.expected_full_fill_fee, fill_event.trade_fee)

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
        self.assertIn(order.client_order_id, self.exchange._order_tracker.all_fillable_orders)
        self.assertFalse(
            self.is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

        # Configure again the response to the order fills request since it is required by lost orders update logic
        self.clob_data_source_mock.configure_get_historical_spot_orders_response_for_in_flight_order(
            timestamp=self.start_timestamp,
            in_flight_order=order,
            filled_size=self.expected_order_size,
        )
        self.clob_data_source_mock.configure_trades_response_with_exchange_order_id(
            timestamp=self.start_timestamp,
            exchange_order_id=self.expected_exchange_order_id,
            price=self.expected_order_price,
            size=self.expected_order_size,
            fee=self.expected_full_fill_fee,
            trade_id=self.expected_trade_id,
        )

        self.async_run_with_timeout(self.exchange._update_lost_orders_status())

        self.assertTrue(order.is_done)
        self.assertTrue(order.is_failure)

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.all_fillable_orders)
        self.assertFalse(
            self.is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

    def test_cancel_lost_order_successfully(self):
        self.exchange._set_current_timestamp(self.start_timestamp)

        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=self.expected_exchange_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=self.expected_order_price,
            amount=self.expected_order_size,
            order_type=OrderType.LIMIT,
        )

        self.assertIn("11", self.exchange.in_flight_orders)
        order: InFlightOrder = self.exchange.in_flight_orders["11"]

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id))

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        self.clob_data_source_mock.configure_cancel_order_response(
            timestamp=self.start_timestamp, transaction_hash=self.expected_transaction_hash
        )

        self.async_run_with_timeout(self.exchange._cancel_lost_orders())

        if self.exchange.is_cancel_request_in_exchange_synchronous:
            self.assertNotIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
            self.assertFalse(order.is_cancelled)
            self.assertTrue(order.is_failure)
            self.assertEqual(0, len(self.order_cancelled_logger.event_log))
        else:
            self.assertIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
            self.assertTrue(order.is_failure)

        self.assertFalse(
            self.is_logged_that_starts_with(log_level="WARNING", message_starts_with="Failed to cancel the order ")
        )
        self.assertFalse(
            self.is_logged_that_starts_with(log_level="ERROR", message_starts_with="Failed to cancel order ")
        )

    def test_cancel_lost_order_raises_failure_event_when_request_fails(self):
        self.exchange._set_current_timestamp(self.start_timestamp)

        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=self.expected_exchange_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=self.expected_order_price,
            amount=self.expected_order_size,
            order_type=OrderType.LIMIT,
        )

        self.assertIn("11", self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders["11"]

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id))

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        self.clob_data_source_mock.configure_cancel_order_fails_response(exception=RuntimeError("some error"))

        self.async_run_with_timeout(self.exchange._cancel_lost_orders())

        self.assertIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertEquals(0, len(self.order_cancelled_logger.event_log))
        self.assertTrue(any(log.msg.startswith(f"Failed to cancel order {order.client_order_id}")
                            for log in self.log_records))

    def test_lost_order_removed_after_cancel_status_user_event_received(self):
        self.exchange._set_current_timestamp(self.start_timestamp)
        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=self.expected_order_price,
            amount=self.expected_order_size,
        )
        order = self.exchange.in_flight_orders["11"]

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id))

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        self.clob_data_source_mock.configure_order_stream_event_for_in_flight_order(
            timestamp=self.start_timestamp,
            in_flight_order=order,
            is_canceled=True,
        )

        self.clob_data_source_mock.run_until_all_items_delivered()

        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertEqual(0, len(self.order_cancelled_logger.event_log))
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertFalse(order.is_cancelled)
        self.assertTrue(order.is_failure)

    def test_lost_order_user_stream_full_fill_events_are_processed(self):
        self.exchange._set_current_timestamp(self.start_timestamp)
        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=self.expected_order_price,
            amount=self.expected_order_size,
        )
        order = self.exchange.in_flight_orders["11"]

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id))

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        self.clob_data_source_mock.configure_order_stream_event_for_in_flight_order(
            timestamp=self.start_timestamp,
            in_flight_order=order,
            filled_size=self.expected_order_size,
        )
        self.clob_data_source_mock.configure_trade_stream_event(
            timestamp=self.start_timestamp,
            price=self.expected_order_price,
            size=self.expected_order_size,
            maker_fee=self.expected_full_fill_fee,
            taker_fee=self.expected_full_fill_fee,
            exchange_order_id=self.expected_exchange_order_id,
            taker_trade_id=self.expected_trade_id,
        )
        self.clob_data_source_mock.configure_order_status_update_response(
            timestamp=self.start_timestamp,
            order=order,
            filled_size=self.expected_order_size,
        )

        self.clob_data_source_mock.run_until_all_items_delivered()
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(order.wait_until_completely_filled())

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(order.price, fill_event.price)
        self.assertEqual(order.amount, fill_event.amount)
        expected_fee = self.expected_full_fill_fee
        self.assertEqual(expected_fee, fill_event.trade_fee)

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_failure)

    @patch("hummingbot.client.settings.GatewayConnectionSetting.load")
    def test_estimated_fee_calculation(self, gateway_settings_load_mock: MagicMock):
        AllConnectorSettings.all_connector_settings = {}
        gateway_settings_load_mock.return_value = [
            {
                "connector": "injective",
                "chain": "injective",
                "network": "mainnet",
                "trading_type": "CLOB_SPOT",
                "wallet_address": "0xc7287236f64484b476cfbec0fd21bc49d85f8850c8885665003928a122041e18",  # noqa: mock
                "additional_spenders": [],
            },
        ]
        init_fee_overrides_config()
        fee_schema = TradeFeeSchemaLoader.configured_schema_for_exchange(exchange_name=self.exchange.name)

        self.assertFalse(fee_schema.buy_percent_fee_deducted_from_returns)
        self.assertEqual(0, len(fee_schema.maker_fixed_fees))
        self.assertEqual(0, fee_schema.maker_percent_fee_decimal)
        self.assertIsNone(fee_schema.percent_fee_token)
        self.assertEqual(0, len(fee_schema.taker_fixed_fees))
        self.assertEqual(0, fee_schema.taker_percent_fee_decimal)

        fee = self.exchange.get_fee(
            base_currency=self.base_asset,
            quote_currency=self.quote_asset,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal(100),
            price=Decimal(1000),
            is_maker=True
        )

        self.assertEqual(self.quote_asset, fee.percent_token)
        self.assertEqual(Decimal("-0.00006"), fee.percent)  # factoring in Injective service-provider rebate

        fee = self.exchange.get_fee(
            base_currency=self.base_asset,
            quote_currency=self.quote_asset,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal(100),
            price=Decimal(1000),
            is_maker=False
        )

        self.assertEqual(self.quote_asset, fee.percent_token)
        self.assertEqual(Decimal("0.0006"), fee.percent)
