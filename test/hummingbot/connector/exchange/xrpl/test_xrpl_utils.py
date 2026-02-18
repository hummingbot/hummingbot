import asyncio
import time
from collections import deque
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from xrpl.asyncio.clients import AsyncWebsocketClient, XRPLRequestFailureException
from xrpl.asyncio.transaction import XRPLReliableSubmissionException
from xrpl.models import OfferCancel, Response
from xrpl.models.response import ResponseStatus

from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange.xrpl.xrpl_utils import (
    RateLimiter,
    XRPLConfigMap,
    XRPLConnection,
    XRPLConnectionError,
    XRPLNodePool,
    _wait_for_final_transaction_outcome,
    autofill,
    compute_order_book_changes,
    convert_string_to_hex,
    get_latest_validated_ledger_sequence,
    get_token_from_changes,
    parse_offer_create_transaction,
)


class TestXRPLUtils(IsolatedAsyncioWrapperTestCase):

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
        if metadata is None:
            self.skipTest("metadata is None, skipping test to avoid type error.")
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

    def test_validate_wss_node_url_valid(self):
        valid_url = "wss://s1.ripple.com/,wss://s2.ripple.com/"
        self.assertEqual(
            XRPLConfigMap.validate_wss_node_urls(valid_url), ["wss://s1.ripple.com/", "wss://s2.ripple.com/"]
        )

    def test_validate_wss_node_url_invalid(self):
        invalid_url = "http://invalid.url"
        with self.assertRaises(ValueError) as context:
            XRPLConfigMap.validate_wss_node_urls(invalid_url)
        self.assertIn("Invalid node url", str(context.exception))

    async def test_auto_fill(self):
        client = AsyncMock()

        request = OfferCancel(
            account="rsoLoDTcxn9wCEHHBR7enMhzQMThkB2w28",  # noqa: mock
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

        filled_request = await autofill(request, client)

        self.assertIsInstance(filled_request, OfferCancel)
        self.assertEqual(filled_request.fee, str(10 * CONSTANTS.FEE_MULTIPLIER))
        self.assertEqual(filled_request.last_ledger_sequence, 99999221 + 20)
        self.assertEqual(filled_request.network_id, 1026)

        client._request_impl.side_effect = Exception("Error")

        with self.assertRaises(Exception):
            await autofill(request, client)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_utils._sleep")
    async def test_wait_for_final_transaction_outcome(self, _):
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
            await _wait_for_final_transaction_outcome("transaction_hash", client, "something", 12345)

        with self.assertRaises(XRPLRequestFailureException):
            client._request_impl.return_value = Response(
                status=ResponseStatus.ERROR,
                result={"error": "something happened"},
            )
            await _wait_for_final_transaction_outcome("transaction_hash", client, "something", 12345)

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
            await _wait_for_final_transaction_outcome("transaction_hash", client, "something", 12345)

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

        response = await _wait_for_final_transaction_outcome("transaction_hash", client, "something", 1234500000)

        self.assertEqual(response.result["ledger_index"], 99999221)
        self.assertEqual(response.result["validated"], True)
        self.assertEqual(response.result["meta"]["TransactionResult"], "tesSUCCESS")


class TestRateLimiter(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        self.rate_limiter = RateLimiter(requests_per_10s=10.0, burst_tokens=2, max_burst_tokens=5)

    def test_initialization(self):
        self.assertEqual(self.rate_limiter._rate_limit, 10.0)
        self.assertEqual(self.rate_limiter._burst_tokens, 2)
        self.assertEqual(self.rate_limiter._max_burst_tokens, 5)
        self.assertEqual(len(self.rate_limiter._request_times), 0)

    def test_add_burst_tokens(self):
        # Test adding tokens within max limit
        self.rate_limiter.add_burst_tokens(2)
        self.assertEqual(self.rate_limiter.burst_tokens, 4)

        # Test adding tokens exceeding max limit
        self.rate_limiter.add_burst_tokens(5)
        self.assertEqual(self.rate_limiter.burst_tokens, 5)  # Should cap at max_burst_tokens

        # Test adding negative tokens
        self.rate_limiter.add_burst_tokens(-1)
        self.assertEqual(self.rate_limiter.burst_tokens, 5)  # Should not change

    def test_calculate_current_rate(self):
        # Test with no requests
        self.assertEqual(self.rate_limiter._calculate_current_rate(), 0.0)

        # Add some requests
        now = time.time()
        self.rate_limiter._request_times.extend([now - 5, now - 3, now - 1])
        rate = self.rate_limiter._calculate_current_rate()
        self.assertGreater(rate, 0.0)
        self.assertLess(rate, 10.0)  # Should be less than rate limit

        # Test with old requests (should be filtered out)
        self.rate_limiter._request_times.extend([now - 20, now - 15])
        rate = self.rate_limiter._calculate_current_rate()
        self.assertLess(rate, 10.0)  # Old requests should be filtered out

    async def test_acquire(self):
        # Test with burst token
        wait_time = await self.rate_limiter.acquire(use_burst=True)
        self.assertEqual(wait_time, 0.0)
        self.assertEqual(self.rate_limiter.burst_tokens, 1)  # One token used

        # Test without burst token, under rate limit
        now = time.time()
        self.rate_limiter._request_times.extend([now - i for i in range(8)])  # Add 8 requests
        wait_time = await self.rate_limiter.acquire(use_burst=False)
        self.assertEqual(wait_time, 0.0)

        # Test without burst token, over rate limit
        now = time.time()
        self.rate_limiter._request_times.extend([now - i for i in range(15)])  # Add 15 requests
        wait_time = await self.rate_limiter.acquire(use_burst=False)
        self.assertGreater(wait_time, 0.0)  # Should need to wait


class TestParseOfferCreateTransaction(IsolatedAsyncioWrapperTestCase):
    def test_normal_offer_node(self):
        tx = {
            "Account": "acc1",
            "Sequence": 123,
            "meta": {
                "AffectedNodes": [
                    {
                        "ModifiedNode": {
                            "LedgerEntryType": "Offer",
                            "FinalFields": {
                                "Account": "acc1",
                                "Sequence": 123,
                                "TakerGets": "10",
                                "TakerPays": {"value": "20"},
                            },
                            "PreviousFields": {"TakerGets": "15", "TakerPays": {"value": "30"}},
                        }
                    }
                ]
            },
        }
        result = parse_offer_create_transaction(tx)
        self.assertAlmostEqual(result["taker_gets_transferred"], 5)
        self.assertAlmostEqual(result["taker_pays_transferred"], 10)
        self.assertAlmostEqual(result["quality"], 2)

    def test_no_meta(self):
        tx = {"Account": "acc1", "Sequence": 1}
        result = parse_offer_create_transaction(tx)
        self.assertIsNone(result["quality"])
        self.assertIsNone(result["taker_gets_transferred"])
        self.assertIsNone(result["taker_pays_transferred"])

    def test_no_offer_node(self):
        tx = {"Account": "acc1", "Sequence": 1, "meta": {"AffectedNodes": []}}
        result = parse_offer_create_transaction(tx)
        self.assertIsNone(result["quality"])
        self.assertIsNone(result["taker_gets_transferred"])
        self.assertIsNone(result["taker_pays_transferred"])

    def test_offer_node_missing_previousfields(self):
        tx = {
            "Account": "acc1",
            "Sequence": 123,
            "meta": {
                "AffectedNodes": [
                    {
                        "ModifiedNode": {
                            "LedgerEntryType": "Offer",
                            "FinalFields": {
                                "Account": "acc1",
                                "Sequence": 123,
                                "TakerGets": "10",
                                "TakerPays": {"value": "20"},
                            },
                        }
                    }
                ]
            },
        }
        result = parse_offer_create_transaction(tx)
        self.assertIsNone(result["quality"])
        self.assertIsNone(result["taker_gets_transferred"])
        self.assertIsNone(result["taker_pays_transferred"])

    def test_offer_node_int_and_dict_types(self):
        tx = {
            "Account": "acc1",
            "Sequence": 123,
            "meta": {
                "AffectedNodes": [
                    {
                        "ModifiedNode": {
                            "LedgerEntryType": "Offer",
                            "FinalFields": {
                                "Account": "acc1",
                                "Sequence": 123,
                                "TakerGets": 10,
                                "TakerPays": {"value": 20},
                            },
                            "PreviousFields": {"TakerGets": 15, "TakerPays": {"value": 30}},
                        }
                    }
                ]
            },
        }
        result = parse_offer_create_transaction(tx)
        self.assertAlmostEqual(result["taker_gets_transferred"], 5)
        self.assertAlmostEqual(result["taker_pays_transferred"], 10)
        self.assertAlmostEqual(result["quality"], 2)

    def test_offer_node_fallback_to_first_offer(self):
        tx = {
            "Account": "acc1",  # Different account than the offer node
            "Sequence": 999,  # Different sequence than the offer node
            "meta": {
                "AffectedNodes": [
                    {
                        "ModifiedNode": {
                            "LedgerEntryType": "Offer",
                            "FinalFields": {
                                "Account": "acc2",  # Different account
                                "Sequence": 456,  # Different sequence
                                "TakerGets": "100",
                                "TakerPays": {"value": "200"},
                            },
                            "PreviousFields": {"TakerGets": "150", "TakerPays": {"value": "300"}},
                        }
                    }
                ]
            },
        }
        result = parse_offer_create_transaction(tx)
        # Should still parse the offer node even though account/sequence don't match
        self.assertAlmostEqual(result["taker_gets_transferred"], 50)
        self.assertAlmostEqual(result["taker_pays_transferred"], 100)
        self.assertAlmostEqual(result["quality"], 2)

    def test_offer_node_mixed_types(self):
        tx = {
            "Account": "acc1",
            "Sequence": 123,
            "meta": {
                "AffectedNodes": [
                    {
                        "ModifiedNode": {
                            "LedgerEntryType": "Offer",
                            "FinalFields": {
                                "Account": "acc1",
                                "Sequence": 123,
                                "TakerGets": {"value": "100"},  # Dict with string
                                "TakerPays": {"value": "200"},  # Dict with string
                            },
                            "PreviousFields": {
                                "TakerGets": {"value": "150"},  # Dict with string
                                "TakerPays": {"value": "300"},  # Dict with string
                            },
                        }
                    }
                ]
            },
        }
        result = parse_offer_create_transaction(tx)
        self.assertAlmostEqual(result["taker_gets_transferred"], 50)  # 150 - 100
        self.assertAlmostEqual(result["taker_pays_transferred"], 100)  # 300 - 200
        self.assertAlmostEqual(result["quality"], 2)

    def test_offer_node_string_values(self):
        tx = {
            "Account": "acc1",
            "Sequence": 123,
            "meta": {
                "AffectedNodes": [
                    {
                        "ModifiedNode": {
                            "LedgerEntryType": "Offer",
                            "FinalFields": {
                                "Account": "acc1",
                                "Sequence": 123,
                                "TakerGets": "100",  # String
                                "TakerPays": "200",  # String
                            },
                            "PreviousFields": {
                                "TakerGets": "150",  # String
                                "TakerPays": "300",  # String
                            },
                        }
                    }
                ]
            },
        }
        result = parse_offer_create_transaction(tx)
        self.assertAlmostEqual(result["taker_gets_transferred"], 50)  # 150 - 100
        self.assertAlmostEqual(result["taker_pays_transferred"], 100)  # 300 - 200
        self.assertAlmostEqual(result["quality"], 2)

    def test_offer_node_int_values(self):
        tx = {
            "Account": "acc1",
            "Sequence": 123,
            "meta": {
                "AffectedNodes": [
                    {
                        "ModifiedNode": {
                            "LedgerEntryType": "Offer",
                            "FinalFields": {
                                "Account": "acc1",
                                "Sequence": 123,
                                "TakerGets": 100,  # Int
                                "TakerPays": 200,  # Int
                            },
                            "PreviousFields": {
                                "TakerGets": 150,  # Int
                                "TakerPays": 300,  # Int
                            },
                        }
                    }
                ]
            },
        }
        result = parse_offer_create_transaction(tx)
        self.assertAlmostEqual(result["taker_gets_transferred"], 50)  # 150 - 100
        self.assertAlmostEqual(result["taker_pays_transferred"], 100)  # 300 - 200
        self.assertAlmostEqual(result["quality"], 2)

    def test_offer_node_invalid_values(self):
        tx = {
            "Account": "acc1",
            "Sequence": 123,
            "meta": {
                "AffectedNodes": [
                    {
                        "ModifiedNode": {
                            "LedgerEntryType": "Offer",
                            "FinalFields": {
                                "Account": "acc1",
                                "Sequence": 123,
                                "TakerGets": "invalid",  # Invalid value
                                "TakerPays": {"value": "200"},
                            },
                            "PreviousFields": {
                                "TakerGets": "150",
                                "TakerPays": {"value": "300"},
                            },
                        }
                    }
                ]
            },
        }
        result = parse_offer_create_transaction(tx)
        self.assertIsNone(result["taker_gets_transferred"])  # Should be None due to invalid value
        self.assertAlmostEqual(result["taker_pays_transferred"], 100)
        self.assertIsNone(result["quality"])  # Should be None since taker_gets_transferred is None

    def test_offer_node_missing_value_key(self):
        tx = {
            "Account": "acc1",
            "Sequence": 123,
            "meta": {
                "AffectedNodes": [
                    {
                        "ModifiedNode": {
                            "LedgerEntryType": "Offer",
                            "FinalFields": {
                                "Account": "acc1",
                                "Sequence": 123,
                                "TakerGets": {"wrong_key": "100"},  # Missing "value" key
                                "TakerPays": {"value": "200"},
                            },
                            "PreviousFields": {
                                "TakerGets": "150",
                                "TakerPays": {"value": "300"},
                            },
                        }
                    }
                ]
            },
        }
        result = parse_offer_create_transaction(tx)
        self.assertIsNone(result["taker_gets_transferred"])  # Should be None due to missing value key
        self.assertAlmostEqual(result["taker_pays_transferred"], 100)
        self.assertIsNone(result["quality"])

    def test_offer_node_division_by_zero(self):
        tx = {
            "Account": "acc1",
            "Sequence": 123,
            "meta": {
                "AffectedNodes": [
                    {
                        "ModifiedNode": {
                            "LedgerEntryType": "Offer",
                            "FinalFields": {
                                "Account": "acc1",
                                "Sequence": 123,
                                "TakerGets": "100",
                                "TakerPays": {"value": "200"},
                            },
                            "PreviousFields": {
                                "TakerGets": "100",  # Same as final, so transferred = 0
                                "TakerPays": {"value": "300"},
                            },
                        }
                    }
                ]
            },
        }
        result = parse_offer_create_transaction(tx)
        self.assertAlmostEqual(result["taker_gets_transferred"], 0)
        self.assertAlmostEqual(result["taker_pays_transferred"], 100)
        self.assertIsNone(result["quality"])  # Should be None due to division by zero

    def test_offer_node_invalid_quality_calculation(self):
        tx = {
            "Account": "acc1",
            "Sequence": 123,
            "meta": {
                "AffectedNodes": [
                    {
                        "ModifiedNode": {
                            "LedgerEntryType": "Offer",
                            "FinalFields": {
                                "Account": "acc1",
                                "Sequence": 123,
                                "TakerGets": "100",
                                "TakerPays": {"value": "invalid"},  # Invalid value for pays
                            },
                            "PreviousFields": {
                                "TakerGets": "150",
                                "TakerPays": {"value": "300"},
                            },
                        }
                    }
                ]
            },
        }
        result = parse_offer_create_transaction(tx)
        self.assertAlmostEqual(result["taker_gets_transferred"], 50)
        self.assertIsNone(result["taker_pays_transferred"])  # Should be None due to invalid value
        self.assertIsNone(result["quality"])  # Should be None since taker_pays_transferred is None


class TestConvertStringToHex(IsolatedAsyncioWrapperTestCase):
    """Tests for convert_string_to_hex function."""

    def test_short_string_returned_as_is(self):
        """Strings of length <= 3 should be returned unchanged."""
        self.assertEqual(convert_string_to_hex("XRP"), "XRP")
        self.assertEqual(convert_string_to_hex("USD"), "USD")

    def test_long_string_converted_to_hex_with_padding(self):
        """Strings of length > 3 should be converted to uppercase hex with zero padding to 40 chars."""
        result = convert_string_to_hex("SOLO")
        self.assertEqual(len(result), 40)
        self.assertTrue(result.endswith("00"))
        self.assertEqual(result[:8], "534F4C4F")

    def test_long_string_no_padding(self):
        """Strings of length > 3 with padding=False should not be padded."""
        result = convert_string_to_hex("SOLO", padding=False)
        self.assertEqual(result, "534F4C4F")


class TestGetTokenFromChanges(IsolatedAsyncioWrapperTestCase):
    """Tests for get_token_from_changes function."""

    def test_token_found(self):
        changes = [
            {"currency": "XRP", "value": "100"},
            {"currency": "USD", "value": "50"},
        ]
        result = get_token_from_changes(changes, "USD")
        self.assertEqual(result, {"currency": "USD", "value": "50"})

    def test_token_not_found(self):
        changes = [
            {"currency": "XRP", "value": "100"},
        ]
        result = get_token_from_changes(changes, "USD")
        self.assertIsNone(result)

    def test_empty_changes(self):
        result = get_token_from_changes([], "XRP")
        self.assertIsNone(result)


class TestGetLatestValidatedLedgerSequence(IsolatedAsyncioWrapperTestCase):
    """Tests for get_latest_validated_ledger_sequence function."""

    async def test_successful_response(self):
        client = AsyncMock()
        client._request_impl.return_value = Response(
            status=ResponseStatus.SUCCESS,
            result={"ledger_index": 99999},
        )
        result = await get_latest_validated_ledger_sequence(client)
        self.assertEqual(result, 99999)

    async def test_failed_response_raises(self):
        client = AsyncMock()
        client._request_impl.return_value = Response(
            status=ResponseStatus.ERROR,
            result={"error": "some error"},
        )
        with self.assertRaises(XRPLRequestFailureException):
            await get_latest_validated_ledger_sequence(client)

    async def test_key_error_raises_connection_error(self):
        """KeyError during request should be converted to XRPLConnectionError (lines 269,272)."""
        client = AsyncMock()
        client._request_impl.side_effect = KeyError("missing_key")
        with self.assertRaises(XRPLConnectionError) as ctx:
            await get_latest_validated_ledger_sequence(client)
        self.assertIn("Request lost during reconnection", str(ctx.exception))


class TestWaitForFinalTransactionOutcomeKeyError(IsolatedAsyncioWrapperTestCase):
    """Test KeyError handling in _wait_for_final_transaction_outcome (lines 309,312)."""

    @patch("hummingbot.connector.exchange.xrpl.xrpl_utils._sleep")
    async def test_key_error_on_tx_query_raises_connection_error(self, _):
        """KeyError during Tx query should be converted to XRPLConnectionError."""
        client = AsyncMock()
        # First call for get_latest_validated_ledger_sequence succeeds
        client._request_impl.side_effect = [
            Response(status=ResponseStatus.SUCCESS, result={"ledger_index": 100}),
            KeyError("missing_key"),
        ]
        with self.assertRaises(XRPLConnectionError) as ctx:
            await _wait_for_final_transaction_outcome("hash123", client, "tesSUCCESS", 1234500000)
        self.assertIn("Request lost during reconnection", str(ctx.exception))

    @patch("hummingbot.connector.exchange.xrpl.xrpl_utils._sleep")
    async def test_txn_not_found_retries(self, _):
        """txnNotFound should cause a retry (recursive call)."""
        client = AsyncMock()
        # First call: ledger sequence (success), tx query (txnNotFound)
        # Second call: ledger sequence (success), tx query (success validated)
        client._request_impl.side_effect = [
            Response(status=ResponseStatus.SUCCESS, result={"ledger_index": 100}),
            Response(status=ResponseStatus.ERROR, result={"error": "txnNotFound"}),
            Response(status=ResponseStatus.SUCCESS, result={"ledger_index": 100}),
            Response(
                status=ResponseStatus.SUCCESS,
                result={"ledger_index": 101, "validated": True, "meta": {"TransactionResult": "tesSUCCESS"}},
            ),
        ]
        response = await _wait_for_final_transaction_outcome("hash123", client, "tesSUCCESS", 1234500000)
        self.assertTrue(response.result["validated"])


class TestXRPLConnectionMethods(IsolatedAsyncioWrapperTestCase):
    """Tests for XRPLConnection dataclass methods (lines 518-538)."""

    def test_update_latency_first_call(self):
        """First call sets avg_latency directly (line 518-519)."""
        conn = XRPLConnection(url="wss://test.com")
        self.assertEqual(conn.avg_latency, 0.0)
        conn.update_latency(0.5)
        self.assertEqual(conn.avg_latency, 0.5)

    def test_update_latency_subsequent_call(self):
        """Subsequent calls use exponential moving average (line 521)."""
        conn = XRPLConnection(url="wss://test.com")
        conn.update_latency(1.0)  # First: sets to 1.0
        conn.update_latency(0.5)  # EMA: 0.3 * 0.5 + 0.7 * 1.0 = 0.85
        self.assertAlmostEqual(conn.avg_latency, 0.85)

    def test_update_latency_custom_alpha(self):
        """Test with custom alpha value."""
        conn = XRPLConnection(url="wss://test.com")
        conn.update_latency(1.0)
        conn.update_latency(0.0, alpha=0.5)  # EMA: 0.5 * 0 + 0.5 * 1.0 = 0.5
        self.assertAlmostEqual(conn.avg_latency, 0.5)

    def test_record_success(self):
        """record_success increments request_count and resets consecutive_errors (lines 525-527)."""
        conn = XRPLConnection(url="wss://test.com")
        conn.consecutive_errors = 5
        before = time.time()
        conn.record_success()
        self.assertEqual(conn.request_count, 1)
        self.assertEqual(conn.consecutive_errors, 0)
        self.assertGreaterEqual(conn.last_used, before)

    def test_record_error(self):
        """record_error increments error_count and consecutive_errors (lines 531-533)."""
        conn = XRPLConnection(url="wss://test.com")
        before = time.time()
        conn.record_error()
        self.assertEqual(conn.error_count, 1)
        self.assertEqual(conn.consecutive_errors, 1)
        self.assertGreaterEqual(conn.last_used, before)

        conn.record_error()
        self.assertEqual(conn.error_count, 2)
        self.assertEqual(conn.consecutive_errors, 2)

    def test_age_property(self):
        """age returns seconds since creation (line 538)."""
        conn = XRPLConnection(url="wss://test.com")
        # age should be very small (just created)
        self.assertGreaterEqual(conn.age, 0.0)
        self.assertLess(conn.age, 2.0)

    def test_is_open_with_closed_client(self):
        """is_open returns False when client is closed."""
        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.is_open.return_value = False
        conn = XRPLConnection(url="wss://test.com", client=mock_client)
        self.assertFalse(conn.is_open)

    def test_is_open_with_open_client(self):
        """is_open returns True when client is open."""
        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.is_open.return_value = True
        conn = XRPLConnection(url="wss://test.com", client=mock_client)
        self.assertTrue(conn.is_open)


class TestXRPLNodePoolStartStop(IsolatedAsyncioWrapperTestCase):
    """Tests for XRPLNodePool start/stop lifecycle (lines 758-835)."""

    async def test_start_no_successful_connections(self):
        """When all connections fail, pool should still start in degraded mode (line 782-783)."""
        pool = XRPLNodePool(node_urls=["wss://fail1.com", "wss://fail2.com"])
        with patch.object(pool, "_init_connection", new_callable=AsyncMock) as mock_init:
            mock_init.return_value = False
            await pool.start()
            self.assertTrue(pool._running)
            self.assertEqual(mock_init.call_count, 2)
        await pool.stop()

    async def test_stop_closes_open_connections(self):
        """Stop should close all open connections (lines 822-833)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        pool._running = True

        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.is_open.return_value = True
        mock_client.close = AsyncMock()

        conn = XRPLConnection(url="wss://test.com", client=mock_client)
        pool._connections["wss://test.com"] = conn
        pool._healthy_connections.append("wss://test.com")

        # Create fake tasks that can be cancelled
        pool._health_check_task = asyncio.create_task(asyncio.sleep(100))
        pool._proactive_ping_task = asyncio.create_task(asyncio.sleep(100))

        await pool.stop()

        self.assertFalse(pool._running)
        self.assertEqual(len(pool._connections), 0)
        self.assertEqual(len(pool._healthy_connections), 0)
        mock_client.close.assert_called_once()


class TestXRPLNodePoolCloseConnectionSafe(IsolatedAsyncioWrapperTestCase):
    """Tests for _close_connection_safe (lines 839-843)."""

    async def test_close_connection_safe_success(self):
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        mock_client = AsyncMock()
        conn = XRPLConnection(url="wss://test.com", client=mock_client)
        await pool._close_connection_safe(conn)
        mock_client.close.assert_called_once()

    async def test_close_connection_safe_exception(self):
        """Should not raise even when close() raises (line 842-843)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        mock_client = AsyncMock()
        mock_client.close.side_effect = Exception("close failed")
        conn = XRPLConnection(url="wss://test.com", client=mock_client)
        # Should not raise
        await pool._close_connection_safe(conn)

    async def test_close_connection_safe_no_client(self):
        """Should handle conn with no client."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        conn = XRPLConnection(url="wss://test.com", client=None)
        # Should not raise
        await pool._close_connection_safe(conn)


class TestXRPLNodePoolInitConnection(IsolatedAsyncioWrapperTestCase):
    """Tests for _init_connection (lines 845-896)."""

    async def test_init_connection_success(self):
        """Successful connection should be added to pool (lines 880-888)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])

        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.is_open.return_value = True
        mock_client._websocket = MagicMock()
        mock_client.open = AsyncMock()
        mock_client._request_impl = AsyncMock(
            return_value=Response(status=ResponseStatus.SUCCESS, result={"info": {}})
        )

        with patch("hummingbot.connector.exchange.xrpl.xrpl_utils.AsyncWebsocketClient", return_value=mock_client):
            result = await pool._init_connection("wss://test.com")

        self.assertTrue(result)
        self.assertIn("wss://test.com", pool._connections)
        self.assertIn("wss://test.com", pool._healthy_connections)

    async def test_init_connection_server_info_failure(self):
        """Failed ServerInfo should close client and return False (lines 875-878)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])

        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client._websocket = MagicMock()
        mock_client.open = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client._request_impl = AsyncMock(
            return_value=Response(status=ResponseStatus.ERROR, result={"error": "fail"})
        )

        with patch("hummingbot.connector.exchange.xrpl.xrpl_utils.AsyncWebsocketClient", return_value=mock_client):
            result = await pool._init_connection("wss://test.com")

        self.assertFalse(result)
        mock_client.close.assert_called_once()

    async def test_init_connection_timeout(self):
        """Timeout should return False (lines 891-893)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"], connection_timeout=0.01)

        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.open = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch("hummingbot.connector.exchange.xrpl.xrpl_utils.AsyncWebsocketClient", return_value=mock_client):
            result = await pool._init_connection("wss://test.com")

        self.assertFalse(result)

    async def test_init_connection_general_exception(self):
        """General exception should return False (lines 894-896)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])

        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.open = AsyncMock(side_effect=ConnectionError("refused"))

        with patch("hummingbot.connector.exchange.xrpl.xrpl_utils.AsyncWebsocketClient", return_value=mock_client):
            result = await pool._init_connection("wss://test.com")

        self.assertFalse(result)


class TestXRPLNodePoolGetClient(IsolatedAsyncioWrapperTestCase):
    """Tests for get_client (lines 898-976)."""

    async def test_get_client_returns_healthy_connection(self):
        """Should return client from a healthy, open connection (lines 930-957)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        pool._init_time = 0  # Ensure rate limiting applies

        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.is_open.return_value = True

        conn = XRPLConnection(url="wss://test.com", client=mock_client, is_healthy=True)
        pool._connections["wss://test.com"] = conn
        pool._healthy_connections.append("wss://test.com")

        # Mock rate limiter to not delay
        with patch.object(pool._rate_limiter, "acquire", new_callable=AsyncMock, return_value=0.0):
            result = await pool.get_client()
        self.assertIs(result, mock_client)

    async def test_get_client_skips_closed_connection(self):
        """Closed connections should be skipped and trigger reconnection (lines 938-943)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        pool._init_time = 0

        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.is_open.return_value = False

        conn = XRPLConnection(url="wss://test.com", client=mock_client, is_healthy=True)
        pool._connections["wss://test.com"] = conn
        pool._healthy_connections.append("wss://test.com")

        with patch.object(pool._rate_limiter, "acquire", new_callable=AsyncMock, return_value=0.0), \
             patch.object(pool, "_reconnect", new_callable=AsyncMock):
            with self.assertRaises(XRPLConnectionError):
                await pool.get_client()

    async def test_get_client_skips_unhealthy_connection(self):
        """Unhealthy connections should be skipped (lines 946-947)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        pool._init_time = 0

        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.is_open.return_value = True

        conn = XRPLConnection(url="wss://test.com", client=mock_client, is_healthy=False)
        pool._connections["wss://test.com"] = conn
        pool._healthy_connections.append("wss://test.com")

        with patch.object(pool._rate_limiter, "acquire", new_callable=AsyncMock, return_value=0.0):
            with self.assertRaises(XRPLConnectionError):
                await pool.get_client()

    async def test_get_client_skips_reconnecting_connection(self):
        """Reconnecting connections should be skipped (lines 951-953)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        pool._init_time = 0

        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.is_open.return_value = True

        conn = XRPLConnection(url="wss://test.com", client=mock_client, is_healthy=True, is_reconnecting=True)
        pool._connections["wss://test.com"] = conn
        pool._healthy_connections.append("wss://test.com")

        with patch.object(pool._rate_limiter, "acquire", new_callable=AsyncMock, return_value=0.0):
            with self.assertRaises(XRPLConnectionError):
                await pool.get_client()

    async def test_get_client_with_rate_limit_wait(self):
        """Rate limiter returning wait > 0 should cause a sleep (lines 916-919)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        pool._init_time = 0  # Ensure rate limiting path is taken

        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.is_open.return_value = True

        conn = XRPLConnection(url="wss://test.com", client=mock_client, is_healthy=True)
        pool._connections["wss://test.com"] = conn
        pool._healthy_connections.append("wss://test.com")

        with patch.object(pool._rate_limiter, "acquire", new_callable=AsyncMock, return_value=0.01), \
             patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await pool.get_client()
            mock_sleep.assert_called_once_with(0.01)
            self.assertIs(result, mock_client)

    async def test_get_client_missing_connection_in_dict(self):
        """Connection in healthy_connections but missing from _connections dict (line 934)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        pool._init_time = 0
        pool._healthy_connections.append("wss://ghost.com")

        with patch.object(pool._rate_limiter, "acquire", new_callable=AsyncMock, return_value=0.0):
            with self.assertRaises(XRPLConnectionError):
                await pool.get_client()


class TestXRPLNodePoolReconnect(IsolatedAsyncioWrapperTestCase):
    """Tests for _reconnect (lines 978-1021)."""

    async def test_reconnect_nonexistent_url(self):
        """Reconnecting a URL not in connections should return early (line 988-989)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        pool._connections = {}
        # Should not raise
        await pool._reconnect("wss://nonexistent.com")

    async def test_reconnect_already_reconnecting(self):
        """Should return early if already reconnecting (lines 991-993)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        conn = XRPLConnection(url="wss://test.com", is_reconnecting=True)
        pool._connections["wss://test.com"] = conn
        # Should return without doing anything
        await pool._reconnect("wss://test.com")
        self.assertTrue(conn.is_reconnecting)  # Still True

    async def test_reconnect_success(self):
        """Successful reconnection (lines 1002-1015)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])

        mock_client = AsyncMock()
        conn = XRPLConnection(url="wss://test.com", client=mock_client)
        pool._connections["wss://test.com"] = conn
        pool._healthy_connections.append("wss://test.com")

        with patch.object(pool, "_init_connection", new_callable=AsyncMock, return_value=True):
            await pool._reconnect("wss://test.com")

        # is_reconnecting should be reset
        self.assertFalse(pool._connections["wss://test.com"].is_reconnecting)
        mock_client.close.assert_called_once()

    async def test_reconnect_failure(self):
        """Failed reconnection (lines 1016-1017)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])

        mock_client = AsyncMock()
        conn = XRPLConnection(url="wss://test.com", client=mock_client)
        pool._connections["wss://test.com"] = conn

        with patch.object(pool, "_init_connection", new_callable=AsyncMock, return_value=False):
            await pool._reconnect("wss://test.com")

        self.assertFalse(pool._connections["wss://test.com"].is_reconnecting)

    async def test_reconnect_close_exception(self):
        """Exception during close of old connection should not prevent reconnection (lines 1007-1010)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])

        mock_client = AsyncMock()
        mock_client.close.side_effect = Exception("close error")
        conn = XRPLConnection(url="wss://test.com", client=mock_client)
        pool._connections["wss://test.com"] = conn

        with patch.object(pool, "_init_connection", new_callable=AsyncMock, return_value=True):
            await pool._reconnect("wss://test.com")

        self.assertFalse(pool._connections["wss://test.com"].is_reconnecting)


class TestXRPLNodePoolHealthMonitorLoop(IsolatedAsyncioWrapperTestCase):
    """Tests for _health_monitor_loop (lines 1023-1036)."""

    async def test_health_monitor_exception_handling(self):
        """Exceptions in _check_all_connections should be caught (lines 1033-1034)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        pool._running = True
        pool._health_check_interval = 0.01

        call_count = 0

        async def mock_check():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("check failed")
            pool._running = False  # Stop after second call

        with patch.object(pool, "_check_all_connections", side_effect=mock_check):
            await pool._health_monitor_loop()

        self.assertGreaterEqual(call_count, 1)


class TestXRPLNodePoolProactivePingLoop(IsolatedAsyncioWrapperTestCase):
    """Tests for _proactive_ping_loop and _ping_connection (lines 1038-1133)."""

    async def test_ping_connection_success(self):
        """Successful ping returns True (lines 1110-1123)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.is_open.return_value = True
        mock_client._request_impl = AsyncMock(
            return_value=Response(status=ResponseStatus.SUCCESS, result={"info": {}})
        )
        conn = XRPLConnection(url="wss://test.com", client=mock_client)
        result = await pool._ping_connection(conn)
        self.assertTrue(result)
        self.assertGreater(conn.avg_latency, 0.0)

    async def test_ping_connection_no_client(self):
        """Ping with no client returns False (lines 1110-1111)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        conn = XRPLConnection(url="wss://test.com", client=None)
        result = await pool._ping_connection(conn)
        self.assertFalse(result)

    async def test_ping_connection_error_response(self):
        """Ping with error response returns False (lines 1125-1126)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.is_open.return_value = True
        mock_client._request_impl = AsyncMock(
            return_value=Response(status=ResponseStatus.ERROR, result={"error": "fail"})
        )
        conn = XRPLConnection(url="wss://test.com", client=mock_client)
        result = await pool._ping_connection(conn)
        self.assertFalse(result)

    async def test_ping_connection_timeout(self):
        """Ping timeout returns False (lines 1128-1130)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.is_open.return_value = True
        mock_client._request_impl = AsyncMock(side_effect=asyncio.TimeoutError())
        conn = XRPLConnection(url="wss://test.com", client=mock_client)
        result = await pool._ping_connection(conn)
        self.assertFalse(result)

    async def test_ping_connection_exception(self):
        """Ping with general exception returns False (lines 1132-1133)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.is_open.return_value = True
        mock_client._request_impl = AsyncMock(side_effect=Exception("network error"))
        conn = XRPLConnection(url="wss://test.com", client=mock_client)
        result = await pool._ping_connection(conn)
        self.assertFalse(result)

    async def test_proactive_ping_loop_marks_unhealthy_after_errors(self):
        """Ping loop should mark connection unhealthy after consecutive errors (lines 1070-1085)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        pool._running = True

        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.is_open.return_value = True

        conn = XRPLConnection(url="wss://test.com", client=mock_client, is_healthy=True)
        # Set consecutive errors to threshold - 1 so one more failure marks it unhealthy
        conn.consecutive_errors = CONSTANTS.CONNECTION_MAX_CONSECUTIVE_ERRORS - 1
        pool._connections["wss://test.com"] = conn
        pool._healthy_connections.append("wss://test.com")

        call_count = 0

        async def mock_ping(c):
            nonlocal call_count
            call_count += 1
            return False  # Simulate ping failure

        with patch.object(pool, "_ping_connection", side_effect=mock_ping), \
             patch.object(pool, "_reconnect", new_callable=AsyncMock), \
             patch("hummingbot.connector.exchange.xrpl.xrpl_constants.PROACTIVE_PING_INTERVAL", 0.01):
            # Run one iteration then stop
            async def run_one_iter():
                await asyncio.sleep(0.02)
                pool._running = False

            task = asyncio.create_task(pool._proactive_ping_loop())
            await run_one_iter()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self.assertFalse(conn.is_healthy)

    async def test_proactive_ping_loop_resets_errors_on_success(self):
        """Successful ping should reset consecutive errors (lines 1087-1090)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        pool._running = True

        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.is_open.return_value = True

        conn = XRPLConnection(url="wss://test.com", client=mock_client, is_healthy=True)
        conn.consecutive_errors = 2
        pool._connections["wss://test.com"] = conn
        pool._healthy_connections.append("wss://test.com")

        async def mock_ping(c):
            return True

        with patch.object(pool, "_ping_connection", side_effect=mock_ping), \
             patch("hummingbot.connector.exchange.xrpl.xrpl_constants.PROACTIVE_PING_INTERVAL", 0.01):
            async def run_one_iter():
                await asyncio.sleep(0.02)
                pool._running = False

            task = asyncio.create_task(pool._proactive_ping_loop())
            await run_one_iter()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self.assertEqual(conn.consecutive_errors, 0)

    async def test_proactive_ping_loop_exception_handling(self):
        """Exceptions in ping loop should be caught (lines 1094-1095)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        pool._running = True

        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.is_open.return_value = True

        conn = XRPLConnection(url="wss://test.com", client=mock_client, is_healthy=True)
        pool._connections["wss://test.com"] = conn
        pool._healthy_connections.append("wss://test.com")

        call_count = 0

        async def mock_ping(c):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("unexpected error")

        with patch.object(pool, "_ping_connection", side_effect=mock_ping), \
             patch("hummingbot.connector.exchange.xrpl.xrpl_constants.PROACTIVE_PING_INTERVAL", 0.01):
            async def stop_after_delay():
                await asyncio.sleep(0.05)
                pool._running = False

            task = asyncio.create_task(pool._proactive_ping_loop())
            stop_task = asyncio.create_task(stop_after_delay())
            await asyncio.gather(task, stop_task)

        # The loop should have continued despite the exception
        self.assertGreaterEqual(call_count, 1)


class TestXRPLNodePoolCheckAllConnections(IsolatedAsyncioWrapperTestCase):
    """Tests for _check_all_connections (lines 1135-1190)."""

    async def test_check_connection_closed_triggers_reconnect(self):
        """Closed connection should trigger reconnection (lines 1148-1150)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])

        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.is_open.return_value = False

        conn = XRPLConnection(url="wss://test.com", client=mock_client, is_healthy=True)
        pool._connections["wss://test.com"] = conn

        with patch.object(pool, "_reconnect", new_callable=AsyncMock):
            # Need to patch asyncio.create_task since _check_all_connections calls it
            with patch("asyncio.create_task"):
                await pool._check_all_connections()

        self.assertFalse(conn.is_healthy)

    async def test_check_connection_too_old_triggers_reconnect(self):
        """Old connection should trigger reconnection (lines 1153-1155)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"], max_connection_age=0.01)

        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.is_open.return_value = True

        conn = XRPLConnection(url="wss://test.com", client=mock_client, is_healthy=True)
        conn.created_at = time.time() - 100  # Very old connection
        pool._connections["wss://test.com"] = conn

        with patch("asyncio.create_task"):
            await pool._check_all_connections()

        self.assertFalse(conn.is_healthy)

    async def test_check_connection_ping_success(self):
        """Successful ping during health check should mark connection healthy (lines 1174-1176)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"], max_connection_age=99999)

        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.is_open.return_value = True
        mock_client._request_impl = AsyncMock(
            return_value=Response(status=ResponseStatus.SUCCESS, result={"info": {}})
        )

        conn = XRPLConnection(url="wss://test.com", client=mock_client, is_healthy=False)
        conn.consecutive_errors = 2
        pool._connections["wss://test.com"] = conn

        await pool._check_all_connections()

        self.assertTrue(conn.is_healthy)
        self.assertEqual(conn.consecutive_errors, 0)

    async def test_check_connection_ping_error_response(self):
        """Error response during health check should record error (lines 1169-1173)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"], max_connection_age=99999)

        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.is_open.return_value = True
        mock_client._request_impl = AsyncMock(
            return_value=Response(status=ResponseStatus.ERROR, result={"error": "fail"})
        )

        conn = XRPLConnection(url="wss://test.com", client=mock_client, is_healthy=True)
        conn.consecutive_errors = CONSTANTS.CONNECTION_MAX_CONSECUTIVE_ERRORS - 1
        pool._connections["wss://test.com"] = conn

        with patch("asyncio.create_task"):
            await pool._check_all_connections()

        self.assertFalse(conn.is_healthy)

    async def test_check_connection_ping_timeout(self):
        """Timeout during health check should trigger reconnect (lines 1178-1181)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"], max_connection_age=99999)

        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.is_open.return_value = True
        mock_client._request_impl = AsyncMock(side_effect=asyncio.TimeoutError())

        conn = XRPLConnection(url="wss://test.com", client=mock_client, is_healthy=True)
        pool._connections["wss://test.com"] = conn

        with patch("asyncio.create_task"):
            await pool._check_all_connections()

        self.assertFalse(conn.is_healthy)

    async def test_check_connection_ping_exception(self):
        """General exception during health check should trigger reconnect (lines 1182-1185)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"], max_connection_age=99999)

        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.is_open.return_value = True
        mock_client._request_impl = AsyncMock(side_effect=ConnectionError("lost"))

        conn = XRPLConnection(url="wss://test.com", client=mock_client, is_healthy=True)
        pool._connections["wss://test.com"] = conn

        with patch("asyncio.create_task"):
            await pool._check_all_connections()

        self.assertFalse(conn.is_healthy)

    async def test_check_skips_reconnecting_connections(self):
        """Connections already reconnecting should be skipped (line 1141)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])

        conn = XRPLConnection(url="wss://test.com", is_reconnecting=True, is_healthy=True)
        pool._connections["wss://test.com"] = conn

        await pool._check_all_connections()
        # Connection state should be unchanged
        self.assertTrue(conn.is_healthy)


class TestXRPLNodePoolMarkError(IsolatedAsyncioWrapperTestCase):
    """Tests for mark_error (lines 1192-1214)."""

    async def test_mark_error_records_error(self):
        """mark_error should record error on matching connection (lines 1200-1205)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])

        mock_client = MagicMock(spec=AsyncWebsocketClient)
        conn = XRPLConnection(url="wss://test.com", client=mock_client, is_healthy=True)
        pool._connections["wss://test.com"] = conn

        pool.mark_error(mock_client)
        self.assertEqual(conn.error_count, 1)
        self.assertEqual(conn.consecutive_errors, 1)
        self.assertTrue(conn.is_healthy)  # Not yet at threshold

    async def test_mark_error_triggers_unhealthy_after_threshold(self):
        """After enough errors, connection should be marked unhealthy (lines 1207-1214)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])

        mock_client = MagicMock(spec=AsyncWebsocketClient)
        conn = XRPLConnection(url="wss://test.com", client=mock_client, is_healthy=True)
        conn.consecutive_errors = CONSTANTS.CONNECTION_MAX_CONSECUTIVE_ERRORS - 1
        pool._connections["wss://test.com"] = conn

        with patch.object(pool, "_reconnect", new_callable=AsyncMock), \
             patch("asyncio.create_task"):
            pool.mark_error(mock_client)

        self.assertFalse(conn.is_healthy)

    async def test_mark_error_no_matching_client(self):
        """No matching client should not raise."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        mock_client_in_pool = MagicMock(spec=AsyncWebsocketClient)
        mock_client_other = MagicMock(spec=AsyncWebsocketClient)

        conn = XRPLConnection(url="wss://test.com", client=mock_client_in_pool, is_healthy=True)
        pool._connections["wss://test.com"] = conn

        pool.mark_error(mock_client_other)
        self.assertEqual(conn.error_count, 0)  # Unchanged


class TestXRPLNodePoolMarkBadNode(IsolatedAsyncioWrapperTestCase):
    """Tests for mark_bad_node (lines 1216-1228)."""

    async def test_mark_bad_node_adds_to_bad_nodes(self):
        """mark_bad_node should add URL to bad_nodes dict (lines 1218-1220)."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        conn = XRPLConnection(url="wss://test.com", is_healthy=True)
        pool._connections["wss://test.com"] = conn

        with patch("asyncio.create_task"):
            pool.mark_bad_node("wss://test.com")

        self.assertIn("wss://test.com", pool._bad_nodes)
        self.assertFalse(conn.is_healthy)

    async def test_mark_bad_node_nonexistent(self):
        """Marking a non-existent node should still add to bad_nodes."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        pool.mark_bad_node("wss://nonexistent.com")
        self.assertIn("wss://nonexistent.com", pool._bad_nodes)


class TestXRPLNodePoolCurrentNode(IsolatedAsyncioWrapperTestCase):
    """Tests for current_node property (lines 1232-1234)."""

    def test_current_node_with_healthy_connections(self):
        """Should return first healthy connection URL (line 1233)."""
        pool = XRPLNodePool(node_urls=["wss://test1.com", "wss://test2.com"])
        pool._healthy_connections = deque(["wss://test2.com", "wss://test1.com"])
        self.assertEqual(pool.current_node, "wss://test2.com")

    def test_current_node_no_healthy_connections(self):
        """Should fallback to first node_urls (line 1234)."""
        pool = XRPLNodePool(node_urls=["wss://test1.com", "wss://test2.com"])
        pool._healthy_connections = deque()
        self.assertEqual(pool.current_node, "wss://test1.com")

    def test_current_node_no_urls_at_all(self):
        """Should fallback to DEFAULT_NODES."""
        pool = XRPLNodePool(node_urls=[])
        pool._healthy_connections = deque()
        self.assertEqual(pool.current_node, pool._node_urls[0])


class TestXRPLConfigMapValidation(IsolatedAsyncioWrapperTestCase):
    """Additional tests for XRPLConfigMap validators."""

    def test_validate_wss_node_urls_empty_list(self):
        """Empty list should raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            XRPLConfigMap.validate_wss_node_urls([])
        self.assertIn("At least one XRPL node URL must be provided", str(ctx.exception))

    def test_validate_wss_node_urls_list_input(self):
        """List input should be validated directly."""
        result = XRPLConfigMap.validate_wss_node_urls(["wss://s1.ripple.com/"])
        self.assertEqual(result, ["wss://s1.ripple.com/"])
