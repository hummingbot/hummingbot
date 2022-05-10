import asyncio
import logging
import warnings
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional

from async_timeout import timeout
from bidict import bidict

from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.exchange.okex import constants as CONSTANTS, okex_utils, okex_web_utils as web_utils
from hummingbot.connector.exchange.okex.okex_api_order_book_data_source import OkexAPIOrderBookDataSource
from hummingbot.connector.exchange.okex.okex_api_user_stream_data_source import OkexAPIUserStreamDataSource
from hummingbot.connector.exchange.okex.okex_auth import OKExAuth
from hummingbot.connector.exchange_base import ExchangeBase, s_decimal_NaN
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_client_order_id
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.logger import HummingbotLogger

hm_logger = None
s_decimal_0 = Decimal(0)


class OKExAPIError(IOError):
    def __init__(self, error_payload: Dict[str, Any]):
        super().__init__(str(error_payload))
        self.error_payload = error_payload


class OkexExchange(ExchangeBase):
    UPDATE_ORDERS_INTERVAL = 10.0
    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 120.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global hm_logger
        if hm_logger is None:
            hm_logger = logging.getLogger(__name__)
        return hm_logger

    def __init__(self,
                 okex_api_key: str,
                 okex_secret_key: str,
                 okex_passphrase: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):

        super().__init__()
        self._throttler = web_utils.create_throttler()
        self._time_synchronizer = TimeSynchronizer()
        self._auth = OKExAuth(
            api_key=okex_api_key,
            secret_key=okex_secret_key,
            passphrase=okex_passphrase,
            time_provider=self._time_synchronizer)
        self._api_factory = web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            auth=self._auth)
        self._last_poll_timestamp = 0
        self._last_timestamp = 0
        self._set_order_book_tracker(OrderBookTracker(
            data_source=OkexAPIOrderBookDataSource(
                trading_pairs=trading_pairs,
                connector=self,
                api_factory=self._api_factory),
            trading_pairs=trading_pairs))
        self._user_stream_tracker = UserStreamTracker(
            data_source=OkexAPIUserStreamDataSource(
                auth=self._auth,
                api_factory=self._api_factory))
        self._poll_notifier = asyncio.Event()
        self._status_polling_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._trading_required = trading_required
        self._trading_rules = {}
        self._order_tracker: ClientOrderTracker = ClientOrderTracker(connector=self)

    @property
    def name(self) -> str:
        return "okex"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self.order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, InFlightOrder]:
        return self._order_tracker.active_orders

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self._in_flight_orders.values()
        ]

    @property
    def tracking_states(self) -> Dict[str, Any]:
        return {
            key: value.to_json()
            for key, value in self._in_flight_orders.items()
        }

    def restore_tracking_states(self, saved_states: Dict[str, Any]):
        """
        Restore in-flight orders from saved tracking states, this is st the connector can pick up on where it left off
        when it disconnects.

        :param saved_states: The saved tracking_states.
        """
        self._order_tracker.restore_tracking_states(tracking_states=saved_states)

    async def start_network(self):
        self._stop_network()
        self.order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())

        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())
            await self._update_balances()

    def _stop_network(self):
        self.order_book_tracker.stop()
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

    async def stop_network(self):
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        try:
            await self._api_request(path_url=CONSTANTS.OKEX_SERVER_TIME_PATH, method=RESTMethod.GET)
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    def tick(self, timestamp: float):
        """
        Includes the logic that has to be processed every time a new tick happens in the bot. Particularly it enables
        the execution of the status update polling loop using an event.
        """
        poll_interval = (self.SHORT_POLL_INTERVAL
                         if timestamp - self._user_stream_tracker.last_recv_time > 60.0
                         else self.LONG_POLL_INTERVAL)
        last_tick = int(self._last_timestamp / poll_interval)
        current_tick = int(timestamp / poll_interval)

        if current_tick > last_tick:
            self._poll_notifier.set()
        self._last_timestamp = timestamp

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "symbols_mapping_initialized": self.trading_pair_symbol_map_ready(),
            "order_books_initialized": self.order_book_tracker.ready,
            "account_balance": not self._trading_required or len(self._account_balances) > 0,
            "trading_rule_initialized": len(self._trading_rules) > 0,
            "user_stream_initialized":
                self._user_stream_tracker.data_source.last_recv_time > 0 if self._trading_required else True,
        }

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        """
        Cancels all currently active orders. The cancellations are performed in parallel tasks.

        :param timeout_seconds: the maximum time (in seconds) the cancel logic should run

        :return: a list of CancellationResult instances, one for each of the orders to be cancelled
        """
        incomplete_orders = [o for o in self.in_flight_orders.values() if not o.is_done]
        tasks = [asyncio.create_task(self._execute_cancel(o.trading_pair, o.client_order_id))
                 for o in incomplete_orders]
        order_id_set = set([o.client_order_id for o in incomplete_orders])
        successful_cancellations = []

        try:
            async with timeout(timeout_seconds):
                cancellation_results = await safe_gather(*tasks, return_exceptions=True)
                for cr in cancellation_results:
                    if isinstance(cr, Exception):
                        continue
                    if cr is not None:
                        client_order_id = cr
                        order_id_set.remove(client_order_id)
                        successful_cancellations.append(CancellationResult(client_order_id, True))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().network(
                "Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel order. Check API key and network connection."
            )

        failed_cancellations = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancellations + failed_cancellations

    def get_order_book(self, trading_pair: str) -> OrderBook:
        """
        Returns the current order book for a particular market

        :param trading_pair: the pair of tokens for which the order book should be retrieved
        """
        if trading_pair not in self.order_book_tracker.order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return self.order_book_tracker.order_books[trading_pair]

    def start_tracking_order(self,
                             order_id: str,
                             exchange_order_id: Optional[str],
                             trading_pair: str,
                             trade_type: TradeType,
                             price: Decimal,
                             amount: Decimal,
                             order_type: OrderType):
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
        self._order_tracker.start_tracking_order(
            InFlightOrder(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=trade_type,
                amount=amount,
                price=price,
                creation_timestamp=self.current_timestamp
            )
        )

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order

        :param order_id: The id of the order that will not be tracked any more
        """
        self._order_tracker.stop_tracking_order(client_order_id=order_id)

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        """
        Used by quantize_order_price() in _create_order()
        Returns a price step, a minimum price increment for a given trading pair.

        :param trading_pair: the trading pair to check for market conditions
        :param price: the starting point price
        """
        trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        """
        Used by quantize_order_price() in _create_order()
        Returns an order amount step, a minimum amount increment for a given trading pair.

        :param trading_pair: the trading pair to check for market conditions
        :param order_size: the starting point order price
        """
        trading_rule = self._trading_rules[trading_pair]
        return Decimal(trading_rule.min_base_amount_increment)

    def quantize_order_amount(self, trading_pair: str, amount: Decimal, price: Decimal = s_decimal_0) -> Decimal:
        """
        Applies the trading rules to calculate the correct order amount for the market

        :param trading_pair: the token pair for which the order will be created
        :param amount: the intended amount for the order
        :param price: the intended price for the order

        :return: the quantized order amount after applying the trading rules
        """
        trading_rule = self._trading_rules[trading_pair]
        quantized_amount: Decimal = super().quantize_order_amount(trading_pair, amount)

        # Check against min_order_size and min_notional_size. If not passing either check, return 0.
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        if price == s_decimal_0:
            current_price: Decimal = self.get_price(trading_pair, False)
            notional_size = current_price * quantized_amount
        else:
            notional_size = price * quantized_amount

        # Add 1% as a safety factor in case the prices changed while making the order.
        if notional_size < trading_rule.min_notional_size * Decimal("1.01"):
            return s_decimal_0

        return quantized_amount

    def get_price(self, trading_pair: str, is_buy: bool) -> Decimal:
        return self.c_get_price(trading_pair, is_buy)

    def buy(self,
            trading_pair: str,
            amount: Decimal,
            order_type=OrderType.MARKET,
            price: Decimal = s_decimal_NaN,
            **kwargs) -> str:

        order_id: str = get_new_client_order_id(
            is_buy=True,
            trading_pair=trading_pair,
            hbot_order_id_prefix=CONSTANTS.CLIENT_ID_PREFIX,
            max_id_len=CONSTANTS.MAX_ID_LEN,
        )

        safe_ensure_future(self._create_order(
            trade_type=TradeType.BUY,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price))
        return order_id

    def sell(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
             price: Decimal = s_decimal_NaN, **kwargs) -> str:

        order_id: str = get_new_client_order_id(
            is_buy=False,
            trading_pair=trading_pair,
            hbot_order_id_prefix=CONSTANTS.CLIENT_ID_PREFIX,
            max_id_len=CONSTANTS.MAX_ID_LEN,
        )

        safe_ensure_future(self._create_order(
            trade_type=TradeType.SELL,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price))
        return order_id

    def cancel(self, trading_pair: str, order_id: str):
        """
        Creates a promise to cancel an order in the exchange

        :param trading_pair: the trading pair the order to cancel operates with
        :param order_id: the client id of the order to cancel

        :return: the client id of the order to cancel
        """
        safe_ensure_future(self._execute_cancel(trading_pair, order_id))
        return order_id

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_NaN,
                is_maker: Optional[bool] = None):
        warnings.warn(
            "The 'estimate_fee' method is deprecated, use 'build_trade_fee' and 'build_perpetual_trade_fee' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        raise DeprecationWarning(
            "The 'estimate_fee' method is deprecated, use 'build_trade_fee' and 'build_perpetual_trade_fee' instead."
        )

    async def _initialize_trading_pair_symbol_map(self):
        try:
            exchange_info = await self._api_request(
                path_url=CONSTANTS.OKEX_INSTRUMENTS_PATH,
                method=RESTMethod.GET,
                params={"instType": "SPOT"},
            )
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)
        except Exception:
            self.logger().exception("There was an error requesting exchange info.")

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(okex_utils.is_exchange_information_valid, exchange_info["data"]):
            mapping[symbol_data["instId"]] = combine_to_hb_trading_pair(base=symbol_data["baseCcy"],
                                                                        quote=symbol_data["quoteCcy"])
        self._set_trading_pair_symbol_map(mapping)

    async def _create_order(self,
                            trade_type: TradeType,
                            order_id: str,
                            trading_pair: str,
                            amount: Decimal,
                            order_type: OrderType,
                            price: Optional[Decimal] = None):
        """
        Creates an order in the exchange using the parameters to configure it

        :param trade_type: the side of the order (BUY of SELL)
        :param order_id: the id that should be assigned to the order (the client id)
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        """
        trading_rule = self._trading_rules[trading_pair]

        if order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER]:
            price = self.quantize_order_price(trading_pair, price)
            amount = self.quantize_order_amount(trading_pair=trading_pair, amount=amount, price=price)
        else:
            amount = self.quantize_order_amount(trading_pair, amount)

        self.start_tracking_order(
            order_id=order_id,
            exchange_order_id=None,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount
        )

        if amount < trading_rule.min_order_size:
            self.logger().warning(f"{trade_type.name.title()} order amount {amount} is lower than the minimum order"
                                  f" size {trading_rule.min_order_size}. The order will not be created.")
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                trading_pair=trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=OrderState.FAILED,
            )
            self._order_tracker.process_order_update(order_update)
            return

        try:

            exchange_order_id = await self._place_order(
                order_id=order_id,
                trading_pair=trading_pair,
                amount=amount,
                trade_type=trade_type,
                order_type=order_type,
                price=price)

            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=OrderState.OPEN,
            )
            self._order_tracker.process_order_update(order_update)

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().network(
                f"Error submitting {trade_type.name.lower()} {order_type.name.upper()} order to Kucoin for "
                f"{amount} {trading_pair} "
                f"{price}.",
                exc_info=True,
                app_warning_msg="Failed to submit buy order to Kucoin. Check API key and network connection."
            )
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                trading_pair=trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=OrderState.FAILED,
            )
            self._order_tracker.process_order_update(order_update)

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal) -> str:
        data = {
            'clOrdId': order_id,
            'tdMode': 'cash',
            'ordType': 'limit',
            'side': trade_type.name.lower(),
            'instId': await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            'sz': str(amount),
            'px': str(price)
        }

        exchange_order_id = await self._api_request(
            path_url=CONSTANTS.OKEX_PLACE_ORDER_PATH,
            method=RESTMethod.POST,
            data=data,
            is_auth_required=True,
            limit_id=CONSTANTS.OKEX_PLACE_ORDER_PATH,
        )
        data = exchange_order_id["data"][0]
        if data["sCode"] != "0":
            raise IOError(f"Error submitting order {order_id}: {data['sMsg']}")
        return str(data['ordId'])

    async def _execute_cancel(self, trading_pair: str, order_id: str):
        """
        Requests the exchange to cancel an active order

        :param trading_pair: the trading pair the order to cancel operates with
        :param order_id: the client id of the order to cancel
        """
        tracked_order = self._order_tracker.fetch_tracked_order(order_id)
        if tracked_order is not None:
            try:
                params = {
                    "clOrdId": order_id,
                    "instId": trading_pair
                }
                response = await self._api_request(
                    path_url=CONSTANTS.OKEX_ORDER_CANCEL_PATH,
                    method=RESTMethod.POST,
                    data=params,
                    is_auth_required=True,
                )

                if response['code'] == '0':
                    order_update: OrderUpdate = OrderUpdate(
                        client_order_id=order_id,
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=self.current_timestamp,
                        new_state=OrderState.PENDING_CANCEL,
                    )
                    self._order_tracker.process_order_update(order_update)
                    return order_id
                else:
                    raise IOError(response["msg"])
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().network(
                    f"Failed to cancel order {order_id}: {str(e)}",
                    exc_info=True,
                    app_warning_msg=f"Failed to cancel the order {order_id} on OKX. "
                                    f"Check API key and network connection."
                )

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        params = {"instId": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)}

        resp_json = await self._api_request(
            path_url=CONSTANTS.OKEX_TICKER_PATH,
            params=params,
        )

        ticker_data, *_ = resp_json["data"]
        return float(ticker_data["last"])

    async def _update_balances(self):
        msg = await self._api_request(
            path_url=CONSTANTS.OKEX_BALANCE_PATH,
            is_auth_required=True)

        if msg['code'] == '0':
            balances = msg['data'][0]['details']
        else:
            raise Exception(msg['msg'])

        self._account_available_balances.clear()
        self._account_balances.clear()

        for balance in balances:
            self._account_balances[balance['ccy']] = Decimal(balance['cashBal'])
            self._account_available_balances[balance['ccy']] = Decimal(balance['availBal'])

    async def _update_trading_rules(self):
        last_tick = int(self._last_timestamp / 60.0)
        current_tick = int(self.current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) < 1:
            exchange_info = await self._api_request(
                path_url=CONSTANTS.OKEX_INSTRUMENTS_PATH,
                params={"instType": "SPOT"})
            trading_rules_list = await self._format_trading_rules(exchange_info["data"])
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.trading_pair] = trading_rule

    async def _format_trading_rules(self, raw_trading_pair_info: List[Dict[str, Any]]) -> List[TradingRule]:
        trading_rules = []

        for info in raw_trading_pair_info:
            try:
                trading_rules.append(
                    TradingRule(
                        trading_pair=await self.trading_pair_associated_to_exchange_symbol(symbol=info["instId"]),
                        min_order_size=Decimal(info["minSz"]),
                        min_price_increment=Decimal(info["tickSz"]),
                        min_base_amount_increment=Decimal(info["lotSz"]),
                    )
                )
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {info}. Skipping.")
        return trading_rules

    async def _request_order_update(self, order: InFlightOrder) -> Dict[str, Any]:
        return await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.OKEX_ORDER_DETAILS_PATH,
            params={
                "instId": await self.exchange_symbol_associated_to_pair(order.trading_pair),
                "clOrdId": order.client_order_id},
            is_auth_required=True)

    async def _request_order_fills(self, order: InFlightOrder) -> Dict[str, Any]:
        return await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.OKEX_TRADE_FILLS_PATH,
            params={
                "instType": "SPOT",
                "instId": await self.exchange_symbol_associated_to_pair(order.trading_pair),
                "ordId": await order.get_exchange_order_id()},
            is_auth_required=True)

    async def _update_order_status(self):

        tracked_orders = list(self.in_flight_orders.values())
        order_tasks = []
        order_fills_tasks = []
        for order in tracked_orders:
            order_tasks.append(asyncio.create_task(self._request_order_update(order=order)))
            order_fills_tasks.append(asyncio.create_task(self._request_order_fills(order=order)))
        self.logger().debug(f"Polling for order status updates of {len(order_tasks)} orders.")

        order_updates = await safe_gather(*order_tasks, return_exceptions=True)
        order_fills = await safe_gather(*order_fills_tasks, return_exceptions=True)
        for order_update, order_fill, tracked_order in zip(order_updates, order_fills, tracked_orders):
            client_order_id = tracked_order.client_order_id

            # If the order has already been cancelled or has failed do nothing
            if client_order_id not in self.in_flight_orders:
                continue

            if isinstance(order_fill, Exception):
                self.logger().network(
                    f"Error fetching order fills for the order {client_order_id}: {order_fill}.",
                    app_warning_msg=f"Failed to fetch status update for the order {client_order_id}."
                )

            else:
                fills_data = order_fill["data"]

                for fill_data in fills_data:
                    fee = TradeFeeBase.new_spot_fee(
                        fee_schema=self.trade_fee_schema(),
                        trade_type=tracked_order.trade_type,
                        percent_token=fill_data["feeCcy"],
                        flat_fees=[TokenAmount(amount=Decimal(fill_data["fee"]), token=fill_data["feeCcy"])]
                    )
                    trade_update = TradeUpdate(
                        trade_id=str(fill_data["tradeId"]),
                        client_order_id=client_order_id,
                        exchange_order_id=str(fill_data["ordId"]),
                        trading_pair=tracked_order.trading_pair,
                        fee=fee,
                        fill_base_amount=Decimal(fill_data["fillSz"]),
                        fill_quote_amount=Decimal(fill_data["fillSz"]) * Decimal(fill_data["fillPx"]),
                        fill_price=Decimal(fill_data["fillPx"]),
                        fill_timestamp=int(fill_data["ts"]) * 1e-3,
                    )
                    self._order_tracker.process_trade_update(trade_update)

            if isinstance(order_update, Exception):
                self.logger().network(
                    f"Error fetching status update for the order {client_order_id}: {order_update}.",
                    app_warning_msg=f"Failed to fetch status update for the order {client_order_id}."
                )
                await self._order_tracker.process_order_not_found(client_order_id)

            else:
                # Update order execution status
                order_data = order_update["data"][0]
                new_state = CONSTANTS.ORDER_STATE[order_data["state"]]

                update = OrderUpdate(
                    client_order_id=client_order_id,
                    exchange_order_id=str(order_data["ordId"]),
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=int(order_data["uTime"]) * 1e-3,
                    new_state=new_state,
                )
                self._order_tracker.process_order_update(update)

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()

                await safe_gather(
                    self._update_balances(),
                    self._update_order_status(),
                )
                self._last_poll_timestamp = self._current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching account updates.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch account updates from OKEx. "
                                                      "Check API key and network connection.")
                await self._sleep(0.5)

    async def _trading_rules_polling_loop(self):
        while True:
            try:
                await self._update_trading_rules()
                await self._sleep(60 * 5)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching trading rules.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from OkEx. "
                                                      "Check network connection.")
                await self._sleep(0.5)

    async def _iter_user_stream_queue(self) -> AsyncIterable[Dict[str, Any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unknown error. Retrying after 1 second. {e}", exc_info=True)
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        async for stream_message in self._iter_user_stream_queue():
            try:
                args = stream_message.get("arg", {})
                channel = args.get("channel", None)

                if channel == CONSTANTS.OKEX_WS_ORDERS_CHANNEL:
                    for data in stream_message.get("data", []):
                        order_status = CONSTANTS.ORDER_STATE[data["state"]]
                        tracked_order = self._order_tracker.fetch_order(client_order_id=data["clOrdId"])

                        if tracked_order is not None:
                            if order_status in [OrderState.PARTIALLY_FILLED, OrderState.FILLED]:
                                fee = TradeFeeBase.new_spot_fee(
                                    fee_schema=self.trade_fee_schema(),
                                    trade_type=tracked_order.trade_type,
                                    percent_token=data["fillFeeCcy"],
                                    flat_fees=[TokenAmount(amount=Decimal(data["fillFee"]), token=data["fillFeeCcy"])]
                                )
                                trade_update = TradeUpdate(
                                    trade_id=str(data["tradeId"]),
                                    client_order_id=tracked_order.client_order_id,
                                    exchange_order_id=str(data["ordId"]),
                                    trading_pair=tracked_order.trading_pair,
                                    fee=fee,
                                    fill_base_amount=Decimal(data["fillSz"]),
                                    fill_quote_amount=Decimal(data["fillSz"]) * Decimal(data["fillPx"]),
                                    fill_price=Decimal(data["fillPx"]),
                                    fill_timestamp=int(data["uTime"]) * 1e-3,
                                )
                                self._order_tracker.process_trade_update(trade_update)

                            order_update = OrderUpdate(
                                trading_pair=tracked_order.trading_pair,
                                update_timestamp=int(data["uTime"]) * 1e-3,
                                new_state=order_status,
                                client_order_id=tracked_order.client_order_id,
                                exchange_order_id=str(data["ordId"]),
                            )
                            self._order_tracker.process_order_update(order_update=order_update)

                elif channel == CONSTANTS.OKEX_WS_ACCOUNT_CHANNEL:
                    for data in stream_message.get("data", []):
                        details = data["details"]
                        if details:
                            details = details[0]
                            asset_name = details["ccy"]
                            balance = details["cashBal"]
                            available_balance = details["availBal"]

                            self._account_balances.update({asset_name: Decimal(balance)})
                            self._account_available_balances.update({asset_name: Decimal(available_balance)})

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
                await self._sleep(5.0)

    async def _api_request(self,
                           path_url,
                           method: RESTMethod = RESTMethod.GET,
                           params: Optional[Dict[str, Any]] = None,
                           data: Optional[Dict[str, Any]] = None,
                           is_auth_required: bool = False,
                           limit_id: Optional[str] = None) -> Dict[str, Any]:

        rest_assistant = await self._api_factory.get_rest_assistant()
        url = web_utils.rest_url(path_url)

        return await rest_assistant.execute_request(
            url=url,
            params=params,
            data=data,
            method=method,
            is_auth_required=is_auth_required,
            throttler_limit_id=limit_id if limit_id else path_url,
        )
