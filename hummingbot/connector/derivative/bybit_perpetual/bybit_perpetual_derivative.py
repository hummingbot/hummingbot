import aiohttp
import asyncio
import logging
import ujson

import hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_utils as bybit_utils
import hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_constants as CONSTANTS

from decimal import Decimal
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_auth import BybitPerpetualAuth
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_api_order_book_data_source import BybitPerpetualAPIOrderBookDataSource
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.perpetual_trading import PerpetualTrading
from hummingbot.core.event.events import (
    FundingInfo,
    PositionMode,
)
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger


bbpd_logger = None


class BybitPerpetualDerivative(ExchangeBase, PerpetualTrading):

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global bbpd_logger
        if bbpd_logger is None:
            bbpd_logger = logging.getLogger(__name__)
        return bbpd_logger

    def __init__(self,
                 bybit_perpetual_api_key: str = None,
                 bybit_perpetual_secret_key: str = None,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: Optional[str] = None):
        self._auth: BybitPerpetualAuth = BybitPerpetualAuth(api_key=bybit_perpetual_api_key,
                                                            secret_key=bybit_perpetual_secret_key)
        self._trading_pairs = trading_pairs
        self._trading_required = trading_required
        self._domain = domain
        self._shared_client = None

        # Tasks
        self._funding_info_polling_task = None
        self._funding_fee_polling_task = None

    async def _aiohttp_client(self) -> aiohttp.ClientSession:
        """
        :returns Shared aiohttp Client session
        """
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY, PositionMode.HEDGE]

    async def start_network(self):
        self._funding_info_polling_task = safe_ensure_future(self._funding_info_polling_loop())
        if self._trading_required:
            self._user_funding_fee_polling_task = safe_ensure_future(self._user_funding_fee_polling_loop())

    async def stop_network(self):
        if self._funding_info_polling_task is not None:
            self._funding_info_polling_task.cancel()
            self._funding_info_polling_task = None
        if self._user_funding_fee_polling_task is not None:
            self._user_funding_fee_polling_task.cancel()
            self._user_funding_fee_polling_task = None

    async def _api_request(self,
                           method: str,
                           path_url: str,
                           params: Optional[Dict[str, Any]] = None,
                           body: Optional[Dict[str, Any]] = None,
                           is_auth_required: bool = False,
                           ):
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param path_url: The path url or the API end point
        :param params: The query parameters of the API request
        :param body: The body parameters of the API request
        :param is_auth_required: Whether an authentication is required, when True the function will add encrypted
        signature to the request.
        :returns A response in json format.
        """
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self._domain)
        client = await self._aiohttp_client()
        try:
            if method == "GET":
                if is_auth_required:
                    params = self._auth.extend_params_with_authentication_info(params=params)
                response = await client.get(url=url,
                                            headers=self._auth.get_headers(),
                                            params=params,
                                            )
            elif method == "POST":
                if is_auth_required:
                    params = self._auth.extend_params_with_authentication_info(params=body)
                response = await client.post(url=url,
                                             headers=self._auth.get_headers(),
                                             data=ujson.dumps(params)
                                             )
            else:
                raise NotImplementedError(f"{method} HTTP Method not implemented. ")

            parsed_response: Dict[str, Any] = await response.json()

        except Exception as e:
            self.logger().error(f"Error submitting {path_url} request. Error: {e}",
                                exc_info=True)

        if response.status != 200 or (isinstance(parsed_response, dict) and not parsed_response.get("result", True)):
            self.logger().error(f"Error fetching data from {url}. HTTP status is {response.status}. "
                                f"Message: {parsed_response} "
                                f"Params: {params} "
                                f"Data: {body}")
            raise Exception(f"Error fetching data from {url}. HTTP status is {response.status}. "
                            f"Message: {parsed_response} "
                            f"Params: {params} "
                            f"Data: {body}")
        return parsed_response

    async def _funding_info_polling_loop(self):
        """
        Retrieves funding information periodically. Tends to only update every set interval(i.e. 8hrs).
        Updates _funding_info variable.
        """
        while True:
            try:
                # TODO: Confirm the appropriate time interval
                for trading_pair in self._trading_pairs:
                    if trading_pair not in BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map:
                        self.logger().error(f"Trading pair {trading_pair} not supported.")
                        raise ValueError(f"Trading pair {trading_pair} not supported.")
                    params = {
                        "symbol": BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map[trading_pair]
                    }
                    resp = await self._api_request(method="GET",
                                                   path_url=CONSTANTS.LATEST_SYMBOL_INFORMATION_ENDPOINT,
                                                   params=params)

                    self._funding_info[trading_pair] = FundingInfo(
                        trading_pair=trading_pair,
                        index_price=Decimal(str(resp["index_price"])),
                        mark_price=Decimal(str(resp["mark_price"])),
                        next_funding_utc_timestamp=resp["next_funding_time"],
                        rate=Decimal(str(resp["funding_rate"]))  # TODO: Confirm whether to use funding_rate or predicted_funding_rate
                    )

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error updating funding info. Error: {e}. Retrying in 10 seconds... ",
                                    exc_info=True)

    async def _user_funding_fee_polling_loop(self):
        """
        Retrieve User Funding Fee every Funding Time(every 8hrs). Trigger FundingPaymentCompleted event as required.
        """
        pass
