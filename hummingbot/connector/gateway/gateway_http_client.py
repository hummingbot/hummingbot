"""
Gateway Transaction Handler for managing blockchain transactions with retry logic.
This module provides chain-agnostic transaction management with automatic fee
escalation and retry capabilities. Also handles all Gateway HTTP communications.
"""
import asyncio
import logging
import re
import ssl
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import aiohttp
from aiohttp import ContentTypeError

from hummingbot.client.config.security import Security
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class GatewayHttpClient:
    """
    Unified handler for Gateway transactions and HTTP communications.
    Manages fee determination, retry logic, and all Gateway API interactions.
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
    _shared_client: Optional[aiohttp.ClientSession] = None
    _base_url: str
    __instance = None

    @staticmethod
    def get_instance(client_config_map: Optional["ClientConfigAdapter"] = None) -> "GatewayHttpClient":
        if GatewayHttpClient.__instance is None:
            GatewayHttpClient.__instance = object.__new__(GatewayHttpClient)
            GatewayHttpClient.__instance.__init__(client_config_map)
        elif client_config_map is not None and GatewayHttpClient.__instance._client_config_map != client_config_map:
            # Update the client config map if it's different
            GatewayHttpClient.__instance._client_config_map = client_config_map
            # Update base_url based on new config
            api_host = client_config_map.gateway.gateway_api_host
            api_port = client_config_map.gateway.gateway_api_port
            use_ssl = getattr(client_config_map.gateway, "gateway_use_ssl", True)
            protocol = "https" if use_ssl else "http"
            GatewayHttpClient.__instance._base_url = f"{protocol}://{api_host}:{api_port}"
        return GatewayHttpClient.__instance

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, client_config_map: Optional["ClientConfigAdapter"] = None):
        if client_config_map is None:
            from hummingbot.client.hummingbot_application import HummingbotApplication
            client_config_map = HummingbotApplication.main_application().client_config_map

        api_host = client_config_map.gateway.gateway_api_host
        api_port = client_config_map.gateway.gateway_api_port
        use_ssl = getattr(client_config_map.gateway, "gateway_use_ssl", False)

        protocol = "https" if use_ssl else "http"
        self._base_url = f"{protocol}://{api_host}:{api_port}"

        self._client_config_map = client_config_map
        self._config_cache: Dict[str, Dict[str, Any]] = {}
        self._pending_transactions: Dict[str, Dict[str, Any]] = {}
        self._fee_estimates: Dict[str, Dict[str, Any]] = {}  # {"chain:network": {"fee_per_compute_unit": int, "denomination": str, "timestamp": float}}
        self._compute_units_cache: Dict[str, int] = {}  # {"tx_type:chain:network": compute_units}
        GatewayHttpClient.__instance = self

    @property
    def base_url(self) -> str:
        return self._base_url

    @base_url.setter
    def base_url(self, url: str):
        self._base_url = url

    @property
    def current_timestamp(self) -> float:
        """Get current timestamp."""
        return time.time()

    @classmethod
    def _http_client(cls, client_config_map: "ClientConfigAdapter", re_init: bool = False) -> aiohttp.ClientSession:
        """
        :returns Shared client session instance
        """
        if cls._shared_client is None or re_init:
            use_ssl = getattr(client_config_map.gateway, "gateway_use_ssl", False)
            if use_ssl:
                cert_path = client_config_map.certs_path
                ssl_ctx = ssl.create_default_context(cafile=f"{cert_path}/ca_cert.pem")
                ssl_ctx.load_cert_chain(certfile=f"{cert_path}/client_cert.pem",
                                        keyfile=f"{cert_path}/client_key.pem",
                                        password=Security.secrets_manager.password.get_secret_value())
                conn = aiohttp.TCPConnector(ssl_context=ssl_ctx)
            else:
                # Non-SSL connection for development
                conn = aiohttp.TCPConnector(ssl=False)
            cls._shared_client = aiohttp.ClientSession(connector=conn)
        return cls._shared_client

    @classmethod
    def reload_certs(cls, client_config_map: "ClientConfigAdapter"):
        """
        Re-initializes the aiohttp.ClientSession. This should be called whenever there is any updates to the
        Certificates used to secure a HTTPS connection to the Gateway service.
        """
        cls._http_client(client_config_map, re_init=True)

    @staticmethod
    def is_timeout_error(e) -> bool:
        """
        Check if an error is a timeout error by looking for 'timeout' in the error string.
        """
        error_string = str(e)
        if re.search('timeout', error_string, re.IGNORECASE):
            return True
        return False

    async def api_request(
            self,
            method: str,
            path_url: str,
            params: Dict[str, Any] = {},
            fail_silently: bool = False,
            use_body: bool = False,
    ) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param path_url: The path url or the API end point
        :param params: A dictionary of required params for the end point
        :param fail_silently: used to determine if errors will be raise or silently ignored
        :param use_body: used to determine if the request should sent the parameters in the body or as query string
        :returns A response in json format.
        """
        if path_url:
            url = f"{self.base_url}/{path_url}"
        else:
            url = self.base_url
        client = GatewayHttpClient._http_client(self._client_config_map)

        parsed_response = {}
        try:
            # Convert method to lowercase for comparison
            method_lower = method.lower()
            if method_lower == "get":
                if len(params) > 0:
                    if use_body:
                        response = await client.get(url, json=params)
                    else:
                        response = await client.get(url, params=params)
                else:
                    response = await client.get(url)
            elif method_lower == "post":
                response = await client.post(url, json=params)
            elif method_lower == 'put':
                response = await client.put(url, json=params)
            elif method_lower == 'delete':
                response = await client.delete(url, json=params)
            else:
                raise ValueError(f"Unsupported request method {method}")

            if not fail_silently and response.status == 504:
                self.logger().network(f"The network call to {url} has timed out.")
            else:
                try:
                    parsed_response = await response.json()
                except ContentTypeError:
                    parsed_response = await response.text()
                if response.status != 200 and \
                   not fail_silently and \
                   not self.is_timeout_error(parsed_response):
                    if "error" in parsed_response:
                        raise ValueError(f"Error on {method.upper()} {url} Error: {parsed_response['error']}")
                    else:
                        raise ValueError(f"Error on {method.upper()} {url} Error: {parsed_response}")

        except Exception as e:
            if not fail_silently:
                if self.is_timeout_error(e):
                    self.logger().network(f"The network call to {url} has timed out.")
                else:
                    self.logger().network(
                        e,
                        exc_info=True,
                        app_warning_msg=f"Call to {url} failed. See logs for more details."
                    )
                raise e

        return parsed_response

    async def execute_transaction(
        self,
        chain: str,
        network: str,
        connector: str,
        method: str,
        params: Dict[str, Any],
        order_id: str,
        gateway_connector: Any  # Gateway connector instance
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
        :param gateway_connector: The Gateway connector instance that can update orders
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
            gateway_connector=gateway_connector
        ))

        # Return immediately - transaction will be processed in background
        return ""

    async def _get_chain_config(self, chain: str) -> Dict[str, Any]:
        """
        Get chain configuration from Gateway, with caching.
        """
        if chain not in self._config_cache:
            try:
                params = {"chainOrConnector": chain} if chain is not None else {}
                config = await self.api_request("get", "config", params=params, fail_silently=False)
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
            response = await self.api_request(
                method="post",
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
                response = await self.api_request(
                    method="post",
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
        gateway_connector: Any
    ):
        """
        Background retry logic for transaction execution.
        Updates the order state through the gateway connector.
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
                response = await self.api_request(
                    method="post",
                    path_url=f"connectors/{connector}/{method}",
                    params=request_params
                )

                tx_hash = response.get("signature")

                # Update order with transaction hash
                if tx_hash:
                    gateway_connector.update_order_transaction_hash(order_id, tx_hash)

                status = response.get("status", 0)

                if status == 1:  # CONFIRMED
                    # Transaction confirmed immediately
                    self._process_transaction_success(gateway_connector, order_id, response)
                    return

                # Monitor pending transaction
                confirmed = await self._monitor_transaction(chain, network, tx_hash)

                if confirmed:
                    self._process_transaction_success(gateway_connector, order_id, confirmed)
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
        gateway_connector._handle_operation_failure(
            order_id=order_id,
            trading_pair=params.get("baseToken", "") + "-" + params.get("quoteToken", ""),
            operation_name="executing transaction",
            error=Exception(last_error or "Max retries exceeded")
        )

    def _process_transaction_success(self, gateway_connector: Any, order_id: str, response: Dict[str, Any]):
        """
        Process successful transaction confirmation.
        This calls process_transaction_confirmation_update which will emit the fill event.
        """
        # Find the in-flight order
        in_flight_order = gateway_connector._order_tracker.fetch_order(order_id)
        if not in_flight_order:
            self.logger().warning(f"Could not find order {order_id} to process transaction success")
            return

        # Calculate fee from compute units used
        compute_units_used = response.get("computeUnitsUsed", 0)
        # Convert microlamports to SOL (or appropriate denomination)
        fee_amount = Decimal(str(compute_units_used)) / Decimal("1e9")

        # Process the transaction confirmation which will trigger the fill event
        gateway_connector.process_transaction_confirmation_update(in_flight_order, fee_amount)

    # Common Gateway API methods for compatibility
    async def ping_gateway(self) -> bool:
        try:
            response: Dict[str, Any] = await self.api_request("get", "", fail_silently=True)
            return response.get("status") == "ok"
        except Exception:
            return False

    async def get_gateway_status(self, fail_silently: bool = False) -> Dict[str, Any]:
        """
        Get the overall Gateway status by pinging the root endpoint.
        """
        try:
            return await self.api_request("get", "", fail_silently=fail_silently)
        except Exception as e:
            self.logger().network(
                "Error fetching gateway status info",
                exc_info=True,
                app_warning_msg=str(e)
            )
            return {}

    async def get_balances(
            self,
            chain: str,
            network: str,
            address: str,
            token_symbols: List[str],
            fail_silently: bool = False,
    ) -> Dict[str, Any]:
        if isinstance(token_symbols, list):
            token_symbols = [x for x in token_symbols if isinstance(x, str) and x.strip() != '']
            return await self.chain_request(
                "post", chain, "balances",
                {"network": network, "address": address, "tokens": token_symbols},
                fail_silently=fail_silently
            )
        else:
            return {}

    async def get_configuration(
            self,
            config_key: str = None,
            fail_silently: bool = True
    ) -> Dict[str, Any]:
        """
        Retrieve configuration from the Gateway.
        """
        if config_key:
            return await self.api_request("get", f"config/{config_key}", fail_silently=fail_silently)
        else:
            return await self.api_request("get", "config", fail_silently=fail_silently)

    async def update_config(self, config_key: str, config_value: Any) -> Dict[str, Any]:
        """
        Update a configuration value on the Gateway.
        """
        return await self.api_request(
            "put",
            "config/update",
            {"configKey": config_key, "configValue": config_value}
        )

    async def connector_request(
            self,
            method: str,
            connector: str,
            endpoint: str,
            params: Dict[str, Any] = None,
            fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Generic method to make requests to any connector endpoint.

        :param method: HTTP method (get, post, put, delete)
        :param connector: Connector name (e.g., "raydium/clmm", "uniswap/amm")
        :param endpoint: API endpoint (e.g., "pool-info", "open-position")
        :param params: Request parameters
        :param fail_silently: Whether to suppress errors
        :return: API response
        """
        path = f"connectors/{connector}/{endpoint}"
        return await self.api_request(method, path, params or {}, fail_silently=fail_silently)

    async def chain_request(
            self,
            method: str,
            chain: str,
            endpoint: str,
            params: Dict[str, Any] = None,
            fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Generic method to make requests to any chain endpoint.

        :param method: HTTP method (get, post, put, delete)
        :param chain: Chain name (e.g., "ethereum", "solana")
        :param endpoint: API endpoint (e.g., "tokens", "balances")
        :param params: Request parameters
        :param fail_silently: Whether to suppress errors
        :return: API response
        """
        path = f"chains/{chain}/{endpoint}"
        return await self.api_request(method, path, params or {}, fail_silently=fail_silently)

    async def get_wallets(self, chain: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get wallets from gateway, optionally filtered by chain.

        :param chain: Optional chain name to filter wallets
        :return: List of wallet objects with chain and walletAddresses
        """
        params = {"chain": chain} if chain else {}
        response = await self.api_request("get", "wallet", params, fail_silently=False)
        return response if isinstance(response, list) else []

    async def add_wallet(self, chain: str, private_key: str) -> Dict[str, Any]:
        """
        Add a wallet to gateway.

        :param chain: Chain name (e.g., "ethereum", "solana")
        :param private_key: Private key for the wallet
        :return: Response with wallet address
        """
        return await self.api_request(
            "post",
            "wallet/add",
            {"chain": chain, "privateKey": private_key},
            fail_silently=False
        )

    async def remove_wallet(self, chain: str, address: str) -> Dict[str, Any]:
        """
        Remove a wallet from gateway.

        :param chain: Chain name (e.g., "ethereum", "solana")
        :param address: Wallet address to remove
        :return: Response indicating success/failure
        """
        return await self.api_request(
            "delete",
            "wallet/remove",
            {"chain": chain, "address": address},
            fail_silently=False
        )

    async def approve_token(self, network: str, address: str, token: str, connector: str) -> Dict[str, Any]:
        """
        Approve token for spending on a DEX.

        :param network: Network name
        :param address: Wallet address
        :param token: Token symbol to approve
        :param connector: Connector name
        :return: Transaction response with hash
        """
        return await self.connector_request(
            "post",
            connector,
            "approve",
            {
                "network": network,
                "address": address,
                "token": token
            }
        )

    async def get_transaction_status(self, chain: str, network: str, tx_hash: str) -> Dict[str, Any]:
        """
        Get transaction status from chain.

        :param chain: Chain name
        :param network: Network name
        :param tx_hash: Transaction hash
        :return: Transaction status
        """
        return await self.chain_request(
            "post",
            chain,
            "poll",
            {
                "network": network,
                "signature": tx_hash
            }
        )

    async def get_allowances(
            self,
            chain: str,
            network: str,
            address: str,
            tokens: List[str],
            connector: str,
            fail_silently: bool = True
    ) -> Dict[str, Any]:
        """
        Get token allowances for a wallet.

        :param chain: Chain name
        :param network: Network name
        :param address: Wallet address
        :param tokens: List of token symbols
        :param connector: Connector name
        :param fail_silently: Whether to suppress errors
        :return: Allowances by token
        """
        return await self.chain_request(
            "post",
            chain,
            "allowances",
            {
                "network": network,
                "address": address,
                "tokens": tokens,
                "spender": connector
            },
            fail_silently=fail_silently
        )
