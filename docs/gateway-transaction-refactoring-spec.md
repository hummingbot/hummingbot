# Gateway Transaction Refactoring Specification

> **Note**: This is one of the major changes planned for the **Hummingbot v2.7 release**. Community members are welcome to provide feedback on this specification before implementation work begins in June 2025. Please share your thoughts and suggestions in the [Hummingbot Discord](https://discord.gg/hummingbot) in the **#amm-connectors** channel or by creating an issue in the [Hummingbot repository](https://github.com/hummingbot/hummingbot/issues).

## Overview

This specification outlines a major refactoring of how Hummingbot handles blockchain transactions through Gateway. The goal is to move fee control and retry logic from Gateway to Hummingbot, making Gateway more stateless and giving Hummingbot full control over transaction fees and execution strategies.

## Current Architecture

### Transaction Flow
1. **Hummingbot** → sends operation request (e.g., `clmm_open_position`) with basic parameters
2. **Gateway** → constructs transaction, determines fees, handles retries, sends transaction
3. **Gateway** → returns success/failure with transaction hash
4. **Hummingbot** → polls for transaction status

### Problems with Current Architecture
- **No fee control**: Hummingbot cannot specify gas prices or priority fees
- **Limited visibility**: Hummingbot doesn't know actual fees until transaction completes
- **Inflexible retry logic**: Gateway's retry strategy is hardcoded
- **Stateful Gateway**: Gateway manages transaction state and retry logic
- **Chain-specific logic scattered**: Fee handling differs significantly between chains

## Proposed Architecture

### New Transaction Flow
1. **GatewayLP** → sends operation request to GatewayTxHandler with basic parameters
2. **GatewayTxHandler** → adds chain-specific fee parameters and sends to Gateway endpoint
3. **Gateway** → constructs transaction with fees, sends it, returns txHash and status
4. **GatewayTxHandler** → polls for status, determines if retry with higher fees is needed
5. **If retry needed** → GatewayTxHandler sends updated request with higher fees to Gateway
6. **GatewayLP** → can always poll for tx status using the hash

## Key Components

### 1. GatewayTxHandler (Python - Hummingbot)

```python
# Location: hummingbot/connector/gateway/gateway_tx_handler.py

from typing import Dict, Any, Optional
from decimal import Decimal
import asyncio
import time

class GatewayTxHandler:
    """
    Chain-agnostic transaction handler that manages fee determination and retry logic.
    Pulls configuration from Gateway's chain config files.
    """

    # Default values if not specified in Gateway config
    DEFAULT_CONFIG = {
        "defaultComputeUnits": 200000,
        "basePriorityFeePct": 90,
        "priorityFeeMultiplier": 2.0,
        "maxPriorityFee": 0.01,
        "minPriorityFee": 0.0001,
        "retryCount": 3,
        "retryIntervalMs": 2000
    }

    def __init__(self, gateway_client):
        self.gateway_client = gateway_client
        self._config_cache: Dict[str, Dict[str, Any]] = {}
        self._pending_transactions: Dict[str, Dict[str, Any]] = {}

    async def execute_transaction(
        self,
        chain: str,
        network: str,
        connector: str,
        method: str,
        params: Dict[str, Any],
        order_id: str,
        tracked_order: GatewayInFlightOrder
    ) -> str:
        """
        Execute a Gateway transaction with automatic fee management and retry logic.
        Always runs in non-blocking mode using safe_ensure_future.

        :param chain: Blockchain name (e.g., 'solana', 'ethereum')
        :param network: Network name (e.g., 'mainnet-beta', 'mainnet')
        :param connector: Connector name (e.g., 'raydium/clmm')
        :param method: API method (e.g., 'execute-swap', 'open-position')
        :param params: Method-specific parameters
        :param order_id: Client order ID for tracking
        :param tracked_order: The GatewayInFlightOrder to update
        :return: Transaction hash immediately (empty string if not yet available)
        """
        # 1. Get chain configuration from Gateway
        config = await self._get_chain_config(chain)

        # 2. Estimate initial priority fee based on chain's current conditions
        current_priority_fee = await self._estimate_priority_fee(chain, network, config)

        # 3. Apply min/max bounds from config
        min_fee = config.get("minPriorityFee", self.DEFAULT_CONFIG["minPriorityFee"])
        max_fee = config.get("maxPriorityFee", self.DEFAULT_CONFIG["maxPriorityFee"])
        current_priority_fee = max(min_fee, min(current_priority_fee, max_fee))

        # 4. Add standardized fee parameters to request
        fee_params = self._create_fee_params(current_priority_fee, config)
        request_params = {**params, **fee_params}

        # 5. Execute transaction with retry logic in background
        safe_ensure_future(self._execute_with_retry(
            chain=chain,
            network=network,
            connector=connector,
            method=method,
            params=request_params,
            config=config,
            initial_priority_fee=current_priority_fee,
            order_id=order_id,
            tracked_order=tracked_order
        ))

        # Return immediately - transaction will be processed in background
        return ""
            # This method is removed - logic moved to _execute_with_retry

    async def _get_chain_config(self, chain: str) -> Dict[str, Any]:
        """
        Get chain configuration from Gateway, with caching.
        """
        if chain not in self._config_cache:
            try:
                config = await self.gateway_client.get_configuration(chain)
                self._config_cache[chain] = config or {}
            except Exception as e:
                self.logger.warning(f"Failed to get {chain} config: {e}")
                self._config_cache[chain] = {}

        return self._config_cache[chain]

    async def _estimate_priority_fee(self, chain: str, network: str, config: Dict[str, Any]) -> float:
        """
        Estimate priority fee based on current chain conditions.
        Returns fee in native token units (SOL/ETH).
        """
        try:
            # Get gas/fee estimate from Gateway
            response = await self.gateway_client.api_request(
                method="POST",
                path_url=f"/chain/{chain}/estimateGas",
                params={"network": network}
            )

            # Gateway returns gasPriceToken which is the estimated fee in native token
            min_fee = config.get("minPriorityFee", self.DEFAULT_CONFIG["minPriorityFee"])
            estimated_fee = float(response.get("gasPriceToken", min_fee))

            # TODO: Apply percentile calculation based on basePriorityFeePct
            # For now, use the estimate directly
            return estimated_fee

        except Exception as e:
            self.logger.warning(f"Failed to estimate fee, using minimum: {e}")
            return config.get("minPriorityFee", self.DEFAULT_CONFIG["minPriorityFee"])

    def _create_fee_params(self, priority_fee: float, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create standardized fee parameters that work across chains.
        Each chain's Gateway endpoint interprets these according to its needs.
        """
        compute_units = config.get("defaultComputeUnits", self.DEFAULT_CONFIG["defaultComputeUnits"])

        return {
            # Used by all chains - the priority fee in native token
            "priorityFee": priority_fee,

            # Compute units / gas limit
            "computeUnits": compute_units,
        }

    async def _monitor_transaction(
        self,
        chain: str,
        network: str,
        tx_hash: str,
        timeout: float = 60.0
    ) -> Optional[Dict[str, Any]]:
        """
        Monitor a transaction until it's confirmed or timeout.
        Returns transaction data if confirmed, None if failed/timeout.
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # Poll transaction status
                response = await self.gateway_client.api_request(
                    method="POST",
                    path_url=f"/chain/{chain}/poll",
                    params={
                        "network": network,
                        "txHash": tx_hash
                    }
                )

                if response.get("confirmed"):
                    return response
                elif response.get("failed"):
                    return None

            except Exception as e:
                self.logger.debug(f"Error polling transaction: {e}")

            await asyncio.sleep(2)  # Poll every 2 seconds

        return None  # Timeout

    async def _execute_with_retry(
        self,
        chain: str,
        network: str,
        connector: str,
        method: str,
        params: Dict[str, Any],
        config: Dict[str, Any],
        initial_priority_fee: float,
        order_id: str,
        tracked_order: GatewayInFlightOrder
    ):
        """
        Background retry logic for transaction execution.
        Updates the GatewayInFlightOrder with transaction progress.
        """
        from hummingbot.core.data_type.in_flight_order import OrderUpdate, OrderState

        max_retries = config.get("retryCount", self.DEFAULT_CONFIG["retryCount"])
        retry_interval = config.get("retryIntervalMs", self.DEFAULT_CONFIG["retryIntervalMs"]) / 1000
        fee_multiplier = config.get("priorityFeeMultiplier", self.DEFAULT_CONFIG["priorityFeeMultiplier"])
        max_fee = config.get("maxPriorityFee", self.DEFAULT_CONFIG["maxPriorityFee"])

        current_priority_fee = initial_priority_fee
        attempt = 0
        last_error = None

        while attempt <= max_retries:
            try:
                # Update fee parameters
                fee_params = self._create_fee_params(current_priority_fee, config)
                request_params = {**params, **fee_params}

                # Send transaction
                response = await self.gateway_client.api_request(
                    method="POST",
                    path_url=f"/connector/{connector}/{method}",
                    params=request_params
                )

                tx_hash = response.get("signature") or response.get("txHash")

                # Update order with transaction hash
                if tx_hash:
                    tracked_order.update_creation_transaction_hash(tx_hash)

                    # Update order state to OPEN
                    order_update = OrderUpdate(
                        client_order_id=order_id,
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=self.current_timestamp,
                        new_state=OrderState.OPEN,
                        misc_updates={"creation_transaction_hash": tx_hash}
                    )
                    tracked_order.update_with_order_update(order_update)

                status = response.get("status", 0)

                if status == 1:  # CONFIRMED
                    # Transaction confirmed immediately
                    self._process_transaction_success(tracked_order, response)
                    return

                # Monitor pending transaction
                confirmed = await self._monitor_transaction(chain, network, tx_hash)

                if confirmed:
                    self._process_transaction_success(tracked_order, confirmed)
                    return

                # Transaction failed, prepare for retry
                last_error = "Transaction failed to confirm"

            except Exception as e:
                last_error = str(e)
                self.logger.warning(f"Transaction attempt {attempt + 1} failed: {last_error}")

            # Retry with higher fee
            if attempt < max_retries:
                attempt += 1
                current_priority_fee = min(current_priority_fee * fee_multiplier, max_fee)
                self.logger.info(f"Retrying with priority fee: {current_priority_fee:.6f}")
                await asyncio.sleep(retry_interval)
            else:
                break

        # All retries failed
        order_update = OrderUpdate(
            client_order_id=order_id,
            trading_pair=tracked_order.trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=OrderState.FAILED,
            misc_updates={"error": last_error or "Max retries exceeded"}
        )
        tracked_order.update_with_order_update(order_update)

    def _process_transaction_success(self, tracked_order: GatewayInFlightOrder, response: Dict[str, Any]):
        """
        Process successful transaction and update order state.
        """
        from hummingbot.core.data_type.in_flight_order import OrderUpdate, OrderState

        # Extract transaction data
        data = response.get("data", {})
        fee = response.get("fee", 0)

        # Update order to FILLED state with transaction data
        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            trading_pair=tracked_order.trading_pair,
            update_timestamp=self.gateway_client.current_timestamp,
            new_state=OrderState.FILLED,
            misc_updates={
                "fee": fee,
                "data": data
            }
        )
        tracked_order.update_with_order_update(order_update)
```

## Gateway API Changes

### 1. Standardized Fee Parameters

All transaction-creating endpoints will accept these standardized fee parameters:

```typescript
interface TransactionRequest {
  // ... existing parameters ...

  // New standardized fee parameters (optional)
  priorityFee?: number;        // Priority fee in native token (SOL/ETH)
  computeUnits?: number;       // Compute units (Solana) or gas limit (Ethereum)
}
```

Each chain's Gateway implementation interprets these parameters appropriately:

**Solana Implementation:**
```typescript
// In openPosition and other transaction methods
const computeUnits = request.computeUnits || 300000;
const priorityFeeLamports = request.priorityFee ? request.priorityFee * 1e9 : await estimateDefault();
const priorityFeePerCU = priorityFeeLamports / computeUnits;
```

**Ethereum Implementation:**
```typescript
// In transaction methods
const gasLimit = request.computeUnits || 500000;
const gasPriceWei = request.priorityFee ? request.priorityFee * 1e18 : await estimateDefault();
```

### 2. Modified Response Structure

Transaction endpoints will return status information when transaction is not immediately confirmed:

```typescript
// Transaction status enum
enum TransactionStatus {
  PENDING = 0,
  CONFIRMED = 1,
  FAILED = -1
}

// Modified response for transaction endpoints
interface TransactionResponse<T = any> {
  // Always returned
  signature: string;       // Transaction hash
  status: TransactionStatus;  // Status as enum (0=pending, 1=confirmed, -1=failed)

  // Returned when status is CONFIRMED
  data?: T;               // Operation-specific data conforming to endpoint schema (e.g., CLMMPositionResponse)
  fee?: number;           // Actual fee paid in native token
}

// Example: For CLMM open position, when confirmed:
interface CLMMOpenPositionResponse extends TransactionResponse<CLMMPositionData> {
  status: TransactionStatus.CONFIRMED;
  data: {
    positionAddress: string;
    poolAddress: string;
    lowerPrice: number;
    upperPrice: number;
    baseTokenAmount: string;
    quoteTokenAmount: string;
    // ... other fields from @clmm-schema
  };
  fee: number;
}
```

### 3. Gateway Internal Changes

The Gateway code needs minimal modifications:

```typescript
// Example: Raydium openPosition function modifications
async function openPosition(
  // ... existing parameters ...
  priorityFeePerCU?: number,  // New parameter from request
  computeUnits?: number,      // New parameter from request
): Promise<OpenPositionResponseType> {
  // ... existing setup code ...

  // Use provided fee or calculate default
  const COMPUTE_UNITS = computeUnits || 300000;
  let currentPriorityFee = priorityFeePerCU
    ? priorityFeePerCU * COMPUTE_UNITS / 1e6  // Convert from per CU to total
    : (await solana.estimateGas()) * 1e9 - BASE_FEE;

  // Remove retry loop - just single attempt
  const priorityFeePerCUFinal = Math.floor(
    (currentPriorityFee * 1e6) / COMPUTE_UNITS
  );

  // ... construct and send transaction ...

  const { confirmed, signature, txData } =
    await solana.sendAndConfirmRawTransaction(transaction);

  // Return with status
  if (confirmed && txData) {
    // Return confirmed response with full data conforming to schema
    return {
      signature,
      status: TransactionStatus.CONFIRMED,  // 1
      fee: totalFee / 1e9,
      data: {
        positionAddress: extInfo.nftMint.toBase58(),
        poolAddress: poolInfo.poolAddress,
        lowerPrice: lowerPrice,
        upperPrice: upperPrice,
        baseTokenAmount: baseTokenAmount.toString(),
        quoteTokenAmount: quoteTokenAmount.toString(),
        // ... all other fields required by @clmm-schema
      }
    };
  } else {
    // Return pending status for Hummingbot to handle retry
    return {
      signature,
      status: TransactionStatus.PENDING,  // 0
    };
  }
}
```

## Migration Strategy

### Phase 1: Add New Infrastructure
1. Implement `GatewayTxHandler` in Hummingbot
2. Add new Gateway endpoints without breaking existing ones
3. Add `prepareOnly` parameter to existing endpoints

### Phase 2: Gradual Migration
1. Update connectors to use `GatewayTxHandler` for new transactions
2. Keep existing behavior as fallback
3. Add configuration option to enable new transaction handling

### Phase 3: Complete Migration
1. Remove old transaction handling from Gateway
2. Update all connectors to use new flow
3. Remove deprecated endpoints

## Detailed Migration Example: Execute Swap

Let's walk through migrating the execute-swap functionality for Raydium CLMM as a concrete example.

### Current Implementation Flow

1. **Hummingbot** calls `execute_swap()` → sends to Gateway
2. **Gateway** receives request, builds transaction, retries with fee escalation
3. **Gateway** returns result with signature
4. **Hummingbot** tracks order with signature

### Target Implementation Flow

1. **Hummingbot** calls `execute_swap()` → GatewayTxHandler adds fees
2. **GatewayTxHandler** sends to Gateway with `priorityFee` and `computeUnits`
3. **Gateway** builds transaction with provided fees, attempts once, returns status
4. **If pending**, GatewayTxHandler monitors and retries with higher fees
5. **If confirmed**, returns to calling code with full response data

### File Changes Required

#### 1. Gateway Schema Changes (`gateway/src/schemas/swap-schema.ts`)

```typescript
// Add to ExecuteSwapRequest
export const ExecuteSwapRequest = Type.Object(
  {
    // ... existing fields ...

    // New optional fee parameters
    priorityFee: Type.Optional(Type.Number({
      description: 'Priority fee in SOL (or native token)'
    })),
    computeUnits: Type.Optional(Type.Number({
      description: 'Compute units for transaction'
    })),
  },
  { $id: 'ExecuteSwapRequest' },
);

// Modify ExecuteSwapResponse to include status
export enum TransactionStatus {
  PENDING = 0,
  CONFIRMED = 1,
  FAILED = -1
}

export const ExecuteSwapResponse = Type.Object({
  signature: Type.String(),
  status: Type.Number(), // TransactionStatus enum value

  // Only included when status = CONFIRMED
  data: Type.Optional(Type.Object({
    totalInputSwapped: Type.Number(),
    totalOutputSwapped: Type.Number(),
    fee: Type.Number(),
    baseTokenBalanceChange: Type.Number(),
    quoteTokenBalanceChange: Type.Number(),
  })),
});
```

#### 2. Gateway Connector Changes (`gateway/src/connectors/raydium/clmm-routes/executeSwap.ts`)

```typescript
async function executeSwap(
  // ... existing parameters ...
  priorityFee?: number,      // New parameter
  computeUnits?: number,     // New parameter
): Promise<ExecuteSwapResponseType> {
  // ... existing setup code ...

  // REMOVE the retry loop - just single attempt
  const COMPUTE_UNITS = computeUnits || 600000;

  // Use provided priority fee or estimate default
  const priorityFeeLamports = priorityFee
    ? priorityFee * 1e9
    : (await solana.estimateGas()) * 1e9 - BASE_FEE;

  const priorityFeePerCU = Math.floor(
    (priorityFeeLamports * 1e6) / COMPUTE_UNITS
  );

  // ... build transaction ...

  const { confirmed, signature, txData } =
    await solana.sendAndConfirmRawTransaction(transaction);

  if (confirmed && txData) {
    // Return confirmed with full data
    const { baseTokenBalanceChange, quoteTokenBalanceChange } =
      await solana.extractPairBalanceChangesAndFee(/* ... */);

    return {
      signature,
      status: 1, // CONFIRMED
      data: {
        totalInputSwapped: Math.abs(baseTokenBalanceChange),
        totalOutputSwapped: Math.abs(quoteTokenBalanceChange),
        fee: txData.meta.fee / 1e9,
        baseTokenBalanceChange,
        quoteTokenBalanceChange,
      }
    };
  } else {
    // Return pending for Hummingbot to handle retry
    return {
      signature,
      status: 0, // PENDING
    };
  }
}

// Update route handler to pass new parameters
fastify.post</* ... */>(/* ... */, async (request) => {
  const {
    // ... existing fields ...
    priorityFee,
    computeUnits
  } = request.body;

  return await executeSwap(
    // ... existing parameters ...
    priorityFee,
    computeUnits,
  );
});
```

#### 3. Solana Chain Changes (`gateway/src/chains/solana/solana.ts`)

```typescript
// Modify sendAndConfirmRawTransaction to support single attempt mode
async sendAndConfirmRawTransaction(
  transaction: VersionedTransaction | Transaction,
  options?: { singleAttempt?: boolean }
): Promise<{ confirmed: boolean; signature: string; txData: any }> {
  // ... existing code ...

  if (options?.singleAttempt) {
    // Skip retry loop, just send once
    const signature = await this.connection.sendRawTransaction(serializedTx, {
      skipPreflight: true,
    });

    // Don't wait for confirmation, return immediately
    return {
      confirmed: false,
      signature,
      txData: null
    };
  }

  // ... existing retry logic for backward compatibility ...
}
```

#### 4. Hummingbot GatewayHttpClient Changes (`hummingbot/core/gateway/gateway_http_client.py`)

```python
# Add unencrypted mode support
class GatewayHttpClient:
    def __init__(self, client_config_map: Optional["ClientConfigAdapter"] = None):
        # ... existing code ...
        self._use_ssl = client_config_map.gateway.gateway_use_ssl  # New config

        if self._use_ssl:
            self._base_url = f"https://{api_host}:{api_port}"
        else:
            self._base_url = f"http://{api_host}:{api_port}"

    @classmethod
    def _http_client(cls, client_config_map: "ClientConfigAdapter", re_init: bool = False) -> aiohttp.ClientSession:
        if cls._shared_client is None or re_init:
            if client_config_map.gateway.gateway_use_ssl:
                # Existing SSL setup
                cert_path = client_config_map.certs_path
                ssl_ctx = ssl.create_default_context(cafile=f"{cert_path}/ca_cert.pem")
                # ... existing SSL code ...
            else:
                # Simple HTTP connector
                conn = aiohttp.TCPConnector()

            cls._shared_client = aiohttp.ClientSession(connector=conn)
        return cls._shared_client
```

#### 5. Hummingbot Gateway Connector Changes

Both `GatewaySwap` and `GatewayLP` connectors need to be updated to use the new `GatewayTxHandler`:

**GatewaySwap Changes** (`hummingbot/connector/gateway/gateway_swap.py`):

```python
class GatewaySwap(GatewayBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize transaction handler
        self._tx_handler = None

    @property
    def tx_handler(self):
        if self._tx_handler is None:
            from hummingbot.connector.gateway.gateway_tx_handler import GatewayTxHandler
            self._tx_handler = GatewayTxHandler(self._get_gateway_instance())
        return self._tx_handler

    async def _create_order(
        self,
        trade_type: TradeType,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        price: Decimal
    ):
        """Updated to use GatewayTxHandler for transaction execution."""
        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)

        base, quote = trading_pair.split("-")
        self.start_tracking_order(
            order_id=order_id,
            trading_pair=trading_pair,
            trade_type=trade_type,
            price=price,
            amount=amount
        )

        # Get the tracked order
        tracked_order = self._in_flight_orders.get(order_id)

        try:
            # Execute transaction with retry logic (non-blocking)
            tx_hash = await self.tx_handler.execute_transaction(
                chain=self.chain,
                network=self.network,
                connector=self.connector_name,
                method="execute-swap",
                params={
                    "walletAddress": self.address,
                    "baseToken": base,
                    "quoteToken": quote,
                    "amount": float(amount),
                    "side": trade_type.name,
                },
                order_id=order_id,
                tracked_order=tracked_order
            )

            # Transaction executes in background
            self.logger().info(f"Swap order {order_id} submitted")

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._handle_operation_failure(
                order_id,
                trading_pair,
                f"submitting {trade_type.name} swap order",
                e
            )
```

**GatewayLP Changes** (`hummingbot/connector/gateway/gateway_lp.py`):

```python
class GatewayLP(GatewaySwap):
    # Inherits tx_handler from GatewaySwap

    async def _clmm_open_position(
        self,
        trade_type: TradeType,
        order_id: str,
        trading_pair: str,
        price: float,
        spread_pct: float,
        base_token_amount: Optional[float] = None,
        quote_token_amount: Optional[float] = None,
        slippage_pct: Optional[float] = None,
    ):
        """Open a CLMM position with automatic fee management and retry logic."""
        # ... existing setup code ...

        # Start tracking order
        self.start_tracking_order(
            order_id=order_id,
            trading_pair=trading_pair,
            trade_type=trade_type,
            price=Decimal(str(price)),
            amount=Decimal(str(total_amount_in_base))
        )

        # Get the tracked order
        tracked_order = self._in_flight_orders.get(order_id)

        try:
            # Execute transaction with retry logic (non-blocking)
            tx_hash = await self.tx_handler.execute_transaction(
                chain=self._chain,
                network=self._network,
                connector=self._connector_name,
                method="clmm/open-position",
                params={
                    "walletAddress": self.address,
                    "baseToken": base_token,
                    "quoteToken": quote_token,
                    "lowerPrice": lower_price,
                    "upperPrice": upper_price,
                    "baseTokenAmount": base_token_amount,
                    "quoteTokenAmount": quote_token_amount,
                    "slippagePct": slippage_pct
                },
                order_id=order_id,
                tracked_order=tracked_order
            )

            # Method returns immediately - transaction executes in background
            self.logger().info(f"Position opening submitted for {order_id}")

        except Exception as e:
            self._handle_operation_failure(order_id, trading_pair, "opening CLMM position", e)
```

#### 6. Create GatewayTxHandler (`hummingbot/connector/gateway/gateway_tx_handler.py`)

```python
# Full implementation as shown in the main specification
# Key differences from the spec:
# - Add proper logging setup
# - Import required Hummingbot types
# - Handle connector-specific method paths

from hummingbot.logger import HummingbotLogger
from hummingbot.core.utils.async_utils import safe_ensure_future

from hummingbot.logger import HummingbotLogger
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.data_type.in_flight_order import OrderUpdate, OrderState

class GatewayTxHandler:
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @property
    def current_timestamp(self) -> float:
        """Get current timestamp from gateway client."""
        return self.gateway_client.current_timestamp
```

### Testing the Migration

1. **Unit Tests**: Test each component in isolation
   - Test GatewayTxHandler retry logic
   - Test Gateway endpoint with new parameters
   - Test status code handling

2. **Integration Test**: Full flow test
   ```python
   # Test script
   async def test_execute_swap_with_retry():
       gateway_swap = GatewaySwap(/* ... */)

       # Execute a swap
       order_id = gateway_swap.buy(
           trading_pair="SOL-USDC",
           amount=Decimal("0.1"),
           order_type=OrderType.MARKET,
           price=Decimal("100")
       )

       # Wait for completion
       await asyncio.sleep(30)

       # Verify order completed with retries
       order = gateway_swap.in_flight_orders.get(order_id)
       assert order.is_done
       assert order.last_state == OrderState.FILLED
   ```

3. **Rollback Plan**:
   - Keep old endpoints active during migration
   - Add feature flag to toggle between old/new behavior
   - Monitor error rates and rollback if needed

### Configuration Updates

```yaml
# hummingbot_application.py - add new config
gateway_use_ssl: false  # For development
gateway_enable_tx_handler: true  # Feature flag

# Gateway solana.yml - ensure retry params exist
retryCount: 10
retryIntervalMs: 500
priorityFeeMultiplier: 2
maxPriorityFee: 0.01
minPriorityFee: 0.0001
```

### Benefits of This Approach

1. **Incremental Migration**: Can migrate one endpoint at a time
2. **Backward Compatible**: Old behavior remains until explicitly removed
3. **Testing Friendly**: Each component can be tested independently
4. **Rollback Safe**: Easy to revert if issues arise
5. **Clear Separation**: Gateway remains stateless, Hummingbot controls retry logic

## Configuration

Transaction fee parameters are stored in Gateway's chain configuration files:

```yaml
# In gateway/src/templates/solana.yml
networks:
  mainnet-beta:
    nodeURL: https://api.mainnet-beta.solana.com
    tokenListType: FILE
    tokenListSource: /home/gateway/conf/lists/solana.json
    nativeCurrencySymbol: SOL
  devnet:
    nodeURL: https://api.devnet.solana.com
    tokenListType: FILE
    tokenListSource: /home/gateway/conf/lists/solana-devnet.json
    nativeCurrencySymbol: SOL

# Transaction fee configuration
defaultComputeUnits: 200000       # Default compute units
basePriorityFeePct: 90            # Percentile for fee estimation
priorityFeeMultiplier: 2          # Fee increase multiplier on retry
maxPriorityFee: 0.01              # Maximum priority fee in SOL
minPriorityFee: 0.0001            # Minimum priority fee in SOL
retryIntervalMs: 500              # Retry interval in milliseconds
retryCount: 10                    # Number of retry attempts
```

```yaml
# In gateway/src/templates/ethereum.yml
networks:
  mainnet:
    nodeURL: https://mainnet.infura.io/v3/...
    tokenListType: FILE
    tokenListSource: /home/gateway/conf/lists/mainnet.json
    nativeCurrencySymbol: ETH

# Transaction fee configuration (interpreted as gas limit and ETH values)
defaultComputeUnits: 500000       # Default gas limit
basePriorityFeePct: 75            # Percentile for gas price estimation
priorityFeeMultiplier: 1.3        # Gas price increase on retry
maxPriorityFee: 0.01              # Maximum gas cost in ETH
minPriorityFee: 0.00001           # Minimum gas cost in ETH
retryIntervalMs: 3000             # Retry interval in milliseconds
retryCount: 3                     # Number of retry attempts
```

## Benefits

1. **Full Fee Control**: Hummingbot can implement sophisticated fee strategies
2. **Better Visibility**: Complete transaction lifecycle visibility
3. **Flexible Retry Logic**: Customizable retry strategies per use case
4. **Stateless Gateway**: Gateway becomes a simple transaction builder/submitter
5. **Unified Interface**: Consistent transaction handling across all chains
6. **Cost Optimization**: Better fee management can reduce transaction costs
7. **Strategy Integration**: Trading strategies can directly influence fee decisions

## Implementation Priority

1. **High Priority**:
   - `GatewayTxHandler` base implementation
   - Solana fee strategy (most complex)
   - Basic retry logic
   - Gateway endpoint changes

2. **Medium Priority**:
   - Ethereum fee strategy
   - Advanced retry strategies
   - Configuration system
   - Monitoring and metrics

3. **Low Priority**:
   - Other chain support
   - Advanced fee prediction
   - Historical fee analysis

### Customizing Chain Configuration

To customize fee behavior for different use cases, update the Gateway configuration:

```yaml
# For arbitrage on Solana - gateway/conf/solana.yml
defaultComputeUnits: 400000       # More compute for complex operations
basePriorityFeePct: 95            # Use 95th percentile
priorityFeeMultiplier: 3          # Aggressive escalation
maxPriorityFee: 0.1               # Higher max for arbitrage
minPriorityFee: 0.001             # Start with higher fee
retryCount: 5                     # More retry attempts
retryIntervalMs: 300              # Faster retries

# For market making on Ethereum - gateway/conf/ethereum.yml
defaultComputeUnits: 200000       # Standard gas limit
basePriorityFeePct: 50            # Use median gas price
priorityFeeMultiplier: 1.5        # Gentle escalation
maxPriorityFee: 0.005             # Keep costs low (0.005 ETH)
minPriorityFee: 0.00001           # Start with minimum
retryCount: 2                     # Fewer retries
retryIntervalMs: 5000             # Slower retries
```

## Summary of Simplified Design

This specification presents a streamlined approach to giving Hummingbot control over transaction fees:

1. **Single Chain-Agnostic Handler**: One `GatewayTxHandler` class works for all chains by pulling configuration from Gateway's chain config files.

2. **Configuration in Gateway**: Transaction fee parameters are stored in Gateway's chain templates (e.g., `solana.yml`, `ethereum.yml`), maintaining single source of truth for chain-specific settings.

3. **Standardized Parameters**: All chains use the same parameter names:
   - `defaultComputeUnits`: Compute units (Solana) or gas limit (Ethereum)
   - `basePriorityFeePct`: Percentile for fee estimation
   - `priorityFeeMultiplier`: Fee escalation factor
   - `maxPriorityFee`: Maximum fee in native token
   - `minPriorityFee`: Minimum fee in native token
   - `retryCount`: Number of retry attempts
   - `retryIntervalMs`: Milliseconds between retries

4. **Zero Configuration in Hummingbot**: No need to maintain separate fee configurations - everything is pulled from Gateway at runtime.

5. **Minimal Code Changes**:
   - Add `GatewayTxHandler` to Hummingbot
   - Gateway accepts standardized fee parameters
   - Remove Gateway's internal retry loops

## Benefits of This Approach

1. **Simpler Implementation**: Leverages existing Gateway transaction construction logic
2. **Maintains Gateway Expertise**: Gateway still handles chain-specific transaction building
3. **Flexible Fee Control**: Hummingbot can implement sophisticated fee strategies
4. **Backward Compatible**: Easy migration path with minimal breaking changes
5. **Strategy-Aware Fees**: Different strategies can use different fee approaches

## Conclusion

This refactoring achieves the goal of giving Hummingbot control over transaction fees and retry logic while maintaining Gateway's role as the blockchain interaction expert. The minimal changes required make this a practical approach that can be implemented incrementally without disrupting existing functionality.

The design provides a foundation for future enhancements like MEV protection, dynamic fee models, and cross-chain optimizations while keeping the implementation focused and achievable.
