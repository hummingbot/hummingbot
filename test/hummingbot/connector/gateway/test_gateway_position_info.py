import unittest
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.gateway.gateway import Gateway


def _fake_connector(position_info_side_effect=None):
    """Bare `self` for calling Gateway.get_position_info_fresh unbound.

    The method only touches network/address/logger and the gateway HTTP client,
    so a full connector (which needs a live event loop and settings registration)
    is unnecessary.
    """
    fake = MagicMock()
    fake.network = "mainnet-beta"
    fake.address = "test_wallet"
    gateway_instance = MagicMock()
    gateway_instance.clmm_position_info = AsyncMock(side_effect=position_info_side_effect)
    fake._get_gateway_instance = MagicMock(return_value=gateway_instance)
    fake.logger = MagicMock(return_value=MagicMock())
    return fake


class GatewayPositionInfoContractTest(unittest.IsolatedAsyncioTestCase):
    """Pins the None-vs-raise contract of get_position_info_fresh.

    None must mean "the position definitively does not exist on-chain";
    everything else must raise. Callers (LPExecutor close pre-flight and
    external-close detection) treat None as "already closed", so a swallowed
    transient error here silently abandons a live position.
    """

    async def test_position_specific_404_returns_none(self):
        # Gateway position-info routes raise "Position not found: X" /
        # "Position not found or closed: X" for a nonexistent position
        fake = _fake_connector(
            ValueError("Gateway error: Position not found or closed: pos123 (Not Found) [code: X]")
        )
        result = await Gateway.get_position_info_fresh(
            fake, trading_pair="SOL-USDC", dex_name="orca", trading_type="clmm", position_address="pos123"
        )
        self.assertIsNone(result)

    async def test_unrelated_404_raises(self):
        # The HTTP client stamps "(Not Found)" on EVERY 404 — a missing route
        # after a Gateway redeploy must not read as "position gone"
        fake = _fake_connector(
            ValueError("Gateway error: Route GET:/connectors/orca/clmm/position-info not found (Not Found)")
        )
        with self.assertRaises(ValueError):
            await Gateway.get_position_info_fresh(
                fake, trading_pair="SOL-USDC", dex_name="orca", trading_type="clmm", position_address="pos123"
            )

    async def test_missing_wallet_404_raises(self):
        fake = _fake_connector(ValueError("Gateway error: Wallet not found: test_wallet (Not Found)"))
        with self.assertRaises(ValueError):
            await Gateway.get_position_info_fresh(
                fake, trading_pair="SOL-USDC", dex_name="orca", trading_type="clmm", position_address="pos123"
            )

    async def test_transient_error_raises(self):
        fake = _fake_connector(ConnectionError("Cannot connect to host localhost:15888"))
        with self.assertRaises(ConnectionError):
            await Gateway.get_position_info_fresh(
                fake, trading_pair="SOL-USDC", dex_name="orca", trading_type="clmm", position_address="pos123"
            )


if __name__ == "__main__":
    unittest.main()
