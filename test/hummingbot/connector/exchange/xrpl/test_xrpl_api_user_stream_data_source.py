import asyncio
import unittest
from asyncio import CancelledError
from decimal import Decimal
from typing import Awaitable
from unittest.mock import AsyncMock

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange.xrpl.xrpl_api_user_stream_data_source import XRPLAPIUserStreamDataSource
from hummingbot.connector.exchange.xrpl.xrpl_auth import XRPLAuth
from hummingbot.connector.exchange.xrpl.xrpl_exchange import XrplExchange
from hummingbot.connector.trading_rule import TradingRule


class XRPLUserStreamDataSourceUnitTests(unittest.TestCase):
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
        self.data_source = XRPLAPIUserStreamDataSource(
            auth=XRPLAuth(xrpl_secret_key=""),
            connector=self.connector,
        )
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

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

    def _event_message(self):
        resp = {
            "transaction": {
                "Account": "rE3xcPg7mRTUwS2XKarZgTDimBY8VdfZgh",
                "Amount": "54",
                "Destination": "rJn2zAPdFA193sixJwuFixRkYDUtx3apQh",
                "DestinationTag": 500650668,
                "Fee": "10",
                "Sequence": 88946237,
                "SigningPubKey": "ED9160E36E72C04E65A8F1FB0756B8C1183EDF6E1E1F23AB333352AA2E74261005", # noqa: mock
                "TransactionType": "Payment",
                "TxnSignature": "ED8BC137211720346E2D495541267385963AC2A3CE8BFAA9F35E72E299C6D3F6C7D03BDC90B007B2D9F164A27F4B62F516DDFCFCD5D2844E56D5A335BCCD8E0A", # noqa: mock
                "hash": "B2A73146A25E1FFD2EA80268DF4C0DDF8B6D2DF8B45EB33B1CB96F356873F824", # noqa: mock
                "DeliverMax": "54",
                "date": 772789130,
            },
            "meta": {
                "AffectedNodes": [
                    {
                        "ModifiedNode": {
                            "FinalFields": {
                                "Account": "rJn2zAPdFA193sixJwuFixRkYDUtx3apQh", # noqa: mock
                                "Balance": "4518270821183",
                                "Flags": 131072,
                                "OwnerCount": 1,
                                "Sequence": 115711,
                            },
                            "LedgerEntryType": "AccountRoot",
                            "LedgerIndex": "C19B36F6B6F2EEC9F4E2AF875E533596503F4541DBA570F06B26904FDBBE9C52", # noqa: mock
                            "PreviousFields": {"Balance": "4518270821129"},
                            "PreviousTxnID": "F1C1BAAF756567DB986114034755734E8325127741FF232A551BCF322929AF58", # noqa: mock
                            "PreviousTxnLgrSeq": 88973728,
                        }
                    },
                    {
                        "ModifiedNode": {
                            "FinalFields": {
                                "Account": "rE3xcPg7mRTUwS2XKarZgTDimBY8VdfZgh", # noqa: mock
                                "Balance": "20284095",
                                "Flags": 0,
                                "OwnerCount": 0,
                                "Sequence": 88946238,
                            },
                            "LedgerEntryType": "AccountRoot",
                            "LedgerIndex": "FE4BF634F1E942248603DC4A3FE34A365218FDE7AF9DCA93850518E870E51D74", # noqa: mock
                            "PreviousFields": {"Balance": "20284159", "Sequence": 88946237},
                            "PreviousTxnID": "9A9D303AD39937976F4198EDB53E7C9AE4651F7FB116DFBBBF0B266E6E30EF3C", # noqa: mock
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
            "ledger_hash": "90C78DEECE2DD7FD3271935BD6017668F500CCF0CF42C403F8B86A03F8A902AE", # noqa: mock
            "engine_result_code": 0,
            "engine_result": "tesSUCCESS",
            "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
        }

        return resp

    def test_listen_for_user_stream_with_exception(self):
        self.data_source._xrpl_client.send.return_value = None
        self.data_source._xrpl_client.send.side_effect = CancelledError
        self.data_source._xrpl_client.__aiter__.return_value = iter([self._event_message()])

        with self.assertRaises(CancelledError):
            self.async_run_with_timeout(self.data_source.listen_for_user_stream(asyncio.Queue()), timeout=6)

        self.data_source._xrpl_client.send.assert_called_once()
