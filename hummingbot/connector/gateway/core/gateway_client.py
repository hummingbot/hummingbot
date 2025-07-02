"""
Unified Gateway HTTP client with built-in retry and fee management.
"""
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Union

import aiohttp
from aiohttp import ContentTypeError

from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger


class GatewayClient:
    """
    Unified Gateway HTTP client with built-in retry and fee management.
    Handles all HTTP communications with the Gateway service.
    """

    _logger: Optional[HummingbotLogger] = None
    _shared_session: Optional[aiohttp.ClientSession] = None
    __instance = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @staticmethod
    def get_instance(base_url: Optional[str] = None) -> "GatewayClient":
        """Get singleton instance of GatewayClient."""
        if GatewayClient.__instance is None:
            if base_url is None:
                raise ValueError("base_url required for first initialization")
            GatewayClient.__instance = GatewayClient(base_url)
        return GatewayClient.__instance

    def __init__(self, base_url: str):
        """
        Initialize Gateway client.

        :param base_url: Base URL for Gateway service (e.g., "http://localhost:15888")
        """
        self.base_url = base_url.rstrip("/")
        self._config_cache: Dict[str, Dict[str, Any]] = {}
        self._compute_units_cache: Dict[str, int] = {}  # {"tx_type:connector:network": compute_units}
        self._fee_estimates: Dict[str, Dict[str, Any]] = {}  # {"chain:network": fee_data}
        self._connector_info_cache: Dict[str, Dict[str, Any]] = {}
        self._chain_info_cache: List[Dict[str, Any]] = []
        self._cache_timestamp = 0
        self._cache_ttl = 300  # 5 minutes

    @property
    def session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._shared_session is None or self._shared_session.closed:
            # For now, create a simple session without SSL
            # In production, SSL configuration would be added here
            connector = aiohttp.TCPConnector(ssl=False)
            self._shared_session = aiohttp.ClientSession(connector=connector)
        return self._shared_session

    async def close(self):
        """Close HTTP session."""
        if self._shared_session and not self._shared_session.closed:
            await self._shared_session.close()

    async def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Make HTTP request to Gateway.

        :param method: HTTP method (GET, POST, PUT, DELETE)
        :param endpoint: API endpoint (e.g., "chains", "connectors/raydium/amm/quote-swap")
        :param params: Query parameters (for GET) or body parameters (for POST/PUT if data not provided)
        :param data: JSON body data (overrides params for POST/PUT)
        :param kwargs: Additional arguments
        :return: Response data
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            method_lower = method.lower()

            if method_lower == "get":
                if params:
                    response = await self.session.get(url, params=params)
                else:
                    response = await self.session.get(url)
            elif method_lower == "post":
                json_data = data if data is not None else params
                response = await self.session.post(url, json=json_data)
            elif method_lower == "put":
                json_data = data if data is not None else params
                response = await self.session.put(url, json=json_data)
            elif method_lower == "delete":
                if params:
                    response = await self.session.delete(url, params=params)
                else:
                    response = await self.session.delete(url)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if response.status == 200:
                try:
                    return await response.json()
                except ContentTypeError:
                    return await response.text()
            else:
                error_text = await response.text()
                raise Exception(f"Gateway request failed ({response.status}): {error_text}")

        except Exception as e:
            self.logger().error(f"Gateway request error: {method} {url} - {str(e)}")
            raise

    async def get_network_config(self, chain: str, network: str) -> Dict[str, Any]:
        """
        Get network-specific configuration.

        :param chain: Chain name (e.g., "ethereum", "solana")
        :param network: Network name (e.g., "mainnet", "mainnet-beta")
        :return: Network configuration
        """
        cache_key = f"{chain}-{network}"

        if cache_key not in self._config_cache:
            try:
                namespace = f"{chain}-{network}"
                config = await self.request("GET", "config", params={"namespace": namespace})
                self._config_cache[cache_key] = config or {}
            except Exception as e:
                self.logger().warning(f"Failed to get config for {cache_key}: {e}")
                self._config_cache[cache_key] = {}

        return self._config_cache[cache_key]

    async def get_chains(self) -> List[Dict[str, Any]]:
        """Get available chains from Gateway."""
        if not self._chain_info_cache or (time.time() - self._cache_timestamp) > self._cache_ttl:
            response = await self.request("GET", "chains")
            self._chain_info_cache = response.get("chains", [])
            self._cache_timestamp = time.time()
        return self._chain_info_cache

    async def get_connectors(self) -> Dict[str, Dict[str, Any]]:
        """Get available connectors from Gateway."""
        if not self._connector_info_cache or (time.time() - self._cache_timestamp) > self._cache_ttl:
            response = await self.request("GET", "connectors")
            connectors = response.get("connectors", [])
            self._connector_info_cache = {c["name"]: c for c in connectors}
            self._cache_timestamp = time.time()
        return self._connector_info_cache

    async def get_connector_info(self, connector_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific connector."""
        connectors = await self.get_connectors()

        # Try exact match first
        if connector_name in connectors:
            return connectors[connector_name]

        # Try without trading type suffix (e.g., "raydium/amm" -> "raydium")
        base_name = connector_name.split("/")[0]
        return connectors.get(base_name)

    async def get_network_status(self, chain: str, network: str) -> Dict[str, Any]:
        """
        Get network status for a specific chain and network.

        :param chain: Chain name (e.g., "ethereum", "solana")
        :param network: Network name (e.g., "mainnet", "mainnet-beta")
        :return: Network status including block number and RPC URL
        """
        return await self.request("GET", f"chains/{chain}/status", params={"network": network})

    async def get_configuration(self, chain_or_connector: Optional[str] = None) -> Dict[str, Any]:
        """
        Get configuration settings for a specific chain/connector or all configs.

        :param chain_or_connector: Chain or connector name (e.g., "solana", "ethereum", "uniswap")
        :return: Configuration settings
        """
        params = {"chainOrConnector": chain_or_connector} if chain_or_connector else {}
        return await self.request("GET", "config", params=params)

    async def update_config(self, config_path: str, config_value: Any) -> Dict[str, Any]:
        """
        Update a specific configuration value by its path.

        :param config_path: Configuration path (e.g., "solana.networks.mainnet-beta.nodeURL")
        :param config_value: New configuration value
        :return: Update status
        """
        return await self.request(
            "POST",
            "config/update",
            data={
                "configPath": config_path,
                "configValue": config_value
            }
        )

    async def get_wallets(self, chain: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get wallets from Gateway."""
        params = {"chain": chain} if chain else {}
        response = await self.request("GET", "wallet", params=params)
        return response if isinstance(response, list) else []

    async def get_balances(
        self,
        chain: str,
        network: str,
        address: str,
        tokens: List[str]
    ) -> Dict[str, Any]:
        """Get token balances for a wallet."""
        return await self.request(
            "POST",
            f"chains/{chain}/balances",
            data={
                "network": network,
                "address": address,
                "tokens": tokens
            }
        )

    async def get_tokens(
        self,
        chain: str,
        network: str,
        search: Optional[str] = None,
        fail_silently: bool = False
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """Get available tokens for a specific chain and network."""
        try:
            params = {"network": network}
            if search:
                params["tokenSymbols"] = [search]

            response = await self.request(
                "GET",
                f"chains/{chain}/tokens",
                params=params
            )
            return response
        except Exception:
            if fail_silently:
                return {"tokens": []}
            raise

    def cache_compute_units(self, tx_type: str, connector: str, network: str, compute_units: int):
        """
        Cache compute units for a specific transaction type.

        :param tx_type: Transaction type - full method name (e.g., "execute-swap", "open-position")
        :param connector: Connector name (e.g., "raydium/amm", "uniswap/v3")
        :param network: Network name
        :param compute_units: Compute units to cache
        """
        cache_key = f"{tx_type}:{connector}:{network}"
        self._compute_units_cache[cache_key] = compute_units
        self.logger().debug(f"Cached compute units for {cache_key}: {compute_units}")

    def get_cached_compute_units(
        self,
        tx_type: str,
        connector: str,
        network: str,
        default_compute_units: Optional[int] = None
    ) -> Optional[int]:
        """
        Get cached compute units for a transaction type.

        :param tx_type: Transaction type - full method name
        :param connector: Connector name
        :param network: Network name
        :param default_compute_units: Default value if not cached
        :return: Compute units or default
        """
        cache_key = f"{tx_type}:{connector}:{network}"
        return self._compute_units_cache.get(cache_key, default_compute_units)

    async def execute_transaction(
        self,
        chain: str,
        network: str,
        connector: str,
        method: str,
        params: Dict[str, Any],
        order_id: str,
        callback=None
    ) -> str:
        """
        Execute a Gateway transaction with automatic fee management and retry logic.

        :param chain: Blockchain name
        :param network: Network name
        :param connector: Connector name
        :param method: API method (e.g., "execute-swap", "open-position")
        :param params: Method-specific parameters
        :param order_id: Client order ID for tracking
        :param callback: Optional callback for transaction updates
        :return: Transaction hash (empty string if async)
        """
        # Get network configuration
        config = await self.get_network_config(chain, network)

        # Get compute units
        compute_units = params.get("computeUnits") or self.get_cached_compute_units(
            method, connector, network, config.get("defaultComputeUnits")
        )

        if not compute_units:
            raise ValueError(f"No compute units available for {method} on {connector}:{network}")

        # Estimate priority fee
        estimated_fee = await self._estimate_priority_fee(chain, network, config)

        # Calculate fee bounds
        min_fee = config.get("minFee", 0.0001)
        max_fee = config.get("maxFee", 0.01)

        # Convert to per-CU values (chain-specific)
        if chain == "solana":
            # For Solana, fee is in microlamports per CU
            min_fee_per_cu = int((min_fee * 1e9 * 1e6) / compute_units)
            max_fee_per_cu = int((max_fee * 1e9 * 1e6) / compute_units)
        else:
            # For Ethereum, different calculation
            min_fee_per_cu = int(min_fee * 1e9)  # Gwei
            max_fee_per_cu = int(max_fee * 1e9)  # Gwei

        # Apply bounds
        current_fee_per_cu = max(min_fee_per_cu, min(estimated_fee, max_fee_per_cu))

        # Add fee parameters
        request_params = {
            **params,
            "priorityFeePerCU": current_fee_per_cu,
            "computeUnits": compute_units,
        }

        # Execute with retry in background
        safe_ensure_future(self._execute_with_retry(
            chain, network, connector, method, request_params, config,
            current_fee_per_cu, compute_units, order_id, callback
        ))

        return ""  # Async execution

    async def _estimate_priority_fee(
        self,
        chain: str,
        network: str,
        config: Dict[str, Any]
    ) -> int:
        """Estimate priority fee for a transaction."""
        cache_key = f"{chain}:{network}"
        current_time = time.time()
        gas_estimate_interval = config.get("gasEstimateInterval", 60)

        # Check cache
        if cache_key in self._fee_estimates:
            cached = self._fee_estimates[cache_key]
            if current_time - cached["timestamp"] < gas_estimate_interval:
                return cached["fee_per_compute_unit"]

        try:
            # Get gas estimate
            response = await self.request(
                "POST",
                f"chains/{chain}/estimate-gas",
                data={"network": network}
            )

            estimated_fee = int(response.get("feePerComputeUnit", 0))

            # Cache the estimate
            self._fee_estimates[cache_key] = {
                "fee_per_compute_unit": estimated_fee,
                "denomination": response.get("denomination", "unknown"),
                "timestamp": response.get("timestamp", current_time)
            }

            return estimated_fee

        except Exception as e:
            self.logger().warning(f"Failed to estimate fee: {e}")
            return 0

    async def _execute_with_retry(
        self,
        chain: str,
        network: str,
        connector: str,
        method: str,
        params: Dict[str, Any],
        config: Dict[str, Any],
        initial_fee_per_cu: int,
        compute_units: int,
        order_id: str,
        callback
    ):
        """Background retry logic for transaction execution."""
        max_retries = config.get("retryCount", 3)
        retry_interval = config.get("retryInterval", 2)
        fee_multiplier = config.get("retryFeeMultiplier", 2.0)
        max_fee = config.get("maxFee", 0.01)

        current_fee_per_cu = initial_fee_per_cu
        attempt = 0
        last_error = None

        while attempt <= max_retries:
            try:
                # Update fee parameters
                request_params = {
                    **params,
                    "priorityFeePerCU": current_fee_per_cu,
                    "computeUnits": compute_units,
                }

                # Send transaction
                response = await self.request(
                    "POST",
                    f"connectors/{connector}/{method}",
                    data=request_params
                )

                tx_hash = response.get("signature")
                status = response.get("status", 0)

                # Notify callback if provided
                if callback and tx_hash:
                    await callback("tx_hash", order_id, tx_hash)

                if status == 1:  # CONFIRMED
                    if callback:
                        await callback("confirmed", order_id, response)
                    return

                # Monitor pending transaction
                confirmed = await self._monitor_transaction(chain, network, tx_hash)

                if confirmed:
                    if callback:
                        await callback("confirmed", order_id, confirmed)
                    return

                last_error = "Transaction failed to confirm"

            except Exception as e:
                last_error = str(e)
                self.logger().warning(f"Transaction attempt {attempt + 1} failed: {last_error}")

            # Retry with higher fee
            if attempt < max_retries:
                attempt += 1
                # Increase fee
                if chain == "solana":
                    max_fee_per_cu = int((max_fee * 1e9 * 1e6) / compute_units)
                else:
                    max_fee_per_cu = int(max_fee * 1e9)

                current_fee_per_cu = min(int(current_fee_per_cu * fee_multiplier), max_fee_per_cu)
                await asyncio.sleep(retry_interval)
            else:
                break

        # All retries failed
        if callback:
            await callback("failed", order_id, last_error or "Max retries exceeded")

    async def _monitor_transaction(
        self,
        chain: str,
        network: str,
        tx_hash: str,
        timeout: float = 60.0
    ) -> Optional[Dict[str, Any]]:
        """Monitor transaction until confirmed or timeout."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = await self.request(
                    "POST",
                    f"chains/{chain}/poll",
                    data={
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

            await asyncio.sleep(2)

        return None  # Timeout

    async def ping_gateway(self) -> bool:
        """Check if Gateway is online."""
        try:
            await self.request("GET", "")
            return True
        except Exception:
            return False

    async def get_gateway_status(self) -> Dict[str, Any]:
        """Get Gateway status information."""
        return await self.request("GET", "")

    async def reload_certs(self, client_config_map) -> None:
        """Reload SSL certificates."""
        # This is a no-op for now as SSL handling is done differently
        pass

    async def get_config(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Get configuration (alias for get_configuration)."""
        return await self.get_configuration(namespace)

    async def api_request(self, method: str, path: str, **kwargs) -> Any:
        """Generic API request method for compatibility."""
        return await self.request(method, path, **kwargs)

    async def get_transaction_status(self, chain: str, network: str, tx_hash: str) -> Dict[str, Any]:
        """Get transaction status."""
        return await self.request(
            "POST",
            f"chains/{chain}/poll",
            data={
                "network": network,
                "signature": tx_hash
            }
        )

    async def approve_token(self, network: str, address: str, token: str, spender: str) -> Dict[str, Any]:
        """Approve token spending on Ethereum."""
        return await self.request(
            "POST",
            "chains/ethereum/approve",
            data={
                "network": network,
                "address": address,
                "token": token,
                "spender": spender
            }
        )

    async def get_allowances(self, network: str, address: str, spender: str, tokens: List[str]) -> Dict[str, Any]:
        """Get token allowances on Ethereum."""
        return await self.request(
            "POST",
            "chains/ethereum/allowances",
            data={
                "network": network,
                "address": address,
                "spender": spender,
                "tokens": tokens
            }
        )
