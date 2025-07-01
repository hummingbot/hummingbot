from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from xrpl.asyncio.clients import AsyncWebsocketClient
from xrpl.models import XRP, AMMDeposit, AMMWithdraw, IssuedCurrency, Memo, Response
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.models.response import ResponseStatus

from hummingbot.connector.exchange.xrpl.xrpl_exchange import XrplExchange
from hummingbot.connector.exchange.xrpl.xrpl_utils import (
    AddLiquidityResponse,
    PoolInfo,
    QuoteLiquidityResponse,
    RemoveLiquidityResponse,
)


class TestXRPLAMMFunctions(IsolatedAsyncioWrapperTestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "XRP"
        cls.quote_asset = "USD"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.connector = MagicMock(spec=XrplExchange)

        # Mock XRP and IssuedCurrency objects
        self.xrp = XRP()
        self.usd = IssuedCurrency(currency="USD", issuer="rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R")  # noqa: mock
        # LP token uses a valid 3-character currency code or hex format (40 chars for hex)
        self.lp_token = IssuedCurrency(
            currency="534F4C4F00000000000000000000000000000000", issuer="rAMMPoolAddress123"
        )  # noqa: mock

        # Mock client
        self.client = MagicMock(spec=AsyncWebsocketClient)
        self.connector._xrpl_query_client = self.client
        self.connector._xrpl_query_client_lock = MagicMock()

        # Mock authentication
        self.connector._xrpl_auth = MagicMock()
        self.connector._xrpl_auth.get_account.return_value = "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R"  # noqa: mock

        # Mock request_with_retry method
        self.connector.request_with_retry = AsyncMock()

        # Mock other methods
        self.connector.get_currencies_from_trading_pair = MagicMock(return_value=(self.xrp, self.usd))
        self.connector._submit_transaction = AsyncMock()
        self.connector._sleep = AsyncMock()
        self.connector._lock_delay_seconds = 0

    @patch("xrpl.utils.xrp_to_drops")
    @patch("xrpl.utils.drops_to_xrp")
    def test_create_pool_info(self, mock_drops_to_xrp, mock_xrp_to_drops):
        # Setup mock responses
        mock_drops_to_xrp.return_value = Decimal("1000")

        # amm_pool_info = {
        #     "account": "rAMMPoolAddress123",  # noqa: mock
        #     "amount": "1000000000",  # XRP amount in drops
        #     "amount2": {
        #         "currency": "USD",
        #         "issuer": "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R",
        #         "value": "1000",
        #     },  # noqa: mock
        #     "lp_token": {
        #         "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
        #         "issuer": "rAMMPoolAddress123",  # noqa: mock
        #         "value": "1000",
        #     },
        #     "trading_fee": "5",  # 0.5% in basis points
        # }

        # Create a PoolInfo object
        pool_info = PoolInfo(
            address="rAMMPoolAddress123",
            base_token_address=self.xrp,
            quote_token_address=self.usd,
            lp_token_address=self.lp_token,
            fee_pct=Decimal("0.005"),
            price=Decimal("1"),
            base_token_amount=Decimal("1000"),
            quote_token_amount=Decimal("1000"),
            lp_token_amount=Decimal("1000"),
            pool_type="XRPL-AMM",
        )

        # Verify the pool info properties
        self.assertEqual(pool_info.address, "rAMMPoolAddress123")  # noqa: mock
        self.assertEqual(pool_info.fee_pct, Decimal("0.005"))
        self.assertEqual(pool_info.base_token_amount, Decimal("1000"))
        self.assertEqual(pool_info.quote_token_amount, Decimal("1000"))
        self.assertEqual(pool_info.lp_token_amount, Decimal("1000"))
        self.assertEqual(pool_info.price, Decimal("1"))

    @patch("hummingbot.connector.exchange.xrpl.xrpl_utils.convert_string_to_hex")
    async def test_amm_get_pool_info(self, mock_convert_string_to_hex):
        # Setup mock responses
        resp = MagicMock(spec=Response)
        resp.status = ResponseStatus.SUCCESS
        resp.result = {
            "amm": {
                "account": "rAMMPoolAddress123",  # noqa: mock
                "amount": "1000000000",  # XRP amount in drops
                "amount2": {
                    "currency": "USD",
                    "issuer": "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R",  # noqa: mock
                    "value": "1000",
                },  # noqa: mock
                "lp_token": {
                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                    "issuer": "rAMMPoolAddress123",  # noqa: mock
                    "value": "1000",
                },
                "trading_fee": "5",  # 0.5% in basis points
            }
        }

        # Configure the mock to return our response
        self.connector.request_with_retry.return_value = resp

        # Mock amm_get_pool_info to call the real implementation
        # This ensures our mocked request_with_retry gets called
        self.connector.amm_get_pool_info = XrplExchange.amm_get_pool_info.__get__(self.connector)

        # Call the method with a trading pair
        result = await self.connector.amm_get_pool_info(trading_pair=self.trading_pair)

        # Verify the method called request_with_retry with the correct parameters
        self.connector.request_with_retry.assert_called_once()
        call_args = self.connector.request_with_retry.call_args[0]
        self.assertEqual(call_args[0].method, "amm_info")

        # Verify the result
        self.assertEqual(result.address, "rAMMPoolAddress123")  # noqa: mock
        self.assertEqual(result.fee_pct, Decimal("0.005"))

        # Call the method with a pool address
        self.connector.request_with_retry.reset_mock()
        result = await self.connector.amm_get_pool_info(pool_address="rAMMPoolAddress123")  # noqa: mock

        # Verify the method called request_with_retry with the correct parameters
        self.connector.request_with_retry.assert_called_once()
        call_args = self.connector.request_with_retry.call_args[0]
        self.assertEqual(call_args[0].method, "amm_info")

        # Test error case - missing required parameters
        result_without_params = await self.connector.amm_get_pool_info()
        self.assertIsNone(result_without_params)

    async def test_amm_quote_add_liquidity(self):
        # Setup mock for amm_get_pool_info
        mock_pool_info = PoolInfo(
            address="rAMMPoolAddress123",
            base_token_address=self.xrp,
            quote_token_address=self.usd,
            lp_token_address=self.lp_token,
            fee_pct=Decimal("0.005"),
            price=Decimal("2"),  # 2 USD per XRP
            base_token_amount=Decimal("1000"),
            quote_token_amount=Decimal("2000"),
            lp_token_amount=Decimal("1000"),
            pool_type="XRPL-AMM",
        )
        self.connector.amm_get_pool_info = AsyncMock(return_value=mock_pool_info)

        # Mock amm_quote_add_liquidity to call the real implementation
        self.connector.amm_quote_add_liquidity = XrplExchange.amm_quote_add_liquidity.__get__(self.connector)

        # Test base limited case (providing more base token relative to current pool ratio)
        result = await self.connector.amm_quote_add_liquidity(
            pool_address="rAMMPoolAddress123",  # noqa: mock
            base_token_amount=Decimal("10"),
            quote_token_amount=Decimal("10"),
            slippage_pct=Decimal("0.01"),
        )

        # Verify the result
        self.assertTrue(result.base_limited)
        self.assertEqual(result.base_token_amount, Decimal("10"))
        self.assertEqual(result.quote_token_amount, Decimal("20"))  # 10 XRP * 2 USD/XRP = 20 USD
        self.assertEqual(result.quote_token_amount_max, Decimal("20.2"))  # 20 USD * 1.01 = 20.2 USD

        # Test quote limited case (providing more quote token relative to current pool ratio)
        result = await self.connector.amm_quote_add_liquidity(
            pool_address="rAMMPoolAddress123",  # noqa: mock
            base_token_amount=Decimal("10"),
            quote_token_amount=Decimal("30"),
            slippage_pct=Decimal("0.01"),
        )

        # Verify the result
        self.assertFalse(result.base_limited)
        self.assertEqual(result.base_token_amount, Decimal("15"))  # 30 USD / 2 USD/XRP = 15 XRP
        self.assertEqual(result.quote_token_amount, Decimal("30"))
        self.assertEqual(result.base_token_amount_max, Decimal("15.15"))  # 15 XRP * 1.01 = 15.15 XRP

    @patch("hummingbot.connector.exchange.xrpl.xrpl_utils.convert_string_to_hex")
    @patch("xrpl.utils.xrp_to_drops")
    async def test_amm_add_liquidity(self, mock_xrp_to_drops, mock_convert_string_to_hex):
        # Setup mocks
        mock_xrp_to_drops.return_value = "10000000"
        mock_convert_string_to_hex.return_value = (
            "68626F742D6C69717569646974792D61646465642D73756363657373"  # noqa: mock
        )

        # Mock quote response
        quote_response = QuoteLiquidityResponse(
            base_limited=True,
            base_token_amount=Decimal("10"),
            quote_token_amount=Decimal("20"),
            base_token_amount_max=Decimal("10"),
            quote_token_amount_max=Decimal("20.2"),
        )
        self.connector.amm_quote_add_liquidity = AsyncMock(return_value=quote_response)

        # Mock pool info
        mock_pool_info = PoolInfo(
            address="rAMMPoolAddress123",
            base_token_address=self.xrp,
            quote_token_address=self.usd,
            lp_token_address=self.lp_token,
            fee_pct=Decimal("0.005"),
            price=Decimal("2"),
            base_token_amount=Decimal("1000"),
            quote_token_amount=Decimal("2000"),
            lp_token_amount=Decimal("1000"),
            pool_type="XRPL-AMM",
        )
        self.connector.amm_get_pool_info = AsyncMock(return_value=mock_pool_info)

        # Mock transaction submission response
        submit_response = MagicMock(spec=Response)
        submit_response.status = ResponseStatus.SUCCESS
        submit_response.result = {
            "engine_result": "tesSUCCESS",
            "tx_json": {"hash": "transaction_hash", "Fee": "10"},
            "meta": {
                "AffectedNodes": [
                    {
                        "ModifiedNode": {
                            "FinalFields": {
                                "Account": "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R",  # noqa: mock
                                "Balance": "99990000000",  # Changed to represent 10 XRP (10 * 10^6 drops)
                                "Flags": 0,
                                "OwnerCount": 1,
                                "Sequence": 12345,
                            },
                            "LedgerEntryType": "AccountRoot",
                            "LedgerIndex": "1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF",  # noqa: mock
                            "PreviousFields": {
                                "Balance": "100000000000",  # Changed to represent 100 XRP (100 * 10^6 drops)
                            },
                            "PreviousTxnID": "ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890",  # noqa: mock
                            "PreviousTxnLgrSeq": 96213077,
                        }
                    },
                    {
                        "ModifiedNode": {
                            "FinalFields": {
                                "Balance": {
                                    "currency": "USD",
                                    "issuer": "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R",  # noqa: mock
                                    "value": "980",
                                },
                                "Flags": 2228224,
                                "HighLimit": {
                                    "currency": "USD",
                                    "issuer": "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R",  # noqa: mock
                                    "value": "1000",
                                },
                                "HighNode": "0",
                                "LowLimit": {
                                    "currency": "USD",
                                    "issuer": "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R",  # noqa: mock
                                    "value": "0",
                                },
                                "LowNode": "0",
                            },
                            "LedgerEntryType": "RippleState",
                            "LedgerIndex": "ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890",  # noqa: mock
                            "PreviousFields": {
                                "Balance": {
                                    "currency": "USD",
                                    "issuer": "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R",  # noqa: mock
                                    "value": "1000",
                                }
                            },
                            "PreviousTxnID": "ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890",  # noqa: mock
                            "PreviousTxnLgrSeq": 96213077,
                        }
                    },
                    {
                        "ModifiedNode": {
                            "FinalFields": {
                                "Balance": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rAMMPoolAddress123",  # noqa: mock
                                    "value": "10",
                                },
                                "Flags": 2228224,
                                "HighLimit": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rAMMPoolAddress123",  # noqa: mock
                                    "value": "0",
                                },
                                "HighNode": "2",
                                "LowLimit": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rAMMPoolAddress123",  # noqa: mock
                                    "value": "0",
                                },
                                "LowNode": "4c",
                            },
                            "LedgerEntryType": "RippleState",
                            "LedgerIndex": "095C3D1280BB6A122C322AB3F379A51656AB786B7793D7C301916333EF69E5B3",  # noqa: mock
                            "PreviousFields": {
                                "Balance": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rAMMPoolAddress123",
                                    "value": "0",
                                }
                            },
                            "PreviousTxnID": "F54DB49251260913310662B5716CA96C7FE78B5BE9F68DCEA3F27ECB6A904A71",  # noqa: mock
                            "PreviousTxnLgrSeq": 96213077,
                        }
                    },
                    {
                        "ModifiedNode": {
                            "FinalFields": {
                                "Account": "rAMMPoolAddress123",  # noqa: mock
                                "Asset": {"currency": "XRP"},
                                "Asset2": {
                                    "currency": "USD",
                                    "issuer": "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R",
                                },  # noqa: mock
                                "AuctionSlot": {
                                    "Account": "rAMMPoolAddress123",  # noqa: mock
                                    "DiscountedFee": 23,
                                    "Expiration": 791668410,
                                    "Price": {
                                        "currency": "USD",
                                        "issuer": "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R",  # noqa: mock
                                        "value": "0",
                                    },
                                },
                                "Flags": 0,
                                "LPTokenBalance": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rAMMPoolAddress123",  # noqa: mock
                                    "value": "1010",
                                },
                                "OwnerNode": "0",
                                "TradingFee": 235,
                            },
                            "LedgerEntryType": "AMM",
                            "LedgerIndex": "160C6649399D6AF625ED94A66812944BDA1D8993445A503F6B5730DECC7D3767",  # noqa: mock
                            "PreviousFields": {
                                "LPTokenBalance": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rAMMPoolAddress123",
                                    "value": "1000",
                                }
                            },
                            "PreviousTxnID": "26F52AD68480EAB7ADF19C2CCCE3A0329AEF8CF9CB46329031BD16C6200BCD4D",  # noqa: mock
                            "PreviousTxnLgrSeq": 96220690,
                        }
                    },
                ],
                "TransactionIndex": 12,
                "TransactionResult": "tesSUCCESS",
            },
        }
        self.connector._submit_transaction = AsyncMock(return_value=submit_response)

        # Mock the real implementation of amm_add_liquidity
        self.connector.amm_add_liquidity = XrplExchange.amm_add_liquidity.__get__(self.connector)

        # Call the method
        result = await self.connector.amm_add_liquidity(
            pool_address="rAMMPoolAddress123",
            wallet_address="rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R",
            base_token_amount=Decimal("10"),
            quote_token_amount=Decimal("20"),
            slippage_pct=Decimal("0.01"),
        )

        # Verify the transaction was created and submitted
        self.connector._submit_transaction.assert_called_once()
        call_args = self.connector._submit_transaction.call_args[0]
        tx = call_args[0]
        self.assertIsInstance(tx, AMMDeposit)
        self.assertEqual(tx.account, "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R")  # noqa: mock
        self.assertEqual(tx.asset, self.xrp)
        self.assertEqual(tx.asset2, self.usd)

        # Verify memo is included
        self.assertIsInstance(tx.memos[0], Memo)

        # Verify the result
        self.assertIsInstance(result, AddLiquidityResponse)
        self.assertEqual(result.signature, "transaction_hash")
        self.assertEqual(result.fee, Decimal("0.00001"))
        self.assertEqual(result.base_token_amount_added, Decimal("10"))
        self.assertEqual(result.quote_token_amount_added, Decimal("20"))

    @patch("hummingbot.connector.exchange.xrpl.xrpl_utils.convert_string_to_hex")
    async def test_amm_remove_liquidity(self, mock_convert_string_to_hex):
        # Setup mocks
        mock_convert_string_to_hex.return_value = (
            "68626F742D6C69717569646974792D72656D6F7665642D73756363657373"  # noqa: mock
        )

        # Mock pool info
        mock_pool_info = PoolInfo(
            address="rAMMPoolAddress123",
            base_token_address=self.xrp,
            quote_token_address=self.usd,
            lp_token_address=self.lp_token,
            fee_pct=Decimal("0.005"),
            price=Decimal("2"),
            base_token_amount=Decimal("1000"),
            quote_token_amount=Decimal("2000"),
            lp_token_amount=Decimal("1000"),
            pool_type="XRPL-AMM",
        )
        self.connector.amm_get_pool_info = AsyncMock(return_value=mock_pool_info)

        # Mock account objects (LP tokens)
        account_objects_response = MagicMock(spec=Response)
        account_objects_response.status = ResponseStatus.SUCCESS
        account_objects_response.result = {
            "account": "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R",  # noqa: mock
            "account_objects": [
                {
                    "Balance": {
                        "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                        "issuer": "rAMMPoolAddress123",
                        "value": "100",
                    },
                    "LedgerEntryType": "RippleState",
                }
            ],
        }
        self.connector.request_with_retry = AsyncMock(return_value=account_objects_response)

        # Mock transaction submission response with metadata to simulate balance changes
        submit_response = MagicMock(spec=Response)
        submit_response.status = ResponseStatus.SUCCESS
        submit_response.result = {
            "engine_result": "tesSUCCESS",
            "tx_json": {"hash": "transaction_hash", "Fee": "12"},
            "meta": {
                "AffectedNodes": [
                    {
                        "ModifiedNode": {
                            "FinalFields": {
                                "Account": "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R",  # noqa: mock
                                "Balance": "100010000000",  # Increased by 10 XRP
                                "Flags": 0,
                                "OwnerCount": 1,
                                "Sequence": 12345,
                            },
                            "LedgerEntryType": "AccountRoot",
                            "LedgerIndex": "1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF",  # noqa: mock
                            "PreviousFields": {
                                "Balance": "100000000000",
                            },
                            "PreviousTxnID": "ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890",  # noqa: mock
                            "PreviousTxnLgrSeq": 96213077,
                        }
                    },
                    {
                        "ModifiedNode": {
                            "FinalFields": {
                                "Balance": {
                                    "currency": "USD",
                                    "issuer": "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R",  # noqa: mock
                                    "value": "980",  # Increased by 20 USD
                                },
                                "Flags": 2228224,
                                "HighLimit": {
                                    "currency": "USD",
                                    "issuer": "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R",  # noqa: mock
                                    "value": "1000",
                                },
                                "HighNode": "0",
                                "LowLimit": {
                                    "currency": "USD",
                                    "issuer": "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R",  # noqa: mock
                                    "value": "0",
                                },
                                "LowNode": "0",
                            },
                            "LedgerEntryType": "RippleState",
                            "LedgerIndex": "ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890",  # noqa: mock
                            "PreviousFields": {
                                "Balance": {
                                    "currency": "USD",
                                    "issuer": "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R",  # noqa: mock
                                    "value": "1000",
                                }
                            },
                            "PreviousTxnID": "ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890",  # noqa: mock
                            "PreviousTxnLgrSeq": 96213077,
                        }
                    },
                    {
                        "ModifiedNode": {
                            "FinalFields": {
                                "Balance": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rAMMPoolAddress123",
                                    "value": "90",  # Decreased by 10 LP tokens
                                },
                                "Flags": 2228224,
                                "HighLimit": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rAMMPoolAddress123",
                                    "value": "0",
                                },
                                "HighNode": "2",
                                "LowLimit": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rAMMPoolAddress123",
                                    "value": "0",
                                },
                                "LowNode": "4c",
                            },
                            "LedgerEntryType": "RippleState",
                            "LedgerIndex": "095C3D1280BB6A122C322AB3F379A51656AB786B7793D7C301916333EF69E5B3",  # noqa: mock
                            "PreviousFields": {
                                "Balance": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rAMMPoolAddress123",
                                    "value": "100",
                                }
                            },
                            "PreviousTxnID": "F54DB49251260913310662B5716CA96C7FE78B5BE9F68DCEA3F27ECB6A904A71",  # noqa: mock
                            "PreviousTxnLgrSeq": 96213077,
                        }
                    },
                    {
                        "ModifiedNode": {
                            "FinalFields": {
                                "Account": "rAMMPoolAddress123",
                                "Asset": {"currency": "XRP"},
                                "Asset2": {
                                    "currency": "USD",
                                    "issuer": "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R",  # noqa: mock
                                },  # noqa: mock
                                "AuctionSlot": {
                                    "Account": "rAMMPoolAddress123",
                                    "DiscountedFee": 23,
                                    "Expiration": 791668410,
                                    "Price": {
                                        "currency": "USD",
                                        "issuer": "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R",  # noqa: mock
                                        "value": "0",
                                    },
                                },
                                "Flags": 0,
                                "LPTokenBalance": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rAMMPoolAddress123",
                                    "value": "990",  # Decreased by 10 LP tokens
                                },
                                "OwnerNode": "0",
                                "TradingFee": 235,
                            },
                            "LedgerEntryType": "AMM",
                            "LedgerIndex": "160C6649399D6AF625ED94A66812944BDA1D8993445A503F6B5730DECC7D3767",  # noqa: mock
                            "PreviousFields": {
                                "LPTokenBalance": {
                                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                                    "issuer": "rAMMPoolAddress123",
                                    "value": "1000",
                                }
                            },
                            "PreviousTxnID": "26F52AD68480EAB7ADF19C2CCCE3A0329AEF8CF9CB46329031BD16C6200BCD4D",  # noqa: mock
                            "PreviousTxnLgrSeq": 96220690,
                        }
                    },
                ],
                "TransactionIndex": 12,
                "TransactionResult": "tesSUCCESS",
            },
        }
        self.connector._submit_transaction = AsyncMock(return_value=submit_response)

        # Mock the real implementation of amm_remove_liquidity
        self.connector.amm_remove_liquidity = XrplExchange.amm_remove_liquidity.__get__(self.connector)

        # Call the method
        result = await self.connector.amm_remove_liquidity(
            pool_address="rAMMPoolAddress123",
            wallet_address="rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R",  # noqa: mock
            percentage_to_remove=Decimal("50"),
        )

        # Verify the request_with_retry was called (with the correct parameters but not checking specifics)
        self.connector.request_with_retry.assert_called()

        # Verify amm_get_pool_info was called with the pool address
        self.connector.amm_get_pool_info.assert_called_with("rAMMPoolAddress123", None)

        # Verify the transaction was created and submitted
        self.connector._submit_transaction.assert_called_once()
        call_args = self.connector._submit_transaction.call_args[0]
        tx = call_args[0]
        self.assertIsInstance(tx, AMMWithdraw)
        self.assertEqual(tx.account, "rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R")  # noqa: mock
        self.assertEqual(tx.asset, self.xrp)
        self.assertEqual(tx.asset2, self.usd)
        self.assertEqual(tx.flags, 0x00010000)  # LPToken flag

        # Check the LP token amount is correct (50% of 100)
        expected_lp_token = IssuedCurrencyAmount(
            currency="534F4C4F00000000000000000000000000000000",  # noqa: mock
            issuer="rAMMPoolAddress123",
            value="50.0",
        )
        self.assertEqual(Decimal(tx.lp_token_in.value), Decimal(expected_lp_token.value))

        # Verify the result
        self.assertIsInstance(result, RemoveLiquidityResponse)
        self.assertEqual(result.signature, "transaction_hash")
        self.assertEqual(result.fee, Decimal("0.000012"))
        self.assertEqual(result.base_token_amount_removed, Decimal("10"))
        self.assertEqual(result.quote_token_amount_removed, Decimal("20"))

        # Test error case - transaction failure
        error_response = MagicMock(spec=Response)
        error_response.status = ResponseStatus.SUCCESS
        error_response.result = {
            "engine_result": "tecPATH_DRY",
            "tx_json": {"hash": "error_hash"},
            "meta": {"AffectedNodes": []},
        }
        self.connector._submit_transaction.return_value = error_response

    async def test_amm_get_balance(self):
        # Mock pool info
        mock_pool_info = PoolInfo(
            address="rAMMPoolAddress123",
            base_token_address=self.xrp,
            quote_token_address=self.usd,
            lp_token_address=self.lp_token,
            fee_pct=Decimal("0.005"),
            price=Decimal("2"),
            base_token_amount=Decimal("1000"),
            quote_token_amount=Decimal("2000"),
            lp_token_amount=Decimal("1000"),
            pool_type="XRPL-AMM",
        )
        self.connector.amm_get_pool_info = AsyncMock(return_value=mock_pool_info)

        # Mock account lines response with LP tokens
        resp = MagicMock(spec=Response)
        resp.result = {
            "lines": [
                {
                    "account": "rAMMPoolAddress123",
                    "balance": "100",
                    "currency": "534F4C4F00000000000000000000000000000000",  # noqa: mock
                }
            ]
        }
        self.connector.request_with_retry.return_value = resp

        # Use the real implementation for this test
        self.connector.amm_get_balance = XrplExchange.amm_get_balance.__get__(self.connector)

        # Call the method
        result = await self.connector.amm_get_balance(
            pool_address="rAMMPoolAddress123", wallet_address="rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R"  # noqa: mock
        )

        # Verify the result
        self.assertEqual(result["lp_token_amount"], Decimal("100"))
        self.assertEqual(result["lp_token_amount_pct"], Decimal("10"))  # 100/1000 * 100 = 10%
        self.assertEqual(result["base_token_lp_amount"], Decimal("100"))  # 10% of 1000 = 100
        self.assertEqual(result["quote_token_lp_amount"], Decimal("200"))  # 10% of 2000 = 200

        # Test case with no LP tokens
        self.connector.request_with_retry.reset_mock()
        resp.result = {"lines": []}
        self.connector.request_with_retry.return_value = resp

        # Call the method
        result = await self.connector.amm_get_balance(
            pool_address="rAMMPoolAddress123", wallet_address="rP9jPyP5kyvFRb6ZiLdcyzmUZ1Zp5t2V7R"  # noqa: mock
        )

        # Verify zero balances are returned
        self.assertEqual(result["lp_token_amount"], Decimal("0"))
        self.assertEqual(result["lp_token_amount_pct"], Decimal("0"))
        self.assertEqual(result["base_token_lp_amount"], Decimal("0"))
        self.assertEqual(result["quote_token_lp_amount"], Decimal("0"))

    @patch("hummingbot.connector.exchange.xrpl.xrpl_utils.convert_string_to_hex")
    @patch("xrpl.utils.xrp_to_drops")
    async def test_amm_add_liquidity_none_pool_info(self, mock_xrp_to_drops, mock_convert_string_to_hex):
        # Setup mocks
        mock_xrp_to_drops.return_value = "10000000"
        mock_convert_string_to_hex.return_value = (
            "68626F742D6C69717569646974792D61646465642D73756363657373"  # noqa: mock
        )

        # Mock amm_get_pool_info to return None
        self.connector.amm_get_pool_info = AsyncMock(return_value=None)

        # Use the real implementation for amm_add_liquidity
        self.connector.amm_add_liquidity = XrplExchange.amm_add_liquidity.__get__(self.connector)

        # Call amm_add_liquidity
        result = await self.connector.amm_add_liquidity(
            pool_address="rAMMPoolAddress123",  # noqa: mock
            wallet_address="rWalletAddress123",  # noqa: mock
            base_token_amount=Decimal("10"),
            quote_token_amount=Decimal("20"),
            slippage_pct=Decimal("0.01"),
        )

        # Verify the result is None
        self.assertIsNone(result)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_utils.convert_string_to_hex")
    @patch("xrpl.utils.xrp_to_drops")
    async def test_amm_add_liquidity_none_quote(self, mock_xrp_to_drops, mock_convert_string_to_hex):
        # Setup mocks
        mock_xrp_to_drops.return_value = "10000000"
        mock_convert_string_to_hex.return_value = (
            "68626F742D6C69717569646974792D61646465642D73756363657373"  # noqa: mock
        )

        # Mock pool info
        mock_pool_info = PoolInfo(
            address="rAMMPoolAddress123",  # noqa: mock
            base_token_address=self.xrp,
            quote_token_address=self.usd,
            lp_token_address=self.lp_token,
            fee_pct=Decimal("0.005"),
            price=Decimal("2"),
            base_token_amount=Decimal("1000"),
            quote_token_amount=Decimal("2000"),
            lp_token_amount=Decimal("1000"),
            pool_type="XRPL-AMM",
        )
        self.connector.amm_get_pool_info = AsyncMock(return_value=mock_pool_info)

        # Mock amm_quote_add_liquidity to return None
        self.connector.amm_quote_add_liquidity = AsyncMock(return_value=None)

        # Use the real implementation for amm_add_liquidity
        self.connector.amm_add_liquidity = XrplExchange.amm_add_liquidity.__get__(self.connector)

        # Call amm_add_liquidity
        result = await self.connector.amm_add_liquidity(
            pool_address="rAMMPoolAddress123",  # noqa: mock
            wallet_address="rWalletAddress123",  # noqa: mock
            base_token_amount=Decimal("10"),
            quote_token_amount=Decimal("20"),
            slippage_pct=Decimal("0.01"),
        )

        # Verify the result is None
        self.assertIsNone(result)
