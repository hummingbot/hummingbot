import logging
from decimal import Decimal
from typing import (
    Dict,
    Any,
)
import json
import asyncio
import aiohttp
import socket

from hummingbot.logger import HummingbotLogger
ctce_logger = None


class AdminApi:
    """
    Wrapper of admin API
    """
    API_REQUEST_TIMEOUT = 30
    UPDATE_INTERVAL = 60    # 60 seconds

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global ctce_logger
        if ctce_logger is None:
            ctce_logger = logging.getLogger(__name__)
        return ctce_logger

    def __init__(self,
                 api_url: str,
                 admin_control_type: str,
                 order_amount: Decimal,
                 order_amount_delta: Decimal,
                 filled_order_delay: float,
                 filled_order_delay_delta: float):
        self._shared_client = None
        self._ev_loop = asyncio.get_event_loop()
        self._updated_timestamp = 0
        self._ipaddr = ""

        self._api_url = api_url
        self._admin_control_type = admin_control_type
        self._order_amount = order_amount
        self._order_amount_delta = order_amount_delta
        self._filled_order_delay = filled_order_delay
        self._filled_order_delay_delta = filled_order_delay_delta

    def _get_ipaddr(self):
        if self._ipaddr == "":
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                self._ipaddr = s.getsockname()[0]
                s.close()
            except Exception as e:
                self.logger().error(str(e), exc_info=True)
        return self._ipaddr

    async def _http_client(self) -> aiohttp.ClientSession:
        """
        :returns Shared client session instance
        """
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _api_request(self,
                           method: str,
                           path_url: str,
                           params: Dict[str, Any] = {}) -> Dict[str, Any]:
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param path_url: The path url or the API end point
        :param is_auth_required: Whether an authentication is required, when True the function will add encrypted
        signature to the request.
        :returns A response in json format.
        """
        url = f"{self._api_url}/{path_url}"
        client = await self._http_client()
        headers = {"Content-Type": "application/json"}

        if method == "get":
            response = await client.get(url, headers=headers, timeout=self.API_REQUEST_TIMEOUT)
        elif method == "post":
            post_json = json.dumps(params)
            response = await client.post(url, data=post_json, headers=headers, timeout=self.API_REQUEST_TIMEOUT)
        else:
            raise NotImplementedError

        try:
            parsed_response = json.loads(await response.text())
        except Exception as e:
            raise IOError(f"Error parsing data from {url}. Error: {str(e)}")

        if response.status != 200:
            raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. Message: {parsed_response}")
        return parsed_response

    def get_updated_params(self,
                           current_timestamp: int) -> Dict[str, Any]:
        """
        Calls to get updated parameters by admin API
        """
        if self._admin_control_type != "" and self.UPDATE_INTERVAL < (current_timestamp - self._updated_timestamp):
            self._updated_timestamp = current_timestamp
            asyncio.run_coroutine_threadsafe(self.update_params(), self._ev_loop)

        return {
            "order_amount": self._order_amount,
            "order_amount_delta": self._order_amount_delta,
            "filled_order_delay": self._filled_order_delay,
            "filled_order_delay_delta": self._filled_order_delay_delta,
        }

    async def update_params(self):
        """
        Calls create-order API end point to place an order, starts tracking the order and triggers order created event.
        """
        try:
            url = "bot_conf?bot_type=" + self._admin_control_type + "&ip=" + self._get_ipaddr()
            result = await self._api_request("get", url)
            data = result.get("data")
            if data is not None:
                amount_min_str = data.get("order_amount_min")
                if amount_min_str is not None and amount_min_str != "":
                    self._order_amount = Decimal(amount_min_str)

                amount_max_str = data.get("order_amount_max")
                if amount_max_str is not None and amount_max_str != "":
                    amount_max = Decimal(amount_max_str)
                    delta = amount_max - self._order_amount
                    if 0 <= float(delta):
                        self._order_amount_delta = delta

                time_min_str = data.get("time_elapsed_min")
                if time_min_str is not None and time_min_str != "":
                    self._filled_order_delay = float(time_min_str)

                time_max_str = data.get("time_elapsed_max")
                if time_max_str is not None and time_max_str != "":
                    time_max = float(time_max_str)
                    delta = time_max - self._filled_order_delay
                    if 0 <= delta:
                        self._filled_order_delay_delta = delta

        except Exception as e:
            self.logger().error(str(e), exc_info=True)
            self.logger().network("Unexpected error while fetching data from admin API.",
                                  exc_info=True,
                                  app_warning_msg="Could not fetch data from API.")
