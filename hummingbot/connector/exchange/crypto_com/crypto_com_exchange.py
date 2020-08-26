import logging
from typing import (
    Dict,
    List,
    Optional,
    Any,
)
from decimal import Decimal
import asyncio
import json
import aiohttp
import math

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.logger import HummingbotLogger
from hummingbot.core.clock import Clock
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.market.trading_rule import TradingRule
from .crypto_com_order_book_tracker import CryptoComOrderBookTracker
from .crypto_com_user_stream_tracker import CryptoComUserStreamTracker
from .crypto_com_auth import CryptoComAuth
from . import crypto_com_utils
from . import crypto_com_constants as Constants
s_logger = None


class CryptoComExchange(ExchangeBase):

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 fee_estimates: Dict[bool, Decimal],
                 balance_limits: Dict[str, Decimal],
                 crypto_com_api_key: str,
                 crypto_com_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):
        super().__init__(fee_estimates, balance_limits)
        self._crypto_com_auth = CryptoComAuth(crypto_com_api_key, crypto_com_api_secret)
        self._trading_required = trading_required
        self._order_book_tracker = CryptoComOrderBookTracker(trading_pairs=trading_pairs)
        self._user_stream_tracker = CryptoComUserStreamTracker(self._crypto_com_auth, trading_pairs)
        self._ev_loop = asyncio.get_event_loop()
        self._shared_client = None
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._in_flight_orders = {}  # Dict[client_order_id:str, BinanceInFlightOrder]
        self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        # self._tx_tracker = BinanceMarketTransactionTracker(self)
        self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._status_polling_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._last_poll_timestamp = 0

    def start(self, clock: Clock, timestamp: float):
        # self._tx_tracker.c_start(clock, timestamp)
        ExchangeBase.start(self, clock, timestamp)

    def stop(self, clock: Clock):
        ExchangeBase.stop(self, clock)
        # self._async_scheduler.stop()

    async def start_network(self):
        self._order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        # if self._trading_required:
        #     await self._update_account_id()
        #     self._status_polling_task = safe_ensure_future(self._status_polling_loop())
        #     self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
        #     self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

    async def stop_network(self):
        self._order_book_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
            self._trading_rules_polling_task = None
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
            self._user_stream_tracker_task = None
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
            self._user_stream_event_listener_task = None

    async def _http_client(self) -> aiohttp.ClientSession:
        """
        :returns: Shared client session instance
        """
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _trading_rules_polling_loop(self):
        while True:
            try:
                await self._update_trading_rules()
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching trading rules.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from Kucoin. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    async def _update_trading_rules(self):
        instruments_info = await self._api_request("get", path_url="public/get-instruments")
        self._trading_rules.clear()
        self._trading_rules = self._format_trading_rules(instruments_info)

    def _format_trading_rules(self, instruments_info: Dict[str, Any]) -> Dict[str, TradingRule]:
        """
        Example:
        {
            "id": 11,
            "method": "public/get-instruments",
            "code": 0,
            "result": {
                "instruments": [
                      {
                        "instrument_name": "ETH_CRO",
                        "quote_currency": "CRO",
                        "base_currency": "ETH",
                        "price_decimals": 2,
                        "quantity_decimals": 2
                      },
                      {
                        "instrument_name": "CRO_BTC",
                        "quote_currency": "BTC",
                        "base_currency": "CRO",
                        "price_decimals": 8,
                        "quantity_decimals": 2
                      }
                    ]
              }
        }
        """
        result = {}
        for rule in instruments_info["result"]["instruments"]:
            try:
                trading_pair = crypto_com_utils.convert_from_exchange_trading_pair(rule["instrument_name"])
                price_decimals = Decimal(str(rule["price_decimals"]))
                quantity_decimals = Decimal(str(rule["quantity_decimals"]))
                price_step = Decimal("1") / Decimal(str(math.pow(10, price_decimals)))
                quantity_step = Decimal("1") / Decimal(str(math.pow(10, quantity_decimals)))
                result[trading_pair] = TradingRule(trading_pair,
                                                   min_price_increment=price_step,
                                                   min_quote_amount_increment=quantity_step)
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {rule}. Skipping.", exc_info=True)
        return result

    async def _api_request(self,
                           method: str,
                           path_url: str,
                           params: Dict[str, Any] = {},
                           is_auth_required: bool = False) -> Dict[str, Any]:
        url = f"{Constants.REST_URL}/{path_url}"
        client = await self._http_client()
        if is_auth_required:
            request_id = crypto_com_utils.RequestId.generate_request_id()
            data = {"params": params}
            params = self._crypto_com_auth.generate_auth_dict(path_url, request_id,
                                                              crypto_com_utils.get_ms_timestamp(), data)
            headers = self._crypto_com_auth.get_headers()
        else:
            headers = {"Content-Type": "application/json"}

        if method == "get":
            response = await client.get(url, headers=headers)
        elif method == "post":
            post_json = json.dumps(params)
            response = await client.post(url, data=post_json, headers=headers)
        # elif method == "delete":
        #     response = await client.delete(url, headers=headers)
        else:
            raise NotImplementedError

        if response:
            if response.status != 200:
                raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}.")
            try:
                parsed_response = json.loads(await response.text())
            except Exception:
                raise IOError(f"Error parsing data from {url}.")
            return parsed_response
