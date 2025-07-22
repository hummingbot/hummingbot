"""
Unified Gateway HTTP client with fee management and transaction monitoring.
"""
import logging
import ssl
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import aiohttp
from aiohttp import ContentTypeError

from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class GatewayHttpClient:
    """
    Gateway HTTP client that handles all communications with the Gateway service.
    """

    _ghc_logger: Optional[HummingbotLogger] = None
    _shared_client: Optional[aiohttp.ClientSession] = None
    __instance = None

    # ============================================
    # Initialization and Core Methods
    # ============================================

    @staticmethod
    def get_instance(client_config_map: Optional["ClientConfigAdapter"] = None) -> "GatewayHttpClient":
        """Get singleton instance of GatewayHttpClient."""
        if GatewayHttpClient.__instance is None:
            GatewayHttpClient(client_config_map)
        return GatewayHttpClient.__instance

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

        self._use_ssl = use_ssl
        self.base_url = f"{protocol}://{api_host}:{api_port}"
        self._client_config_map = client_config_map
        GatewayHttpClient.__instance = self

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._ghc_logger is None:
            cls._ghc_logger = logging.getLogger(__name__)
        return cls._ghc_logger

    def _http_client(self, re_init: bool = False) -> aiohttp.ClientSession:
        """
        :returns Shared client session instance
        """
        if self._shared_client is None or re_init:
            if self._use_ssl:
                # SSL connection with client certs
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
            self._shared_client = aiohttp.ClientSession(connector=conn)
        return self._shared_client

    def reload_certs(self):
        """
        Re-initializes the aiohttp.ClientSession. This should be called whenever there is any updates to the
        Certificates used to secure a HTTPS connection to the Gateway service.
        """
        self._http_client(re_init=True)

    @property
    def base_url(self) -> str:
        return self._base_url

    @base_url.setter
    def base_url(self, url: str):
        self._base_url = url

    # ============================================
    # Base Request Methods
    # ============================================

    async def api_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        use_body: bool = False,
        data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Sends an aiohttp request to Gatewayand waits for a response.

        :param method: HTTP method (GET, POST, PUT, DELETE)
        :param endpoint: API endpoint (e.g., "chains", "connectors/raydium/amm/quote-swap")
        :param params: Query parameters (for GET) or body parameters (for POST/PUT if data not provided)
        :param data: JSON body data (overrides params for POST/PUT)
        :param kwargs: Additional arguments
        :return: Response data
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        client = self._http_client()

        parsed_response = {}
        try:
            method_lower = method.lower()
            if method_lower == "get":
                if params and len(params) > 0:
                    if use_body:
                        response = await client.get(url, json=params)
                    else:
                        response = await client.get(url, params=params)
                else:
                    response = await client.get(url)
            elif method_lower == "post":
                json_data = data if data is not None else params
                response = await client.post(url, json=json_data)
            elif method_lower == "put":
                json_data = data if data is not None else params
                response = await client.put(url, json=json_data)
            elif method_lower == 'delete':
                if data is not None:
                    # DELETE with JSON body (some APIs support this)
                    response = await self.session.delete(url, json=data)
                elif params:
                    response = await self.session.delete(url, params=params)
            else:
                raise ValueError(f"Unsupported request method {method}")

            try:
                parsed_response = await response.json()
            except ContentTypeError:
                parsed_response = await response.text()

            if response.status >= 400:
                if isinstance(parsed_response, dict) and "error" in parsed_response:
                    error_msg = f"Error on {method.upper()} {url} Error: {parsed_response['error']}"
                else:
                    error_msg = f"Error on {method.upper()} {url} Error: {parsed_response}"
                raise ValueError(error_msg)

        except Exception as e:
            self.logger().error(f"Gateway request error: {method} {url} - {str(e)}")
            raise

        return parsed_response

    async def connector_request(
        self,
        method: str,
        connector: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generic method to make requests to any connector endpoint.

        :param method: HTTP method (get, post, put, delete)
        :param connector: Connector name (e.g., "raydium/clmm", "uniswap/amm")
        :param endpoint: API endpoint (e.g., "execute-swap", "open-position")
        :param params: Request parameters
        :param data: Request body data
        :return: API response
        """
        path = f"connectors/{connector}/{endpoint}"
        return await self.api_request(method, path, params=params, data=data)

    async def chain_request(
        self,
        method: str,
        chain: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generic method to make requests to any chain endpoint.

        :param method: HTTP method (get, post, put, delete)
        :param chain: Chain name (e.g., "ethereum", "solana")
        :param endpoint: API endpoint (e.g., "tokens", "balances")
        :param params: Request parameters
        :param data: Request body data
        :return: API response
        """
        path = f"chains/{chain}/{endpoint}"
        return await self.api_request(method, path, params=params, data=data)

    # ============================================
    # Gateway Status and Restart Methods
    # ============================================

    async def ping_gateway(self) -> bool:
        """Check if Gateway is online."""
        try:
            response = await self.api_request("GET", "")
            return isinstance(response, dict) and response.get("status") == "ok"
        except Exception:
            return False

    async def get_gateway_status(self) -> Dict[str, Any]:
        """
        Calls the status endpoint on Gateway to know basic info about connected networks.
        """
        try:
            return await self.get_network_status()
        except Exception as e:
            self.logger().network(
                "Error fetching gateway status info",
                exc_info=True,
                app_warning_msg=str(e)
            )
        return await self.api_request("GET", "")

    async def post_restart(self):
        await self.api_request("post", "restart")

    # ============================================
    # Configuration Methods
    # ============================================

    async def get_configuration(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Get configuration settings for a specific namespace or all configs.

        :param namespace: Configuration namespace (e.g., "solana", "solana-mainnet", "ethereum-mainnet", "jupiter", etc.)
        :return: Configuration settings
        """
        params = {"namespace": namespace} if namespace else {}
        return await self.api_request("GET", "config/", params=params)

    async def update_config(self, namespace: str, path: str, value: Any) -> Dict[str, Any]:
        """
        Update a specific configuration value.

        :param namespace: Configuration namespace (e.g., "ethereum-mainnet", "solana-mainnet-beta")
        :param path: Configuration path within namespace (e.g., "gasLimitTransaction", "nodeURL")
        :param value: New configuration value
        :return: Update status
        """
        response = await self.request(
            "POST",
            "config/update",
            data={
                "namespace": namespace,
                "path": path,
                "value": value
            }
        )
        self.logger().info("Detected change to Gateway config - restarting Gateway...", exc_info=False)
        await self.post_restart()
        return response

    async def get_chains(self) -> Dict[str, Any]:
        return await self.api_request("get", "config/chains")

    async def get_connectors(self) -> Dict[str, Any]:
        return await self.api_request("get", "config/connectors")

    async def get_namespaces(self) -> List[str]:
        return await self.api_request("GET", "config/namespaces")

    # ============================================
    # Network Methods
    # ============================================

    async def get_network_status(
            self, chain: str, network: str) -> Dict[str, Any]:
        """
        Get network status for a specific chain and network.

        :param chain: Chain name (e.g., "ethereum", "solana")
        :param network: Network name (e.g., "mainnet", "mainnet-beta")
        :return: Network status including block number and RPC URL
        """
        return await self.api_request("GET", f"chains/{chain}/status", params={"network": network})

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

    async def get_native_currency_symbol(self, chain: str, network: str) -> Optional[str]:
        """
        Get the native currency symbol for a chain and network from gateway config.

        :param chain: Blockchain chain (e.g., "ethereum", "bsc")
        :param network: Network name (e.g., "mainnet", "testnet")
        :return: Native currency symbol (e.g., "ETH", "BNB") or None if not found
        """
        try:
            # Use namespace approach for more reliable config access
            namespace = f"{chain}-{network}"
            network_config = await self.get_configuration(namespace)
            if network_config:
                return network_config.get("nativeCurrencySymbol")
        except Exception as e:
            self.logger().warning(f"Failed to get native currency symbol for {chain}-{network}: {e}")
        return None

    # ============================================
    # Wallet Methods
    # ============================================

    async def get_wallets(self, chain: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get wallets from Gateway."""
        # Always fetch all wallets with hardware
        params = {"showHardware": "true"}
        response = await self.api_request("GET", "wallet", params=params)
        wallets = response if isinstance(response, list) else []

        # Filter by chain if requested
        if chain:
            return [wallet for wallet in wallets if wallet.get("chain") == chain]

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

        return await self.api_request(
            "POST",
            "wallet/add",
            data=data
        )

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

        return await self.api_request(
            "POST",
            "wallet/add-hardware",
            data=data
        )

    async def remove_wallet(self, chain: str, address: str) -> Dict[str, Any]:
        """Remove a wallet from Gateway."""
        return await self.api_request(
            "DELETE",
            "wallet/remove",
            data={
                "chain": chain,
                "address": address
            }
        )

    async def set_default_wallet(self, chain: str, address: str) -> Dict[str, Any]:
        """Set default wallet for a chain."""
        return await self.api_request(
            "POST",
            "wallet/setDefault",
            data={"chain": chain, "address": address}
        )

    # ============================================
    # Token Methods
    # ============================================

    async def get_tokens(
        self,
        chain: str,
        network: str,
        search: Optional[str] = None
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """Get available tokens for a specific chain and network."""
        params = {"chain": chain, "network": network}
        if search:
            params["search"] = search

        response = await self.api_request(
            "GET",
            "tokens",
            params=params
        )
        return response

    async def get_token(
        self,
        symbol_or_address: str,
        chain: str,
        network: str
    ) -> Dict[str, Any]:
        """Get details for a specific token by symbol or address."""
        params = {"chain": chain, "network": network}
        try:
            response = await self.api_request(
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
        return await self.api_request(
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
        return await self.api_request(
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
        return await self.api_request(
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
        return await self.api_request(
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
        return await self.api_request(
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
            "GET", connector, "quote-swap", params=request_payload
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
        route: Optional[List[str]] = None
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
            "POST", connector, "execute-swap", data=request_payload
        )

    # ============================================
    # Pool Methods
    # ============================================

    async def get_pools(
        self,
        connector: str,
        network: Optional[str] = None,
        pool_type: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get pools from a connector.

        :param connector: Connector name
        :param network: Optional network name
        :param pool_type: Optional pool type (amm or clmm)
        :param search: Optional search term (token symbol or address)
        :return: List of pools
        """
        params = {"connector": connector}
        if network:
            params["network"] = network
        if pool_type:
            params["type"] = pool_type
        if search:
            params["search"] = search

        response = await self.api_request("GET", "pools", params=params)
        return response if isinstance(response, list) else response.get("pools", [])

    async def get_pool_info(
        self,
        connector: str,
        network: str,
        pool_address: str
    ) -> Dict[str, Any]:
        """
        Get detailed information about a specific pool.

        :param connector: Connector name
        :param network: Network name
        :param pool_address: Pool address
        :return: Pool information
        """
        return await self.connector_request(
            "GET", connector, "pool-info",
            params={"network": network, "poolAddress": pool_address}
        )

    async def add_pool(
        self,
        connector: str,
        network: str,
        pool_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Add a new pool to tracking.

        :param connector: Connector name
        :param network: Network name
        :param pool_data: Pool configuration data
        :return: Response with status
        """
        data = {
            "connector": connector,
            "network": network,
            **pool_data
        }
        return await self.api_request("POST", "pools", data=data)

    async def remove_pool(
        self,
        address: str,
        connector: str,
        network: str,
        pool_type: str = "amm"
    ) -> Dict[str, Any]:
        """
        Remove a pool from tracking.

        :param address: Pool address to remove
        :param connector: Connector name
        :param network: Network name
        :param pool_type: Pool type (amm or clmm)
        :return: Response with status
        """
        params = {
            "connector": connector,
            "network": network,
            "type": pool_type
        }
        return await self.api_request("DELETE", f"pools/{address}", params=params)

    # ============================================
    # Transaction Methods
    # ============================================

    async def get_transaction_status(self, chain: str, network: str, tx_hash: str) -> Dict[str, Any]:
        """Get transaction status."""
        return await self.api_request(
            "POST",
            f"chains/{chain}/poll",
            data={
                "network": network,
                "signature": tx_hash
            }
        )
