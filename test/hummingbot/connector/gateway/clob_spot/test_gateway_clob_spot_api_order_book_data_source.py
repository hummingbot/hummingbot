import asyncio
import unittest
from decimal import Decimal
from test.hummingbot.connector.gateway.clob_spot.data_sources.injective.injective_mock_utils import InjectiveClientMock
from typing import Awaitable
from unittest.mock import MagicMock

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.gateway.clob_spot.data_sources.injective.injective_api_data_source import (
    InjectiveAPIDataSource,
)
from hummingbot.connector.gateway.clob_spot.gateway_clob_api_order_book_data_source import (
    GatewayCLOBSPOTAPIOrderBookDataSource,
)
from hummingbot.connector.gateway.gateway_order_tracker import GatewayOrderTracker
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount


class MockExchange(ExchangeBase):
    pass


class GatewayCLOBSPOTAPIOrderBookDataSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base = "COIN"
        cls.quote = "ALPHA"
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.base, quote=cls.quote)
        cls.sub_account_id = "someSubAccountId"

    def setUp(self) -> None:
        super().setUp()
        self.listening_tasks = []

        self.initial_timestamp = 1669100347689
        self.injective_async_client_mock = InjectiveClientMock(
            initial_timestamp=self.initial_timestamp,
            sub_account_id=self.sub_account_id,
            base=self.base,
            quote=self.quote,
        )
        self.injective_async_client_mock.start()

        client_config_map = ClientConfigAdapter(hb_config=ClientConfigMap())
        self.api_data_source = InjectiveAPIDataSource(
            trading_pairs=[self.trading_pair],
            connector_spec={
                "chain": "someChain",
                "network": "mainnet",
                "wallet_address": self.sub_account_id,
            },
            client_config_map=client_config_map,
        )
        self.connector = MockExchange(client_config_map=client_config_map)
        self.tracker = GatewayOrderTracker(connector=self.connector)
        self.api_data_source.gateway_order_tracker = self.tracker
        self.ob_data_source = GatewayCLOBSPOTAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair], api_data_source=self.api_data_source
        )
        self.async_run_with_timeout(coro=self.api_data_source.start())

    def tearDown(self) -> None:
        self.injective_async_client_mock.stop()
        self.async_run_with_timeout(coro=self.api_data_source.stop())
        for task in self.listening_tasks:
            task.cancel()
        super().tearDown()

    @staticmethod
    def async_run_with_timeout(coro: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coro, timeout))
        return ret

    def test_get_new_order_book_successful(self):
        self.injective_async_client_mock.configure_orderbook_snapshot(
            timestamp=self.initial_timestamp, bids=[(9, 1), (8, 2)], asks=[(11, 3)]
        )
        order_book: OrderBook = self.async_run_with_timeout(
            self.ob_data_source.get_new_order_book(self.trading_pair)
        )

        self.assertEqual(self.initial_timestamp * 1e3, order_book.snapshot_uid)

        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())

        self.assertEqual(2, len(bids))
        self.assertEqual(9, bids[0].price)
        self.assertEqual(1, bids[0].amount)
        self.assertEqual(1, len(asks))
        self.assertEqual(11, asks[0].price)
        self.assertEqual(3, asks[0].amount)

    def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.ob_data_source._message_queue[self.ob_data_source._trade_messages_queue_key] = mock_queue

        with self.assertRaises(asyncio.CancelledError):
            listening_task = self.ev_loop.create_task(
                self.ob_data_source.listen_for_trades(self.ev_loop, asyncio.Queue())
            )
            self.listening_tasks.append(listening_task)
            self.async_run_with_timeout(listening_task)

    def test_listen_for_trades_successful(self):
        target_price = Decimal("1.157")
        target_size = Decimal("0.001")
        target_maker_fee = Decimal("0.0001157")
        target_taker_fee = Decimal("0.00024")
        target_maker_fee = AddedToCostTradeFee(flat_fees=[TokenAmount(token=self.quote, amount=Decimal("0.0001157"))])
        target_taker_fee = AddedToCostTradeFee(flat_fees=[TokenAmount(token=self.quote, amount=Decimal("0.00024"))])
        target_trade_id = "19889401_someTradeId"

        def configure_trade():
            self.injective_async_client_mock.configure_trade_stream_event(
                timestamp=self.initial_timestamp,
                price=target_price,
                size=target_size,
                maker_fee=target_maker_fee,
                taker_fee=target_taker_fee,
                taker_trade_id=target_trade_id,
            )

        msg_queue: asyncio.Queue = asyncio.Queue()

        subs_listening_task = self.ev_loop.create_task(coro=self.ob_data_source.listen_for_subscriptions())
        self.listening_tasks.append(subs_listening_task)
        trades_listening_task = self.ev_loop.create_task(
            coro=self.ob_data_source.listen_for_trades(self.ev_loop, msg_queue)
        )
        self.listening_tasks.append(trades_listening_task)
        self.ev_loop.call_soon(callback=configure_trade)
        self.injective_async_client_mock.run_until_all_items_delivered()

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertTrue(msg_queue.empty())  # only the taker update was forwarded by the ob data source
        self.assertEqual(OrderBookMessageType.TRADE, msg.type)
        self.assertEqual(target_trade_id, msg.trade_id)
        self.assertEqual(self.initial_timestamp, msg.timestamp)

    def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.ob_data_source._message_queue[self.ob_data_source._snapshot_messages_queue_key] = mock_queue

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(
                self.ob_data_source.listen_for_order_book_snapshots(self.ev_loop, asyncio.Queue())
            )

    def test_listen_for_order_book_snapshots_successful(self):
        def configure_snapshot():
            self.injective_async_client_mock.configure_orderbook_snapshot_stream_event(
                timestamp=self.initial_timestamp, bids=[(9, 1), (8, 2)], asks=[(11, 3)]
            )

        subs_listening_task = self.ev_loop.create_task(coro=self.ob_data_source.listen_for_subscriptions())
        self.listening_tasks.append(subs_listening_task)
        msg_queue: asyncio.Queue = asyncio.Queue()
        listening_task = self.ev_loop.create_task(
            self.ob_data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )
        self.listening_tasks.append(listening_task)
        self.ev_loop.call_soon(callback=configure_snapshot)

        snapshot_msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_msg.type)
        self.assertEqual(self.initial_timestamp, snapshot_msg.timestamp)
        self.assertEqual(2, len(snapshot_msg.bids))
        self.assertEqual(9, snapshot_msg.bids[0].price)
        self.assertEqual(1, snapshot_msg.bids[0].amount)
        self.assertEqual(1, len(snapshot_msg.asks))
        self.assertEqual(11, snapshot_msg.asks[0].price)
        self.assertEqual(3, snapshot_msg.asks[0].amount)
