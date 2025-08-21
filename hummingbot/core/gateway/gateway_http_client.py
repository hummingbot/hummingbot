import logging
import re
import ssl
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

import aiohttp
from aiohttp import ContentTypeError

from hummingbot.client.config.security import Security
from hummingbot.connector.gateway.common_types import ConnectorType, get_connector_type
from hummingbot.core.event.events import TradeType
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class GatewayError(Enum):
    """
    The gateway route error codes defined in /gateway/src/services/error-handler.ts
    """

    Network = 1001
    RateLimit = 1002
    OutOfGas = 1003
    TransactionGasPriceTooLow = 1004
    LoadWallet = 1005
    TokenNotSupported = 1006
    TradeFailed = 1007
    SwapPriceExceedsLimitPrice = 1008
    SwapPriceLowerThanLimitPrice = 1009
    ServiceUnitialized = 1010
    UnknownChainError = 1011
    InvalidNonceError = 1012
    PriceFailed = 1013
    UnknownError = 1099
    InsufficientBaseBalance = 1022
    InsufficientQuoteBalance = 1023
    SimulationError = 1024
    SwapRouteFetchError = 1025


class GatewayHttpClient:
    """
    An HTTP client for making requests to the gateway API.
    """

    _ghc_logger: Optional[HummingbotLogger] = None
    _shared_client: Optional[aiohttp.ClientSession] = None
    _base_url: str
    _use_ssl: bool

    __instance = None

    @staticmethod
    def get_instance(client_config_map: Optional["ClientConfigAdapter"] = None) -> "GatewayHttpClient":
        if GatewayHttpClient.__instance is None:
            GatewayHttpClient(client_config_map)
        return GatewayHttpClient.__instance

    def __init__(self, client_config_map: Optional["ClientConfigAdapter"] = None):
        if client_config_map is None:
            from hummingbot.client.hummingbot_application import HummingbotApplication
            client_config_map = HummingbotApplication.main_application().client_config_map
        api_host = client_config_map.gateway.gateway_api_host
        api_port = client_config_map.gateway.gateway_api_port
        use_ssl = client_config_map.gateway.gateway_use_ssl
        if GatewayHttpClient.__instance is None:
            protocol = "https" if use_ssl else "http"
            self._base_url = f"{protocol}://{api_host}:{api_port}"
            self._use_ssl = use_ssl
        self._client_config_map = client_config_map
        GatewayHttpClient.__instance = self

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._ghc_logger is None:
            cls._ghc_logger = logging.getLogger(__name__)
        return cls._ghc_logger

    @classmethod
    def _http_client(cls, client_config_map: "ClientConfigAdapter", re_init: bool = False) -> aiohttp.ClientSession:
        """
        :returns Shared client session instance
        """
        if cls._shared_client is None or re_init:
            use_ssl = getattr(client_config_map.gateway, "gateway_use_ssl", False)
            if use_ssl:
                # SSL connection with client certs
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

    @property
    def base_url(self) -> str:
        return self._base_url

    @base_url.setter
    def base_url(self, url: str):
        self._base_url = url

    def log_error_codes(self, resp: Dict[str, Any]):
        """
        If the API returns an error code, interpret the code, log a useful
        message to the user, then raise an exception.
        """
        error_code: Optional[int] = resp.get("errorCode") if isinstance(resp, dict) else None
        if error_code is not None:
            if error_code == GatewayError.Network.value:
                self.logger().network("Gateway had a network error. Make sure it is still able to communicate with the node.")
            elif error_code == GatewayError.RateLimit.value:
                self.logger().network("Gateway was unable to communicate with the node because of rate limiting.")
            elif error_code == GatewayError.OutOfGas.value:
                self.logger().network("There was an out of gas error. Adjust the gas limit in the gateway config.")
            elif error_code == GatewayError.TransactionGasPriceTooLow.value:
                self.logger().network("The gas price provided by gateway was too low to create a blockchain operation. Consider increasing the gas price.")
            elif error_code == GatewayError.LoadWallet.value:
                self.logger().network("Gateway failed to load your wallet. Try running 'gateway connect' with the correct wallet settings.")
            elif error_code == GatewayError.TokenNotSupported.value:
                self.logger().network("Gateway tried to use an unsupported token.")
            elif error_code == GatewayError.TradeFailed.value:
                self.logger().network("The trade on gateway has failed.")
            elif error_code == GatewayError.PriceFailed.value:
                self.logger().network("The price query on gateway has failed.")
            elif error_code == GatewayError.InvalidNonceError.value:
                self.logger().network("The nonce was invalid.")
            elif error_code == GatewayError.ServiceUnitialized.value:
                self.logger().network("Some values was uninitialized. Please contact dev@hummingbot.io ")
            elif error_code == GatewayError.SwapPriceExceedsLimitPrice.value:
                self.logger().network("The swap price is greater than your limit buy price. The market may be too volatile or your slippage rate is too low. Try adjusting the strategy's allowed slippage rate.")
            elif error_code == GatewayError.SwapPriceLowerThanLimitPrice.value:
                self.logger().network("The swap price is lower than your limit sell price. The market may be too volatile or your slippage rate is too low. Try adjusting the strategy's allowed slippage rate.")
            elif error_code == GatewayError.UnknownChainError.value:
                self.logger().network("An unknown chain error has occurred on gateway. Make sure your gateway settings are correct.")
            elif error_code == GatewayError.InsufficientBaseBalance.value:
                self.logger().network("Insufficient base token balance needed to execute the trade.")
            elif error_code == GatewayError.InsufficientQuoteBalance.value:
                self.logger().network("Insufficient quote token balance needed to execute the trade.")
            elif error_code == GatewayError.SimulationError.value:
                self.logger().network("Transaction simulation failed.")
            elif error_code == GatewayError.SwapRouteFetchError.value:
                self.logger().network("Failed to fetch swap route.")
            elif error_code == GatewayError.UnknownError.value:
                self.logger().network("An unknown error has occurred on gateway. Please send your logs to operations@hummingbot.org.")
            else:
                self.logger().network("An unknown error has occurred on gateway. Please send your logs to operations@hummingbot.org.")

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
        client = self._http_client(self._client_config_map)

        parsed_response = {}
        try:
            if method == "get":
                if len(params) > 0:
                    if use_body:
                        response = await client.get(url, json=params)
                    else:
                        response = await client.get(url, params=params)
                else:
                    response = await client.get(url)
            elif method == "post":
                response = await client.post(url, json=params)
            elif method == 'put':
                response = await client.put(url, json=params)
            elif method == 'delete':
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
                    self.log_error_codes(parsed_response)

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

    # ============================================
    # Gateway Status and Restart Methods
    # ============================================

    async def ping_gateway(self) -> bool:
        try:
            response: Dict[str, Any] = await self.api_request("get", "", fail_silently=True)
            return response["status"] == "ok"
        except Exception:
            return False

    async def get_gateway_status(self, fail_silently: bool = False) -> List[Dict[str, Any]]:
        """
        Calls the status endpoint on Gateway to know basic info about connected networks.
        """
        try:
            return await self.get_network_status(fail_silently=fail_silently)
        except Exception as e:
            self.logger().network(
                "Error fetching gateway status info",
                exc_info=True,
                app_warning_msg=str(e)
            )

    async def get_network_status(
        self,
        chain: str = None,
        network: str = None,
        fail_silently: bool = False
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        req_data: Dict[str, str] = {}
        req_data["network"] = network
        return await self.api_request("get", f"chains/{chain}/status", req_data, fail_silently=fail_silently)

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
        token_symbols: List[str],
        fail_silently: bool = False,
    ) -> Dict[str, Any]:
        if isinstance(token_symbols, list):
            token_symbols = [x for x in token_symbols if isinstance(x, str) and x.strip() != '']
            request_params = {
                "network": network,
                "address": address,
                "tokens": token_symbols,
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

    async def quote_swap(
        self,
        network: str,
        connector: str,
        base_asset: str,
        quote_asset: str,
        amount: Decimal,
        side: TradeType,
        slippage_pct: Optional[Decimal] = None,
        pool_address: Optional[str] = None,
        fail_silently: bool = False,
    ) -> Dict[str, Any]:
        if side not in [TradeType.BUY, TradeType.SELL]:
            raise ValueError("Only BUY and SELL prices are supported.")

        connector_type = get_connector_type(connector)

        request_payload = {
            "network": network,
            "baseToken": base_asset,
            "quoteToken": quote_asset,
            "amount": float(amount),
            "side": side.name
        }
        if slippage_pct is not None:
            request_payload["slippagePct"] = float(slippage_pct)
        if connector_type in (ConnectorType.CLMM, ConnectorType.AMM) and pool_address is not None:
            request_payload["poolAddress"] = pool_address

        return await self.api_request(
            "get",
            f"connectors/{connector}/quote-swap",
            request_payload,
            fail_silently=fail_silently
        )

    async def get_price(
        self,
        chain: str,
        network: str,
        connector: str,
        base_asset: str,
        quote_asset: str,
        amount: Decimal,
        side: TradeType,
        fail_silently: bool = False,
        pool_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Wrapper for quote_swap
        """
        try:
            response = await self.quote_swap(
                network=network,
                connector=connector,
                base_asset=base_asset,
                quote_asset=quote_asset,
                amount=amount,
                side=side,
                pool_address=pool_address
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
        connector: str,
        base_asset: str,
        quote_asset: str,
        side: TradeType,
        amount: Decimal,
        slippage_pct: Optional[Decimal] = None,
        pool_address: Optional[str] = None,
        network: Optional[str] = None,
        wallet_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        if side not in [TradeType.BUY, TradeType.SELL]:
            raise ValueError("Only BUY and SELL prices are supported.")

        request_payload: Dict[str, Any] = {
            "baseToken": base_asset,
            "quoteToken": quote_asset,
            "amount": float(amount),
            "side": side.name,
        }
        if slippage_pct is not None:
            request_payload["slippagePct"] = float(slippage_pct)
        if pool_address is not None:
            request_payload["poolAddress"] = pool_address
        if network is not None:
            request_payload["network"] = network
        if wallet_address is not None:
            request_payload["walletAddress"] = wallet_address
        return await self.api_request(
            "post",
            f"connectors/{connector}/execute-swap",
            request_payload
        )

    async def execute_quote(
        self,
        connector: str,
        quote_id: str,
        network: Optional[str] = None,
        wallet_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a previously obtained quote by its ID.

        :param connector: Connector name (e.g., 'jupiter/router')
        :param quote_id: ID of the quote to execute
        :param network: Optional blockchain network to use
        :param wallet_address: Optional wallet address that will execute the swap
        :return: Transaction details
        """
        request_payload: Dict[str, Any] = {
            "quoteId": quote_id,
        }
        if network is not None:
            request_payload["network"] = network
        if wallet_address is not None:
            request_payload["walletAddress"] = wallet_address

        return await self.api_request(
            "post",
            f"connectors/{connector}/execute-quote",
            request_payload
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
    # ============================================

    async def pool_info(
        self,
        connector: str,
        network: str,
        pool_address: str,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Gets information about a AMM or CLMM pool
        """
        query_params = {
            "network": network,
            "poolAddress": pool_address
        }

        # Parse connector to get name and type
        # Format is always "raydium/amm" with the "/" included
        connector_name, connector_type = connector.split("/", 1)
        path = f"connectors/{connector_name}/{connector_type}/pool-info"

        return await self.api_request(
            "get",
            path,
            params=query_params,
            fail_silently=fail_silently,
        )

    async def clmm_position_info(
        self,
        connector: str,
        network: str,
        position_address: str,
        wallet_address: str,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Gets information about a concentrated liquidity position
        """
        query_params = {
            "network": network,
            "positionAddress": position_address,
            "walletAddress": wallet_address,
        }

        # Parse connector to get name and type
        # Format is always "raydium/clmm" with the "/" included
        connector_name, connector_type = connector.split("/", 1)
        path = f"connectors/{connector_name}/{connector_type}/position-info"

        return await self.api_request(
            "get",
            path,
            params=query_params,
            fail_silently=fail_silently,
        )

    async def amm_position_info(
        self,
        connector: str,
        network: str,
        wallet_address: str,
        pool_address: str,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Gets information about a AMM liquidity position
        """
        query_params = {
            "network": network,
            "walletAddress": wallet_address,
            "poolAddress": pool_address
        }

        # Parse connector to get name and type
        # Format is always "raydium/amm" with the "/" included
        connector_name, connector_type = connector.split("/", 1)
        path = f"connectors/{connector_name}/{connector_type}/position-info"

        return await self.api_request(
            "get",
            path,
            params=query_params,
            fail_silently=fail_silently,
        )

    async def clmm_open_position(
        self,
        connector: str,
        network: str,
        wallet_address: str,
        pool_address: str,
        lower_price: float,
        upper_price: float,
        base_token_amount: Optional[float] = None,
        quote_token_amount: Optional[float] = None,
        slippage_pct: Optional[float] = None,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Opens a new concentrated liquidity position
        """
        request_payload = {
            "network": network,
            "walletAddress": wallet_address,
            "poolAddress": pool_address,
            "lowerPrice": lower_price,
            "upperPrice": upper_price,
        }
        if base_token_amount is not None:
            request_payload["baseTokenAmount"] = base_token_amount
        if quote_token_amount is not None:
            request_payload["quoteTokenAmount"] = quote_token_amount
        if slippage_pct is not None:
            request_payload["slippagePct"] = slippage_pct

        # Parse connector to get name and type
        connector_name, connector_type = connector.split("/", 1)
        path = f"connectors/{connector_name}/{connector_type}/open-position"

        return await self.api_request(
            "post",
            path,
            request_payload,
            fail_silently=fail_silently,
        )

    async def clmm_close_position(
        self,
        connector: str,
        network: str,
        wallet_address: str,
        position_address: str,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Closes an existing concentrated liquidity position
        """
        request_payload = {
            "network": network,
            "walletAddress": wallet_address,
            "positionAddress": position_address,
        }

        # Parse connector to get name and type
        connector_name, connector_type = connector.split("/", 1)
        path = f"connectors/{connector_name}/{connector_type}/close-position"

        return await self.api_request(
            "post",
            path,
            request_payload,
            fail_silently=fail_silently,
        )

    async def clmm_add_liquidity(
        self,
        connector: str,
        network: str,
        wallet_address: str,
        position_address: str,
        base_token_amount: Optional[float] = None,
        quote_token_amount: Optional[float] = None,
        slippage_pct: Optional[float] = None,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Add liquidity to an existing concentrated liquidity position
        """
        request_payload = {
            "network": network,
            "walletAddress": wallet_address,
            "positionAddress": position_address,
        }
        if base_token_amount is not None:
            request_payload["baseTokenAmount"] = base_token_amount
        if quote_token_amount is not None:
            request_payload["quoteTokenAmount"] = quote_token_amount
        if slippage_pct is not None:
            request_payload["slippagePct"] = slippage_pct

        # Parse connector to get name and type
        connector_name, connector_type = connector.split("/", 1)
        path = f"connectors/{connector_name}/{connector_type}/add-liquidity"

        return await self.api_request(
            "post",
            path,
            request_payload,
            fail_silently=fail_silently,
        )

    async def clmm_remove_liquidity(
        self,
        connector: str,
        network: str,
        wallet_address: str,
        position_address: str,
        percentage: float,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Remove liquidity from a concentrated liquidity position
        """
        request_payload = {
            "network": network,
            "walletAddress": wallet_address,
            "positionAddress": position_address,
            "percentageToRemove": percentage,
        }

        # Parse connector to get name and type
        connector_name, connector_type = connector.split("/", 1)
        path = f"connectors/{connector_name}/{connector_type}/remove-liquidity"

        return await self.api_request(
            "post",
            path,
            request_payload,
            fail_silently=fail_silently,
        )

    async def clmm_collect_fees(
        self,
        connector: str,
        network: str,
        wallet_address: str,
        position_address: str,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Collect accumulated fees from a concentrated liquidity position
        """
        request_payload = {
            "network": network,
            "walletAddress": wallet_address,
            "positionAddress": position_address,
        }

        # Parse connector to get name and type
        connector_name, connector_type = connector.split("/", 1)
        path = f"connectors/{connector_name}/{connector_type}/collect-fees"

        return await self.api_request(
            "post",
            path,
            request_payload,
            fail_silently=fail_silently,
        )

    async def clmm_positions_owned(
        self,
        connector: str,
        network: str,
        wallet_address: str,
        pool_address: Optional[str] = None,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Get all CLMM positions owned by a wallet, optionally filtered by pool
        """
        query_params = {
            "network": network,
            "walletAddress": wallet_address,
        }
        if pool_address:
            query_params["poolAddress"] = pool_address

        # Parse connector to get name and type
        connector_name, connector_type = connector.split("/", 1)
        path = f"connectors/{connector_name}/{connector_type}/positions-owned"

        return await self.api_request(
            "get",
            path,
            params=query_params,
            fail_silently=fail_silently,
        )

    async def amm_quote_liquidity(
        self,
        connector: str,
        network: str,
        pool_address: str,
        base_token_amount: float,
        quote_token_amount: float,
        slippage_pct: Optional[float] = None,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Quote the required token amounts for adding liquidity to an AMM pool
        """
        query_params = {
            "network": network,
            "poolAddress": pool_address,
            "baseTokenAmount": base_token_amount,
            "quoteTokenAmount": quote_token_amount,
        }
        if slippage_pct is not None:
            query_params["slippagePct"] = slippage_pct

        # Parse connector to get name and type
        connector_name, connector_type = connector.split("/", 1)
        path = f"connectors/{connector_name}/{connector_type}/quote-liquidity"

        return await self.api_request(
            "get",
            path,
            params=query_params,
            fail_silently=fail_silently,
        )

    async def clmm_quote_position(
        self,
        connector: str,
        network: str,
        pool_address: str,
        lower_price: float,
        upper_price: float,
        base_token_amount: Optional[float] = None,
        quote_token_amount: Optional[float] = None,
        slippage_pct: Optional[float] = None,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Quote the required token amounts for opening a CLMM position
        """
        query_params = {
            "network": network,
            "poolAddress": pool_address,
            "lowerPrice": lower_price,
            "upperPrice": upper_price,
        }
        if base_token_amount is not None:
            query_params["baseTokenAmount"] = base_token_amount
        if quote_token_amount is not None:
            query_params["quoteTokenAmount"] = quote_token_amount
        if slippage_pct is not None:
            query_params["slippagePct"] = slippage_pct

        # Parse connector to get name and type
        connector_name, connector_type = connector.split("/", 1)
        path = f"connectors/{connector_name}/{connector_type}/quote-position"

        return await self.api_request(
            "get",
            path,
            params=query_params,
            fail_silently=fail_silently,
        )

    async def amm_add_liquidity(
        self,
        connector: str,
        network: str,
        wallet_address: str,
        pool_address: str,
        base_token_amount: float,
        quote_token_amount: float,
        slippage_pct: Optional[float] = None,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Add liquidity to an AMM liquidity position
        """
        request_payload = {
            "network": network,
            "walletAddress": wallet_address,
            "poolAddress": pool_address,
            "baseTokenAmount": base_token_amount,
            "quoteTokenAmount": quote_token_amount,
        }
        if slippage_pct is not None:
            request_payload["slippagePct"] = slippage_pct

        # Parse connector to get name and type
        connector_name, connector_type = connector.split("/", 1)
        path = f"connectors/{connector_name}/{connector_type}/add-liquidity"

        return await self.api_request(
            "post",
            path,
            request_payload,
            fail_silently=fail_silently,
        )

    async def amm_remove_liquidity(
        self,
        connector: str,
        network: str,
        wallet_address: str,
        pool_address: str,
        percentage: float,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Closes an existing AMM liquidity position
        """
        request_payload = {
            "network": network,
            "walletAddress": wallet_address,
            "poolAddress": pool_address,
            "percentageToRemove": percentage,
        }

        # Parse connector to get name and type
        connector_name, connector_type = connector.split("/", 1)
        path = f"connectors/{connector_name}/{connector_type}/remove-liquidity"

        return await self.api_request(
            "post",
            path,
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
        """Remove a token from the gateway."""
        return await self.api_request(
            "delete",
            f"tokens/{address}",
            params={
                "chain": chain,
                "network": network
            }
        )

    # ============================================
    # Pool Methods
    # ============================================

    async def get_pool(
        self,
        trading_pair: str,
        connector: str,
        network: str,
        type: str = "amm"
    ) -> Dict[str, Any]:
        """
        Get pool information for a specific trading pair.

        :param trading_pair: Trading pair (e.g., "SOL-USDC")
        :param connector: Connector name (e.g., "raydium")
        :param network: Network name (e.g., "mainnet-beta")
        :param type: Pool type ("amm" or "clmm"), defaults to "amm"
        :return: Pool information including address
        """
        params = {
            "connector": connector,
            "network": network,
            "type": type
        }

        response = await self.api_request("get", f"pools/{trading_pair}", params=params)
        return response

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
        params = {
            "connector": connector,
            "network": network,
            **pool_data
        }
        return await self.api_request("post", "pools", params=params)

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
        return await self.api_request("delete", f"pools/{address}", params=params)

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
        Get chain and default network for a connector.

        :param connector: Connector name in format 'name/type' (e.g., 'uniswap/amm')
        :return: Tuple of (chain, network, error_message)
        """
        # Parse connector format
        connector_parts = connector.split('/')
        if len(connector_parts) != 2:
            return None, None, "Invalid connector format. Use format like 'uniswap/amm' or 'jupiter/router'"

        connector_name = connector_parts[0]

        # Get all connectors to find chain info
        try:
            connectors_resp = await self.get_connectors()
            if "error" in connectors_resp:
                return None, None, f"Error getting connectors: {connectors_resp['error']}"

            # Find the connector info
            connector_info = None
            for conn in connectors_resp.get("connectors", []):
                if conn.get("name") == connector_name:
                    connector_info = conn
                    break

            if not connector_info:
                return None, None, f"Connector '{connector_name}' not found"

            # Get chain from connector info
            chain = connector_info.get("chain")
            if not chain:
                return None, None, f"Could not determine chain for connector '{connector_name}'"

            # Get default network for the chain
            network = await self.get_default_network_for_chain(chain)
            if not network:
                return None, None, f"Could not get default network for chain '{chain}'"

            return chain, network, None

        except Exception as e:
            return None, None, f"Error getting connector info: {str(e)}"

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
        transaction_type: str = "swap"
    ) -> Dict[str, Any]:
        """
        Estimate transaction fee using gateway's estimate-gas endpoint.

        :param chain: Chain name (e.g., "ethereum", "solana")
        :param network: Network name
        :param transaction_type: Type of transaction ("swap" or "approve")
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

            return {
                "success": True,
                "fee_per_unit": fee_per_unit,
                "estimated_units": compute_units,
                "denomination": denomination,
                "fee_in_native": fee_in_native,
                "native_token": native_token
            }

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
