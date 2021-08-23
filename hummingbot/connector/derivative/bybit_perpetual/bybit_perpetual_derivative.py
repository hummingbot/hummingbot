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
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_api_order_book_data_source import BybitPerpetualAPIOrderBookDataSource as OrderBookDataSource
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.perpetual_trading import PerpetualTrading
from hummingbot.core.event.events import (
    FundingInfo,
    FundingPaymentCompletedEvent,
    PositionMode,
    PositionSide,
)
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger


bbpd_logger = None
s_decimal_0 = Decimal(0)


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
        self._status_poll_notifier = asyncio.Event()
        self._funding_fee_poll_notifier = asyncio.Event()

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
        self._status_poll_notifier = asyncio.Event()
        self._funding_fee_poll_notifier = asyncio.Event()

        if self._funding_info_polling_task is not None:
            self._funding_info_polling_task.cancel()
            self._funding_info_polling_task = None
        if self._user_funding_fee_polling_task is not None:
            self._user_funding_fee_polling_task.cancel()
            self._user_funding_fee_polling_task = None

    def get_next_funding_timestamp(self) -> float:
        # On ByBit Perpetuals, funding occurs every 8 hours at 00:00UTC, 08:00UTC and 16:00UTC.
        # Reference: https://help.bybit.com/hc/en-us/articles/360039261134-Funding-fee-calculation
        int_ts = int(self.current_timestamp)
        eight_hours = 8 * 60 * 60
        mod = int_ts % eight_hours
        return float(int_ts - mod + eight_hours)

    def tick(self, timestamp: float):
        """
        Called automatically by the run/run_til() functions in the Clock class. Each tick interval is 1 second by default.
        This function checks if the relevant polling task(s) is dued for execution
        """
        super().tick()
        # now = time.time()
        # poll_interval = (self.SHORT_POLL_INTERVAL
        #                  if now - self._user_stream_tracker.last_recv_time > 60.0
        #                  else self.LONG_POLL_INTERVAL)
        # last_tick = int(self._last_timestamp / poll_interval)
        # current_tick = int(timestamp / poll_interval)
        # if current_tick > last_tick:
        #     if not self._poll_notifier.is_set():
        #         self._poll_notifier.set()
        if self.current_timestamp >= self.get_next_funding_timestamp():
            if not self._funding_fee_poll_notifier.is_set():
                self._funding_fee_poll_notifier.set()

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
                    if trading_pair not in OrderBookDataSource._trading_pair_symbol_map:
                        self.logger().error(f"Trading pair {trading_pair} not supported.")
                        raise ValueError(f"Trading pair {trading_pair} not supported.")
                    params = {
                        "symbol": OrderBookDataSource._trading_pair_symbol_map[trading_pair]
                    }
                    resp = await self._api_request(method="GET",
                                                   path_url=CONSTANTS.LATEST_SYMBOL_INFORMATION_ENDPOINT,
                                                   params=params)

                    self._funding_info[trading_pair] = FundingInfo(
                        trading_pair=trading_pair,
                        index_price=Decimal(str(resp["index_price"])),
                        mark_price=Decimal(str(resp["mark_price"])),
                        next_funding_utc_timestamp=resp["next_funding_time"],
                        rate=Decimal(str(resp["predicted_funding_rate"]))
                    )

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error updating funding info. Error: {e}. Retrying in 10 seconds... ",
                                    exc_info=True)

    async def _fetch_funding_fee(self, trading_pair: str) -> bool:
        try:
            trading_pair_symbol_map: Dict[str, str] = await OrderBookDataSource.trading_pair_symbol_map(self._domain)
            if trading_pair not in trading_pair_symbol_map:
                self.logger().error(f"Unable to fetch funding fee for {trading_pair}. Trading pair not supported.")
                return False

            params = {
                "symbol": trading_pair_symbol_map[trading_pair]
            }
            raw_response: Dict[str, Any] = await self._api_request(method="GET",
                                                                   path_url=CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL,
                                                                   params=params,
                                                                   is_auth_required=True)
            data: Dict[str, Any] = raw_response["result"]

            funding_rate: Decimal = Decimal(str(data["funding_rate"]))
            position_size: Decimal = Decimal(str(data["size"]))
            payment: Decimal = funding_rate * position_size
            action: str = "paid" if payment < s_decimal_0 else "received"
            if payment != s_decimal_0:
                self.logger().info(f"Funding payment of {payment} {action} on {trading_pair} market.")
                self.trigger_event(self.MARKET_FUNDING_PAYMENT_COMPLETED_EVENT_TAG,
                                   FundingPaymentCompletedEvent(timestamp=int(data["exec_timestamp"] * 1e3),
                                                                market=self.name,
                                                                funding_rate=funding_rate,
                                                                trading_pair=trading_pair,
                                                                amount=payment))

            return True
        except Exception as e:
            self.logger().error(f"Unexpected error occurred fetching funding fee for {trading_pair}. Error: {e}",
                                exc_info=True)
            return False

    async def _user_funding_fee_polling_loop(self):
        """
        Retrieve User Funding Fee every Funding Time(every 8hrs). Trigger FundingPaymentCompleted event as required.
        """
        while True:
            try:
                await self._funding_fee_poll_notifier.wait()

                tasks = []
                for trading_pair in self._trading_pairs:
                    tasks.append(
                        asyncio.create_task(self._fetch_funding_fee(trading_pair))
                    )
                # Only when all tasks is successful would the event notifier be resetted
                responses: List[bool] = await safe_gather(*tasks)
                if all(responses):
                    self._funding_fee_poll_notifier = asyncio.Event()

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error whilst retrieving funding payments. "
                                    f"Error: {e} ",
                                    exc_info=True)

    async def _update_positions(self):
        trading_pair_symbol_map: Dict[str, str] = await OrderBookDataSource.trading_pair_symbol_map(self._domain)
        symbol_trading_pair_map: Dict[str, str] = {
            symbol: trading_pair
            for trading_pair, symbol in trading_pair_symbol_map.items()
        }

        raw_response = await self._api_request(method="GET",
                                               path_url=CONSTANTS.GET_POSITIONS_PATH_URL,
                                               is_auth_required=True)

        result: List[Dict[str, Any]] = raw_response["result"]

        for position in result:
            if not position["is_valid"]:
                self.logger().error(f"Received an invalid position entry. Position: {position}")
                continue
            ex_trading_pair = position.get("symbol")
            hb_trading_pair = symbol_trading_pair_map.get(ex_trading_pair)
            position_side = PositionSide.LONG if position.get("side") == "buy" else PositionSide.SHORT
            unrealized_pnl = Decimal(str(position.get("unrealised_pnl")))
            entry_price = Decimal(str(position.get("entry_price")))
            amount = Decimal(str(position.get("size")))
            leverage = Decimal(str(position.get("effective_leverage")))
            pos_key = self.position_key(hb_trading_pair, position_side)
            if amount != s_decimal_0:
                self._account_positions[pos_key] = Position(
                    trading_pair=hb_trading_pair,
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=amount,
                    leverage=leverage,
                )
            else:
                if pos_key in self._account_positions:
                    del self._account_positions[pos_key]

    async def _status_polling_loop(self):
        while True:
            try:
                await self._status_poll_notifier.wait()
                await safe_gather(
                    # self._update_balances(),
                    self._update_positions()
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().network(f"Unexpected error while fetching account updates. Error: {e}",
                                      exc_info=True,
                                      app_warning_msg=f"Could not fetch account updates from {CONSTANTS.EXCHANGE_NAME} Perpetuals. "
                                      )
                await asyncio.sleep(0.5)
            finally:
                self._status_poll_notifier = asyncio.Event()

    async def _set_leverage(self, trading_pair: str, leverage: int = 1):
        trading_pair_symbol_map: Dict[str, str] = await OrderBookDataSource.trading_pair_symbol_map(self._domain)
        if trading_pair not in trading_pair_symbol_map:
            self.logger().error(f"Unable to set leverage for {trading_pair}. Trading pair not supported.")
            return
        body_params = {
            "symbol": trading_pair_symbol_map,
            "leverage": leverage
        }
        resp = await self._api_request(method="POST",
                                       path_url=CONSTANTS.SET_LEVERAGE_PATH_URL,
                                       body=body_params,
                                       is_auth_required=True)

        if resp["ret_msg"] == "ok":
            self._leverage[trading_pair] = leverage
            self.logger().info(f"Leverage Successfully set to {leverage} for {trading_pair}.")
        else:
            self.logger().error("Unable to set leverage.")

    def set_leverage(self, trading_pair: str, leverage: int):
        safe_ensure_future(self._set_leverage(trading_pair=trading_pair, leverage=leverage))
