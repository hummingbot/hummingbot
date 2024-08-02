import asyncio
import time
import unittest
from decimal import Decimal
from typing import Awaitable
from unittest.mock import AsyncMock, MagicMock, patch

from xrpl.asyncio.clients import XRPLRequestFailureException
from xrpl.models import OfferCancel, Request, Response, Transaction
from xrpl.models.requests.request import RequestMethod
from xrpl.models.response import ResponseStatus, ResponseType
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
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate
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
        cls.trading_pair_usd = f"{cls.base_asset}-USD"

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
            trading_pairs=[self.trading_pair, self.trading_pair_usd],
            trading_required=False,
        )
        self.data_source = XRPLAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair, self.trading_pair_usd],
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

        self.connector._xrpl_query_client = AsyncMock()
        self.connector._xrpl_query_client.__aenter__.return_value = self.connector._xrpl_query_client
        self.connector._xrpl_query_client.__aexit__.return_value = None

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

        return resp

    # noqa: mock
    def _event_message(self):
        resp = {
            "transaction": {
                "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
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
                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                    "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                    "value": "2.239836701211152",
                },
                "TransactionType": "OfferCreate",
                "TxnSignature": "2E87E743DE37738DCF1EE6C28F299C4FF18BDCB064A07E9068F1E920F8ACA6C62766177E82917ED0995635E636E3BB8B4E2F4DDCB198B0B9185041BEB466FD03",  # noqa: mock
                "hash": "undefined",
                "ctid": "C54D567C00030000",  # noqa: mock
                "meta": "undefined",
                "validated": "undefined",
                "date": 772789130,
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
                                "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                "Balance": "56148988",
                                "Flags": 0,
                                "OwnerCount": 3,
                                "Sequence": 84437781,
                            },
                            "LedgerEntryType": "AccountRoot",
                            "LedgerIndex": "2B3020738E7A44FBDE454935A38D77F12DC5A11E0FA6DAE2D9FCF4719FFAA3BC",  # noqa: mock
                            "PreviousFields": {"Balance": "56651951", "Sequence": 84437780},
                            "PreviousTxnID": "BCBB6593A916EDBCC84400948B0525BE7E972B893111FE1C89A7519F8A5ACB2B",  # noqa: mock
                            "PreviousTxnLgrSeq": 88954461,
                        }
                    },
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
                            "LedgerIndex": "3ABFC9B192B73ECE8FB6E2C46E49B57D4FBC4DE8806B79D913C877C44E73549E",  # noqa: mock
                            "PreviousFields": {
                                "TakerGets": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                    "value": "44.756352009",
                                },
                                "TakerPays": "10000000",
                            },
                            "PreviousTxnID": "7398CE2FDA7FF61B52C1039A219D797E526ACCCFEC4C44A9D920ED28B551B539",  # noqa: mock
                            "PreviousTxnLgrSeq": 88954480,
                        }
                    },
                    {
                        "ModifiedNode": {
                            "FinalFields": {
                                "Account": "rhqTdSsJAaEReRsR27YzddqyGoWTNMhEvC",  # noqa: mock
                                "Balance": "251504663",
                                "Flags": 0,
                                "OwnerCount": 30,
                                "Sequence": 71762949,
                            },
                            "LedgerEntryType": "AccountRoot",
                            "LedgerIndex": "4F7BC1BE763E253402D0CA5E58E7003D326BEA2FEB5C0FEE228660F795466F6E",  # noqa: mock
                            "PreviousFields": {"Balance": "251001710"},
                            "PreviousTxnID": "7398CE2FDA7FF61B52C1039A219D797E526ACCCFEC4C44A9D920ED28B551B539",  # noqa: mock
                            "PreviousTxnLgrSeq": 88954480,
                        }
                    },
                    {
                        "ModifiedNode": {
                            "FinalFields": {
                                "Balance": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",  # noqa: mock
                                    "value": "-195.4313653751863",
                                },
                                "Flags": 2228224,
                                "HighLimit": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rhqTdSsJAaEReRsR27YzddqyGoWTNMhEvC",  # noqa: mock
                                    "value": "399134226.5095641",
                                },
                                "HighNode": "0",
                                "LowLimit": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                    "value": "0",
                                },
                                "LowNode": "36a5",
                            },
                            "LedgerEntryType": "RippleState",
                            "LedgerIndex": "9DB660A1BF3B982E5A8F4BE0BD4684FEFEBE575741928E67E4EA1DAEA02CA5A6",  # noqa: mock
                            "PreviousFields": {
                                "Balance": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",  # noqa: mock
                                    "value": "-197.6826246297997",
                                }
                            },
                            "PreviousTxnID": "BCBB6593A916EDBCC84400948B0525BE7E972B893111FE1C89A7519F8A5ACB2B",  # noqa: mock
                            "PreviousTxnLgrSeq": 88954461,
                        }
                    },
                    {
                        "ModifiedNode": {
                            "FinalFields": {
                                "Balance": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",  # noqa: mock
                                    "value": "45.47502732568766",
                                },
                                "Flags": 1114112,
                                "HighLimit": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                    "value": "0",
                                },
                                "HighNode": "3799",
                                "LowLimit": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                    "value": "1000000000",
                                },
                                "LowNode": "0",
                            },
                            "LedgerEntryType": "RippleState",
                            "LedgerIndex": "E1C84325F137AD05CB78F59968054BCBFD43CB4E70F7591B6C3C1D1C7E44C6FC",  # noqa: mock
                            "PreviousFields": {
                                "Balance": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",  # noqa: mock
                                    "value": "43.2239931744894",
                                }
                            },
                            "PreviousTxnID": "BCBB6593A916EDBCC84400948B0525BE7E972B893111FE1C89A7519F8A5ACB2B",  # noqa: mock
                            "PreviousTxnLgrSeq": 88954461,
                        }
                    },
                ],
                "TransactionIndex": 3,
                "TransactionResult": "tesSUCCESS",
            },
            "hash": "86440061A351FF77F21A24ED045EE958F6256697F2628C3555AEBF29A887518C",  # noqa: mock
            "ledger_index": 88954492,
            "date": 772789130,
        }

        return resp

    def _event_message_limit_order_partially_filled(self):
        resp = {
            "transaction": {
                "Account": "rapido5rxPmP4YkMZZEeXSHqWefxHEkqv6",  # noqa: mock
                "Fee": "10",
                "Flags": 655360,
                "LastLedgerSequence": 88981161,
                "Memos": [
                    {
                        "Memo": {
                            "MemoData": "06574D47B3D98F0D1103815555734BF30D72EC4805086B873FCCD69082FE00903FF7AC1910CF172A3FD5554FBDAD75193FF00068DB8BAC71"  # noqa: mock
                        }
                    }
                ],
                "Sequence": 2368849,
                "SigningPubKey": "EDE30BA017ED458B9B372295863B042C2BA8F11AD53B4BDFB398E778CB7679146B",  # noqa: mock
                "TakerGets": {
                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                    "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                    "value": "1.479368155160602",
                },
                "TakerPays": "333",
                "TransactionType": "OfferCreate",
                "TxnSignature": "1165D0B39A5C3C48B65FD20DDF1C0AF544B1413C8B35E6147026F521A8468FB7F8AA3EAA33582A9D8DC9B56E1ED59F6945781118EC4DEC92FF639C3D41C3B402",  # noqa: mock
                "hash": "undefined",
                "ctid": "C54DBEA8001D0000",  # noqa: mock
                "meta": "undefined",
                "validated": "undefined",
                "date": 772789130,
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
                                "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                "Balance": "57030924",
                                "Flags": 0,
                                "OwnerCount": 9,
                                "Sequence": 84437901,
                            },
                            "LedgerEntryType": "AccountRoot",
                            "LedgerIndex": "2B3020738E7A44FBDE454935A38D77F12DC5A11E0FA6DAE2D9FCF4719FFAA3BC",  # noqa: mock
                            "PreviousFields": {"Balance": "57364223"},
                            "PreviousTxnID": "1D63D9DFACB8F25ADAF44A1976FBEAF875EF199DEA6F9502B1C6C32ABA8583F6",  # noqa: mock
                            "PreviousTxnLgrSeq": 88981158,
                        }
                    },
                    {
                        "ModifiedNode": {
                            "FinalFields": {
                                "Account": "rapido5rxPmP4YkMZZEeXSHqWefxHEkqv6",  # noqa: mock
                                "AccountTxnID": "602B32630738581F2618849B3338401D381139F8458DDF2D0AC9B61BEED99D70",  # noqa: mock
                                "Balance": "4802538039",
                                "Flags": 0,
                                "OwnerCount": 229,
                                "Sequence": 2368850,
                            },
                            "LedgerEntryType": "AccountRoot",
                            "LedgerIndex": "BFF40FB02870A44349BB5E482CD2A4AA3415C7E72F4D2E9E98129972F26DA9AA",  # noqa: mock
                            "PreviousFields": {
                                "AccountTxnID": "43B7820240604D3AFE46079D91D557259091DDAC17D42CD7688637D58C3B7927",  # noqa: mock
                                "Balance": "4802204750",
                                "Sequence": 2368849,
                            },
                            "PreviousTxnID": "43B7820240604D3AFE46079D91D557259091DDAC17D42CD7688637D58C3B7927",  # noqa: mock
                            "PreviousTxnLgrSeq": 88981160,
                        }
                    },
                    {
                        "ModifiedNode": {
                            "FinalFields": {
                                "Balance": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",  # noqa: mock
                                    "value": "41.49115329259071",
                                },
                                "Flags": 1114112,
                                "HighLimit": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                    "value": "0",
                                },
                                "HighNode": "3799",
                                "LowLimit": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                    "value": "1000000000",
                                },
                                "LowNode": "0",
                            },
                            "LedgerEntryType": "RippleState",
                            "LedgerIndex": "E1C84325F137AD05CB78F59968054BCBFD43CB4E70F7591B6C3C1D1C7E44C6FC",  # noqa: mock
                            "PreviousFields": {
                                "Balance": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",  # noqa: mock
                                    "value": "40.01178513743011",
                                }
                            },
                            "PreviousTxnID": "EA21F8D1CD22FA64C98CB775855F53C186BF0AD24D59728AA8D18340DDAA3C57",  # noqa: mock
                            "PreviousTxnLgrSeq": 88981118,
                        }
                    },
                    {
                        "ModifiedNode": {
                            "FinalFields": {
                                "Balance": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",  # noqa: mock
                                    "value": "-5.28497026524528",
                                },
                                "Flags": 2228224,
                                "HighLimit": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rapido5rxPmP4YkMZZEeXSHqWefxHEkqv6",  # noqa: mock
                                    "value": "0",
                                },
                                "HighNode": "18",
                                "LowLimit": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                    "value": "0",
                                },
                                "LowNode": "387f",
                            },
                            "LedgerEntryType": "RippleState",
                            "LedgerIndex": "E56AB275B511ECDF6E9C9D8BE9404F3FECBE5C841770584036FF8A832AF3F3B9",  # noqa: mock
                            "PreviousFields": {
                                "Balance": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",  # noqa: mock
                                    "value": "-6.764486357221399",
                                }
                            },
                            "PreviousTxnID": "43B7820240604D3AFE46079D91D557259091DDAC17D42CD7688637D58C3B7927",  # noqa: mock
                            "PreviousTxnLgrSeq": 88981160,
                        }
                    },
                    {
                        "ModifiedNode": {
                            "FinalFields": {
                                "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                "BookDirectory": "C73FAC6C294EBA5B9E22A8237AAE80725E85372510A6CA794F0FC4DA2F8AAF5B",  # noqa: mock
                                "BookNode": "0",
                                "Flags": 131072,
                                "OwnerNode": "0",
                                "Sequence": 84437895,
                                "TakerGets": "33",
                                "TakerPays": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                    "value": "0.000147936815515",
                                },
                            },
                            "LedgerEntryType": "Offer",
                            "LedgerIndex": "F91EFE46023BA559CEF49B670052F19189C8B6422A93FA26D35F2D6A25290D24",  # noqa: mock
                            "PreviousFields": {
                                "TakerGets": "333332",
                                "TakerPays": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                    "value": "1.479516091976118",
                                },
                            },
                            "PreviousTxnID": "12A2F4A0FAA21802E68F4BF78BCA3DE302222B0B9FB938C355EE10E931C151D2",  # noqa: mock
                            "PreviousTxnLgrSeq": 88981157,
                        }
                    },
                ],
                "TransactionIndex": 29,
                "TransactionResult": "tesSUCCESS",
            },
            "hash": "602B32630738581F2618849B3338401D381139F8458DDF2D0AC9B61BEED99D70",  # noqa: mock
            "ledger_index": 88981160,
            "date": 772789130,
        }

        return resp

    def _client_response_account_info(self):
        resp = Response(
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

        return resp

    def _client_response_account_lines(self):
        resp = Response(
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
            },  # noqa: mock
            id="account_lines_144811",
            type=ResponseType.RESPONSE,
        )

        return resp

    def _client_response_account_objects(self):
        resp = Response(
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
                        },  # noqa: mock
                        "HighNode": "22d3",
                        "LedgerEntryType": "RippleState",
                        "LowLimit": {
                            "currency": "USD",
                            "issuer": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",
                            "value": "0",
                        },  # noqa: mock
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
            },  # noqa: mock
            id="account_objects_144811",
            type=ResponseType.RESPONSE,
        )

        return resp

    def _client_response_account_info_issuer(self):
        resp = Response(
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

    @patch('hummingbot.connector.exchange.xrpl.xrpl_exchange.AsyncWebsocketClient')
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._verify_transaction_result")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_autofill")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_sign")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_submit")
    @patch("hummingbot.connector.client_order_tracker.ClientOrderTracker.process_order_update")
    def test_place_limit_order(
        self,
        process_order_update_mock,
        submit_mock,
        sign_mock,
        autofill_mock,
        verify_transaction_result_mock,
        mock_async_websocket_client
    ):
        # Create a mock client to be returned by the context manager
        mock_client = AsyncMock()
        mock_async_websocket_client.return_value.__aenter__.return_value = mock_client

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
                "hbot",
                self.trading_pair,
                Decimal("12345.12345678901234567"),
                TradeType.BUY,
                OrderType.LIMIT,
                Decimal("1"),
            )
        )

        self.async_run_with_timeout(
            self.connector._place_order(
                "hbot",
                self.trading_pair,
                Decimal("12345.12345678901234567"),
                TradeType.SELL,
                OrderType.LIMIT,
                Decimal("1234567.123456789"),
            )
        )

        self.async_run_with_timeout(
            self.connector._place_order(
                "hbot",
                self.trading_pair_usd,
                Decimal("12345.12345678901234567"),
                TradeType.BUY,
                OrderType.LIMIT,
                Decimal("1234567.123456789"),
            )
        )

        self.async_run_with_timeout(
            self.connector._place_order(
                "hbot",
                self.trading_pair_usd,
                Decimal("12345.12345678901234567"),
                TradeType.SELL,
                OrderType.LIMIT,
                Decimal("1234567.123456789"),
            )
        )

        order_id = self.connector.buy(
            self.trading_pair_usd,
            Decimal("12345.12345678901234567"),
            OrderType.LIMIT,
            Decimal("1234567.123456789"),
        )

        self.assertEqual(order_id.split("-")[0], "hbot")

        order_id = self.connector.sell(
            self.trading_pair_usd,
            Decimal("12345.12345678901234567"),
            OrderType.LIMIT,
            Decimal("1234567.123456789"),
        )

        self.assertEqual(order_id.split("-")[0], "hbot")

        self.assertTrue(process_order_update_mock.called)
        self.assertTrue(verify_transaction_result_mock.called)
        self.assertTrue(submit_mock.called)
        self.assertTrue(autofill_mock.called)
        self.assertTrue(sign_mock.called)

    @patch('hummingbot.connector.exchange.xrpl.xrpl_exchange.AsyncWebsocketClient')
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._verify_transaction_result")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_autofill")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_sign")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_submit")
    @patch("hummingbot.connector.client_order_tracker.ClientOrderTracker.process_order_update")
    def test_place_market_order(
        self,
        process_order_update_mock,
        submit_mock,
        sign_mock,
        autofill_mock,
        verify_transaction_result_mock,
        mock_async_websocket_client
    ):
        # Create a mock client to be returned by the context manager
        mock_client = AsyncMock()
        mock_async_websocket_client.return_value.__aenter__.return_value = mock_client

        autofill_mock.return_value = {}
        verify_transaction_result_mock.return_value = True, {}
        sign_mock.return_value = Transaction(
            sequence=1, last_ledger_sequence=1, account="r1234", transaction_type=TransactionType.OFFER_CREATE
        )

        submit_mock.return_value = Response(
            status=ResponseStatus.SUCCESS, result={"engine_result": "tesSUCCESS", "engine_result_message": "something"}
        )

        class MockGetPriceReturn:
            def __init__(self, result_price):
                self.result_price = result_price

        # get_price_for_volume_mock.return_value = Decimal("1")
        self.connector.order_books[self.trading_pair] = MagicMock()
        self.connector.order_books[self.trading_pair].get_price_for_volume = MagicMock(
            return_value=MockGetPriceReturn(result_price=Decimal("1"))
        )

        self.connector.order_books[self.trading_pair_usd] = MagicMock()
        self.connector.order_books[self.trading_pair_usd].get_price_for_volume = MagicMock(
            return_value=MockGetPriceReturn(result_price=Decimal("1"))
        )

        self.async_run_with_timeout(
            self.connector._place_order(
                "hbot", self.trading_pair, Decimal("1"), TradeType.BUY, OrderType.MARKET, Decimal("1")
            )
        )

        self.async_run_with_timeout(
            self.connector._place_order(
                "hbot", self.trading_pair, Decimal("1"), TradeType.SELL, OrderType.MARKET, Decimal("1")
            )
        )

        self.async_run_with_timeout(
            self.connector._place_order(
                "hbot", self.trading_pair_usd, Decimal("1"), TradeType.BUY, OrderType.MARKET, Decimal("1")
            )
        )

        self.async_run_with_timeout(
            self.connector._place_order(
                "hbot", self.trading_pair_usd, Decimal("1"), TradeType.SELL, OrderType.MARKET, Decimal("1")
            )
        )

        order_id = self.connector.buy(
            self.trading_pair_usd,
            Decimal("12345.12345678901234567"),
            OrderType.MARKET,
            Decimal("1234567.123456789"),
        )

        self.assertEqual(order_id.split("-")[0], "hbot")

        order_id = self.connector.sell(
            self.trading_pair_usd,
            Decimal("12345.12345678901234567"),
            OrderType.MARKET,
            Decimal("1234567.123456789"),
        )

        self.assertEqual(order_id.split("-")[0], "hbot")

        self.assertTrue(process_order_update_mock.called)
        self.assertTrue(verify_transaction_result_mock.called)
        self.assertTrue(submit_mock.called)
        self.assertTrue(autofill_mock.called)
        self.assertTrue(sign_mock.called)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.autofill", new_callable=MagicMock)
    # @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.submit", new_callable=MagicMock)
    def test_place_order_exception_handling_not_found_market(self, autofill_mock):
        with self.assertRaises(Exception) as context:
            self.async_run_with_timeout(
                self.connector._place_order(
                    order_id="test_order",
                    trading_pair="NOT_FOUND",
                    amount=Decimal("1.0"),
                    trade_type=TradeType.BUY,
                    order_type=OrderType.MARKET,
                    price=Decimal("1"),
                )
            )

        # Verify the exception was raised and contains the expected message
        self.assertTrue("Market NOT_FOUND not found in markets list" in str(context.exception))

    @patch('hummingbot.connector.exchange.xrpl.xrpl_exchange.AsyncWebsocketClient')
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.autofill", new_callable=MagicMock)
    # @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.submit", new_callable=MagicMock)
    def test_place_order_exception_handling_autofill(self, autofill_mock, mock_async_websocket_client):
        # Create a mock client to be returned by the context manager
        mock_client = AsyncMock()
        mock_async_websocket_client.return_value.__aenter__.return_value = mock_client

        # Simulate an exception during the autofill operation
        autofill_mock.side_effect = Exception("Test exception during autofill")

        with self.assertRaises(Exception) as context:
            self.async_run_with_timeout(
                self.connector._place_order(
                    order_id="test_order",
                    trading_pair="SOLO-XRP",
                    amount=Decimal("1.0"),
                    trade_type=TradeType.BUY,
                    order_type=OrderType.MARKET,
                    price=Decimal("1"),
                )
            )

        # Verify the exception was raised and contains the expected message
        self.assertTrue(
            "Order None (test_order) creation failed: Test exception during autofill" in str(context.exception)
        )

    @patch('hummingbot.connector.exchange.xrpl.xrpl_exchange.AsyncWebsocketClient')
    @patch("hummingbot.connector.exchange_py_base.ExchangePyBase._sleep")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._verify_transaction_result")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_autofill")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_sign")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_submit")
    @patch("hummingbot.connector.client_order_tracker.ClientOrderTracker.process_order_update")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._make_network_check_request")
    def test_place_order_exception_handling_failed_verify(
        self,
        network_mock,
        process_order_update_mock,
        submit_mock,
        sign_mock,
        autofill_mock,
        verify_transaction_result_mock,
        sleep_mock,
        mock_async_websocket_client
    ):
        # Create a mock client to be returned by the context manager
        mock_client = AsyncMock()
        mock_async_websocket_client.return_value.__aenter__.return_value = mock_client

        autofill_mock.return_value = {}
        verify_transaction_result_mock.return_value = False, {}
        sign_mock.return_value = Transaction(
            sequence=1, last_ledger_sequence=1, account="r1234", transaction_type=TransactionType.OFFER_CREATE
        )

        submit_mock.return_value = Response(
            status=ResponseStatus.SUCCESS, result={"engine_result": "tesSUCCESS", "engine_result_message": "something"}
        )

        with self.assertRaises(Exception) as context:
            self.async_run_with_timeout(
                self.connector._place_order(
                    "hbot",
                    self.trading_pair_usd,
                    Decimal("12345.12345678901234567"),
                    TradeType.SELL,
                    OrderType.LIMIT,
                    Decimal("1234567.123456789"),
                )
            )

        # # Verify the exception was raised and contains the expected message
        self.assertTrue(
            "Order 1-1 (hbot) creation failed: Failed to verify transaction result for order hbot (1-1)"
            in str(context.exception)
        )

    @patch('hummingbot.connector.exchange.xrpl.xrpl_exchange.AsyncWebsocketClient')
    @patch("hummingbot.connector.exchange_py_base.ExchangePyBase._sleep")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._verify_transaction_result")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_autofill")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_sign")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_submit")
    @patch("hummingbot.connector.client_order_tracker.ClientOrderTracker.process_order_update")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._make_network_check_request")
    def test_place_order_exception_handling_none_verify_resp(
        self,
        network_mock,
        process_order_update_mock,
        submit_mock,
        sign_mock,
        autofill_mock,
        verify_transaction_result_mock,
        sleep_mock,
        mock_async_websocket_client
    ):
        # Create a mock client to be returned by the context manager
        mock_client = AsyncMock()
        mock_async_websocket_client.return_value.__aenter__.return_value = mock_client

        autofill_mock.return_value = {}
        verify_transaction_result_mock.return_value = False, None
        sign_mock.return_value = Transaction(
            sequence=1, last_ledger_sequence=1, account="r1234", transaction_type=TransactionType.OFFER_CREATE
        )

        submit_mock.return_value = Response(
            status=ResponseStatus.SUCCESS, result={"engine_result": "tesSUCCESS", "engine_result_message": "something"}
        )

        with self.assertRaises(Exception) as context:
            self.async_run_with_timeout(
                self.connector._place_order(
                    "hbot",
                    self.trading_pair_usd,
                    Decimal("12345.12345678901234567"),
                    TradeType.SELL,
                    OrderType.LIMIT,
                    Decimal("1234567.123456789"),
                )
            )

        # # Verify the exception was raised and contains the expected message
        self.assertTrue("Order 1-1 (hbot) creation failed: Failed to place order hbot (1-1)" in str(context.exception))

    @patch('hummingbot.connector.exchange.xrpl.xrpl_exchange.AsyncWebsocketClient')
    @patch("hummingbot.connector.exchange_py_base.ExchangePyBase._sleep")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._verify_transaction_result")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_autofill")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_sign")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_submit")
    @patch("hummingbot.connector.client_order_tracker.ClientOrderTracker.process_order_update")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._make_network_check_request")
    def test_place_order_exception_handling_failed_submit(
        self,
        network_mock,
        process_order_update_mock,
        submit_mock,
        sign_mock,
        autofill_mock,
        verify_transaction_result_mock,
        sleep_mock,
        mock_async_websocket_client
    ):
        # Create a mock client to be returned by the context manager
        mock_client = AsyncMock()
        mock_async_websocket_client.return_value.__aenter__.return_value = mock_client

        autofill_mock.return_value = {}
        verify_transaction_result_mock.return_value = False, None
        sign_mock.return_value = Transaction(
            sequence=1, last_ledger_sequence=1, account="r1234", transaction_type=TransactionType.OFFER_CREATE
        )

        submit_mock.return_value = Response(
            status=ResponseStatus.ERROR, result={"engine_result": "tec", "engine_result_message": "something"}
        )

        with self.assertRaises(Exception) as context:
            self.async_run_with_timeout(
                self.connector._place_order(
                    "hbot",
                    self.trading_pair_usd,
                    Decimal("12345.12345678901234567"),
                    TradeType.SELL,
                    OrderType.LIMIT,
                    Decimal("1234567.123456789"),
                )
            )

        # # Verify the exception was raised and contains the expected message
        self.assertTrue("Order 1-1 (hbot) creation failed: Failed to place order hbot (1-1)" in str(context.exception))

    @patch('hummingbot.connector.exchange.xrpl.xrpl_exchange.AsyncWebsocketClient')
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_autofill")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_sign")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_submit")
    def test_place_cancel(
        self,
        submit_mock,
        sign_mock,
        autofill_mock,
        mock_async_websocket_client,
    ):
        # Create a mock client to be returned by the context manager
        mock_client = AsyncMock()
        mock_async_websocket_client.return_value.__aenter__.return_value = mock_client

        autofill_mock.return_value = {}
        sign_mock.return_value = Transaction(
            sequence=1, last_ledger_sequence=1, account="r1234", transaction_type=TransactionType.OFFER_CREATE
        )

        submit_mock.return_value = Response(
            status=ResponseStatus.SUCCESS, result={"engine_result": "tesSUCCESS", "engine_result_message": "something"}
        )

        in_flight_order = InFlightOrder(
            client_order_id="hbot",
            exchange_order_id="1234-4321",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            creation_timestamp=1,
        )

        self.async_run_with_timeout(self.connector._place_cancel("hbot", tracked_order=in_flight_order))
        self.assertTrue(submit_mock.called)
        self.assertTrue(autofill_mock.called)
        self.assertTrue(sign_mock.called)

    @patch('hummingbot.connector.exchange.xrpl.xrpl_exchange.AsyncWebsocketClient')
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._verify_transaction_result")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_autofill")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_sign")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_submit")
    @patch("hummingbot.connector.client_order_tracker.ClientOrderTracker.process_order_update")
    @patch("hummingbot.connector.client_order_tracker.ClientOrderTracker.process_trade_update")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.process_trade_fills")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._request_order_status")
    def test_place_order_and_process_update(
        self,
        request_order_status_mock,
        process_trade_fills_mock,
        process_trade_update_mock,
        process_order_update_mock,
        submit_mock,
        sign_mock,
        autofill_mock,
        verify_transaction_result_mock,
        mock_async_websocket_client,
    ):
        # Create a mock client to be returned by the context manager
        mock_client = AsyncMock()
        mock_async_websocket_client.return_value.__aenter__.return_value = mock_client

        request_order_status_mock.return_value = OrderUpdate(
            trading_pair=self.trading_pair,
            new_state=OrderState.FILLED,
            update_timestamp=1,
        )
        autofill_mock.return_value = {}
        verify_transaction_result_mock.return_value = True, Response(
            status=ResponseStatus.SUCCESS, result={"engine_result": "tesSUCCESS", "engine_result_message": "something"}
        )
        sign_mock.return_value = Transaction(
            sequence=1, last_ledger_sequence=1, account="r1234", transaction_type=TransactionType.OFFER_CREATE
        )

        submit_mock.return_value = Response(
            status=ResponseStatus.SUCCESS, result={"engine_result": "tesSUCCESS", "engine_result_message": "something"}
        )

        in_flight_order = InFlightOrder(
            client_order_id="hbot",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("1"),
            creation_timestamp=1,
        )

        exchange_order_id = self.async_run_with_timeout(
            self.connector._place_order_and_process_update(order=in_flight_order)
        )
        self.assertTrue(submit_mock.called)
        self.assertTrue(autofill_mock.called)
        self.assertTrue(sign_mock.called)
        self.assertTrue(process_order_update_mock.called)
        self.assertTrue(process_trade_update_mock.called)
        self.assertTrue(process_trade_fills_mock.called)
        self.assertEqual("1-1", exchange_order_id)

    @patch('hummingbot.connector.exchange.xrpl.xrpl_exchange.AsyncWebsocketClient')
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._verify_transaction_result")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_autofill")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_sign")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.tx_submit")
    @patch("hummingbot.connector.client_order_tracker.ClientOrderTracker.process_order_update")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._make_network_check_request")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._request_order_status")
    def test_execute_order_cancel_and_process_update(
        self,
        request_order_status_mock,
        network_mock,
        process_order_update_mock,
        submit_mock,
        sign_mock,
        autofill_mock,
        verify_transaction_result_mock,
        mock_async_websocket_client,
    ):
        # Create a mock client to be returned by the context manager
        mock_client = AsyncMock()
        mock_async_websocket_client.return_value.__aenter__.return_value = mock_client

        request_order_status_mock.return_value = OrderUpdate(
            trading_pair=self.trading_pair,
            new_state=OrderState.FILLED,
            update_timestamp=1,
        )
        autofill_mock.return_value = {}
        verify_transaction_result_mock.return_value = True, Response(
            status=ResponseStatus.SUCCESS,
            result={"engine_result": "tesSUCCESS", "engine_result_message": "something", "meta": {"AffectedNodes": []}},
        )
        sign_mock.return_value = Transaction(
            sequence=1, last_ledger_sequence=1, account="r1234", transaction_type=TransactionType.OFFER_CREATE
        )

        submit_mock.return_value = Response(
            status=ResponseStatus.SUCCESS, result={"engine_result": "tesSUCCESS", "engine_result_message": "something"}
        )

        in_flight_order = InFlightOrder(
            client_order_id="hbot",
            exchange_order_id="1234-4321",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("1"),
            creation_timestamp=1,
        )

        result = self.async_run_with_timeout(
            self.connector._execute_order_cancel_and_process_update(order=in_flight_order)
        )
        self.assertTrue(process_order_update_mock.called)
        self.assertTrue(result)

        request_order_status_mock.return_value = OrderUpdate(
            trading_pair=self.trading_pair,
            new_state=OrderState.OPEN,
            update_timestamp=1,
        )

        result = self.async_run_with_timeout(
            self.connector._execute_order_cancel_and_process_update(order=in_flight_order)
        )
        self.assertTrue(process_order_update_mock.called)
        self.assertTrue(result)

    def test_format_trading_rules(self):
        trading_rules_info = {"XRP-USD": {"base_tick_size": 8, "quote_tick_size": 8, "minimum_order_size": 0.01}}

        result = self.connector._format_trading_rules(trading_rules_info)

        expected_result = [
            TradingRule(
                trading_pair="XRP-USD",
                min_order_size=Decimal(0.01),
                min_price_increment=Decimal("1e-8"),
                min_quote_amount_increment=Decimal("1e-8"),
                min_base_amount_increment=Decimal("1e-8"),
                min_notional_size=Decimal("1e-8"),
            )
        ]

        self.assertEqual(result[0].min_order_size, expected_result[0].min_order_size)
        self.assertEqual(result[0].min_price_increment, expected_result[0].min_price_increment)
        self.assertEqual(result[0].min_quote_amount_increment, expected_result[0].min_quote_amount_increment)
        self.assertEqual(result[0].min_base_amount_increment, expected_result[0].min_base_amount_increment)
        self.assertEqual(result[0].min_notional_size, expected_result[0].min_notional_size)

    def test_format_trading_pair_fee_rules(self):
        trading_rules_info = {"XRP-USD": {"base_transfer_rate": 0.01, "quote_transfer_rate": 0.01}}

        result = self.connector._format_trading_pair_fee_rules(trading_rules_info)

        expected_result = [
            {
                "trading_pair": "XRP-USD",
                "base_token": "XRP",
                "quote_token": "USD",
                "base_transfer_rate": 0.01,
                "quote_transfer_rate": 0.01,
            }
        ]

        self.assertEqual(result, expected_result)

    @patch("hummingbot.connector.exchange_py_base.ExchangePyBase._iter_user_event_queue")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.get_order_by_sequence")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._update_balances")
    @patch("hummingbot.connector.client_order_tracker.ClientOrderTracker.process_order_update")
    def test_user_stream_event_listener(
        self,
        process_order_update_mock,
        update_balances_mock,
        get_account_mock,
        get_order_by_sequence,
        iter_user_event_queue_mock,
    ):
        async def async_generator(lst):
            for item in lst:
                yield item

        message_list = [self._event_message()]
        async_iterable = async_generator(message_list)

        in_flight_order = InFlightOrder(
            client_order_id="hbot",
            exchange_order_id="84437780-88954510",
            trading_pair=self.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=TradeType.BUY,
            amount=Decimal("2.239836701211152"),
            price=Decimal("0.224547537"),
            creation_timestamp=1,
        )

        iter_user_event_queue_mock.return_value = async_iterable
        get_order_by_sequence.return_value = in_flight_order
        get_account_mock.return_value = "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK"  # noqa: mock

        self.async_run_with_timeout(self.connector._user_stream_event_listener())
        self.assertTrue(update_balances_mock.called)
        self.assertTrue(get_account_mock.called)
        self.assertTrue(get_order_by_sequence.called)
        self.assertTrue(iter_user_event_queue_mock.called)

        args, kwargs = process_order_update_mock.call_args
        self.assertEqual(kwargs["order_update"].new_state, OrderState.FILLED)

    @patch("hummingbot.connector.exchange_py_base.ExchangePyBase._iter_user_event_queue")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.get_order_by_sequence")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._update_balances")
    @patch("hummingbot.connector.client_order_tracker.ClientOrderTracker.process_order_update")
    def test_user_stream_event_listener_partially_filled(
        self,
        process_order_update_mock,
        update_balances_mock,
        get_account_mock,
        get_order_by_sequence,
        iter_user_event_queue_mock,
    ):
        async def async_generator(lst):
            for item in lst:
                yield item

        message_list = [self._event_message_limit_order_partially_filled()]
        async_iterable = async_generator(message_list)

        in_flight_order = InFlightOrder(
            client_order_id="hbot",
            exchange_order_id="84437895-88954510",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1.47951609"),
            price=Decimal("0.224547537"),
            creation_timestamp=1,
        )

        iter_user_event_queue_mock.return_value = async_iterable
        get_order_by_sequence.return_value = in_flight_order
        get_account_mock.return_value = "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK"  # noqa: mock

        self.async_run_with_timeout(self.connector._user_stream_event_listener())
        self.assertTrue(update_balances_mock.called)
        self.assertTrue(get_account_mock.called)
        self.assertTrue(get_order_by_sequence.called)
        self.assertTrue(iter_user_event_queue_mock.called)

        args, kwargs = process_order_update_mock.call_args
        self.assertEqual(kwargs["order_update"].new_state, OrderState.PARTIALLY_FILLED)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._make_network_check_request")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    def test_update_balances(self, get_account_mock, network_mock):
        get_account_mock.return_value = "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK"  # noqa: mock

        def side_effect_function(arg: Request):
            if arg.method == RequestMethod.ACCOUNT_INFO:
                return self._client_response_account_info()
            elif arg.method == RequestMethod.ACCOUNT_OBJECTS:
                return self._client_response_account_objects()
            elif arg.method == RequestMethod.ACCOUNT_LINES:
                return self._client_response_account_lines()
            else:
                raise ValueError("Invalid method")

        self.connector._xrpl_query_client.request.side_effect = side_effect_function

        self.async_run_with_timeout(self.connector._update_balances())

        self.assertTrue(get_account_mock.called)

        self.assertEqual(self.connector._account_balances["XRP"], Decimal("57.030864"))
        self.assertEqual(self.connector._account_balances["USD"], Decimal("0.011094399237562"))
        self.assertEqual(self.connector._account_balances["SOLO"], Decimal("35.95165691730148"))

        self.assertEqual(self.connector._account_available_balances["XRP"], Decimal("32.030868"))
        self.assertEqual(self.connector._account_available_balances["USD"], Decimal("0.011094399237562"))
        self.assertEqual(self.connector._account_available_balances["SOLO"], Decimal("31.337975848655761"))

    def test_make_trading_rules_request(self):
        def side_effect_function(arg: Request):
            if arg.method == RequestMethod.ACCOUNT_INFO:
                return self._client_response_account_info_issuer()
            else:
                raise ValueError("Invalid method")

        self.connector._xrpl_query_client.request.side_effect = side_effect_function

        result = self.async_run_with_timeout(self.connector._make_trading_rules_request())

        self.assertEqual(
            result["SOLO-XRP"]["base_currency"].currency, "534F4C4F00000000000000000000000000000000"
        )  # noqa: mock
        self.assertEqual(result["SOLO-XRP"]["base_currency"].issuer, "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz")  # noqa: mock
        self.assertEqual(result["SOLO-XRP"]["base_tick_size"], 15)
        self.assertEqual(result["SOLO-XRP"]["quote_tick_size"], 6)
        self.assertEqual(result["SOLO-XRP"]["base_transfer_rate"], 9.999999999998899e-05)
        self.assertEqual(result["SOLO-XRP"]["quote_transfer_rate"], 0)
        self.assertEqual(result["SOLO-XRP"]["minimum_order_size"], 1e-06)

        self.async_run_with_timeout(self.connector._update_trading_rules())
        trading_rule = self.connector.trading_rules["SOLO-XRP"]
        self.assertEqual(
            trading_rule.min_order_size,
            Decimal("9.99999999999999954748111825886258685613938723690807819366455078125E-7"),  # noqa: mock
        )

        self.assertEqual(
            result["SOLO-USD"]["base_currency"].currency, "534F4C4F00000000000000000000000000000000"  # noqa: mock
        )
        self.assertEqual(result["SOLO-USD"]["quote_currency"].currency, "USD")

    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.wait_for_final_transaction_outcome")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._make_network_check_request")
    def test_verify_transaction_success(self, network_check_mock, wait_for_outcome_mock):
        wait_for_outcome_mock.return_value = Response(status=ResponseStatus.SUCCESS, result={})
        transaction_mock = MagicMock()
        transaction_mock.get_hash.return_value = "hash"
        transaction_mock.last_ledger_sequence = 12345

        result, response = self.async_run_with_timeout(
            self.connector._verify_transaction_result({"transaction": transaction_mock, "prelim_result": "tesSUCCESS"})
        )
        self.assertTrue(result)
        self.assertIsNotNone(response)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.wait_for_final_transaction_outcome")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._make_network_check_request")
    def test_verify_transaction_exception(self, network_check_mock, wait_for_outcome_mock):
        wait_for_outcome_mock.side_effect = Exception("Test exception")
        transaction_mock = MagicMock()
        transaction_mock.get_hash.return_value = "hash"
        transaction_mock.last_ledger_sequence = 12345

        with self.assertLogs(level="ERROR") as log:
            result, response = self.async_run_with_timeout(
                self.connector._verify_transaction_result(
                    {"transaction": transaction_mock, "prelim_result": "tesSUCCESS"}
                )
            )

        log_output = log.output[0]
        self.assertEqual(
            log_output,
            "ERROR:hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange:Submitted transaction failed: Test exception",
        )

    def test_verify_transaction_exception_none_transaction(self):
        with self.assertLogs(level="ERROR") as log:
            self.async_run_with_timeout(
                self.connector._verify_transaction_result({"transaction": None, "prelim_result": "tesSUCCESS"})
            )

        log_output = log.output[0]
        self.assertEqual(
            log_output,
            "ERROR:hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange:Failed to verify transaction result, transaction is None",
        )

        self.connector.wait_for_final_transaction_outcome = AsyncMock()
        self.connector.wait_for_final_transaction_outcome.side_effect = TimeoutError
        self.connector._sleep = AsyncMock()

        with self.assertLogs(level="ERROR") as log:
            self.async_run_with_timeout(
                self.connector._verify_transaction_result(
                    {
                        "transaction": Transaction(
                            account="r1234", transaction_type=TransactionType.ACCOUNT_SET
                        ),  # noqa: mock
                        "prelim_result": "tesSUCCESS",
                    }
                )
            )

        log_output = log.output[0]
        self.assertEqual(
            log_output,
            "ERROR:hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange:Max retries reached. Verify transaction failed due to timeout.",
        )

        with self.assertLogs(level="ERROR") as log:
            self.async_run_with_timeout(
                self.connector._verify_transaction_result(
                    {
                        "transaction": Transaction(
                            account="r1234", transaction_type=TransactionType.ACCOUNT_SET
                        ),  # noqa: mock
                        "prelim_result": "tesSUCCESS",
                    },
                    try_count=CONSTANTS.VERIFY_TRANSACTION_MAX_RETRY,
                )
            )

        log_output = log.output[0]
        self.assertEqual(
            log_output,
            "ERROR:hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange:Max retries reached. Verify transaction failed due to timeout.",
        )

    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.wait_for_final_transaction_outcome")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._make_network_check_request")
    def test_verify_transaction_exception_none_prelim(self, network_check_mock, wait_for_outcome_mock):
        wait_for_outcome_mock.side_effect = Exception("Test exception")
        transaction_mock = MagicMock()
        transaction_mock.get_hash.return_value = "hash"
        transaction_mock.last_ledger_sequence = 12345

        with self.assertLogs(level="ERROR") as log:
            result, response = self.async_run_with_timeout(
                self.connector._verify_transaction_result({"transaction": transaction_mock, "prelim_result": None})
            )

        log_output = log.output[0]
        self.assertEqual(
            log_output,
            "ERROR:hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange:Failed to verify transaction result, prelim_result is None",
        )

    def test_get_order_by_sequence_order_found(self):
        # Setup
        sequence = "84437895"
        order = InFlightOrder(
            client_order_id="hbot",
            exchange_order_id="84437895-88954510",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1.47951609"),
            price=Decimal("0.224547537"),
            creation_timestamp=1,
        )

        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_fillable_orders = {"test_order": order}

        # Action
        result = self.connector.get_order_by_sequence(sequence)

        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result.client_order_id, "hbot")

    def test_get_order_by_sequence_order_not_found(self):
        # Setup
        sequence = "100"

        # Action
        result = self.connector.get_order_by_sequence(sequence)

        # Assert
        self.assertIsNone(result)

    def test_get_order_by_sequence_order_without_exchange_id(self):
        # Setup
        order = InFlightOrder(
            client_order_id="test_order",
            trading_pair="XRP_USD",
            amount=Decimal("1.47951609"),
            price=Decimal("0.224547537"),
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            exchange_order_id=None,
            creation_timestamp=1,
        )

        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_fillable_orders = {"test_order": order}

        # Action
        result = self.connector.get_order_by_sequence("100")

        # Assert
        self.assertIsNone(result)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._make_network_check_request")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._fetch_account_transactions")
    def test_request_order_status(self, fetch_account_transactions_mock, network_check_mock, get_account_mock):
        transactions = [
            {
                "meta": {
                    "AffectedNodes": [
                        {
                            "ModifiedNode": {
                                "FinalFields": {
                                    "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                    "Balance": "55333348",
                                    "Flags": 0,
                                    "OwnerCount": 4,
                                    "Sequence": 84439853,
                                },
                                "LedgerEntryType": "AccountRoot",
                                "LedgerIndex": "2B3020738E7A44FBDE454935A38D77F12DC5A11E0FA6DAE2D9FCF4719FFAA3BC",  # noqa: mock
                                "PreviousFields": {"Balance": "55333358", "OwnerCount": 3, "Sequence": 84439852},
                                "PreviousTxnID": "5D402BF9D88BAFB49F28B90912F447840AEBC67776B8522E16F3AD9871725F75",  # noqa: mock
                                "PreviousTxnLgrSeq": 89076176,
                            }
                        },
                        {
                            "ModifiedNode": {
                                "FinalFields": {
                                    "Flags": 0,
                                    "Owner": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                    "RootIndex": "96A6199A80137B4B000352202D95C7F977EEBED39070B485D41903BD991E1F4B",  # noqa: mock
                                },
                                "LedgerEntryType": "DirectoryNode",
                                "LedgerIndex": "96A6199A80137B4B000352202D95C7F977EEBED39070B485D41903BD991E1F4B",  # noqa: mock
                            }
                        },
                        {
                            "CreatedNode": {
                                "LedgerEntryType": "Offer",
                                "LedgerIndex": "B0056398D70A57B8A535EB9F32E35486DEAB354CFAF29777E636755A98323B5F",  # noqa: mock
                                "NewFields": {
                                    "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                    "BookDirectory": "C73FAC6C294EBA5B9E22A8237AAE80725E85372510A6CA794F105E50A1A8ECA4",  # noqa: mock
                                    "Flags": 131072,
                                    "Sequence": 84439852,
                                    "TakerGets": "499999",
                                    "TakerPays": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                        "value": "2.303645407683732",
                                    },
                                },
                            }
                        },
                        {
                            "CreatedNode": {
                                "LedgerEntryType": "DirectoryNode",
                                "LedgerIndex": "C73FAC6C294EBA5B9E22A8237AAE80725E85372510A6CA794F105E50A1A8ECA4",  # noqa: mock
                                "NewFields": {
                                    "ExchangeRate": "4f105e50a1a8eca4",  # noqa: mock
                                    "RootIndex": "C73FAC6C294EBA5B9E22A8237AAE80725E85372510A6CA794F105E50A1A8ECA4",  # noqa: mock
                                    "TakerPaysCurrency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "TakerPaysIssuer": "1EB3EAA3AD86242E1D51DC502DD6566BD39E06A6",  # noqa: mock
                                },
                            }
                        },
                    ],
                    "TransactionIndex": 33,
                    "TransactionResult": "tesSUCCESS",
                },
                "tx": {
                    "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                    "Fee": "10",
                    "Flags": 524288,
                    "LastLedgerSequence": 89077154,
                    "Memos": [
                        {
                            "Memo": {
                                "MemoData": "68626F742D313731393836383934323231373635332D42534F585036316333363331356337316463616132656233626234363139323466343666343333366632"  # noqa: mock
                            }
                        }
                    ],
                    "Sequence": 84439852,
                    "SigningPubKey": "ED23BA20D57103E05BA762F0A04FE50878C11BD36B7BF9ADACC3EDBD9E6D320923",  # noqa: mock
                    "TakerGets": "499999",
                    "TakerPays": {
                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                        "value": "2.303645407683732",
                    },
                    "TransactionType": "OfferCreate",
                    "TxnSignature": "6C6FA022E59DD9DA59E47D6736FF6DD5473A416D4A96B031D273A3DBE19E3ACA9B12A1719587CE55F19F9EA62884329A6D2C8224053517397308B59C4D39D607",  # noqa: mock
                    "date": 773184150,
                    "hash": "E25C2542FEBF4F7728A9AEB015FE00B9938BFA2C08ABB5F1B34670F15964E0F9",  # noqa: mock
                    "inLedger": 89077136,
                    "ledger_index": 89077136,
                },
                "validated": True,
            },
            {
                "meta": {
                    "AffectedNodes": [
                        {
                            "CreatedNode": {
                                "LedgerEntryType": "Offer",
                                "LedgerIndex": "1612E220D4745CE63F6FF45821317DDFFACFCFF8A4F798A92628977A39E31C55",  # noqa: mock
                                "NewFields": {
                                    "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                    "BookDirectory": "C73FAC6C294EBA5B9E22A8237AAE80725E85372510A6CA794F105DE55C02FE6E",  # noqa: mock
                                    "Flags": 131072,
                                    "Sequence": 84439853,
                                    "TakerGets": "499999",
                                    "TakerPays": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                        "value": "2.303415043142963",
                                    },
                                },
                            }
                        },
                        {
                            "ModifiedNode": {
                                "FinalFields": {
                                    "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                    "Balance": "55333338",
                                    "Flags": 0,
                                    "OwnerCount": 5,
                                    "Sequence": 84439854,
                                },
                                "LedgerEntryType": "AccountRoot",
                                "LedgerIndex": "2B3020738E7A44FBDE454935A38D77F12DC5A11E0FA6DAE2D9FCF4719FFAA3BC",  # noqa: mock
                                "PreviousFields": {"Balance": "55333348", "OwnerCount": 4, "Sequence": 84439853},
                                "PreviousTxnID": "E25C2542FEBF4F7728A9AEB015FE00B9938BFA2C08ABB5F1B34670F15964E0F9",  # noqa: mock
                                "PreviousTxnLgrSeq": 89077136,
                            }
                        },
                        {
                            "ModifiedNode": {
                                "FinalFields": {
                                    "Flags": 0,
                                    "Owner": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                    "RootIndex": "96A6199A80137B4B000352202D95C7F977EEBED39070B485D41903BD991E1F4B",  # noqa: mock
                                },
                                "LedgerEntryType": "DirectoryNode",
                                "LedgerIndex": "96A6199A80137B4B000352202D95C7F977EEBED39070B485D41903BD991E1F4B",  # noqa: mock
                            }
                        },
                        {
                            "CreatedNode": {
                                "LedgerEntryType": "DirectoryNode",
                                "LedgerIndex": "C73FAC6C294EBA5B9E22A8237AAE80725E85372510A6CA794F105DE55C02FE6E",  # noqa: mock
                                "NewFields": {
                                    "ExchangeRate": "4f105de55c02fe6e",  # noqa: mock
                                    "RootIndex": "C73FAC6C294EBA5B9E22A8237AAE80725E85372510A6CA794F105DE55C02FE6E",  # noqa: mock
                                    "TakerPaysCurrency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "TakerPaysIssuer": "1EB3EAA3AD86242E1D51DC502DD6566BD39E06A6",  # noqa: mock
                                },
                            }
                        },
                    ],
                    "TransactionIndex": 34,
                    "TransactionResult": "tesSUCCESS",
                },
                "tx": {
                    "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                    "Fee": "10",
                    "Flags": 524288,
                    "LastLedgerSequence": 89077154,
                    "Memos": [
                        {
                            "Memo": {
                                "MemoData": "68626F742D313731393836383934323231373938322D42534F585036316333363331356337333065616132656233626234363139323466343666343333366632"  # noqa: mock
                            }
                        }
                    ],
                    "Sequence": 84439853,
                    "SigningPubKey": "ED23BA20D57103E05BA762F0A04FE50878C11BD36B7BF9ADACC3EDBD9E6D320923",  # noqa: mock
                    "TakerGets": "499999",
                    "TakerPays": {
                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                        "value": "2.303415043142963",
                    },
                    "TransactionType": "OfferCreate",
                    "TxnSignature": "9F830864D3522824F1E4349EF2FA719513F8E3D2742BDDA37DE42F8982F95571C207A4D5138CCFFE2DA14AA187570AD8FC43D74E88B01BB272B37B9CD6D77E0A",  # noqa: mock
                    "date": 773184150,
                    "hash": "CD80F1985807A0824D4C5DAC78C972A0A417B77FE1598FA51E166A105454E767",  # noqa: mock
                    "inLedger": 89077136,
                    "ledger_index": 89077136,
                },
                "validated": True,
            },
            {
                "meta": {
                    "AffectedNodes": [
                        {
                            "CreatedNode": {
                                "LedgerEntryType": "Offer",
                                "LedgerIndex": "1292552AAC3151AA5A4EA807BC3731B8D2CD45A80AA7DD675501BA7CC051E618",  # noqa: mock
                                "NewFields": {
                                    "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                    "BookDirectory": "5C8970D155D65DB8FF49B291D7EFFA4A09F9E8A68D9974B25A07B66BAB1A824D",  # noqa: mock
                                    "Flags": 131072,
                                    "Sequence": 84439854,
                                    "TakerGets": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                        "value": "2.303184724670496",
                                    },
                                    "TakerPays": "499998",
                                },
                            }
                        },
                        {
                            "DeletedNode": {
                                "FinalFields": {
                                    "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                    "BookDirectory": "C73FAC6C294EBA5B9E22A8237AAE80725E85372510A6CA794F105DE55C02FE6E",  # noqa: mock
                                    "BookNode": "0",
                                    "Flags": 131072,
                                    "OwnerNode": "0",
                                    "PreviousTxnID": "CD80F1985807A0824D4C5DAC78C972A0A417B77FE1598FA51E166A105454E767",  # noqa: mock
                                    "PreviousTxnLgrSeq": 89077136,
                                    "Sequence": 84439853,
                                    "TakerGets": "499999",
                                    "TakerPays": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                        "value": "2.303415043142963",
                                    },
                                },
                                "LedgerEntryType": "Offer",
                                "LedgerIndex": "1612E220D4745CE63F6FF45821317DDFFACFCFF8A4F798A92628977A39E31C55",  # noqa: mock
                            }
                        },
                        {
                            "ModifiedNode": {
                                "FinalFields": {
                                    "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                    "Balance": "55333328",
                                    "Flags": 0,
                                    "OwnerCount": 5,
                                    "Sequence": 84439855,
                                },
                                "LedgerEntryType": "AccountRoot",
                                "LedgerIndex": "2B3020738E7A44FBDE454935A38D77F12DC5A11E0FA6DAE2D9FCF4719FFAA3BC",  # noqa: mock
                                "PreviousFields": {"Balance": "55333338", "Sequence": 84439854},
                                "PreviousTxnID": "CD80F1985807A0824D4C5DAC78C972A0A417B77FE1598FA51E166A105454E767",  # noqa: mock
                                "PreviousTxnLgrSeq": 89077136,
                            }
                        },
                        {
                            "CreatedNode": {
                                "LedgerEntryType": "DirectoryNode",
                                "LedgerIndex": "5C8970D155D65DB8FF49B291D7EFFA4A09F9E8A68D9974B25A07B66BAB1A824D",  # noqa: mock
                                "NewFields": {
                                    "ExchangeRate": "5a07b66bab1a824d",  # noqa: mock
                                    "RootIndex": "5C8970D155D65DB8FF49B291D7EFFA4A09F9E8A68D9974B25A07B66BAB1A824D",  # noqa: mock
                                    "TakerGetsCurrency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "TakerGetsIssuer": "1EB3EAA3AD86242E1D51DC502DD6566BD39E06A6",  # noqa: mock
                                },
                            }
                        },
                        {
                            "ModifiedNode": {
                                "FinalFields": {
                                    "Flags": 0,
                                    "Owner": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                    "RootIndex": "96A6199A80137B4B000352202D95C7F977EEBED39070B485D41903BD991E1F4B",  # noqa: mock
                                },
                                "LedgerEntryType": "DirectoryNode",
                                "LedgerIndex": "96A6199A80137B4B000352202D95C7F977EEBED39070B485D41903BD991E1F4B",  # noqa: mock
                            }
                        },
                        {
                            "DeletedNode": {
                                "FinalFields": {
                                    "ExchangeRate": "4f105de55c02fe6e",  # noqa: mock
                                    "Flags": 0,
                                    "RootIndex": "C73FAC6C294EBA5B9E22A8237AAE80725E85372510A6CA794F105DE55C02FE6E",  # noqa: mock
                                    "TakerGetsCurrency": "0000000000000000000000000000000000000000",  # noqa: mock
                                    "TakerGetsIssuer": "0000000000000000000000000000000000000000",  # noqa: mock
                                    "TakerPaysCurrency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "TakerPaysIssuer": "1EB3EAA3AD86242E1D51DC502DD6566BD39E06A6",  # noqa: mock
                                },
                                "LedgerEntryType": "DirectoryNode",
                                "LedgerIndex": "C73FAC6C294EBA5B9E22A8237AAE80725E85372510A6CA794F105DE55C02FE6E",  # noqa: mock
                            }
                        },
                    ],
                    "TransactionIndex": 35,
                    "TransactionResult": "tesSUCCESS",
                },
                "tx": {
                    "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                    "Fee": "10",
                    "Flags": 524288,
                    "LastLedgerSequence": 89077154,
                    "Memos": [
                        {
                            "Memo": {
                                "MemoData": "68626F742D313731393836383934323231383930302D53534F585036316333363331356337366132616132656233626234363139323466343666343333366632"  # noqa: mock
                            }
                        }
                    ],
                    "Sequence": 84439854,
                    "SigningPubKey": "ED23BA20D57103E05BA762F0A04FE50878C11BD36B7BF9ADACC3EDBD9E6D320923",  # noqa: mock
                    "TakerGets": {
                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                        "value": "2.303184724670496",
                    },
                    "TakerPays": "499998",
                    "TransactionType": "OfferCreate",
                    "TxnSignature": "0E62B49938249F9AED6C6D3C893C21569F23A84CE44F9B9189D22545D5FA05896A5F0C471C68079C8CF78682D74F114038E10DA2995C18560C2259C7590A0304",  # noqa: mock
                    "date": 773184150,
                    "hash": "5BAF81CF16BA62153F31096DDDEFC12CE39EC41025A9625357BF084411045517",  # noqa: mock
                    "inLedger": 89077136,
                    "ledger_index": 89077136,
                },
                "validated": True,
            },
            {
                "meta": {
                    "AffectedNodes": [
                        {
                            "ModifiedNode": {
                                "FinalFields": {
                                    "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                    "Balance": "55333318",
                                    "Flags": 0,
                                    "OwnerCount": 6,
                                    "Sequence": 84439856,
                                },
                                "LedgerEntryType": "AccountRoot",
                                "LedgerIndex": "2B3020738E7A44FBDE454935A38D77F12DC5A11E0FA6DAE2D9FCF4719FFAA3BC",  # noqa: mock
                                "PreviousFields": {"Balance": "55333328", "OwnerCount": 5, "Sequence": 84439855},
                                "PreviousTxnID": "5BAF81CF16BA62153F31096DDDEFC12CE39EC41025A9625357BF084411045517",  # noqa: mock
                                "PreviousTxnLgrSeq": 89077136,
                            }
                        },
                        {
                            "CreatedNode": {
                                "LedgerEntryType": "DirectoryNode",
                                "LedgerIndex": "5C8970D155D65DB8FF49B291D7EFFA4A09F9E8A68D9974B25A07B70349E902F1",  # noqa: mock
                                "NewFields": {
                                    "ExchangeRate": "5a07b70349e902f1",  # noqa: mock
                                    "RootIndex": "5C8970D155D65DB8FF49B291D7EFFA4A09F9E8A68D9974B25A07B70349E902F1",  # noqa: mock
                                    "TakerGetsCurrency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "TakerGetsIssuer": "1EB3EAA3AD86242E1D51DC502DD6566BD39E06A6",  # noqa: mock
                                },
                            }
                        },
                        {
                            "ModifiedNode": {
                                "FinalFields": {
                                    "Flags": 0,
                                    "Owner": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                    "RootIndex": "96A6199A80137B4B000352202D95C7F977EEBED39070B485D41903BD991E1F4B",  # noqa: mock
                                },
                                "LedgerEntryType": "DirectoryNode",
                                "LedgerIndex": "96A6199A80137B4B000352202D95C7F977EEBED39070B485D41903BD991E1F4B",  # noqa: mock
                            }
                        },
                        {
                            "CreatedNode": {
                                "LedgerEntryType": "Offer",
                                "LedgerIndex": "BC66BC739E696FEEB8063F9C30027C1E016D6AB6467F830DE9F6DE5E04EDC937",  # noqa: mock
                                "NewFields": {
                                    "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                    "BookDirectory": "5C8970D155D65DB8FF49B291D7EFFA4A09F9E8A68D9974B25A07B70349E902F1",  # noqa: mock
                                    "Flags": 131072,
                                    "Sequence": 84439855,
                                    "TakerGets": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                        "value": "2.302494045524753",
                                    },
                                    "TakerPays": "499998",
                                },
                            }
                        },
                    ],
                    "TransactionIndex": 36,
                    "TransactionResult": "tesSUCCESS",
                },
                "tx": {
                    "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                    "Fee": "10",
                    "Flags": 524288,
                    "LastLedgerSequence": 89077154,
                    "Memos": [
                        {
                            "Memo": {
                                "MemoData": "68626F742D313731393836383934323231393137382D53534F585036316333363331356337376331616132656233626234363139323466343666343333366632"  # noqa: mock
                            }
                        }
                    ],
                    "Sequence": 84439855,
                    "SigningPubKey": "ED23BA20D57103E05BA762F0A04FE50878C11BD36B7BF9ADACC3EDBD9E6D320923",  # noqa: mock
                    "TakerGets": {
                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                        "value": "2.302494045524753",
                    },
                    "TakerPays": "499998",
                    "TransactionType": "OfferCreate",
                    "TxnSignature": "505B250B923C6330CE415B6CB182767AB11A633E0D30D5FF1B3A93638AC88D5078F33E3B6D6DAE67599D02DA86494B2AD8A7A23DCA54EBE0B4928F3E86DF7E01",  # noqa: mock
                    "date": 773184150,
                    "hash": "B4D9196A5F2BFDC33B820F27E4499C22F1D4E4EAACCB58E02B640CF0B9B73BED",  # noqa: mock
                    "inLedger": 89077136,
                    "ledger_index": 89077136,
                },
                "validated": True,
            },
        ]

        fetch_account_transactions_mock.return_value = transactions
        get_account_mock.return_value = "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK"  # noqa: mock

        in_flight_order = InFlightOrder(
            client_order_id="hbot-1719868942218900-SSOXP61c36315c76a2aa2eb3bb461924f46f4336f2",  # noqa: mock
            exchange_order_id="84439854-89077154",
            trading_pair="SOLO-XRP",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            price=Decimal("0.217090"),
            amount=Decimal("2.303184724670496"),
            creation_timestamp=1719868942.0,
        )

        order_update = self.async_run_with_timeout(self.connector._request_order_status(in_flight_order))

        self.assertEqual(
            order_update.client_order_id,
            "hbot-1719868942218900-SSOXP61c36315c76a2aa2eb3bb461924f46f4336f2",  # noqa: mock
        )
        self.assertEqual(order_update.exchange_order_id, "84439854-89077154")
        self.assertEqual(order_update.new_state, OrderState.OPEN)

        in_flight_order = InFlightOrder(
            client_order_id="hbot-1719868942218900-SSOXP61c36315c76a2aa2eb3bb461924f46f4336f2",  # noqa: mock
            exchange_order_id="84439854-89077154",
            trading_pair="SOLO-XRP",
            order_type=OrderType.MARKET,
            trade_type=TradeType.SELL,
            price=Decimal("0.217090"),
            amount=Decimal("2.303184724670496"),
            creation_timestamp=1719868942.0,
        )

        order_update = self.async_run_with_timeout(self.connector._request_order_status(in_flight_order))
        self.assertEqual(order_update.new_state, OrderState.FILLED)

        fetch_account_transactions_mock.return_value = []

        order_update = self.async_run_with_timeout(self.connector._request_order_status(in_flight_order))
        self.assertEqual(order_update.new_state, OrderState.PENDING_CREATE)

        in_flight_order = InFlightOrder(
            client_order_id="hbot-1719868942218900-SSOXP61c36315c76a2aa2eb3bb461924f46f4336f2",  # noqa: mock
            exchange_order_id="84439854-89077154",
            trading_pair="SOLO-XRP",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            price=Decimal("0.217090"),
            amount=Decimal("2.303184724670496"),
            creation_timestamp=1719868942.0,
        )

        order_update = self.async_run_with_timeout(self.connector._request_order_status(in_flight_order))
        self.assertEqual(order_update.new_state, OrderState.FAILED)

        in_flight_order = InFlightOrder(
            client_order_id="hbot-1719868942218900-SSOXP61c36315c76a2aa2eb3bb461924f46f4336f2",  # noqa: mock
            exchange_order_id="84439854-89077154",
            trading_pair="SOLO-XRP",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            price=Decimal("0.217090"),
            amount=Decimal("2.303184724670496"),
            creation_timestamp=time.time(),
        )

        order_update = self.async_run_with_timeout(self.connector._request_order_status(in_flight_order))
        self.assertEqual(order_update.new_state, OrderState.PENDING_CREATE)

        in_flight_order = InFlightOrder(
            client_order_id="hbot-1719868942218900-SSOXP61c36315c76a2aa2eb3bb461924f46f4336f2",  # noqa: mock
            trading_pair="SOLO-XRP",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            price=Decimal("0.217090"),
            amount=Decimal("2.303184724670496"),
            creation_timestamp=time.time(),
        )

        in_flight_order.current_state = OrderState.PENDING_CREATE
        order_update = self.async_run_with_timeout(self.connector._request_order_status(in_flight_order))
        self.assertEqual(order_update.new_state, OrderState.PENDING_CREATE)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._make_network_check_request")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._fetch_account_transactions")
    def test_get_trade_fills(self, fetch_account_transactions_mock, network_check_mock, get_account_mock):
        transactions = [
            {
                "meta": {
                    "AffectedNodes": [
                        {
                            "ModifiedNode": {
                                "FinalFields": {
                                    "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                    "Balance": "59912051",
                                    "Flags": 0,
                                    "OwnerCount": 6,
                                    "Sequence": 84436575,
                                },
                                "LedgerEntryType": "AccountRoot",
                                "LedgerIndex": "2B3020738E7A44FBDE454935A38D77F12DC5A11E0FA6DAE2D9FCF4719FFAA3BC",  # noqa: mock
                                "PreviousFields": {"Balance": "61162046", "OwnerCount": 7},
                                "PreviousTxnID": "5220A3E8F0F1814621E6A346078A22F32596487FA8D0C35BCAF2CF1B2415B92C",  # noqa: mock
                                "PreviousTxnLgrSeq": 88824963,
                            }
                        },
                        {
                            "ModifiedNode": {
                                "FinalFields": {
                                    "Account": "r9aZRryD8AZzGqQjYrQQuBBzebjF555Xsa",  # noqa: mock
                                    "Balance": "41317279592",
                                    "Flags": 0,
                                    "OwnerCount": 14,
                                    "Sequence": 86464581,
                                },
                                "LedgerEntryType": "AccountRoot",
                                "LedgerIndex": "547BD7E3B75FDEE721B73AED1D39AD94D3250E520358CC6521F39F15C6ADE46D",  # noqa: mock
                                "PreviousFields": {"Balance": "41316029612", "OwnerCount": 13, "Sequence": 86464580},
                                "PreviousTxnID": "82BDFD72A5BD1A423E54C9C880DEDC3DC002261050001B04C28C00036640D591",  # noqa: mock
                                "PreviousTxnLgrSeq": 88824963,
                            }
                        },
                        {
                            "ModifiedNode": {
                                "FinalFields": {
                                    "Flags": 0,
                                    "Owner": "r9aZRryD8AZzGqQjYrQQuBBzebjF555Xsa",  # noqa: mock
                                    "RootIndex": "54A167B9559FAA8E617B87CE2F24702769BF18C20EE8BDB21025186B76479465",  # noqa: mock
                                },
                                "LedgerEntryType": "DirectoryNode",
                                "LedgerIndex": "54A167B9559FAA8E617B87CE2F24702769BF18C20EE8BDB21025186B76479465",  # noqa: mock
                            }
                        },
                        {
                            "CreatedNode": {
                                "LedgerEntryType": "DirectoryNode",
                                "LedgerIndex": "5C8970D155D65DB8FF49B291D7EFFA4A09F9E8A68D9974B25A07E6DEEEDC1281",  # noqa: mock
                                "NewFields": {
                                    "ExchangeRate": "5a07e6deeedc1281",  # noqa: mock
                                    "RootIndex": "5C8970D155D65DB8FF49B291D7EFFA4A09F9E8A68D9974B25A07E6DEEEDC1281",  # noqa: mock
                                    "TakerGetsCurrency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "TakerGetsIssuer": "1EB3EAA3AD86242E1D51DC502DD6566BD39E06A6",  # noqa: mock
                                },
                            }
                        },
                        {
                            "ModifiedNode": {
                                "FinalFields": {
                                    "Flags": 0,
                                    "Owner": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                    "RootIndex": "96A6199A80137B4B000352202D95C7F977EEBED39070B485D41903BD991E1F4B",  # noqa: mock
                                },
                                "LedgerEntryType": "DirectoryNode",
                                "LedgerIndex": "96A6199A80137B4B000352202D95C7F977EEBED39070B485D41903BD991E1F4B",  # noqa: mock
                            }
                        },
                        {
                            "DeletedNode": {
                                "FinalFields": {
                                    "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                    "BookDirectory": "C73FAC6C294EBA5B9E22A8237AAE80725E85372510A6CA794F0FF88501536AF6",  # noqa: mock
                                    "BookNode": "0",
                                    "Flags": 131072,
                                    "OwnerNode": "0",
                                    "PreviousTxnID": "6D0197A7D6CA87B2C90A92C80ACBC5DDB39C21BDCA9C60EAB49D7506BA560119",  # noqa: mock
                                    "PreviousTxnLgrSeq": 88824963,
                                    "Sequence": 84436571,
                                    "TakerGets": "0",
                                    "TakerPays": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                        "value": "0",
                                    },
                                },
                                "LedgerEntryType": "Offer",
                                "LedgerIndex": "AFAE88AD69BC25C5DF122C38DF727F41C8F1793E2FA436382A093247BE2A3418",  # noqa: mock
                                "PreviousFields": {
                                    "TakerGets": "1249995",
                                    "TakerPays": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                        "value": "5.619196007179491",
                                    },
                                },
                            }
                        },
                        {
                            "ModifiedNode": {
                                "FinalFields": {
                                    "Balance": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",  # noqa: mock
                                        "value": "-75772.00199150676",
                                    },
                                    "Flags": 2228224,
                                    "HighLimit": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "r9aZRryD8AZzGqQjYrQQuBBzebjF555Xsa",  # noqa: mock
                                        "value": "100000000",
                                    },
                                    "HighNode": "0",
                                    "LowLimit": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                        "value": "0",
                                    },
                                    "LowNode": "3778",
                                },
                                "LedgerEntryType": "RippleState",
                                "LedgerIndex": "BF2F4026A88BF068A5DF2ADF7A22C67193DE3E57CAE95C520EE83D02EDDADE64",  # noqa: mock
                                "PreviousFields": {
                                    "Balance": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",  # noqa: mock
                                        "value": "-75777.62174943354",
                                    }
                                },
                                "PreviousTxnID": "D5E4213C132A2EBC09C7258D727CAAC2C04FE2D9A73BE2901A41975C27943044",  # noqa: mock
                                "PreviousTxnLgrSeq": 88824411,
                            }
                        },
                        {
                            "DeletedNode": {
                                "FinalFields": {
                                    "ExchangeRate": "4f0ff88501536af6",  # noqa: mock
                                    "Flags": 0,
                                    "RootIndex": "C73FAC6C294EBA5B9E22A8237AAE80725E85372510A6CA794F0FF88501536AF6",  # noqa: mock
                                    "TakerGetsCurrency": "0000000000000000000000000000000000000000",  # noqa: mock
                                    "TakerGetsIssuer": "0000000000000000000000000000000000000000",  # noqa: mock
                                    "TakerPaysCurrency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "TakerPaysIssuer": "1EB3EAA3AD86242E1D51DC502DD6566BD39E06A6",  # noqa: mock
                                },
                                "LedgerEntryType": "DirectoryNode",
                                "LedgerIndex": "C73FAC6C294EBA5B9E22A8237AAE80725E85372510A6CA794F0FF88501536AF6",  # noqa: mock
                            }
                        },
                        {
                            "CreatedNode": {
                                "LedgerEntryType": "Offer",
                                "LedgerIndex": "C8EA027E0D2E9D1627C0D1B41DCFD165A748D396B5B1FCDF2C201FA0CC97EF2D",  # noqa: mock
                                "NewFields": {
                                    "Account": "r9aZRryD8AZzGqQjYrQQuBBzebjF555Xsa",  # noqa: mock
                                    "BookDirectory": "5C8970D155D65DB8FF49B291D7EFFA4A09F9E8A68D9974B25A07E6DEEEDC1281",  # noqa: mock
                                    "Flags": 131072,
                                    "Sequence": 86464580,
                                    "TakerGets": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                        "value": "1347.603946992821",
                                    },
                                    "TakerPays": "299730027",
                                },
                            }
                        },
                        {
                            "ModifiedNode": {
                                "FinalFields": {
                                    "Balance": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",  # noqa: mock
                                        "value": "29.36723384518376",
                                    },
                                    "Flags": 1114112,
                                    "HighLimit": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                        "value": "0",
                                    },
                                    "HighNode": "3799",
                                    "LowLimit": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                        "value": "1000000000",
                                    },
                                    "LowNode": "0",
                                },
                                "LedgerEntryType": "RippleState",
                                "LedgerIndex": "E1C84325F137AD05CB78F59968054BCBFD43CB4E70F7591B6C3C1D1C7E44C6FC",  # noqa: mock
                                "PreviousFields": {
                                    "Balance": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",  # noqa: mock
                                        "value": "23.74803783800427",
                                    }
                                },
                                "PreviousTxnID": "5C537801A80FBB8D673B19B0C3BCBF5F85B2A380064FA133D1E328C88DFC73F1",  # noqa: mock
                                "PreviousTxnLgrSeq": 88824265,
                            }
                        },
                    ],
                    "TransactionIndex": 20,
                    "TransactionResult": "tesSUCCESS",
                },
                "tx": {
                    "Account": "r9aZRryD8AZzGqQjYrQQuBBzebjF555Xsa",  # noqa: mock
                    "Fee": "15",
                    "Flags": 524288,
                    "Memos": [
                        {
                            "Memo": {
                                "MemoData": "3559334C4E412D4D66496D4E7A576A6C7367724B74",  # noqa: mock
                                "MemoType": "696E7465726E616C6F726465726964",  # noqa: mock
                            }
                        }
                    ],
                    "Sequence": 86464580,
                    "SigningPubKey": "02DFB5DD7091EC6E99A12AD016439DBBBBB8F60438D17B21B97E9F83C57106F8DB",  # noqa: mock
                    "TakerGets": {
                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                        "value": "1353.223143",
                    },
                    "TakerPays": "300979832",
                    "TransactionType": "OfferCreate",
                    "TxnSignature": "30450221009A265D011DA57D9C9A9FC3657D5DFE249DBA5D3BD5819B90D3F97E121571F51F02207ACE9130D47AF28CCE24E4D07DC58E7B51B717CA0FCB2FDBB2C9630F72642AEB",  # noqa: mock
                    "date": 772221290,
                    "hash": "1B74D0FE8F6CBAC807D3C7137D4C265F49CBC30B3EC2FEB8F94CD0EB39162F41",  # noqa: mock
                    "inLedger": 88824964,
                    "ledger_index": 88824964,
                },
                "validated": True,
            }
        ]

        in_flight_order = InFlightOrder(
            client_order_id="hbot-1718906078435341-BSOXP61b56023518294a8eb046fb3701345edf3cf5",  # noqa: mock
            exchange_order_id="84436571-88824981",
            trading_pair="SOLO-XRP",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("0.222451"),
            amount=Decimal("5.619196007179491"),
            creation_timestamp=1718906078.0,
        )

        fetch_account_transactions_mock.return_value = transactions
        get_account_mock.return_value = "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK"  # noqa: mock

        trade_fills = self.async_run_with_timeout(self.connector._all_trade_updates_for_order(in_flight_order))

        self.assertEqual(len(trade_fills), 1)
        self.assertEqual(
            trade_fills[0].trade_id, "1B74D0FE8F6CBAC807D3C7137D4C265F49CBC30B3EC2FEB8F94CD0EB39162F41"  # noqa: mock
        )  # noqa: mock
        self.assertEqual(
            trade_fills[0].client_order_id,
            "hbot-1718906078435341-BSOXP61b56023518294a8eb046fb3701345edf3cf5",  # noqa: mock
        )
        self.assertEqual(trade_fills[0].exchange_order_id, "84436571-88824981")
        self.assertEqual(trade_fills[0].trading_pair, "SOLO-XRP")
        self.assertEqual(trade_fills[0].fill_timestamp, 1718906090)
        self.assertEqual(trade_fills[0].fill_price, Decimal("0.2224508627929896078790446618"))
        self.assertEqual(trade_fills[0].fill_base_amount, Decimal("5.619196007179491"))
        self.assertEqual(trade_fills[0].fill_quote_amount, Decimal("1.249995"))
        self.assertEqual(
            trade_fills[0].fee.percent,
            Decimal("0.01000000000000000020816681711721685132943093776702880859375"),  # noqa: mock
        )
        self.assertEqual(trade_fills[0].fee.percent_token, "XRP")
        self.assertEqual(trade_fills[0].fee.flat_fees, [])
        self.assertEqual(trade_fills[0].is_taker, True)

        transactions = [
            {
                "meta": {
                    "AffectedNodes": [
                        {
                            "ModifiedNode": {
                                "FinalFields": {
                                    "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                    "Balance": "59912051",
                                    "Flags": 0,
                                    "OwnerCount": 6,
                                    "Sequence": 84436575,
                                },
                                "LedgerEntryType": "AccountRoot",
                                "LedgerIndex": "2B3020738E7A44FBDE454935A38D77F12DC5A11E0FA6DAE2D9FCF4719FFAA3BC",  # noqa: mock
                                "PreviousFields": {"Balance": "61162046", "OwnerCount": 7},
                                "PreviousTxnID": "5220A3E8F0F1814621E6A346078A22F32596487FA8D0C35BCAF2CF1B2415B92C",  # noqa: mock
                                "PreviousTxnLgrSeq": 88824963,
                            }
                        },
                        {
                            "ModifiedNode": {
                                "FinalFields": {
                                    "Account": "r9aZRryD8AZzGqQjYrQQuBBzebjF555Xsa",  # noqa: mock
                                    "Balance": "41317279592",
                                    "Flags": 0,
                                    "OwnerCount": 14,
                                    "Sequence": 86464581,
                                },
                                "LedgerEntryType": "AccountRoot",
                                "LedgerIndex": "547BD7E3B75FDEE721B73AED1D39AD94D3250E520358CC6521F39F15C6ADE46D",  # noqa: mock
                                "PreviousFields": {"Balance": "41316029612", "OwnerCount": 13, "Sequence": 86464580},
                                "PreviousTxnID": "82BDFD72A5BD1A423E54C9C880DEDC3DC002261050001B04C28C00036640D591",  # noqa: mock
                                "PreviousTxnLgrSeq": 88824963,
                            }
                        },
                        {
                            "ModifiedNode": {
                                "FinalFields": {
                                    "Flags": 0,
                                    "Owner": "r9aZRryD8AZzGqQjYrQQuBBzebjF555Xsa",  # noqa: mock
                                    "RootIndex": "54A167B9559FAA8E617B87CE2F24702769BF18C20EE8BDB21025186B76479465",  # noqa: mock
                                },
                                "LedgerEntryType": "DirectoryNode",
                                "LedgerIndex": "54A167B9559FAA8E617B87CE2F24702769BF18C20EE8BDB21025186B76479465",  # noqa: mock
                            }
                        },
                        {
                            "CreatedNode": {
                                "LedgerEntryType": "DirectoryNode",
                                "LedgerIndex": "5C8970D155D65DB8FF49B291D7EFFA4A09F9E8A68D9974B25A07E6DEEEDC1281",  # noqa: mock
                                "NewFields": {
                                    "ExchangeRate": "5a07e6deeedc1281",  # noqa: mock
                                    "RootIndex": "5C8970D155D65DB8FF49B291D7EFFA4A09F9E8A68D9974B25A07E6DEEEDC1281",  # noqa: mock
                                    "TakerGetsCurrency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "TakerGetsIssuer": "1EB3EAA3AD86242E1D51DC502DD6566BD39E06A6",  # noqa: mock
                                },
                            }
                        },
                        {
                            "ModifiedNode": {
                                "FinalFields": {
                                    "Flags": 0,
                                    "Owner": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                    "RootIndex": "96A6199A80137B4B000352202D95C7F977EEBED39070B485D41903BD991E1F4B",  # noqa: mock
                                },
                                "LedgerEntryType": "DirectoryNode",
                                "LedgerIndex": "96A6199A80137B4B000352202D95C7F977EEBED39070B485D41903BD991E1F4B",  # noqa: mock
                            }
                        },
                        {
                            "DeletedNode": {
                                "FinalFields": {
                                    "Account": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                    "BookDirectory": "C73FAC6C294EBA5B9E22A8237AAE80725E85372510A6CA794F0FF88501536AF6",  # noqa: mock
                                    "BookNode": "0",
                                    "Flags": 131072,
                                    "OwnerNode": "0",
                                    "PreviousTxnID": "6D0197A7D6CA87B2C90A92C80ACBC5DDB39C21BDCA9C60EAB49D7506BA560119",  # noqa: mock
                                    "PreviousTxnLgrSeq": 88824963,
                                    "Sequence": 84436571,
                                    "TakerGets": "0",
                                    "TakerPays": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                        "value": "0",
                                    },
                                },
                                "LedgerEntryType": "Offer",
                                "LedgerIndex": "AFAE88AD69BC25C5DF122C38DF727F41C8F1793E2FA436382A093247BE2A3418",  # noqa: mock
                                "PreviousFields": {
                                    "TakerGets": "1249995",
                                    "TakerPays": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                        "value": "5.619196007179491",
                                    },
                                },
                            }
                        },
                        {
                            "ModifiedNode": {
                                "FinalFields": {
                                    "Balance": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",  # noqa: mock
                                        "value": "-75772.00199150676",
                                    },
                                    "Flags": 2228224,
                                    "HighLimit": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "r9aZRryD8AZzGqQjYrQQuBBzebjF555Xsa",  # noqa: mock
                                        "value": "100000000",
                                    },
                                    "HighNode": "0",
                                    "LowLimit": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                        "value": "0",
                                    },
                                    "LowNode": "3778",
                                },
                                "LedgerEntryType": "RippleState",
                                "LedgerIndex": "BF2F4026A88BF068A5DF2ADF7A22C67193DE3E57CAE95C520EE83D02EDDADE64",  # noqa: mock
                                "PreviousFields": {
                                    "Balance": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",  # noqa: mock
                                        "value": "-75777.62174943354",
                                    }
                                },
                                "PreviousTxnID": "D5E4213C132A2EBC09C7258D727CAAC2C04FE2D9A73BE2901A41975C27943044",  # noqa: mock
                                "PreviousTxnLgrSeq": 88824411,
                            }
                        },
                        {
                            "DeletedNode": {
                                "FinalFields": {
                                    "ExchangeRate": "4f0ff88501536af6",  # noqa: mock
                                    "Flags": 0,
                                    "RootIndex": "C73FAC6C294EBA5B9E22A8237AAE80725E85372510A6CA794F0FF88501536AF6",  # noqa: mock
                                    "TakerGetsCurrency": "0000000000000000000000000000000000000000",  # noqa: mock
                                    "TakerGetsIssuer": "0000000000000000000000000000000000000000",  # noqa: mock
                                    "TakerPaysCurrency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "TakerPaysIssuer": "1EB3EAA3AD86242E1D51DC502DD6566BD39E06A6",  # noqa: mock
                                },
                                "LedgerEntryType": "DirectoryNode",
                                "LedgerIndex": "C73FAC6C294EBA5B9E22A8237AAE80725E85372510A6CA794F0FF88501536AF6",  # noqa: mock
                            }
                        },
                        {
                            "CreatedNode": {
                                "LedgerEntryType": "Offer",
                                "LedgerIndex": "C8EA027E0D2E9D1627C0D1B41DCFD165A748D396B5B1FCDF2C201FA0CC97EF2D",  # noqa: mock
                                "NewFields": {
                                    "Account": "r9aZRryD8AZzGqQjYrQQuBBzebjF555Xsa",  # noqa: mock
                                    "BookDirectory": "5C8970D155D65DB8FF49B291D7EFFA4A09F9E8A68D9974B25A07E6DEEEDC1281",  # noqa: mock
                                    "Flags": 131072,
                                    "Sequence": 86464580,
                                    "TakerGets": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                        "value": "1347.603946992821",
                                    },
                                    "TakerPays": "299730027",
                                },
                            }
                        },
                        {
                            "ModifiedNode": {
                                "FinalFields": {
                                    "Balance": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",  # noqa: mock
                                        "value": "29.36723384518376",
                                    },
                                    "Flags": 1114112,
                                    "HighLimit": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                                        "value": "0",
                                    },
                                    "HighNode": "3799",
                                    "LowLimit": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
                                        "value": "1000000000",
                                    },
                                    "LowNode": "0",
                                },
                                "LedgerEntryType": "RippleState",
                                "LedgerIndex": "E1C84325F137AD05CB78F59968054BCBFD43CB4E70F7591B6C3C1D1C7E44C6FC",  # noqa: mock
                                "PreviousFields": {
                                    "Balance": {
                                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                        "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",  # noqa: mock
                                        "value": "23.74803783800427",
                                    }
                                },
                                "PreviousTxnID": "5C537801A80FBB8D673B19B0C3BCBF5F85B2A380064FA133D1E328C88DFC73F1",  # noqa: mock
                                "PreviousTxnLgrSeq": 88824265,
                            }
                        },
                    ],
                    "TransactionIndex": 20,
                    "TransactionResult": "tesSUCCESS",
                },
                "tx": {
                    "Account": "r9aZRryD8AZzGqQjYrQQuBBzebjF555Xsa",  # noqa: mock
                    "Fee": "15",
                    "Flags": 524288,
                    "Memos": [
                        {
                            "Memo": {
                                "MemoData": "3559334C4E412D4D66496D4E7A576A6C7367724B74",  # noqa: mock
                                "MemoType": "696E7465726E616C6F726465726964",  # noqa: mock
                            }
                        }
                    ],
                    "Sequence": 84436571,
                    "SigningPubKey": "02DFB5DD7091EC6E99A12AD016439DBBBBB8F60438D17B21B97E9F83C57106F8DB",  # noqa: mock
                    "TakerGets": {
                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",  # noqa: mock
                        "value": "1353.223143",
                    },
                    "TakerPays": "300979832",
                    "TransactionType": "OfferCreate",
                    "TxnSignature": "30450221009A265D011DA57D9C9A9FC3657D5DFE249DBA5D3BD5819B90D3F97E121571F51F02207ACE9130D47AF28CCE24E4D07DC58E7B51B717CA0FCB2FDBB2C9630F72642AEB",  # noqa: mock
                    "date": 772221290,
                    "hash": "1B74D0FE8F6CBAC807D3C7137D4C265F49CBC30B3EC2FEB8F94CD0EB39162F41",  # noqa: mock
                    "inLedger": 88824981,
                    "ledger_index": 88824981,
                },
                "validated": True,
            }
        ]

        fetch_account_transactions_mock.return_value = transactions

        in_flight_order = InFlightOrder(
            client_order_id="hbot-1718906078435341-BSOXP61b56023518294a8eb046fb3701345edf3cf5",  # noqa: mock
            exchange_order_id="84436571-88824981",
            trading_pair="SOLO-XRP",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("0.222451"),
            amount=Decimal("5.619196007179491"),
            creation_timestamp=1718906078.0,
        )

        trade_fills = self.async_run_with_timeout(self.connector._all_trade_updates_for_order(in_flight_order))

        self.assertEqual(len(trade_fills), 1)
        self.assertEqual(
            trade_fills[0].trade_id, "1B74D0FE8F6CBAC807D3C7137D4C265F49CBC30B3EC2FEB8F94CD0EB39162F41"  # noqa: mock
        )
        self.assertEqual(
            trade_fills[0].client_order_id,
            "hbot-1718906078435341-BSOXP61b56023518294a8eb046fb3701345edf3cf5",  # noqa: mock
        )
        self.assertEqual(trade_fills[0].exchange_order_id, "84436571-88824981")
        self.assertEqual(trade_fills[0].trading_pair, "SOLO-XRP")
        self.assertEqual(trade_fills[0].fill_timestamp, 1718906090)
        self.assertEqual(trade_fills[0].fill_price, Decimal("4.417734611892777801348826549"))
        self.assertEqual(trade_fills[0].fill_base_amount, Decimal("306.599028007179491"))
        self.assertEqual(trade_fills[0].fill_quote_amount, Decimal("1354.473138"))

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange.request_with_retry")
    def test_fetch_account_transactions(self, request_with_retry_mock, get_account_mock):

        get_account_mock.return_value = "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK"  # noqa: mock
        request_with_retry_mock.return_value = Response(
            status=ResponseStatus.SUCCESS,
            result={"transactions": ["something"]},
            id="account_info_644216",
            type=ResponseType.RESPONSE,
        )

        txs = self.async_run_with_timeout(self.connector._fetch_account_transactions(ledger_index=88824981))
        self.assertEqual(len(txs), 1)

    def test_tx_submit(self):
        mock_client = AsyncMock()
        mock_client._request_impl.return_value = Response(
            status=ResponseStatus.SUCCESS,
            result={"transactions": ["something"]},
            id="something_1234",
            type=ResponseType.RESPONSE,
        )

        some_tx = OfferCancel(account="r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK", offer_sequence=88824981)

        resp = self.async_run_with_timeout(self.connector.tx_submit(some_tx, mock_client))
        self.assertEqual(resp.status, ResponseStatus.SUCCESS)

        # check if there is exception if response status is not success
        mock_client._request_impl.return_value = Response(
            status=ResponseStatus.ERROR,
            result={"error": "something"},
            id="something_1234",
            type=ResponseType.RESPONSE,
        )

        with self.assertRaises(XRPLRequestFailureException) as context:
            self.async_run_with_timeout(self.connector.tx_submit(some_tx, mock_client))

        self.assertTrue("something" in str(context.exception))
