"""
Shared base class and helpers for XRPL exchange test chunks.

This module provides `XRPLExchangeTestBase`, a mixin that sets up a fully
configured `XrplExchange` connector with mock clients, data sources,
trading rules, and fee rules.  All chunk test files inherit from this
mixin together with `IsolatedAsyncioTestCase`.
"""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock

from xrpl.models import Response
from xrpl.models.response import ResponseStatus, ResponseType

from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange.xrpl.xrpl_api_order_book_data_source import XRPLAPIOrderBookDataSource
from hummingbot.connector.exchange.xrpl.xrpl_api_user_stream_data_source import XRPLAPIUserStreamDataSource
from hummingbot.connector.exchange.xrpl.xrpl_auth import XRPLAuth
from hummingbot.connector.exchange.xrpl.xrpl_exchange import XrplExchange
from hummingbot.connector.exchange.xrpl.xrpl_worker_pool import TransactionSubmitResult, TransactionVerifyResult
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker


class XRPLExchangeTestBase:
    """
    Mixin providing shared setUp / tearDown and mock helpers for all
    XRPL exchange test chunk files.

    Usage::

        class TestSomething(XRPLExchangeTestBase, IsolatedAsyncioTestCase):
            ...
    """

    # ------------------------------------------------------------------ #
    # Class-level constants
    # ------------------------------------------------------------------ #
    base_asset = "SOLO"
    quote_asset = "XRP"
    trading_pair = f"{base_asset}-{quote_asset}"
    trading_pair_usd = f"{base_asset}-USD"

    # ------------------------------------------------------------------ #
    # setUp / tearDown
    # ------------------------------------------------------------------ #

    def setUp(self) -> None:
        super().setUp()  # type: ignore[misc]
        self.log_records: list = []
        self.listening_task = None

        self.connector = XrplExchange(
            xrpl_secret_key="",
            wss_node_urls=["wss://sample.com"],
            max_request_per_minute=100,
            trading_pairs=[self.trading_pair, self.trading_pair_usd],
            trading_required=False,
        )

        self.connector._sleep = AsyncMock()

        self.data_source = XRPLAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair, self.trading_pair_usd],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
        )

        self.data_source._sleep = AsyncMock()
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

        trading_rule_usd = TradingRule(
            trading_pair=self.trading_pair_usd,
            min_order_size=Decimal("1e-6"),
            min_price_increment=Decimal("1e-6"),
            min_quote_amount_increment=Decimal("1e-6"),
            min_base_amount_increment=Decimal("1e-6"),
            min_notional_size=Decimal("1e-6"),
        )

        self.connector._trading_rules[self.trading_pair] = trading_rule
        self.connector._trading_rules[self.trading_pair_usd] = trading_rule_usd

        trading_rules_info = {
            self.trading_pair: {"base_transfer_rate": 0.01, "quote_transfer_rate": 0.01},
            self.trading_pair_usd: {"base_transfer_rate": 0.01, "quote_transfer_rate": 0.01},
        }
        trading_pair_fee_rules = self.connector._format_trading_pair_fee_rules(trading_rules_info)

        for trading_pair_fee_rule in trading_pair_fee_rules:
            self.connector._trading_pair_fee_rules[trading_pair_fee_rule["trading_pair"]] = trading_pair_fee_rule

        self.mock_client = AsyncMock()
        self.mock_client.__aenter__.return_value = self.mock_client
        self.mock_client.__aexit__.return_value = None
        self.mock_client.request = AsyncMock()
        self.mock_client.close = AsyncMock()
        self.mock_client.open = AsyncMock()
        self.mock_client.url = "wss://sample.com"
        self.mock_client.is_open = Mock(return_value=True)

        self.data_source._get_client = AsyncMock(return_value=self.mock_client)

        self.connector._orderbook_ds = self.data_source
        self.connector._set_order_book_tracker(
            OrderBookTracker(
                data_source=self.connector._orderbook_ds,
                trading_pairs=self.connector.trading_pairs,
                domain=self.connector.domain,
            )
        )

        # Mock subscription connection to prevent network connections
        self.data_source._create_subscription_connection = AsyncMock(return_value=None)

        self.user_stream_source = XRPLAPIUserStreamDataSource(
            auth=XRPLAuth(xrpl_secret_key=""),
            connector=self.connector,
        )
        self.user_stream_source.logger().setLevel(1)
        self.user_stream_source.logger().addHandler(self)
        self.user_stream_source._get_client = AsyncMock(return_value=self.mock_client)

        self.connector._user_stream_tracker = UserStreamTracker(data_source=self.user_stream_source)

        self.connector._get_async_client = AsyncMock(return_value=self.mock_client)

        self.connector._lock_delay_seconds = 0

    def tearDown(self) -> None:
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
        # Stop the order book tracker to cancel background tasks
        if hasattr(self, "connector") and self.connector.order_book_tracker is not None:
            self.connector.order_book_tracker.stop()
        super().tearDown()  # type: ignore[misc]

    # ------------------------------------------------------------------ #
    # Logging helper (acts as a logging handler)
    # ------------------------------------------------------------------ #

    level = 0  # Required by Python logging when the test acts as a handler

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    # ------------------------------------------------------------------ #
    # New shared mock helpers (for worker-pool-based architecture)
    # ------------------------------------------------------------------ #

    def _mock_query_xrpl(self, side_effect=None):
        """
        Install a mock ``_query_xrpl`` on ``self.connector``.

        If *side_effect* is ``None`` a default dispatcher that routes by
        ``RequestMethod`` is installed.  Override by passing your own
        async callable / side-effect list.
        """
        if side_effect is None:
            from xrpl.models.requests.request import RequestMethod

            async def _default_dispatch(request, priority=None, timeout=None):
                if hasattr(request, "method"):
                    if request.method == RequestMethod.ACCOUNT_INFO:
                        return self._client_response_account_info()
                    elif request.method == RequestMethod.ACCOUNT_LINES:
                        return self._client_response_account_lines()
                    elif request.method == RequestMethod.ACCOUNT_OBJECTS:
                        return self._client_response_account_objects()
                raise ValueError(f"Unexpected request: {request}")

            side_effect = _default_dispatch

        self.connector._query_xrpl = AsyncMock(side_effect=side_effect)
        return self.connector._query_xrpl

    def _mock_tx_pool(
        self,
        success: bool = True,
        sequence: int = 12345,
        last_ledger_sequence: int = 67890,
        prelim_result: str = "tesSUCCESS",
        exchange_order_id: str = "12345-67890-ABCDEF",
        tx_hash: str = "ABCDEF1234567890",
    ):
        """
        Install a mock ``_tx_pool`` on ``self.connector`` that returns
        a ``TransactionSubmitResult``.
        """
        signed_tx = MagicMock()
        signed_tx.sequence = sequence
        signed_tx.last_ledger_sequence = last_ledger_sequence

        result = TransactionSubmitResult(
            success=success,
            signed_tx=signed_tx,
            response=Response(
                status=ResponseStatus.SUCCESS if success else ResponseStatus.ERROR,
                result={"engine_result": prelim_result},
            ),
            prelim_result=prelim_result,
            exchange_order_id=exchange_order_id,
            tx_hash=tx_hash,
        )

        mock_pool = MagicMock()
        mock_pool.submit_transaction = AsyncMock(return_value=result)
        self.connector._tx_pool = mock_pool
        return mock_pool

    def _mock_verification_pool(
        self,
        verified: bool = True,
        final_result: str = "tesSUCCESS",
    ):
        """
        Install a mock ``_verification_pool`` on ``self.connector`` that
        returns a ``TransactionVerifyResult``.
        """
        result = TransactionVerifyResult(
            verified=verified,
            response=Response(
                status=ResponseStatus.SUCCESS if verified else ResponseStatus.ERROR,
                result={},
            ),
            final_result=final_result,
        )

        mock_pool = MagicMock()
        mock_pool.submit_verification = AsyncMock(return_value=result)
        self.connector._verification_pool = mock_pool
        return mock_pool

    # ------------------------------------------------------------------ #
    # Response generators (copied from original monolith)
    # ------------------------------------------------------------------ #

    def _trade_update_event(self):
        trade_data = {
            "trade_type": float(TradeType.SELL.value),
            "trade_id": "example_trade_id",
            "update_id": 123456789,
            "price": Decimal("0.001"),
            "amount": Decimal("1"),
            "timestamp": 123456789,
        }
        return {"trading_pair": self.trading_pair, "trades": trade_data}

    def _snapshot_response(self):
        return {
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
                    "Account": "rsoLoDTcxn9wCEHHBR7enMhzQMThkB2w28",  # noqa: mock
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
                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                        "value": "402.6077034840102",
                    },
                    "index": "4D31D069F1E2B0F2016DA0F1BF232411CB1B4642A49538CD6BB989F353D52411",  # noqa: mock
                    "owner_funds": "827169016",
                    "quality": "0.000004473418927600114",
                },
            ],
            "trading_pair": "SOLO-XRP",
        }

    def _client_response_account_info(self):
        return Response(
            status=ResponseStatus.SUCCESS,
            result={
                "account_data": {
                    "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                    "Balance": "57030864",
                    "Flags": 0,
                    "LedgerEntryType": "AccountRoot",
                    "OwnerCount": 3,
                    "PreviousTxnID": "0E8031892E910EB8F19537610C36E5816D5BABF14C91CF8C73FFE5F5D6A0623E",  # noqa: mock
                    "PreviousTxnLgrSeq": 88981167,
                    "Sequence": 84437907,
                    "index": "2B3020738E7A44FBDE454935A38D77F12DC5A11E0FA6DAE2D9FCF4719FFAA3BC",  # noqa: mock
                },
                "account_flags": {
                    "allowTrustLineClawback": False,
                    "defaultRipple": False,
                    "depositAuth": False,
                    "disableMasterKey": False,
                    "disallowIncomingCheck": False,
                    "disallowIncomingNFTokenOffer": False,
                    "disallowIncomingPayChan": False,
                    "disallowIncomingTrustline": False,
                    "disallowIncomingXRP": False,
                    "globalFreeze": False,
                    "noFreeze": False,
                    "passwordSpent": False,
                    "requireAuthorization": False,
                    "requireDestinationTag": False,
                },
                "ledger_hash": "DFDFA9B7226B8AC1FD909BB9C2EEBDBADF4C37E2C3E283DB02C648B2DC90318C",  # noqa: mock
                "ledger_index": 89003974,
                "validated": True,
            },
            id="account_info_644216",
            type=ResponseType.RESPONSE,
        )

    def _client_response_account_empty_lines(self):
        return Response(
            status=ResponseStatus.SUCCESS,
            result={
                "account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                "ledger_hash": "6626B7AC7E184B86EE29D8B9459E0BC0A56E12C8DA30AE747051909CF16136D3",  # noqa: mock
                "ledger_index": 89692233,
                "validated": True,
                "limit": 200,
                "lines": [],
            },
            id="account_lines_144811",
            type=ResponseType.RESPONSE,
        )

    def _client_response_account_lines(self):
        return Response(
            status=ResponseStatus.SUCCESS,
            result={
                "account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                "ledger_hash": "6626B7AC7E184B86EE29D8B9459E0BC0A56E12C8DA30AE747051909CF16136D3",  # noqa: mock
                "ledger_index": 89692233,
                "validated": True,
                "limit": 200,
                "lines": [
                    {
                        "account": "rvYAfWj5gh67oV6fW32ZzP3Aw4Eubs59B",  # noqa: mock
                        "balance": "0.9957725256649131",
                        "currency": "USD",
                        "limit": "0",
                        "limit_peer": "0",
                        "quality_in": 0,
                        "quality_out": 0,
                        "no_ripple": True,
                        "no_ripple_peer": False,
                    },
                    {
                        "account": "rcEGREd8NmkKRE8GE424sksyt1tJVFZwu",  # noqa: mock
                        "balance": "2.981957518895808",
                        "currency": "5553444300000000000000000000000000000000",  # noqa: mock
                        "limit": "0",
                        "limit_peer": "0",
                        "quality_in": 0,
                        "quality_out": 0,
                        "no_ripple": True,
                        "no_ripple_peer": False,
                    },
                    {
                        "account": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",  # noqa: mock
                        "balance": "0.011094399237562",
                        "currency": "USD",
                        "limit": "0",
                        "limit_peer": "0",
                        "quality_in": 0,
                        "quality_out": 0,
                        "no_ripple": True,
                        "no_ripple_peer": False,
                    },
                    {
                        "account": "rpakCr61Q92abPXJnVboKENmpKssWyHpwu",  # noqa: mock
                        "balance": "104.9021857197376",
                        "currency": "457175696C69627269756D000000000000000000",  # noqa: mock
                        "limit": "0",
                        "limit_peer": "0",
                        "quality_in": 0,
                        "quality_out": 0,
                        "no_ripple": True,
                        "no_ripple_peer": False,
                    },
                    {
                        "account": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                        "balance": "35.95165691730148",
                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                        "limit": "1000000000",
                        "limit_peer": "0",
                        "quality_in": 0,
                        "quality_out": 0,
                        "no_ripple": True,
                        "no_ripple_peer": False,
                    },
                ],
            },
            id="account_lines_144811",
            type=ResponseType.RESPONSE,
        )

    def _client_response_account_empty_objects(self):
        return Response(
            status=ResponseStatus.SUCCESS,
            result={
                "account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                "ledger_hash": "6626B7AC7E184B86EE29D8B9459E0BC0A56E12C8DA30AE747051909CF16136D3",  # noqa: mock
                "ledger_index": 89692233,
                "validated": True,
                "limit": 200,
                "account_objects": [],
            },
            id="account_objects_144811",
            type=ResponseType.RESPONSE,
        )

    def _client_response_account_objects(self):
        return Response(
            status=ResponseStatus.SUCCESS,
            result={
                "account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                "account_objects": [
                    {
                        "Balance": {
                            "currency": "5553444300000000000000000000000000000000",  # noqa: mock
                            "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",  # noqa: mock
                            "value": "2.981957518895808",
                        },
                        "Flags": 1114112,
                        "HighLimit": {
                            "currency": "5553444300000000000000000000000000000000",  # noqa: mock
                            "issuer": "rcEGREd8NmkKRE8GE424sksyt1tJVFZwu",  # noqa: mock
                            "value": "0",
                        },
                        "HighNode": "f9",
                        "LedgerEntryType": "RippleState",
                        "LowLimit": {
                            "currency": "5553444300000000000000000000000000000000",  # noqa: mock
                            "issuer": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                            "value": "0",
                        },
                        "LowNode": "0",
                        "PreviousTxnID": "C6EFE5E21ABD5F457BFCCE6D5393317B90821F443AD41FF193620E5980A52E71",  # noqa: mock
                        "PreviousTxnLgrSeq": 86277627,
                        "index": "55049B8164998B0566FC5CDB3FC7162280EFE5A84DB9333312D3DFF98AB52380",  # noqa: mock
                    },
                    {
                        "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                        "BookDirectory": "C73FAC6C294EBA5B9E22A8237AAE80725E85372510A6CA794F10652F287D59AD",  # noqa: mock
                        "BookNode": "0",
                        "Flags": 131072,
                        "LedgerEntryType": "Offer",
                        "OwnerNode": "0",
                        "PreviousTxnID": "44038CD94CDD0A6FD7912F788FA5FBC575A3C44948E31F4C21B8BC3AA0C2B643",  # noqa: mock
                        "PreviousTxnLgrSeq": 89078756,
                        "Sequence": 84439998,
                        "TakerGets": "499998",
                        "taker_gets_funded": "299998",
                        "TakerPays": {
                            "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                            "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                            "value": "2.307417192565501",
                        },
                        "index": "BE4ACB6610B39F2A9CD1323F63D479177917C02AA8AF2122C018D34AAB6F4A35",  # noqa: mock
                    },
                    {
                        "Balance": {
                            "currency": "USD",
                            "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",  # noqa: mock
                            "value": "0.011094399237562",
                        },
                        "Flags": 1114112,
                        "HighLimit": {
                            "currency": "USD",
                            "issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
                            "value": "0",
                        },
                        "HighNode": "22d3",
                        "LedgerEntryType": "RippleState",
                        "LowLimit": {
                            "currency": "USD",
                            "issuer": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",
                            "value": "0",
                        },
                        "LowNode": "0",
                        "PreviousTxnID": "1A9E685EA694157050803B76251C0A6AFFCF1E69F883BF511CF7A85C3AC002B8",  # noqa: mock
                        "PreviousTxnLgrSeq": 85648064,
                        "index": "C510DDAEBFCE83469032E78B9F41D352DABEE2FB454E6982AA5F9D4ECC4D56AA",  # noqa: mock
                    },
                    {
                        "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                        "BookDirectory": "C73FAC6C294EBA5B9E22A8237AAE80725E85372510A6CA794F10659A9DE833CA",  # noqa: mock
                        "BookNode": "0",
                        "Flags": 131072,
                        "LedgerEntryType": "Offer",
                        "OwnerNode": "0",
                        "PreviousTxnID": "262201134A376F2E888173680EDC4E30E2C07A6FA94A8C16603EB12A776CBC66",  # noqa: mock
                        "PreviousTxnLgrSeq": 89078756,
                        "Sequence": 84439997,
                        "TakerGets": "499998",
                        "TakerPays": {
                            "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                            "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                            "value": "2.307647957361237",
                        },
                        "index": "D6F2B37690FA7540B7640ACC61AA2641A6E803DAF9E46CC802884FA5E1BF424E",  # noqa: mock
                    },
                    {
                        "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                        "BookDirectory": "5C8970D155D65DB8FF49B291D7EFFA4A09F9E8A68D9974B25A07B39757FA194D",  # noqa: mock
                        "BookNode": "0",
                        "Flags": 131072,
                        "LedgerEntryType": "Offer",
                        "OwnerNode": "0",
                        "PreviousTxnID": "254F74BF0E5A2098DDE998609F4E8697CCF6A7FD61D93D76057467366A18DA24",  # noqa: mock
                        "PreviousTxnLgrSeq": 89078757,
                        "Sequence": 84440000,
                        "TakerGets": {
                            "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                            "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                            "value": "2.30649459472761",
                        },
                        "taker_gets_funded": {
                            "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                            "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                            "value": "1.30649459472761",
                        },
                        "TakerPays": "499999",
                        "index": "D8F57C7C230FA5DE98E8FEB6B75783693BDECAD1266A80538692C90138E7BADE",  # noqa: mock
                    },
                    {
                        "Balance": {
                            "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                            "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",  # noqa: mock
                            "value": "47.21480375660969",
                        },
                        "Flags": 1114112,
                        "HighLimit": {
                            "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                            "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                            "value": "0",
                        },
                        "HighNode": "3799",
                        "LedgerEntryType": "RippleState",
                        "LowLimit": {
                            "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                            "issuer": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                            "value": "1000000000",
                        },
                        "LowNode": "0",
                        "PreviousTxnID": "E1260EC17725167D0407F73F6B73D7DAF1E3037249B54FC37F2E8B836703AB95",  # noqa: mock
                        "PreviousTxnLgrSeq": 89077268,
                        "index": "E1C84325F137AD05CB78F59968054BCBFD43CB4E70F7591B6C3C1D1C7E44C6FC",  # noqa: mock
                    },
                    {
                        "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                        "BookDirectory": "5C8970D155D65DB8FF49B291D7EFFA4A09F9E8A68D9974B25A07B2FFFC6A7DA8",  # noqa: mock
                        "BookNode": "0",
                        "Flags": 131072,
                        "LedgerEntryType": "Offer",
                        "OwnerNode": "0",
                        "PreviousTxnID": "819FF36C6F44F3F858B25580F1E3A900F56DCC59F2398626DB35796AF9E47E7A",  # noqa: mock
                        "PreviousTxnLgrSeq": 89078756,
                        "Sequence": 84439999,
                        "TakerGets": {
                            "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                            "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                            "value": "2.307186473918109",
                        },
                        "TakerPays": "499999",
                        "index": "ECF76E93DBD7923D0B352A7719E5F9BBF6A43D5BA80173495B0403C646184301",  # noqa: mock
                    },
                ],
                "ledger_hash": "5A76A3A3D115DBC7CE0E4D9868D1EA15F593C8D74FCDF1C0153ED003B5621671",  # noqa: mock
                "ledger_index": 89078774,
                "limit": 200,
                "validated": True,
            },
            id="account_objects_144811",
            type=ResponseType.RESPONSE,
        )

    def _client_response_account_info_issuer(self):
        return Response(
            status=ResponseStatus.SUCCESS,
            result={
                "account_data": {
                    "Account": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                    "Balance": "7329544278",
                    "Domain": "736F6C6F67656E69632E636F6D",  # noqa: mock
                    "EmailHash": "7AC3878BF42A5329698F468A6AAA03B9",  # noqa: mock
                    "Flags": 12058624,
                    "LedgerEntryType": "AccountRoot",
                    "OwnerCount": 0,
                    "PreviousTxnID": "C35579B384BE5DBE064B4778C4EDD18E1388C2CAA2C87BA5122C467265FC7A79",  # noqa: mock
                    "PreviousTxnLgrSeq": 89004092,
                    "RegularKey": "rrrrrrrrrrrrrrrrrrrrBZbvji",
                    "Sequence": 14,
                    "TransferRate": 1000100000,
                    "index": "ED3EE6FAB9822943809FBCBEEC44F418D76292A355B38C1224A378AEB3A65D6D",  # noqa: mock
                    "urlgravatar": "http://www.gravatar.com/avatar/7ac3878bf42a5329698f468a6aaa03b9",  # noqa: mock
                },
                "account_flags": {
                    "allowTrustLineClawback": False,
                    "defaultRipple": True,
                    "depositAuth": False,
                    "disableMasterKey": True,
                    "disallowIncomingCheck": False,
                    "disallowIncomingNFTokenOffer": False,
                    "disallowIncomingPayChan": False,
                    "disallowIncomingTrustline": False,
                    "disallowIncomingXRP": True,
                    "globalFreeze": False,
                    "noFreeze": True,
                    "passwordSpent": False,
                    "requireAuthorization": False,
                    "requireDestinationTag": False,
                },
                "ledger_hash": "AE78A574FCD1B45135785AC9FB64E7E0E6E4159821EF0BB8A59330C1B0E047C9",  # noqa: mock
                "ledger_index": 89004663,
                "validated": True,
            },
            id="account_info_73967",
            type=ResponseType.RESPONSE,
        )

    def _client_response_amm_info(self):
        return Response(
            status=ResponseStatus.SUCCESS,
            result={
                "amm": {
                    "account": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
                    "amount": "268924465",
                    "amount2": {
                        "currency": "534F4C4F00000000000000000000000000000000",
                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
                        "value": "23.4649097465469",
                    },
                    "asset2_frozen": False,
                    "auction_slot": {
                        "account": "rPpvF7eVkV716EuRmCVWRWC1CVFAqLdn3t",
                        "discounted_fee": 50,
                        "expiration": "2024-12-30T14:03:02+0000",
                        "price": {
                            "currency": "039C99CD9AB0B70B32ECDA51EAAE471625608EA2",
                            "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
                            "value": "32.4296376304",
                        },
                        "time_interval": 20,
                    },
                    "lp_token": {
                        "currency": "039C99CD9AB0B70B32ECDA51EAAE471625608EA2",
                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
                        "value": "79170.1044740602",
                    },
                    "trading_fee": 500,
                    "vote_slots": [
                        {
                            "account": "r4rtnJpA2ZzMK4Ncsy6TnR9PQX4N9Vigof",
                            "trading_fee": 500,
                            "vote_weight": 100000,
                        },
                    ],
                },
                "ledger_current_index": 7442853,
                "validated": False,
            },
            id="amm_info_1234",
            type=ResponseType.RESPONSE,
        )

    def _client_response_account_info_issuer_error(self):
        return Response(
            status=ResponseStatus.ERROR,
            result={},
            id="account_info_73967",
            type=ResponseType.RESPONSE,
        )
