import asyncio
import unittest
from contextlib import ExitStack
from decimal import Decimal
from pathlib import Path
from test.hummingbot.connector.gateway.clob_spot.data_sources.xrpl.xrpl_mock_utils import XrplClientMock
from test.mock.http_recorder import HttpPlayer
from typing import Awaitable, List

from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.gateway.clob_spot.data_sources.xrpl.xrpl_api_data_source import XrplAPIDataSource
from hummingbot.connector.gateway.common_types import CancelOrderResult, PlaceOrderResult
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.gateway.gateway_order_tracker import GatewayOrderTracker
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import AccountEvent, MarketEvent, OrderBookDataSourceEvent


class MockExchange(ExchangeBase):
    pass


class XrplAPIDataSourceTest(unittest.TestCase):
    base: str
    quote: str
    trading_pair: str
    xrpl_wallet_address: str
    db_path: Path
    http_player: HttpPlayer
    patch_stack: ExitStack

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base = "USD"
        cls.quote = "VND"
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.base, quote=cls.quote)
        cls.xrpl_trading_pair = combine_to_hb_trading_pair(base="XRP", quote=cls.quote)
        cls.xrpl_wallet_address = "r3z4R6KQWfwRf9G15AhUZe2GN67Sj6PYNV"  # noqa: mock

    def setUp(self) -> None:
        super().setUp()
        self.initial_timestamp = 1669100347689
        self.xrpl_async_client_mock = XrplClientMock(
            initial_timestamp=self.initial_timestamp,
            wallet_address=self.xrpl_wallet_address,
            base=self.base,
            quote=self.quote,
        )
        self.xrpl_async_client_mock.start()

        client_config_map = ClientConfigAdapter(hb_config=ClientConfigMap())

        self.connector = MockExchange(client_config_map=ClientConfigAdapter(ClientConfigMap()))
        self.tracker = GatewayOrderTracker(connector=self.connector)
        connector_spec = {
            "chain": "xrpl",
            "network": "testnet",
            "wallet_address": self.xrpl_wallet_address
        }
        self.data_source = XrplAPIDataSource(
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
        self.xrpl_async_client_mock.stop()
        self.async_run_with_timeout(coro=self.data_source.stop())
        super().tearDown()

    def test_place_order(self):
        expected_exchange_order_id = "1234567"
        expected_transaction_hash = "'C026E957AC3BE397B13DBF5021CF33D3EFA53D095AA497568228D5810EF6E5E0'"  # noqa: mock
        self.xrpl_async_client_mock.configure_place_order_response(
            timestamp=self.initial_timestamp,
            transaction_hash=expected_transaction_hash,
            exchange_order_id=expected_exchange_order_id,
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
        self.xrpl_async_client_mock.run_until_place_order_called()
        self.assertEqual(None, exchange_order_id)
        self.assertEqual({"creation_transaction_hash": expected_transaction_hash.lower()}, misc_updates)

        exchange_order_id = self.async_run_with_timeout(
            coro=self.data_source._get_exchange_order_id_from_transaction(in_flight_order=order))
        self.xrpl_async_client_mock.run_until_transaction_status_update_called()
        self.assertEqual(expected_exchange_order_id, exchange_order_id)

    def test_cancel_order(self):
        creation_transaction_hash = "DB6287E5301A494E849B232287F22811EBB50BD629BF76E9E643682DCA5FB1DB"  # noqa: mock
        expected_client_order_id = "someID"
        expected_transaction_hash = "DF01497AB6C0E296D0AD19890A89B6315E814E7EAE43F6F900B3BB2D9BD65AF8"  # noqa: mock
        expected_exchange_order_id = "1234567"  # noqa: mock
        self.xrpl_async_client_mock.configure_cancel_order_response(
            timestamp=self.initial_timestamp,
            transaction_hash=expected_transaction_hash
        )
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

        cancelation_success, misc_updates = self.async_run_with_timeout(coro=self.data_source.cancel_order(order=order))
        self.xrpl_async_client_mock.run_until_cancel_order_called()

        self.assertTrue(cancelation_success)
        self.assertEqual({"cancelation_transaction_hash": expected_transaction_hash.lower()}, misc_updates)

    def test_batch_order_create(self):
        expected_exchange_order_id = "1234567"
        expected_transaction_hash = "'C026E957AC3BE397B13DBF5021CF33D3EFA53D095AA497568228D5810EF6E5E0'"  # noqa: mock
        self.xrpl_async_client_mock.configure_place_order_response(
            timestamp=self.initial_timestamp,
            transaction_hash=expected_transaction_hash,
            exchange_order_id=expected_exchange_order_id,
        )

        buy_order_to_create = GatewayInFlightOrder(
            client_order_id="someCOIDCancelCreate",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            creation_timestamp=self.initial_timestamp,
            price=Decimal("10"),
            amount=Decimal("2"),
            exchange_order_id=expected_exchange_order_id,
        )
        sell_order_to_create = GatewayInFlightOrder(
            client_order_id="someCOIDCancelCreate",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            creation_timestamp=self.initial_timestamp,
            price=Decimal("11"),
            amount=Decimal("3"),
            exchange_order_id=expected_exchange_order_id,
        )
        orders_to_create = [buy_order_to_create, sell_order_to_create]

        result: List[PlaceOrderResult] = self.async_run_with_timeout(
            coro=self.data_source.batch_order_create(orders_to_create=orders_to_create)
        )
        self.xrpl_async_client_mock.run_until_place_order_called()

        exchange_order_id_1 = self.async_run_with_timeout(
            coro=self.data_source._get_exchange_order_id_from_transaction(in_flight_order=buy_order_to_create))
        self.xrpl_async_client_mock.run_until_transaction_status_update_called()

        exchange_order_id_2 = self.async_run_with_timeout(
            coro=self.data_source._get_exchange_order_id_from_transaction(in_flight_order=sell_order_to_create))
        self.xrpl_async_client_mock.run_until_transaction_status_update_called()

        self.assertEqual(2, len(result))
        self.assertEqual(expected_exchange_order_id, exchange_order_id_1)
        self.assertEqual(expected_exchange_order_id, exchange_order_id_2)
        self.assertEqual({"creation_transaction_hash": expected_transaction_hash.lower()}, result[0].misc_updates)
        self.assertEqual({"creation_transaction_hash": expected_transaction_hash.lower()}, result[1].misc_updates)

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
        self.xrpl_async_client_mock.configure_cancel_order_response(
            timestamp=self.initial_timestamp,
            transaction_hash=expected_transaction_hash
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
        self.xrpl_async_client_mock.configure_trading_rules_response(minimum_order_size="0.001",
                                                                     base_transfer_rate="0.1",
                                                                     quote_transfer_rate="0.1")
        trading_rules = self.async_run_with_timeout(coro=self.data_source.get_trading_rules())
        self.xrpl_async_client_mock.run_until_update_market_called()

        self.assertEqual(1, len(trading_rules))
        self.assertIn(self.trading_pair, trading_rules)

        trading_rule: TradingRule = trading_rules[self.trading_pair]

        self.assertEqual(self.trading_pair, trading_rule.trading_pair)
        self.assertEqual(Decimal("1E-8"), trading_rule.min_price_increment)
        self.assertEqual(Decimal("1E-8"), trading_rule.min_quote_amount_increment)
        self.assertEqual(Decimal("1E-15"), trading_rule.min_base_amount_increment)

    def test_get_symbol_map(self):
        self.xrpl_async_client_mock.configure_trading_rules_response(minimum_order_size="0.001",
                                                                     base_transfer_rate="0.1",
                                                                     quote_transfer_rate="0.1")
        symbol_map = self.async_run_with_timeout(coro=self.data_source.get_symbol_map())
        self.xrpl_async_client_mock.run_until_update_market_called()

        self.assertIsInstance(symbol_map, bidict)
        self.assertEqual(1, len(symbol_map))
        self.assertIn(self.trading_pair, symbol_map.inverse)

    def test_get_last_traded_price(self):
        target_price = "3.14"
        self.xrpl_async_client_mock.configure_last_traded_price_response(
            price=target_price, trading_pair=self.trading_pair
        )
        price = self.async_run_with_timeout(coro=self.data_source.get_last_traded_price(trading_pair=self.trading_pair))
        self.xrpl_async_client_mock.run_until_update_ticker_called()

        self.assertEqual(target_price, price)

    def test_get_order_book_snapshot(self):
        self.xrpl_async_client_mock.configure_orderbook_snapshot(
            timestamp=self.initial_timestamp, bids=[(9, 1), (8, 2)], asks=[(11, 3)]
        )
        order_book_snapshot: OrderBookMessage = self.async_run_with_timeout(
            coro=self.data_source.get_order_book_snapshot(trading_pair=self.trading_pair)
        )
        self.xrpl_async_client_mock.run_until_orderbook_snapshot_called()

        self.assertEqual(self.initial_timestamp, order_book_snapshot.timestamp)
        self.assertEqual(2, len(order_book_snapshot.bids))
        self.assertEqual(9, order_book_snapshot.bids[0].price)
        self.assertEqual(1, order_book_snapshot.bids[0].amount)
        self.assertEqual(1, len(order_book_snapshot.asks))
        self.assertEqual(11, order_book_snapshot.asks[0].price)
        self.assertEqual(3, order_book_snapshot.asks[0].amount)

    def test_get_account_balances(self):
        base_total_balance = Decimal("10")
        quote_total_balance = Decimal("200")

        self.xrpl_async_client_mock.configure_trading_rules_response(minimum_order_size="0.001",
                                                                     base_transfer_rate="0.1",
                                                                     quote_transfer_rate="0.1")
        self.async_run_with_timeout(coro=self.data_source.get_symbol_map())
        self.xrpl_async_client_mock.run_until_update_market_called()

        self.xrpl_async_client_mock.configure_get_account_balances_response(
            base=self.base,
            quote=self.quote,
            base_balance=base_total_balance,
            quote_balance=quote_total_balance,
        )
        wallet_balances = self.async_run_with_timeout(coro=self.data_source.get_account_balances())
        self.xrpl_async_client_mock.run_until_update_balances_called()

        self.assertEqual(base_total_balance, wallet_balances[self.base]["total_balance"])
        self.assertEqual(base_total_balance, wallet_balances[self.base]["available_balance"])
        self.assertEqual(quote_total_balance, wallet_balances[self.quote]["total_balance"])
        self.assertEqual(quote_total_balance, wallet_balances[self.quote]["available_balance"])
