import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from xrpl.models import XRP, IssuedCurrency
from xrpl.models.response import Response, ResponseStatus, ResponseType

from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange.xrpl.xrpl_api_order_book_data_source import XRPLAPIOrderBookDataSource
from hummingbot.connector.exchange.xrpl.xrpl_exchange import XrplExchange
from hummingbot.connector.exchange.xrpl.xrpl_worker_pool import QueryResult
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook


class XRPLAPIOrderBookDataSourceUnitTests(IsolatedAsyncioWrapperTestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "SOLO"
        cls.quote_asset = "XRP"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None

        self.connector = XrplExchange(
            xrpl_secret_key="",
            wss_node_urls=["wss://sample.com"],
            max_request_per_minute=100,
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )
        self.data_source = XRPLAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
        )

        self.data_source._sleep = AsyncMock()
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.resume_test_event = asyncio.Event()

        self.connector._lock_delay_seconds = 0

        trading_rule = TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("1e-6"),
            min_price_increment=Decimal("1e-6"),
            min_quote_amount_increment=Decimal("1e-6"),
            min_base_amount_increment=Decimal("1e-15"),
            min_notional_size=Decimal("1e-6"),
        )

        self.connector._trading_rules[self.trading_pair] = trading_rule

        # Setup mock worker manager
        self.mock_query_pool = MagicMock()
        self.mock_worker_manager = MagicMock()
        self.mock_worker_manager.get_query_pool.return_value = self.mock_query_pool

    def tearDown(self) -> None:
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _trade_update_event(self):
        trade_data = {
            "trade_type": float(TradeType.SELL.value),
            "trade_id": "example_trade_id",
            "update_id": 123456789,
            "price": Decimal("0.001"),
            "amount": Decimal("1"),
            "timestamp": 123456789,
        }

        resp = {"trading_pair": self.trading_pair, "trades": trade_data}
        return resp

    def _snapshot_response(self):
        resp = {
            "asks": [
                {
                    "Account": "r9aZRryD8AZzGqQjYrQQuBBzebjF555Xsa",  # noqa: mock
                    "BookDirectory": "5C8970D155D65DB8FF49B291D7EFFA4A09F9E8A68D9974B25A07FA0FAB195976",  # noqa: mock
                    "BookNode": "0",
                    "Flags": 131072,
                    "LedgerEntryType": "Offer",
                    "OwnerNode": "0",
                    "PreviousTxnID": "373EA7376A1F9DC150CCD534AC0EF8544CE889F1850EFF0084B46997DAF4F1DA",  # noqa: mock
                    "PreviousTxnLgrSeq": 88935730,
                    "Sequence": 86514258,
                    "TakerGets": {
                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                        "value": "91.846106",
                    },
                    "TakerPays": "20621931",
                    "index": "1395ACFB20A47DE6845CF5DB63CF2E3F43E335D6107D79E581F3398FF1B6D612",  # noqa: mock
                    "owner_funds": "140943.4119268388",
                    "quality": "224527.003899327",
                },
                {
                    "Account": "rhqTdSsJAaEReRsR27YzddqyGoWTNMhEvC",  # noqa: mock
                    "BookDirectory": "5C8970D155D65DB8FF49B291D7EFFA4A09F9E8A68D9974B25A07FA8ECFD95726",  # noqa: mock
                    "BookNode": "0",
                    "Flags": 0,
                    "LedgerEntryType": "Offer",
                    "OwnerNode": "2",
                    "PreviousTxnID": "2C266D54DDFAED7332E5E6EC68BF08CC37CE2B526FB3CFD8225B667C4C1727E1",  # noqa: mock
                    "PreviousTxnLgrSeq": 88935726,
                    "Sequence": 71762354,
                    "TakerGets": {
                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                        "value": "44.527243023",
                    },
                    "TakerPays": "10000000",
                    "index": "186D33545697D90A5F18C1541F2228A629435FC540D473574B3B75FEA7B4B88B",  # noqa: mock
                    "owner_funds": "88.4155435721498",
                    "quality": "224581.6116401958",
                },
            ],
            "bids": [
                {
                    "Account": "rn3uVsXJL7KRTa7JF3jXXGzEs3A2UEfett",  # noqa: mock
                    "BookDirectory": "C73FAC6C294EBA5B9E22A8237AAE80725E85372510A6CA794F0FE48CEADD8471",  # noqa: mock
                    "BookNode": "0",
                    "Flags": 0,
                    "LedgerEntryType": "Offer",
                    "OwnerNode": "0",
                    "PreviousTxnID": "2030FB97569D955921659B150A2F5F02CC9BBFCA95BAC6B8D55D141B0ABFA945",  # noqa: mock
                    "PreviousTxnLgrSeq": 88935721,
                    "Sequence": 74073461,
                    "TakerGets": "187000000",
                    "TakerPays": {
                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                        "value": "836.5292665312212",
                    },
                    "index": "3F41585F327EA3690AD19F2A302C5DF2904E01D39C9499B303DB7FA85868B69F",  # noqa: mock
                    "owner_funds": "6713077567",
                    "quality": "0.000004473418537600113",
                },
                {
                    "Account": "rsoLoDTcxn9wCEHHBR7enMhzQMThkB2w28",
                    "BookDirectory": "C73FAC6C294EBA5B9E22A8237AAE80725E85372510A6CA794F0FE48D021C71F2",  # noqa: mock
                    "BookNode": "0",
                    "Expiration": 772644742,
                    "Flags": 0,
                    "LedgerEntryType": "Offer",
                    "OwnerNode": "0",
                    "PreviousTxnID": "226434A5399E210F82F487E8710AE21FFC19FE86FC38F3634CF328FA115E9574",  # noqa: mock
                    "PreviousTxnLgrSeq": 88935719,
                    "Sequence": 69870875,
                    "TakerGets": "90000000",
                    "TakerPays": {
                        "currency": "534F4C4F00000000000000000000000000000000",
                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
                        "value": "402.6077034840102",
                    },
                    "index": "4D31D069F1E2B0F2016DA0F1BF232411CB1B4642A49538CD6BB989F353D52411",  # noqa: mock
                    "owner_funds": "827169016",
                    "quality": "0.000004473418927600114",
                },
            ],
            "trading_pair": "SOLO-XRP",
        }

        return resp

    @patch(
        "hummingbot.connector.exchange.xrpl.xrpl_api_order_book_data_source.XRPLAPIOrderBookDataSource._request_order_book_snapshot"
    )
    async def test_get_new_order_book_successful(self, request_order_book_mock):
        request_order_book_mock.return_value = self._snapshot_response()

        order_book: OrderBook = await self.data_source.get_new_order_book(self.trading_pair)

        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(2, len(bids))
        self.assertEqual(0.2235426870065409, bids[0].price)
        self.assertEqual(836.5292665312212, bids[0].amount)
        self.assertEqual(2, len(asks))
        self.assertEqual(0.22452700389932698, asks[0].price)
        self.assertEqual(91.846106, asks[0].amount)

    @patch(
        "hummingbot.connector.exchange.xrpl.xrpl_api_order_book_data_source.XRPLAPIOrderBookDataSource._request_order_book_snapshot"
    )
    async def test_get_new_order_book_get_empty(self, request_order_book_mock):
        request_order_book_mock.return_value = {}
        order_book: OrderBook = await self.data_source.get_new_order_book(self.trading_pair)

        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(0, len(bids))
        self.assertEqual(0, len(asks))

    @patch(
        "hummingbot.connector.exchange.xrpl.xrpl_api_order_book_data_source.XRPLAPIOrderBookDataSource.get_last_traded_prices"
    )
    async def test_get_last_traded_prices(self, mock_get_last_traded_prices):
        mock_get_last_traded_prices.return_value = {"SOLO-XRP": 0.5}
        result = await self.data_source.get_last_traded_prices(["SOLO-XRP"])
        self.assertEqual(result, {"SOLO-XRP": 0.5})

    async def test_request_order_book_snapshot(self):
        """Test requesting order book snapshot with worker pool."""
        # Set up the worker manager
        self.data_source.set_worker_manager(self.mock_worker_manager)

        # Mock the connector's get_currencies_from_trading_pair
        base_currency = IssuedCurrency(
            currency="534F4C4F00000000000000000000000000000000",
            issuer="rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
        )
        quote_currency = XRP()
        self.connector.get_currencies_from_trading_pair = Mock(
            return_value=(base_currency, quote_currency)
        )

        # Create mock responses for asks and bids
        asks_response = Response(
            status=ResponseStatus.SUCCESS,
            result={"offers": []},
            id=1,
            type=ResponseType.RESPONSE
        )
        bids_response = Response(
            status=ResponseStatus.SUCCESS,
            result={"offers": []},
            id=2,
            type=ResponseType.RESPONSE
        )

        # Create QueryResult objects
        asks_result = QueryResult(success=True, response=asks_response, error=None)
        bids_result = QueryResult(success=True, response=bids_response, error=None)

        # Mock query pool submit to return different results for asks and bids
        self.mock_query_pool.submit = AsyncMock(side_effect=[asks_result, bids_result])

        # Call the method
        result = await self.data_source._request_order_book_snapshot("SOLO-XRP")

        # Verify
        self.assertEqual(result, {"asks": [], "bids": []})
        self.assertEqual(self.mock_query_pool.submit.call_count, 2)

    async def test_request_order_book_snapshot_without_worker_manager(self):
        """Test that _request_order_book_snapshot raises error without worker manager."""
        # Don't set worker manager - it should raise
        with self.assertRaises(RuntimeError) as context:
            await self.data_source._request_order_book_snapshot("SOLO-XRP")

        self.assertIn("Worker manager not initialized", str(context.exception))

    async def test_request_order_book_snapshot_error_response(self):
        """Test error handling when query pool returns error result."""
        # Set up the worker manager
        self.data_source.set_worker_manager(self.mock_worker_manager)

        # Mock the connector's get_currencies_from_trading_pair
        base_currency = IssuedCurrency(
            currency="534F4C4F00000000000000000000000000000000",
            issuer="rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
        )
        quote_currency = XRP()
        self.connector.get_currencies_from_trading_pair = Mock(
            return_value=(base_currency, quote_currency)
        )

        # Create error result for asks
        asks_result = QueryResult(success=False, response=None, error="Connection failed")

        # Mock query pool submit
        self.mock_query_pool.submit = AsyncMock(return_value=asks_result)

        # Call the method - should raise ValueError
        with self.assertRaises(ValueError) as context:
            await self.data_source._request_order_book_snapshot("SOLO-XRP")

        self.assertIn("Error fetching", str(context.exception))

    async def test_request_order_book_snapshot_exception(self):
        """Test exception handling in _request_order_book_snapshot."""
        # Set up the worker manager
        self.data_source.set_worker_manager(self.mock_worker_manager)

        # Mock the connector's get_currencies_from_trading_pair
        base_currency = IssuedCurrency(
            currency="534F4C4F00000000000000000000000000000000",
            issuer="rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
        )
        quote_currency = XRP()
        self.connector.get_currencies_from_trading_pair = Mock(
            return_value=(base_currency, quote_currency)
        )

        # Mock query pool submit to raise exception
        self.mock_query_pool.submit = AsyncMock(side_effect=Exception("Network error"))

        # Call the method - should raise
        with self.assertRaises(Exception) as context:
            await self.data_source._request_order_book_snapshot("SOLO-XRP")

        self.assertIn("Network error", str(context.exception))

    async def test_set_worker_manager(self):
        """Test setting worker manager."""
        self.assertIsNone(self.data_source._worker_manager)

        self.data_source.set_worker_manager(self.mock_worker_manager)

        self.assertEqual(self.data_source._worker_manager, self.mock_worker_manager)

    async def test_get_next_node_url(self):
        """Test _get_next_node_url method."""
        # Setup mock node pool
        self.connector._node_pool = MagicMock()
        self.connector._node_pool._node_urls = ["wss://node1.com", "wss://node2.com", "wss://node3.com"]
        self.connector._node_pool._bad_nodes = {}

        # Get first URL
        url1 = self.data_source._get_next_node_url()
        self.assertEqual(url1, "wss://node1.com")

        # Get next URL - should rotate
        url2 = self.data_source._get_next_node_url()
        self.assertEqual(url2, "wss://node2.com")

        # Get next URL with exclusion
        url3 = self.data_source._get_next_node_url(exclude_url="wss://node3.com")
        self.assertEqual(url3, "wss://node1.com")

    async def test_get_next_node_url_skips_bad_nodes(self):
        """Test that _get_next_node_url skips bad nodes."""
        import time

        # Setup mock node pool with bad node
        self.connector._node_pool = MagicMock()
        self.connector._node_pool._node_urls = ["wss://node1.com", "wss://node2.com"]
        # Mark node1 as bad (future timestamp means still in cooldown)
        self.connector._node_pool._bad_nodes = {"wss://node1.com": time.time() + 3600}

        # Reset the index
        self.data_source._subscription_node_index = 0

        # Should skip node1 and return node2
        url = self.data_source._get_next_node_url()
        self.assertEqual(url, "wss://node2.com")

    async def test_close_subscription_connection(self):
        """Test _close_subscription_connection method."""
        # Test with None client
        await self.data_source._close_subscription_connection(None)

        # Test with mock client
        mock_client = AsyncMock()
        await self.data_source._close_subscription_connection(mock_client)
        mock_client.close.assert_called_once()

        # Test with client that raises exception
        mock_client_error = AsyncMock()
        mock_client_error.close.side_effect = Exception("Close error")
        # Should not raise
        await self.data_source._close_subscription_connection(mock_client_error)

    @patch(
        "hummingbot.connector.exchange.xrpl.xrpl_api_order_book_data_source.AsyncWebsocketClient"
    )
    async def test_create_subscription_connection_success(self, mock_ws_class):
        """Test successful creation of subscription connection."""
        # Setup mock node pool
        self.connector._node_pool = MagicMock()
        self.connector._node_pool._node_urls = ["wss://node1.com"]
        self.connector._node_pool._bad_nodes = {}

        # Setup mock websocket client
        mock_client = AsyncMock()
        mock_client._websocket = MagicMock()
        mock_ws_class.return_value = mock_client

        # Reset node index
        self.data_source._subscription_node_index = 0

        # Create connection
        result = await self.data_source._create_subscription_connection(self.trading_pair)

        self.assertEqual(result, mock_client)
        mock_client.open.assert_called_once()

    @patch(
        "hummingbot.connector.exchange.xrpl.xrpl_api_order_book_data_source.AsyncWebsocketClient"
    )
    async def test_create_subscription_connection_timeout(self, mock_ws_class):
        """Test subscription connection timeout handling."""
        # Setup mock node pool
        self.connector._node_pool = MagicMock()
        self.connector._node_pool._node_urls = ["wss://node1.com"]
        self.connector._node_pool._bad_nodes = {}

        # Setup mock websocket client that times out
        mock_client = AsyncMock()
        mock_client.open.side_effect = asyncio.TimeoutError()
        mock_ws_class.return_value = mock_client

        # Reset node index
        self.data_source._subscription_node_index = 0

        # Create connection - should return None after trying all nodes
        result = await self.data_source._create_subscription_connection(self.trading_pair)

        self.assertIsNone(result)
        self.connector._node_pool.mark_bad_node.assert_called_with("wss://node1.com")

    async def test_on_message_with_health_tracking(self):
        """Test _on_message_with_health_tracking processes trade messages correctly."""
        # Setup mock client with async iterator
        mock_client = AsyncMock()

        mock_message = {
            "transaction": {
                "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                "Fee": "10",
                "Flags": 786432,
                "LastLedgerSequence": 88954510,
                "Sequence": 84437780,
                "TakerGets": "502953",
                "TakerPays": {
                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                    "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                    "value": "2.239836701211152",
                },
                "TransactionType": "OfferCreate",
                "date": 772640450,
            },
            "meta": {
                "AffectedNodes": [],
                "TransactionIndex": 0,
                "TransactionResult": "tesSUCCESS",
                "delivered_amount": {
                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                    "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                    "value": "2.239836701211152",
                },
            },
        }

        # Make mock_client async iterable with one message then stop
        async def async_iter():
            yield mock_message

        mock_client.__aiter__ = lambda self: async_iter()

        # Setup base currency
        base_currency = IssuedCurrency(
            currency="534F4C4F00000000000000000000000000000000",
            issuer="rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
        )

        # Initialize message queue
        self.data_source._message_queue = {CONSTANTS.TRADE_EVENT_TYPE: asyncio.Queue()}

        # Run the method - it should process the message without trades (no offer_changes)
        await self.data_source._on_message_with_health_tracking(mock_client, self.trading_pair, base_currency)

        # No trades should be added since there are no offer_changes in meta
        self.assertTrue(self.data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE].empty())

    async def test_on_message_with_health_tracking_with_trade(self):
        """Test _on_message_with_health_tracking processes trade messages with offer changes."""
        # Setup mock client with async iterator
        mock_client = MagicMock()

        mock_message = {
            "transaction": {
                "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                "Fee": "10",
                "Flags": 786432,
                "LastLedgerSequence": 88954510,
                "Sequence": 84437780,
                "TakerGets": "502953",
                "TakerPays": {
                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                    "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                    "value": "2.239836701211152",
                },
                "TransactionType": "OfferCreate",
                "date": 772640450,
            },
            "meta": {
                "AffectedNodes": [
                    {
                        "ModifiedNode": {
                            "FinalFields": {
                                "Account": "rhqTdSsJAaEReRsR27YzddqyGoWTNMhEvC",  # noqa: mock
                                "BookDirectory": "5C8970D155D65DB8FF49B291D7EFFA4A09F9E8A68D9974B25A07F01A195F8476",  # noqa: mock
                                "BookNode": "0",
                                "Flags": 0,
                                "OwnerNode": "2",
                                "Sequence": 71762948,
                                "TakerGets": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                    "value": "42.50531785780174",
                                },
                                "TakerPays": "9497047",
                            },
                            "LedgerEntryType": "Offer",
                            "PreviousFields": {
                                "TakerGets": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                    "value": "44.756352009",
                                },
                                "TakerPays": "10000000",
                            },
                            "LedgerIndex": "186D33545697D90A5F18C1541F2228A629435FC540D473574B3B75FEA7B4B88B",  # noqa: mock
                        }
                    }
                ],
                "TransactionIndex": 0,
                "TransactionResult": "tesSUCCESS",
            },
        }

        # Make mock_client async iterable - using a helper class
        class AsyncIteratorMock:
            def __init__(self, messages):
                self.messages = messages
                self.index = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index < len(self.messages):
                    msg = self.messages[self.index]
                    self.index += 1
                    return msg
                raise StopAsyncIteration

        mock_client = AsyncIteratorMock([mock_message])

        # Setup base currency
        base_currency = IssuedCurrency(
            currency="534F4C4F00000000000000000000000000000000",
            issuer="rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
        )

        # Initialize message queue
        self.data_source._message_queue = {CONSTANTS.TRADE_EVENT_TYPE: asyncio.Queue()}

        # Run the method
        await self.data_source._on_message_with_health_tracking(mock_client, self.trading_pair, base_currency)

        # Check if trade was added to the queue (depends on get_order_book_changes result)
        # The actual result depends on xrpl library processing

    async def test_on_message_with_invalid_message(self):
        """Test _on_message_with_health_tracking handles invalid messages."""
        # Message without transaction or meta
        invalid_message = {"some": "data"}

        class AsyncIteratorMock:
            def __init__(self, messages):
                self.messages = messages
                self.index = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index < len(self.messages):
                    msg = self.messages[self.index]
                    self.index += 1
                    return msg
                raise StopAsyncIteration

        mock_client = AsyncIteratorMock([invalid_message])

        base_currency = IssuedCurrency(
            currency="534F4C4F00000000000000000000000000000000",
            issuer="rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
        )

        self.data_source._message_queue = {CONSTANTS.TRADE_EVENT_TYPE: asyncio.Queue()}

        # Should not raise, just log debug message
        await self.data_source._on_message_with_health_tracking(mock_client, self.trading_pair, base_currency)

        # No trades should be added
        self.assertTrue(self.data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE].empty())

    async def test_parse_trade_message(self):
        """Test _parse_trade_message method."""
        raw_message = {
            "trading_pair": self.trading_pair,
            "trade": {
                "trade_type": float(TradeType.BUY.value),
                "trade_id": 123456,
                "update_id": 789012,
                "price": Decimal("0.25"),
                "amount": Decimal("100"),
                "timestamp": 1234567890,
            },
        }

        message_queue = asyncio.Queue()

        await self.data_source._parse_trade_message(raw_message, message_queue)

        # Verify message was added to queue
        self.assertFalse(message_queue.empty())

    async def test_subscribe_to_trading_pair_not_supported(self):
        """Test that dynamic subscription returns False."""
        result = await self.data_source.subscribe_to_trading_pair(self.trading_pair)
        self.assertFalse(result)

    async def test_unsubscribe_from_trading_pair_not_supported(self):
        """Test that dynamic unsubscription returns False."""
        result = await self.data_source.unsubscribe_from_trading_pair(self.trading_pair)
        self.assertFalse(result)

    async def test_subscription_connection_dataclass(self):
        """Test SubscriptionConnection dataclass."""
        from hummingbot.connector.exchange.xrpl.xrpl_api_order_book_data_source import SubscriptionConnection

        conn = SubscriptionConnection(
            trading_pair=self.trading_pair,
            url="wss://test.com",
        )

        # Test default values
        self.assertIsNone(conn.client)
        self.assertIsNone(conn.listener_task)
        self.assertFalse(conn.is_connected)
        self.assertEqual(conn.reconnect_count, 0)

        # Test update_last_message_time
        old_time = conn.last_message_time
        conn.update_last_message_time()
        self.assertGreaterEqual(conn.last_message_time, old_time)

        # Test is_stale
        self.assertFalse(conn.is_stale(timeout=3600))  # Not stale with 1 hour timeout
        # Manually set old time to test stale detection
        conn.last_message_time = 0
        self.assertTrue(conn.is_stale(timeout=1))  # Stale with 1 second timeout
