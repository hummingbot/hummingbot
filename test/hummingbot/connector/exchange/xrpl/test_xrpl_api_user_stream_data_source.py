import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, AsyncIterable, Dict
from unittest.mock import AsyncMock, Mock

from hummingbot.connector.exchange.xrpl.xrpl_api_user_stream_data_source import XRPLAPIUserStreamDataSource
from hummingbot.connector.exchange.xrpl.xrpl_auth import XRPLAuth
from hummingbot.connector.exchange.xrpl.xrpl_exchange import XrplExchange
from hummingbot.connector.trading_rule import TradingRule


class XRPLUserStreamDataSourceUnitTests(IsolatedAsyncioWrapperTestCase):
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
        self.data_source = XRPLAPIUserStreamDataSource(
            auth=XRPLAuth(xrpl_secret_key=""),
            connector=self.connector,
        )

        self.data_source._sleep = AsyncMock()
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

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
        self.mock_client = AsyncMock()
        self.mock_client.__aenter__.return_value = self.mock_client
        self.mock_client.__aexit__.return_value = None
        self.mock_client.is_open = Mock(return_value=True)
        self.data_source._get_client = AsyncMock(return_value=self.mock_client)

    def tearDown(self) -> None:
        if self.listening_task is not None:
            self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _event_message(self):
        resp = {
            "transaction": {
                "Account": "rE3xcPg7mRTUwS2XKarZgTDimBY8VdfZgh",  # noqa: mock
                "Amount": "54",
                "Destination": "rJn2zAPdFA193sixJwuFixRkYDUtx3apQh",  # noqa: mock
                "DestinationTag": 500650668,
                "Fee": "10",
                "Sequence": 88946237,
                "SigningPubKey": "ED9160E36E72C04E65A8F1FB0756B8C1183EDF6E1E1F23AB333352AA2E74261005",  # noqa: mock
                "TransactionType": "Payment",
                "TxnSignature": "ED8BC137211720346E2D495541267385963AC2A3CE8BFAA9F35E72E299C6D3F6C7D03BDC90B007B2D9F164A27F4B62F516DDFCFCD5D2844E56D5A335BCCD8E0A",  # noqa: mock
                "hash": "B2A73146A25E1FFD2EA80268DF4C0DDF8B6D2DF8B45EB33B1CB96F356873F824",  # noqa: mock
                "DeliverMax": "54",
                "date": 772789130,
            },
            "meta": {
                "AffectedNodes": [
                    {
                        "ModifiedNode": {
                            "FinalFields": {
                                "Account": "rJn2zAPdFA193sixJwuFixRkYDUtx3apQh",  # noqa: mock
                                "Balance": "4518270821183",
                                "Flags": 131072,
                                "OwnerCount": 1,
                                "Sequence": 115711,
                            },
                            "LedgerEntryType": "AccountRoot",
                            "LedgerIndex": "C19B36F6B6F2EEC9F4E2AF875E533596503F4541DBA570F06B26904FDBBE9C52",  # noqa: mock
                            "PreviousFields": {"Balance": "4518270821129"},
                            "PreviousTxnID": "F1C1BAAF756567DB986114034755734E8325127741FF232A551BCF322929AF58",  # noqa: mock
                            "PreviousTxnLgrSeq": 88973728,
                        }
                    },
                    {
                        "ModifiedNode": {
                            "FinalFields": {
                                "Account": "rE3xcPg7mRTUwS2XKarZgTDimBY8VdfZgh",  # noqa: mock
                                "Balance": "20284095",
                                "Flags": 0,
                                "OwnerCount": 0,
                                "Sequence": 88946238,
                            },
                            "LedgerEntryType": "AccountRoot",
                            "LedgerIndex": "FE4BF634F1E942248603DC4A3FE34A365218FDE7AF9DCA93850518E870E51D74",  # noqa: mock
                            "PreviousFields": {"Balance": "20284159", "Sequence": 88946237},
                            "PreviousTxnID": "9A9D303AD39937976F4198EDB53E7C9AE4651F7FB116DFBBBF0B266E6E30EF3C",  # noqa: mock
                            "PreviousTxnLgrSeq": 88973727,
                        }
                    },
                ],
                "TransactionIndex": 22,
                "TransactionResult": "tesSUCCESS",
                "delivered_amount": "54",
            },
            "type": "transaction",
            "validated": True,
            "status": "closed",
            "close_time_iso": "2024-06-27T07:38:50Z",
            "ledger_index": 88973728,
            "ledger_hash": "90C78DEECE2DD7FD3271935BD6017668F500CCF0CF42C403F8B86A03F8A902AE",  # noqa: mock
            "engine_result_code": 0,
            "engine_result": "tesSUCCESS",
            "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
        }

        return resp

    async def test_listen_for_user_stream_with_exception(self):
        self.mock_client.send.return_value = None
        self.mock_client.send.side_effect = asyncio.CancelledError()
        self.mock_client.__aiter__.return_value = iter([self._event_message()])

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_user_stream(asyncio.Queue())

        self.mock_client.send.assert_called_once()

    async def test_balance_changes_handling(self):
        # Setup initial balances
        self.connector._account_balances = {"XRP": Decimal("100"), "SOLO": Decimal("50")}
        self.connector._account_available_balances = {"XRP": Decimal("100"), "SOLO": Decimal("50")}

        # Mock the auth to return our test account
        test_account = "rTestAccount123"
        self.connector._xrpl_auth.get_account = Mock(return_value=test_account)

        # Mock the token symbol lookup
        self.connector.get_token_symbol_from_all_markets = Mock(return_value="SOLO")

        # Create the full message that would come from websocket
        message = {
            "type": "transaction",
            "transaction": {
                "Account": test_account,
                "Fee": "12",
                "Flags": 655360,
                "Sequence": 123,
                "TransactionType": "Payment",
                "hash": "test_hash",
                "ctid": "test_ctid",
            },
            "meta": {
                "AffectedNodes": [
                    {
                        "ModifiedNode": {
                            "FinalFields": {
                                "Account": test_account,
                                "Balance": "110500000",  # 110.5 XRP in drops
                                "Flags": 0,
                                "OwnerCount": 0,
                                "Sequence": 123,
                            },
                            "LedgerEntryType": "AccountRoot",
                            "LedgerIndex": "test_ledger_index",
                            "PreviousFields": {
                                "Balance": "100000000",  # 100 XRP in drops
                            },
                            "PreviousTxnID": "test_prev_txn_id",
                            "PreviousTxnLgrSeq": 12345,
                        }
                    },
                    {
                        "ModifiedNode": {
                            "FinalFields": {
                                "Balance": {
                                    "currency": "534F4C4F00000000000000000000000000000000",
                                    "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",
                                    "value": "55.25",
                                },
                                "Flags": 1114112,
                                "HighLimit": {
                                    "currency": "534F4C4F00000000000000000000000000000000",
                                    "issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
                                    "value": "0",
                                },
                                "HighNode": "783",
                                "LowLimit": {
                                    "currency": "534F4C4F00000000000000000000000000000000",
                                    "issuer": test_account,
                                    "value": "1000000000",
                                },
                                "LowNode": "0",
                            },
                            "LedgerEntryType": "RippleState",
                            "LedgerIndex": "test_ledger_index_2",
                            "PreviousFields": {
                                "Balance": {
                                    "currency": "534F4C4F00000000000000000000000000000000",
                                    "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",
                                    "value": "50",
                                }
                            },
                            "PreviousTxnID": "test_prev_txn_id_2",
                            "PreviousTxnLgrSeq": 12346,
                        }
                    },
                ],
                "TransactionIndex": 12,
                "TransactionResult": "tesSUCCESS",
            },
            "validated": True,
            "date": 802513441,
            "ledger_index": 96621217,
            "inLedger": 96621217,
        }

        # Create a mock iterator that will yield our message
        async def mock_iter_queue() -> AsyncIterable[Dict[str, Any]]:
            yield message

        # Mock the _iter_user_event_queue method
        self.connector._iter_user_event_queue = mock_iter_queue

        # Call the event listener directly
        async for _ in self.connector._iter_user_event_queue():
            await self.connector._user_stream_event_listener()
            break  # We only need to process one message

        # Verify XRP balance updates
        self.assertEqual(self.connector._account_balances["XRP"], Decimal("110.5"))
        self.assertEqual(self.connector._account_available_balances["XRP"], Decimal("110.5"))

        # Verify SOLO balance updates
        self.assertEqual(self.connector._account_balances["SOLO"], Decimal("55.25"))
        self.assertEqual(self.connector._account_available_balances["SOLO"], Decimal("55.25"))

        # Verify the token symbol lookup was called with correct parameters
        self.connector.get_token_symbol_from_all_markets.assert_called_once_with("SOLO", test_account)
