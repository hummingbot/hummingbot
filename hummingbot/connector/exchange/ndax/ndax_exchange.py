import asyncio
import logging
import math

from decimal import Decimal
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
)

from hummingbot.connector.exchange.ndax import ndax_constants as CONSTANTS
from hummingbot.connector.exchange.ndax.ndax_auth import NdaxAuth
from hummingbot.connector.exchange.ndax.ndax_in_flight_order import NdaxInFlightOrder
from hummingbot.connector.exchange.ndax.ndax_user_stream_tracker import NdaxUserStreamTracker
from hummingbot.connector.exchange.ndax.ndax_websocket_adaptor import NdaxWebSocketAdaptor
from hummingbot.connector.exchange_base import ExchangeBase

from hummingbot.core.event.events import (
    OrderType, MarketEvent, OrderCancelledEvent, MarketOrderFailureEvent, TradeType, OrderFilledEvent, TradeFee,
    BuyOrderCompletedEvent, SellOrderCompletedEvent,
)
from hummingbot.logger import HummingbotLogger

s_decimal_NaN = Decimal("nan")


class NdaxExchange(ExchangeBase):
    """
    Class to onnect with NDAX exchange. Provides order book pricing, user account tracking and
    trading functionality.
    """

    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 uid: str,
                 api_key: str,
                 secret_key: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True
                 ):
        """
        :param uid: User ID of the account
        :param api_key: The API key to connect to private NDAX APIs.
        :param secret_key: The API secret.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        super().__init__()
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._auth = NdaxAuth(uid=uid, api_key=api_key, secret_key=secret_key)
        # self._order_book_tracker = ProbitOrderBookTracker(trading_pairs=trading_pairs, domain=domain)
        self._user_stream_tracker = NdaxUserStreamTracker(self._auth)
        self._ev_loop = asyncio.get_event_loop()
        self._shared_client = None
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._in_flight_orders = {}
        # self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        # self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        # self._last_poll_timestamp = 0

        # self._status_polling_task = None
        # self._user_stream_tracker_task = None
        # self._user_stream_event_listener_task = None
        # self._trading_rules_polling_task = None

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def in_flight_orders(self) -> Dict[str, NdaxInFlightOrder]:
        return self._in_flight_orders

    def supported_order_types(self) -> List[OrderType]:
        """
        :return: a list of OrderType supported by this connector.
        Note that Market order type is no longer required and will not be used.
        """
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

    def start_tracking_order(self,
                             order_id: str,
                             exchange_order_id: str,
                             trading_pair: str,
                             trade_type: TradeType,
                             price: Decimal,
                             amount: Decimal,
                             order_type: OrderType):
        """
        Starts tracking an order by simply adding it into _in_flight_orders dictionary.
        """
        self._in_flight_orders[order_id] = NdaxInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount
        )

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order by simply removing it from _in_flight_orders dictionary.
        """
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 seconds.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from NDAX. Check API key and network connection."
                )
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Listens to message in _user_stream_tracker.user_stream queue.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                endpoint = NdaxWebSocketAdaptor.endpoint_from_message(event_message)
                payload = NdaxWebSocketAdaptor.payload_from_message(event_message)

                if endpoint == CONSTANTS.ACCOUNT_POSITION_EVENT_ENDPOINT_NAME:
                    self._process_account_position_event(payload)
                elif endpoint == CONSTANTS.ORDER_STATE_EVENT_ENDPOINT_NAME:
                    self._process_order_event_message(payload)
                elif endpoint == CONSTANTS.ORDER_TRADE_EVENT_ENDPOINT_NAME:
                    self._process_trade_event_message(payload)
                else:
                    self.logger().debug(f"Unknown event received from the connector ({event_message})")
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().error(f"Unexpected error in user stream listener loop ({ex})", exc_info=True)
                await asyncio.sleep(5.0)

    def _process_account_position_event(self, account_position_event: Dict[str, Any]):
        token = account_position_event["ProductSymbol"]
        amount = Decimal(str(account_position_event["Amount"]))
        on_hold = Decimal(str(account_position_event["Hold"]))
        self._account_balances[token] = amount
        self._account_available_balances[token] = (amount - on_hold)

    def _process_order_event_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        :param order_msg: The order event message payload
        """
        client_order_id = str(order_msg["ClientOrderId"])
        if client_order_id in self.in_flight_orders:
            tracked_order = self.in_flight_orders[client_order_id]

            # Update order execution status
            tracked_order.last_state = order_msg["OrderState"]

            if tracked_order.is_cancelled:
                self.logger().info(f"Successfully cancelled order {client_order_id}")
                self.trigger_event(MarketEvent.OrderCancelled,
                                   OrderCancelledEvent(
                                       self.current_timestamp,
                                       client_order_id))
                self.stop_tracking_order(client_order_id)
            elif tracked_order.is_failure:
                self.logger().info(f"The market order {client_order_id} has failed according to order status event. "
                                   f"Reason: {order_msg['ChangeReason']}")
                self.trigger_event(MarketEvent.OrderFailure,
                                   MarketOrderFailureEvent(
                                       self.current_timestamp,
                                       client_order_id,
                                       tracked_order.order_type
                                   ))
                self.stop_tracking_order(client_order_id)

    def _process_trade_event_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        :param order_msg: The order event message payload
        """

        client_order_id = str(order_msg["ClientOrderId"])
        if client_order_id in self.in_flight_orders:
            tracked_order = self.in_flight_orders[client_order_id]
            updated = tracked_order.update_with_trade_update(order_msg)

            if updated:
                self.trigger_event(
                    MarketEvent.OrderFilled,
                    OrderFilledEvent(
                        self.current_timestamp,
                        tracked_order.client_order_id,
                        tracked_order.trading_pair,
                        tracked_order.trade_type,
                        tracked_order.order_type,
                        Decimal(str(order_msg["Price"])),
                        Decimal(str(order_msg["Quantity"])),
                        # TODO get the feed by sending a GetTradesHistory API request
                        # TradeFee(0.0, [(tracked_order.quote_asset, Decimal(str(order_msg["fee_amount"])))]),
                        TradeFee(0.0, []),
                        exchange_trade_id=str(order_msg["TradeId"])
                    )
                )
                if (math.isclose(tracked_order.executed_amount_base, tracked_order.amount) or
                        tracked_order.executed_amount_base >= tracked_order.amount):
                    tracked_order.mark_as_filled()
                    self.logger().info(f"The {tracked_order.trade_type.name} order "
                                       f"{tracked_order.client_order_id} has completed "
                                       f"according to order status API")
                    event_tag = (MarketEvent.BuyOrderCompleted if tracked_order.trade_type is TradeType.BUY
                                 else MarketEvent.SellOrderCompleted)
                    event_class = (BuyOrderCompletedEvent if tracked_order.trade_type is TradeType.BUY
                                   else SellOrderCompletedEvent)
                    self.trigger_event(event_tag,
                                       event_class(self.current_timestamp,
                                                   tracked_order.client_order_id,
                                                   tracked_order.base_asset,
                                                   tracked_order.quote_asset,
                                                   tracked_order.fee_asset,
                                                   tracked_order.executed_amount_base,
                                                   tracked_order.executed_amount_quote,
                                                   tracked_order.fee_paid,
                                                   tracked_order.order_type,
                                                   tracked_order.exchange_order_id))
                    self.stop_tracking_order(tracked_order.client_order_id)
