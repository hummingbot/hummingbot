import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, Mock, patch

from xrpl.models import XRP, IssuedCurrency

from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange.xrpl.xrpl_api_order_book_data_source import XRPLAPIOrderBookDataSource
from hummingbot.connector.exchange.xrpl.xrpl_exchange import XrplExchange
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
        # self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1
        self.resume_test_event = asyncio.Event()

        # exchange_market_info = CONSTANTS.MARKETS
        # self.connector._initialize_trading_pair_symbols_from_exchange_info(exchange_market_info)

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
        self.mock_client = AsyncMock()
        self.mock_client.__aenter__.return_value = self.mock_client
        self.mock_client.__aexit__.return_value = None
        self.mock_client.is_open = Mock(return_value=True)
        self.data_source._get_client = AsyncMock(return_value=self.mock_client)

    def tearDown(self) -> None:
        # self.listening_task and self.listening_task.cancel()
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

    @patch("xrpl.models.requests.BookOffers")
    async def test_request_order_book_snapshot(self, mock_book_offers):
        mock_book_offers.return_value.status = "success"
        mock_book_offers.return_value.result = {"offers": []}

        self.mock_client.request.return_value = mock_book_offers.return_value

        await self.data_source._request_order_book_snapshot("SOLO-XRP")

        assert self.mock_client.request.call_count == 2

        order_book: OrderBook = await self.data_source.get_new_order_book(self.trading_pair)

        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(0, len(bids))
        self.assertEqual(0, len(asks))

    @patch("xrpl.models.requests.BookOffers")
    async def test_request_order_book_snapshot_exception(self, mock_book_offers):
        mock_book_offers.return_value.status = "error"
        mock_book_offers.return_value.result = {"offers": []}

        self.mock_client.request.return_value = mock_book_offers.return_value

        with self.assertRaises(Exception) as context:
            await self.data_source._request_order_book_snapshot("SOLO-XRP")

        self.assertTrue("Error fetching order book snapshot" in str(context.exception))

    async def test_fetch_order_book_side_exception(self):
        self.mock_client.request.side_effect = TimeoutError
        self.data_source._sleep = AsyncMock()

        with self.assertRaises(TimeoutError):
            await self.data_source.fetch_order_book_side(self.mock_client, 12345, {}, {}, 50)

    async def test_process_websocket_messages_for_pair_success(self):
        # Setup mock client
        self.mock_client.is_open = Mock(side_effect=[True, False])  # Return True first, then False to exit the loop
        self.mock_client.send = AsyncMock()

        # Setup mock message iterator
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
                "delivered_amount": {
                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                    "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mocks
                    "value": "2.239836701211152",
                },
                "offer_changes": [
                    {
                        "status": "filled",
                        "taker_gets": {
                            "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                            "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                            "value": "2.239836701211152",
                        },
                        "maker_exchange_rate": "0.22452700389932698",
                        "ledger_index": "186D33545697D90A5F18C1541F2228A629435FC540D473574B3B75FEA7B4B88B",  # noqa: mock
                    }
                ],
            },
        }
        self.mock_client.__aiter__.return_value = [mock_message]

        # Mock the connector's get_currencies_from_trading_pair method
        self.connector.get_currencies_from_trading_pair = Mock(
            return_value=(
                IssuedCurrency(
                    currency="534F4C4F00000000000000000000000000000000",  # noqa: mock
                    issuer="rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                ),
                XRP,
            )
        )
        self.connector.auth.get_account = Mock(return_value="r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK")  # noqa: mock

        task = asyncio.create_task(self.data_source._process_websocket_messages_for_pair(self.trading_pair))
        await asyncio.wait_for(asyncio.sleep(0.1), timeout=1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify the results
        self.mock_client.send.assert_called()
        self.assertTrue(self.mock_client.__aenter__.called)
        self.assertTrue(self.mock_client.__aexit__.called)

    async def test_process_websocket_messages_for_pair_connection_error(self):
        # Setup mock client that raises ConnectionError
        mock_client = AsyncMock()
        mock_client.__aenter__.side_effect = ConnectionError("Connection failed")

        # Mock the connector's get_currencies_from_trading_pair method
        self.connector.get_currencies_from_trading_pair = Mock(
            return_value=(
                IssuedCurrency(
                    currency="534F4C4F00000000000000000000000000000000",  # noqa: mock
                    issuer="rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                ),
                XRP,
            )
        )
        self.connector.auth.get_account = Mock(return_value="r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK")  # noqa: mock

        task = asyncio.create_task(self.data_source._process_websocket_messages_for_pair(self.trading_pair))
        await asyncio.wait_for(asyncio.sleep(0.1), timeout=1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify the results
        self.assertTrue(self.mock_client.__aenter__.called)
        self.assertTrue(self.mock_client.__aexit__.called)

    async def test_on_message_process_trade(self):
        # Setup mock client with async iterator
        mock_client = AsyncMock()
        mock_client.__aiter__.return_value = [
            {
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
                    "delivered_amount": {
                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                        "value": "2.239836701211152",
                    },
                    "offer_changes": [
                        {
                            "status": "filled",
                            "taker_gets": {
                                "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                "value": "2.239836701211152",
                            },
                            "maker_exchange_rate": "0.22452700389932698",
                            "ledger_index": "186D33545697D90A5F18C1541F2228A629435FC540D473574B3B75FEA7B4B88B",  # noqa: mock
                        }
                    ],
                },
            }
        ]

        # Mock the message queue
        self.data_source._message_queue = {CONSTANTS.TRADE_EVENT_TYPE: asyncio.Queue()}

        # Create proper IssuedCurrency object for base currency
        base_currency = IssuedCurrency(
            currency="534F4C4F00000000000000000000000000000000",  # hex encoded "SOLO"
            issuer="rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
        )

        # Run the test
        await self.data_source.on_message(mock_client, self.trading_pair, base_currency)

        # Verify that a trade message was added to the queue
        self.assertFalse(self.data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE].empty())
        trade_message = await self.data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE].get()
        self.assertEqual(trade_message["trading_pair"], self.trading_pair)
        self.assertIn("trade", trade_message)

        trade_data = trade_message["trade"]
        self.assertIn("trade_type", trade_data)
        self.assertIn("trade_id", trade_data)
        self.assertIn("update_id", trade_data)
        self.assertIn("price", trade_data)
        self.assertIn("amount", trade_data)
        self.assertIn("timestamp", trade_data)

        # Verify trade values
        self.assertEqual(trade_data["trade_type"], float(TradeType.BUY.value))
        self.assertEqual(trade_data["price"], Decimal("0.223431972248075594311700342586846090853214263916015625"))
        self.assertEqual(trade_data["amount"], Decimal("2.25103415119826"))

    async def test_on_message_invalid_message(self):
        # Setup mock client
        mock_client = AsyncMock()

        # Mock the message queue
        self.data_source._message_queue = {CONSTANTS.TRADE_EVENT_TYPE: asyncio.Queue()}

        # Run the test
        await self.data_source.on_message(
            mock_client,
            self.trading_pair,
            {"currency": "SOLO", "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz"},  # noqa: mock
        )

        # Verify that no message was added to the queue
        self.assertTrue(self.data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE].empty())

    async def test_on_message_exception(self):
        # Setup mock client that raises an exception
        self.mock_client.__aiter__.side_effect = Exception("Test exception")

        # Mock the message queue
        self.data_source._message_queue = {CONSTANTS.TRADE_EVENT_TYPE: asyncio.Queue()}

        # Run the test
        with self.assertRaises(Exception) as context:
            await self.data_source.on_message(
                self.mock_client,
                self.trading_pair,
                {"currency": "SOLO", "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz"},  # noqa: mock
            )
        self.assertEqual(str(context.exception), "Test exception")
