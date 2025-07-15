"""
Unified Gateway HTTP client with fee management and transaction monitoring.
"""
import logging
import ssl
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import aiohttp
from aiohttp import ContentTypeError

from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

from .transaction_monitor import TransactionMonitor


class GatewayClient:
    """
    Unified Gateway HTTP client that handles all communications with the Gateway service.
    Features transaction monitoring and dynamic fee estimation without retry logic.
    """

    _logger: Optional[HummingbotLogger] = None
    _shared_session: Optional[aiohttp.ClientSession] = None
    _client_config_map: Optional["ClientConfigAdapter"] = None
    __instance = None

    # ============================================
    # Initialization and Core Methods
    # ============================================

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @staticmethod
    def get_instance(client_config_map: Optional["ClientConfigAdapter"] = None) -> "GatewayClient":
        """Get singleton instance of GatewayClient."""
        if GatewayClient.__instance is None:
            GatewayClient.__instance = GatewayClient(client_config_map)
        elif client_config_map is not None and GatewayClient.__instance._client_config_map != client_config_map:
            # Update the client config map if it's different
            GatewayClient.__instance._client_config_map = client_config_map
            # Update base_url based on new config
            api_host = client_config_map.gateway.gateway_api_host
            api_port = client_config_map.gateway.gateway_api_port
            use_ssl = getattr(client_config_map.gateway, "gateway_use_ssl", False)
            protocol = "https" if use_ssl else "http"
            GatewayClient.__instance.base_url = f"{protocol}://{api_host}:{api_port}"
        return GatewayClient.__instance

    def __init__(self, client_config_map: Optional["ClientConfigAdapter"] = None):
        """
        Initialize Gateway client.

        :param client_config_map: Client configuration
        """
        if client_config_map is None:
            from hummingbot.client.hummingbot_application import HummingbotApplication
            client_config_map = HummingbotApplication.main_application().client_config_map

        api_host = client_config_map.gateway.gateway_api_host
        api_port = client_config_map.gateway.gateway_api_port
        use_ssl = getattr(client_config_map.gateway, "gateway_use_ssl", False)

        protocol = "https" if use_ssl else "http"
        self.base_url = f"{protocol}://{api_host}:{api_port}"
        self._client_config_map = client_config_map
        self._config_cache: Dict[str, Dict[str, Any]] = {}
        self._compute_units_cache: Dict[str, int] = {}  # {"tx_type:connector:network": compute_units}
        self._fee_estimates: Dict[str, Dict[str, Any]] = {}  # {"chain:network": fee_data}
        self._connector_info_cache: Dict[str, Dict[str, Any]] = {}
        self._swap_connectors_cache: List[str] = []  # List of swap connectors with type suffixes
        self._chain_info_cache: List[Dict[str, Any]] = []
        self._wallets_cache: Dict[str, List[Dict[str, Any]]] = {}  # {"chain": [wallet_info]}
        self._config_namespaces_cache: List[str] = []  # Cache for config namespaces
        self._cache_initialized = False
        self._cache_timestamp = 0
        self._cache_ttl = 300  # 5 minutes

    @property
    def session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._shared_session is None or self._shared_session.closed:
            use_ssl = getattr(self._client_config_map.gateway, "gateway_use_ssl", False) if self._client_config_map else False
            if use_ssl:
                from hummingbot.client.config.security import Security
                cert_path = self._client_config_map.certs_path
                ssl_ctx = ssl.create_default_context(cafile=f"{cert_path}/ca_cert.pem")
                ssl_ctx.load_cert_chain(certfile=f"{cert_path}/client_cert.pem",
                                        keyfile=f"{cert_path}/client_key.pem",
                                        password=Security.secrets_manager.password.get_secret_value())
                conn = aiohttp.TCPConnector(ssl_context=ssl_ctx)
            else:
                # Non-SSL connection for development
                conn = aiohttp.TCPConnector(ssl=False)
            self._shared_session = aiohttp.ClientSession(connector=conn)
        return self._shared_session

    async def close(self):
        """Close HTTP session."""
        if self._shared_session and not self._shared_session.closed:
            await self._shared_session.close()

    async def reload_certs(self, client_config_map) -> None:
        """Reload SSL certificates."""
        # Close existing session
        if self._shared_session and not self._shared_session.closed:
            await self._shared_session.close()
        self._shared_session = None
        self._client_config_map = client_config_map
        # New session will be created on next access with updated certs

    # ============================================
    # Base Request Methods
    # ============================================

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
                if data is not None:
                    # DELETE with JSON body (some APIs support this)
                    response = await self.session.delete(url, json=data)
                elif params:
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
            # Only log detailed errors for non-ping requests to reduce noise
            if endpoint not in ["/", ""]:
                self.logger().error(f"Gateway request error: {method} {url} - {str(e)}")
            raise

    async def connector_request(
        self,
        method: str,
        connector: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Generic method to make requests to any connector endpoint.

        :param method: HTTP method (get, post, put, delete)
        :param connector: Connector name (e.g., "raydium/clmm", "uniswap/amm")
        :param endpoint: API endpoint (e.g., "execute-swap", "open-position")
        :param params: Request parameters
        :param data: Request body data
        :param fail_silently: Whether to suppress errors
        :return: API response
        """
        path = f"connectors/{connector}/{endpoint}"
        try:
            return await self.request(method, path, params=params, data=data)
        except Exception as e:
            if not fail_silently:
                raise
            return {"error": str(e)}

    async def chain_request(
        self,
        method: str,
        chain: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Generic method to make requests to any chain endpoint.

        :param method: HTTP method (get, post, put, delete)
        :param chain: Chain name (e.g., "ethereum", "solana")
        :param endpoint: API endpoint (e.g., "tokens", "balances")
        :param params: Request parameters
        :param data: Request body data
        :param fail_silently: Whether to suppress errors
        :return: API response
        """
        path = f"chains/{chain}/{endpoint}"
        try:
            return await self.request(method, path, params=params, data=data)
        except Exception as e:
            if not fail_silently:
                raise
            return {"error": str(e)}

    # Compatibility alias
    async def api_request(self, method: str, path: str, **kwargs) -> Any:
        """Generic API request method for compatibility."""
        return await self.request(method, path, **kwargs)

    # ============================================
    # Gateway Status Methods
    # ============================================

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

    # ============================================
    # Chain and Connector Info Methods
    # ============================================

    async def get_chains(self) -> List[Dict[str, Any]]:
        """Get available chains from Gateway."""
        if not self._chain_info_cache or (time.time() - self._cache_timestamp) > self._cache_ttl:
            response = await self.request("GET", "config/chains")
            self._chain_info_cache = response.get("chains", [])
            self._cache_timestamp = time.time()
        return self._chain_info_cache

    async def get_connectors(self) -> Dict[str, Dict[str, Any]]:
        """Get available connectors from Gateway."""
        if not self._connector_info_cache or (time.time() - self._cache_timestamp) > self._cache_ttl:
            response = await self.request("GET", "config/connectors")
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

    def get_swap_connectors(self) -> List[str]:
        """Get list of swap connectors with type suffixes (e.g., uniswap/router, raydium/amm)."""
        return self._swap_connectors_cache.copy()

    async def get_connector_trading_types(self, connector_name: str) -> Optional[List[str]]:
        """
        Get supported trading types for a specific connector.

        :param connector_name: Name of the connector
        :return: List of supported trading types, or None if connector not found
        """
        try:
            connectors = await self.get_connectors()
            for name, info in connectors.items():
                if name.lower() == connector_name.lower():
                    return info.get("trading_types", [])
            return None
        except Exception as e:
            self.logger().error(f"Failed to get trading types for {connector_name}: {str(e)}")
            return None

    async def get_network_status(self, chain: str, network: str) -> Dict[str, Any]:
        """
        Get network status for a specific chain and network.

        :param chain: Chain name (e.g., "ethereum", "solana")
        :param network: Network name (e.g., "mainnet", "mainnet-beta")
        :return: Network status including block number and RPC URL
        """
        return await self.request("GET", f"chains/{chain}/status", params={"network": network})

    # ============================================
    # Configuration Methods
    # ============================================

    async def get_configuration(self, chain_or_connector: Optional[str] = None) -> Dict[str, Any]:
        """
        Get configuration settings for a specific chain/connector or all configs.

        :param chain_or_connector: Chain or connector name (e.g., "solana", "ethereum", "uniswap")
        :return: Configuration settings
        """
        params = {"namespace": chain_or_connector} if chain_or_connector else {}
        return await self.request("GET", "config/", params=params)

    async def get_config(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Get configuration (alias for get_configuration)."""
        return await self.get_configuration(namespace)

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
                config = await self.request("GET", "config/", params={"namespace": namespace})
                self._config_cache[cache_key] = config or {}
            except Exception as e:
                self.logger().warning(f"Failed to get config for {cache_key}: {e}")
                self._config_cache[cache_key] = {}

        return self._config_cache[cache_key]

    async def update_config(self, namespace: str, path: str, value: Any) -> Dict[str, Any]:
        """
        Update a specific configuration value.

        :param namespace: Configuration namespace (e.g., "ethereum-mainnet", "solana-mainnet-beta")
        :param path: Configuration path within namespace (e.g., "gasLimitTransaction", "nodeURL")
        :param value: New configuration value
        :return: Update status
        """
        return await self.request(
            "POST",
            "config/update",
            data={
                "namespace": namespace,
                "path": path,
                "value": value
            }
        )

    async def get_namespaces(self) -> List[str]:
        """
        Get available configuration namespaces from gateway.

        :return: List of namespace strings
        """
        response = await self.request("GET", "config/namespaces")
        namespaces = response.get("namespaces", [])
        # Update cache
        self._config_namespaces_cache = namespaces
        return namespaces

    async def get_default_network_for_chain(self, chain: str) -> Optional[str]:
        """
        Get the default network for a chain from its configuration.

        :param chain: Chain name (e.g., "ethereum", "solana")
        :return: Default network name or None if not found
        """
        try:
            config = await self.get_configuration(chain)
            return config.get("defaultNetwork")
        except Exception as e:
            self.logger().warning(f"Failed to get default network for {chain}: {e}")
            return None

    async def get_default_wallet_for_chain(self, chain: str) -> Optional[str]:
        """
        Get the default wallet for a chain from its configuration.

        :param chain: Chain name (e.g., "ethereum", "solana")
        :return: Default wallet address or None if not found
        """
        try:
            # Get the configuration for the chain namespace (not chain-network)
            config = await self.get_configuration(chain)
            return config.get("defaultWallet")
        except Exception as e:
            self.logger().warning(f"Failed to get default wallet for {chain}: {e}")
            return None

    async def initialize_gateway(self) -> None:
        """
        Initialize the gateway by loading all necessary information.
        This should be called once when the gateway comes online.
        """
        if self._cache_initialized and (time.time() - self._cache_timestamp) < self._cache_ttl:
            return  # Cache is still valid

        self.logger().info("Starting gateway initialization...")

        try:
            # Load chains
            chains_response = await self.get_chains()
            self._chain_info_cache = chains_response if isinstance(chains_response, list) else chains_response.get("chains", [])

            # Cache chain names for tab completion
            chain_names = []
            chain_networks = {}
            for chain_info in self._chain_info_cache:
                chain = chain_info.get("chain", "")
                networks = chain_info.get("networks", [])
                if chain:
                    chain_names.append(chain)
                    chain_networks[chain] = networks

            # Load connectors
            connectors = await self.get_connectors()
            self._connector_info_cache = connectors

            # Build swap connectors list with type suffixes
            swap_connectors = []
            for name, info in connectors.items():
                trading_types = info.get("trading_types", [])
                if "router" in trading_types:
                    swap_connectors.append(f"{name}/router")
                if "amm" in trading_types:
                    swap_connectors.append(f"{name}/amm")
                if "clmm" in trading_types:
                    swap_connectors.append(f"{name}/clmm")
            self._swap_connectors_cache = sorted(swap_connectors)

            # Load wallets for all chains
            all_wallets = await self.get_wallets()
            # The get_wallets method will automatically cache them

            # Load all config namespaces
            try:
                config_namespaces = await self.get_namespaces()
                self._config_namespaces_cache = config_namespaces  # Cache the namespaces
            except Exception as e:
                self.logger().warning(f"Failed to load config namespaces: {str(e)}")
                config_namespaces = []
                self._config_namespaces_cache = []

            # Update tab completers with cached data
            try:
                from hummingbot.client.hummingbot_application import HummingbotApplication
                app = HummingbotApplication.main_application()

                if app and hasattr(app, 'app') and hasattr(app.app, 'input'):
                    completer = app.app.input.completer

                    if hasattr(completer, 'update_gateway_chains'):
                        completer.update_gateway_chains(chain_names)
                    if hasattr(completer, 'update_gateway_config_namespaces'):
                        completer.update_gateway_config_namespaces(config_namespaces)
                    # Cache networks for each chain
                    if hasattr(completer, '_cached_gateway_networks'):
                        completer._cached_gateway_networks = chain_networks

                    # Cache all wallets in completer
                    if all_wallets and hasattr(completer, '_all_gateway_wallets'):
                        completer._all_gateway_wallets = all_wallets
                else:
                    # Silently skip if completer is not ready - this is expected during startup
                    pass
            except Exception as e:
                self.logger().warning(f"Error updating completer: {str(e)}", exc_info=True)

            self._cache_initialized = True
            self._cache_timestamp = time.time()
            self.logger().info(f"Gateway initialized with {len(self._chain_info_cache)} chains, "
                               f"{len(self._connector_info_cache)} connectors, "
                               f"and wallets for {len(self._wallets_cache)} chains")

        except Exception as e:
            self.logger().error(f"Failed to initialize gateway: {str(e)}", exc_info=True)

    # ============================================
    # Wallet Methods
    # ============================================

    async def get_wallets(self, chain: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get wallets from Gateway."""
        # Always fetch all wallets with hardware
        params = {"showHardware": "true"}
        response = await self.request("GET", "wallet", params=params)
        wallets = response if isinstance(response, list) else []

        # Add signingAddresses array that contains both regular and hardware wallets
        for wallet in wallets:
            regular_addresses = wallet.get("walletAddresses", [])
            hardware_addresses = wallet.get("hardwareWalletAddresses", [])

            # Create signingAddresses for wallets that can sign transactions
            # Regular wallets first, then hardware wallets
            signing_addresses = regular_addresses + hardware_addresses
            wallet["signingAddresses"] = signing_addresses

        # Update the cache with all wallets
        if wallets:
            # Clear and rebuild the entire cache
            self._wallets_cache.clear()
            for wallet_info in wallets:
                wallet_chain = wallet_info.get("chain")
                if wallet_chain:
                    if wallet_chain not in self._wallets_cache:
                        self._wallets_cache[wallet_chain] = []
                    self._wallets_cache[wallet_chain].append(wallet_info)

        # Filter by chain if requested
        if chain:
            # Return cached wallets for specific chain
            return self._wallets_cache.get(chain, [])

        return wallets

    async def add_wallet(self, chain: str, private_key: str) -> Dict[str, Any]:
        """Add a new wallet to Gateway."""
        # Check if this is the first wallet for the chain
        existing_wallets = await self.get_wallets(chain)
        has_no_wallets = (
            not existing_wallets or
            len(existing_wallets) == 0 or
            (len(existing_wallets[0].get("walletAddresses", [])) == 0 and
             len(existing_wallets[0].get("hardwareWalletAddresses", [])) == 0)
        )

        data = {
            "chain": chain,
            "privateKey": private_key
        }

        # Set as default if no wallets exist
        if has_no_wallets:
            data["setDefault"] = True

        return await self.request(
            "POST",
            "wallet/add",
            data=data
        )

    async def remove_wallet(self, chain: str, address: str) -> Dict[str, Any]:
        """Remove a wallet from Gateway."""
        return await self.request(
            "DELETE",
            "wallet/remove",
            data={
                "chain": chain,
                "address": address
            }
        )

    async def set_default_wallet(self, chain: str, address: str) -> Dict[str, Any]:
        """Set default wallet for a chain."""
        return await self.request(
            "POST",
            "wallet/setDefault",
            data={"chain": chain, "address": address}
        )

    async def restart_gateway(self) -> None:
        """Restart the gateway service."""
        url = f"{self.base_url}/restart"
        try:
            # Send POST with empty JSON body
            async with self.session.post(url, json={}) as response:
                # We expect a 200 response before the process exits
                if response.status == 200:
                    # Success - the gateway will now restart
                    pass
        except Exception:
            # Connection errors might occur as the gateway shuts down
            # This is expected behavior
            pass

    async def add_hardware_wallet(self, chain: str, address: str) -> Dict[str, Any]:
        """Add a hardware wallet to Gateway."""
        # Check if this is the first wallet for the chain
        existing_wallets = await self.get_wallets(chain)
        has_no_wallets = (
            not existing_wallets or
            len(existing_wallets) == 0 or
            (len(existing_wallets[0].get("walletAddresses", [])) == 0 and
             len(existing_wallets[0].get("hardwareWalletAddresses", [])) == 0)
        )

        data = {
            "chain": chain,
            "address": address
        }

        # Set as default if no wallets exist
        if has_no_wallets:
            data["setDefault"] = True

        return await self.request(
            "POST",
            "wallet/add-hardware",
            data=data
        )

    # ============================================
    # Token Methods
    # ============================================

    async def get_tokens(
        self,
        chain: str,
        network: str,
        search: Optional[str] = None,
        fail_silently: bool = False
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """Get available tokens for a specific chain and network."""
        try:
            params = {"chain": chain, "network": network}
            if search:
                params["search"] = search

            response = await self.request(
                "GET",
                "tokens",
                params=params
            )
            return response
        except Exception:
            if fail_silently:
                return {"tokens": []}
            raise

    async def get_token(
        self,
        symbol_or_address: str,
        chain: str,
        network: str
    ) -> Dict[str, Any]:
        """Get details for a specific token by symbol or address."""
        params = {"chain": chain, "network": network}
        try:
            response = await self.request(
                "GET",
                f"tokens/{symbol_or_address}",
                params=params
            )
            return response
        except Exception as e:
            # If not found, return error
            return {"error": f"Token '{symbol_or_address}' not found on {chain}/{network}: {str(e)}"}

    async def add_token(
        self,
        chain: str,
        network: str,
        token_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add a new token to the gateway."""
        return await self.request(
            "POST",
            "tokens",
            data={
                "chain": chain,
                "network": network,
                "token": token_data
            }
        )

    async def remove_token(
        self,
        address: str,
        chain: str,
        network: str
    ) -> Dict[str, Any]:
        """Remove a token from the gateway."""
        return await self.request(
            "DELETE",
            f"tokens/{address}",
            params={
                "chain": chain,
                "network": network
            }
        )

    # ============================================
    # Balance and Allowance Methods
    # ============================================

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

    # ============================================
    # Trading Methods
    # ============================================

    async def get_price(
        self,
        chain: str,
        network: str,
        connector: str,
        base_asset: str,
        quote_asset: str,
        amount: float,
        side: str,
        fail_silently: bool = False,
        pool_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get price quote for a swap.

        :param chain: Chain name
        :param network: Network name
        :param connector: Connector name
        :param base_asset: Base token symbol
        :param quote_asset: Quote token symbol
        :param amount: Amount to swap
        :param side: Trade side (BUY or SELL)
        :param fail_silently: Whether to suppress errors
        :param pool_address: Optional pool address
        :return: Price response
        """
        request_payload = {
            "network": network,
            "baseToken": base_asset,
            "quoteToken": quote_asset,
            "amount": amount,
            "side": side
        }
        if pool_address:
            request_payload["poolAddress"] = pool_address

        return await self.connector_request(
            "GET", connector, "quote-swap", params=request_payload, fail_silently=fail_silently
        )

    async def execute_swap(
        self,
        chain: str,
        network: str,
        connector: str,
        base_asset: str,
        quote_asset: str,
        amount: float,
        side: str,
        address: str,
        minimum_out: Optional[str] = None,
        pool_address: Optional[str] = None,
        route: Optional[List[str]] = None,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Execute a swap transaction.

        :param chain: Chain name
        :param network: Network name
        :param connector: Connector name (with type suffix like /amm, /clmm, /router)
        :param base_asset: Base token symbol
        :param quote_asset: Quote token symbol
        :param amount: Amount to swap
        :param side: Trade side (BUY or SELL)
        :param address: Wallet address
        :param minimum_out: Minimum amount to receive (for slippage protection)
        :param pool_address: Optional pool address
        :param route: Optional route for complex swaps
        :param fail_silently: Whether to suppress errors
        :return: Transaction response with signature/hash
        """
        request_payload = {
            "chain": chain,
            "network": network,
            "connector": connector,
            "baseToken": base_asset,
            "quoteToken": quote_asset,
            "amount": str(amount),
            "side": side,
            "address": address
        }

        if minimum_out:
            request_payload["minimumOut"] = minimum_out
        if pool_address:
            request_payload["poolAddress"] = pool_address
        if route:
            request_payload["route"] = route

        return await self.connector_request(
            "POST", connector, "execute-swap", data=request_payload, fail_silently=fail_silently
        )

    # ============================================
    # Pool Methods
    # ============================================

    async def get_pools(
        self,
        connector: str,
        network: Optional[str] = None,
        pool_type: Optional[str] = None,
        search: Optional[str] = None,
        fail_silently: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get pools from a connector.

        :param connector: Connector name
        :param network: Optional network name
        :param pool_type: Optional pool type (amm or clmm)
        :param search: Optional search term (token symbol or address)
        :param fail_silently: Whether to suppress errors
        :return: List of pools
        """
        params = {"connector": connector}
        if network:
            params["network"] = network
        if pool_type:
            params["type"] = pool_type
        if search:
            params["search"] = search

        try:
            response = await self.request("GET", "pools", params=params)
            return response if isinstance(response, list) else response.get("pools", [])
        except Exception:
            if fail_silently:
                return []
            raise

    async def get_pool_info(
        self,
        connector: str,
        network: str,
        pool_address: str,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Get detailed information about a specific pool.

        :param connector: Connector name
        :param network: Network name
        :param pool_address: Pool address
        :param fail_silently: Whether to suppress errors
        :return: Pool information
        """
        return await self.connector_request(
            "GET", connector, "pool-info",
            params={"network": network, "poolAddress": pool_address},
            fail_silently=fail_silently
        )

    async def add_pool(
        self,
        connector: str,
        network: str,
        pool_data: Dict[str, Any],
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Add a new pool to tracking.

        :param connector: Connector name
        :param network: Network name
        :param pool_data: Pool configuration data
        :param fail_silently: Whether to suppress errors
        :return: Response with status
        """
        data = {
            "connector": connector,
            "network": network,
            **pool_data
        }
        try:
            return await self.request("POST", "pools", data=data)
        except Exception:
            if fail_silently:
                return {"error": "Failed to add pool"}
            raise

    async def remove_pool(
        self,
        address: str,
        connector: str,
        network: str,
        pool_type: str = "amm",
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Remove a pool from tracking.

        :param address: Pool address to remove
        :param connector: Connector name
        :param network: Network name
        :param pool_type: Pool type (amm or clmm)
        :param fail_silently: Whether to suppress errors
        :return: Response with status
        """
        params = {
            "connector": connector,
            "network": network,
            "type": pool_type
        }
        try:
            return await self.request("DELETE", f"pools/{address}", params=params)
        except Exception:
            if fail_silently:
                return {"error": "Failed to remove pool"}
            raise

    # ============================================
    # Transaction Methods
    # ============================================

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
        Execute a Gateway transaction with automatic fee management.

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

        # Execute transaction ONCE (no retry)
        try:
            response = await self.request(
                "POST",
                f"connectors/{connector}/{method}",
                data=request_params
            )

            # Use TransactionMonitor to handle the monitoring
            if callback:
                monitor = TransactionMonitor(self)
                safe_ensure_future(
                    monitor.monitor_transaction(
                        response=response,
                        chain=chain,
                        network=network,
                        order_id=order_id,
                        callback=callback
                    )
                )

        except Exception as e:
            # If transaction submission fails, notify callback
            if callback:
                callback("failed", order_id, str(e))
            raise

        return ""  # Async execution

    # ============================================
    # Cache Management Methods
    # ============================================

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

    # ============================================
    # Private Helper Methods
    # ============================================

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
