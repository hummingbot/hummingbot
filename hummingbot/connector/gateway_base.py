import asyncio
import copy
import json
import logging
import ssl
import time
from decimal import Decimal
from typing import Dict, Any, List

import aiohttp
from hummingbot.connector.connector_base import ConnectorBase, global_config_map
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.network_iterator import NetworkStatus

from hummingbot.client.settings import GATEAWAY_CA_CERT_PATH, GATEAWAY_CLIENT_CERT_PATH, GATEAWAY_CLIENT_KEY_PATH
from hummingbot.connector.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.event.events import (
    OrderType,
    TradeType,
)
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL

s_logger = None
s_decimal_0 = Decimal("0")
s_decimal_NaN = Decimal("nan")
logging.basicConfig(level=METRICS_LOG_LEVEL)


class GatewayBase(ConnectorBase):
    """
    Defines basic functions common to connectors that interact with DEXes through Gateway.
    """

    API_CALL_TIMEOUT = 10.0
    POLL_INTERVAL = 1.0
    UPDATE_BALANCE_INTERVAL = 30.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(cls.__name__)
        return s_logger

    def __init__(self,
                 trading_pairs: List[str],
                 trading_required: bool = True
                 ):
        """
        :param trading_pairs: a list of trading pairs
        :param trading_required: Whether actual trading is needed. Useful for some functionalities or commands like the balance command
        """
        super().__init__()
        self._trading_pairs = trading_pairs
        self._tokens = set()
        for trading_pair in trading_pairs:
            self._tokens.update(set(trading_pair.split("-")))
        self._trading_required = trading_required
        self._ev_loop = asyncio.get_event_loop()
        self._shared_client = None
        self._last_poll_timestamp = 0.0
        self._last_balance_poll_timestamp = time.time()
        self._in_flight_orders = {}
        self._chain_info = {}
        self._status_polling_task = None
        self._init_task = None
        self._get_chain_info_task = None
        self._poll_notifier = None

    @property
    def name(self):
        """
        This should be overwritten to return the appropriate name of new connector when inherited.
        """
        return "GatewayServer"

    @property
    def network_base_path(self):
        raise NotImplementedError

    @property
    def base_path(self):
        raise NotImplementedError

    @property
    def private_key(self):
        raise NotImplementedError

    async def init(self):
        """
        Function to prepare the wallet, which was connected. For Ethereum this might include approving allowances,
        for Solana the initialization of token accounts. If finished, should set self.ready = True.
        """
        raise NotImplementedError

    @property
    def ready(self):
        raise NotImplementedError

    @property
    def amm_orders(self) -> List[GatewayInFlightOrder]:
        return [
            in_flight_order
            for in_flight_order in self._in_flight_orders.values() if
            in_flight_order.client_order_id.split("_")[0] != "approve"
        ]

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self.amm_orders
        ]

    async def get_chain_info(self):
        """
        Calls the base endpoint of the connector on Gateway to know basic info about chain being used.
        """
        try:
            resp = await self._api_request("get", f"{self.base_path}/")
            if bool(str(resp["success"])):
                self._chain_info = resp
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                "Error fetching chain info",
                exc_info=True,
                app_warning_msg=str(e)
            )

    def start_tracking_order(self,
                             order_id: str,
                             exchange_order_id: str = None,
                             trading_pair: str = "",
                             order_type: OrderType = OrderType.LIMIT,
                             trade_type: TradeType = TradeType.BUY,
                             price: Decimal = s_decimal_0,
                             amount: Decimal = s_decimal_0,
                             gas_price: Decimal = s_decimal_0):
        """
        Starts tracking an order by simply adding it into _in_flight_orders dictionary.
        """
        self._in_flight_orders[order_id] = GatewayInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount,
            gas_price=gas_price
        )

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order by simply removing it from _in_flight_orders dictionary.
        """
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    async def start_network(self):
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._init_task = safe_ensure_future(self.init())

    async def stop_network(self):
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._init_task is not None:
            self._init_task.cancel()
            self._init_task = None
        if self._get_chain_info_task is not None:
            self._get_chain_info_task.cancel()
            self._get_chain_info_task = None

    async def check_network(self) -> NetworkStatus:
        try:
            response = await self._api_request("get", "")
            if response.get('message', None) == 'ok' or response.get('status', None) == 'ok':
                pass
            else:
                raise Exception(f"Error connecting to Gateway API. Response is {response}.")
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock's tick (1 second by default).
        It checks if status polling task is due for execution.
        """
        if time.time() - self._last_poll_timestamp > self.POLL_INTERVAL:
            if self._poll_notifier is not None and not self._poll_notifier.is_set():
                self._poll_notifier.set()

    async def _update(self):
        """Async function to query all independent endpoints, like balances, approvals and order status."""
        raise NotImplementedError

    async def _status_polling_loop(self):
        await self._update_balances(on_interval=False)
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()
                await self._update()
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(str(e), exc_info=True)
                self.logger().network("Unexpected error while fetching account updates.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch balances from Gateway API.")

    async def _update_balances(self, on_interval=False):
        """
        Calls Gateway API to update total and available balances.
        """
        last_tick = self._last_balance_poll_timestamp
        current_tick = self.current_timestamp
        if not on_interval or (current_tick - last_tick) > self.UPDATE_BALANCE_INTERVAL:
            self._last_balance_poll_timestamp = current_tick
            local_asset_names = set(self._account_balances.keys())
            remote_asset_names = set()
            resp_json = await self._api_request("post", f"{self.network_base_path}/balances",
                                                {"tokenSymbols": list(self._tokens)})
            for token, bal in resp_json["balances"].items():
                self._account_available_balances[token] = Decimal(str(bal))
                self._account_balances[token] = Decimal(str(bal))
                remote_asset_names.add(token)

            asset_names_to_remove = local_asset_names.difference(remote_asset_names)
            for asset_name in asset_names_to_remove:
                del self._account_available_balances[asset_name]
                del self._account_balances[asset_name]

            self._in_flight_orders_snapshot = {k: copy.copy(v) for k, v in self._in_flight_orders.items()}
            self._in_flight_orders_snapshot_timestamp = self.current_timestamp

    async def _http_client(self) -> aiohttp.ClientSession:
        """
        :returns Shared client session instance
        """
        if self._shared_client is None:
            ssl_ctx = ssl.create_default_context(cafile=GATEAWAY_CA_CERT_PATH)
            ssl_ctx.load_cert_chain(GATEAWAY_CLIENT_CERT_PATH, GATEAWAY_CLIENT_KEY_PATH)
            conn = aiohttp.TCPConnector(ssl_context=ssl_ctx)
            self._shared_client = aiohttp.ClientSession(connector=conn)
        return self._shared_client

    async def _api_request(self,
                           method: str,
                           path_url: str,
                           params: Dict[str, Any] = {}) -> Dict[str, Any]:
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param path_url: The path url or the API end point
        :param params: A dictionary of required params for the end point
        :returns A response in json format.
        """
        base_url = f"https://{global_config_map['gateway_api_host'].value}:" \
                   f"{global_config_map['gateway_api_port'].value}"
        url = f"{base_url}/{path_url}"
        client = await self._http_client()
        if method == "get":
            if len(params) > 0:
                response = await client.get(url, params=params)
            else:
                response = await client.get(url)
        elif method == "post":
            params["privateKey"] = self.private_key
            response = await client.post(url, json=params)
        parsed_response = json.loads(await response.text())
        if response.status != 200:
            err_msg = ""
            if "error" in parsed_response:
                err_msg = f" Message: {parsed_response['error']}"
            elif "message" in parsed_response:
                err_msg = f" Message: {parsed_response['message']}"
            raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}.{err_msg}")
        if "error" in parsed_response:
            raise Exception(f"Error: {parsed_response['error']} {parsed_response['message']}")

        return parsed_response

    @property
    def in_flight_orders(self) -> Dict[str, GatewayInFlightOrder]:
        return self._in_flight_orders
