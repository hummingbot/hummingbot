import logging
import re
import ssl
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import aiohttp
from aiohttp import ContentTypeError

from hummingbot.client.config.security import Security
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
        if GatewayHttpClient.__instance is None:
            self._base_url = f"https://{api_host}:{api_port}"
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
            cert_path = client_config_map.certs_path
            ssl_ctx = ssl.create_default_context(cafile=f"{cert_path}/ca_cert.pem")
            ssl_ctx.load_cert_chain(certfile=f"{cert_path}/client_cert.pem",
                                    keyfile=f"{cert_path}/client_key.pem",
                                    password=Security.secrets_manager.password.get_secret_value())
            conn = aiohttp.TCPConnector(ssl_context=ssl_ctx)
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

    async def update_config(self, config_path: str, config_value: Any) -> Dict[str, Any]:
        response = await self.api_request("post", "config/update", {
            "configPath": config_path,
            "configValue": config_value,
        })
        self.logger().info("Detected change to Gateway config - restarting Gateway...", exc_info=False)
        await self.post_restart()
        return response

    async def post_restart(self):
        await self.api_request("post", "restart", fail_silently=True)

    async def get_connectors(self, fail_silently: bool = False) -> Dict[str, Any]:
        return await self.api_request("get", "connectors", fail_silently=fail_silently)

    async def get_wallets(self, fail_silently: bool = False) -> List[Dict[str, Any]]:
        return await self.api_request("get", "wallet", fail_silently=fail_silently)

    async def add_wallet(
        self, chain: str, network: str, private_key: str, **kwargs
    ) -> Dict[str, Any]:
        request = {"chain": chain, "network": network, "privateKey": private_key}
        request.update(kwargs)
        return await self.api_request(method="post", path_url="wallet/add", params=request)

    async def get_configuration(self, chain: str = None, fail_silently: bool = False) -> Dict[str, Any]:
        params = {"chainOrConnector": chain} if chain is not None else {}
        return await self.api_request("get", "config", params=params, fail_silently=fail_silently)

    async def get_balances(
            self,
            chain: str,
            network: str,
            address: str,
            token_symbols: List[str],
            connector: str = None,
            fail_silently: bool = False,
    ) -> Dict[str, Any]:
        if isinstance(token_symbols, list):
            token_symbols = [x for x in token_symbols if isinstance(x, str) and x.strip() != '']
            request_params = {
                "network": network,
                "address": address,
                "tokenSymbols": token_symbols,
            }
            if connector is not None:
                request_params["connector"] = connector
            return await self.api_request(
                method="post",
                path_url=f"{chain}/balances",
                params=request_params,
                fail_silently=fail_silently,
            )
        else:
            return {}

    async def get_tokens(
            self,
            chain: str,
            network: str,
            fail_silently: bool = True
    ) -> Dict[str, Any]:
        return await self.api_request("get", f"{chain}/tokens", {
            "network": network
        }, fail_silently=fail_silently)

    async def get_network_status(
            self,
            chain: str = None,
            network: str = None,
            fail_silently: bool = False
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        req_data: Dict[str, str] = {}
        if chain is not None and network is not None:
            req_data["network"] = network
            return await self.api_request("get", f"{chain}/status", req_data, fail_silently=fail_silently)
        return await self.api_request("get", "network/status", req_data, fail_silently=fail_silently)  # Default endpoint when chain is None

    async def approve_token(
            self,
            chain: str,
            network: str,
            address: str,
            token: str,
            spender: str,
            nonce: Optional[int] = None,
            max_fee_per_gas: Optional[int] = None,
            max_priority_fee_per_gas: Optional[int] = None
    ) -> Dict[str, Any]:
        request_payload: Dict[str, Any] = {
            "network": network,
            "address": address,
            "token": token,
            "spender": spender
        }
        if nonce is not None:
            request_payload["nonce"] = nonce
        if max_fee_per_gas is not None:
            request_payload["maxFeePerGas"] = str(max_fee_per_gas)
        if max_priority_fee_per_gas is not None:
            request_payload["maxPriorityFeePerGas"] = str(max_priority_fee_per_gas)
        return await self.api_request(
            "post",
            "ethereum/approve",
            request_payload
        )

    async def get_allowances(
            self,
            chain: str,
            network: str,
            address: str,
            token_symbols: List[str],
            spender: str,
            fail_silently: bool = False
    ) -> Dict[str, Any]:
        return await self.api_request("post", "ethereum/allowances", {
            "network": network,
            "address": address,
            "tokenSymbols": token_symbols,
            "spender": spender
        }, fail_silently=fail_silently)

    async def get_transaction_status(
            self,
            chain: str,
            network: str,
            transaction_hash: str,
            connector: Optional[str] = None,
            address: Optional[str] = None,
            fail_silently: bool = False
    ) -> Dict[str, Any]:
        request = {
            "network": network,
            "txHash": transaction_hash
        }
        # if connector:
        #     request["connector"] = connector
        # if address:
        #     request["address"] = address
        return await self.api_request("post", f"{chain}/poll", request, fail_silently=fail_silently)

    async def wallet_sign(
        self,
        chain: str,
        network: str,
        address: str,
        message: str,
    ) -> Dict[str, Any]:
        request = {
            "chain": chain,
            "network": network,
            "address": address,
            "message": message,
        }
        return await self.api_request("get", "wallet/sign", request)

    async def get_evm_nonce(
            self,
            chain: str,
            network: str,
            address: str,
            fail_silently: bool = False
    ) -> Dict[str, Any]:
        return await self.api_request("post", "ethereum/nextNonce", {
            "network": network,
            "address": address
        }, fail_silently=fail_silently)

    async def cancel_evm_transaction(
            self,
            chain: str,
            network: str,
            address: str,
            nonce: int
    ) -> Dict[str, Any]:
        return await self.api_request("post", "ethereum/cancel", {
            "network": network,
            "address": address,
            "nonce": nonce
        })

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
            pool_id: Optional[str] = None
    ) -> Dict[str, Any]:
        if side not in [TradeType.BUY, TradeType.SELL]:
            raise ValueError("Only BUY and SELL prices are supported.")

        request_payload = {
            "chain": chain,
            "network": network,
            "connector": connector,
            "base": base_asset,
            "quote": quote_asset,
            "amount": f"{amount:.18f}",
            "side": side.name,
            "allowedSlippage": "0/1",  # hummingbot applies slippage itself
        }

        if pool_id not in ["", None]:
            request_payload["poolId"] = pool_id

        return await self.api_request(
            "post",
            f"{connector}/price",
            request_payload,
            fail_silently=fail_silently,
        )

    async def amm_trade(
        self,
        chain: str,
        network: str,
        connector: str,
        address: str,
        base_asset: str,
        quote_asset: str,
        side: TradeType,
        amount: Decimal,
        price: Decimal,
        nonce: Optional[int] = None,
        max_fee_per_gas: Optional[int] = None,
        max_priority_fee_per_gas: Optional[int] = None,
        pool_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        request_payload: Dict[str, Any] = {
            "chain": chain,
            "network": network,
            "connector": connector,
            "address": address,
            "base": base_asset,
            "quote": quote_asset,
            "side": side.name,
            "amount": f"{amount:.18f}",
            # "limitPrice": f"{price:.20f}",
            # "allowedSlippage": "0/1",  # hummingbot applies slippage itself
        }
        if pool_id not in ["", None]:
            request_payload["poolId"] = pool_id
        if nonce is not None:
            request_payload["nonce"] = int(nonce)
        if max_fee_per_gas is not None:
            request_payload["maxFeePerGas"] = str(max_fee_per_gas)
        if max_priority_fee_per_gas is not None:
            request_payload["maxPriorityFeePerGas"] = str(max_priority_fee_per_gas)
        return await self.api_request("post", f"{connector}/trade", request_payload)

    async def amm_estimate_gas(
            self,
            chain: str,
            network: str,
            connector: str,
    ) -> Dict[str, Any]:
        return await self.api_request("post", f"{connector}/estimateGas", {
            "chain": chain,
            "network": network,
            "connector": connector,
        })
