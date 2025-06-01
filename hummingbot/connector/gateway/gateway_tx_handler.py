"""
Gateway Transaction Handler for managing blockchain transactions with retry logic.
This module provides chain-agnostic transaction management with automatic fee
escalation and retry capabilities.
"""
import asyncio
import logging
import time
from typing import Any, Dict, Optional

from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger


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

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, gateway_client):
        self.gateway_client = gateway_client
        self._config_cache: Dict[str, Dict[str, Any]] = {}
        self._pending_transactions: Dict[str, Dict[str, Any]] = {}
        self._fee_estimates: Dict[str, Dict[str, Any]] = {}  # {"chain:network": {"fee_per_compute_unit": int, "denomination": str, "timestamp": float}}
        self._compute_units_cache: Dict[str, int] = {}  # {"tx_type:chain:network": compute_units}

    @property
    def current_timestamp(self) -> float:
        """Get current timestamp from gateway client."""
        return self.gateway_client.current_timestamp

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

        # 3. Estimate priority fee per unit based on chain's current conditions
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

        # 5. Execute transaction with retry logic in background
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

    async def _get_chain_config(self, chain: str) -> Dict[str, Any]:
        """
        Get chain configuration from Gateway, with caching.
        """
        if chain not in self._config_cache:
            try:
                config = await self.gateway_client.get_configuration(chain)
                self._config_cache[chain] = config or {}
            except Exception as e:
                self.logger().warning(f"Failed to get {chain} config: {e}")
                self._config_cache[chain] = {}

        return self._config_cache[chain]

    async def _estimate_priority_fee(self, chain: str, network: str, config: Dict[str, Any]) -> int:
        """
        Get cached priority fee estimate or fetch new one if expired.
        Returns fee per compute unit (microlamports per CU on Solana).
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

            # Use timestamp from response if provided, otherwise use current time
            timestamp = response.get("timestamp", current_time)

            # Cache the estimate
            self._fee_estimates[cache_key] = {
                "fee_per_compute_unit": estimated_fee,
                "denomination": denomination,
                "timestamp": timestamp
            }

            return estimated_fee

        except Exception as e:
            self.logger().warning(f"Failed to estimate fee: {e}")
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
        self.logger().debug(f"Cached compute units for {cache_key}: {compute_units}")

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
                self.logger().debug(f"Error polling transaction: {e}")

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
                self.logger().warning(f"Transaction attempt {attempt + 1} failed: {last_error}")

            # Retry with higher fee
            if attempt < max_retries:
                attempt += 1
                # Increase fee per CU, respecting max total fee
                max_fee_per_cu = int((max_fee * 1e9 * 1e6) / compute_units)
                current_priority_fee_per_cu = min(int(current_priority_fee_per_cu * fee_multiplier), max_fee_per_cu)
                total_fee = (current_priority_fee_per_cu * compute_units) / (1e9 * 1e6)  # Convert back to SOL/ETH
                self.logger().info(f"Retrying with priority fee: {total_fee:.6f} ({current_priority_fee_per_cu} per CU)")
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
