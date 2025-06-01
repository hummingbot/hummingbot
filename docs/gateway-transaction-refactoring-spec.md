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
        "gasEstimateInterval": 60,  # seconds
        "maxFee": 0.01,
        "minFee": 0.0001,
        "retryCount": 3,
        "retryFeeMultiplier": 2.0,
        "retryInterval": 2  # seconds
    }

    def __init__(self, gateway_client):
        self.gateway_client = gateway_client
        self._config_cache: Dict[str, Dict[str, Any]] = {}
        self._pending_transactions: Dict[str, Dict[str, Any]] = {}
        self._fee_estimates: Dict[str, Dict[str, Any]] = {}  # {"chain:network": {"fee_per_compute_unit": int, "denomination": str, "timestamp": float}}
        self._compute_units_cache: Dict[str, int] = {}  # {"tx_type:chain:network": compute_units}

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

        # 2. Get compute units for this transaction
        # Extract transaction type from method (e.g., "execute-swap" -> "swap")
        tx_type = method.split("-")[-1] if "-" in method else method
        compute_units = params.get("computeUnits") or self._get_cached_compute_units(tx_type, chain, network, config)

        # 3. Estimate priority fee per CU based on chain's current conditions
        estimated_fee_per_cu = await self._estimate_priority_fee(chain, network, config)

        # 4. Calculate total fee and apply min/max bounds
        min_fee = config.get("minFee", self.DEFAULT_CONFIG["minFee"])
        max_fee = config.get("maxFee", self.DEFAULT_CONFIG["maxFee"])

        # Convert min/max total fees to per-CU values for comparison
        min_fee_per_cu = int((min_fee * 1e9 * 1e6) / compute_units)  # microlamports per CU
        max_fee_per_cu = int((max_fee * 1e9 * 1e6) / compute_units)  # microlamports per CU

        # Apply bounds to the per-CU fee
        current_priority_fee_per_cu = max(min_fee_per_cu, min(estimated_fee_per_cu, max_fee_per_cu))

        # 5. Add standardized fee parameters to request
        request_params = {
            **params,
            "priorityFeePerCU": current_priority_fee_per_cu,
            "computeUnits": compute_units,
        }

        # 6. Execute transaction with retry logic in background
        safe_ensure_future(self._execute_with_retry(
            chain=chain,
            network=network,
            connector=connector,
            method=method,
            params=request_params,
            config=config,
            initial_priority_fee_per_cu=current_priority_fee_per_cu,
            compute_units=compute_units,
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

    async def _estimate_priority_fee(self, chain: str, network: str, config: Dict[str, Any]) -> int:
        """
        Get cached priority fee estimate or fetch new one if expired.
        Returns fee per compute unit (microlamports per CU on Solana, Wei on Ethereum).
        """
        cache_key = f"{chain}:{network}"
        current_time = time.time()
        gas_estimate_interval = config.get("gasEstimateInterval", self.DEFAULT_CONFIG["gasEstimateInterval"])

        # Check if we have a valid cached estimate
        if cache_key in self._fee_estimates:
            cached = self._fee_estimates[cache_key]
            if current_time - cached["timestamp"] < gas_estimate_interval:
                return cached["fee_per_compute_unit"]

        try:
            # Get gas/fee estimate from Gateway
            response = await self.gateway_client.api_request(
                method="POST",
                path_url=f"chains/{chain}/estimate-gas",
                params={"network": network}
            )

            # Get the fee per compute unit from simplified response
            # The denomination is microlamports for Solana, wei for Ethereum
            estimated_fee = int(response.get("feePerComputeUnit", 0))
            denomination = response.get("denomination", "unknown")
            timestamp = response.get("timestamp", current_time)

            # Cache the estimate
            self._fee_estimates[cache_key] = {
                "fee_per_compute_unit": estimated_fee,
                "denomination": denomination,
                "timestamp": timestamp
            }

            return estimated_fee

        except Exception as e:
            self.logger.warning(f"Failed to estimate fee: {e}")
            return 0  # Return 0 to let the caller apply minFee


    def _get_cached_compute_units(self, tx_type: str, chain: str, network: str, config: Dict[str, Any]) -> int:
        """
        Get cached compute units for a transaction type, or fall back to default.

        :param tx_type: Transaction type (e.g., "swap", "position")
        :param chain: Blockchain name
        :param network: Network name
        :param config: Chain configuration
        :return: Compute units to use
        """
        cache_key = f"{tx_type}:{chain}:{network}"
        if cache_key in self._compute_units_cache:
            return self._compute_units_cache[cache_key]

        # Fall back to default
        return config.get("defaultComputeUnits", self.DEFAULT_CONFIG["defaultComputeUnits"])

    def cache_compute_units(self, tx_type: str, chain: str, network: str, compute_units: int):
        """
        Cache compute units for a specific transaction type.

        :param tx_type: Transaction type (e.g., "swap", "position")
        :param chain: Blockchain name
        :param network: Network name
        :param compute_units: Compute units to cache
        """
        cache_key = f"{tx_type}:{chain}:{network}"
        self._compute_units_cache[cache_key] = compute_units
        self.logger.debug(f"Cached compute units for {cache_key}: {compute_units}")

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
                    path_url=f"chains/{chain}/poll",
                    params={
                        "network": network,
                        "signature": tx_hash
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
        initial_priority_fee_per_cu: int,
        compute_units: int,
        order_id: str,
        tracked_order: GatewayInFlightOrder
    ):
        """
        Background retry logic for transaction execution.
        Updates the GatewayInFlightOrder with transaction progress.
        """
        from hummingbot.core.data_type.in_flight_order import OrderUpdate, OrderState

        max_retries = config.get("retryCount", self.DEFAULT_CONFIG["retryCount"])
        retry_interval = config.get("retryInterval", self.DEFAULT_CONFIG["retryInterval"])
        fee_multiplier = config.get("retryFeeMultiplier", self.DEFAULT_CONFIG["retryFeeMultiplier"])
        max_fee = config.get("maxFee", self.DEFAULT_CONFIG["maxFee"])

        current_priority_fee_per_cu = initial_priority_fee_per_cu
        attempt = 0
        last_error = None

        while attempt <= max_retries:
            try:
                # Update fee parameters
                request_params = {
                    **params,
                    "priorityFeePerCU": current_priority_fee_per_cu,
                    "computeUnits": compute_units,
                }

                # Send transaction
                response = await self.gateway_client.api_request(
                    method="POST",
                    path_url=f"connectors/{connector}/{method}",
                    params=request_params
                )

                tx_hash = response.get("signature")

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
                # Increase fee per CU, respecting max total fee
                max_fee_per_cu = int((max_fee * 1e9 * 1e6) / compute_units)
                current_priority_fee_per_cu = min(int(current_priority_fee_per_cu * fee_multiplier), max_fee_per_cu)
                total_fee = (current_priority_fee_per_cu * compute_units) / (1e9 * 1e6)  # Convert back to SOL/ETH
                self.logger.info(f"Retrying with priority fee: {total_fee:.6f} ({current_priority_fee_per_cu} per CU)")
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
  priorityFeePerCU?: number;   // Priority fee per compute unit (microlamports on Solana)
  computeUnits?: number;       // Compute units (Solana) or gas limit (Ethereum)
}
```

### 2. Simplified GetSwapQuoteResponse

Update `gateway/src/schemas/swap-schema.ts` to simplify GetSwapQuoteResponse:

```typescript
// Remove gas-related fields, add computeUnits
export const GetSwapQuoteResponse = Type.Object({
  poolAddress: Type.Optional(Type.String()),
  estimatedAmountIn: Type.Number(),
  estimatedAmountOut: Type.Number(),
  minAmountOut: Type.Number(),
  maxAmountIn: Type.Number(),
  baseTokenBalanceChange: Type.Number(),
  quoteTokenBalanceChange: Type.Number(),
  price: Type.Number(),
  computeUnits: Type.Number(),  // Compute units required for this swap
});
```

When Gateway returns a quote, it should include the compute units needed for that specific swap. This allows Hummingbot to cache and reuse accurate compute unit values for similar transactions.

### 3. Simplified Gas Estimate Response

Update `gateway/src/schemas/chain-schema.ts` to simplify the EstimateGasResponse:

```typescript
// Current response has too many fields
export const EstimateGasResponseSchema = Type.Object({
  gasPrice: Type.Number(),
  gasPriceToken: Type.String(),
  gasLimit: Type.Number(),
  gasCost: Type.Number(),
});

// Simplified response - just what we need
export const EstimateGasResponseSchema = Type.Object({
  feePerComputeUnit: Type.Number(), // Fee per compute unit
  denomination: Type.String(),      // Denomination: "microlamports" or "wei"
  timestamp: Type.Number(),         // Unix timestamp when estimate was made
});
```

Each chain can implement its own gas lookup logic as long as it returns these three values. The `denomination` field clarifies what unit the fee is expressed in (e.g., "microlamports" for Solana, "wei" for Ethereum). The value is always per compute unit, making it easy to calculate total fees. This simplifies the interface and makes it truly chain-agnostic.

Each chain's Gateway implementation interprets these parameters appropriately:

**Solana Implementation:**
```typescript
// In openPosition and other transaction methods
const computeUnits = request.computeUnits || 300000;
const priorityFeePerCU = request.priorityFeePerCU || await estimateDefault();
// Pass directly to SDK without transformation
```

**Ethereum Implementation:**
```typescript
// In transaction methods
const gasLimit = request.computeUnits || 500000;
const gasPriceWei = request.priorityFee ? request.priorityFee * 1e18 : await estimateDefault();
```

### Example: Raydium AMM executeSwap Changes

In `gateway/src/connectors/raydium/amm-routes/executeSwap.ts`, the current implementation has:
```typescript
// Current: Transformations done in Gateway
const COMPUTE_UNITS = 600000;
let currentPriorityFee = (await solana.estimateGas()) * 1e9 - BASE_FEE;
const priorityFeePerCU = Math.floor(
  (currentPriorityFee * 1e6) / COMPUTE_UNITS,
);
```

With the refactoring, this becomes:
```typescript
// New: Direct pass-through from Hummingbot
const COMPUTE_UNITS = computeUnits || 600000;
const finalPriorityFeePerCU = priorityFeePerCU || await estimateDefault();

// Pass directly to SDK:
computeBudgetConfig: {
  units: COMPUTE_UNITS,
  microLamports: finalPriorityFeePerCU,  // No transformation needed
}
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
2. Update Gateway schemas to accept fee parameters
3. Convert one route at a time and test thoroughly

### Phase 2: Incremental Migration
1. Start with Raydium CLMM executeSwap as proof of concept
2. Test thoroughly before proceeding to next route
3. Convert remaining routes one by one

### Phase 3: Complete Migration
1. Remove old retry loops from all Gateway routes
2. Ensure all routes use the new status-based response
3. Update documentation

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
    priorityFeePerCU: Type.Optional(Type.Number({
      description: 'Priority fee per compute unit (microlamports on Solana)'
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

**Key Changes:**
1. Remove the retry loop (lines 134-220 in current implementation)
2. Accept `priorityFeePerCU` parameter and pass it directly to SDK
3. Keep `solana.sendAndConfirmRawTransaction` as-is (it retries sending the same tx hash)

```typescript
async function executeSwap(
  // ... existing parameters ...
  priorityFeePerCU?: number,   // New parameter - priority fee per compute unit
  computeUnits?: number,       // New parameter
): Promise<ExecuteSwapResponseType> {
  // ... existing setup code ...

  // Use provided compute units or default
  const COMPUTE_UNITS = computeUnits || 600000;

  // Use provided priority fee per CU or estimate default
  let finalPriorityFeePerCU: number;
  if (priorityFeePerCU !== undefined) {
    finalPriorityFeePerCU = priorityFeePerCU;
  } else {
    // Calculate default if not provided
    const currentPriorityFee = (await solana.estimateGas()) * 1e9 - BASE_FEE;
    finalPriorityFeePerCU = Math.floor((currentPriorityFee * 1e6) / COMPUTE_UNITS);
  }

  // Build transaction with SDK - pass parameters directly
  let transaction: VersionedTransaction;
  if (side === 'BUY') {
    const exactOutResponse = response as ReturnTypeComputeAmountOutBaseOut;
    // ... calculate amounts ...
    ({ transaction } = (await raydium.raydiumSDK.clmm.swapBaseOut({
      // ... existing parameters ...
      computeBudgetConfig: {
        units: COMPUTE_UNITS,
        microLamports: finalPriorityFeePerCU,  // Pass directly without transformation
      },
    })) as { transaction: VersionedTransaction });
  } else {
    const exactInResponse = response as ReturnTypeComputeAmountOutFormat;
    ({ transaction } = (await raydium.raydiumSDK.clmm.swap({
      // ... existing parameters ...
      computeBudgetConfig: {
        units: COMPUTE_UNITS,
        microLamports: finalPriorityFeePerCU,  // Pass directly without transformation
      },
    })) as { transaction: VersionedTransaction });
  }

  // Sign and simulate transaction
  transaction.sign([wallet]);
  await solana.simulateTransaction(transaction);

  // Send and confirm - keep retry loop here for retrying same tx hash
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
    priorityFeePerCU,
    computeUnits
  } = request.body;

  return await executeSwap(
    // ... existing parameters ...
    priorityFeePerCU,
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

When GatewaySwap receives a quote response, it should cache the compute units:

```python
class GatewaySwap(GatewayBase):
    async def _get_quote(self, ...):
        """Get quote and cache compute units if provided."""
        # ... existing quote logic ...
        response = await self._api_request(...)

        # Cache compute units if provided in the quote
        if "computeUnits" in response:
            self.tx_handler.cache_compute_units(
                tx_type="swap",
                chain=self.chain,
                network=self.network,
                compute_units=response["computeUnits"]
            )

        return response
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

3. **Testing Plan**:
   - Test each converted route thoroughly before moving to the next
   - Verify retry logic works as expected
   - Monitor transaction success rates

### Configuration Updates

```yaml
# hummingbot_application.py - add new config
gateway_use_ssl: false  # For development

# Gateway solana.yml - ensure retry params exist
defaultComputeUnits: 200000
gasEstimateInterval: 60
maxFee: 0.01
minFee: 0.0001
retryCount: 10
retryFeeMultiplier: 2
retryInterval: 0.5
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
gasEstimateInterval: 60           # Gas estimate cache interval in seconds
maxFee: 0.01                      # Maximum fee in SOL
minFee: 0.0001                    # Minimum fee in SOL
retryCount: 10                    # Number of retry attempts
retryFeeMultiplier: 2             # Fee increase multiplier on retry
retryInterval: 0.5                # Retry interval in seconds
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
gasEstimateInterval: 30           # Gas estimate cache interval in seconds
maxFee: 0.01                      # Maximum gas cost in ETH
minFee: 0.00001                   # Minimum gas cost in ETH
retryCount: 3                     # Number of retry attempts
retryFeeMultiplier: 1.3           # Gas price increase on retry
retryInterval: 3                  # Retry interval in seconds
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
gasEstimateInterval: 10           # More frequent gas updates for arbitrage
maxFee: 0.1                       # Higher max for arbitrage
minFee: 0.001                     # Start with higher fee
retryCount: 5                     # More retry attempts
retryFeeMultiplier: 3             # Aggressive escalation
retryInterval: 0.3                # Faster retries in seconds

# For market making on Ethereum - gateway/conf/ethereum.yml
defaultComputeUnits: 200000       # Standard gas limit
gasEstimateInterval: 120          # Less frequent updates for stable conditions
maxFee: 0.005                     # Keep costs low (0.005 ETH)
minFee: 0.00001                   # Start with minimum
retryCount: 2                     # Fewer retries
retryFeeMultiplier: 1.5           # Gentle escalation
retryInterval: 5                  # Slower retries in seconds
```

## Summary of Simplified Design

This specification presents a streamlined approach to giving Hummingbot control over transaction fees:

1. **Single Chain-Agnostic Handler**: One `GatewayTxHandler` class works for all chains by pulling configuration from Gateway's chain config files.

2. **Configuration in Gateway**: Transaction fee parameters are stored in Gateway's chain templates (e.g., `solana.yml`, `ethereum.yml`), maintaining single source of truth for chain-specific settings.

3. **Standardized Parameters**: All chains use the same parameter names:
   - `defaultComputeUnits`: Compute units (Solana) or gas limit (Ethereum)
   - `gasEstimateInterval`: Seconds between gas estimate updates
   - `maxFee`: Maximum fee in native token
   - `minFee`: Minimum fee in native token
   - `retryCount`: Number of retry attempts
   - `retryFeeMultiplier`: Fee escalation factor on retry
   - `retryInterval`: Seconds between retries

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

## Migration To-Do List

**Current Status**: Raydium CLMM executeSwap has been successfully implemented and tested as the proof of concept. The fee retry logic is working correctly from the Hummingbot side. Ready to proceed with remaining routes.

### Immediate Priority - Complete Current Route

#### 1. Complete Raydium CLMM executeSwap (Current Proof of Concept)
- [x] Update function signature to accept fee parameters
- [x] Remove retry loop
- [x] Implement status-based response
- [x] Update route handler to pass parameters
- [x] **Test thoroughly** before proceeding to next route

### Next Routes (One at a Time)

#### 2. Raydium AMM executeSwap
- [ ] Add `priorityFeePerCU` and `computeUnits` parameters to function signature
- [ ] Remove retry loop (lines 62-180 in current implementation)
- [ ] Implement status-based response format
- [ ] Update route handler to extract and pass new parameters
- [ ] Test thoroughly with Hummingbot integration

#### 3. Raydium CLMM openPosition
- [ ] Add fee parameters to function signature
- [ ] Remove retry loop
- [ ] Return status-based response
- [ ] Update route handler
- [ ] Test with GatewayLP integration

#### 4. Continue with remaining routes in order:
- [ ] Raydium CLMM closePosition
- [ ] Raydium CLMM addLiquidity
- [ ] Raydium CLMM removeLiquidity
- [ ] Jupiter executeSwap
- [ ] Meteora CLMM routes (openPosition, closePosition, etc.)
- [ ] Uniswap AMM routes (with Ethereum gas price adaptations)
- [ ] Uniswap CLMM routes

### Required Supporting Changes

#### Gateway Side:
- [x] Update swap schema (completed)
- [x] Update GetSwapQuoteResponse - remove gasPrice/gasLimit/gasCost, add computeUnits
- [x] Update chain schema - simplify EstimateGasResponse to just `feePerComputeUnit`, `denomination`, and `timestamp`
- [ ] Update CLMM schema when working on CLMM routes
- [ ] Update AMM schema when working on AMM routes
- [x] Ensure all response types include TransactionStatus enum
- [x] Update chain implementations to return simplified gas estimate response
- [x] Update all quote methods to return appropriate computeUnits values

#### Hummingbot Side:
- [x] GatewayTxHandler implementation (completed)
- [x] GatewaySwap integration (completed)
- [x] GatewayHttpClient SSL support (completed)
- [x] GatewayLP integration - update methods as routes are converted:
  - [ ] `_clmm_open_position`
  - [ ] `_clmm_close_position`
  - [ ] `_clmm_add_liquidity`
  - [ ] `_clmm_remove_liquidity`

### Testing Approach

For each route conversion:
1. Convert the Gateway route (remove retry loop, add fee params, return status)
2. Test with direct Gateway API calls using curl/Postman
3. Test with Hummingbot integration
4. Monitor transaction success rates and retry behavior
5. Only proceed to next route after confirmation

#### Completed Testing for Raydium CLMM executeSwap:
- [x] Direct API testing with custom fee parameters
- [x] Successful SELL transaction: `5TBLtTe9wvG69kitNrpETAjjNmTw3dWcwWxGsWyNvBecPHkrZTgBaPQJMCb89v9FL9b33U3Pd9iW1trDvvbDpJCK`
- [x] Successful BUY transaction: `45eeF7L7qZmWANgud8YNnwwLkJ2uZoWqZaMuNCzpUSX9qMyqrkBx2jV9LfMqWJzR5rVYhUbpFTeWvyHAg94BUSQQ`
- [x] Fee retry logic implementation and testing
- [x] Integration tests with mock Gateway responses

### Chain-Specific Adaptations

When working on Ethereum-based routes (Uniswap):
- [ ] Adapt `priorityFeePerCU` to gas price (Wei)
- [ ] Adapt `computeUnits` to gas limit
- [ ] Ensure fee calculations work with ETH decimals
- [ ] Test with Ethereum testnet first

### Documentation Updates

After all routes are converted:
- [ ] Update Gateway API documentation
- [ ] Update Hummingbot connector documentation
- [ ] Create migration guide for custom strategies
- [ ] Document recommended fee configurations

## Conclusion

This refactoring achieves the goal of giving Hummingbot control over transaction fees and retry logic while maintaining Gateway's role as the blockchain interaction expert. The minimal changes required make this a practical approach that can be implemented incrementally without disrupting existing functionality.

The design provides a foundation for future enhancements like MEV protection, dynamic fee models, and cross-chain optimizations while keeping the implementation focused and achievable.
