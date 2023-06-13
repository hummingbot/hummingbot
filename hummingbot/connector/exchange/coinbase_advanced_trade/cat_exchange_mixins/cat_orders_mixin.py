from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from _decimal import Decimal

from hummingbot.connector.exchange.coinbase_advanced_trade import cat_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_enums import (
    CoinbaseAdvancedTradeOrderSide,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_order_types import (
    COINBASE_ADVANCED_TRADE_ORDER_TYPE_ENUM_MAPPING,
    CoinbaseAdvancedTradeAPIOrderConfiguration,
    CoinbaseAdvancedTradeOrderType,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_request_types import (
    CoinbaseAdvancedTradeCreateOrderRequest,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_exchange_mixins.cat_exchange_protocols import (
    CoinbaseAdvancedTradeAPICallsMixinProtocol,
    CoinbaseAdvancedTradeOrdersMixinProtocol,
    CoinbaseAdvancedTradeTradingPairsMixinProtocol,
    CoinbaseAdvancedTradeUtilitiesMixinProtocol,
    CoinbaseAdvancedTradeWebsocketMixinProtocol,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utils import DEFAULT_FEES
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_web_utils import (
    get_timestamp_from_exchange_time,
    set_exchange_time_from_timestamp,
)
from hummingbot.connector.exchange_base import s_decimal_NaN
from hummingbot.connector.utils import TradeFillOrderDetails
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent
from hummingbot.core.utils.async_utils import safe_gather


class _OrdersMixinSuperCalls:
    """
    This class is used to call the methods of the super class of a subclass of its Mixin.
    It allows a dynamic search of the methods in the super classes of its Mixin.
    The methods must be defined in one of the super classes defined after its Mixin class.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def current_trade_fills(self) -> Set:
        # Defined in ConnectorBase
        return super()._current_trade_fills

    @property
    def exchange_order_ids(self) -> Dict:
        # Defined in ConnectorBase
        return super()._exchange_order_ids

    def is_confirmed_new_order_filled_event(self, exchange_trade_id: str, exchange_order_id: str, trading_pair: str):
        # Defined in ConnectorBase
        return super().is_confirmed_new_order_filled_event(exchange_trade_id, exchange_order_id, trading_pair)

    def trigger_event(self, event_tag: Enum, message: Any):
        # Defined in PubSub
        return super().trigger_event(event_tag, message)


class _OrdersMixinProtocol(CoinbaseAdvancedTradeTradingPairsMixinProtocol,
                           CoinbaseAdvancedTradeUtilitiesMixinProtocol,
                           CoinbaseAdvancedTradeAPICallsMixinProtocol,
                           CoinbaseAdvancedTradeWebsocketMixinProtocol,
                           CoinbaseAdvancedTradeOrdersMixinProtocol
                           ):
    _last_trades_poll_timestamp: float


def _create_trade_updates(trade_list: List[Any], client_order_id: str) -> List[TradeUpdate]:
    trade_updates = []
    for trade in trade_list:
        quote_token: str = trade["symbol"].split("-")[1]
        fee = AddedToCostTradeFee(flat_fees=[TokenAmount(amount=Decimal(trade["commission"]),
                                                         token=quote_token)])
        trade_update = TradeUpdate(
            trade_id=str(trade["id"]),
            client_order_id=client_order_id,
            exchange_order_id=str(trade["orderId"]),
            trading_pair=trade["symbol"],
            fee=fee,
            fill_base_amount=Decimal(trade["qty"]),
            fill_quote_amount=Decimal(trade["quoteQty"]),
            fill_price=Decimal(trade["price"]),
            fill_timestamp=trade["time"] * 1e-3,
        )
        trade_updates.append(trade_update)
    return trade_updates


class OrdersMixin(_OrdersMixinSuperCalls):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._last_trades_poll_timestamp: float = 0.0

    @staticmethod
    def supported_order_types() -> List[OrderType]:
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

    @staticmethod
    def to_coinbase_advanced_trade_order_type(order_type: OrderType) -> str:
        return COINBASE_ADVANCED_TRADE_ORDER_TYPE_ENUM_MAPPING.inverse.get(order_type)

    @staticmethod
    def to_hb_order_type(order_type: CoinbaseAdvancedTradeOrderType) -> OrderType:
        return COINBASE_ADVANCED_TRADE_ORDER_TYPE_ENUM_MAPPING.get(order_type)

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_STATUS_NOT_FOUND_ERROR_CODE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return "UNKNOWN_CANCEL_ORDER" in str(cancelation_exception)

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> AddedToCostTradeFee:
        return AddedToCostTradeFee(DEFAULT_FEES)

    async def _place_order(self: _OrdersMixinProtocol,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        """
        Places an order with the exchange and returns the order ID and the timestamp of the order.
        reference: https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_postorder
        Maximum open orders: 500

        Example:
            payload = json.dumps({
              "client_order_id": "client_order_id",
              "product_id": "product_id",
              "side": "BUY",
              "order_configuration": {
                "market_market_ioc": {
                  "quote_size": "1",
                  "base_size": "1"
                },
                "limit_limit_gtc": {
                  "base_size": "1",
                  "limit_price": "1",
                  "post_only": False
                },
                "limit_limit_gtd": {
                  "base_size": "1",
                  "limit_price": "1",
                  "end_time": "2023-05-04T16:17",
                  "post_only": True
                },
                "stop_limit_stop_limit_gtc": {
                  "base_size": "1",
                  "limit_price": "1",
                  "stop_price": "1",
                  "stop_direction": "STOP_DIRECTION_STOP_UP"
                },
                "stop_limit_stop_limit_gtd": {
                  "base_size": "1",
                  "limit_price": "1",
                  "stop_price": "1",
                  "end_time": "2023-05-04T16:17",
                  "stop_direction": "STOP_DIRECTION_STOP_DOWN"
                }
              }
            })

        """
        product_id = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        side = CoinbaseAdvancedTradeOrderSide.BUY if trade_type is TradeType.BUY else CoinbaseAdvancedTradeOrderSide.SELL

        order_configuration: CoinbaseAdvancedTradeAPIOrderConfiguration = \
            CoinbaseAdvancedTradeAPIOrderConfiguration.create(
                order_type,
                base_size=amount,
                quote_size=amount * price,
                limit_price=price,
                **kwargs
            )
        try:
            order = CoinbaseAdvancedTradeCreateOrderRequest(
                client_order_id=order_id,
                product_id=product_id,
                side=side,
                order_configuration=order_configuration
            )
        except Exception as e:
            print(order_configuration)
            print(f"Exception {e}")
            raise

        order_result: Dict = await self.api_post(
            path_url=CONSTANTS.ORDER_EP,
            data=order.to_dict_for_json(),
            is_auth_required=True)

        return order_result["order_id"], self.time_synchronizer.time()

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """
        Cancels an order with the exchange and returns the order ID and the timestamp of the order.
        https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_cancelorders

        """
        # Coinbase Advanced Trade seems to require the exchange order ID to cancel an order
        result = await self._place_cancels(order_ids=[tracked_order.exchange_order_id])
        if result[0]["success"]:
            return True
        else:
            if result[0]["failure_reason"] == "UNKNOWN_CANCEL_ORDER":
                # return False
                raise Exception(
                    f"Order {order_id}:{tracked_order.exchange_order_id} not found on the exchange. UNKNOWN_CANCEL_ORDER")

    async def _place_cancels(self: _OrdersMixinProtocol, order_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Cancels an order with the exchange and returns the order ID and the timestamp of the order.
        https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_cancelorders

        """
        api_data = {
            "order_ids": order_ids
        }
        cancel_result: Dict[str, Any] = await self.api_post(
            path_url=CONSTANTS.BATCH_CANCEL_EP,
            data=api_data,
            is_auth_required=True)

        return [r for r in cancel_result["results"]]

    async def _request_order_status(self: _OrdersMixinProtocol, tracked_order: InFlightOrder) -> OrderUpdate:
        """
        Queries Order status by order_id.
        https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_gethistoricalorder

        """
        updated_order_data = await self.api_get(
            path_url=CONSTANTS.GET_ORDER_STATUS_EP.format(order_id=tracked_order.exchange_order_id),
            params={},
            is_auth_required=True,
            limit_id=CONSTANTS.GET_ORDER_STATUS_RATE_LIMIT_ID,
        )

        status: str = updated_order_data['order']["status"]
        completion: Decimal = Decimal(updated_order_data['order']["completion_percentage"])
        if status == "OPEN" and completion < Decimal("100"):
            status = "PARTIALLY_FILLED"
        new_state = CONSTANTS.ORDER_STATE[status]

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(updated_order_data['order']["order_id"]),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=self.time_synchronizer.time(),
            new_state=new_state,
        )

        return order_update

    async def _update_order_fills_from_trades(self: _OrdersMixinProtocol):
        """
        This is intended to be a backup measure to get filled events with trade ID for orders,
        in case Binance's user stream events are not working.
        NOTE: It is not required to copy this functionality in other connectors.
        This is separated from _update_order_status which only updates the order status without producing filled
        events, since Binance's get order endpoint does not return trade IDs.
        The minimum poll interval for order status is 10 seconds.
        """
        small_interval_last_tick: float = self.last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        small_interval_current_tick: float = self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        long_interval_last_tick: float = self.last_poll_timestamp / self.LONG_POLL_INTERVAL
        long_interval_current_tick: float = self.current_timestamp / self.LONG_POLL_INTERVAL

        in_flight_orders: Dict[str, InFlightOrder] = self.in_flight_orders

        if (long_interval_current_tick > long_interval_last_tick
                or (in_flight_orders and small_interval_current_tick > small_interval_last_tick)):
            query_time = set_exchange_time_from_timestamp(self._last_trades_poll_timestamp, "s")
            self._last_trades_poll_timestamp = self.time_synchronizer.time()
            order_by_exchange_id_map = {}
            for order in self.order_tracker.all_fillable_orders.values():
                order_by_exchange_id_map[order.exchange_order_id] = order

            tasks = []
            trading_pairs = self.trading_pairs
            for trading_pair in trading_pairs:
                product_id = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                params = {
                    "product_id": product_id
                }
                if self.last_poll_timestamp > 0:
                    params["start_sequence_timestamp"] = query_time
                tasks.append(self.api_get(
                    path_url=CONSTANTS.FILLS_EP,
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
                    exchange_order_id = trade["order_id"]
                    quote_token: str = trading_pair.split("-")[1]
                    fee = AddedToCostTradeFee(flat_fees=[TokenAmount(amount=Decimal(trade["commission"]),
                                                                     token=quote_token)])
                    if exchange_order_id in order_by_exchange_id_map:
                        # This is a fill for a tracked order
                        tracked_order = order_by_exchange_id_map[exchange_order_id]
                        trade_update = TradeUpdate(
                            trade_id=str(trade["trade_id"]),
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=exchange_order_id,
                            trading_pair=trading_pair,
                            fee=fee,
                            fill_base_amount=Decimal(trade["size"]),
                            fill_quote_amount=Decimal("0" if trade["size_in_quote"] is True else trade["size"]),
                            fill_price=Decimal(trade["price"]),
                            fill_timestamp=trade["trade_time"],
                            is_taker=False
                        )
                        self.order_tracker.process_trade_update(trade_update)

                    elif self.is_confirmed_new_order_filled_event(str(trade["trade_id"]),
                                                                  str(exchange_order_id),
                                                                  trading_pair):
                        # This is a fill of an order registered in the DB but not tracked anymore
                        self.current_trade_fills.add(TradeFillOrderDetails(
                            market=self.display_name,
                            exchange_trade_id=str(trade["trade_id"]),
                            symbol=trading_pair))
                        self.trigger_event(
                            MarketEvent.OrderFilled,
                            OrderFilledEvent(
                                timestamp=float(get_timestamp_from_exchange_time(trade["trade_time"], "s")),
                                order_id=self.exchange_order_ids.get(str(trade["order_id"]), None),
                                trading_pair=trading_pair,
                                trade_type=TradeType.BUY if trade["side"] == "BUY" else TradeType.SELL,
                                order_type=OrderType.LIMIT,
                                price=Decimal(trade["price"]),
                                amount=Decimal(trade["size"]),
                                trade_fee=fee,
                                exchange_trade_id=str(trade["trade_id"])
                            ))
                        self.logger().info(f"Recreating missing trade in TradeFill: {trade}")

    async def _all_trade_updates_for_order(self: _OrdersMixinProtocol, order: InFlightOrder) -> List[TradeUpdate]:
        """
        Queries all trades for an order.
        https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getfills
        """
        trade_updates = []
        if order.exchange_order_id is not None:
            order_id = int(order.exchange_order_id)
            product_id = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            all_fills_response: Dict[str, Any] = await self.api_get(
                path_url=CONSTANTS.FILLS_EP,
                params={
                    "product_id": product_id,
                    "order_id": order_id
                },
                is_auth_required=True)

            for trade in all_fills_response["fills"]:
                exchange_order_id = trade["order_id"]
                quote_token: str = order.trading_pair.split("-")[1]
                fee = AddedToCostTradeFee(flat_fees=[TokenAmount(amount=Decimal(trade["commission"]),
                                                                 token=quote_token)])
                trade_update = TradeUpdate(
                    trade_id=str(trade["trade_id"]),
                    client_order_id=order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=order.trading_pair,
                    fee=fee,
                    fill_base_amount=Decimal(trade["size"]),
                    fill_quote_amount=Decimal("0" if trade["size_in_quote"] is True else trade["size"]),
                    fill_price=Decimal(trade["price"]),
                    fill_timestamp=trade["trade_time"],
                )
                trade_updates.append(trade_update)

        return trade_updates
