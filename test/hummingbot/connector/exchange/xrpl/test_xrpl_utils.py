import time
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, patch

from xrpl.asyncio.clients import XRPLRequestFailureException
from xrpl.asyncio.transaction import XRPLReliableSubmissionException
from xrpl.models import OfferCancel, Response
from xrpl.models.response import ResponseStatus

from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange.xrpl.xrpl_utils import (
    RateLimiter,
    XRPLConfigMap,
    XRPLNodePool,
    _wait_for_final_transaction_outcome,
    autofill,
    compute_order_book_changes,
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


class TestXRPLNodePool(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        self.node_urls = [
            "wss://test1.ripple.com/",
            "wss://test2.ripple.com/",
            "wss://test3.ripple.com/",
        ]
        self.node_pool = XRPLNodePool(
            node_urls=self.node_urls,
            requests_per_10s=10.0,
            burst_tokens=2,
            max_burst_tokens=5,
            proactive_switch_interval=30,
            cooldown=60,
        )

    @patch("hummingbot.connector.exchange.xrpl.xrpl_utils.AsyncWebsocketClient")
    async def test_get_node(self, mock_client_class):
        # Setup mock client
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client._request_impl.return_value = Response(
            status=ResponseStatus.SUCCESS,
            result={"info": {"build_version": "1.11.1"}},
        )

        # Test getting node
        node = await self.node_pool.get_node()
        self.assertIn(node, self.node_urls)
        self.assertEqual(node, self.node_pool.current_node)

        # Test marking node as bad
        self.node_pool.mark_bad_node(node)
        self.assertIn(node, self.node_pool._bad_nodes)

        # Test getting node after marking as bad
        new_node = await self.node_pool.get_node()
        self.assertNotEqual(new_node, node)  # Should get a different node
        self.assertIn(new_node, self.node_urls)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_utils.AsyncWebsocketClient")
    async def test_get_latency(self, mock_client_class):
        # Setup mock client
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client._request_impl.return_value = Response(
            status=ResponseStatus.SUCCESS,
            result={"info": {"build_version": "1.11.1"}},
        )

        # Test getting latency
        latency = await self.node_pool.get_latency(self.node_urls[0])
        self.assertIsInstance(latency, float)
        self.assertGreater(latency, 0.0)

        # Test getting latency with error
        mock_client._request_impl.side_effect = Exception("Test error")
        latency = await self.node_pool.get_latency(self.node_urls[0])
        self.assertEqual(latency, 9999)  # Should return max latency on error

    def test_add_burst_tokens(self):
        # Test adding burst tokens
        self.node_pool.add_burst_tokens(2)
        self.assertEqual(self.node_pool.burst_tokens, 4)  # Initial 2 + added 2

        # Test adding tokens exceeding max limit
        self.node_pool.add_burst_tokens(5)
        self.assertEqual(self.node_pool.burst_tokens, 5)  # Should cap at max_burst_tokens

    @patch("hummingbot.connector.exchange.xrpl.xrpl_utils.AsyncWebsocketClient")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_utils.XRPLNodePool._get_latency_safe")
    async def test_rotate_node_with_cooldown(self, mock_get_latency, mock_client_class):
        # Setup mock client
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client._request_impl.return_value = Response(
            status=ResponseStatus.SUCCESS,
            result={"info": {"build_version": "1.11.1"}},
        )

        # Setup mock latency for all nodes
        def mock_latency(node):
            # Return good latency for all nodes
            return 0.1

        mock_get_latency.side_effect = mock_latency

        # Mark first node as bad with future cooldown
        test_node = self.node_urls[0]
        current_time = time.time()
        future_time = current_time + 100  # 100 seconds in future
        self.node_pool._bad_nodes[test_node] = future_time

        # Make sure test node is first in rotation
        while self.node_pool._nodes[0] != test_node:
            self.node_pool._nodes.rotate(-1)

        # Try to rotate - should skip the node in cooldown
        await self.node_pool._rotate_node_locked(current_time)

        # Verify the node in cooldown was skipped
        self.assertNotEqual(self.node_pool.current_node, test_node)
        self.assertIn(test_node, self.node_pool._bad_nodes)

        # Verify the next node was checked and selected
        next_node = self.node_urls[1]  # Should be the next node after test_node
        self.assertEqual(self.node_pool.current_node, next_node)
        mock_get_latency.assert_called_with(next_node)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_utils.AsyncWebsocketClient")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_utils.XRPLNodePool._get_latency_safe")
    async def test_rotate_node_cooldown_expiry(self, mock_get_latency, mock_client_class):
        # Setup mock client
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client._request_impl.return_value = Response(
            status=ResponseStatus.SUCCESS,
            result={"info": {"build_version": "1.11.1"}},
        )

        # Setup mock latency for all nodes
        def mock_latency(node):
            # Return good latency for all nodes
            return 0.1

        mock_get_latency.side_effect = mock_latency

        # Mark first node as bad with past cooldown
        test_node = self.node_urls[0]
        current_time = time.time()
        past_time = current_time - 100  # 100 seconds in past
        self.node_pool._bad_nodes[test_node] = past_time

        # Make sure test node is first in rotation
        while self.node_pool._nodes[0] != test_node:
            self.node_pool._nodes.rotate(-1)

        await self.node_pool._rotate_node_locked(current_time)
        self.assertNotEqual(self.node_pool.current_node, test_node)


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
