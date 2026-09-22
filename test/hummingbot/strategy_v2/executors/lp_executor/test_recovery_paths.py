"""Recovering when Gateway's answer was incomplete, without guessing.

Two places an LP executor has to act on missing information, and in both the wrong
answer is worse than none: adopting the wrong position address later closes someone
else's position, and a malformed swap provider becomes a 400 in the middle of a
close-out swap rather than at startup.
"""
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.executors.lp_executor.data_types import LPExecutorConfig
from hummingbot.strategy_v2.executors.lp_executor.lp_executor import LPExecutor


def a_config(**overrides) -> LPExecutorConfig:
    fields = dict(
        id="test-recovery",
        timestamp=1234567890,
        connector_name="solana-mainnet-beta",
        lp_provider="meteora/clmm",
        trading_pair="SOL-USDC",
        pool_address="pool123",
        lower_price=Decimal("95"),
        upper_price=Decimal("105"),
        base_amount=Decimal("1"),
        quote_amount=Decimal("100"),
        side=TradeType.BUY,
    )
    fields.update(overrides)
    return LPExecutorConfig(**fields)


class TestSwapProviderResolution(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        super().setUp()
        self.strategy = MagicMock()
        self.strategy.current_timestamp = 1234567890

    def an_executor(self, **overrides) -> LPExecutor:
        return LPExecutor(self.strategy, a_config(**overrides), update_interval=1.0)

    async def test_a_provider_already_set_needs_no_lookup(self):
        executor = self.an_executor(swap_provider="jupiter/router")

        self.assertTrue(await executor._resolve_swap_provider())

    async def test_the_network_default_is_adopted(self):
        executor = self.an_executor()
        gateway = MagicMock()
        gateway.get_default_swap_provider = AsyncMock(return_value="jupiter/router")

        with patch("hummingbot.strategy_v2.executors.lp_executor.lp_executor.GatewayHttpClient") as client:
            client.get_instance.return_value = gateway
            self.assertTrue(await executor._resolve_swap_provider())

        self.assertEqual(executor.config.swap_provider, "jupiter/router")

    async def test_an_untyped_network_default_is_refused_at_startup(self):
        """Gateway's own config is not covered by LPExecutorConfig's validator, so a bare
        'jupiter' would sail through and become a 400 mid close-out swap instead."""
        executor = self.an_executor()
        gateway = MagicMock()
        gateway.get_default_swap_provider = AsyncMock(return_value="jupiter")

        with patch("hummingbot.strategy_v2.executors.lp_executor.lp_executor.GatewayHttpClient") as client:
            client.get_instance.return_value = gateway
            self.assertFalse(await executor._resolve_swap_provider())

        self.assertIsNone(executor.config.swap_provider)

    async def test_no_default_at_all_is_refused(self):
        executor = self.an_executor()
        gateway = MagicMock()
        gateway.get_default_swap_provider = AsyncMock(return_value=None)

        with patch("hummingbot.strategy_v2.executors.lp_executor.lp_executor.GatewayHttpClient") as client:
            client.get_instance.return_value = gateway
            self.assertFalse(await executor._resolve_swap_provider())


class TestPositionAddressRecovery(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        super().setUp()
        self.strategy = MagicMock()
        self.strategy.current_timestamp = 1234567890

    def an_executor(self) -> LPExecutor:
        return LPExecutor(self.strategy, a_config(), update_interval=1.0)

    def a_connector(self, positions=None, raises=None):
        connector = MagicMock()
        if raises is not None:
            connector.get_user_positions = AsyncMock(side_effect=raises)
        else:
            connector.get_user_positions = AsyncMock(return_value=positions or [])
        return connector

    def a_position(self, address, lower="95", upper="105"):
        return MagicMock(address=address, lower_price=Decimal(lower), upper_price=Decimal(upper))

    async def test_a_single_position_in_the_pool_is_unambiguous(self):
        executor = self.an_executor()

        found = await executor._recover_position_address(self.a_connector([self.a_position("only")]))

        self.assertEqual(found, "only")

    async def test_the_configured_bounds_pick_one_out_of_several(self):
        executor = self.an_executor()
        connector = self.a_connector([
            self.a_position("other", lower="50", upper="60"),
            self.a_position("mine", lower="95", upper="105"),
        ])

        self.assertEqual(await executor._recover_position_address(connector), "mine")

    async def test_two_positions_matching_the_same_bounds_are_ambiguous(self):
        """Adopting either would risk closing someone else's position later, so the
        caller escalates rather than the executor guessing."""
        executor = self.an_executor()
        connector = self.a_connector([self.a_position("a"), self.a_position("b")])

        self.assertEqual(await executor._recover_position_address(connector), "")

    async def test_a_lone_position_is_adopted_even_if_its_bounds_drifted(self):
        """One position in the pool is unambiguous by count alone — there is nothing else
        it could be — so the bounds check is not consulted."""
        executor = self.an_executor()
        connector = self.a_connector([self.a_position("only", lower="1", upper="2")])

        self.assertEqual(await executor._recover_position_address(connector), "only")

    async def test_several_positions_none_matching_the_bounds_is_ambiguous(self):
        executor = self.an_executor()
        connector = self.a_connector([
            self.a_position("far", lower="1", upper="2"),
            self.a_position("further", lower="500", upper="600"),
        ])

        self.assertEqual(await executor._recover_position_address(connector), "")

    async def test_a_listing_failure_recovers_nothing_rather_than_raising(self):
        executor = self.an_executor()

        found = await executor._recover_position_address(self.a_connector(raises=RuntimeError("rpc down")))

        self.assertEqual(found, "")


class TestBoundsMatching(IsolatedAsyncioWrapperTestCase):
    """The chain snaps bounds to ticks/bins, so an exact comparison would never match."""

    def setUp(self):
        super().setUp()
        self.strategy = MagicMock()
        self.strategy.current_timestamp = 1234567890
        self.executor = LPExecutor(self.strategy, a_config(), update_interval=1.0)

    def test_exact_bounds_match(self):
        self.assertTrue(self.executor._bounds_match(Decimal("95"), Decimal("105")))

    def test_bounds_snapped_within_tolerance_match(self):
        self.assertTrue(self.executor._bounds_match(Decimal("95.5"), Decimal("104.8")))

    def test_bounds_beyond_tolerance_do_not(self):
        self.assertFalse(self.executor._bounds_match(Decimal("80"), Decimal("105")))

    def test_a_configured_bound_of_zero_never_matches(self):
        """Guards the division. LPExecutorConfig's validator rejects a zero bound, so this
        state is only reachable by a config that bypassed validation — model_construct
        here builds exactly that, which is the situation the guard is for."""
        config = LPExecutorConfig.model_construct(
            **{**a_config().model_dump(), "lower_price": Decimal("0")}
        )
        executor = LPExecutor(self.strategy, config, update_interval=1.0)

        self.assertFalse(executor._bounds_match(Decimal("0"), Decimal("105")))
