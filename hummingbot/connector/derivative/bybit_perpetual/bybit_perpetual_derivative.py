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

from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_in_flight_order import BybitPerpetualInFlightOrder
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_order_book_tracker import \
    BybitPerpetualOrderBookTracker
from hummingbot.connector.perpetual_trading import PerpetualTrading
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.event.events import (
    FundingInfo,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderType,
    PositionAction,
    PositionMode,
    TradeType,
)
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger


s_decimal_NaN = Decimal("nan")
s_decimal_0 = Decimal(0)


class BybitPerpetualDerivative(ExchangeBase, PerpetualTrading):

    _logger = None

    _DEFAULT_TIME_IN_FORCE = "GoodTillCancel"

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 bybit_perpetual_api_key: str = None,
                 bybit_perpetual_secret_key: str = None,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: Optional[str] = None):

        ExchangeBase.__init__(self)
        PerpetualTrading.__init__(self)

        self._trading_pairs = trading_pairs
        self._trading_required = trading_required
        self._domain = domain
        self._shared_client = None

        self._auth: BybitPerpetualAuth = BybitPerpetualAuth(api_key=bybit_perpetual_api_key,
                                                            secret_key=bybit_perpetual_secret_key)
        self._order_book_tracker = BybitPerpetualOrderBookTracker(
            session=asyncio.get_event_loop().run_until_complete(self._aiohttp_client()),
            trading_pairs=trading_pairs,
            domain=domain)
        # self._user_stream_tracker = BybitPerpetualUserStreamTracker(self._auth, domain=domain)
        self._in_flight_orders = {}

        # Tasks
        self._funding_info_polling_task = None
        self._funding_fee_polling_task = None

    @property
    def in_flight_orders(self) -> Dict[str, BybitPerpetualInFlightOrder]:
        return self._in_flight_orders

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
        self._order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        self._funding_info_polling_task = safe_ensure_future(self._funding_info_polling_loop())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            # self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())
            self._user_funding_fee_polling_task = safe_ensure_future(self._user_funding_fee_polling_loop())

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
        if self._funding_info_polling_task is not None:
            self._funding_info_polling_task.cancel()
            self._funding_info_polling_task = None
        if self._user_funding_fee_polling_task is not None:
            self._user_funding_fee_polling_task.cancel()
            self._user_funding_fee_polling_task = None

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector
        """
        return [OrderType.LIMIT, OrderType.MARKET]

    async def _trading_pair_symbol(self, trading_pair: str) -> str:
        return await self._order_book_tracker.trading_pair_symbol(trading_pair)

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

        response_status = response.status
        if response_status != 200 or (isinstance(parsed_response, dict) and not parsed_response.get("result", True)):
            self.logger().error(f"Error fetching data from {url}. HTTP status is {response_status}. "
                                f"Message: {parsed_response} "
                                f"Params: {params} "
                                f"Data: {body}")
            raise Exception(f"Error fetching data from {url}. HTTP status is {response_status}. "
                            f"Message: {parsed_response} "
                            f"Params: {params} "
                            f"Data: {body}")
        return parsed_response

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        """
        Returns a price step, a minimum price increment for a given trading pair.
        :param trading_pair: trading pair for which the price quantum will be calculated
        :param price: the actual price
        """
        trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        """
        Returns an order amount step, a minimum amount increment for a given trading pair.
        :param trading_pair: trading pair for which the size quantum will be calculated
        :param order_size: the actual amount
        """
        trading_rule = self._trading_rules[trading_pair]
        return Decimal(trading_rule.min_base_amount_increment)

    def start_tracking_order(self, order_id: str, exchange_order_id: str, trading_pair: str, trading_type: object,
                             price: object, amount: object, order_type: object, leverage: int, position: str):
        self._in_flight_orders[order_id] = BybitPerpetualInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trading_type,
            price=price,
            amount=amount,
            leverage=leverage,
            position=position)

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order by simply removing it from _in_flight_orders dictionary.
        :param order_id" client order id of the order that should no longer be tracked
        """
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    async def _create_order(self,
                            trade_type: TradeType,
                            order_id: str,
                            trading_pair: str,
                            amount: Decimal,
                            position_action: PositionAction,
                            price: Decimal = s_decimal_0,
                            order_type: OrderType = OrderType.MARKET):
        """
        Calls create-order API end point to place an order, starts tracking the order and triggers order created event.
        :param trade_type: BUY or SELL
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The market to place order
        :param amount: The order amount (in base token value)
        :param amount: Action to take for the position (OPEN or CLOSE)
        :param price: The order price
        :param order_type: The order type
        """
        trading_rule: TradingRule = self._trading_rules[trading_pair]

        if position_action not in [PositionAction.OPEN, PositionAction.CLOSE]:
            raise ValueError("Specify either OPEN_POSITION or CLOSE_POSITION position_action to create an order")

        try:
            amount: Decimal = self.quantize_order_amount(trading_pair, amount)
            if amount < trading_rule.min_order_size:
                raise ValueError(f"{trade_type.name} order amount {amount} is lower than the minimum order size "
                                 f"{trading_rule.min_order_size}.")

            params = {
                "side": "Buy" if trade_type == TradeType.BUY else "Sell",
                "symbol": await self._trading_pair_symbol(trading_pair),
                "qty": amount,
                "time_in_force": self._DEFAULT_TIME_IN_FORCE,
                "order_link_id": order_id,
            }

            if order_type.is_limit_type():
                price: Decimal = self.quantize_order_price(trading_pair, price)
                params.update({
                    "order_type": "Limit",
                    "price": price,
                })
            else:
                params.update({
                    "order_type": "Market"
                })

            self.start_tracking_order(order_id,
                                      None,
                                      trading_pair,
                                      trade_type,
                                      price,
                                      amount,
                                      order_type,
                                      self.get_leverage(trading_pair),
                                      position_action.name)

            send_order_results = await self._api_request(
                method="POST",
                path_url=CONSTANTS.PLACE_ACTIVE_ORDER_ENDPOINT,
                body=params,
                is_auth_required=True
            )

            if send_order_results["ret_code"] != 0:
                raise ValueError(f"Order is rejected by the API. "
                                 f"Parameters: {params} Error Msg: {send_order_results['ret_msg']}")

            result = send_order_results["result"]
            exchange_order_id = str(result["order_id"])

            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type.name} {trade_type.name} order {order_id} for "
                                   f"{amount} {trading_pair}.")
                tracked_order.update_exchange_order_id(exchange_order_id)

            # TODO the event should be triggered once the order creation is confirmed by the exchange
            # since they process requests asynchronously

            # event_tag = MarketEvent.BuyOrderCreated if trade_type is TradeType.BUY else MarketEvent.SellOrderCreated
            # event_class = BuyOrderCreatedEvent if trade_type is TradeType.BUY else SellOrderCreatedEvent
            # self.trigger_event(event_tag,
            #                    event_class(
            #                        self.current_timestamp,
            #                        order_type,
            #                        trading_pair,
            #                        amount,
            #                        price,
            #                        order_id,
            #                        leverage=self.get_leverage(trading_pair),
            #                        position=position_action.name
            #                    ))

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.stop_tracking_order(order_id)
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(self.current_timestamp, order_id, order_type))
            self.logger().network(
                f"Error submitting {trade_type.name} {order_type.name} order to Bybit Perpetual for "
                f"{amount} {trading_pair} {price}. Error: {str(e)}",
                exc_info=True,
                app_warning_msg="Error submitting order to Bybit Perpetual. "
            )

    def buy(self, trading_pair: str, amount: Decimal, order_type: OrderType = OrderType.MARKET,
            price: Decimal = s_decimal_NaN, **kwargs) -> str:
        """
        Buys an amount of base asset as specified in the trading pair. This function returns immediately.
        To see an actual order, wait for a BuyOrderCreatedEvent.
        :param trading_pair: The market (e.g. BTC-CAD) to buy from
        :param amount: The amount in base token value
        :param order_type: The order type
        :param price: The price in which the order is to be placed at
        :returns: A new client order id
        """
        order_id: str = bybit_utils.get_new_client_order_id(True, trading_pair)
        safe_ensure_future(self._create_order(trade_type=TradeType.BUY,
                                              trading_pair=trading_pair,
                                              order_id=order_id,
                                              amount=amount,
                                              price=price,
                                              order_type=order_type,
                                              position_action=kwargs["position_action"]
                                              ))
        return order_id

    def sell(self, trading_pair: str, amount: Decimal, order_type: OrderType = OrderType.MARKET,
             price: Decimal = s_decimal_NaN, **kwargs) -> str:
        """
        Sells an amount of base asset as specified in the trading pair. This function returns immediately.
        To see an actual order, wait for a BuyOrderCreatedEvent.
        :param trading_pair: The market (e.g. BTC-CAD) to buy from
        :param amount: The amount in base token value
        :param order_type: The order type
        :param price: The price in which the order is to be placed at
        :returns: A new client order id
        """
        order_id: str = bybit_utils.get_new_client_order_id(False, trading_pair)
        safe_ensure_future(self._create_order(trade_type=TradeType.SELL,
                                              trading_pair=trading_pair,
                                              order_id=order_id,
                                              amount=amount,
                                              price=price,
                                              order_type=order_type,
                                              position_action=kwargs["position_action"]
                                              ))
        return order_id

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
