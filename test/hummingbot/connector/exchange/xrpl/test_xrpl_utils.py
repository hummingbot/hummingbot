import asyncio
import unittest
from typing import Awaitable
from unittest.mock import AsyncMock

from xrpl.asyncio.clients import XRPLRequestFailureException
from xrpl.asyncio.transaction import XRPLReliableSubmissionException
from xrpl.models import OfferCancel, Response
from xrpl.models.response import ResponseStatus

from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange.xrpl.xrpl_utils import (
    XRPLConfigMap,
    _wait_for_final_transaction_outcome,
    autofill,
    compute_order_book_changes,
)


class TestXRPLUtils(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

    def setUp(self) -> None:
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 5):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

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

    def test_full_node(self):
        # Mock a fully populated NormalizedNode
        metadata = self._event_message_limit_order_partially_filled().get("meta")
        result = compute_order_book_changes(metadata)

        print(result)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].get("maker_account"), "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK")
        self.assertEqual(len(result[0].get("offer_changes")), 1)
        self.assertEqual(result[0].get("offer_changes")[0].get("flags"), 131072)
        self.assertEqual(result[0].get("offer_changes")[0].get("taker_gets"), {"currency": "XRP", "value": "-0.333299"})
        self.assertEqual(
            result[0].get("offer_changes")[0].get("taker_pays"),
            {
                "currency": "534F4C4F00000000000000000000000000000000",
                "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
                "value": "-1.479368155160603",
            },
        )
        self.assertEqual(result[0].get("offer_changes")[0].get("sequence"), 84437895)
        self.assertEqual(result[0].get("offer_changes")[0].get("status"), "partially-filled")
        self.assertEqual(result[0].get("offer_changes")[0].get("maker_exchange_rate"), "4.438561637330454036765786876")

    def test_validate_xrpl_secret_key_valid(self):
        valid_key = "sEdTvpec3RNNWwphd1WKZqt5Vs6GEFu"  # noqa: mock
        self.assertEqual(XRPLConfigMap.validate_xrpl_secret_key(valid_key), valid_key)

    def test_validate_xrpl_secret_key_invalid(self):
        invalid_key = "xINVALIDKEY"
        with self.assertRaises(ValueError) as context:
            XRPLConfigMap.validate_xrpl_secret_key(invalid_key)
        self.assertIn("Invalid XRPL wallet secret key", str(context.exception))

    def test_validate_wss_node_url_valid(self):
        valid_url = "wss://s1.ripple.com/"
        self.assertEqual(XRPLConfigMap.validate_wss_node_url(valid_url), valid_url)

    def test_validate_wss_node_url_invalid(self):
        invalid_url = "http://invalid.url"
        with self.assertRaises(ValueError) as context:
            XRPLConfigMap.validate_wss_node_url(invalid_url)
        self.assertIn("Invalid node url", str(context.exception))

    def test_validate_wss_second_node_url_valid(self):
        valid_url = "wss://s2.ripple.com/"
        self.assertEqual(XRPLConfigMap.validate_wss_second_node_url(valid_url), valid_url)

    def test_validate_wss_second_node_url_invalid(self):
        invalid_url = "https://invalid.url"
        with self.assertRaises(ValueError) as context:
            XRPLConfigMap.validate_wss_second_node_url(invalid_url)
        self.assertIn("Invalid node url", str(context.exception))

    def test_auto_fill(self):
        client = AsyncMock()

        request = OfferCancel(
            account="rsoLoDTcxn9wCEHHBR7enMhzQMThkB2w28", # noqa: mock
            offer_sequence=69870875,
        )

        client.network_id = None
        client.build_version = None
        client._request_impl.return_value = Response(
            status=ResponseStatus.SUCCESS,
            result={
                "info": {"network_id": 1026, "build_version": "1.11.1"},
                "account_data": {"Sequence": 99999911},
                "drops": {
                    "open_ledger_fee": "10",
                    "minimum_fee": "10",
                },
                "ledger_index": 99999221,
            },
        )

        filled_request = self.async_run_with_timeout(autofill(request, client))

        self.assertIsInstance(filled_request, OfferCancel)
        self.assertEqual(filled_request.fee, str(10 * CONSTANTS.FEE_MULTIPLIER))
        self.assertEqual(filled_request.last_ledger_sequence, 99999221 + 20)
        self.assertEqual(filled_request.network_id, 1026)

        client._request_impl.side_effect = Exception("Error")

        with self.assertRaises(Exception):
            self.async_run_with_timeout(autofill(request, client))

    def test_wait_for_final_transaction_outcome(self):
        client = AsyncMock()
        client.network_id = None
        client.build_version = None
        client._request_impl.return_value = Response(
            status=ResponseStatus.SUCCESS,
            result={
                "ledger_index": 99999221,
                "validated": True,
                "meta": {
                    "TransactionResult": "tesSUCCESS",
                },
            },
        )

        with self.assertRaises(XRPLReliableSubmissionException):
            self.async_run_with_timeout(
                _wait_for_final_transaction_outcome("transaction_hash", client, "something", 12345)
            )

        with self.assertRaises(XRPLRequestFailureException):
            client._request_impl.return_value = Response(
                status=ResponseStatus.ERROR,
                result={"error": "something happened"},
            )
            self.async_run_with_timeout(
                _wait_for_final_transaction_outcome("transaction_hash", client, "something", 12345)
            )

        with self.assertRaises(XRPLReliableSubmissionException):
            client._request_impl.return_value = Response(
                status=ResponseStatus.SUCCESS,
                result={
                    "ledger_index": 99999221,
                    "validated": True,
                    "meta": {
                        "TransactionResult": "tecKilled",
                    },
                },
            )
            self.async_run_with_timeout(
                _wait_for_final_transaction_outcome("transaction_hash", client, "something", 12345)
            )

        client._request_impl.return_value = Response(
            status=ResponseStatus.SUCCESS,
            result={
                "ledger_index": 99999221,
                "validated": True,
                "meta": {
                    "TransactionResult": "tesSUCCESS",
                },
            },
        )

        response = self.async_run_with_timeout(
            _wait_for_final_transaction_outcome("transaction_hash", client, "something", 1234500000)
        )

        self.assertEqual(response.result["ledger_index"], 99999221)
        self.assertEqual(response.result["validated"], True)
        self.assertEqual(response.result["meta"]["TransactionResult"], "tesSUCCESS")
