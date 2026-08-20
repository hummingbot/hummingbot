import asyncio
import logging
import re
import ssl
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlencode

import aiohttp
from aiohttp import ContentTypeError

from hummingbot.client.config.client_config_map import GatewayConfigMap
from hummingbot.client.config.security import Security
from hummingbot.client.settings import (
    GATEWAY_CHAINS,
    GATEWAY_DEXS,
    GATEWAY_ETH_DEXS,
    GATEWAY_NAMESPACES,
    AllConnectorSettings,
    ConnectorSetting,
    ConnectorType as ConnectorTypeSettings,
)
from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from hummingbot.core.event.events import TradeType
from hummingbot.core.gateway.gateway_error import GatewayError
from hummingbot.core.gateway.gateway_models import (
    AmmAddRequest,
    AmmExecuteSwapRequest,
    AmmPoolInfoRequest,
    AmmPositionInfoRequest,
    AmmQuoteLiquidityRequest,
    AmmQuoteSwapRequest,
    AmmRemoveRequest,
    ClmmAddRequest,
    ClmmCloseRequest,
    ClmmCollectFeesRequest,
    ClmmExecuteSwapRequest,
    ClmmOpenRequest,
    ClmmPoolInfoRequest,
    ClmmPositionInfoRequest,
    ClmmPositionsOwnedRequest,
    ClmmQuoteLiquidityRequest,
    ClmmQuoteSwapRequest,
    ClmmRemoveRequest,
    RouterExecuteQuoteRequest,
    RouterExecuteSwapRequest,
    RouterQuoteSwapRequest,
)
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.gateway_config_utils import build_config_namespace_keys
from hummingbot.logger import HummingbotLogger

POLL_INTERVAL = 2.0
POLL_TIMEOUT = 1.0

# The request model for each unified /trading route, keyed by the trading type the caller
# picks at runtime. The three surfaces do not take the same fields — only the router
# accepts approximateIfNoExactOut, only the pool-scoped ones accept poolAddress — so each
# has its own model rather than one shape covering all three.
_QUOTE_SWAP_REQUESTS = {
    "router": RouterQuoteSwapRequest,
    "clmm": ClmmQuoteSwapRequest,
    "amm": AmmQuoteSwapRequest,
}
_EXECUTE_SWAP_REQUESTS = {
    "router": RouterExecuteSwapRequest,
    "clmm": ClmmExecuteSwapRequest,
    "amm": AmmExecuteSwapRequest,
}
_POOL_INFO_REQUESTS = {"clmm": ClmmPoolInfoRequest, "amm": AmmPoolInfoRequest}


def _query(request: Any) -> Dict[str, str]:
    """A request model as query parameters.

    Everything is stringified because aiohttp rejects a non-string query value, and
    Gateway coerces the strings back per its schema. Fields left as None are dropped:
    Gateway applies its own default for an absent parameter, which is not the same as
    being told the value is null.
    """
    return {
        key: ("true" if value is True else "false" if value is False else str(value))
        for key, value in request.model_dump(by_alias=True, exclude_none=True).items()
    }


def _body(request: Any) -> Dict[str, Any]:
    """A request model as a JSON body.

    Dumped in python mode and widened here rather than with ``mode="json"``, which
    renders Decimal as a string. Gateway declares these fields as `type: number` — its
    `decimal` format tells a client to *hold* the value as a decimal, not to send it as
    text — so a string would arrive as the wrong JSON type.
    """
    return {
        key: (float(value) if isinstance(value, Decimal) else value)
        for key, value in request.model_dump(by_alias=True, exclude_none=True).items()
    }


class GatewayStatus(Enum):
    ONLINE = 1
    OFFLINE = 2


class GatewayHttpClient:
    """
    An HTTP client for making requests to the gateway API with built-in status monitoring.
    """

    _ghc_logger: Optional[HummingbotLogger] = None
    _shared_client: Optional[aiohttp.ClientSession] = None
    _base_url: str
    _use_ssl: bool
    _monitor_task: Optional[asyncio.Task] = None
    _gateway_status: GatewayStatus = GatewayStatus.OFFLINE
    _gateway_config_keys: List[str] = []
    _gateway_ready_event: Optional[asyncio.Event] = None
    __instance = None

    @staticmethod
    def get_instance(gateway_config: Optional["GatewayConfigMap"] = None) -> "GatewayHttpClient":
        if GatewayHttpClient.__instance is None:
            GatewayHttpClient(gateway_config)
        return GatewayHttpClient.__instance

    def __init__(self, gateway_config: Optional["GatewayConfigMap"] = None):
        if gateway_config is None:
            gateway_config = GatewayConfigMap()
        api_host = gateway_config.gateway_api_host
        api_port = gateway_config.gateway_api_port
        use_ssl = gateway_config.gateway_use_ssl
        if GatewayHttpClient.__instance is None:
            protocol = "https" if use_ssl else "http"
            self._base_url = f"{protocol}://{api_host}:{api_port}"
            self._use_ssl = use_ssl
            self._gateway_ready_event = asyncio.Event()
        self._gateway_config = gateway_config
        GatewayHttpClient.__instance = self

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._ghc_logger is None:
            cls._ghc_logger = logging.getLogger(__name__)
        return cls._ghc_logger

    @classmethod
    def _http_client(cls, gateway_config: "GatewayConfigMap", re_init: bool = False) -> aiohttp.ClientSession:
        """
        :returns Shared client session instance
        """
        if cls._shared_client is None or re_init:
            use_ssl = gateway_config.gateway_use_ssl
            if use_ssl:
                # SSL connection with client certs
                from hummingbot import root_path

                cert_path = root_path() / "certs"
                ca_file = str(cert_path / "ca_cert.pem")
                cert_file = str(cert_path / "client_cert.pem")
                key_file = str(cert_path / "client_key.pem")

                password = Security.secrets_manager.password.get_secret_value()

                ssl_ctx = ssl.create_default_context(cafile=ca_file)
                ssl_ctx.load_cert_chain(
                    certfile=cert_file,
                    keyfile=key_file,
                    password=password
                )

                # Create connector with explicit timeout settings
                conn = aiohttp.TCPConnector(
                    ssl=ssl_ctx,
                    force_close=True,  # Don't reuse connections for debugging
                    limit=100,
                    limit_per_host=30,
                )
            else:
                # Non-SSL connection for development
                conn = aiohttp.TCPConnector(ssl=False)
            cls._shared_client = aiohttp.ClientSession(connector=conn)
        return cls._shared_client

    @classmethod
    def reload_certs(cls, gateway_config: "GatewayConfigMap"):
        """
        Re-initializes the aiohttp.ClientSession. This should be called whenever there is any updates to the
        Certificates used to secure a HTTPS connection to the Gateway service.
        """
        cls._http_client(gateway_config, re_init=True)

    @property
    def base_url(self) -> str:
        return self._base_url

    @base_url.setter
    def base_url(self, url: str):
        self._base_url = url

    @property
    def ready(self) -> bool:
        return self._gateway_status is GatewayStatus.ONLINE

    @property
    def ready_event(self) -> asyncio.Event:
        return self._gateway_ready_event

    @property
    def gateway_status(self) -> GatewayStatus:
        return self._gateway_status

    @property
    def gateway_config_keys(self) -> List[str]:
        return self._gateway_config_keys

    @gateway_config_keys.setter
    def gateway_config_keys(self, new_config: List[str]):
        self._gateway_config_keys = new_config

    def start_monitor(self):
        """Start the gateway status monitoring loop"""
        if self._monitor_task is None:
            self._monitor_task = safe_ensure_future(self._monitor_loop())

    def stop_monitor(self):
        """Stop the gateway status monitoring loop"""
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            self._monitor_task = None

    async def wait_for_online_status(self, max_tries: int = 30) -> bool:
        """
        Wait for gateway status to go online with a max number of tries. If it
        is online before time is up, it returns early, otherwise it returns the
        current status after the max number of tries.

        :param max_tries: maximum number of retries (default is 30)
        """
        while True:
            if self.ready or max_tries <= 0:
                return self.ready
            await asyncio.sleep(POLL_INTERVAL)
            max_tries = max_tries - 1

    async def _monitor_loop(self):
        """Monitor gateway status and update connector/chain lists when online"""
        while True:
            try:
                if await asyncio.wait_for(self.ping_gateway(), timeout=POLL_TIMEOUT):
                    if self.gateway_status is GatewayStatus.OFFLINE:
                        # Clear all collections
                        GATEWAY_DEXS.clear()
                        GATEWAY_ETH_DEXS.clear()
                        GATEWAY_CHAINS.clear()
                        GATEWAY_NAMESPACES.clear()

                        # Get DEX providers for CLI completers (not registered in AllConnectorSettings)
                        gateway_connectors = await self.get_connectors(fail_silently=True)
                        for connector in gateway_connectors.get("connectors", []):
                            name = connector["name"]
                            chain = connector.get("chain", "")
                            trading_types = connector.get("trading_types", [])
                            for trading_type in trading_types:
                                dex_name = f"{name}/{trading_type}"
                                GATEWAY_DEXS.append(dex_name)
                                if chain.lower() == "ethereum":
                                    GATEWAY_ETH_DEXS.append(dex_name)

                        # Get chains using the dedicated endpoint
                        try:
                            chains_response = await self.get_chains(fail_silently=True)
                            if chains_response and "chains" in chains_response:
                                # Extract chain names and build network identifiers
                                network_connectors = []
                                for chain_info in chains_response["chains"]:
                                    chain_name = chain_info["chain"]
                                    GATEWAY_CHAINS.append(chain_name)
                                    # Add networks as valid connectors (e.g., "solana-mainnet-beta")
                                    for network in chain_info.get("networks", []):
                                        network_connector = f"{chain_name}-{network}"
                                        network_connectors.append(network_connector)
                                # Add network connectors to GATEWAY_DEXS
                                GATEWAY_DEXS.extend(network_connectors)
                                # Also register network connectors with AllConnectorSettings
                                await self._register_gateway_connectors(network_connectors)
                        except Exception:
                            pass

                        # Get namespaces using the dedicated endpoint
                        try:
                            namespaces_response = await self.get_namespaces(fail_silently=True)
                            if namespaces_response and "namespaces" in namespaces_response:
                                GATEWAY_NAMESPACES.extend(sorted(namespaces_response["namespaces"]))
                        except Exception:
                            pass

                        # Update config keys for backward compatibility
                        await self.update_gateway_config_key_list()

                    # If gateway was already online, ensure connectors are registered
                    if self._gateway_status is GatewayStatus.ONLINE and not GATEWAY_DEXS:
                        # Gateway is online but connectors haven't been registered yet
                        await self.ensure_gateway_connectors_registered()

                    self._gateway_status = GatewayStatus.ONLINE
                else:
                    if self._gateway_status is GatewayStatus.ONLINE:
                        self.logger().info("Connection to Gateway container lost...")
                        self._gateway_status = GatewayStatus.OFFLINE

            except asyncio.CancelledError:
                raise
            except Exception:
                """
                We wouldn't be changing any status here because whatever error happens here would have been a result of manipulation data from
                the try block. They wouldn't be as a result of http related error because they're expected to fail silently.
                """
                pass
            finally:
                if self.gateway_status is GatewayStatus.ONLINE:
                    if not self._gateway_ready_event.is_set():
                        self.logger().info("Gateway Service is ONLINE.")
                    self._gateway_ready_event.set()
                else:
                    self._gateway_ready_event.clear()
                await asyncio.sleep(POLL_INTERVAL)

    async def update_gateway_config_key_list(self):
        """Update the list of gateway configuration keys"""
        try:
            config_list: List[str] = []
            config_dict: Dict[str, Any] = await self.get_configuration(fail_silently=True)
            build_config_namespace_keys(config_list, config_dict)
            self.gateway_config_keys = config_list
        except Exception:
            self.logger().error("Error fetching gateway configs. Please check that Gateway service is online. ",
                                exc_info=True)

    async def _register_gateway_connectors(self, connector_list: List[str]):
        """Register gateway connectors in AllConnectorSettings"""
        all_settings = AllConnectorSettings.get_connector_settings()
        for connector_name in connector_list:
            if connector_name not in all_settings:
                # Create connector setting for gateway connector
                all_settings[connector_name] = ConnectorSetting(
                    name=connector_name,
                    type=ConnectorTypeSettings.GATEWAY_DEX,
                    centralised=False,
                    example_pair="ETH-USDC",
                    use_ethereum_wallet=False,  # Gateway handles wallet internally
                    # Zero schema to match GatewayBase.trade_fee_schema(): Gateway reports
                    # actual swap/gas fees per fill via flat_fees in events, so there is no
                    # percent schema to assume here (and self-registration on the connector
                    # uses the same zero schema — keep the two in sync).
                    trade_fee_schema=TradeFeeSchema(),
                    config_keys=None,
                    is_sub_domain=False,
                    parent_name=None,
                    domain_parameter=None,
                    use_eth_gas_lookup=False,
                )

    async def ensure_gateway_connectors_registered(self):
        """Ensure gateway network connectors are registered in AllConnectorSettings"""
        if self.gateway_status is not GatewayStatus.ONLINE:
            return

        try:
            # Populate GATEWAY_DEXS with DEX providers for CLI completers
            # (not registered in AllConnectorSettings)
            gateway_connectors = await self.get_connectors(fail_silently=True)
            for connector in gateway_connectors.get("connectors", []):
                name = connector["name"]
                chain = connector.get("chain", "")
                trading_types = connector.get("trading_types", [])
                for trading_type in trading_types:
                    dex_name = f"{name}/{trading_type}"
                    if dex_name not in GATEWAY_DEXS:
                        GATEWAY_DEXS.append(dex_name)
                    if chain.lower() == "ethereum" and dex_name not in GATEWAY_ETH_DEXS:
                        GATEWAY_ETH_DEXS.append(dex_name)

            # Register network connectors (e.g., "solana-mainnet-beta", "ethereum-mainnet")
            chains_response = await self.get_chains(fail_silently=True)
            if chains_response and "chains" in chains_response:
                network_connectors = []
                for chain_info in chains_response["chains"]:
                    chain_name = chain_info["chain"]
                    for network in chain_info.get("networks", []):
                        network_connector = f"{chain_name}-{network}"
                        network_connectors.append(network_connector)
                await self._register_gateway_connectors(network_connectors)

        except Exception as e:
            self.logger().error(f"Error ensuring gateway connectors are registered: {e}", exc_info=True)

    @staticmethod
    def is_timeout_error(e) -> bool:
        """
        It is hard to consistently return a timeout error from gateway
        because it uses many different libraries to communicate with the
        chains with their own idiosyncracies and they do not necessarilly
        return HTTP status code 504 when there is a timeout error. It is
        easier to rely on the presence of the word 'timeout' in the error.
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
        url = f"{self.base_url}/{path_url}"
        client = self._http_client(self._gateway_config)

        parsed_response = {}
        try:
            timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
            if method == "get":
                if len(params) > 0:
                    if use_body:
                        response = await client.get(url, json=params, timeout=timeout)
                    else:
                        response = await client.get(url, params=params, timeout=timeout)
                else:
                    response = await client.get(url, timeout=timeout)
            elif method == "post":
                response = await client.post(url, json=params)
            elif method == 'put':
                response = await client.put(url, json=params)
            elif method == 'delete':
                response = await client.delete(url, json=params)
            else:
                raise ValueError(f"Unsupported request method {method}")
            # Always parse the response
            try:
                parsed_response = await response.json()
            except ContentTypeError:
                parsed_response = await response.text()

            # Handle non-200 responses
            if response.status != 200 and not fail_silently:
                if "message" in parsed_response:
                    # Gateway HttpError format: message (detailed), code (optional), error (generic HTTP name), name
                    raise GatewayError(
                        parsed_response.get('message'),
                        status=response.status,
                        code=parsed_response.get('code') or None,
                        error_type=parsed_response.get('name') or None,
                        http_error=parsed_response.get('error') or None,
                    )
                else:
                    raise ValueError(f"Error on {method.upper()} {url}: {parsed_response}")

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

    # ============================================
    # Gateway Status and Restart Methods
    # ============================================

    async def ping_gateway(self) -> bool:
        try:
            response: Dict[str, Any] = await self.api_request("get", "", fail_silently=True)
            success = response.get("status") == "ok"
            return success
        except Exception as e:
            self.logger().error(f"✗ Failed to ping gateway: {type(e).__name__}: {e}", exc_info=True)
            return False

    async def get_gateway_status(self, fail_silently: bool = False) -> List[Dict[str, Any]]:
        """
        Status for every chain/network Gateway knows, one poll per network.
        (There is no all-chains status route; the old no-arg get_network_status call
        built "chains/None/status" and could never succeed.)
        """
        statuses: List[Dict[str, Any]] = []
        try:
            chains_resp = await self.get_chains(fail_silently=fail_silently)
            for chain_info in (chains_resp or {}).get("chains", []):
                chain = chain_info.get("chain")
                for network in chain_info.get("networks", []):
                    try:
                        status = await self.get_network_status(
                            chain=chain, network=network, fail_silently=fail_silently)
                        if isinstance(status, dict):
                            statuses.append(status)
                    except Exception as e:
                        self.logger().network(f"Error fetching status for {chain}/{network}: {e}")
        except Exception as e:
            self.logger().network(
                "Error fetching gateway status info",
                exc_info=True,
                app_warning_msg=str(e)
            )
        return statuses

    async def get_network_status(
        self,
        chain: str = None,
        network: str = None,
        fail_silently: bool = False
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        if not chain or not network:
            raise ValueError(
                "get_network_status requires both chain and network "
                "(use get_gateway_status() for all networks)."
            )
        return await self.api_request(
            "get", f"chains/{chain}/status", {"network": network}, fail_silently=fail_silently)

    async def update_config(self, namespace: str, path: str, value: Any) -> Dict[str, Any]:
        response = await self.api_request("post", "config/update", {
            "namespace": namespace,
            "path": path,
            "value": value,
        })
        self.logger().info("Detected change to Gateway config - restarting Gateway...", exc_info=False)
        await self.post_restart()
        return response

    async def post_restart(self):
        await self.api_request("post", "restart", fail_silently=False)

    # ============================================
    # Configuration Methods
    # ============================================

    async def get_configuration(self, namespace: str = None, fail_silently: bool = False) -> Dict[str, Any]:
        params = {"namespace": namespace} if namespace is not None else {}
        return await self.api_request("get", "config", params=params, fail_silently=fail_silently)

    async def get_connectors(self, fail_silently: bool = False) -> Dict[str, Any]:
        return await self.api_request("get", "config/connectors", fail_silently=fail_silently)

    async def get_chains(self, fail_silently: bool = False) -> Dict[str, Any]:
        return await self.api_request("get", "config/chains", fail_silently=fail_silently)

    async def get_namespaces(self, fail_silently: bool = False) -> Dict[str, Any]:
        return await self.api_request("get", "config/namespaces", fail_silently=fail_silently)

    # ============================================
    # Fetch Defaults
    # ============================================

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

    async def get_default_swap_provider(self, network: str) -> Optional[str]:
        """
        Get the default swap provider for a network from Gateway config.

        :param network: Full network name (e.g., "solana-mainnet-beta")
        :return: Swap provider string in format "dex_name/trading_type" or None if not found
        """
        try:
            # Get swapProvider from network config (most authoritative source)
            network_config = await self.get_configuration(network)
            if network_config:
                swap_provider = network_config.get("swapProvider")
                if swap_provider:
                    return swap_provider
            return None
        except Exception as e:
            self.logger().warning(f"Failed to get default swap provider for {network}: {e}")
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

    # ============================================
    # Wallet Methods
    # ============================================

    async def get_wallets(self, show_hardware: bool = True, fail_silently: bool = False) -> List[Dict[str, Any]]:
        params = {"showHardware": str(show_hardware).lower()}
        return await self.api_request("get", "wallet", params=params, fail_silently=fail_silently)

    async def add_wallet(
        self, chain: str, network: str = None, private_key: str = None, set_default: bool = True, **kwargs
    ) -> Dict[str, Any]:
        # Wallet only needs chain, privateKey, and setDefault
        request = {"chain": chain, "setDefault": set_default}
        if private_key:
            request["privateKey"] = private_key
        request.update(kwargs)
        return await self.api_request(method="post", path_url="wallet/add", params=request)

    async def add_hardware_wallet(
        self, chain: str, network: str = None, address: str = None, set_default: bool = True, **kwargs
    ) -> Dict[str, Any]:
        # Hardware wallet only needs chain, address, and setDefault
        request = {"chain": chain, "setDefault": set_default}
        if address:
            request["address"] = address
        request.update(kwargs)
        return await self.api_request(method="post", path_url="wallet/add-hardware", params=request)

    async def remove_wallet(
        self, chain: str, address: str
    ) -> Dict[str, Any]:
        return await self.api_request(method="delete", path_url="wallet/remove", params={"chain": chain, "address": address})

    async def set_default_wallet(self, chain: str, address: str) -> Dict[str, Any]:
        return await self.api_request(
            method="post",
            path_url="wallet/setDefault",
            params={"chain": chain, "address": address}
        )

    # ============================================
    # Balance and Allowance Methods
    # ============================================

    async def get_balances(
        self,
        chain: str,
        network: str,
        address: str,
        token_symbols: List[str],  # Can be symbols or addresses
        fail_silently: bool = False,
    ) -> Dict[str, Any]:
        """
        Get token balances for a wallet address.

        :param chain: The blockchain (e.g., "solana", "ethereum")
        :param network: The network (e.g., "mainnet-beta", "mainnet")
        :param address: The wallet address
        :param token_symbols: List of token symbols OR token addresses to fetch balances for
        :param fail_silently: If True, suppress errors
        :return: Dictionary with balances
        """
        if isinstance(token_symbols, list):
            token_symbols = [x for x in token_symbols if isinstance(x, str) and x.strip() != '']
            request_params = {
                "network": network,
                "address": address,
                "tokens": token_symbols,  # Gateway accepts both symbols and addresses
            }
            return await self.api_request(
                method="post",
                path_url=f"chains/{chain}/balances",
                params=request_params,
                fail_silently=fail_silently,
            )
        else:
            return {}

    async def get_allowances(
        self,
        chain: str,
        network: str,
        address: str,
        token_symbols: List[str],
        spender: str,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        return await self.api_request("post", "chains/ethereum/allowances", {
            "network": network,
            "address": address,
            "tokens": token_symbols,
            "spender": spender
        }, fail_silently=fail_silently)

    async def approve_token(
        self,
        network: str,
        address: str,
        token: str,
        spender: str,
        amount: Optional[int] = None,
    ) -> Dict[str, Any]:
        request_payload: Dict[str, Any] = {
            "network": network,
            "address": address,
            "token": token,
            "spender": spender
        }
        if amount is not None:
            request_payload["amount"] = amount
        return await self.api_request(
            "post",
            "chains/ethereum/approve",
            request_payload
        )

    async def get_transaction_status(
        self,
        chain: str,
        network: str,
        transaction_hash: str,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        request = {
            "network": network,
            "signature": transaction_hash
        }
        return await self.api_request("post", f"chains/{chain}/poll", request, fail_silently=fail_silently)

    # ============================================
    # AMM and CLMM Methods
    # ============================================

    @staticmethod
    def _parse_network(network: str) -> str:
        """
        Parse network string to extract just the network portion for API calls.

        Full format "solana-mainnet-beta" -> "mainnet-beta"
        Short format "mainnet-beta" -> "mainnet-beta"
        """
        # If network contains chain prefix (e.g., "solana-mainnet-beta"), extract network portion
        if "-" in network:
            parts = network.split("-", 1)
            if len(parts) == 2 and parts[0].lower() in ("solana", "ethereum"):
                return parts[1]
        return network

    @staticmethod
    def _parse_swap_provider(swap_provider: str) -> tuple:
        """
        Parse swap provider string into dex and trading_type.

        "jupiter/router" -> ("jupiter", "router")
        """
        if "/" not in swap_provider:
            raise ValueError(f"Invalid swap provider format '{swap_provider}' - expected 'dex/trading_type'")
        return swap_provider.split("/", 1)

    @staticmethod
    def _to_chain_network(network: str, chain: Optional[str] = None) -> str:
        """
        Build the full "chain-network" identifier the unified /trading endpoints expect.

        The unified endpoints reject a bare network (e.g. "mainnet-beta" -> "Unsupported
        chain: mainnet"), so combine the chain with the network when a chain is supplied.
        A network that already carries its chain prefix (e.g. "solana-mainnet-beta") is
        returned unchanged.

        "mainnet-beta" + "solana" -> "solana-mainnet-beta"
        "solana-mainnet-beta" + "solana" -> "solana-mainnet-beta"
        "solana-mainnet-beta" + None -> "solana-mainnet-beta"
        """
        if chain and not network.startswith(f"{chain}-"):
            return f"{chain}-{network}"
        return network

    async def quote_swap(
        self,
        network: str,
        base_asset: str,
        quote_asset: str,
        amount: Decimal,
        side: TradeType,
        dex: Optional[str] = None,
        trading_type: Optional[str] = None,
        slippage_pct: Optional[Decimal] = None,
        chain: Optional[str] = None,
        fail_silently: bool = False,
    ) -> Dict[str, Any]:
        """
        Get a swap quote from the specified DEX via /trading/{router,clmm,amm}/quote-swap.

        :param network: Network name - accepts both full format (e.g., "solana-mainnet-beta") or short format (e.g., "mainnet-beta")
        :param base_asset: Base token symbol
        :param quote_asset: Quote token symbol
        :param amount: Amount to swap
        :param side: Trade side (BUY or SELL)
        :param dex: DEX protocol name (e.g., "jupiter", "orca", "raydium"). If not provided, uses network's default swap provider.
        :param trading_type: Trading type (e.g., "router", "clmm", "amm"). If not provided, uses network's default swap provider.
        :param slippage_pct: Optional slippage percentage
        :param chain: Chain name (e.g., "solana", "ethereum"); combined with a short network to form the "chain-network" the endpoint requires.
        :param fail_silently: Whether to fail silently on error
        :return: Quote response with price, amountIn, amountOut
        """
        if side not in [TradeType.BUY, TradeType.SELL]:
            raise ValueError("Only BUY and SELL prices are supported.")

        # If dex/trading_type not provided, get from network's default swap provider
        if not dex or not trading_type:
            swap_provider = await self.get_default_swap_provider(network)
            if not swap_provider:
                raise ValueError(f"No swap provider configured for network {network}")
            dex, trading_type = self._parse_swap_provider(swap_provider)

        # Gateway carries the trading type in the path — /trading/{router,clmm,amm} —
        # and constrains each route's `connector` to a bare, enum'd name. The type
        # selects the route; it no longer qualifies the connector.
        request_model = _QUOTE_SWAP_REQUESTS.get(trading_type)
        if request_model is None:
            raise ValueError(
                f"Unknown trading type '{trading_type}' — expected one of "
                f"{', '.join(_QUOTE_SWAP_REQUESTS)}"
            )
        request = request_model(
            chainNetwork=self._to_chain_network(network, chain),
            connector=dex,
            baseToken=base_asset,
            quoteToken=quote_asset,
            amount=amount,
            side=side.name,
            slippagePct=slippage_pct,
        )

        return await self.api_request(
            "get",
            f"trading/{trading_type}/quote-swap",
            _query(request),
            fail_silently=fail_silently
        )

    async def get_price(
        self,
        network: str,
        base_asset: str,
        quote_asset: str,
        amount: Decimal,
        side: TradeType,
        dex: Optional[str] = None,
        trading_type: Optional[str] = None,
        fail_silently: bool = False,
        chain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Wrapper for quote_swap.

        :param network: Network name (e.g., "solana-mainnet-beta")
        :param base_asset: Base token symbol
        :param quote_asset: Quote token symbol
        :param amount: Amount to swap
        :param side: Trade side (BUY or SELL)
        :param dex: DEX protocol name (e.g., "jupiter", "orca", "raydium"). If not provided, uses network's default swap provider.
        :param trading_type: Trading type (e.g., "router", "clmm", "amm"). If not provided, uses network's default swap provider.
        :param fail_silently: Whether to fail silently on error
        :param chain: Chain name; combined with a short network to form the "chain-network" the endpoint requires.
        """
        try:
            response = await self.quote_swap(
                network=network,
                base_asset=base_asset,
                quote_asset=quote_asset,
                amount=amount,
                side=side,
                dex=dex,
                trading_type=trading_type,
                chain=chain,
            )
            return response
        except Exception as e:
            if not fail_silently:
                raise
            return {
                "price": None,
                "error": str(e)
            }

    async def execute_swap(
        self,
        network: str,
        base_asset: str,
        quote_asset: str,
        side: TradeType,
        amount: Decimal,
        dex: Optional[str] = None,
        trading_type: Optional[str] = None,
        slippage_pct: Optional[Decimal] = None,
        wallet_address: Optional[str] = None,
        chain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a swap on the specified DEX via /trading/{router,clmm,amm}/execute-swap.

        :param network: Network name (e.g., "solana-mainnet-beta")
        :param base_asset: Base token symbol
        :param quote_asset: Quote token symbol
        :param side: Trade side (BUY or SELL)
        :param amount: Amount to swap
        :param dex: DEX protocol name (e.g., "jupiter", "orca", "raydium"). If not provided, uses network's default swap provider.
        :param trading_type: Trading type (e.g., "router", "clmm", "amm"). If not provided, uses network's default swap provider.
        :param slippage_pct: Optional slippage percentage
        :param wallet_address: Wallet address to execute the swap
        :param chain: Chain name; combined with a short network to form the "chain-network" the endpoint requires.
        """
        if side not in [TradeType.BUY, TradeType.SELL]:
            raise ValueError("Only BUY and SELL prices are supported.")

        # If dex/trading_type not provided, get from network's default swap provider
        if not dex or not trading_type:
            swap_provider = await self.get_default_swap_provider(network)
            if not swap_provider:
                raise ValueError(f"No swap provider configured for network {network}")
            dex, trading_type = self._parse_swap_provider(swap_provider)

        # /trading/{type}/execute-swap (see quote_swap for the keying rationale).
        request_model = _EXECUTE_SWAP_REQUESTS.get(trading_type)
        if request_model is None:
            raise ValueError(
                f"Unknown trading type '{trading_type}' — expected one of "
                f"{', '.join(_EXECUTE_SWAP_REQUESTS)}"
            )
        request = request_model(
            chainNetwork=self._to_chain_network(network, chain),
            connector=dex,
            baseToken=base_asset,
            quoteToken=quote_asset,
            amount=amount,
            side=side.name,
            slippagePct=slippage_pct,
            walletAddress=wallet_address,
        )
        return await self.api_request(
            "post",
            f"trading/{trading_type}/execute-swap",
            _body(request)
        )

    async def execute_quote(
        self,
        dex: str,
        network: str,
        quote_id: str,
        wallet_address: str,
        chain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a previously obtained quote by its ID.

        Router-only: quoting-then-executing by id is a router affordance, and Gateway
        mounts execute-quote solely under /trading/router. The pool-scoped surfaces
        quote and execute in one call instead, so there is no trading_type to pass.

        :param dex: Router connector name (e.g., "jupiter", "0x")
        :param network: Blockchain network, bare or chain-prefixed
        :param quote_id: ID of the quote to execute
        :param wallet_address: Wallet address that will execute the swap
        :param chain: Chain to combine with a bare network
        :return: Transaction details
        """
        return await self.api_request(
            "post",
            "trading/router/execute-quote",
            _body(
                RouterExecuteQuoteRequest(
                    chainNetwork=self._to_chain_network(network, chain),
                    connector=dex,
                    walletAddress=wallet_address,
                    quoteId=quote_id,
                )
            ),
        )

    async def estimate_gas(
        self,
        chain: str,
        network: str,
    ) -> Dict[str, Any]:
        return await self.api_request("get", f"chains/{chain}/estimate-gas", {
            "network": network
        })

    # ============================================
    # AMM and CLMM Methods
    #
    # These all target Gateway's UNIFIED /trading/{clmm,amm}/* routes, which key the
    # request by a "connector" name plus the full "chain-network" identifier instead of
    # encoding the connector in the path. The legacy per-connector
    # /connectors/{dex}/{type}/* routes each declare their own request schema, and those
    # schemas disagree: raydium/uniswap/pancakeswap/pancakeswap-sol make the CLMM
    # add-liquidity amounts REQUIRED (so a single-sided add 400s), and Meteora's AMM
    # remove-liquidity requires a positionAddress the legacy caller never sent. The
    # unified routes have one schema per verb, so there is a single payload to get right.
    # ============================================

    def _lp_route(self, trading_type: str, verb: str) -> str:
        """Path of a unified /trading LP route, e.g. ("clmm", "open") -> "trading/clmm/open"."""
        if trading_type not in ("clmm", "amm"):
            raise ValueError(f"Trading type '{trading_type}' has no unified /trading LP route")
        return f"trading/{trading_type}/{verb}"

    async def pool_info(
        self,
        network: str,
        pool_address: str,
        dex: str,
        trading_type: str = "clmm",
        chain: Optional[str] = None,
        fail_silently: bool = False,
    ) -> Dict[str, Any]:
        """
        Gets information about a AMM or CLMM pool.

        Args:
            network: Network name (e.g., "mainnet-beta")
            pool_address: Pool contract address
            dex: DEX protocol name (e.g., "orca", "meteora", "raydium")
            trading_type: Trading type (e.g., "clmm", "amm"). Defaults to "clmm".
            chain: Chain name; combined with a short network to form the "chain-network" the endpoint requires.
            fail_silently: If True, suppress errors
        """
        request_model = _POOL_INFO_REQUESTS.get(trading_type)
        if request_model is None:
            raise ValueError(f"Trading type '{trading_type}' has no unified pool-info route")
        query_params = _query(
            request_model(
                connector=dex,
                chainNetwork=self._to_chain_network(network, chain),
                poolAddress=pool_address,
            )
        )

        return await self.api_request(
            "get",
            self._lp_route(trading_type, "pool-info"),
            params=query_params,
            fail_silently=fail_silently,
        )

    async def clmm_position_info(
        self,
        network: str,
        position_address: str,
        dex: str,
        trading_type: str = "clmm",
        chain: Optional[str] = None,
        fail_silently: bool = False,
    ) -> Dict[str, Any]:
        """
        Gets information about a concentrated liquidity position.

        A CLMM position address identifies the position (and its owner) on its own, so
        the unified route takes no wallet address.

        Args:
            network: Network name (e.g., "mainnet-beta")
            position_address: Position address
            dex: DEX protocol name (e.g., "orca", "meteora", "raydium")
            trading_type: Trading type (e.g., "clmm"). Defaults to "clmm".
            chain: Chain name; combined with a short network to form the "chain-network" the endpoint requires.
            fail_silently: If True, suppress errors
        """
        query_params = _query(
            ClmmPositionInfoRequest(
                connector=dex,
                chainNetwork=self._to_chain_network(network, chain),
                positionAddress=position_address,
            )
        )

        return await self.api_request(
            "get",
            self._lp_route(trading_type, "position-info"),
            params=query_params,
            fail_silently=fail_silently,
        )

    async def amm_position_info(
        self,
        network: str,
        wallet_address: str,
        pool_address: str,
        dex: str,
        trading_type: str = "amm",
        chain: Optional[str] = None,
        fail_silently: bool = False,
    ) -> Dict[str, Any]:
        """
        Gets information about a AMM liquidity position.

        Args:
            network: Network name (e.g., "mainnet-beta")
            wallet_address: Wallet address
            pool_address: Pool address
            dex: DEX protocol name (e.g., "raydium")
            trading_type: Trading type. Defaults to "amm".
            chain: Chain name; combined with a short network to form the "chain-network" the endpoint requires.
            fail_silently: If True, suppress errors
        """
        query_params = _query(
            AmmPositionInfoRequest(
                connector=dex,
                chainNetwork=self._to_chain_network(network, chain),
                poolAddress=pool_address,
                walletAddress=wallet_address,
            )
        )

        return await self.api_request(
            "get",
            self._lp_route(trading_type, "position-info"),
            params=query_params,
            fail_silently=fail_silently,
        )

    async def clmm_open_position(
        self,
        network: str,
        wallet_address: str,
        pool_address: str,
        lower_price: float,
        upper_price: float,
        dex: str,
        trading_type: str = "clmm",
        base_token_amount: Optional[float] = None,
        quote_token_amount: Optional[float] = None,
        slippage_pct: Optional[float] = None,
        extra_params: Optional[Dict[str, Any]] = None,
        chain: Optional[str] = None,
        fail_silently: bool = False,
    ) -> Dict[str, Any]:
        """
        Opens a new concentrated liquidity position.

        Args:
            network: Network name (e.g., "mainnet-beta")
            wallet_address: Wallet address
            pool_address: Pool contract address
            lower_price: Lower price bound
            upper_price: Upper price bound
            dex: DEX protocol name (e.g., "orca", "meteora", "raydium")
            trading_type: Trading type. Defaults to "clmm".
            base_token_amount: Amount of base token to deposit
            quote_token_amount: Amount of quote token to deposit
            slippage_pct: Maximum slippage percentage
            extra_params: Optional connector-specific parameters (e.g., {"strategyType": 0} for Meteora)
            chain: Chain name; combined with a short network to form the "chain-network" the endpoint requires.
            fail_silently: If True, suppress errors
        """
        # Both amounts are optional on the unified route (it enforces at least one), so a
        # single-sided open is expressed by omitting the other side — which _body does by
        # dropping whatever is None.
        request_payload = _body(
            ClmmOpenRequest(
                connector=dex,
                chainNetwork=self._to_chain_network(network, chain),
                walletAddress=wallet_address,
                poolAddress=pool_address,
                lowerPrice=lower_price,
                upperPrice=upper_price,
                baseTokenAmount=base_token_amount,
                quoteTokenAmount=quote_token_amount,
                slippagePct=slippage_pct,
            )
        )

        # Connector-specific parameters, merged after the model rather than through it:
        # they are named by the connector, not by the route, so the schema does not
        # describe them and validating against it would reject them.
        if extra_params:
            request_payload.update(extra_params)

        return await self.api_request(
            "post",
            self._lp_route(trading_type, "open"),
            request_payload,
            fail_silently=fail_silently,
        )

    async def clmm_close_position(
        self,
        network: str,
        wallet_address: str,
        position_address: str,
        dex: str,
        trading_type: str = "clmm",
        chain: Optional[str] = None,
        fail_silently: bool = False,
    ) -> Dict[str, Any]:
        """
        Closes an existing concentrated liquidity position.

        Args:
            network: Network name (e.g., "mainnet-beta")
            wallet_address: Wallet address
            position_address: Position address to close
            dex: DEX protocol name (e.g., "orca", "meteora", "raydium")
            trading_type: Trading type. Defaults to "clmm".
            chain: Chain name; combined with a short network to form the "chain-network" the endpoint requires.
            fail_silently: If True, suppress errors
        """
        request_payload = _body(
            ClmmCloseRequest(
                connector=dex,
                chainNetwork=self._to_chain_network(network, chain),
                walletAddress=wallet_address,
                positionAddress=position_address,
            )
        )

        return await self.api_request(
            "post",
            self._lp_route(trading_type, "close"),
            request_payload,
            fail_silently=fail_silently,
        )

    async def clmm_add_liquidity(
        self,
        network: str,
        wallet_address: str,
        position_address: str,
        dex: str,
        trading_type: str = "clmm",
        base_token_amount: Optional[float] = None,
        quote_token_amount: Optional[float] = None,
        slippage_pct: Optional[float] = None,
        extra_params: Optional[Dict[str, Any]] = None,
        chain: Optional[str] = None,
        fail_silently: bool = False,
    ) -> Dict[str, Any]:
        """
        Add liquidity to an existing concentrated liquidity position.

        Args:
            network: Network name (e.g., "mainnet-beta")
            wallet_address: Wallet address
            position_address: Existing position address
            dex: DEX protocol name (e.g., "orca", "meteora", "raydium")
            trading_type: Trading type. Defaults to "clmm".
            base_token_amount: Amount of base token to add
            quote_token_amount: Amount of quote token to add
            slippage_pct: Maximum slippage percentage
            extra_params: Optional connector-specific parameters (e.g., {"strategyType": 0} for Meteora)
            chain: Chain name; combined with a short network to form the "chain-network" the endpoint requires.
            fail_silently: If True, suppress errors
        """
        # Both amounts are optional on the unified route (it enforces at least one), so a
        # single-sided add is expressed by omitting the other side. The legacy
        # per-connector routes made them REQUIRED on raydium/uniswap/pancakeswap(-sol),
        # where the same omission produced a 400.
        request_payload = _body(
            ClmmAddRequest(
                connector=dex,
                chainNetwork=self._to_chain_network(network, chain),
                walletAddress=wallet_address,
                positionAddress=position_address,
                baseTokenAmount=base_token_amount,
                quoteTokenAmount=quote_token_amount,
                slippagePct=slippage_pct,
            )
        )

        # Connector-specific parameters, merged after the model — see clmm_open_position.
        if extra_params:
            request_payload.update(extra_params)

        return await self.api_request(
            "post",
            self._lp_route(trading_type, "add"),
            request_payload,
            fail_silently=fail_silently,
        )

    async def clmm_remove_liquidity(
        self,
        network: str,
        wallet_address: str,
        position_address: str,
        percentage: float,
        dex: str,
        trading_type: str = "clmm",
        chain: Optional[str] = None,
        fail_silently: bool = False,
    ) -> Dict[str, Any]:
        """
        Remove liquidity from a concentrated liquidity position.

        Args:
            network: Network name (e.g., "mainnet-beta")
            wallet_address: Wallet address
            position_address: Position address
            percentage: Percentage of liquidity to remove (0-100)
            dex: DEX protocol name (e.g., "orca", "meteora", "raydium")
            trading_type: Trading type. Defaults to "clmm".
            chain: Chain name; combined with a short network to form the "chain-network" the endpoint requires.
            fail_silently: If True, suppress errors
        """
        request_payload = _body(
            ClmmRemoveRequest(
                connector=dex,
                chainNetwork=self._to_chain_network(network, chain),
                walletAddress=wallet_address,
                positionAddress=position_address,
                percentageToRemove=percentage,
            )
        )

        return await self.api_request(
            "post",
            self._lp_route(trading_type, "remove"),
            request_payload,
            fail_silently=fail_silently,
        )

    async def clmm_collect_fees(
        self,
        network: str,
        wallet_address: str,
        position_address: str,
        dex: str,
        trading_type: str = "clmm",
        chain: Optional[str] = None,
        fail_silently: bool = False,
    ) -> Dict[str, Any]:
        """
        Collect accumulated fees from a concentrated liquidity position.

        Args:
            network: Network name (e.g., "mainnet-beta")
            wallet_address: Wallet address
            position_address: Position address
            dex: DEX protocol name (e.g., "orca", "meteora", "raydium")
            trading_type: Trading type. Defaults to "clmm".
            chain: Chain name; combined with a short network to form the "chain-network" the endpoint requires.
            fail_silently: If True, suppress errors
        """
        request_payload = _body(
            ClmmCollectFeesRequest(
                connector=dex,
                chainNetwork=self._to_chain_network(network, chain),
                walletAddress=wallet_address,
                positionAddress=position_address,
            )
        )

        return await self.api_request(
            "post",
            self._lp_route(trading_type, "collect-fees"),
            request_payload,
            fail_silently=fail_silently,
        )

    async def clmm_positions_owned(
        self,
        network: str,
        wallet_address: str,
        dex: str,
        trading_type: str = "clmm",
        chain: Optional[str] = None,
        fail_silently: bool = False,
    ) -> Dict[str, Any]:
        """
        Get all CLMM positions owned by a wallet.

        Args:
            network: Network name (e.g., "mainnet-beta")
            wallet_address: Wallet address
            dex: DEX protocol name (e.g., "orca", "meteora", "raydium")
            trading_type: Trading type. Defaults to "clmm".
            chain: Chain name; combined with a short network to form the "chain-network" the endpoint requires.
            fail_silently: If True, suppress errors

        Note: Filtering by pool_address must be done client-side.
        """
        query_params = _query(
            ClmmPositionsOwnedRequest(
                connector=dex,
                chainNetwork=self._to_chain_network(network, chain),
                walletAddress=wallet_address,
            )
        )

        return await self.api_request(
            "get",
            self._lp_route(trading_type, "positions-owned"),
            params=query_params,
            fail_silently=fail_silently,
        )

    async def amm_quote_liquidity(
        self,
        network: str,
        pool_address: str,
        base_token_amount: float,
        quote_token_amount: float,
        dex: str,
        trading_type: str = "amm",
        slippage_pct: Optional[float] = None,
        chain: Optional[str] = None,
        fail_silently: bool = False,
    ) -> Dict[str, Any]:
        """
        Quote the required token amounts for adding liquidity to an AMM pool.

        Args:
            network: Network name (e.g., "mainnet-beta")
            pool_address: Pool address
            base_token_amount: Amount of base token
            quote_token_amount: Amount of quote token
            dex: DEX protocol name (e.g., "raydium")
            trading_type: Trading type. Defaults to "amm".
            slippage_pct: Maximum slippage percentage
            chain: Chain name; combined with a short network to form the "chain-network" the endpoint requires.
            fail_silently: If True, suppress errors
        """
        query_params = _query(
            AmmQuoteLiquidityRequest(
                connector=dex,
                chainNetwork=self._to_chain_network(network, chain),
                poolAddress=pool_address,
                baseTokenAmount=base_token_amount,
                quoteTokenAmount=quote_token_amount,
                slippagePct=slippage_pct,
            )
        )

        return await self.api_request(
            "get",
            self._lp_route(trading_type, "quote-liquidity"),
            params=query_params,
            fail_silently=fail_silently,
        )

    async def clmm_quote_position(
        self,
        network: str,
        pool_address: str,
        lower_price: float,
        upper_price: float,
        dex: str,
        trading_type: str = "clmm",
        base_token_amount: Optional[float] = None,
        quote_token_amount: Optional[float] = None,
        slippage_pct: Optional[float] = None,
        chain: Optional[str] = None,
        fail_silently: bool = False,
    ) -> Dict[str, Any]:
        """
        Quote the required token amounts for opening a CLMM position.

        Args:
            network: Network name (e.g., "mainnet-beta")
            pool_address: Pool address
            lower_price: Lower price bound
            upper_price: Upper price bound
            dex: DEX protocol name (e.g., "orca", "meteora", "raydium")
            trading_type: Trading type. Defaults to "clmm".
            base_token_amount: Amount of base token
            quote_token_amount: Amount of quote token
            slippage_pct: Maximum slippage percentage
            chain: Chain name; combined with a short network to form the "chain-network" the endpoint requires.
            fail_silently: If True, suppress errors
        """
        query_params = _query(
            ClmmQuoteLiquidityRequest(
                connector=dex,
                chainNetwork=self._to_chain_network(network, chain),
                poolAddress=pool_address,
                lowerPrice=lower_price,
                upperPrice=upper_price,
                baseTokenAmount=base_token_amount,
                quoteTokenAmount=quote_token_amount,
                slippagePct=slippage_pct,
            )
        )

        return await self.api_request(
            "get",
            self._lp_route(trading_type, "quote-liquidity"),
            params=query_params,
            fail_silently=fail_silently,
        )

    async def amm_add_liquidity(
        self,
        network: str,
        wallet_address: str,
        pool_address: str,
        base_token_amount: float,
        quote_token_amount: float,
        dex: str,
        trading_type: str = "amm",
        slippage_pct: Optional[float] = None,
        position_address: Optional[str] = None,
        chain: Optional[str] = None,
        fail_silently: bool = False,
    ) -> Dict[str, Any]:
        """
        Add liquidity to an AMM liquidity position.

        Args:
            network: Network name (e.g., "mainnet-beta")
            wallet_address: Wallet address
            pool_address: Pool address
            base_token_amount: Amount of base token
            quote_token_amount: Amount of quote token
            dex: DEX protocol name (e.g., "raydium")
            trading_type: Trading type. Defaults to "amm".
            slippage_pct: Maximum slippage percentage
            position_address: Existing position (NFT) to add to on AMMs whose LP is
                non-fungible (Meteora DAMM v2). Omit to open a new position; ignored by
                fungible-LP AMMs.
            chain: Chain name; combined with a short network to form the "chain-network" the endpoint requires.
            fail_silently: If True, suppress errors
        """
        request_payload = _body(
            AmmAddRequest(
                connector=dex,
                chainNetwork=self._to_chain_network(network, chain),
                walletAddress=wallet_address,
                poolAddress=pool_address,
                baseTokenAmount=base_token_amount,
                quoteTokenAmount=quote_token_amount,
                positionAddress=position_address,
                slippagePct=slippage_pct,
            )
        )

        return await self.api_request(
            "post",
            self._lp_route(trading_type, "add"),
            request_payload,
            fail_silently=fail_silently,
        )

    async def amm_remove_liquidity(
        self,
        network: str,
        wallet_address: str,
        pool_address: str,
        percentage: float,
        dex: str,
        trading_type: str = "amm",
        position_address: Optional[str] = None,
        chain: Optional[str] = None,
        fail_silently: bool = False,
    ) -> Dict[str, Any]:
        """
        Closes an existing AMM liquidity position.

        Args:
            network: Network name (e.g., "mainnet-beta")
            wallet_address: Wallet address
            pool_address: Pool address
            percentage: Percentage of liquidity to remove (0-100)
            dex: DEX protocol name (e.g., "raydium")
            trading_type: Trading type. Defaults to "amm".
            position_address: The specific position (NFT) to remove from. REQUIRED by
                Meteora DAMM v2, whose positions are non-fungible and where a wallet may
                hold several per pool; ignored by fungible-LP AMMs.
            chain: Chain name; combined with a short network to form the "chain-network" the endpoint requires.
            fail_silently: If True, suppress errors
        """
        request_payload = _body(
            AmmRemoveRequest(
                connector=dex,
                chainNetwork=self._to_chain_network(network, chain),
                walletAddress=wallet_address,
                poolAddress=pool_address,
                percentageToRemove=percentage,
                positionAddress=position_address,
            )
        )

        return await self.api_request(
            "post",
            self._lp_route(trading_type, "remove"),
            request_payload,
            fail_silently=fail_silently,
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
            "get",
            "tokens",
            params=params
        )
        return response

    async def get_token(
        self,
        symbol_or_address: str,
        chain: str,
        network: str,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """Get details for a specific token by symbol or address."""
        params = {"chain": chain, "network": network}
        try:
            response = await self.api_request(
                "get",
                f"tokens/{symbol_or_address}",
                params=params,
                fail_silently=fail_silently
            )
            return response
        except Exception as e:
            return {"error": f"Token '{symbol_or_address}' not found on {chain}/{network}: {str(e)}"}

    async def add_token(
        self,
        chain: str,
        network: str,
        token_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add a new token to the gateway."""
        return await self.api_request(
            "post",
            "tokens",
            params={
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
        """Remove a token from the gateway.

        Gateway declares chain/network as required QUERYSTRING for this DELETE;
        api_request sends DELETE params as a JSON body, so they ride the URL here.
        """
        query = urlencode({"chain": chain, "network": network})
        return await self.api_request("delete", f"tokens/{address}?{query}")

    # ============================================
    # Pool Methods
    # ============================================

    async def get_pool(
        self,
        trading_pair: str,
        chain: str,
        network: str,
        trading_type: str = "amm",
        connector: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get pool information for a specific trading pair.

        :param trading_pair: Trading pair (e.g., "SOL-USDC")
        :param chain: Blockchain chain (e.g., "solana", "ethereum")
        :param network: Network name (e.g., "mainnet-beta")
        :param trading_type: Pool type ("amm" or "clmm"), defaults to "amm"
        :param connector: Optional connector filter (e.g., "raydium", "orca", "uniswap")
        :return: Pool information including address
        """
        params = {
            "chain": chain,
            "network": network,
            "type": trading_type
        }
        if connector:
            params["connector"] = connector

        response = await self.api_request("get", f"pools/{trading_pair}", params=params)
        return response

    async def add_pool(
        self,
        chain: str,
        connector: str,
        network: str,
        pool_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Add a new pool to tracking.

        :param chain: Blockchain chain (e.g., "solana", "ethereum")
        :param connector: Connector name
        :param network: Network name
        :param pool_data: Pool configuration data. Required fields:
            - address (str): Pool contract address
            - type (str): Pool type ("amm" or "clmm")
            - baseTokenAddress (str): Base token contract address
            - quoteTokenAddress (str): Quote token contract address
            Optional fields from pool-info:
            - baseSymbol (str): Base token symbol
            - quoteSymbol (str): Quote token symbol
            - feePct (float): Pool fee percentage
        :return: Response with status
        """
        params = {
            "chain": chain,
            "connector": connector,
            "network": network,
            **pool_data
        }
        return await self.api_request("post", "pools", params=params)

    async def remove_pool(
        self,
        address: str,
        chain: str,
        network: str,
        pool_type: str = "amm"
    ) -> Dict[str, Any]:
        """
        Remove a pool from tracking.

        :param address: Pool address to remove
        :param chain: Blockchain chain (e.g., "solana", "ethereum")
        :param network: Network name
        :param pool_type: Pool type (amm or clmm)
        :return: Response with status
        """
        # Gateway's route declares chain/network as required QUERYSTRING (and no
        # "type" at all); api_request sends DELETE params as a body, so ride the URL.
        query = urlencode({"chain": chain, "network": network})
        return await self.api_request("delete", f"pools/{address}?{query}")

    async def list_pools(
        self,
        chain: str,
        network: str,
        search: Optional[str] = None,
        connector: Optional[str] = None,
        pool_type: Optional[str] = None,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        List pools for a chain/network with optional filtering.

        :param chain: Blockchain chain (e.g., "solana", "ethereum")
        :param network: Network name (e.g., "mainnet-beta")
        :param search: Optional search term (trading pair or address)
        :param connector: Optional connector filter (e.g., "raydium", "orca")
        :param pool_type: Optional pool type filter ("amm" or "clmm")
        :param fail_silently: If True, return error dict instead of raising
        :return: List of pools
        """
        params = {
            "chain": chain,
            "network": network
        }
        if search:
            params["search"] = search
        if connector:
            params["connector"] = connector
        if pool_type:
            params["type"] = pool_type

        try:
            response = await self.api_request("get", "pools", params=params)
            return response
        except Exception as e:
            if fail_silently:
                return {"error": str(e)}
            raise

    async def save_pool(
        self,
        chain_network: str,
        address: str
    ) -> Dict[str, Any]:
        """
        Save a pool by address using GeckoTerminal lookup.
        This fetches pool info from GeckoTerminal and saves it.

        :param chain_network: Chain-network string (e.g., "solana-mainnet-beta")
        :param address: Pool contract address
        :return: Response with saved pool info
        """
        # POST with query params - need to append to URL since api_request sends POST params as body
        return await self.api_request("post", f"pools/save/{address}?chainNetwork={chain_network}")

    # ============================================
    # Gateway Command Utils - API Functions
    # ============================================

    async def get_default_wallet(
        self,
        chain: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Get default wallet for a chain.

        :param chain: Chain name
        :return: Tuple of (wallet_address, error_message)
        """
        wallet_address = await self.get_default_wallet_for_chain(chain)
        if not wallet_address:
            return None, f"No default wallet found for {chain}. Please add one with 'gateway connect {chain}'"

        # Check if wallet address is a placeholder
        if "wallet-address" in wallet_address.lower():
            return None, f"{chain} wallet not configured (found placeholder: {wallet_address}). Please add a real wallet with: gateway connect {chain}"

        return wallet_address, None

    async def get_connector_config(
        self,
        connector: str
    ) -> Dict:
        """
        Get connector configuration.

        :param connector: Connector name (with or without type suffix)
        :return: Configuration dictionary
        """
        try:
            # Use base connector name for config (strip type suffix)
            base_connector = connector.split("/")[0] if "/" in connector else connector
            return await self.get_configuration(namespace=base_connector)
        except Exception:
            return {}

    async def get_connector_chain_network(
        self,
        connector: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Get chain and network for a network-format connector.

        :param connector: Network connector in format 'chain-network' (e.g., 'solana-mainnet-beta', 'ethereum-mainnet')
        :return: Tuple of (chain, network, error_message)
        """
        try:
            if '-' not in connector:
                return None, None, f"Invalid network format '{connector}'. Use format like 'solana-mainnet-beta'"

            # Try to find in chains config first
            chains_resp = await self.get_chains(fail_silently=True)
            if chains_resp and "chains" in chains_resp:
                for chain_info in chains_resp["chains"]:
                    chain_name = chain_info["chain"]
                    for network in chain_info.get("networks", []):
                        network_connector = f"{chain_name}-{network}"
                        if connector == network_connector:
                            return chain_name, network, None

            # Fallback: parse directly using GATEWAY_CHAINS
            parts = connector.split('-', 1)
            if len(parts) == 2 and parts[0].lower() in [c.lower() for c in GATEWAY_CHAINS]:
                return parts[0], parts[1], None

            return None, None, f"Unknown network '{connector}'"

        except Exception as e:
            return None, None, f"Error parsing network: {str(e)}"

    async def get_dex_info(
        self,
        dex_connector: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        Get DEX info including chain and network for a DEX-format connector.

        :param dex_connector: DEX connector in format 'dex/trading_type' (e.g., 'orca/clmm', 'jupiter/router')
        :return: Tuple of (dex_name, trading_type, chain, network, error_message)
        """
        try:
            if '/' not in dex_connector:
                return None, None, None, None, f"Invalid DEX format '{dex_connector}'. Use format like 'orca/clmm'"

            # Parse dex_name and trading_type
            dex_name, trading_type = dex_connector.split('/', 1)

            # Get connector info to find chain
            connectors_resp = await self.get_connectors()
            if "error" in connectors_resp:
                return None, None, None, None, f"Error getting connectors: {connectors_resp['error']}"

            # Find the connector info
            connector_info = None
            for conn in connectors_resp.get("connectors", []):
                if conn.get("name") == dex_name:
                    connector_info = conn
                    break

            if not connector_info:
                return None, None, None, None, f"DEX '{dex_name}' not found"

            # Get chain from connector info
            chain = connector_info.get("chain")
            if not chain:
                return None, None, None, None, f"Could not determine chain for DEX '{dex_name}'"

            # Get default network for the chain
            network = await self.get_default_network_for_chain(chain)
            if not network:
                return None, None, None, None, f"Could not get default network for chain '{chain}'"

            return dex_name, trading_type, chain, network, None

        except Exception as e:
            return None, None, None, None, f"Error getting DEX info: {str(e)}"

    async def get_available_tokens(
        self,
        chain: str,
        network: str
    ) -> List[Dict[str, Any]]:
        """
        Get list of available tokens with full information.

        :param chain: Chain name
        :param network: Network name
        :return: List of Token objects containing symbol, address, decimals, and name
        """
        try:
            tokens_resp = await self.get_tokens(chain, network)
            tokens = tokens_resp.get("tokens", [])
            # Return the full token objects
            return tokens
        except Exception:
            return []

    async def get_available_networks_for_chain(
        self,
        chain: str
    ) -> List[str]:
        """
        Get list of available networks for a specific chain.

        :param chain: Chain name (e.g., "ethereum", "solana")
        :return: List of network names available for the chain
        """
        try:
            # Get chain configuration
            chains_resp = await self.get_chains()
            if not chains_resp or "chains" not in chains_resp:
                return []

            # Find the specific chain
            for chain_info in chains_resp["chains"]:
                if chain_info.get("chain", "").lower() == chain.lower():
                    # Get networks from the chain config
                    networks = chain_info.get("networks", [])
                    return networks

            return []
        except Exception:
            return []

    async def validate_tokens(
        self,
        chain: str,
        network: str,
        token_symbols: List[str]
    ) -> Tuple[List[str], List[str]]:
        """
        Validate that tokens exist in the available token list.

        :param chain: Chain name
        :param network: Network name
        :param token_symbols: List of token symbols to validate
        :return: Tuple of (valid_tokens, invalid_tokens)
        """
        if not token_symbols:
            return [], []

        # Get available tokens
        available_tokens = await self.get_available_tokens(chain, network)
        available_symbols = {token["symbol"].upper() for token in available_tokens}

        # Check which tokens are valid/invalid
        valid_tokens = []
        invalid_tokens = []

        for token in token_symbols:
            token_upper = token.upper()
            if token_upper in available_symbols:
                valid_tokens.append(token_upper)
            else:
                invalid_tokens.append(token)

        return valid_tokens, invalid_tokens

    async def get_wallet_balances(
        self,
        chain: str,
        network: str,
        wallet_address: str,
        tokens_to_check: List[str],
        native_token: str
    ) -> Dict[str, float]:
        """
        Get wallet balances for specified tokens.

        :param chain: Chain name
        :param network: Network name
        :param wallet_address: Wallet address
        :param tokens_to_check: List of tokens to check
        :param native_token: Native token symbol (e.g., ETH, SOL)
        :return: Dictionary of token balances
        """
        # Ensure native token is in the list
        if native_token not in tokens_to_check:
            tokens_to_check = tokens_to_check + [native_token]

        # Fetch balances
        try:
            balances_resp = await self.get_balances(
                chain, network, wallet_address, tokens_to_check
            )
            balances = balances_resp.get("balances", {})

            # Convert to float
            balance_dict = {}
            for token in tokens_to_check:
                balance = float(balances.get(token, 0))
                balance_dict[token] = balance

            return balance_dict

        except Exception:
            return {}

    async def estimate_transaction_fee(
        self,
        chain: str,
        network: str,
    ) -> Dict[str, Any]:
        """
        Estimate transaction fee using gateway's estimate-gas endpoint.

        :param chain: Chain name (e.g., "ethereum", "solana")
        :param network: Network name
        :return: Dictionary with fee estimation details
        """
        try:
            # Get gas estimation from gateway
            gas_resp = await self.estimate_gas(chain, network)

            # Extract fee info directly from response
            fee_per_unit = gas_resp.get("feePerComputeUnit", 0)
            denomination = gas_resp.get("denomination", "")
            compute_units = gas_resp.get("computeUnits", 0)
            fee_in_native = gas_resp.get("fee", 0)  # Use the fee directly from response
            native_token = gas_resp.get("feeAsset", chain.upper())  # Use feeAsset from response

            # Extract EIP-1559 specific fields if present
            gas_type = gas_resp.get("gasType")
            max_fee_per_gas = gas_resp.get("maxFeePerGas")
            max_priority_fee_per_gas = gas_resp.get("maxPriorityFeePerGas")

            result = {
                "success": True,
                "fee_per_unit": fee_per_unit,
                "estimated_units": compute_units,
                "denomination": denomination,
                "fee_in_native": fee_in_native,
                "native_token": native_token
            }

            # Add EIP-1559 fields if present
            if gas_type:
                result["gas_type"] = gas_type
            if max_fee_per_gas is not None:
                result["max_fee_per_gas"] = max_fee_per_gas
            if max_priority_fee_per_gas is not None:
                result["max_priority_fee_per_gas"] = max_priority_fee_per_gas

            return result

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "fee_per_unit": 0,
                "estimated_units": 0,
                "denomination": "units",
                "fee_in_native": 0,
                "native_token": chain.upper()
            }
