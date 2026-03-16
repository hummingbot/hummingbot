"""Binary options order type abstractions for Limitless prediction markets.

Defines order types as composable, self-contained execution paths between
the controller (brain) and the connector (API). Pure plumbing — no trading logic.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# ── Enums ──────────────────────────────────────────────────────


class OrderSide(str, Enum):
    """Which token to trade and in which direction."""
    BUY_YES = "buy_yes"
    BUY_NO = "buy_no"
    SELL_YES = "sell_yes"
    SELL_NO = "sell_no"


class ExecutionMethod(str, Enum):
    """How the order executes on the book."""
    MARKET = "market"
    LIMIT = "limit"


class OrderIntent(str, Enum):
    """Why the order is being placed."""
    ENTRY = "entry"
    EXIT = "exit"
    MINT_ENTRY = "mint_entry"
    NEUTRAL = "neutral"


# ── Data Classes ───────────────────────────────────────────────


@dataclass(frozen=True)
class OrderTypeConfig:
    """Immutable definition of an execution path. One per order type."""
    name: str
    side: OrderSide
    method: ExecutionMethod
    intent: OrderIntent
    is_maker: bool
    lp_reward_eligible: bool
    maker_rebate_eligible: bool
    requires_token_balance: bool
    requires_mint: bool
    capital_locked: str


@dataclass
class OrderRequest:
    """What the controller sends to execute an order."""
    order_type: OrderTypeConfig
    market_slug: str
    price: Optional[float]
    size: float
    metadata: dict = field(default_factory=dict)


@dataclass
class OrderResult:
    """What comes back after execution."""
    success: bool
    order_id: Optional[str]
    order_type: OrderTypeConfig
    market_slug: str
    price: Optional[float]
    size: float
    status: str
    error: Optional[str]
    timestamp: float
    metadata: dict = field(default_factory=dict)


# ── Order Type Registry ───────────────────────────────────────

# === BULLISH ENTRIES ===

MARKET_BUY_YES = OrderTypeConfig(
    name="Market Buy YES",
    side=OrderSide.BUY_YES,
    method=ExecutionMethod.MARKET,
    intent=OrderIntent.ENTRY,
    is_maker=False,
    lp_reward_eligible=False,
    maker_rebate_eligible=False,
    requires_token_balance=False,
    requires_mint=False,
    capital_locked="yes_price",
)

LIMIT_BUY_YES = OrderTypeConfig(
    name="Limit Buy YES",
    side=OrderSide.BUY_YES,
    method=ExecutionMethod.LIMIT,
    intent=OrderIntent.ENTRY,
    is_maker=True,
    lp_reward_eligible=True,
    maker_rebate_eligible=True,
    requires_token_balance=False,
    requires_mint=False,
    capital_locked="yes_price",
)

MINT_MARKET_SELL_NO = OrderTypeConfig(
    name="Mint + Market Sell NO",
    side=OrderSide.SELL_NO,
    method=ExecutionMethod.MARKET,
    intent=OrderIntent.MINT_ENTRY,
    is_maker=False,
    lp_reward_eligible=False,
    maker_rebate_eligible=False,
    requires_token_balance=False,
    requires_mint=True,
    capital_locked="1_usdc_mint",
)

MINT_LIMIT_SELL_NO = OrderTypeConfig(
    name="Mint + Limit Sell NO",
    side=OrderSide.SELL_NO,
    method=ExecutionMethod.LIMIT,
    intent=OrderIntent.MINT_ENTRY,
    is_maker=True,
    lp_reward_eligible=True,
    maker_rebate_eligible=True,
    requires_token_balance=False,
    requires_mint=True,
    capital_locked="1_usdc_mint",
)

LIMIT_SELL_NO_HELD = OrderTypeConfig(
    name="Limit Sell NO (held tokens)",
    side=OrderSide.SELL_NO,
    method=ExecutionMethod.LIMIT,
    intent=OrderIntent.ENTRY,
    is_maker=True,
    lp_reward_eligible=True,
    maker_rebate_eligible=True,
    requires_token_balance=True,
    requires_mint=False,
    capital_locked="none_already_held",
)

# === BEARISH ENTRIES ===

MARKET_BUY_NO = OrderTypeConfig(
    name="Market Buy NO",
    side=OrderSide.BUY_NO,
    method=ExecutionMethod.MARKET,
    intent=OrderIntent.ENTRY,
    is_maker=False,
    lp_reward_eligible=False,
    maker_rebate_eligible=False,
    requires_token_balance=False,
    requires_mint=False,
    capital_locked="no_price",
)

LIMIT_BUY_NO = OrderTypeConfig(
    name="Limit Buy NO",
    side=OrderSide.BUY_NO,
    method=ExecutionMethod.LIMIT,
    intent=OrderIntent.ENTRY,
    is_maker=True,
    lp_reward_eligible=True,
    maker_rebate_eligible=True,
    requires_token_balance=False,
    requires_mint=False,
    capital_locked="no_price",
)

MINT_MARKET_SELL_YES = OrderTypeConfig(
    name="Mint + Market Sell YES",
    side=OrderSide.SELL_YES,
    method=ExecutionMethod.MARKET,
    intent=OrderIntent.MINT_ENTRY,
    is_maker=False,
    lp_reward_eligible=False,
    maker_rebate_eligible=False,
    requires_token_balance=False,
    requires_mint=True,
    capital_locked="1_usdc_mint",
)

MINT_LIMIT_SELL_YES = OrderTypeConfig(
    name="Mint + Limit Sell YES",
    side=OrderSide.SELL_YES,
    method=ExecutionMethod.LIMIT,
    intent=OrderIntent.MINT_ENTRY,
    is_maker=True,
    lp_reward_eligible=True,
    maker_rebate_eligible=True,
    requires_token_balance=False,
    requires_mint=True,
    capital_locked="1_usdc_mint",
)

LIMIT_SELL_YES_HELD = OrderTypeConfig(
    name="Limit Sell YES (held tokens)",
    side=OrderSide.SELL_YES,
    method=ExecutionMethod.LIMIT,
    intent=OrderIntent.ENTRY,
    is_maker=True,
    lp_reward_eligible=True,
    maker_rebate_eligible=True,
    requires_token_balance=True,
    requires_mint=False,
    capital_locked="none_already_held",
)

# === EXITS ===

MARKET_SELL_EXIT = OrderTypeConfig(
    name="Market Sell (exit)",
    side=OrderSide.SELL_YES,
    method=ExecutionMethod.MARKET,
    intent=OrderIntent.EXIT,
    is_maker=False,
    lp_reward_eligible=False,
    maker_rebate_eligible=False,
    requires_token_balance=True,
    requires_mint=False,
    capital_locked="none_exit",
)

LIMIT_SELL_EXIT = OrderTypeConfig(
    name="Limit Sell (exit)",
    side=OrderSide.SELL_YES,
    method=ExecutionMethod.LIMIT,
    intent=OrderIntent.EXIT,
    is_maker=True,
    lp_reward_eligible=True,
    maker_rebate_eligible=True,
    requires_token_balance=True,
    requires_mint=False,
    capital_locked="none_exit",
)

# === NEUTRAL (Phase 2) ===

MINT_LIMIT_SELL_BOTH = OrderTypeConfig(
    name="Mint + Limit Sell Both (delta neutral)",
    side=OrderSide.SELL_YES,
    method=ExecutionMethod.LIMIT,
    intent=OrderIntent.NEUTRAL,
    is_maker=True,
    lp_reward_eligible=True,
    maker_rebate_eligible=True,
    requires_token_balance=False,
    requires_mint=True,
    capital_locked="1_usdc_mint",
)

LIMIT_BUY_BOTH = OrderTypeConfig(
    name="Limit Buy Both (arb: YES+NO < $1)",
    side=OrderSide.BUY_YES,
    method=ExecutionMethod.LIMIT,
    intent=OrderIntent.NEUTRAL,
    is_maker=True,
    lp_reward_eligible=True,
    maker_rebate_eligible=True,
    requires_token_balance=False,
    requires_mint=False,
    capital_locked="yes_price_plus_no_price",
)

# All 14 order types for easy iteration
ALL_ORDER_TYPES = [
    MARKET_BUY_YES, LIMIT_BUY_YES,
    MINT_MARKET_SELL_NO, MINT_LIMIT_SELL_NO, LIMIT_SELL_NO_HELD,
    MARKET_BUY_NO, LIMIT_BUY_NO,
    MINT_MARKET_SELL_YES, MINT_LIMIT_SELL_YES, LIMIT_SELL_YES_HELD,
    MARKET_SELL_EXIT, LIMIT_SELL_EXIT,
    MINT_LIMIT_SELL_BOTH, LIMIT_BUY_BOTH,
]


# ── Connector Method Mapping ──────────────────────────────────

# Maps OrderSide to (connector_method_name, token_string)
_SIDE_TO_CONNECTOR = {
    OrderSide.BUY_YES: ("buy", "YES"),
    OrderSide.BUY_NO: ("buy", "NO"),
    OrderSide.SELL_YES: ("sell", "YES"),
    OrderSide.SELL_NO: ("sell", "NO"),
}

# Maps ExecutionMethod to SDK order type string
_METHOD_TO_ORDER_TYPE = {
    ExecutionMethod.MARKET: "FOK",
    ExecutionMethod.LIMIT: "GTC",
}


# ── BinaryOrderExecutor ───────────────────────────────────────


class BinaryOrderExecutor:
    """Executes order requests via the Limitless connector.

    No trading logic — just maps order types to connector method calls.
    """

    def __init__(self, connector):
        """
        Args:
            connector: LimitlessConnector instance (started).
        """
        self.connector = connector

    async def execute(self, request: OrderRequest) -> OrderResult:
        """Execute an order request.

        Routes to the correct connector method(s) based on order type.
        Handles mint-then-sell sequences for mint paths.
        """
        ot = request.order_type

        try:
            if ot.requires_mint:
                if ot.intent == OrderIntent.NEUTRAL:
                    return await self._execute_mint_and_sell_both(request)
                else:
                    return await self._execute_mint_and_sell(request)
            else:
                return await self._execute_simple_order(request)
        except Exception as exc:
            return OrderResult(
                success=False,
                order_id=None,
                order_type=ot,
                market_slug=request.market_slug,
                price=request.price,
                size=request.size,
                status="failed",
                error=str(exc),
                timestamp=time.time(),
                metadata=request.metadata,
            )

    async def _execute_simple_order(self, request: OrderRequest) -> OrderResult:
        """Single buy or sell via connector.buy() / connector.sell()."""
        ot = request.order_type
        method_name, token = _SIDE_TO_CONNECTOR[ot.side]
        order_type_str = _METHOD_TO_ORDER_TYPE[ot.method]

        connector_method = getattr(self.connector, method_name)
        result = await connector_method(
            market_slug=request.market_slug,
            price=request.price,
            size=request.size,
            order_type=order_type_str,
            token=token,
        )

        order_id = result.get("order_id")
        status = result.get("status", "submitted")

        return OrderResult(
            success=True,
            order_id=str(order_id) if order_id else None,
            order_type=ot,
            market_slug=request.market_slug,
            price=request.price,
            size=request.size,
            status=status,
            error=None,
            timestamp=time.time(),
            metadata={**request.metadata, "connector_result": result},
        )

    async def _execute_mint_and_sell(self, request: OrderRequest) -> OrderResult:
        """Mint tokens, then place sell order on the specified side."""
        ot = request.order_type

        # Step 1: Mint
        mint_result = await self.connector.mint_tokens(
            market_slug=request.market_slug,
            amount_usdc=request.size,
        )

        if mint_result.get("status") != 1:
            return OrderResult(
                success=False,
                order_id=None,
                order_type=ot,
                market_slug=request.market_slug,
                price=request.price,
                size=request.size,
                status="failed",
                error=f"Mint tx failed: {mint_result.get('tx_hash', 'unknown')}",
                timestamp=time.time(),
                metadata={**request.metadata, "mint_result": mint_result},
            )

        # Step 2: Sell the specified side
        method_name, token = _SIDE_TO_CONNECTOR[ot.side]
        order_type_str = _METHOD_TO_ORDER_TYPE[ot.method]

        connector_method = getattr(self.connector, method_name)
        sell_result = await connector_method(
            market_slug=request.market_slug,
            price=request.price,
            size=request.size,
            order_type=order_type_str,
            token=token,
        )

        order_id = sell_result.get("order_id")
        status = sell_result.get("status", "submitted")

        return OrderResult(
            success=True,
            order_id=str(order_id) if order_id else None,
            order_type=ot,
            market_slug=request.market_slug,
            price=request.price,
            size=request.size,
            status=status,
            error=None,
            timestamp=time.time(),
            metadata={
                **request.metadata,
                "mint_result": mint_result,
                "connector_result": sell_result,
            },
        )

    async def _execute_mint_and_sell_both(self, request: OrderRequest) -> OrderResult:
        """Mint tokens, then place sell orders on BOTH sides."""
        ot = request.order_type

        # Step 1: Mint
        mint_result = await self.connector.mint_tokens(
            market_slug=request.market_slug,
            amount_usdc=request.size,
        )

        if mint_result.get("status") != 1:
            return OrderResult(
                success=False,
                order_id=None,
                order_type=ot,
                market_slug=request.market_slug,
                price=request.price,
                size=request.size,
                status="failed",
                error=f"Mint tx failed: {mint_result.get('tx_hash', 'unknown')}",
                timestamp=time.time(),
                metadata={**request.metadata, "mint_result": mint_result},
            )

        order_type_str = _METHOD_TO_ORDER_TYPE[ot.method]

        # Step 2: Sell YES
        yes_result = await self.connector.sell(
            market_slug=request.market_slug,
            price=request.price,
            size=request.size,
            order_type=order_type_str,
            token="YES",
        )

        # Step 3: Sell NO
        no_result = await self.connector.sell(
            market_slug=request.market_slug,
            price=request.price,
            size=request.size,
            order_type=order_type_str,
            token="NO",
        )

        yes_id = yes_result.get("order_id")
        no_id = no_result.get("order_id")

        return OrderResult(
            success=True,
            order_id=str(yes_id) if yes_id else None,
            order_type=ot,
            market_slug=request.market_slug,
            price=request.price,
            size=request.size,
            status="submitted",
            error=None,
            timestamp=time.time(),
            metadata={
                **request.metadata,
                "mint_result": mint_result,
                "yes_order": yes_result,
                "no_order": no_result,
                "yes_order_id": str(yes_id) if yes_id else None,
                "no_order_id": str(no_id) if no_id else None,
            },
        )

    async def cancel_order(self, order_id: str) -> OrderResult:
        """Cancel a single order."""
        result = await self.connector.cancel(order_id)
        return OrderResult(
            success=True,
            order_id=order_id,
            order_type=MARKET_BUY_YES,  # Placeholder — cancel doesn't need type
            market_slug="",
            price=None,
            size=0,
            status="cancelled",
            error=None,
            timestamp=time.time(),
            metadata={"connector_result": result},
        )

    async def cancel_all_orders(self, market_slug: str) -> OrderResult:
        """Cancel all orders on a market."""
        result = await self.connector.cancel_all(market_slug)
        return OrderResult(
            success=True,
            order_id=None,
            order_type=MARKET_BUY_YES,  # Placeholder
            market_slug=market_slug,
            price=None,
            size=0,
            status="cancelled",
            error=None,
            timestamp=time.time(),
            metadata={"connector_result": result},
        )
