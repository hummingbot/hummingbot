"""Tests for binary options order type abstractions."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from controllers.generic.binary_options.order_types import (
    ALL_ORDER_TYPES,
    LIMIT_BUY_BOTH,
    LIMIT_BUY_NO,
    LIMIT_BUY_YES,
    LIMIT_SELL_EXIT,
    LIMIT_SELL_NO_HELD,
    LIMIT_SELL_YES_HELD,
    MARKET_BUY_NO,
    MARKET_BUY_YES,
    MARKET_SELL_EXIT,
    MINT_LIMIT_SELL_BOTH,
    MINT_LIMIT_SELL_NO,
    MINT_LIMIT_SELL_YES,
    MINT_MARKET_SELL_NO,
    MINT_MARKET_SELL_YES,
    BinaryOrderExecutor,
    ExecutionMethod,
    OrderIntent,
    OrderRequest,
    OrderResult,
    OrderSide,
)

# ── Enum Tests ─────────────────────────────────────────────────


class TestOrderSide:
    def test_values(self):
        assert OrderSide.BUY_YES == "buy_yes"
        assert OrderSide.BUY_NO == "buy_no"
        assert OrderSide.SELL_YES == "sell_yes"
        assert OrderSide.SELL_NO == "sell_no"

    def test_count(self):
        assert len(OrderSide) == 4


class TestExecutionMethod:
    def test_values(self):
        assert ExecutionMethod.MARKET == "market"
        assert ExecutionMethod.LIMIT == "limit"

    def test_count(self):
        assert len(ExecutionMethod) == 2


class TestOrderIntent:
    def test_values(self):
        assert OrderIntent.ENTRY == "entry"
        assert OrderIntent.EXIT == "exit"
        assert OrderIntent.MINT_ENTRY == "mint_entry"
        assert OrderIntent.NEUTRAL == "neutral"

    def test_count(self):
        assert len(OrderIntent) == 4


# ── Registry Tests ─────────────────────────────────────────────


class TestOrderTypeRegistry:
    def test_all_14_types_exist(self):
        assert len(ALL_ORDER_TYPES) == 14

    def test_all_unique_names(self):
        names = [ot.name for ot in ALL_ORDER_TYPES]
        assert len(names) == len(set(names))

    def test_frozen(self):
        with pytest.raises(AttributeError):
            MARKET_BUY_YES.name = "changed"

    def test_bullish_entries(self):
        assert MARKET_BUY_YES.side == OrderSide.BUY_YES
        assert MARKET_BUY_YES.method == ExecutionMethod.MARKET
        assert not MARKET_BUY_YES.is_maker

        assert LIMIT_BUY_YES.side == OrderSide.BUY_YES
        assert LIMIT_BUY_YES.method == ExecutionMethod.LIMIT
        assert LIMIT_BUY_YES.is_maker
        assert LIMIT_BUY_YES.lp_reward_eligible

    def test_bearish_entries(self):
        assert MARKET_BUY_NO.side == OrderSide.BUY_NO
        assert LIMIT_BUY_NO.side == OrderSide.BUY_NO
        assert LIMIT_BUY_NO.is_maker

    def test_mint_paths_require_mint(self):
        mint_types = [
            MINT_MARKET_SELL_NO, MINT_LIMIT_SELL_NO,
            MINT_MARKET_SELL_YES, MINT_LIMIT_SELL_YES,
            MINT_LIMIT_SELL_BOTH,
        ]
        for ot in mint_types:
            assert ot.requires_mint, f"{ot.name} should require mint"
            assert not ot.requires_token_balance, f"{ot.name} should not require token balance"

    def test_held_token_sells(self):
        for ot in [LIMIT_SELL_NO_HELD, LIMIT_SELL_YES_HELD]:
            assert ot.requires_token_balance
            assert not ot.requires_mint
            assert ot.intent == OrderIntent.ENTRY

    def test_exits_require_token_balance(self):
        for ot in [MARKET_SELL_EXIT, LIMIT_SELL_EXIT]:
            assert ot.requires_token_balance
            assert ot.intent == OrderIntent.EXIT

    def test_neutral_types(self):
        assert MINT_LIMIT_SELL_BOTH.intent == OrderIntent.NEUTRAL
        assert MINT_LIMIT_SELL_BOTH.requires_mint
        assert LIMIT_BUY_BOTH.intent == OrderIntent.NEUTRAL
        assert not LIMIT_BUY_BOTH.requires_mint

    def test_market_orders_not_maker(self):
        for ot in ALL_ORDER_TYPES:
            if ot.method == ExecutionMethod.MARKET:
                assert not ot.is_maker, f"{ot.name} is MARKET but marked as maker"
                assert not ot.lp_reward_eligible
                assert not ot.maker_rebate_eligible

    def test_limit_orders_are_maker(self):
        for ot in ALL_ORDER_TYPES:
            if ot.method == ExecutionMethod.LIMIT:
                assert ot.is_maker, f"{ot.name} is LIMIT but not marked as maker"


# ── Data Class Tests ───────────────────────────────────────────


class TestOrderRequest:
    def test_creation(self):
        req = OrderRequest(
            order_type=MARKET_BUY_YES,
            market_slug="test-market",
            price=0.55,
            size=10.0,
        )
        assert req.market_slug == "test-market"
        assert req.metadata == {}

    def test_metadata_default(self):
        req = OrderRequest(
            order_type=LIMIT_BUY_YES,
            market_slug="m",
            price=0.5,
            size=1.0,
            metadata={"signal": "strong"},
        )
        assert req.metadata["signal"] == "strong"


class TestOrderResult:
    def test_creation(self):
        result = OrderResult(
            success=True,
            order_id="abc123",
            order_type=MARKET_BUY_YES,
            market_slug="test",
            price=0.55,
            size=10.0,
            status="filled",
            error=None,
            timestamp=time.time(),
        )
        assert result.success
        assert result.order_id == "abc123"


# ── Executor Tests ─────────────────────────────────────────────


def _mock_connector():
    """Create a mock connector with async methods."""
    connector = MagicMock()
    connector.buy = AsyncMock(return_value={
        "order_id": "buy-123",
        "status": "open",
    })
    connector.sell = AsyncMock(return_value={
        "order_id": "sell-456",
        "status": "open",
    })
    connector.cancel = AsyncMock(return_value={
        "message": "cancelled",
        "order_id": "buy-123",
    })
    connector.cancel_all = AsyncMock(return_value={
        "message": "cancelled all",
    })
    connector.mint_tokens = AsyncMock(return_value={
        "tx_hash": "0xabc",
        "status": 1,
        "gas_used": 100000,
        "amount_minted": 10.0,
    })
    return connector


class TestBinaryOrderExecutor:
    @pytest.fixture
    def executor(self):
        return BinaryOrderExecutor(_mock_connector())

    @pytest.mark.asyncio
    async def test_simple_buy_yes_market(self, executor):
        req = OrderRequest(
            order_type=MARKET_BUY_YES,
            market_slug="test-market",
            price=0.55,
            size=10.0,
        )
        result = await executor.execute(req)
        assert result.success
        assert result.order_id == "buy-123"
        executor.connector.buy.assert_called_once_with(
            market_slug="test-market",
            price=0.55,
            size=10.0,
            order_type="FOK",
            token="YES",
        )

    @pytest.mark.asyncio
    async def test_simple_buy_yes_limit(self, executor):
        req = OrderRequest(
            order_type=LIMIT_BUY_YES,
            market_slug="test-market",
            price=0.50,
            size=20.0,
        )
        result = await executor.execute(req)
        assert result.success
        executor.connector.buy.assert_called_once_with(
            market_slug="test-market",
            price=0.50,
            size=20.0,
            order_type="GTC",
            token="YES",
        )

    @pytest.mark.asyncio
    async def test_simple_buy_no(self, executor):
        req = OrderRequest(
            order_type=MARKET_BUY_NO,
            market_slug="m",
            price=0.40,
            size=5.0,
        )
        result = await executor.execute(req)
        assert result.success
        executor.connector.buy.assert_called_once_with(
            market_slug="m",
            price=0.40,
            size=5.0,
            order_type="FOK",
            token="NO",
        )

    @pytest.mark.asyncio
    async def test_simple_sell_exit(self, executor):
        req = OrderRequest(
            order_type=MARKET_SELL_EXIT,
            market_slug="m",
            price=0.60,
            size=10.0,
        )
        result = await executor.execute(req)
        assert result.success
        executor.connector.sell.assert_called_once_with(
            market_slug="m",
            price=0.60,
            size=10.0,
            order_type="FOK",
            token="YES",
        )

    @pytest.mark.asyncio
    async def test_limit_sell_no_held(self, executor):
        req = OrderRequest(
            order_type=LIMIT_SELL_NO_HELD,
            market_slug="m",
            price=0.45,
            size=10.0,
        )
        result = await executor.execute(req)
        assert result.success
        executor.connector.sell.assert_called_once_with(
            market_slug="m",
            price=0.45,
            size=10.0,
            order_type="GTC",
            token="NO",
        )

    @pytest.mark.asyncio
    async def test_mint_and_sell(self, executor):
        req = OrderRequest(
            order_type=MINT_MARKET_SELL_NO,
            market_slug="m",
            price=0.45,
            size=10.0,
        )
        result = await executor.execute(req)
        assert result.success
        executor.connector.mint_tokens.assert_called_once_with(
            market_slug="m",
            amount_usdc=10.0,
        )
        executor.connector.sell.assert_called_once_with(
            market_slug="m",
            price=0.45,
            size=10.0,
            order_type="FOK",
            token="NO",
        )

    @pytest.mark.asyncio
    async def test_mint_and_sell_both(self, executor):
        req = OrderRequest(
            order_type=MINT_LIMIT_SELL_BOTH,
            market_slug="m",
            price=0.50,
            size=10.0,
        )
        result = await executor.execute(req)
        assert result.success
        executor.connector.mint_tokens.assert_called_once()
        assert executor.connector.sell.call_count == 2
        # Check both YES and NO sells
        calls = executor.connector.sell.call_args_list
        tokens_sold = {c.kwargs["token"] for c in calls}
        assert tokens_sold == {"YES", "NO"}

    @pytest.mark.asyncio
    async def test_mint_failure_stops_execution(self, executor):
        executor.connector.mint_tokens = AsyncMock(return_value={
            "tx_hash": "0xfail",
            "status": 0,
        })
        req = OrderRequest(
            order_type=MINT_MARKET_SELL_NO,
            market_slug="m",
            price=0.45,
            size=10.0,
        )
        result = await executor.execute(req)
        assert not result.success
        assert "failed" in result.status
        executor.connector.sell.assert_not_called()

    @pytest.mark.asyncio
    async def test_cancel_order(self, executor):
        result = await executor.cancel_order("buy-123")
        assert result.success
        assert result.status == "cancelled"
        executor.connector.cancel.assert_called_once_with("buy-123")

    @pytest.mark.asyncio
    async def test_cancel_all_orders(self, executor):
        result = await executor.cancel_all_orders("test-market")
        assert result.success
        assert result.status == "cancelled"
        executor.connector.cancel_all.assert_called_once_with("test-market")

    @pytest.mark.asyncio
    async def test_connector_error_returns_failed_result(self, executor):
        executor.connector.buy = AsyncMock(side_effect=Exception("API down"))
        req = OrderRequest(
            order_type=MARKET_BUY_YES,
            market_slug="m",
            price=0.55,
            size=10.0,
        )
        result = await executor.execute(req)
        assert not result.success
        assert result.status == "failed"
        assert "API down" in result.error

    @pytest.mark.asyncio
    async def test_limit_buy_both_routes_simple(self, executor):
        """LIMIT_BUY_BOTH doesn't require mint, routes to simple."""
        req = OrderRequest(
            order_type=LIMIT_BUY_BOTH,
            market_slug="m",
            price=0.48,
            size=10.0,
        )
        result = await executor.execute(req)
        assert result.success
        # Routes through _execute_simple_order since requires_mint=False
        executor.connector.buy.assert_called_once()
        executor.connector.mint_tokens.assert_not_called()
