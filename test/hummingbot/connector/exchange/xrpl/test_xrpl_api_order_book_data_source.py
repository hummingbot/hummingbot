import asyncio
import unittest
from decimal import Decimal
from typing import Awaitable
from unittest.mock import AsyncMock, patch

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange.xrpl.xrpl_api_order_book_data_source import XRPLAPIOrderBookDataSource
from hummingbot.connector.exchange.xrpl.xrpl_exchange import XrplExchange
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook


class XRPLAPIOrderBookDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "SOLO"
        cls.quote_asset = "XRP"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = XrplExchange(
            client_config_map=client_config_map,
            xrpl_secret_key="",
            wss_node_url="wss://sample.com",
            wss_second_node_url="wss://sample.com",
            wss_third_node_url="wss://sample.com",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )
        self.data_source = XRPLAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
        )
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1
        self.resume_test_event = asyncio.Event()

        exchange_market_info = CONSTANTS.MARKETS
        self.connector._initialize_trading_pair_symbols_from_exchange_info(exchange_market_info)

        trading_rule = TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("1e-6"),
            min_price_increment=Decimal("1e-6"),
            min_quote_amount_increment=Decimal("1e-6"),
            min_base_amount_increment=Decimal("1e-15"),
            min_notional_size=Decimal("1e-6"),
        )

        self.connector._trading_rules[self.trading_pair] = trading_rule
        self.data_source._xrpl_client = AsyncMock()
        self.data_source._xrpl_client.__aenter__.return_value = self.data_source._xrpl_client
        self.data_source._xrpl_client.__aexit__.return_value = None

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 5):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

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
                        "currency": "534F4C4F00000000000000000000000000000000",
                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
                        "value": "91.846106",
                    },
                    "TakerPays": "20621931",
                    "index": "1395ACFB20A47DE6845CF5DB63CF2E3F43E335D6107D79E581F3398FF1B6D612",  # noqa: mock
                    "owner_funds": "140943.4119268388",
                    "quality": "224527.003899327",
                },
                {
                    "Account": "rhqTdSsJAaEReRsR27YzddqyGoWTNMhEvC",
                    "BookDirectory": "5C8970D155D65DB8FF49B291D7EFFA4A09F9E8A68D9974B25A07FA8ECFD95726",  # noqa: mock
                    "BookNode": "0",
                    "Flags": 0,
                    "LedgerEntryType": "Offer",
                    "OwnerNode": "2",
                    "PreviousTxnID": "2C266D54DDFAED7332E5E6EC68BF08CC37CE2B526FB3CFD8225B667C4C1727E1",  # noqa: mock
                    "PreviousTxnLgrSeq": 88935726,
                    "Sequence": 71762354,
                    "TakerGets": {
                        "currency": "534F4C4F00000000000000000000000000000000",
                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
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
                        "currency": "534F4C4F00000000000000000000000000000000",
                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
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
    def test_get_new_order_book_successful(self, request_order_book_mock):
        request_order_book_mock.return_value = self._snapshot_response()

        order_book: OrderBook = self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))

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
    def test_get_new_order_book_get_empty(self, request_order_book_mock):
        request_order_book_mock.return_value = {}
        order_book: OrderBook = self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))

        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(0, len(bids))
        self.assertEqual(0, len(asks))

    @patch(
        "hummingbot.connector.exchange.xrpl.xrpl_api_order_book_data_source.XRPLAPIOrderBookDataSource.get_last_traded_prices"
    )
    def test_get_last_traded_prices(self, mock_get_last_traded_prices):
        mock_get_last_traded_prices.return_value = {"SOLO-XRP": 0.5}
        result = self.async_run_with_timeout(self.data_source.get_last_traded_prices(["SOLO-XRP"]))
        self.assertEqual(result, {"SOLO-XRP": 0.5})

    @patch("xrpl.models.requests.BookOffers")
    def test_request_order_book_snapshot(self, mock_book_offers):
        mock_book_offers.return_value.status = "success"
        mock_book_offers.return_value.result = {"offers": []}

        self.data_source._xrpl_client.is_open.return_value = False
        self.data_source._xrpl_client.request.return_value = mock_book_offers.return_value

        self.async_run_with_timeout(self.data_source._request_order_book_snapshot("SOLO-XRP"))

        assert self.data_source._xrpl_client.request.call_count == 2

        order_book: OrderBook = self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))

        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(0, len(bids))
        self.assertEqual(0, len(asks))

    @patch("xrpl.models.requests.BookOffers")
    def test_request_order_book_snapshot_exception(self, mock_book_offers):
        mock_book_offers.return_value.status = "error"
        mock_book_offers.return_value.result = {"offers": []}

        self.data_source._xrpl_client.is_open.return_value = False
        self.data_source._xrpl_client.request.return_value = mock_book_offers.return_value

        with self.assertRaises(Exception) as context:
            self.async_run_with_timeout(self.data_source._request_order_book_snapshot("SOLO-XRP"))

        self.assertTrue("Error fetching order book snapshot" in str(context.exception))

    def test_fetch_order_book_side_exception(self):
        self.data_source._xrpl_client.request.side_effect = TimeoutError

        with self.assertRaises(TimeoutError):
            self.async_run_with_timeout(self.data_source.fetch_order_book_side(self.data_source._xrpl_client, 12345, {}, {}, 50))

    @patch("hummingbot.connector.exchange.xrpl.xrpl_api_order_book_data_source.XRPLAPIOrderBookDataSource._get_client")
    def test_process_websocket_messages_for_pair(self, mock_get_client):
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__ = AsyncMock()
        mock_client.send.return_value = None
        mock_client.__aiter__.return_value = iter(
            [
                {
                    "transaction": {
                        "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",
                        "Fee": "10",
                        "Flags": 786432,
                        "LastLedgerSequence": 88954510,
                        "Memos": [
                            {
                                "Memo": {
                                    "MemoData": "68626F742D313731393430303738313137303331392D42534F585036316263393330633963366139393139386462343432343461383637313231373562313663"  # noqa: mock
                                }
                            }
                        ],
                        "Sequence": 84437780,
                        "SigningPubKey": "ED23BA20D57103E05BA762F0A04FE50878C11BD36B7BF9ADACC3EDBD9E6D320923",  # noqa: mock
                        "TakerGets": "502953",
                        "TakerPays": {
                            "currency": "534F4C4F00000000000000000000000000000000",
                            "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
                            "value": "2.239836701211152",
                        },
                        "TransactionType": "OfferCreate",
                        "TxnSignature": "2E87E743DE37738DCF1EE6C28F299C4FF18BDCB064A07E9068F1E920F8ACA6C62766177E82917ED0995635E636E3BB8B4E2F4DDCB198B0B9185041BEB466FD03 #",  # noqa: mock
                        "hash": "undefined",
                        "ctid": "C54D567C00030000",
                        "meta": "undefined",
                        "validated": "undefined",
                        "date": 772640450,
                        "ledger_index": "undefined",
                        "inLedger": "undefined",
                        "metaData": "undefined",
                        "status": "undefined",
                    },
                    "meta": {
                        "AffectedNodes": [
                            {
                                "ModifiedNode": {
                                    "FinalFields": {
                                        "Account": "rhqTdSsJAaEReRsR27YzddqyGoWTNMhEvC",
                                        "BookDirectory": "5C8970D155D65DB8FF49B291D7EFFA4A09F9E8A68D9974B25A07F01A195F8476",  # noqa: mock
                                        "BookNode": "0",
                                        "Flags": 0,
                                        "OwnerNode": "2",
                                        "Sequence": 71762948,
                                        "TakerGets": {
                                            "currency": "534F4C4F00000000000000000000000000000000",
                                            "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
                                            "value": "42.50531785780174",
                                        },
                                        "TakerPays": "9497047",
                                    },
                                    "LedgerEntryType": "Offer",
                                    "LedgerIndex": "3ABFC9B192B73ECE8FB6E2C46E49B57D4FBC4DE8806B79D913C877C44E73549E",  # noqa: mock
                                    "PreviousFields": {
                                        "TakerGets": {
                                            "currency": "534F4C4F00000000000000000000000000000000",
                                            "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
                                            "value": "44.756352009",
                                        },
                                        "TakerPays": "10000000",
                                    },
                                    "PreviousTxnID": "7398CE2FDA7FF61B52C1039A219D797E526ACCCFEC4C44A9D920ED28B551B539",  # noqa: mock
                                    "PreviousTxnLgrSeq": 88954480,
                                }
                            }
                        ]
                    },
                }
            ]
        )

        mock_get_client.return_value = mock_client

        self.async_run_with_timeout(self.data_source._process_websocket_messages_for_pair("SOLO-XRP"))

        mock_get_client.assert_called_once_with()
        mock_client.send.assert_called_once()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_api_order_book_data_source.XRPLAPIOrderBookDataSource._get_client")
    def test_process_websocket_messages_for_pair_exception(self, mock_get_client):
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__ = None
        mock_client.send.side_effect = Exception("Error")

        mock_get_client.return_value = mock_client

        with self.assertRaises(Exception):
            self.async_run_with_timeout(self.data_source._process_websocket_messages_for_pair("SOLO-XRP"))
