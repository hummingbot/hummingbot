import asyncio
import unittest
from contextlib import ExitStack
from decimal import Decimal
from pathlib import Path
from test.hummingbot.connector.gateway.clob_spot.data_sources.injective.injective_mock_utils import InjectiveClientMock
from test.mock.http_recorder import HttpPlayer
from typing import Awaitable, List
from unittest.mock import AsyncMock, patch

from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.gateway.clob_spot.data_sources.injective.injective_api_data_source import (
    InjectiveAPIDataSource,
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
    DeductedFromReturnsTradeFee,
    MakerTakerExchangeFeeRates,
    TokenAmount,
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import AccountEvent, BalanceUpdateEvent, MarketEvent, OrderBookDataSourceEvent
from hummingbot.core.network_iterator import NetworkStatus


class MockExchange(ExchangeBase):
    pass


class InjectiveAPIDataSourceTest(unittest.TestCase):
    base: str
    quote: str
    trading_pair: str
    sub_account_id: str
    db_path: Path
    http_player: HttpPlayer
    patch_stack: ExitStack

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base = "COIN"
        cls.quote = "ALPHA"
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.base, quote=cls.quote)
        cls.inj_trading_pair = combine_to_hb_trading_pair(base="INJ", quote=cls.quote)
        cls.sub_account_id = "0xc7287236f64484b476cfbec0fd21bc49d85f8850c8885665003928a122041e18"  # noqa: mock

    def setUp(self) -> None:
        super().setUp()
        self.initial_timestamp = 1669100347689
        self.injective_async_client_mock = InjectiveClientMock(
            initial_timestamp=self.initial_timestamp,
            sub_account_id=self.sub_account_id,
            base=self.base,
            quote=self.quote,
        )
        self.injective_async_client_mock.start()

        client_config_map = ClientConfigAdapter(hb_config=ClientConfigMap())

        self.connector = MockExchange(client_config_map=ClientConfigAdapter(ClientConfigMap()))
        self.tracker = GatewayOrderTracker(connector=self.connector)
        connector_spec = {
            "chain": "injective",
            "network": "mainnet",
            "wallet_address": self.sub_account_id
        }
        self.data_source = InjectiveAPIDataSource(
            trading_pairs=[self.trading_pair],
            connector_spec=connector_spec,
            client_config_map=client_config_map,
        )
        self.data_source.gateway_order_tracker = self.tracker

        self.trades_logger = EventLogger()
        self.order_updates_logger = EventLogger()
        self.trade_updates_logger = EventLogger()
        self.snapshots_logger = EventLogger()
        self.balance_logger = EventLogger()

        self.data_source.add_listener(event_tag=OrderBookDataSourceEvent.TRADE_EVENT, listener=self.trades_logger)
        self.data_source.add_listener(event_tag=MarketEvent.OrderUpdate, listener=self.order_updates_logger)
        self.data_source.add_listener(event_tag=MarketEvent.TradeUpdate, listener=self.trade_updates_logger)
        self.data_source.add_listener(event_tag=OrderBookDataSourceEvent.SNAPSHOT_EVENT, listener=self.snapshots_logger)
        self.data_source.add_listener(event_tag=AccountEvent.BalanceEvent, listener=self.balance_logger)

        self.async_run_with_timeout(coro=self.data_source.start())

    @staticmethod
    def async_run_with_timeout(coro: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coro, timeout))
        return ret

    def tearDown(self) -> None:
        self.injective_async_client_mock.stop()
        self.async_run_with_timeout(coro=self.data_source.stop())
        super().tearDown()

    def test_place_order(self):
        expected_exchange_order_id = "someEOID"
        expected_transaction_hash = "0x7e5f4552091a69125d5dfcb7b8c2659029395bdf"  # noqa: mock
        self.injective_async_client_mock.configure_place_order_response(
            timestamp=self.initial_timestamp,
            transaction_hash=expected_transaction_hash,
            exchange_order_id=expected_exchange_order_id,
            trade_type=TradeType.BUY,
            price=Decimal("10"),
            size=Decimal("2"),
        )
        order = GatewayInFlightOrder(
            client_order_id="someClientOrderID",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            creation_timestamp=self.initial_timestamp,
            price=Decimal("10"),
            amount=Decimal("2"),
        )
        exchange_order_id, misc_updates = self.async_run_with_timeout(coro=self.data_source.place_order(order=order))

        self.assertEqual(expected_exchange_order_id, exchange_order_id)
        self.assertEqual({"creation_transaction_hash": expected_transaction_hash}, misc_updates)

    def test_batch_order_create(self):
        expected_transaction_hash = "0x7e5f4552091a69125d5dfcb7b8c2659029395bdf"  # noqa: mock
        buy_expected_exchange_order_id = (
            "0x7df823e0adc0d4811e8d25d7380c1b45e43b16b0eea6f109cc1fb31d31aeddc8"  # noqa: mock
        )
        sell_expected_exchange_order_id = (
            "0x8df823e0adc0d4811e8d25d7380c1b45e43b16b0eea6f109cc1fb31d31aeddc9"  # noqa: mock
        )
        buy_order_to_create = GatewayInFlightOrder(
            client_order_id="someCOIDCancelCreate",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            creation_timestamp=self.initial_timestamp,
            price=Decimal("10"),
            amount=Decimal("2"),
            exchange_order_id=buy_expected_exchange_order_id,
        )
        sell_order_to_create = GatewayInFlightOrder(
            client_order_id="someCOIDCancelCreate",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            creation_timestamp=self.initial_timestamp,
            price=Decimal("11"),
            amount=Decimal("3"),
            exchange_order_id=sell_expected_exchange_order_id,
        )
        orders_to_create = [buy_order_to_create, sell_order_to_create]
        self.injective_async_client_mock.configure_batch_order_create_response(
            timestamp=self.initial_timestamp,
            transaction_hash=expected_transaction_hash,
            created_orders=orders_to_create,
        )

        result: List[PlaceOrderResult] = self.async_run_with_timeout(
            coro=self.data_source.batch_order_create(orders_to_create=orders_to_create)
        )

        self.assertEqual(2, len(result))
        self.assertEqual(buy_expected_exchange_order_id, result[0].exchange_order_id)
        self.assertEqual({"creation_transaction_hash": expected_transaction_hash}, result[0].misc_updates)
        self.assertEqual(sell_expected_exchange_order_id, result[1].exchange_order_id)
        self.assertEqual({"creation_transaction_hash": expected_transaction_hash}, result[1].misc_updates)

    def test_cancel_order(self):
        creation_transaction_hash = "0x8f6g4552091a69125d5dfcb7b8c2659029395ceg"  # noqa: mock
        expected_client_order_id = "someCOID"
        expected_transaction_hash = "0x7e5f4552091a69125d5dfcb7b8c2659029395bdf"  # noqa: mock
        expected_exchange_order_id = "0x6df823e0adc0d4811e8d25d7380c1b45e43b16b0eea6f109cc1fb31d31aeddc7"  # noqa: mock
        order = GatewayInFlightOrder(
            client_order_id=expected_client_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10"),
            amount=Decimal("1"),
            creation_timestamp=self.initial_timestamp,
            exchange_order_id=expected_exchange_order_id,
            creation_transaction_hash=creation_transaction_hash,
        )
        order.order_fills[creation_transaction_hash] = None  # to prevent requesting creation transaction
        self.injective_async_client_mock.configure_cancel_order_response(
            timestamp=self.initial_timestamp, transaction_hash=expected_transaction_hash
        )
        self.injective_async_client_mock.configure_get_historical_spot_orders_response_for_in_flight_order(
            timestamp=self.initial_timestamp,
            in_flight_order=order,
            order_hash=expected_exchange_order_id,
            is_canceled=True,
        )
        cancelation_success, misc_updates = self.async_run_with_timeout(coro=self.data_source.cancel_order(order=order))

        self.assertTrue(cancelation_success)
        self.assertEqual({"cancelation_transaction_hash": expected_transaction_hash}, misc_updates)

        self.injective_async_client_mock.run_until_all_items_delivered()

    def test_batch_order_cancel(self):
        expected_transaction_hash = "0x7e5f4552091a69125d5dfcb7b8c2659029395bdf"  # noqa: mock
        buy_expected_exchange_order_id = (
            "0x6df823e0adc0d4811e8d25d7380c1b45e43b16b0eea6f109cc1fb31d31aeddc7"  # noqa: mock
        )
        sell_expected_exchange_order_id = (
            "0x7df823e0adc0d4811e8d25d7380c1b45e43b16b0eea6f109cc1fb31d31aeddc8"  # noqa: mock
        )
        creation_transaction_hash_for_cancel = "0x8f6g4552091a69125d5dfcb7b8c2659029395ceg"  # noqa: mock
        buy_order_to_cancel = GatewayInFlightOrder(
            client_order_id="someCOIDCancel",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10"),
            amount=Decimal("1"),
            creation_timestamp=self.initial_timestamp,
            exchange_order_id=buy_expected_exchange_order_id,
            creation_transaction_hash=creation_transaction_hash_for_cancel,
        )
        sell_order_to_cancel = GatewayInFlightOrder(
            client_order_id="someCOIDCancel",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            price=Decimal("11"),
            amount=Decimal("2"),
            creation_timestamp=self.initial_timestamp,
            exchange_order_id=sell_expected_exchange_order_id,
            creation_transaction_hash=creation_transaction_hash_for_cancel,
        )
        self.data_source.gateway_order_tracker.start_tracking_order(order=buy_order_to_cancel)
        self.data_source.gateway_order_tracker.start_tracking_order(order=sell_order_to_cancel)
        orders_to_cancel = [buy_order_to_cancel, sell_order_to_cancel]
        self.injective_async_client_mock.configure_batch_order_cancel_response(
            timestamp=self.initial_timestamp,
            transaction_hash=expected_transaction_hash,
            canceled_orders=orders_to_cancel,
        )

        result: List[CancelOrderResult] = self.async_run_with_timeout(
            coro=self.data_source.batch_order_cancel(orders_to_cancel=orders_to_cancel)
        )

        self.assertEqual(2, len(result))
        self.assertEqual(buy_order_to_cancel.client_order_id, result[0].client_order_id)
        self.assertIsNone(result[0].exception)  # i.e. success
        self.assertEqual({"cancelation_transaction_hash": expected_transaction_hash}, result[0].misc_updates)
        self.assertEqual(sell_order_to_cancel.client_order_id, result[1].client_order_id)
        self.assertIsNone(result[1].exception)  # i.e. success
        self.assertEqual({"cancelation_transaction_hash": expected_transaction_hash}, result[1].misc_updates)

    def test_get_trading_rules(self):
        trading_rules = self.async_run_with_timeout(coro=self.data_source.get_trading_rules())

        self.assertEqual(2, len(trading_rules))
        self.assertIn(self.trading_pair, trading_rules)
        self.assertIn(self.inj_trading_pair, trading_rules)

        trading_rule: TradingRule = trading_rules[self.trading_pair]

        self.assertEqual(self.trading_pair, trading_rule.trading_pair)
        self.assertEqual(Decimal("0.00001"), trading_rule.min_price_increment)
        self.assertEqual(Decimal("0.00001"), trading_rule.min_quote_amount_increment)
        self.assertEqual(Decimal("0.001"), trading_rule.min_base_amount_increment)

    def test_get_symbol_map(self):
        symbol_map = self.async_run_with_timeout(coro=self.data_source.get_symbol_map())

        self.assertIsInstance(symbol_map, bidict)
        self.assertEqual(2, len(symbol_map))
        self.assertIn(self.injective_async_client_mock.market_id, symbol_map)
        self.assertIn(self.trading_pair, symbol_map.inverse)
        self.assertIn(self.inj_trading_pair, symbol_map.inverse)

    def test_get_last_traded_price(self):
        target_price = Decimal("1.157")
        target_maker_fee = AddedToCostTradeFee(flat_fees=[TokenAmount(token=self.quote, amount=Decimal("0.0001157"))])
        target_taker_fee = AddedToCostTradeFee(flat_fees=[TokenAmount(token=self.quote, amount=Decimal("0.00024"))])
        self.injective_async_client_mock.configure_spot_trades_response_to_request_without_exchange_order_id(
            timestamp=self.initial_timestamp,
            price=target_price,
            size=Decimal("0.001"),
            maker_fee=target_maker_fee,
            taker_fee=target_taker_fee,
        )
        price = self.async_run_with_timeout(coro=self.data_source.get_last_traded_price(trading_pair=self.trading_pair))

        self.assertEqual(target_price, price)

    def test_get_order_book_snapshot(self):
        self.injective_async_client_mock.configure_orderbook_snapshot(
            timestamp=self.initial_timestamp, bids=[(9, 1), (8, 2)], asks=[(11, 3)]
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

    def test_delivers_trade_events(self):
        target_price = Decimal("1.157")
        target_size = Decimal("0.001")
        target_maker_fee = DeductedFromReturnsTradeFee(flat_fees=[TokenAmount(token=self.quote, amount=Decimal("0.0001157"))])
        target_taker_fee = AddedToCostTradeFee(flat_fees=[TokenAmount(token=self.quote, amount=Decimal("0.00024"))])
        target_exchange_order_id = "0x6df823e0adc0d4811e8d25d7380c1b45e43b16b0eea6f109cc1fb31d31aeddc7"  # noqa: mock
        target_trade_id = "19889401_someTradeId"
        self.injective_async_client_mock.configure_trade_stream_event(
            timestamp=self.initial_timestamp,
            price=target_price,
            size=target_size,
            maker_fee=target_maker_fee,
            taker_fee=target_taker_fee,
            exchange_order_id=target_exchange_order_id,
            taker_trade_id=target_trade_id,
        )

        self.injective_async_client_mock.run_until_all_items_delivered()

        self.assertEqual(2, len(self.trades_logger.event_log))
        self.assertEqual(2, len(self.trade_updates_logger.event_log))

        first_trade_event: OrderBookMessage = self.trades_logger.event_log[0]

        self.assertEqual(self.initial_timestamp, first_trade_event.timestamp)
        self.assertEqual(self.trading_pair, first_trade_event.content["trading_pair"])
        self.assertEqual(TradeType.SELL, first_trade_event.content["trade_type"])
        self.assertEqual(target_price, first_trade_event.content["price"])
        self.assertEqual(target_size, first_trade_event.content["amount"])
        self.assertFalse(first_trade_event.content["is_taker"])

        second_trade_event: OrderBookMessage = self.trades_logger.event_log[1]

        self.assertEqual(self.initial_timestamp, second_trade_event.timestamp)
        self.assertEqual(self.trading_pair, second_trade_event.content["trading_pair"])
        self.assertEqual(TradeType.BUY, second_trade_event.content["trade_type"])
        self.assertEqual(target_price, second_trade_event.content["price"])
        self.assertEqual(target_size, second_trade_event.content["amount"])
        self.assertTrue(second_trade_event.content["is_taker"])

        first_trade_update: TradeUpdate = self.trade_updates_logger.event_log[0]

        self.assertEqual(self.trading_pair, first_trade_update.trading_pair)
        self.assertEqual(self.initial_timestamp, first_trade_update.fill_timestamp)
        self.assertEqual(target_price, first_trade_update.fill_price)
        self.assertEqual(target_size, first_trade_update.fill_base_amount)
        self.assertEqual(target_price * target_size, first_trade_update.fill_quote_amount)
        self.assertEqual(target_maker_fee, first_trade_update.fee)

        second_order_event: TradeUpdate = self.trade_updates_logger.event_log[1]

        self.assertEqual(target_trade_id, second_order_event.trade_id)
        self.assertEqual(target_exchange_order_id, second_order_event.exchange_order_id)
        self.assertEqual(self.trading_pair, second_order_event.trading_pair)
        self.assertEqual(self.initial_timestamp, second_order_event.fill_timestamp)
        self.assertEqual(target_price, second_order_event.fill_price)
        self.assertEqual(target_size, second_order_event.fill_base_amount)
        self.assertEqual(target_price * target_size, second_order_event.fill_quote_amount)
        self.assertEqual(target_taker_fee, second_order_event.fee)

    def test_delivers_order_created_events(self):
        target_order_id = "someOrderHash"
        target_price = Decimal("100")
        target_size = Decimal("2")
        order = GatewayInFlightOrder(
            client_order_id="someOrderCID",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            creation_timestamp=self.initial_timestamp,
            exchange_order_id=target_order_id,
        )
        self.tracker.start_tracking_order(order=order)
        self.injective_async_client_mock.configure_order_stream_event(
            timestamp=self.initial_timestamp,
            order_hash=target_order_id,
            state="booked",
            execution_type="limit",
            order_type="buy_po",
            price=target_price,
            size=target_size,
            filled_size=Decimal("0"),
            direction="buy",
        )

        self.injective_async_client_mock.run_until_all_items_delivered()

        self.assertEqual(1, len(self.order_updates_logger.event_log))

        order_event: OrderUpdate = self.order_updates_logger.event_log[0]

        self.assertIsInstance(order_event, OrderUpdate)
        self.assertEqual(self.initial_timestamp, order_event.update_timestamp)
        self.assertEqual(target_order_id, order_event.exchange_order_id)
        self.assertEqual(OrderState.OPEN, order_event.new_state)

        target_order_id = "anotherOrderHash"
        target_price = Decimal("50")
        target_size = Decimal("1")
        order = GatewayInFlightOrder(
            client_order_id="someOtherOrderCID",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            creation_timestamp=self.initial_timestamp,
            exchange_order_id=target_order_id,
        )
        self.tracker.start_tracking_order(order=order)
        self.injective_async_client_mock.configure_order_stream_event(
            timestamp=self.initial_timestamp,
            order_hash=target_order_id,
            state="booked",
            execution_type="limit",
            order_type="sell",
            price=target_price,
            size=target_size,
            filled_size=Decimal("0"),
            direction="sell",
        )

        self.injective_async_client_mock.run_until_all_items_delivered()

        self.assertEqual(2, len(self.order_updates_logger.event_log))

        order_event: OrderUpdate = self.order_updates_logger.event_log[1]

        self.assertIsInstance(order_event, OrderUpdate)
        self.assertEqual(self.initial_timestamp, order_event.update_timestamp)
        self.assertEqual(target_order_id, order_event.exchange_order_id)
        self.assertEqual(OrderState.OPEN, order_event.new_state)

    def test_delivers_order_fully_filled_events(self):
        target_order_id = "someOrderHash"
        target_price = Decimal("100")
        target_size = Decimal("2")
        order = GatewayInFlightOrder(
            client_order_id="someOrderCID",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            creation_timestamp=self.initial_timestamp,
            exchange_order_id=target_order_id,
        )
        self.tracker.start_tracking_order(order=order)
        self.injective_async_client_mock.configure_order_stream_event(
            timestamp=self.initial_timestamp,
            order_hash=target_order_id,
            state="filled",
            execution_type="limit",
            order_type="buy",
            price=target_price,
            size=target_size,
            filled_size=target_size,
            direction="buy",
        )

        self.injective_async_client_mock.run_until_all_items_delivered()

        self.assertEqual(2, len(self.order_updates_logger.event_log))

        order_event: OrderUpdate = self.order_updates_logger.event_log[1]

        self.assertIsInstance(order_event, OrderUpdate)
        self.assertEqual(self.initial_timestamp, order_event.update_timestamp)
        self.assertEqual(target_order_id, order_event.exchange_order_id)
        self.assertEqual(OrderState.FILLED, order_event.new_state)

        self.injective_async_client_mock.configure_order_stream_event(
            timestamp=self.initial_timestamp,
            order_hash=target_order_id,
            state="filled",
            execution_type="limit",
            order_type="sell_po",
            price=target_price,
            size=target_size,
            filled_size=target_size,
            direction="sell",
        )

        self.injective_async_client_mock.run_until_all_items_delivered()

        self.assertEqual(4, len(self.order_updates_logger.event_log))

        order_event: OrderUpdate = self.order_updates_logger.event_log[3]

        self.assertIsInstance(order_event, OrderUpdate)
        self.assertEqual(self.initial_timestamp, order_event.update_timestamp)
        self.assertEqual(target_order_id, order_event.exchange_order_id)
        self.assertEqual(OrderState.FILLED, order_event.new_state)

    def test_delivers_order_canceled_events(self):
        target_order_id = "0x6df823e0adc0d4811e8d25d7380c1b45e43b16b0eea6f109cc1fb31d31aeddc7"  # noqa: mock
        target_price = Decimal("100")
        target_size = Decimal("2")
        order = GatewayInFlightOrder(
            client_order_id="someOrderCID",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            creation_timestamp=self.initial_timestamp,
            exchange_order_id=target_order_id,
        )
        self.tracker.start_tracking_order(order=order)
        self.injective_async_client_mock.configure_order_stream_event(
            timestamp=self.initial_timestamp,
            order_hash=target_order_id,
            state="canceled",
            execution_type="limit",
            order_type="buy",
            price=target_price,
            size=target_size,
            filled_size=Decimal("0"),
            direction="buy",
        )

        self.injective_async_client_mock.run_until_all_items_delivered()

        self.assertEqual(2, len(self.order_updates_logger.event_log))

        order_event: OrderUpdate = self.order_updates_logger.event_log[1]

        self.assertIsInstance(order_event, OrderUpdate)
        self.assertEqual(self.initial_timestamp, order_event.update_timestamp)
        self.assertEqual(target_order_id, order_event.exchange_order_id)
        self.assertEqual(OrderState.CANCELED, order_event.new_state)

    def test_delivers_order_book_snapshots(self):
        self.injective_async_client_mock.configure_orderbook_snapshot_stream_event(
            timestamp=self.initial_timestamp, bids=[(9, 1), (8, 2)], asks=[(11, 3)]
        )

        self.injective_async_client_mock.run_until_all_items_delivered()

        self.assertEqual(1, len(self.snapshots_logger.event_log))

        snapshot_event: OrderBookMessage = self.snapshots_logger.event_log[0]

        self.assertEqual(self.initial_timestamp, snapshot_event.timestamp)
        self.assertEqual(2, len(snapshot_event.bids))
        self.assertEqual(9, snapshot_event.bids[0].price)
        self.assertEqual(1, snapshot_event.bids[0].amount)
        self.assertEqual(1, len(snapshot_event.asks))
        self.assertEqual(11, snapshot_event.asks[0].price)
        self.assertEqual(3, snapshot_event.asks[0].amount)

    def test_get_account_balances(self):
        base_bank_balance = Decimal("75")
        base_total_balance = Decimal("10")
        base_available_balance = Decimal("9")
        quote_total_balance = Decimal("200")
        quote_available_balance = Decimal("150")
        self.injective_async_client_mock.configure_get_account_balances_response(
            base_bank_balance=base_bank_balance,
            quote_bank_balance=Decimal("0"),
            base_total_balance=base_total_balance,
            base_available_balance=base_available_balance,
            quote_total_balance=quote_total_balance,
            quote_available_balance=quote_available_balance,
        )

        subaccount_balances = self.async_run_with_timeout(coro=self.data_source.get_account_balances())

        self.assertEqual(base_total_balance, subaccount_balances[self.base]["total_balance"])
        self.assertEqual(base_available_balance, subaccount_balances[self.base]["available_balance"])
        self.assertEqual(quote_total_balance, subaccount_balances[self.quote]["total_balance"])
        self.assertEqual(quote_available_balance, subaccount_balances[self.quote]["available_balance"])

    def test_get_order_status_update_success(self):
        creation_transaction_hash = "0x7cb2eafc389349f86da901cdcbfd9119425a2ea84d61c17b6ded778b6fd2g81d"  # noqa: mock
        target_order_hash = "0x6ba1eafc389349f86da901cdcbfd9119425a2ea84d61c17b6ded778b6fd2f70c"  # noqa: mock
        in_flight_order = GatewayInFlightOrder(
            client_order_id="someClientOrderID",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            creation_timestamp=self.initial_timestamp,
            price=Decimal("10"),
            amount=Decimal("1"),
            creation_transaction_hash=creation_transaction_hash,
            exchange_order_id=target_order_hash,
        )
        self.injective_async_client_mock.configure_get_historical_spot_orders_response(
            timestamp=self.initial_timestamp + 1,
            order_hash=target_order_hash,
            state="booked",
            execution_type="market" if in_flight_order.order_type == OrderType.MARKET else "limit",
            order_type=(
                in_flight_order.trade_type.name.lower()
                + ("_po" if in_flight_order.order_type == OrderType.LIMIT_MAKER else "")
            ),
            price=in_flight_order.price,
            size=in_flight_order.amount,
            filled_size=Decimal("0"),
            direction=in_flight_order.trade_type.name.lower(),
        )

        status_update: OrderUpdate = self.async_run_with_timeout(
            coro=self.data_source.get_order_status_update(in_flight_order=in_flight_order)
        )

        self.assertEqual(self.trading_pair, status_update.trading_pair)
        self.assertEqual(self.initial_timestamp + 1, status_update.update_timestamp)
        self.assertEqual(OrderState.OPEN, status_update.new_state)
        self.assertEqual(in_flight_order.client_order_id, status_update.client_order_id)
        self.assertEqual(target_order_hash, status_update.exchange_order_id)
        self.assertIn("creation_transaction_hash", status_update.misc_updates)
        self.assertEqual(creation_transaction_hash, status_update.misc_updates["creation_transaction_hash"])

    def test_get_all_order_fills_no_fills(self):
        target_order_id = "0x6ba1eafc389349f86da901cdcbfd9119425a2ea84d61c17b6ded778b6fd2f70c"  # noqa: mock
        creation_transaction_hash = "0x7cb2eafc389349f86da901cdcbfd9119425a2ea84d61c17b6ded778b6fd2g81d"  # noqa: mock
        self.injective_async_client_mock.configure_get_historical_spot_orders_response(
            timestamp=self.initial_timestamp,
            order_hash=target_order_id,
            state="booked",
            execution_type="limit",
            order_type="sell",
            price=Decimal("10"),
            size=Decimal("2"),
            filled_size=Decimal("0"),
            direction="sell",
        )
        in_flight_order = GatewayInFlightOrder(
            client_order_id="someOrderId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            creation_timestamp=self.initial_timestamp - 10,
            price=Decimal("10"),
            amount=Decimal("2"),
            exchange_order_id=target_order_id,
        )

        trade_updates = self.async_run_with_timeout(
            coro=self.data_source.get_all_order_fills(in_flight_order=in_flight_order)
        )

        self.assertEqual(0, len(trade_updates))

    def test_get_all_order_fills(self):
        target_client_order_id = "someOrderId"
        target_exchange_order_id = "0x6ba1eafc389349f86da901cdcbfd9119425a2ea84d61c17b6ded778b6fd2f70c"  # noqa: mock
        target_trade_id = "someTradeHash"
        target_price = Decimal("10")
        target_size = Decimal("2")
        target_trade_fee = AddedToCostTradeFee(flat_fees=[TokenAmount(token=self.quote, amount=Decimal("0.01"))])
        target_partial_fill_size = target_size / 2
        target_fill_ts = self.initial_timestamp + 10
        self.injective_async_client_mock.configure_get_historical_spot_orders_response(
            timestamp=self.initial_timestamp,
            order_hash=target_exchange_order_id,
            state="partial_filled",
            execution_type="limit",
            order_type="sell",
            price=target_price,
            size=target_size,
            filled_size=target_partial_fill_size,
            direction="sell",
        )
        self.injective_async_client_mock.configure_trades_response_with_exchange_order_id(
            timestamp=target_fill_ts,
            exchange_order_id=target_exchange_order_id,
            price=target_price,
            size=target_partial_fill_size,
            fee=target_trade_fee,
            trade_id=target_trade_id,
        )
        in_flight_order = GatewayInFlightOrder(
            client_order_id=target_client_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            creation_timestamp=self.initial_timestamp - 10,
            price=target_price,
            amount=target_size,
            exchange_order_id=target_exchange_order_id,
        )

        trade_updates: List[TradeUpdate] = self.async_run_with_timeout(
            coro=self.data_source.get_all_order_fills(in_flight_order=in_flight_order)
        )

        self.assertEqual(1, len(trade_updates))

        trade_update = trade_updates[0]

        self.assertEqual(target_trade_id, trade_update.trade_id)
        self.assertEqual(target_client_order_id, trade_update.client_order_id)
        self.assertEqual(target_exchange_order_id, trade_update.exchange_order_id)
        self.assertEqual(self.trading_pair, trade_update.trading_pair)
        self.assertEqual(target_fill_ts, trade_update.fill_timestamp)
        self.assertEqual(target_price, trade_update.fill_price)
        self.assertEqual(target_partial_fill_size, trade_update.fill_base_amount)
        self.assertEqual(target_partial_fill_size * target_price, trade_update.fill_quote_amount)
        self.assertEqual(target_trade_fee, trade_update.fee)

    def test_check_network_status(self):
        self.injective_async_client_mock.configure_check_network_failure()

        status = self.async_run_with_timeout(coro=self.data_source.check_network_status())

        self.assertEqual(NetworkStatus.NOT_CONNECTED, status)

        self.injective_async_client_mock.configure_check_network_success()

        status = self.async_run_with_timeout(coro=self.data_source.check_network_status())

        self.assertEqual(NetworkStatus.CONNECTED, status)

    def test_get_trading_fees(self):
        all_trading_fees = self.async_run_with_timeout(coro=self.data_source.get_trading_fees())

        self.assertIn(self.trading_pair, all_trading_fees)

        pair_trading_fees: MakerTakerExchangeFeeRates = all_trading_fees[self.trading_pair]

        service_provider_rebate = Decimal("1") - self.injective_async_client_mock.service_provider_fee
        expected_maker_fee = self.injective_async_client_mock.maker_fee_rate * service_provider_rebate
        expected_taker_fee = self.injective_async_client_mock.taker_fee_rate * service_provider_rebate
        self.assertEqual(expected_maker_fee, pair_trading_fees.maker)
        self.assertEqual(expected_taker_fee, pair_trading_fees.taker)

    def test_delivers_balance_events(self):
        target_total_balance = Decimal("20")
        target_available_balance = Decimal("19")
        self.injective_async_client_mock.configure_account_quote_balance_stream_event(
            timestamp=self.initial_timestamp,
            total_balance=target_total_balance,
            available_balance=target_available_balance,
        )

        self.injective_async_client_mock.run_until_all_items_delivered()

        self.assertEqual(1, len(self.balance_logger.event_log))

        balance_event: BalanceUpdateEvent = self.balance_logger.event_log[0]

        self.assertEqual(self.quote, balance_event.asset_name)
        self.assertEqual(target_total_balance, balance_event.total_balance)
        self.assertEqual(target_available_balance, balance_event.available_balance)

    def test_parses_transaction_event_for_order_creation_success(self):
        creation_transaction_hash = "0x7cb1eafc389349f86da901cdcbfd9119435a2ea84d61c17b6ded778b6fd2f81d"  # noqa: mock
        target_order_hash = "0x6ba1eafc389349f86da901cdcbfd9119425a2ea84d61c17b6ded778b6fd2f70c"  # noqa: mock
        in_flight_order = GatewayInFlightOrder(
            client_order_id="someClientOrderID",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            creation_timestamp=self.initial_timestamp,
            price=Decimal("10"),
            amount=Decimal("1"),
            creation_transaction_hash=creation_transaction_hash,
            exchange_order_id=target_order_hash,
        )
        self.tracker.start_tracking_order(order=in_flight_order)
        self.injective_async_client_mock.configure_creation_transaction_stream_event(
            timestamp=self.initial_timestamp + 1, transaction_hash=creation_transaction_hash
        )
        self.injective_async_client_mock.configure_get_historical_spot_orders_response(
            timestamp=self.initial_timestamp + 1,
            order_hash=target_order_hash,
            state="booked",
            execution_type="market" if in_flight_order.order_type == OrderType.MARKET else "limit",
            order_type=(
                in_flight_order.trade_type.name.lower()
                + ("_po" if in_flight_order.order_type == OrderType.LIMIT_MAKER else "")
            ),
            price=in_flight_order.price,
            size=in_flight_order.amount,
            filled_size=Decimal("0"),
            direction=in_flight_order.trade_type.name.lower(),
        )

        self.injective_async_client_mock.run_until_all_items_delivered()

        status_update = self.order_updates_logger.event_log[0]

        self.assertEqual(self.trading_pair, status_update.trading_pair)
        self.assertEqual(self.initial_timestamp + 1, status_update.update_timestamp)
        self.assertEqual(OrderState.OPEN, status_update.new_state)
        self.assertEqual(in_flight_order.client_order_id, status_update.client_order_id)
        self.assertEqual(target_order_hash, status_update.exchange_order_id)

    @patch(
        "hummingbot.connector.gateway.clob_spot.data_sources.injective.injective_api_data_source"
        ".InjectiveAPIDataSource._update_account_address_and_create_order_hash_manager",
        new_callable=AsyncMock,
    )
    def test_parses_transaction_event_for_order_creation_failure(self, _: AsyncMock):
        creation_transaction_hash = "0x7cb1eafc389349f86da901cdcbfd9119435a2ea84d61c17b6ded778b6fd2f81d"  # noqa: mock
        target_order_hash = "0x6ba1eafc389349f86da901cdcbfd9119425a2ea84d61c17b6ded778b6fd2f70c"  # noqa: mock
        in_flight_order = GatewayInFlightOrder(
            client_order_id="someClientOrderID",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            creation_timestamp=self.initial_timestamp,
            price=Decimal("10"),
            amount=Decimal("1"),
            creation_transaction_hash=creation_transaction_hash,
            exchange_order_id=target_order_hash,
        )
        self.tracker.start_tracking_order(order=in_flight_order)
        self.injective_async_client_mock.configure_order_status_update_response(
            timestamp=self.initial_timestamp,
            order=in_flight_order,
            creation_transaction_hash=creation_transaction_hash,
            is_failed=True,
        )

        self.injective_async_client_mock.run_until_all_items_delivered()

        status_update = self.order_updates_logger.event_log[1]

        self.assertEqual(self.trading_pair, status_update.trading_pair)
        self.assertEqual(self.initial_timestamp, status_update.update_timestamp)
        self.assertEqual(OrderState.FAILED, status_update.new_state)
        self.assertEqual(in_flight_order.client_order_id, status_update.client_order_id)
        self.assertEqual(0, len(self.trade_updates_logger.event_log))

    def test_parses_transaction_event_for_order_cancelation(self):
        cancelation_transaction_hash = "0x7cb1eafc389349f86da901cdcbfd9119435a2ea84d61c17b6ded778b6fd2f81d"  # noqa: mock
        target_order_hash = "0x6ba1eafc389349f86da901cdcbfd9119425a2ea84d61c17b6ded778b6fd2f70c"  # noqa: mock
        in_flight_order = GatewayInFlightOrder(
            client_order_id="someClientOrderID",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            creation_timestamp=self.initial_timestamp,
            price=Decimal("10"),
            amount=Decimal("1"),
            creation_transaction_hash="someHash",
            exchange_order_id=target_order_hash,
        )
        in_flight_order.order_fills["someHash"] = None  # to prevent order creation transaction request
        self.tracker.start_tracking_order(order=in_flight_order)
        in_flight_order.cancel_tx_hash = cancelation_transaction_hash
        self.injective_async_client_mock.configure_cancelation_transaction_stream_event(
            timestamp=self.initial_timestamp + 1,
            transaction_hash=cancelation_transaction_hash,
            order_hash=target_order_hash,
        )
        self.injective_async_client_mock.configure_get_historical_spot_orders_response(
            timestamp=self.initial_timestamp + 1,
            order_hash=target_order_hash,
            state="canceled",
            execution_type="limit",
            order_type=in_flight_order.trade_type.name.lower(),
            price=in_flight_order.price,
            size=in_flight_order.amount,
            filled_size=Decimal("0"),
            direction=in_flight_order.trade_type.name.lower(),
        )

        self.injective_async_client_mock.run_until_all_items_delivered()

        status_update = self.order_updates_logger.event_log[1]

        self.assertEqual(self.trading_pair, status_update.trading_pair)
        self.assertEqual(self.initial_timestamp + 1, status_update.update_timestamp)
        self.assertEqual(OrderState.CANCELED, status_update.new_state)
        self.assertEqual(in_flight_order.client_order_id, status_update.client_order_id)
        self.assertEqual(target_order_hash, status_update.exchange_order_id)
