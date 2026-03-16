# SPEC: Binary Options Order Type Abstractions

## Goal

Build the execution layer between the controller (brain) and the connector (API).
Define order types as composable, self-contained units that the controller can invoke
without knowing the connector internals.

## File Structure

```
controllers/
  generic/
    binary_options/
      __init__.py
      order_types.py          ← THIS SPEC
```

## Dependencies

- Connector: `/home/tiger/hummingbot/hummingbot/connector/exchange/limitless/connector.py`
- Connector methods used:
  - `buy(market_slug, price, size, order_type='GTC', token='YES'|'NO')` → dict with order_id
  - `sell(market_slug, price, size, order_type='GTC', token='YES'|'NO')` → dict with order_id
  - `cancel(order_id)` → dict
  - `cancel_all(market_slug)` → dict
  - `get_order_status(order_id)` → dict with status, price, size, remaining
  - `get_order_book(market_slug)` → dict with bids, asks
  - `get_best_bid_ask(market_slug)` → tuple(bid, ask)
  - `redeem_positions(market_slug)` → dict with tx_hash, usdc_redeemed
  - `get_active_markets(ticker=None)` → list of market dicts
  - `get_market(market_slug)` → market dict
- Connector methods to ADD (same file, follow `redeem_positions` pattern):
  - `mint_tokens(market_slug, amount_usdc)` — calls CTF `splitPosition` ($N USDC → N YES + N NO)
  - `get_token_balance(market_slug, token)` — YES/NO token balance for a specific market
  - See "Connector Additions" section below for implementation details

## Enums

### OrderSide
```python
class OrderSide(str, Enum):
    BUY_YES = "buy_yes"       # Buy YES tokens (bullish)
    BUY_NO = "buy_no"         # Buy NO tokens (bearish)
    SELL_YES = "sell_yes"     # Sell YES tokens (exit bullish / enter bearish via mint)
    SELL_NO = "sell_no"       # Sell NO tokens (exit bearish / enter bullish via mint)
```

### ExecutionMethod
```python
class ExecutionMethod(str, Enum):
    MARKET = "market"         # Taker — immediate fill, pays spread
    LIMIT = "limit"           # Maker — rests on book, earns LP rewards + maker rebate
```

### OrderIntent
```python
class OrderIntent(str, Enum):
    ENTRY = "entry"           # Opening a new position
    EXIT = "exit"             # Closing an existing position
    MINT_ENTRY = "mint_entry" # Phase 2: Mint + sell opposite side to enter
    NEUTRAL = "neutral"       # Phase 2: Mint + sell both sides (delta neutral)
```

## Data Classes

### OrderTypeConfig
Immutable definition of an execution path. One per order type.

```python
@dataclass(frozen=True)
class OrderTypeConfig:
    name: str                           # Human-readable name
    side: OrderSide                     # Which token + direction
    method: ExecutionMethod             # Market or limit
    intent: OrderIntent                 # Entry, exit, mint, or neutral
    is_maker: bool                      # True = rests on book
    lp_reward_eligible: bool            # Earns LP rewards while resting
    maker_rebate_eligible: bool         # Earns maker rebate on fill
    requires_token_balance: bool        # Must hold tokens to execute (sells)
    requires_mint: bool                 # Phase 2: needs splitPosition first
    capital_locked: str                 # Description: "token_price", "1_usdc_mint", etc.
```

### OrderRequest
What the controller sends to execute an order.

```python
@dataclass
class OrderRequest:
    order_type: OrderTypeConfig         # Which execution path
    market_slug: str                    # Target market
    price: Optional[float]              # Limit price (None for market orders)
    size: float                         # Number of shares/contracts
    metadata: dict                      # Controller can attach signal info, timestamps, etc.
```

### OrderResult
What comes back after execution.

```python
@dataclass
class OrderResult:
    success: bool
    order_id: Optional[str]             # From connector
    order_type: OrderTypeConfig         # Echo back which path was used
    market_slug: str
    price: Optional[float]              # Actual price (may differ for market orders)
    size: float
    status: str                         # "open", "filled", "failed", "cancelled"
    error: Optional[str]                # Error message if failed
    timestamp: float                    # Execution timestamp
    metadata: dict                      # Pass-through from request + any execution details
```

## Order Type Registry

All 14 execution paths as `OrderTypeConfig` instances:

```python
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
    side=OrderSide.SELL_YES,  # Side set dynamically based on held token
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
    side=OrderSide.SELL_YES,  # Side set dynamically based on held token
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
    side=OrderSide.SELL_YES,  # Actually both sides — special case
    method=ExecutionMethod.LIMIT,
    intent=OrderIntent.NEUTRAL,
    is_maker=True,
    lp_reward_eligible=True,   # On BOTH books
    maker_rebate_eligible=True, # On BOTH fills
    requires_token_balance=False,
    requires_mint=True,
    capital_locked="1_usdc_mint",
)

LIMIT_BUY_BOTH = OrderTypeConfig(
    name="Limit Buy Both (arb: YES+NO < $1)",
    side=OrderSide.BUY_YES,  # Actually both sides — special case
    method=ExecutionMethod.LIMIT,
    intent=OrderIntent.NEUTRAL,
    is_maker=True,
    lp_reward_eligible=True,
    maker_rebate_eligible=True,
    requires_token_balance=False,
    requires_mint=False,
    capital_locked="yes_price_plus_no_price",
)
```

## OrderExecutor Class

Translates `OrderRequest` → connector calls. Pure plumbing, no decisions.

```python
class BinaryOrderExecutor:
    """Executes order requests via the Limitless connector.

    No trading logic — just maps order types to connector method calls.
    """

    def __init__(self, connector):
        """
        Args:
            connector: LimitlessConnector instance (started)
        """
        self.connector = connector

    async def execute(self, request: OrderRequest) -> OrderResult:
        """Execute an order request.

        Routes to the correct connector method(s) based on order type.
        Handles mint-then-sell sequences for mint paths.
        Returns OrderResult with success/failure and execution details.
        """
        ...

    async def _execute_simple_order(self, request: OrderRequest) -> OrderResult:
        """Single buy or sell via connector.buy() / connector.sell()."""
        ...

    async def _execute_mint_and_sell(self, request: OrderRequest) -> OrderResult:
        """Phase 2: mint tokens, then place sell order on opposite side."""
        ...

    async def _execute_mint_and_sell_both(self, request: OrderRequest) -> OrderResult:
        """Phase 2: mint tokens, then place sell orders on BOTH sides."""
        ...

    async def cancel_order(self, order_id: str) -> OrderResult:
        """Cancel a single order."""
        ...

    async def cancel_all_orders(self, market_slug: str) -> OrderResult:
        """Cancel all orders on a market."""
        ...
```

### Routing Logic (inside `execute()`)

```python
async def execute(self, request: OrderRequest) -> OrderResult:
    ot = request.order_type

    if ot.requires_mint:
        if ot.intent == OrderIntent.NEUTRAL:
            return await self._execute_mint_and_sell_both(request)
        else:
            return await self._execute_mint_and_sell(request)
    else:
        return await self._execute_simple_order(request)
```

### Connector Method Mapping

| OrderSide | ExecutionMethod | Connector Call |
|-----------|----------------|---------------|
| BUY_YES + MARKET | `connector.buy(slug, price, size, 'FOK', 'YES')` |
| BUY_YES + LIMIT | `connector.buy(slug, price, size, 'GTC', 'YES')` |
| BUY_NO + MARKET | `connector.buy(slug, price, size, 'FOK', 'NO')` |
| BUY_NO + LIMIT | `connector.buy(slug, price, size, 'GTC', 'NO')` |
| SELL_YES + MARKET | `connector.sell(slug, price, size, 'FOK', 'YES')` |
| SELL_YES + LIMIT | `connector.sell(slug, price, size, 'GTC', 'YES')` |
| SELL_NO + MARKET | `connector.sell(slug, price, size, 'FOK', 'NO')` |
| SELL_NO + LIMIT | `connector.sell(slug, price, size, 'GTC', 'NO')` |

For MINT paths (Phase 2):
1. `connector.mint_tokens(slug, amount)` → get YES + NO tokens
2. Then place SELL order(s) per mapping above

## Connector Additions

Add these two methods to `hummingbot/connector/exchange/limitless/connector.py`.
Use `redeem_positions()` as the template — same contract, same web3 pattern, same signing.

### `mint_tokens(market_slug, amount_usdc)`

Calls `splitPosition` on the Gnosis CTF contract (same address as redeem: `0xC9c98965297Bc527861c898329Ee280632B76e18`).

**What it does:** Send N USDC → receive N YES + N NO conditional tokens for that market.

**Steps:**
1. Fetch market (need `condition_id`, `collateral_token.address`)
2. Market must NOT be resolved (can't mint on settled markets)
3. Approve USDC spending to CTF contract if needed (ERC20 `approve`)
4. Call `splitPosition(collateralToken, parentCollectionId, conditionId, partition, amount)`
   - `collateralToken` = USDC address on Base
   - `parentCollectionId` = `bytes32(0)` (same as redeem)
   - `conditionId` = market's condition_id
   - `partition` = `[1, 2]` (YES=1, NO=2, same as redeem indexSets)
   - `amount` = amount_usdc × 1e6 (USDC has 6 decimals)
5. Return dict: `{tx_hash, status, gas_used, amount_minted, yes_token_id, no_token_id}`

**CTF ABI entry for splitPosition:**
```json
{
    "inputs": [
        {"name": "collateralToken", "type": "address"},
        {"name": "parentCollectionId", "type": "bytes32"},
        {"name": "conditionId", "type": "bytes32"},
        {"name": "partition", "type": "uint256[]"},
        {"name": "amount", "type": "uint256"}
    ],
    "name": "splitPosition",
    "outputs": [],
    "type": "function",
    "stateMutability": "nonpayable"
}
```

**USDC approval:** Before `splitPosition`, must ensure CTF contract has USDC allowance.
Check via `allowance(wallet, CTF_ADDRESS)`. If insufficient, call `approve(CTF_ADDRESS, amount)`.
Use max approval (`2**256 - 1`) to avoid re-approving every time — we already did this manually during testing.

### `get_token_balance(market_slug, token)`

Returns the balance of YES or NO tokens for a specific market.

**Steps:**
1. Resolve token_id via `_resolve_token_id(market_slug, token)`
2. Call `balanceOf(wallet_address, token_id)` on the CTF contract (ERC1155)
3. Return balance as float (divide by 1e6 for USDC-denominated amount)

**CTF ERC1155 ABI entry:**
```json
{
    "inputs": [
        {"name": "account", "type": "address"},
        {"name": "id", "type": "uint256"}
    ],
    "name": "balanceOf",
    "outputs": [{"name": "", "type": "uint256"}],
    "type": "function",
    "stateMutability": "view"
}
```

## Scope

Implement ALL of:
- All enums (`OrderSide`, `ExecutionMethod`, `OrderIntent`)
- All data classes (`OrderTypeConfig`, `OrderRequest`, `OrderResult`)
- All 14 `OrderTypeConfig` registry instances
- `BinaryOrderExecutor` with `execute()`, `_execute_simple_order()`, `cancel_order()`, `cancel_all_orders()`
- `BinaryOrderExecutor._execute_mint_and_sell()` — mint via connector, then place sell order
- `BinaryOrderExecutor._execute_mint_and_sell_both()` — mint via connector, then place sell on BOTH sides
- `connector.mint_tokens(market_slug, amount_usdc)` — on-chain splitPosition
- `connector.get_token_balance(market_slug, token)` — ERC1155 balanceOf

Do NOT implement:
- Any trading logic (signal interpretation, market selection, entry/exit decisions)
- Any parameter tuning

## Tests

The sub-agent should write a test file at `controllers/generic/binary_options/test_order_types.py`:
- Unit tests for all enums
- Unit tests for OrderTypeConfig registry (verify all 14 exist with correct properties)
- Unit tests for BinaryOrderExecutor with a mock connector
- Test that simple buy/sell routes to correct connector method
- Test that mint paths raise NotImplementedError
- Test cancel routing

## Notes for Sub-Agent

- Working directory: `/home/tiger/hummingbot/`
- Connector source: `hummingbot/connector/exchange/limitless/connector.py`
- Conda env: `hummingbot` at `/opt/miniconda3/envs/hummingbot/`
- Python 3.13
- Use dataclasses and enums from stdlib, not pydantic (keep this layer lightweight)
- Pre-commit hooks active (flake8, autopep8, isort) — code must pass
- The exit order types (MARKET_SELL_EXIT, LIMIT_SELL_EXIT) have a note about side being "set dynamically" — handle this by accepting a `token` override in OrderRequest or by having separate YES/NO exit configs. Decide which is cleaner.
- MINT_LIMIT_SELL_BOTH and LIMIT_BUY_BOTH are "both sides" — these need TWO connector calls. The executor should handle sequencing internally.
