import aiohttp
import logging
import ssl

from decimal import Decimal
from enum import Enum
from typing import Optional, Any, Dict, List, Union

from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.config.security import Security
from hummingbot.core.event.events import TradeType
from hummingbot.core.gateway import (
    detect_existing_gateway_container,
    get_gateway_paths,
    restart_gateway
)
from hummingbot.logger import HummingbotLogger


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
    UnknownError = 1099


class GatewayHttpClient:
    """
    An HTTP client for making requests to the gateway API.
    """

    _ghc_logger: Optional[HummingbotLogger] = None
    _shared_client: Optional[aiohttp.ClientSession] = None
    _base_url: str

    __instance = None

    @staticmethod
    def get_instance() -> "GatewayHttpClient":
        if GatewayHttpClient.__instance is None:
            GatewayHttpClient()
        return GatewayHttpClient.__instance

    def __init__(self):
        if GatewayHttpClient.__instance is None:
            self._base_url = f"https://{global_config_map['gateway_api_host'].value}:" \
                             f"{global_config_map['gateway_api_port'].value}"
        GatewayHttpClient.__instance = self

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._ghc_logger is None:
            cls._ghc_logger = logging.getLogger(__name__)
        return cls._ghc_logger

    @classmethod
    def _http_client(cls, re_init: bool = False) -> aiohttp.ClientSession:
        """
        :returns Shared client session instance
        """
        if cls._shared_client is None or re_init:
            cert_path = get_gateway_paths().local_certs_path.as_posix()
            ssl_ctx = ssl.create_default_context(cafile=f"{cert_path}/ca_cert.pem")
            ssl_ctx.load_cert_chain(certfile=f"{cert_path}/client_cert.pem",
                                    keyfile=f"{cert_path}/client_key.pem",
                                    password=Security.password)
            conn = aiohttp.TCPConnector(ssl_context=ssl_ctx)
            cls._shared_client = aiohttp.ClientSession(connector=conn)
        return cls._shared_client

    @classmethod
    def reload_certs(cls):
        """
        Re-initializes the aiohttp.ClientSession. This should be called whenever there is any updates to the
        Certificates used to secure a HTTPS connection to the Gateway service.
        """
        cls._http_client(re_init=True)

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
        error_code: Optional[int] = resp.get("errorCode")
        if error_code is not None:
            if error_code == GatewayError.Network.value:
                self.logger().info("Gateway had a network error. Make sure it is still able to communicate with the node.")
            elif error_code == GatewayError.RateLimit.value:
                self.logger().info("Gateway was unable to communicate with the node because of rate limiting.")
            elif error_code == GatewayError.OutOfGas.value:
                self.logger().info("There was an out of gas error. Adjust the gas limit in the gateway config.")
            elif error_code == GatewayError.TransactionGasPriceTooLow.value:
                self.logger().info("The gas price provided by gateway was too low to create a blockchain operation. Consider increasing the gas price.")
            elif error_code == GatewayError.LoadWallet.value:
                self.logger().info("Gateway failed to load your wallet. Try running 'gateway connect' with the correct wallet settings.")
            elif error_code == GatewayError.TokenNotSupported.value:
                self.logger().info("Gateway tried to use an unsupported token.")
            elif error_code == GatewayError.TradeFailed.value:
                self.logger().info("The trade on gateway has failed.")
            elif error_code == GatewayError.ServiceUnitialized.value:
                self.logger().info("Some values was uninitialized. Please contact dev@hummingbot.io ")
            elif error_code == GatewayError.SwapPriceExceedsLimitPrice.value:
                self.logger().info("The swap price is greater than your limit buy price. The market may be too volatile or your slippage rate is too low. Try adjusting the strategy's allowed slippage rate.")
            elif error_code == GatewayError.SwapPriceLowerThanLimitPrice.value:
                self.logger().info("The swap price is lower than your limit sell price. The market may be too volatile or your slippage rate is too low. Try adjusting the strategy's allowed slippage rate.")
            elif error_code == GatewayError.UnknownChainError.value:
                self.logger().info("An unknown chain error has occurred on gateway. Make sure your gateway settings are correct.")
            elif error_code == GatewayError.UnknownError.value:
                self.logger().info("An unknown error has occurred on gateway. Please send your logs to dev@hummingbot.io")

    async def api_request(
            self,
            method: str,
            path_url: str,
            params: Dict[str, Any] = {},
            fail_silently: bool = False
    ) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param path_url: The path url or the API end point
        :param params: A dictionary of required params for the end point
        :param fail_silently: used to determine if errors will be raise or silently ignored
        :returns A response in json format.
        """
        url = f"{self.base_url}/{path_url}"
        client = self._http_client()

        parsed_response = {}
        try:
            if method == "get":
                if len(params) > 0:
                    response = await client.get(url, params=params)
                else:
                    response = await client.get(url)
            elif method == "post":
                response = await client.post(url, json=params)
            else:
                raise ValueError(f"Unsupported request method {method}")
            parsed_response = await response.json()
            if response.status != 200 and not fail_silently:
                self.log_error_codes(parsed_response)

                if "error" in parsed_response:
                    raise ValueError(f"Error on {method.upper()} {url} Error: {parsed_response['error']}")
                else:
                    raise ValueError(f"Error on {method.upper()} {url} Error: {parsed_response}")
        except Exception as e:
            if not fail_silently:
                self.logger().error(e)
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

        # temporary code until #25625 is implemented (delete afterwards)
        # if the user had a gateway in a container, restart it
        # otherwise if they manually run a gateway, they need to restart it themselves
        container_info: Optional[Dict[str, Any]] = await detect_existing_gateway_container()
        if container_info is not None:
            await restart_gateway()

        return response

    async def get_connectors(self, fail_silently: bool = False) -> Dict[str, Any]:
        return await self.api_request("get", "connectors", fail_silently=fail_silently)

    async def get_wallets(self, fail_silently: bool = False) -> List[Dict[str, Any]]:
        return await self.api_request("get", "wallet", fail_silently=fail_silently)

    async def add_wallet(self, chain: str, network: str, private_key: str) -> Dict[str, Any]:
        return await self.api_request(
            "post",
            "wallet/add",
            {"chain": chain, "network": network, "privateKey": private_key}
        )

    async def get_configuration(self, fail_silently: bool = False) -> Dict[str, Any]:
        return await self.api_request("get", "network/config", fail_silently=fail_silently)

    async def get_balances(
            self,
            chain: str,
            network: str,
            address: str,
            token_symbols: List[str],
            fail_silently: bool = False
    ) -> Dict[str, Any]:
        return await self.api_request("post", "network/balances", {
            "chain": chain,
            "network": network,
            "address": address,
            "tokenSymbols": token_symbols,
        }, fail_silently=fail_silently)

    async def get_tokens(
            self,
            chain: str,
            network: str,
            fail_silently: bool = True
    ) -> Dict[str, Any]:
        return await self.api_request("get", "network/tokens", {
            "chain": chain,
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
            req_data["chain"] = chain
            req_data["network"] = network
        return await self.api_request("get", "network/status", req_data, fail_silently=fail_silently)

    async def approve_token(
            self,
            chain: str,
            network: str,
            address: str,
            token: str,
            spender: str,
            nonce: int,
            max_fee_per_gas: Optional[int] = None,
            max_priority_fee_per_gas: Optional[int] = None
    ) -> Dict[str, Any]:
        request_payload: Dict[str, Any] = {
            "chain": chain,
            "network": network,
            "address": address,
            "token": token,
            "spender": spender,
            "nonce": nonce
        }
        if max_fee_per_gas is not None:
            request_payload["maxFeePerGas"] = str(max_fee_per_gas)
        if max_priority_fee_per_gas is not None:
            request_payload["maxPriorityFeePerGas"] = str(max_priority_fee_per_gas)
        return await self.api_request(
            "post",
            "evm/approve",
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
        return await self.api_request("post", "evm/allowances", {
            "chain": chain,
            "network": network,
            "address": address,
            "tokenSymbols": token_symbols,
            "spender": spender
        }, fail_silently=fail_silently)

    async def get_price(
            self,
            chain: str,
            network: str,
            connector: str,
            base_asset: str,
            quote_asset: str,
            amount: Decimal,
            side: TradeType,
            fail_silently: bool = False
    ) -> Dict[str, Any]:
        if side not in [TradeType.BUY, TradeType.SELL]:
            raise ValueError("Only BUY and SELL prices are supported.")

        # XXX(martin_kou): The amount is always output with 18 decimal places.
        return await self.api_request("post", "amm/price", {
            "chain": chain,
            "network": network,
            "connector": connector,
            "base": base_asset,
            "quote": quote_asset,
            "amount": f"{amount:.18f}",
            "side": side.name
        }, fail_silently=fail_silently)

    async def get_transaction_status(
            self,
            chain: str,
            network: str,
            transaction_hash: str,
            fail_silently: bool = False
    ) -> Dict[str, Any]:
        return await self.api_request("post", "network/poll", {
            "chain": chain,
            "network": network,
            "txHash": transaction_hash
        }, fail_silently=fail_silently)

    async def get_evm_nonce(
            self,
            chain: str,
            network: str,
            address: str,
            fail_silently: bool = False
    ) -> Dict[str, Any]:
        return await self.api_request("post", "evm/nonce", {
            "chain": chain,
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
        return await self.api_request("post", "evm/cancel", {
            "chain": chain,
            "network": network,
            "address": address,
            "nonce": nonce
        })

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
            nonce: int,
            max_fee_per_gas: Optional[int] = None,
            max_priority_fee_per_gas: Optional[int] = None
    ) -> Dict[str, Any]:
        # XXX(martin_kou): The amount is always output with 18 decimal places.
        request_payload: Dict[str, Any] = {
            "chain": chain,
            "network": network,
            "connector": connector,
            "address": address,
            "base": base_asset,
            "quote": quote_asset,
            "side": side.name,
            "amount": f"{amount:.18f}",
            "limitPrice": str(price),
            "nonce": nonce
        }
        if max_fee_per_gas is not None:
            request_payload["maxFeePerGas"] = str(max_fee_per_gas)
        if max_priority_fee_per_gas is not None:
            request_payload["maxPriorityFeePerGas"] = str(max_priority_fee_per_gas)
        return await self.api_request("post", "amm/trade", request_payload)

    async def amm_estimate_gas(
            self,
            chain: str,
            network: str,
            connector: str,
    ) -> Dict[str, Any]:
        return await self.api_request("post", "amm/estimateGas", {
            "chain": chain,
            "network": network,
            "connector": connector,
        })
