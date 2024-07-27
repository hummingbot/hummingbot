from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, Optional, List, Literal
import logging
import asyncio
from functools import partial
import sys
import math

from hummingbot.connector.exchange.chainflip_lp import chainflip_lp_constants as CONSTANTS
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_data_formatter import DataFormatter
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.logger import HummingbotLogger

from substrateinterface import SubstrateInterface
from substrateinterface.exceptions import SubstrateRequestException, ConfigurationError
from requests.exceptions import ConnectionError
import ssl



class BaseRPCExecutor(ABC):
    @abstractmethod
    async def all_assets(self):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def all_markets(self):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def get_orderbook(
        self, 
        base_asset: Dict[str,str],
        quote_asset: Dict[str,str],
        orders:int = 20    
    ):
        raise NotImplementedError  # pragma: no cover
    @abstractmethod
    async def get_open_orders(
        self, 
        base_asset: Dict[str,str],
        quote_asset: Dict[str,str],
    ):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def recent_trade(self, market_symbol: str) -> Dict[str, Any]:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def get_all_balances(self):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def get_order_fills(
        self, blockhash:str
    ) -> Dict[str, Any]:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def place_limit_order(
        self, 
        base_asset:str,
        quote_asset:str,
        order_id:str,
        side: Literal["buy","sell"],
        sell_amount: int
    ):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def cancel_order(
        self,
        base_asset:str,
        quote_asset:str,
        order_id:str,
        side: Literal["buy","sell"],
        
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
    def verify_lp_api_url(cls, url:str):
        """
        We verify this lp api url by first trying a substrate instance
        with the url and then check if an rpc_method is supported by the instance 
        instance. if no error, we return the url, else we raise the error.
        """
        try:
            instance = SubstrateInterface(url=url)
            checker = instance.supports_rpc_method(CONSTANTS.ASSET_BALANCE_METHOD)
            if not checker:
                raise ConfigurationError("RPC url is not Chainflip LP API URL")
            instance.close()
        except ConnectionError as err: # raise proper http error
            cls._logger.error(str(err))
            raise err
        except ConfigurationError as err:
            cls._logger.error(str(err))
            raise err
        return url
    @classmethod
    async def run_in_thread(cls,func: Callable, *args, **kwargs):
        """
            Run a synchoronous function in a seperate thread
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))
    def __init__(
            self,
            throttler: AsyncThrottler,
            chainflip_lp_api_url: str,
            lp_account_address: str,
            domain:str = CONSTANTS.DEFAULT_DOMAIN
            ) -> None:
        super().__init__()
        self._lp_account_address = lp_account_address
        self._rpc_url = self._get_current_rpc_url(domain)
        self._rpc_api_url = self.verify_lp_api_url(chainflip_lp_api_url)
        self._throttler = throttler
        self._rpc_instance = self._start_instance(self._rpc_api_url)
    async def check_connection_status(self):
        response = self._execute_rpc_request(
            CONSTANTS.SUPPORTED_ASSETS_METHOD
        )
        api_response = self._execute_api_request(
            CONSTANTS.ASSET_BALANCE_METHOD
        )
        return response["status"] and api_response["status"]
    async def all_assets(self):
        response = await self._execute_api_request(
            CONSTANTS.SUPPORTED_ASSETS_METHOD
        )
        if not response["status"]:
            return []
        return DataFormatter.format_all_assets_response(response["data"])
    async def all_market(self):
        response = await self._execute_rpc_request(
            CONSTANTS.ACTIVE_POOLS_METHOD
        )
        if not response["status"]:
            return []
        return DataFormatter.format_all_assets_response(response["data"])
    async def get_orderbook(
            self, 
            base_asset: Dict[str,str],
            quote_asset: Dict[str,str],
            orders:int = 20
    ) -> Dict[str, Any]:
        """
            base_asset:{
                "chain": str,
                "asset":str
            }
        """
        params = {
            "base_asset": base_asset,
            "quote_asset": quote_asset,
            "orders": orders
        }
        response = await self._execute_rpc_request(
            CONSTANTS.POOL_ORDERBOOK_METHOD,
            params
        )
        if not response["status"]:
            return []
        return DataFormatter.format_orderbook_response(response["data"])
    async def get_open_orders(self, base_asset: Dict[str, str], quote_asset: Dict[str, str]):
        params = {
            "base_asset": base_asset,
            "quote_asset": quote_asset,
            "lp": self._lp_account_address
        }
        response = await self._execute_rpc_request(
            CONSTANTS.OPEN_ORDERS_METHOD,
            params
        )
        if not response["status"]:
            return []
        return DataFormatter.format_orderbook_response(response["data"])
    async def get_all_balances(self):
        response = await self._execute_api_request(
            CONSTANTS.ASSET_BALANCE_METHOD
        )
        if not response["status"]:
            return []
        return DataFormatter.format_balance_response(response["data"])
    async def get_market_price(
            self, base_asset:Dict[str, str],
            quote_asset:Dict[str,str]):
        params = {
            "base_asset": base_asset,
            "quote_asset": quote_asset
        }
        response = await self._execute_rpc_request(
            CONSTANTS.MARKET_PRICE_V2_METHOD,
            params
        )
        if not response["status"]:
            return DataFormatter.format_error_response(response["data"])
        return  DataFormatter.format_market_price(response["data"])
    async def place_limit_order(
            self, 
            base_asset: Dict[str, str], 
            quote_asset: Dict[str,str], 
            order_id: str,
            order_price: int,
            side: Literal['buy'] | Literal['sell'], sell_amount: int):
        tick = self._calculate_tick(
            order_price, base_asset, quote_asset
        )
        if side == CONSTANTS.SIDE_BUY:
            amount = DataFormatter.format_amount(sell_amount, quote_asset)
        else:
            amount = DataFormatter.format_amount(sell_amount, base_asset)
        params = {
            "base_asset": base_asset["asset"],
            "quote_asset": quote_asset["asset"],
            "id": order_id,
            "side": side,
            "tick":tick,
            "sell_amount": amount
        }
        response = await self._execute_api_request(
            CONSTANTS.PLACE_LIMIT_ORDER_METHOD,
            params
        )
        if not response["status"]:
            return DataFormatter.format_error_response(response["data"])
        return DataFormatter.format_order_response(response["data"])
    async def cancel_order(
            self, base_asset: Dict[str,str], quote_asset: Dict[str,str], 
            order_id: str, side: Literal['buy'] | Literal['sell']) -> bool:
        params = {
            "base_asset": base_asset["asset"],
            "quote_asset": quote_asset["asset"],
            "id": order_id,
            "side": side,
            "sell_amount": DataFormatter.format_amount(0, base_asset)
        }
        response = await self._execute_api_request(
            CONSTANTS.CANCEL_LIMIT_ORDER,
            params
        )
        return response["status"]

    async def listen_to_market_price_updates(self, events_handler: Callable, market_symbol: str):
        all_assets = await self.all_assets()
        if not all_assets:
            self.logger().error(
                    f"Unexpected error getting assets from chainflip rpc. Error: {e}",
                    exc_info=True
                )
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
                    f"Unexpected error listening to Pool Price from chainflip rpc. Error: {e}",
                    exc_info=True
                )
                sys.exit()
    async def listen_to_order_fills(self, event_handler:Callable):
        # will be run in a thread
        while True:
            try:
                response = self._subscribe_to_api_event(CONSTANTS.FILLED_ORDER_METHOD)
                formatted_response =  DataFormatter.format_order_fills_response(response)
                event_handler(formatted_response)
                asyncio.sleep(CONSTANTS.LISTENER_TIME_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(
                    f"Unexpected error listening to order fill update from Chainflip lp. Error: {e}",
                    exc_info=True
                )
                sys.exit()

    def _start_instance(self, url):
        try:
            instance = SubstrateInterface(url=url)
            instance.session
        except ConnectionError as err:
            self.logger().error(
                str(err)
            )
            raise err
        except Exception as err:
            self.logger().error(
                str(err)
            )
            raise err
        return instance
    def _reinitialize_rpc_instance(self):
        self.logger().info("Reinitializing LP RPC Instance")
        self._rpc_instance.close()
        self._rpc_instance = self._start_instance(self._rpc_url)
    def _reinitialize_api_instance(self):
        self.logger().info("Reinitializing LP API Instance")
        self._rpc_api_instance.close()
        self._rpc_api_instance = self._start_instance(self._rpc_api_url)
    async def _execute_api_request(
            self, 
            request_method: str, 
            params: List|Dict = [],
            throttler_limit_id: str = CONSTANTS.GENERAL_LIMIT_ID
    ):
        async with self._throttler.execute_task(throttler_limit_id):
            response_data = {
                "status": True,
                "data":{}
            } 
            while True:
                try:
                    response = await self.run_in_thread(self._rpc_api_instance.rpc_request,
                        method = request_method, 
                        params = params
                    )
                    response_data["data"] = response
                    break
                except ssl.SSLEOFError:
                    self._reinitialize_api_instance()
                except SubstrateRequestException as err:
                    self.logger().error(
                        err
                    )
                    response_data["status"] = False
                    response_data["data"] = err.args[0]
                    break
                except Exception as err:
                    self.logger().error(
                        err
                    )
                    response_data["status"] = False
                    response_data["data"] = {
                        "code": 0,
                        "message":"An Error Occurred"
                    }
                    break
            return response_data
    async def _execute_rpc_request(
            self, 
            request_method: str, 
            params: List|Dict = [],
            throttler_limit_id: str = CONSTANTS.GENERAL_LIMIT_ID
    ):
        async with self._throttler.execute_task(throttler_limit_id):
            response_data = {
                "status": True,
                "data":{}
            } 
            while True:
                try:
                    response = await self.run_in_thread(self._rpc_instance.rpc_request,
                        method = request_method, 
                        params = params
                    )
                    response_data["data"] = response
                    break
                except ssl.SSLEOFError:
                    self._reinitialize_rpc_instance()
                except SubstrateRequestException as err:
                    self.logger().error(
                        err
                    )
                    response_data["status"] = False
                    response_data["data"] = err.args[0]
                    break
                except Exception as err:
                    self.logger().error(
                        err
                    )
                    response_data["status"] = False
                    response_data["data"] = {
                        "code": 0,
                        "message":"An Error Occurred"
                    }
                    break
            return response_data
    
                

    async def _subscribe_to_api_event(self, method_name, params = []):
        instance = SubstrateInterface(url = self._rpc_api_url)
        response = instance.rpc_request(method_name, params) # if an error occurs.. raise
        instance.close()
        return response

    async def _calculate_tick(self,price:float, base_asset:Dict[str,str], quote_asset:Dict[str,str]):
        """
        calculate ticks
        """
        base_precision = DataFormatter.format_asset_precision(base_asset)
        quote_precision = DataFormatter.format_asset_precision(quote_asset)
        full_price = (price * quote_precision)/base_precision
        log_price = math.log(full_price)/ math.log(1.0001)
        bounded_price = max(
            CONSTANTS.LOWER_TICK_BOUND,
            min(log_price,CONSTANTS.UPPER_TICK_BOUND)
        )
        tick_price = round(bounded_price)
        return tick_price
    
    def _get_current_rpc_url(self, domain:str):
        return CONSTANTS.REST_RPC_URLS[domain]
    def _get_current_rpc_ws_url(self, domain:str):
        return CONSTANTS.WS_RPC_URLS[domain]

    
    
