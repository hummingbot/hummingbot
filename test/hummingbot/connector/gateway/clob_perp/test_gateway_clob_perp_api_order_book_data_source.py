import asyncio
import unittest
from decimal import Decimal
from test.hummingbot.connector.gateway.clob_perp.data_sources.injective_perpetual.injective_perpetual_mock_utils import (
    InjectivePerpetualClientMock,
)
from typing import Awaitable
from unittest.mock import MagicMock

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.gateway.clob_perp.data_sources.injective_perpetual.injective_perpetual_api_data_source import (
    InjectivePerpetualAPIDataSource,
)
from hummingbot.connector.gateway.clob_perp.gateway_clob_perp_api_order_book_data_source import (
    GatewayCLOBPerpAPIOrderBookDataSource,
)
from hummingbot.connector.gateway.gateway_order_tracker import GatewayOrderTracker
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount


class MockExchange(ExchangeBase):
    pass


class GatewayCLOBPerpAPIOrderBookDataSourceTest(unittest.TestCase):
    ev_loop: asyncio.AbstractEventLoop
    base: str
    quote: str
    trading_pair: str
    sub_account_id: str

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
        self.injective_async_client_mock = InjectivePerpetualClientMock(
            initial_timestamp=self.initial_timestamp,
            sub_account_id=self.sub_account_id,
            base=self.base,
            quote=self.quote,
        )
        self.injective_async_client_mock.start()

        client_config_map = ClientConfigAdapter(hb_config=ClientConfigMap())
        self.api_data_source = InjectivePerpetualAPIDataSource(
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
        self.ob_data_source = GatewayCLOBPerpAPIOrderBookDataSource(
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

    def test_listen_for_funding_info_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.ob_data_source._message_queue[self.ob_data_source._funding_info_messages_queue_key] = mock_queue

        with self.assertRaises(asyncio.CancelledError):
            listening_task = self.ev_loop.create_task(
                self.ob_data_source.listen_for_funding_info(asyncio.Queue())
            )
            self.listening_tasks.append(listening_task)
            self.async_run_with_timeout(listening_task)

    def test_listen_for_funding_info_successful(self):
        initial_funding_info = self.async_run_with_timeout(
            coro=self.ob_data_source.get_funding_info(self.trading_pair)
        )

        update_target_index_price = initial_funding_info.index_price + 1
        update_target_mark_price = initial_funding_info.mark_price + 2
        update_target_next_funding_time = initial_funding_info.next_funding_utc_timestamp * 2
        update_target_funding_rate = initial_funding_info.rate + Decimal("0.0003")

        self.injective_async_client_mock.configure_funding_info_stream_event(
            index_price=update_target_index_price,
            mark_price=update_target_mark_price,
            next_funding_time=update_target_next_funding_time,
            funding_rate=update_target_funding_rate,
        )

        self.injective_async_client_mock.run_until_all_items_delivered()

        updated_funding_info = self.async_run_with_timeout(
            coro=self.ob_data_source.get_funding_info(self.trading_pair)
        )

        self.assertEqual(update_target_index_price, updated_funding_info.index_price)
        self.assertEqual(update_target_mark_price, updated_funding_info.mark_price)
        self.assertEqual(update_target_next_funding_time, updated_funding_info.next_funding_utc_timestamp)
        self.assertEqual(update_target_funding_rate, updated_funding_info.rate)

    def test_get_funding_info(self):
        expected_index_price = Decimal("10")
        expected_mark_price = Decimal("10.1")
        expected_next_funding_time = 1610000000
        expected_funding_rate = Decimal("0.0009")

        self.injective_async_client_mock.configure_get_funding_info_response(
            index_price=expected_index_price,
            mark_price=expected_mark_price,
            next_funding_time=expected_next_funding_time,
            funding_rate=expected_funding_rate,
        )

        funding_rate: FundingInfo = self.async_run_with_timeout(
            coro=self.ob_data_source.get_funding_info(trading_pair=self.trading_pair)
        )

        self.assertEqual(expected_index_price, funding_rate.index_price)
        self.assertEqual(expected_mark_price, funding_rate.mark_price)
        self.assertEqual(expected_next_funding_time, funding_rate.next_funding_utc_timestamp)
        self.assertEqual(expected_funding_rate, funding_rate.rate)
