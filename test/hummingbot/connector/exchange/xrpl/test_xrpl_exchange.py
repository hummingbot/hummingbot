import asyncio
import unittest
from decimal import Decimal
from typing import Awaitable
from unittest.mock import AsyncMock, patch

from xrpl.models import Response, Transaction
from xrpl.models.response import ResponseStatus
from xrpl.models.transactions.types import TransactionType

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange.xrpl.xrpl_api_order_book_data_source import XRPLAPIOrderBookDataSource
from hummingbot.connector.exchange.xrpl.xrpl_api_user_stream_data_source import XRPLAPIUserStreamDataSource
from hummingbot.connector.exchange.xrpl.xrpl_auth import XRPLAuth
from hummingbot.connector.exchange.xrpl.xrpl_exchange import XrplExchange
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker


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
        self.data_source._request_order_book_snapshot = AsyncMock()
        self.data_source._request_order_book_snapshot.return_value = self._snapshot_response()

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

        self.connector._orderbook_ds = self.data_source
        self.connector._set_order_book_tracker(
            OrderBookTracker(
                data_source=self.connector._orderbook_ds,
                trading_pairs=self.connector.trading_pairs,
                domain=self.connector.domain,
            )
        )

        self.connector.order_book_tracker.start()

        self.user_stream_source = XRPLAPIUserStreamDataSource(
            auth=XRPLAuth(xrpl_secret_key=""),
            connector=self.connector,
        )
        self.user_stream_source.logger().setLevel(1)
        self.user_stream_source.logger().addHandler(self)
        self.user_stream_source._xrpl_client = AsyncMock()
        self.user_stream_source._xrpl_client.__aenter__.return_value = self.data_source._xrpl_client
        self.user_stream_source._xrpl_client.__aexit__.return_value = None

        self.connector._user_stream_tracker = UserStreamTracker(data_source=self.user_stream_source)

        self.connector._xrpl_client = AsyncMock()
        self.connector._xrpl_client.__aenter__.return_value = self.connector._xrpl_client
        self.connector._xrpl_client.__aexit__.return_value = None

        self.connector._xrpl_place_order_client = AsyncMock()
        self.connector._xrpl_place_order_client.__aenter__.return_value = self.connector._xrpl_place_order_client
        self.connector._xrpl_place_order_client.__aexit__.return_value = None

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

    def test_get_new_order_book_successful(self):
        self.async_run_with_timeout(self.connector._orderbook_ds.get_new_order_book(self.trading_pair))
        order_book: OrderBook = self.connector.get_order_book(self.trading_pair)

        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(2, len(bids))
        self.assertEqual(0.2235426870065409, bids[0].price)
        self.assertEqual(836.5292665312212, bids[0].amount)
        self.assertEqual(2, len(asks))
        self.assertEqual(0.22452700389932698, asks[0].price)
        self.assertEqual(91.846106, asks[0].amount)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._verify_transaction_result")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_autofill")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_sign")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_submit")
    @patch("hummingbot.connector.client_order_tracker.ClientOrderTracker.process_order_update")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._make_network_check_request")
    def test_place_order(
        self,
        network_mock,
        process_order_update_mock,
        submit_mock,
        sign_mock,
        autofill_mock,
        verify_transaction_result_mock,
    ):
        autofill_mock.return_value = {}
        verify_transaction_result_mock.return_value = True, {}
        sign_mock.return_value = Transaction(
            sequence=1, last_ledger_sequence=1, account="r1234", transaction_type=TransactionType.OFFER_CREATE
        )

        submit_mock.return_value = Response(
            status=ResponseStatus.SUCCESS, result={"engine_result": "tesSUCCESS", "engine_result_message": "something"}
        )

        self.async_run_with_timeout(
            self.connector._place_order(
                "hbot", self.trading_pair, Decimal("1"), TradeType.BUY, OrderType.LIMIT, Decimal("1")
            )
        )
        self.assertTrue(verify_transaction_result_mock.called)
