import asyncio
import json
import logging
import math
import ssl
import sys
from abc import ABC, abstractmethod
from functools import partial
from typing import Any, Callable, Dict, List, Literal, Optional

<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)
from requests.exceptions import ConnectionError
from substrateinterface import SubstrateInterface
from substrateinterface.exceptions import SubstrateRequestException
from websockets import connect as websockets_connect
<<<<<<< HEAD
=======
import websockets
from requests.exceptions import ConnectionError
from substrateinterface import SubstrateInterface
<<<<<<< HEAD
from substrateinterface.exceptions import ConfigurationError, SubstrateRequestException
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======
from substrateinterface.exceptions import SubstrateRequestException
>>>>>>> 52298288f (fix: make it actually connect to chainflip, and fetch balance)
=======
>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)

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
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
    async def run_in_thread(cls, func: Callable, *args, **kwargs):
        """
        Run a synchronous function in a seperate thread
=======
    async def verify_lp_api_url(cls, url:str):
=======
    async def verify_lp_api_url(cls, url: str):
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
        """
        We verify this lp api url by first trying a substrate instance
        with the url and then check if an rpc_method is supported by the instance
        instance. if no error, we return the instance, else we raise the error.
        """
        try:
            instance = SubstrateInterface(url=url)
            checker = await cls.run_in_thread(instance.supports_rpc_method, CONSTANTS.ASSET_BALANCE_METHOD)
            if not checker:
                raise ConfigurationError("RPC url is not Chainflip LP API URL")

        except ConnectionError as err:  # raise proper http error
            cls.logger().error(str(err))
            raise
        except ConfigurationError as err:
            cls.logger().error(str(err))
            raise
        except Exception as err:
            cls.logger().error(str(err), exc_info=True)
            raise
        return instance

    @classmethod
    async def run_in_thread(cls, func: Callable, *args, **kwargs):
        """
<<<<<<< HEAD
            Run a synchoronous function in a seperate thread
>>>>>>> 9979ea9b9 ((refactor) update code and tests)
=======
        Run a synchoronous function in a seperate thread
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======
    async def run_in_thread(cls, func: Callable, *args, **kwargs):
        """
        Run a synchronous function in a seperate thread
>>>>>>> 52298288f (fix: make it actually connect to chainflip, and fetch balance)
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
<<<<<<< HEAD
<<<<<<< HEAD
        self._lp_api_url = chainflip_lp_api_url
        self._throttler = throttler
        self._rpc_instance = None
        self._lp_api_instance = None
        self._chain_config = chain_config

    async def start(self):
<<<<<<< HEAD
        self.logger().info(f"Starting up! API URL: {self._lp_api_url} RPC URL: {self._rpc_url}")
<<<<<<< HEAD
<<<<<<< HEAD
        self._lp_api_instance = await self._start_instance(self._lp_api_url)
        self._rpc_instance = await self._start_instance(self._rpc_url)
=======
=======
>>>>>>> af09807ef ((refactor) remove unneccessary logs and make minor fixes)
        self._lp_api_instance = self._start_instance(self._lp_api_url)
        self._rpc_instance = self._start_instance(self._rpc_url)
>>>>>>> a23c2447c ((fix) fix invalid await method call)

    async def check_connection_status(self):
        response = await self._execute_rpc_request(CONSTANTS.SUPPORTED_ASSETS_METHOD)
        api_response = await self._execute_api_request(CONSTANTS.ASSET_BALANCE_METHOD)

        if not response["status"] or not api_response["status"]:
            self.logger().error("Could not connect with RPC or API server")

=======
        self._rpc_api_url = chainflip_lp_api_url
=======
        self._lp_api_url = chainflip_lp_api_url
>>>>>>> 52298288f (fix: make it actually connect to chainflip, and fetch balance)
        self._throttler = throttler
        self._rpc_instance = None
        self._lp_api_instance = None
        self._chain_config = chain_config

    async def start(self):
        self.logger().info("Starting up! API URL: " + self._lp_api_url + " RPC URL: " + self._rpc_url)
=======
>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)
        self._lp_api_instance = await self._start_instance(self._lp_api_url)
        self._rpc_instance = await self._start_instance(self._rpc_url)

    async def check_connection_status(self):
        self.logger().info("Checking connection status")
        response = await self._execute_rpc_request(CONSTANTS.SUPPORTED_ASSETS_METHOD)
        api_response = await self._execute_api_request(CONSTANTS.ASSET_BALANCE_METHOD)

        if not response["status"] or not api_response["status"]:
            self.logger().error("Could not connect with RPC or API server")
<<<<<<< HEAD
>>>>>>> 9979ea9b9 ((refactor) update code and tests)
        return response["status"] and api_response["status"]

    async def all_assets(self):
<<<<<<< HEAD
<<<<<<< HEAD
        self.logger().info("Fetching all_assets")
=======
>>>>>>> af09807ef ((refactor) remove unneccessary logs and make minor fixes)
        response = await self._execute_rpc_request(CONSTANTS.SUPPORTED_ASSETS_METHOD)

        if not response["status"]:
            return []

        return DataFormatter.format_all_assets_response(response["data"], chain_config=self._chain_config)

    async def all_markets(self):
        response = await self._execute_rpc_request(CONSTANTS.ACTIVE_POOLS_METHOD)

        if not response["status"]:
            return []

=======
=======

        return response["status"] and api_response["status"]

    async def all_assets(self):
        self.logger().info("Fetching all_assets")
>>>>>>> 52298288f (fix: make it actually connect to chainflip, and fetch balance)
        response = await self._execute_api_request(CONSTANTS.SUPPORTED_ASSETS_METHOD)

        if not response["status"]:
            return []

        return DataFormatter.format_all_assets_response(response["data"], chain_config=self._chain_config)

    async def all_markets(self):
        self.logger().info("Fetching all_markets")
        response = await self._execute_rpc_request(CONSTANTS.ACTIVE_POOLS_METHOD)

        if not response["status"]:
            return []
<<<<<<< HEAD
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======

>>>>>>> 52298288f (fix: make it actually connect to chainflip, and fetch balance)
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
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> 52298288f (fix: make it actually connect to chainflip, and fetch balance)
        self.logger().info("Fetching get_orderbook")
=======
>>>>>>> af09807ef ((refactor) remove unneccessary logs and make minor fixes)
        params = {"base_asset": base_asset, "quote_asset": quote_asset, "orders": orders}
        response = await self._execute_rpc_request(CONSTANTS.POOL_ORDERBOOK_METHOD, params)

<<<<<<< HEAD
=======
        params = {"base_asset": base_asset, "quote_asset": quote_asset, "orders": orders}
        response = await self._execute_rpc_request(CONSTANTS.POOL_ORDERBOOK_METHOD, params)
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
        if not response["status"]:
            return None
=======
        if not response["status"]:
            return []
>>>>>>> 52298288f (fix: make it actually connect to chainflip, and fetch balance)

        return DataFormatter.format_orderbook_response(response["data"], base_asset, quote_asset)

    async def get_open_orders(self, base_asset: Dict[str, str], quote_asset: Dict[str, str]):
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> 52298288f (fix: make it actually connect to chainflip, and fetch balance)
        self.logger().info("Fetching get_open_orders")
=======
>>>>>>> af09807ef ((refactor) remove unneccessary logs and make minor fixes)
        params = {"base_asset": base_asset, "quote_asset": quote_asset, "lp": self._lp_account_address}
        response = await self._execute_rpc_request(CONSTANTS.OPEN_ORDERS_METHOD, params)

<<<<<<< HEAD
=======
        params = {"base_asset": base_asset, "quote_asset": quote_asset, "lp": self._lp_account_address}
        response = await self._execute_rpc_request(CONSTANTS.OPEN_ORDERS_METHOD, params)
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
        if not response["status"]:
            return []
<<<<<<< HEAD
=======
        if not response["status"]:
            return []
>>>>>>> 52298288f (fix: make it actually connect to chainflip, and fetch balance)

        return DataFormatter.format_order_response(response["data"], base_asset, quote_asset)

<<<<<<< HEAD
=======
        return DataFormatter.format_order_response(response["data"])
>>>>>>> 9979ea9b9 ((refactor) update code and tests)
    async def get_all_balances(self):
        response = await self._execute_api_request(CONSTANTS.ASSET_BALANCE_METHOD)

=======
    async def get_all_balances(self):
        self.logger().info("Fetching get_all_balances")
        response = await self._execute_api_request(CONSTANTS.ASSET_BALANCE_METHOD)
<<<<<<< HEAD
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
        if not response["status"]:
            return []

        return DataFormatter.format_balance_response(response["data"])

    async def get_market_price(self, base_asset: Dict[str, str], quote_asset: Dict[str, str]):
<<<<<<< HEAD
<<<<<<< HEAD
        self.logger().info("Fetching get_market_price")
=======
>>>>>>> af09807ef ((refactor) remove unneccessary logs and make minor fixes)
        params = {"base_asset": base_asset, "quote_asset": quote_asset}
        response = await self._execute_rpc_request(CONSTANTS.MARKET_PRICE_V2_METHOD, params)

        if not response["status"]:
            self.logger().error(f"Error getting market price for {base_asset['asset']}-{quote_asset['asset']}")
            return None

=======
=======

        if not response["status"]:
            return []

        return DataFormatter.format_balance_response(response["data"])

    async def get_market_price(self, base_asset: Dict[str, str], quote_asset: Dict[str, str]):
        self.logger().info("Fetching get_market_price")
>>>>>>> 52298288f (fix: make it actually connect to chainflip, and fetch balance)
        params = {"base_asset": base_asset, "quote_asset": quote_asset}
        response = await self._execute_rpc_request(CONSTANTS.MARKET_PRICE_V2_METHOD, params)

        if not response["status"]:
            return DataFormatter.format_error_response(response["data"])
<<<<<<< HEAD
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======

>>>>>>> 52298288f (fix: make it actually connect to chainflip, and fetch balance)
        return DataFormatter.format_market_price(response["data"])

    async def place_limit_order(
        self,
        base_asset: Dict[str, str],
        quote_asset: Dict[str, str],
        order_id: str,
<<<<<<< HEAD
<<<<<<< HEAD
        order_price: float,
=======
        order_price: int,
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======
        order_price: float,
>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)
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
            "wait_for": "InBlock"
        }
        response = await self._execute_api_request(CONSTANTS.PLACE_LIMIT_ORDER_METHOD, params)
        if not response["status"]:
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)
=======
            self.logger().error("Could not place order")
>>>>>>> af09807ef ((refactor) remove unneccessary logs and make minor fixes)
            return False
        return DataFormatter.format_place_order_response(response["data"])

=======
            return DataFormatter.format_error_response(response["data"])
        return DataFormatter.format_place_order_response(response["data"])
<<<<<<< HEAD
>>>>>>> 9979ea9b9 ((refactor) update code and tests)
=======

>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
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
            "wait_for": "InBlock"
        }
        response = await self._execute_api_request(CONSTANTS.CANCEL_LIMIT_ORDER, params)
        return response["status"]

    async def get_account_order_fills(self):
        all_assets = await self.all_assets()
        if not all_assets:
            return []
<<<<<<< HEAD
<<<<<<< HEAD
        response = await self._execute_api_request(CONSTANTS.ORDER_FILLS_METHOD)
=======
        response = await self._execute_api_request(
            CONSTANTS.ORDER_FILLS_METHOD
        )
>>>>>>> 9979ea9b9 ((refactor) update code and tests)
=======
        response = await self._execute_api_request(CONSTANTS.ORDER_FILLS_METHOD)
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
        if not response["status"]:
            return []
        return DataFormatter.format_order_fills_response(response, self._lp_account_address, all_assets)

    async def listen_to_market_price_updates(self, events_handler: Callable, market_symbol: str):
        all_assets = await self.all_assets()
        if not all_assets:
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
            self.logger().error("Unexpected error getting assets from Chainflip LP API.")
=======
            self.logger().error(
                    f"Unexpected error getting assets from chainflip rpc."
                )
>>>>>>> 9979ea9b9 ((refactor) update code and tests)
=======
            self.logger().error("Unexpected error getting assets from chainflip rpc.")
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======
            self.logger().error("Unexpected error getting assets from Chainflip LP API.")
>>>>>>> 52298288f (fix: make it actually connect to chainflip, and fetch balance)
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
<<<<<<< HEAD
<<<<<<< HEAD
                    f"Unexpected error listening to Pool Price from Chainflip LP API. Error: {e}", exc_info=True
                )
                sys.exit()
<<<<<<< HEAD

    async def listen_to_order_fills(self, event_handler: Callable):
        # will run in a thread
        all_assets = await self.all_assets()
        if not all_assets:
            self.logger().error("Unexpected error getting assets from Chainflip LP API.")
            sys.exit()

        def handler(data):
            response = DataFormatter.format_order_fills_response(data, self._lp_account_address, all_assets)
=======
    async def listen_to_order_fills(self, event_handler:Callable):
=======
                    f"Unexpected error listening to Pool Price from chainflip rpc. Error: {e}", exc_info=True
=======
                    f"Unexpected error listening to Pool Price from Chainflip LP API. Error: {e}", exc_info=True
>>>>>>> 52298288f (fix: make it actually connect to chainflip, and fetch balance)
                )
                sys.exit()

    async def listen_to_order_fills(self, event_handler: Callable):
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
        # will run in a thread
        all_assets = await self.all_assets()
        if not all_assets:
            self.logger().error("Unexpected error getting assets from Chainflip LP API.")
            sys.exit()

        def handler(data):
<<<<<<< HEAD
            response = DataFormatter.format_order_fills_response(data, self._lp_account_address)
>>>>>>> 63271bb03 ((refactor) update and cleanup chainflip connector codes)
            event_handler(response)

        await self._subscribe_to_api_event(CONSTANTS.ORDER_FILLS_SUBSCRIPTION_METHOD, handler)
=======
            response = DataFormatter.format_order_fills_response(data, self._lp_account_address, all_assets)
            event_handler(response)

        await self._subscribe_to_api_event(CONSTANTS.ORDER_FILLS_SUBSCRIPTION_METHOD, handler)
<<<<<<< HEAD
    
            
>>>>>>> 9979ea9b9 ((refactor) update code and tests)
=======
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)

    def _start_instance(self, url):
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
        self.logger().info(f"Start instance {url}")
=======
        self.logger().debug(f"Start instance {url}")
>>>>>>> af09807ef ((refactor) remove unneccessary logs and make minor fixes)

        try:
            instance = SubstrateInterface(url=url, auto_discover=False)
=======
        self.logger().info("Start instance " + url)

        try:
            instance = SubstrateInterface(url=url, auto_discover = False)

>>>>>>> 52298288f (fix: make it actually connect to chainflip, and fetch balance)
=======
        self.logger().info(f"Start instance {url}")

        try:
            instance = SubstrateInterface(url=url, auto_discover=False)
>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)
        except ConnectionError as err:
            self.logger().error(str(err))
            raise err

        except Exception as err:
            self.logger().error(str(err))
            raise err

        return instance

    def _reinitialize_rpc_instance(self):
        self.logger().debug("Reinitializing RPC Instance")
        self._rpc_instance.close()
        self._rpc_instance = self._start_instance(self._rpc_url)

    def _reinitialize_api_instance(self):
<<<<<<< HEAD
        self.logger().info("Reinitializing LP API Instance")
<<<<<<< HEAD
<<<<<<< HEAD
=======
        self.logger().debug("Reinitializing LP API Instance")
>>>>>>> ffb9c2b3c ((fix) fix test failures and errors)
        self._lp_api_instance.close()
        self._lp_api_instance = self._start_instance(self._lp_api_url)
=======
        self._rpc_api_instance.close()
        self._rpc_api_instance = self._start_instance(self._rpc_api_url)
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======
        self._lp_api_instance.close()
        self._lp_api_instance = self._start_instance(self._lp_api_url)
>>>>>>> 52298288f (fix: make it actually connect to chainflip, and fetch balance)

    async def _execute_api_request(
        self, request_method: str, params: List | Dict = [], throttler_limit_id: str = CONSTANTS.GENERAL_LIMIT_ID
    ):
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
        self.logger().info(f"Making {request_method} API call")
=======
        self.logger().info("Making " + request_method + " API call")
>>>>>>> 52298288f (fix: make it actually connect to chainflip, and fetch balance)
=======
        self.logger().info(f"Making {request_method} API call")
>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)
=======
        self.logger().debug(f"Making {request_method} API call")
>>>>>>> ffb9c2b3c ((fix) fix test failures and errors)

        if not self._lp_api_instance:
            self._lp_api_instance = self._start_instance(self._lp_api_url)

<<<<<<< HEAD
        async with self._throttler.execute_task(throttler_limit_id):
            response_data = {"status": True, "data": {}}
            self.logger().debug("Calling " + request_method)
            while True:
                try:
                    response = await self.run_in_thread(
                        self._lp_api_instance.rpc_request, method=request_method, params=params
=======
        if not self._rpc_api_instance:
            self._rpc_api_instance = await self.verify_lp_api_url(self._rpc_api_url)
=======
>>>>>>> 52298288f (fix: make it actually connect to chainflip, and fetch balance)
        async with self._throttler.execute_task(throttler_limit_id):
            response_data = {"status": True, "data": {}}
            response = None  # for testing purposes

            while True:
                try:
                    self.logger().info("Calling " + request_method)
                    response = await self.run_in_thread(
<<<<<<< HEAD
                        self._rpc_api_instance.rpc_request, method=request_method, params=params
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======
                        self._lp_api_instance.rpc_request, method=request_method, params=params
>>>>>>> 52298288f (fix: make it actually connect to chainflip, and fetch balance)
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

            return response_data

    async def _execute_rpc_request(
        self, request_method: str, params: List | Dict = [], throttler_limit_id: str = CONSTANTS.GENERAL_LIMIT_ID
    ):
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
        self.logger().info(f"Making {request_method} RPC call")
=======
        self.logger().debug(f"Making {request_method} RPC call")
>>>>>>> ffb9c2b3c ((fix) fix test failures and errors)

        if not self._rpc_instance:
            self._rpc_instance = self._start_instance(self._rpc_url)
        response_data = {"status": True, "data": {}}
        async with self._throttler.execute_task(throttler_limit_id):
            while True:
                try:
<<<<<<< HEAD
<<<<<<< HEAD
                    self.logger().info("Calling " + request_method)
=======
=======
        self.logger().info("Making " + request_method + " RPC call")
=======
        self.logger().info(f"Making {request_method} RPC call")
>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)

>>>>>>> 52298288f (fix: make it actually connect to chainflip, and fetch balance)
        if not self._rpc_instance:
            self._rpc_instance = self._start_instance(self._rpc_url)
        response_data = {"status": True, "data": {}}
        response = None  # for testing purposes
        async with self._throttler.execute_task(throttler_limit_id):
            while True:
                try:
<<<<<<< HEAD
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======
                    self.logger().info("Calling " + request_method)
>>>>>>> 52298288f (fix: make it actually connect to chainflip, and fetch balance)
=======
                    self.logger().debug("Calling " + request_method)
>>>>>>> ffb9c2b3c ((fix) fix test failures and errors)
=======
>>>>>>> af09807ef ((refactor) remove unneccessary logs and make minor fixes)
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
<<<<<<< HEAD
<<<<<<< HEAD
        instance = SubstrateInterface(url=self._lp_api_url)
        while True:
            try:
                response = await self.run_in_thread(
                    instance.rpc_request, method_name, params
                )  # if an error occurs.. raise
<<<<<<< HEAD
=======
        instance = SubstrateInterface(url=self._rpc_api_url)
=======
        instance = SubstrateInterface(url=self._lp_api_url)
>>>>>>> 52298288f (fix: make it actually connect to chainflip, and fetch balance)
        while True:
            try:
                response = instance.rpc_request(method_name, params)  # if an error occurs.. raise
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======
>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)
                handler(response)
                asyncio.sleep(CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
                    f"Unexpected error listening to subscription event from Chainflip LP API. Error: {e}", exc_info=True
=======
                    f"Unexpected error listening to order fill update from Chainflip lp. Error: {e}", exc_info=True
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======
                    f"Unexpected error listening to order fill update from Chainflip LP. Error: {e}", exc_info=True
>>>>>>> 52298288f (fix: make it actually connect to chainflip, and fetch balance)
=======
                    f"Unexpected error listening to subscription event from Chainflip LP API. Error: {e}", exc_info=True
>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)
                )
                instance.close()
                sys.exit()

<<<<<<< HEAD
<<<<<<< HEAD
    async def _subscribe_to_rpc_event(
=======
    async def _subscribe_to_rpc_events(
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======
    async def _subscribe_to_rpc_event(
>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)
        self,
        method_name: str,
        handler: Callable,
        params: List = [],
    ):
        url = self._get_current_rpc_ws_url(self._domain)
<<<<<<< HEAD
<<<<<<< HEAD
        async with websockets_connect(url) as websocket:
=======
        async with websockets.connect(url) as websocket:
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======
        async with websockets_connect(url) as websocket:
>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)
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
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
                        f"Unexpected error listening to subscription event from Chainflip LP RPC. Error: {e}",
                        exc_info=True,
                    )
                    break

    def _calculate_tick(self, price: float, base_asset: Dict[str, str], quote_asset: Dict[str, str]):
=======
                        f"Unexpected error listening to order fill update from Chainflip lp. Error: {e}", exc_info=True
=======
                        f"Unexpected error listening to order fill update from Chainflip LP. Error: {e}", exc_info=True
>>>>>>> 52298288f (fix: make it actually connect to chainflip, and fetch balance)
                    )
                    break

    async def _calculate_tick(self, price: float, base_asset: Dict[str, str], quote_asset: Dict[str, str]):
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======
                        f"Unexpected error listening to subscription event from Chainflip LP RPC. Error: {e}",
                        exc_info=True,
                    )
                    break

    def _calculate_tick(self, price: float, base_asset: Dict[str, str], quote_asset: Dict[str, str]):
>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)
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
