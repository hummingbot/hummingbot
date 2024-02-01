import asyncio
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
import re

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.kraken import kraken_constants as CONSTANTS, kraken_utils, \
    kraken_web_utils as web_utils
from hummingbot.connector.exchange.kraken.kraken_utils import (
    build_api_factory,
    build_rate_limits_by_tier,
    convert_from_exchange_symbol,
    convert_from_exchange_trading_pair,
    convert_to_exchange_trading_pair,
    is_dark_pool,
    split_to_base_quote,
)
from hummingbot.connector.exchange.kraken.kraken_constants import KrakenAPITier
from hummingbot.connector.exchange.kraken.kraken_api_order_book_data_source import KrakenAPIOrderBookDataSource
from hummingbot.connector.exchange.kraken.kraken_api_user_stream_data_source import KrakenAPIUserStreamDataSource
from hummingbot.connector.exchange.kraken.kraken_auth import KrakenAuth
from hummingbot.connector.exchange.kraken.kraken_in_fight_order import (
    KrakenInFlightOrder,
    # KrakenInFlightOrderNotCreated,
)
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import TradeFillOrderDetails, combine_to_hb_trading_pair, get_new_client_order_id
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent
from hummingbot.core.utils.async_utils import safe_gather, safe_ensure_future
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class KrakenExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    SHORT_POLL_INTERVAL = 30.0

    web_utils = web_utils
    REQUEST_ATTEMPTS = 5

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 kraken_api_key: str,
                 kraken_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 kraken_api_tier: str = "starter"
                 ):
        self.api_key = kraken_api_key
        self.secret_key = kraken_api_secret
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        # todo
        self._last_trades_poll_kraken_timestamp = 1.0
        self._kraken_api_tier = KrakenAPITier(kraken_api_tier.upper())
        self._throttler = self._build_async_throttler(api_tier=self._kraken_api_tier)
        self._asset_pairs = {}
        self._last_userref = 0

        super().__init__(client_config_map)

    @staticmethod
    def kraken_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(kraken_type: str) -> OrderType:
        return OrderType[kraken_type]

    @property
    def authenticator(self):
        return KrakenAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        return "kraken"

    # todo
    # @property
    # def rate_limits_rules(self):
    #     return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return self._domain

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.ASSET_PAIRS_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.ASSET_PAIRS_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.TICKER_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    # todo
    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    # async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
    #     pairs_prices = await self._api_get(path_url=CONSTANTS.TICKER_BOOK_PATH_URL)
    #     return pairs_prices

    def _build_async_throttler(self, api_tier: KrakenAPITier) -> AsyncThrottler:
        limits_pct = self._client_config.rate_limits_share_pct
        if limits_pct < Decimal("100"):
            self.logger().warning(
                f"The Kraken API does not allow enough bandwidth for a reduced rate-limit share percentage."
                f" Current percentage: {limits_pct}."
            )
        throttler = AsyncThrottler(build_rate_limits_by_tier(api_tier))
        return throttler

    # todo
    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception)
        is_time_synchronizer_related = ("-1021" in error_description
                                        and "Timestamp for this request" in error_description)
        return is_time_synchronizer_related

    # todo
    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return str(CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE) in str(
            status_update_exception
        ) and CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    # todo
    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return str(CONSTANTS.UNKNOWN_ORDER_ERROR_CODE) in str(
            cancelation_exception
        ) and CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return KrakenAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return KrakenAPIUserStreamDataSource(
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        is_maker = order_type is OrderType.LIMIT_MAKER
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))

    def generate_userref(self):
        self._last_userref += 1
        return self._last_userref

    @staticmethod
    def is_cloudflare_exception(exception: Exception):
        """
        Error status 5xx or 10xx are related to Cloudflare.
        https://support.kraken.com/hc/en-us/articles/360001491786-API-error-messages#6
        """
        return bool(re.search(r"HTTP status is (5|10)\d\d\.", str(exception)))

    async def get_open_orders_with_userref(self, userref: int):
        data = {'userref': userref}
        return await self._api_request_with_retry(RESTMethod.POST,
                                                  CONSTANTS.OPEN_ORDERS_PATH_URL,
                                                  is_auth_required=True,
                                                  data=data)
    # todo 修改KrakenInFlightOrder
    # def restore_tracking_states(self, saved_states: Dict[str, Any]):
    #     in_flight_orders: Dict[str, KrakenInFlightOrder] = {}
    #     for key, value in saved_states.items():
    #         in_flight_orders[key] = KrakenInFlightOrder.from_json(value)
    #         self._last_userref = max(int(value["userref"]), self._last_userref)
    #     self._in_flight_orders.update(in_flight_orders)
    # === Orders placing ===

    def buy(self,
            trading_pair: str,
            amount: Decimal,
            order_type=OrderType.LIMIT,
            price: Decimal = s_decimal_NaN,
            **kwargs) -> str:
        """
        Creates a promise to create a buy order using the parameters

        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price

        :return: the id assigned by the connector to the order (the client id)
        """
        order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length
        )
        userref = self.generate_userref()
        safe_ensure_future(self._create_order(
            trade_type=TradeType.BUY,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            userref=userref))
        return order_id

    def sell(self,
             trading_pair: str,
             amount: Decimal,
             order_type: OrderType = OrderType.LIMIT,
             price: Decimal = s_decimal_NaN,
             **kwargs) -> str:
        """
        Creates a promise to create a sell order using the parameters.
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        :return: the id assigned by the connector to the order (the client id)
        """
        order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length
        )
        userref = self.generate_userref()
        safe_ensure_future(self._create_order(
            trade_type=TradeType.SELL,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            userref=userref))
        return order_id

    async def get_asset_pairs(self) -> Dict[str, Any]:
        if not self._asset_pairs:
            asset_pairs = await self._api_request(method=RESTMethod.GET, path_url=CONSTANTS.ASSET_PAIRS_PATH_URL)
            self._asset_pairs = {f"{details['base']}-{details['quote']}": details
                                 for _, details in asset_pairs.items() if not is_dark_pool(details)}
        return self._asset_pairs

    def start_tracking_order(self,
                             order_id: str,
                             exchange_order_id: Optional[str],
                             trading_pair: str,
                             trade_type: TradeType,
                             price: Decimal,
                             amount: Decimal,
                             order_type: OrderType,
                             **kwargs):
        """
        Starts tracking an order by adding it to the order tracker.

        :param order_id: the order identifier
        :param exchange_order_id: the identifier for the order in the exchange
        :param trading_pair: the token pair for the operation
        :param trade_type: the type of order (buy or sell)
        :param price: the price for the order
        :param amount: the amount for the order
        :param order_type: type of execution for the order (MARKET, LIMIT, LIMIT_MAKER)
        """
        userref = kwargs.get("userref", 0)
        self._order_tracker.start_tracking_order(
            KrakenInFlightOrder(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=trade_type,
                amount=amount,
                price=price,
                creation_timestamp=self.current_timestamp,
                userref=userref,
            )
        )

    def restore_tracking_states(self, saved_states: Dict[str, Any]):
        for serialized_order in saved_states.values():
            order = KrakenInFlightOrder.from_json(serialized_order)
            if order.is_open:
                self._order_tracker._in_flight_orders[order.client_order_id] = order
            elif order.is_failure:
                # If the order is marked as failed but is still in the tracking states, it was a lost order
                self._order_tracker._lost_orders[order.client_order_id] = order
            self._last_userref = max(int(serialized_order.userref), self._last_userref)

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        userref = kwargs.get("userref", 0)
        trading_pair = convert_to_exchange_trading_pair(trading_pair)
        data = {
            "pair": trading_pair,
            "type": "buy" if trade_type is TradeType.BUY else "sell",
            "ordertype": "market" if order_type is OrderType.MARKET else "limit",
            "volume": str(amount),
            "userref": userref,
            "price": str(price)
        }
        if order_type is OrderType.LIMIT_MAKER:
            data["oflags"] = "post"
        order_result = await self._api_request_with_retry(RESTMethod.POST,
                                                          CONSTANTS.ADD_ORDER_PATH_URL,
                                                          data=data,
                                                          is_auth_required=True)

        # todo
        # o_order_result = order_result['response']["data"]["statuses"][0]
        # if "error" in o_order_result:
        #     raise IOError(f"Error submitting order {userref}: {o_order_result['error']}")
        # o_data = o_order_result.get("resting") or o_order_result.get("filled")
        o_id = order_result["txid"][0]
        return (o_id, self.current_timestamp)

    # todo
    async def _api_request_with_retry(self,
                                      method: RESTMethod,
                                      endpoint: str,
                                      params: Optional[Dict[str, Any]] = None,
                                      data: Optional[Dict[str, Any]] = None,
                                      is_auth_required: bool = False,
                                      retry_interval=2.0) -> Dict[str, Any]:
        result = None
        for retry_attempt in range(self.REQUEST_ATTEMPTS):
            try:
                result = await self._api_request(path_url=endpoint, method=method, params=params, data=data,
                                                 is_auth_required=is_auth_required)
                break
            except IOError as e:
                if self.is_cloudflare_exception(e):
                    if endpoint == CONSTANTS.ADD_ORDER_PATH_URL:
                        self.logger().info(f"Retrying {endpoint}")
                        # Order placement could have been successful despite the IOError, so check for the open order.
                        response = self.get_open_orders_with_userref(data.get('userref'))
                        if any(response.get("open").values()):
                            return response
                    self.logger().warning(
                        f"Cloudflare error. Attempt {retry_attempt + 1}/{self.REQUEST_ATTEMPTS}"
                        f" API command {method}: {endpoint}"
                    )
                    await asyncio.sleep(retry_interval ** retry_attempt)
                    continue
                else:
                    raise e
        if result is None:
            raise IOError(f"Error fetching data from {endpoint}.")
        return result

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        api_params = {
            "symbol": symbol,
            "origClientOrderId": order_id,
        }
        cancel_result = await self._api_delete(
            path_url=CONSTANTS.ORDER_PATH_URL,
            params=api_params,
            is_auth_required=True)
        if cancel_result.get("status") == "NEW":
            return True
        return False

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Example:
        {
            "XBTUSDT": {
              "altname": "XBTUSDT",
              "wsname": "XBT/USDT",
              "aclass_base": "currency",
              "base": "XXBT",
              "aclass_quote": "currency",
              "quote": "USDT",
              "lot": "unit",
              "pair_decimals": 1,
              "lot_decimals": 8,
              "lot_multiplier": 1,
              "leverage_buy": [2, 3],
              "leverage_sell": [2, 3],
              "fees": [
                [0, 0.26],
                [50000, 0.24],
                [100000, 0.22],
                [250000, 0.2],
                [500000, 0.18],
                [1000000, 0.16],
                [2500000, 0.14],
                [5000000, 0.12],
                [10000000, 0.1]
              ],
              "fees_maker": [
                [0, 0.16],
                [50000, 0.14],
                [100000, 0.12],
                [250000, 0.1],
                [500000, 0.08],
                [1000000, 0.06],
                [2500000, 0.04],
                [5000000, 0.02],
                [10000000, 0]
              ],
              "fee_volume_currency": "ZUSD",
              "margin_call": 80,
              "margin_stop": 40,
              "ordermin": "0.0002"
            }
        }
        """
        retval: list = []
        trading_pair_rules = exchange_info_dict.values()
        # for trading_pair, rule in asset_pairs_dict.items():
        for rule in filter(web_utils.is_exchange_information_valid, trading_pair_rules):
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule.get("symbol"))
                min_order_size = Decimal(rule.get('ordermin', 0))
                min_price_increment = Decimal(f"1e-{rule.get('pair_decimals')}")
                min_base_amount_increment = Decimal(f"1e-{rule.get('lot_decimals')}")
                retval.append(
                    TradingRule(
                        trading_pair,
                        min_order_size=min_order_size,
                        min_price_increment=min_price_increment,
                        min_base_amount_increment=min_base_amount_increment,
                    )
                )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {rule}. Skipping.", exc_info=True)
        return retval

    async def _status_polling_loop_fetch_updates(self):
        await self._update_order_fills_from_trades()
        await super()._status_polling_loop_fetch_updates()

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    async def _user_stream_event_listener(self):
        """
        Listens to messages from _user_stream_tracker.user_stream queue.
        Traders, Orders, and Balance updates from the WS.
        """
        user_channels = [
            CONSTANTS.USER_TRADES_ENDPOINT_NAME,
            CONSTANTS.USER_ORDERS_ENDPOINT_NAME,
            CONSTANTS.USER_BALANCE_ENDPOINT_NAME,
        ]
        async for event_message in self._iter_user_event_queue():
            try:
                channel: str = event_message.get("c", None)
                results: Dict[str, Any] = event_message.get("d", {})
                if "code" not in event_message and channel not in user_channels:
                    self.logger().error(
                        f"Unexpected message in user stream: {event_message}.", exc_info=True)
                    continue
                if channel == CONSTANTS.USER_TRADES_ENDPOINT_NAME:
                    self._process_trade_message(results)
                elif channel == CONSTANTS.USER_ORDERS_ENDPOINT_NAME:
                    self._process_order_message(event_message)
                elif channel == CONSTANTS.USER_BALANCE_ENDPOINT_NAME:
                    self._process_balance_message_ws(results)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    def _process_balance_message_ws(self, account):
        asset_name = account["a"]
        self._account_available_balances[asset_name] = Decimal(str(account["f"]))
        self._account_balances[asset_name] = Decimal(str(account["f"])) + Decimal(str(account["l"]))

    def _create_trade_update_with_order_fill_data(
            self,
            order_fill: Dict[str, Any],
            order: InFlightOrder):

        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=order.trade_type,
            percent_token=order_fill["N"],
            flat_fees=[TokenAmount(
                amount=Decimal(order_fill["n"]),
                token=order_fill["N"]
            )]
        )
        trade_update = TradeUpdate(
            trade_id=str(order_fill["t"]),
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            fee=fee,
            fill_base_amount=Decimal(order_fill["v"]),
            fill_quote_amount=Decimal(order_fill["a"]),
            fill_price=Decimal(order_fill["p"]),
            fill_timestamp=order_fill["T"] * 1e-3,
        )
        return trade_update

    def _process_trade_message(self, trade: Dict[str, Any], client_order_id: Optional[str] = None):
        client_order_id = client_order_id or str(trade["c"])
        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
        if tracked_order is None:
            self.logger().debug(f"Ignoring trade message with id {client_order_id}: not in in_flight_orders.")
        else:
            trade_update = self._create_trade_update_with_order_fill_data(
                order_fill=trade,
                order=tracked_order)
            self._order_tracker.process_trade_update(trade_update)

    def _create_order_update_with_order_status_data(self, order_status: Dict[str, Any], order: InFlightOrder):
        client_order_id = str(order_status["d"].get("c", ""))
        order_update = OrderUpdate(
            trading_pair=order.trading_pair,
            update_timestamp=int(order_status["t"] * 1e-3),
            new_state=CONSTANTS.WS_ORDER_STATE[order_status["d"]["s"]],
            client_order_id=client_order_id,
            exchange_order_id=str(order_status["d"]["i"]),
        )
        return order_update

    def _process_order_message(self, raw_msg: Dict[str, Any]):
        order_msg = raw_msg.get("d", {})
        client_order_id = str(order_msg.get("c", ""))
        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
        if not tracked_order:
            self.logger().debug(f"Ignoring order message with id {client_order_id}: not in in_flight_orders.")
            return

        order_update = self._create_order_update_with_order_status_data(order_status=raw_msg, order=tracked_order)
        self._order_tracker.process_order_update(order_update=order_update)

    async def _update_order_fills_from_trades(self):
        """
        This is intended to be a backup measure to get filled events with trade ID for orders,
        in case Kraken's user stream events are not working.
        NOTE: It is not required to copy this functionality in other connectors.
        This is separated from _update_order_status which only updates the order status without producing filled
        events, since Kraken's get order endpoint does not return trade IDs.
        The minimum poll interval for order status is 10 seconds.
        """
        small_interval_last_tick = self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        small_interval_current_tick = self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        long_interval_last_tick = self._last_poll_timestamp / self.LONG_POLL_INTERVAL
        long_interval_current_tick = self.current_timestamp / self.LONG_POLL_INTERVAL

        if (long_interval_current_tick > long_interval_last_tick
                or (self.in_flight_orders and small_interval_current_tick > small_interval_last_tick)):
            query_time = int(self._last_trades_poll_kraken_timestamp * 1e3)
            self._last_trades_poll_kraken_timestamp = self._time_synchronizer.time()
            order_by_exchange_id_map = {}
            for order in self._order_tracker.all_fillable_orders.values():
                order_by_exchange_id_map[order.exchange_order_id] = order

            tasks = []
            trading_pairs = self.trading_pairs
            for trading_pair in trading_pairs:
                params = {
                    "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                }
                if self._last_poll_timestamp > 0:
                    params["startTime"] = query_time
                tasks.append(self._api_get(
                    path_url=CONSTANTS.MY_TRADES_PATH_URL,
                    params=params,
                    is_auth_required=True))

            self.logger().debug(f"Polling for order fills of {len(tasks)} trading pairs.")
            results = await safe_gather(*tasks, return_exceptions=True)

            for trades, trading_pair in zip(results, trading_pairs):

                if isinstance(trades, Exception):
                    self.logger().network(
                        f"Error fetching trades update for the order {trading_pair}: {trades}.",
                        app_warning_msg=f"Failed to fetch trade update for {trading_pair}."
                    )
                    continue
                for trade in trades:
                    exchange_order_id = str(trade["orderId"])
                    if exchange_order_id in order_by_exchange_id_map:
                        # This is a fill for a tracked order
                        tracked_order = order_by_exchange_id_map[exchange_order_id]
                        fee = TradeFeeBase.new_spot_fee(
                            fee_schema=self.trade_fee_schema(),
                            trade_type=tracked_order.trade_type,
                            percent_token=trade["commissionAsset"],
                            flat_fees=[TokenAmount(amount=Decimal(trade["commission"]), token=trade["commissionAsset"])]
                        )
                        trade_update = TradeUpdate(
                            trade_id=str(trade["id"]),
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=exchange_order_id,
                            trading_pair=trading_pair,
                            fee=fee,
                            fill_base_amount=Decimal(trade["qty"]),
                            fill_quote_amount=Decimal(trade["quoteQty"]),
                            fill_price=Decimal(trade["price"]),
                            fill_timestamp=trade["time"] * 1e-3,
                        )
                        self._order_tracker.process_trade_update(trade_update)
                    elif self.is_confirmed_new_order_filled_event(str(trade["id"]), exchange_order_id, trading_pair):
                        # This is a fill of an order registered in the DB but not tracked any more
                        self._current_trade_fills.add(TradeFillOrderDetails(
                            market=self.display_name,
                            exchange_trade_id=str(trade["id"]),
                            symbol=trading_pair))
                        self.trigger_event(
                            MarketEvent.OrderFilled,
                            OrderFilledEvent(
                                timestamp=float(trade["time"]) * 1e-3,
                                order_id=self._exchange_order_ids.get(str(trade["orderId"]), None),
                                trading_pair=trading_pair,
                                trade_type=TradeType.BUY if trade["isBuyer"] else TradeType.SELL,
                                order_type=OrderType.LIMIT_MAKER if trade["isMaker"] else OrderType.LIMIT,
                                price=Decimal(trade["price"]),
                                amount=Decimal(trade["qty"]),
                                trade_fee=DeductedFromReturnsTradeFee(
                                    flat_fees=[
                                        TokenAmount(
                                            trade["commissionAsset"],
                                            Decimal(trade["commission"])
                                        )
                                    ]
                                ),
                                exchange_trade_id=str(trade["id"])
                            ))
                        self.logger().info(f"Recreating missing trade in TradeFill: {trade}")

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            exchange_order_id = order.exchange_order_id
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            all_fills_response = await self._api_get(
                path_url=CONSTANTS.MY_TRADES_PATH_URL,
                params={
                    "symbol": trading_pair,
                    "orderId": exchange_order_id
                },
                is_auth_required=True,
                limit_id=CONSTANTS.MY_TRADES_PATH_URL)

            for trade in all_fills_response:
                exchange_order_id = str(trade["orderId"])
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=order.trade_type,
                    percent_token=trade["commissionAsset"],
                    flat_fees=[TokenAmount(amount=Decimal(trade["commission"]), token=trade["commissionAsset"])]
                )
                trade_update = TradeUpdate(
                    trade_id=str(trade["id"]),
                    client_order_id=order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=trading_pair,
                    fee=fee,
                    fill_base_amount=Decimal(trade["qty"]),
                    fill_quote_amount=Decimal(trade["quoteQty"]),
                    fill_price=Decimal(trade["price"]),
                    fill_timestamp=trade["time"] * 1e-3,
                )
                trade_updates.append(trade_update)

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        updated_order_data = await self._api_get(
            path_url=CONSTANTS.ORDER_PATH_URL,
            params={
                "symbol": trading_pair,
                "origClientOrderId": tracked_order.client_order_id},
            is_auth_required=True)

        new_state = CONSTANTS.ORDER_STATE[updated_order_data["status"]]

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(updated_order_data["orderId"]),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=updated_order_data["updateTime"] * 1e-3,
            new_state=new_state,
        )

        return order_update

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        balances = await self._api_request_with_retry(RESTMethod.POST, CONSTANTS.BALANCE_PATH_URL, is_auth_required=True)
        open_orders = await self._api_request_with_retry(RESTMethod.POST, CONSTANTS.OPEN_ORDERS_PATH_URL, is_auth_required=True)

        locked = defaultdict(Decimal)

        for order in open_orders.get("open").values():
            if order.get("status") == "open":
                details = order.get("descr")
                if details.get("ordertype") == "limit":
                    pair = convert_from_exchange_trading_pair(
                        details.get("pair"), tuple((await self.get_asset_pairs()).keys())
                    )
                    (base, quote) = self.split_trading_pair(pair)
                    vol_locked = Decimal(order.get("vol", 0)) - Decimal(order.get("vol_exec", 0))
                    if details.get("type") == "sell":
                        locked[convert_from_exchange_symbol(base)] += vol_locked
                    elif details.get("type") == "buy":
                        locked[convert_from_exchange_symbol(quote)] += vol_locked * Decimal(details.get("price"))

        for asset_name, balance in balances.items():
            cleaned_name = convert_from_exchange_symbol(asset_name).upper()
            total_balance = Decimal(balance)
            free_balance = total_balance - Decimal(locked[cleaned_name])
            self._account_available_balances[cleaned_name] = free_balance
            self._account_balances[cleaned_name] = total_balance
            remote_asset_names.add(cleaned_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]


    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(web_utils.is_exchange_information_valid, exchange_info.values()):
            mapping[symbol_data["altname"]] = combine_to_hb_trading_pair(base=symbol_data["base"],
                                                                        quote=symbol_data["quote"])
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        params = {
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        }

        resp_json = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL,
            params=params
        )

        return float(resp_json["lastPrice"])
