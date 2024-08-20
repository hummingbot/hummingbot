import asyncio
import json
import logging
import math
import ssl
import sys
from abc import ABC, abstractmethod
from functools import partial
from typing import Any, Callable, Dict, List, Literal, Optional

from requests.exceptions import ConnectionError
from substrateinterface import SubstrateInterface
from substrateinterface.exceptions import SubstrateRequestException
from websockets import connect as websockets_connect

from hummingbot.connector.exchange.chainflip_lp import chainflip_lp_constants as CONSTANTS
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_data_formatter import DataFormatter
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.logger import HummingbotLogger


class BaseRPCExecutor(ABC):

    @abstractmethod
    async def all_assets(self):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def all_markets(self):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def get_orderbook(self, base_asset: Dict[str, str], quote_asset: Dict[str, str], orders: int = 20):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def get_open_orders(
        self,
        base_asset: Dict[str, str],
        quote_asset: Dict[str, str],
    ):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def get_all_balances(self):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def place_limit_order(
        self, base_asset: str, quote_asset: str, order_id: str, side: Literal["buy", "sell"], sell_amount: int
    ):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def cancel_order(
        self,
        base_asset: str,
        quote_asset: str,
        order_id: str,
        side: Literal["buy", "sell"],
    ):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def listen_to_market_price_updates(self, events_handler: Callable, market_symbol: str):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def listen_to_order_fills(self, events_handler: Callable, market_symbol: str):
        raise NotImplementedError  # pragma: no cover


class RPCQueryExecutor(BaseRPCExecutor):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))

        return cls._logger

    @classmethod
    async def run_in_thread(cls, func: Callable, *args, **kwargs):
        """
        Run a synchronous function in a seperate thread
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    def __init__(
        self,
        throttler: AsyncThrottler,
        chainflip_lp_api_url: str,
        lp_account_address: str,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        chain_config=CONSTANTS.DEFAULT_CHAIN_CONFIG,
    ) -> None:
        super().__init__()
        self._lp_account_address = lp_account_address
        self._rpc_url = self._get_current_rpc_url(domain)
        self._domain = domain
        self._lp_api_url = chainflip_lp_api_url
        self._throttler = throttler
        self._rpc_instance = None
        self._lp_api_instance = None
        self._chain_config = chain_config

    async def start(self):
        self.logger().info(f"Starting up! API URL: {self._lp_api_url} RPC URL: {self._rpc_url}")
        self._lp_api_instance = await self._start_instance(self._lp_api_url)
        self._rpc_instance = await self._start_instance(self._rpc_url)

    async def check_connection_status(self):
        self.logger().info("Checking connection status")
        response = await self._execute_rpc_request(CONSTANTS.SUPPORTED_ASSETS_METHOD)
        api_response = await self._execute_api_request(CONSTANTS.ASSET_BALANCE_METHOD)

        if not response["status"] or not api_response["status"]:
            self.logger().error("Could not connect with RPC or API server")

        return response["status"] and api_response["status"]

    async def all_assets(self):
        self.logger().info("Fetching all_assets")
        response = await self._execute_api_request(CONSTANTS.SUPPORTED_ASSETS_METHOD)

        if not response["status"]:
            return []

        return DataFormatter.format_all_assets_response(response["data"], chain_config=self._chain_config)

    async def all_markets(self):
        self.logger().info("Fetching all_markets")
        response = await self._execute_rpc_request(CONSTANTS.ACTIVE_POOLS_METHOD)

        if not response["status"]:
            return []

        return DataFormatter.format_all_market_response(response["data"])

    async def get_orderbook(
        self, base_asset: Dict[str, str], quote_asset: Dict[str, str], orders: int = 20
    ) -> Dict[str, Any]:
        """
        base_asset:{
            "chain": str,
            "asset":str
        }
        """
        self.logger().info("Fetching get_orderbook")
        params = {"base_asset": base_asset, "quote_asset": quote_asset, "orders": orders}
        response = await self._execute_rpc_request(CONSTANTS.POOL_ORDERBOOK_METHOD, params)

        if not response["status"]:
            return None

        return DataFormatter.format_orderbook_response(response["data"])

    async def get_open_orders(self, base_asset: Dict[str, str], quote_asset: Dict[str, str]):
        self.logger().info("Fetching get_open_orders")
        params = {"base_asset": base_asset, "quote_asset": quote_asset, "lp": self._lp_account_address}
        response = await self._execute_rpc_request(CONSTANTS.OPEN_ORDERS_METHOD, params)

        if not response["status"]:
            return []

        return DataFormatter.format_order_response(response["data"])

    async def get_all_balances(self):
        self.logger().info("Fetching get_all_balances")
        response = await self._execute_api_request(CONSTANTS.ASSET_BALANCE_METHOD)

        if not response["status"]:
            return []

        return DataFormatter.format_balance_response(response["data"])

    async def get_market_price(self, base_asset: Dict[str, str], quote_asset: Dict[str, str]):
        self.logger().info("Fetching get_market_price")
        params = {"base_asset": base_asset, "quote_asset": quote_asset}
        response = await self._execute_rpc_request(CONSTANTS.MARKET_PRICE_V2_METHOD, params)

        if not response["status"]:
            self.logger().error(f"Error getting market price for {base_asset['asset']}-{quote_asset['asset']}")
            return None

        return DataFormatter.format_market_price(response["data"])

    async def place_limit_order(
        self,
        base_asset: Dict[str, str],
        quote_asset: Dict[str, str],
        order_id: str,
        order_price: float,
        side: Literal["buy"] | Literal["sell"],
        sell_amount: int,
    ):
        tick = self._calculate_tick(order_price, base_asset, quote_asset)
        if side == CONSTANTS.SIDE_BUY:
            amount = DataFormatter.format_amount(sell_amount, quote_asset)
        else:
            amount = DataFormatter.format_amount(sell_amount, base_asset)
        params = {
            "base_asset": base_asset["asset"],
            "quote_asset": quote_asset["asset"],
            "id": order_id,
            "side": side,
            "tick": tick,
            "sell_amount": amount,
        }
        response = await self._execute_api_request(CONSTANTS.PLACE_LIMIT_ORDER_METHOD, params)
        if not response["status"]:
            return False
        return DataFormatter.format_place_order_response(response["data"])

    async def cancel_order(
        self,
        base_asset: Dict[str, str],
        quote_asset: Dict[str, str],
        order_id: str,
        side: Literal["buy"] | Literal["sell"],
    ) -> bool:
        params = {
            "base_asset": base_asset["asset"],
            "quote_asset": quote_asset["asset"],
            "id": order_id,
            "side": side,
            "sell_amount": DataFormatter.format_amount(0, base_asset),
        }
        response = await self._execute_api_request(CONSTANTS.CANCEL_LIMIT_ORDER, params)
        return response["status"]

    async def get_account_order_fills(self):
        all_assets = await self.all_assets()
        if not all_assets:
            return []
        response = await self._execute_api_request(CONSTANTS.ORDER_FILLS_METHOD)
        if not response["status"]:
            return []
        return DataFormatter.format_order_fills_response(response, self._lp_account_address, all_assets)

    async def listen_to_market_price_updates(self, events_handler: Callable, market_symbol: str):
        all_assets = await self.all_assets()
        if not all_assets:
            self.logger().error("Unexpected error getting assets from Chainflip LP API.")
            sys.exit()
        while True:
            try:
                asset = DataFormatter.format_trading_pair(market_symbol, all_assets)
                prices = await self.get_market_price(asset["base_asset"], asset["quote_asset"])
                events_handler(prices, asset)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(
                    f"Unexpected error listening to Pool Price from Chainflip LP API. Error: {e}", exc_info=True
                )
                sys.exit()

    async def listen_to_order_fills(self, event_handler: Callable):
        # will run in a thread
        all_assets = await self.all_assets()
        if not all_assets:
            self.logger().error("Unexpected error getting assets from Chainflip LP API.")
            sys.exit()

        def handler(data):
            response = DataFormatter.format_order_fills_response(data, self._lp_account_address, all_assets)
            event_handler(response)

        await self._subscribe_to_api_event(CONSTANTS.ORDER_FILLS_SUBSCRIPTION_METHOD, handler)

    def _start_instance(self, url):
        self.logger().info(f"Start instance {url}")

        try:
            instance = SubstrateInterface(url=url, auto_discover=False)
        except ConnectionError as err:
            self.logger().error(str(err))
            raise err

        except Exception as err:
            self.logger().error(str(err))
            raise err

        return instance

    def _reinitialize_rpc_instance(self):
        self.logger().info("Reinitializing RPC Instance")
        self._rpc_instance.close()
        self._rpc_instance = self._start_instance(self._rpc_url)

    def _reinitialize_api_instance(self):
        self.logger().info("Reinitializing LP API Instance")
        self._lp_api_instance.close()
        self._lp_api_instance = self._start_instance(self._lp_api_url)

    async def _execute_api_request(
        self, request_method: str, params: List | Dict = [], throttler_limit_id: str = CONSTANTS.GENERAL_LIMIT_ID
    ):
        self.logger().info(f"Making {request_method} API call")

        if not self._lp_api_instance:
            self._lp_api_instance = self._start_instance(self._lp_api_url)

        async with self._throttler.execute_task(throttler_limit_id):
            response_data = {"status": True, "data": {}}
            response = None  # for testing purposes

            while True:
                try:
                    self.logger().info("Calling " + request_method)
                    response = await self.run_in_thread(
                        self._lp_api_instance.rpc_request, method=request_method, params=params
                    )
                    response_data["data"] = response
                    break

                except ssl.SSLEOFError:
                    self._reinitialize_api_instance()

                except SubstrateRequestException as err:
                    self.logger().error(err)
                    response_data["status"] = False
                    response_data["data"] = err.args[0]
                    break

                except Exception as err:
                    self.logger().error(err)
                    response_data["status"] = False
                    response_data["data"] = {"code": 0, "message": "An Error Occurred"}
                    break

            self.logger().info(request_method + " API call response:" + str(response_data["data"]))
            return response_data

    async def _execute_rpc_request(
        self, request_method: str, params: List | Dict = [], throttler_limit_id: str = CONSTANTS.GENERAL_LIMIT_ID
    ):
        self.logger().info(f"Making {request_method} RPC call")

        if not self._rpc_instance:
            self._rpc_instance = self._start_instance(self._rpc_url)
        response_data = {"status": True, "data": {}}
        response = None  # for testing purposes
        async with self._throttler.execute_task(throttler_limit_id):
            while True:
                try:
                    self.logger().info("Calling " + request_method)
                    response = await self.run_in_thread(
                        self._rpc_instance.rpc_request, method=request_method, params=params
                    )
                    response_data["data"] = response
                    break

                except ssl.SSLEOFError:
                    self._reinitialize_rpc_instance()

                except SubstrateRequestException as err:
                    self.logger().error(err)
                    response_data["status"] = False
                    response_data["data"] = err.args[0]
                    break

                except Exception as err:
                    self.logger().error(err)
                    response_data["status"] = False
                    response_data["data"] = {"code": 0, "message": "An Error Occurred"}
                    break
            return response_data

    async def _subscribe_to_api_event(self, method_name: str, handler: Callable, params=[]):
        instance = SubstrateInterface(url=self._lp_api_url)
        while True:
            try:
                response = await self.run_in_thread(
                    instance.rpc_request, method_name, params
                )  # if an error occurs.. raise
                handler(response)
                asyncio.sleep(CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(
                    f"Unexpected error listening to subscription event from Chainflip LP API. Error: {e}", exc_info=True
                )
                instance.close()
                sys.exit()

    async def _subscribe_to_rpc_event(
        self,
        method_name: str,
        handler: Callable,
        params: List = [],
    ):
        url = self._get_current_rpc_ws_url(self._domain)
        async with websockets_connect(url) as websocket:
            request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method_name, "params": params})
            await websocket.send(request)
            while True:
                try:
                    response = await websocket.recv()
                    data = json.loads(response)
                    handler(data)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.logger().error(
                        f"Unexpected error listening to subscription event from Chainflip LP RPC. Error: {e}",
                        exc_info=True,
                    )
                    break

    def _calculate_tick(self, price: float, base_asset: Dict[str, str], quote_asset: Dict[str, str]):
        """
        calculate ticks
        """
        base_precision = DataFormatter.format_asset_precision(base_asset)
        quote_precision = DataFormatter.format_asset_precision(quote_asset)
        full_price = (price * quote_precision) / base_precision
        log_price = math.log(full_price) / math.log(1.0001)
        bounded_price = max(CONSTANTS.LOWER_TICK_BOUND, min(log_price, CONSTANTS.UPPER_TICK_BOUND))
        tick_price = round(bounded_price)
        return tick_price

    def _get_current_rpc_url(self, domain: str):
        return CONSTANTS.REST_RPC_URLS[domain]

    def _get_current_rpc_ws_url(self, domain: str):
        return CONSTANTS.WS_RPC_URLS[domain]
