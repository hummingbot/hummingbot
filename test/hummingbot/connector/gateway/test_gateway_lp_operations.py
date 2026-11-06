import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.gateway.gateway import CLMMPoolInfo, Gateway
from hummingbot.connector.gateway.gateway_base import TX_DATA_UNAVAILABLE
from hummingbot.core.data_type.common import TradeType


def _fake_connector():
    """Bare `self` for calling the Gateway LP verbs unbound.

    They only touch network/chain/address, the order tracker, the LP metadata dict and
    the gateway HTTP client, so a full connector (which needs a live event loop and
    settings registration) is unnecessary.
    """
    fake = MagicMock()
    fake.network = "mainnet-beta"
    fake.chain = "solana"
    fake.address = "WALLET"
    fake.logger = MagicMock(return_value=MagicMock())
    fake._lp_orders_metadata = {}
    fake._order_tracker.fetch_order.return_value = None
    fake.get_pool_address = AsyncMock(return_value="POOL")

    gateway_instance = MagicMock()
    fake._get_gateway_instance = MagicMock(return_value=gateway_instance)

    async def passthrough(operation, operation_name, max_retries=10, **kwargs):
        return await operation()

    fake._execute_with_retry = AsyncMock(side_effect=passthrough)
    return fake, gateway_instance


class GatewayLPRetryChokepointTest(unittest.IsolatedAsyncioTestCase):
    """Every LP transaction verb must go through _execute_with_retry.

    A Gateway transaction response carries a signature for status 0 (broadcast but
    unconfirmed) and status -1 (landed and failed) too, so returning the signature
    without that check books an unlanded or reverted transaction as a success.
    """

    async def test_clmm_remove_liquidity_goes_through_execute_with_retry(self):
        fake, gateway_instance = _fake_connector()
        gateway_instance.clmm_remove_liquidity = AsyncMock(
            return_value={"signature": "sig", "status": 1, "data": {"baseTokenAmountRemoved": 5}}
        )

        result = await Gateway._clmm_remove_liquidity(
            fake, TradeType.RANGE, "oid", "SOL-USDC", "POS", 50.0, dex_name="meteora"
        )

        self.assertEqual("sig", result)
        self.assertEqual(1, fake._execute_with_retry.await_count)
        self.assertEqual(Decimal("5"), fake._lp_orders_metadata["oid"]["base_amount"])

    async def test_clmm_remove_liquidity_failure_is_not_reported_as_success(self):
        fake, gateway_instance = _fake_connector()
        gateway_instance.clmm_remove_liquidity = AsyncMock(
            return_value={"signature": "sig", "status": -1}
        )
        fake._execute_with_retry = AsyncMock(
            side_effect=Exception("Transaction sig not confirmed on-chain [code: TX_NOT_CONFIRMED]")
        )

        result = await Gateway._clmm_remove_liquidity(
            fake, TradeType.RANGE, "oid", "SOL-USDC", "POS", 50.0, dex_name="meteora"
        )

        self.assertIsNone(result)
        self.assertTrue(fake._handle_operation_failure.called)

    async def test_amm_add_liquidity_goes_through_execute_with_retry(self):
        fake, gateway_instance = _fake_connector()
        gateway_instance.amm_add_liquidity = AsyncMock(return_value={"signature": "sig", "status": 1})

        result = await Gateway._amm_add_liquidity(
            fake, TradeType.RANGE, "oid", "SOL-USDC", 100.0, 1.0, 2.0, dex_name="meteora"
        )

        self.assertEqual("sig", result)
        self.assertEqual(1, fake._execute_with_retry.await_count)

    async def test_amm_remove_liquidity_goes_through_execute_with_retry_and_names_the_position(self):
        fake, gateway_instance = _fake_connector()
        gateway_instance.amm_remove_liquidity = AsyncMock(return_value={"signature": "sig", "status": 1})

        result = await Gateway._amm_remove_liquidity(
            fake, TradeType.RANGE, "oid", "SOL-USDC", 100.0, dex_name="meteora", position_address="POS"
        )

        self.assertEqual("sig", result)
        self.assertEqual(1, fake._execute_with_retry.await_count)
        self.assertEqual("POS", gateway_instance.amm_remove_liquidity.call_args.kwargs["position_address"])


class GatewayLPMissingResponseDataTest(unittest.IsolatedAsyncioTestCase):
    """A transaction reconciled from its signature comes back with no `data` block. The
    LP verbs must record that gap rather than reading the missing keys as zeros."""

    async def test_open_position_records_the_gap_instead_of_a_blank_address(self):
        fake, gateway_instance = _fake_connector()
        gateway_instance.clmm_open_position = AsyncMock(
            return_value={"signature": "sig", "status": 1, TX_DATA_UNAVAILABLE: True}
        )

        result = await Gateway._clmm_add_liquidity(
            fake, TradeType.RANGE, "oid", "SOL-USDC", 100.0,
            lower_price=90.0, upper_price=110.0, base_token_amount=1.0, dex_name="meteora",
        )

        self.assertEqual("sig", result)
        metadata = fake._lp_orders_metadata["oid"]
        self.assertTrue(metadata["data_unavailable"])
        # No blank position address, and no zero-valued amounts that read as real figures.
        self.assertNotIn("position_address", metadata)
        self.assertNotIn("position_rent", metadata)

    async def test_close_position_does_not_book_zero_fees_when_data_is_missing(self):
        fake, gateway_instance = _fake_connector()
        gateway_instance.clmm_close_position = AsyncMock(
            return_value={"signature": "sig", "status": 1, TX_DATA_UNAVAILABLE: True}
        )

        result = await Gateway._clmm_close_position(
            fake, TradeType.RANGE, "oid", "SOL-USDC", "POS", dex_name="meteora"
        )

        self.assertEqual("sig", result)
        metadata = fake._lp_orders_metadata["oid"]
        self.assertTrue(metadata["data_unavailable"])
        for key in ("base_fee", "quote_fee", "position_rent_refunded",
                    "base_amount", "quote_amount", "tx_fee"):
            self.assertNotIn(key, metadata)

    async def test_close_position_books_the_data_when_it_is_present(self):
        fake, gateway_instance = _fake_connector()
        gateway_instance.clmm_close_position = AsyncMock(return_value={
            "signature": "sig",
            "status": 1,
            "data": {
                "baseTokenAmountRemoved": 1.5,
                "quoteTokenAmountRemoved": 2.5,
                "baseFeeAmountCollected": 0.1,
                "quoteFeeAmountCollected": 0.2,
                "positionRentRefunded": 0.05,
                "fee": 0.001,
            },
        })

        await Gateway._clmm_close_position(
            fake, TradeType.RANGE, "oid", "SOL-USDC", "POS", dex_name="meteora"
        )

        metadata = fake._lp_orders_metadata["oid"]
        self.assertNotIn("data_unavailable", metadata)
        self.assertEqual(Decimal("0.1"), metadata["base_fee"])
        self.assertEqual(Decimal("0.05"), metadata["position_rent_refunded"])


class CLMMPoolInfoSchemaTest(unittest.TestCase):
    """binStep is Optional in Gateway's CLMM PoolInfo schema (only bin-based CLMMs report
    one). Requiring it turned every other connector's pool-info into a ValidationError
    that surfaced as a misleading "pool not found"."""

    def test_pool_info_parses_without_bin_step(self):
        pool = CLMMPoolInfo(**{
            "address": "POOL",
            "baseTokenAddress": "BASE",
            "quoteTokenAddress": "QUOTE",
            "feePct": 0.3,
            "price": 100.0,
            "baseTokenAmount": 1.0,
            "quoteTokenAmount": 2.0,
            "activeBinId": 7,
        })
        self.assertIsNone(pool.bin_step)

    def test_pool_info_keeps_bin_step_when_reported(self):
        pool = CLMMPoolInfo(**{
            "address": "POOL",
            "baseTokenAddress": "BASE",
            "quoteTokenAddress": "QUOTE",
            "binStep": 20,
            "feePct": 0.3,
            "price": 100.0,
            "baseTokenAmount": 1.0,
            "quoteTokenAmount": 2.0,
            "activeBinId": 7,
        })
        self.assertEqual(20, pool.bin_step)


if __name__ == "__main__":
    unittest.main()
