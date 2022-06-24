import asyncio
import copy
import itertools
import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, cast

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.network_iterator import NetworkStatus

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL

ZERO = Decimal("0")
NaN = Decimal("nan")


class GatewayBase(ConnectorBase):
    """
    Defines basic functions common to connectors that interact with DEXes through the Gateway.
    """

    API_CALL_TIMEOUT = 10.0
    POLL_INTERVAL = 1.0
    UPDATE_BALANCE_INTERVAL = 30.0

    _logger: HummingbotLogger

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            logging.basicConfig(level=METRICS_LOG_LEVEL)
            cls._logger = cast(HummingbotLogger, logging.getLogger(cls.__name__))

        return cls._logger

    def __init__(
        self,
        chain: str,
        network: str,
        connector: str,
        wallet_address: str,
        trading_pairs: List[str],
        is_trading_required: bool = True
    ):
        """
        :param trading_pairs: a list of trading pairs
        :param is_trading_required: Whether actual trading is needed. Useful for some functionalities or commands like the balance command
        """
        super().__init__()

        self._chain = chain
        self._network = network
        self._connector = connector
        self._address = wallet_address
        self._trading_pairs = trading_pairs
        self._is_trading_required = is_trading_required

        self._tokens = set()
        [self._tokens.update(set(trading_pair.split("-"))) for trading_pair in self._trading_pairs]
        self._ev_loop = asyncio.get_event_loop()
        self._shared_client = None
        self._last_poll_timestamp = 0.0
        self._last_balance_poll_timestamp = time.time()
        self._in_flight_orders: Dict[str, InFlightOrderBase] = {}
        self._chain_info = {}
        self._status_polling_task = None
        self._init_task = None
        self._get_chain_info_task = None
        self._poll_notifier = None

    @property
    def chain(self):
        return self._chain

    @property
    def network(self):
        return self._network

    @property
    def connector(self):
        return self._connector

    @property
    def address(self):
        return self._address

    @property
    def in_flight_orders(self) -> Dict[str, InFlightOrderBase]:
        return self._in_flight_orders

    @property
    def ready(self):
        return all(self.status_dict.values())

    @staticmethod
    async def fetch_trading_pairs(chain: str, network: str) -> List[str]:
        """
        Calls the tokens endpoint on Gateway.
        """
        try:
            tokens = await GatewayHttpClient.get_tokens(chain, network)
            token_symbols = [t["symbol"] for t in tokens["tokens"]]
            trading_pairs = []
            for base, quote in itertools.permutations(token_symbols, 2):
                trading_pairs.append(f"{base}-{quote}")
            return trading_pairs
        except Exception:
            return []

    async def initialize(self):
        """
        Function to prepare the wallet, which was connected. For Ethereum this might include approving allowances,
        for Solana the initialization of token accounts. If finished, should set self.ready = True.
        """
        raise NotImplementedError

    async def get_chain_info(self):
        """
        Calls the base endpoint of the connector on Gateway to know basic info about chain being used.
        """
        try:
            self._chain_info = await GatewayHttpClient.get_network_status(chain=self.chain, network=self.network)
        except Exception as e:
            self.logger().network(
                "Error fetching chain info",
                exc_info=True,
                app_warning_msg=str(e)
            )

    async def get_gateway_status(self):
        """
        Calls the status endpoint on Gateway to know basic info about connected networks.
        """
        try:
            return await self._api_request("get", "/status")
        except Exception as e:
            self.logger().network(
                "Error fetching gateway status info",
                exc_info=True,
                app_warning_msg=str(e)
            )

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order by simply removing it from _in_flight_orders dictionary.
        """
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    async def start_network(self):
        if self._is_trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._init_task = safe_ensure_future(self.initialize())
        self._get_chain_info_task = safe_ensure_future(self.get_chain_info())

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
            if await GatewayHttpClient.ping_gateway():
                return NetworkStatus.CONNECTED
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.NOT_CONNECTED

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
        Calls Eth API to update total and available balances.
        """
        last_tick = self._last_balance_poll_timestamp
        current_tick = self.current_timestamp
        if not on_interval or (current_tick - last_tick) > self.UPDATE_BALANCE_INTERVAL:
            self._last_balance_poll_timestamp = current_tick
            local_asset_names = set(self._account_balances.keys())
            remote_asset_names = set()
            resp_json: Dict[str, Any] = await GatewayHttpClient.get_balances(
                self.chain, self.network, self.address, list(self._tokens) + [self._native_currency]
            )
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

    async def _api_request(
        self,
        method: str,
        path_url: str,
        params: Dict[str, Any] = {},
        throttler: Optional[AsyncThrottler] = None
    ) -> Dict[str, Any]:
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param path_url: The path url or the API end point
        :param params: A dictionary of required params for the end point
        :returns A response in json format.
        """
        params['address'] = self.wallet_address
        return await self.api_request(method, path_url, params, throttler)
