import json
from abc import ABC
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

from _decimal import Decimal

from hummingbot.connector.exchange.coinbase_advanced_trade import cat_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_order_types import (
    coinbase_advanced_trade_order_type_mapping,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_exchange_mixins.cat_api_calls_mixin import (
    _APICallsMixinSuperCalls,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_exchange_mixins.cat_trading_pairs_rules_mixin import (
    _TradingPairsMixinAbstract,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_exchange_mixins.cat_utilities_abstract import (
    _UtilitiesMixinAbstract,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utils import DEFAULT_FEES
from hummingbot.connector.exchange_base import s_decimal_NaN
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount


class _OrdersMixin(_APICallsMixinSuperCalls,
                   _UtilitiesMixinAbstract,
                   _TradingPairsMixinAbstract, ABC):

    @staticmethod
    def supported_order_types() -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> AddedToCostTradeFee:
        return AddedToCostTradeFee(DEFAULT_FEES)

    @staticmethod
    def _is_order_not_found_during_cancelation_error(cancellation_exception: Exception) -> bool:
        return CONSTANTS.ORDER_STATUS_NOT_FOUND_ERROR_CODE in str(cancellation_exception)

    async def _place_order(self,
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
        side = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        quote_size = str(amount * price)
        base_size = str(amount)
        limit_price = str(price)

        selected_order_type = coinbase_advanced_trade_order_type_mapping[order_type]
        order = selected_order_type(client_order_id=order_id,
                                    product_id=product_id,
                                    side=side,
                                    base_size=base_size,
                                    quote_size=quote_size,
                                    limit_price=limit_price,
                                    **kwargs)

        # The errors are intercepted and handled in the _api_post method
        order_result: Dict = await self._api_post(
            path_url=CONSTANTS.ORDER_EP,
            data=json.dumps(asdict(order), default=str),
            is_auth_required=True)

        return order_result["order_id"], self._time_s()

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """
        Cancels an order with the exchange and returns the order ID and the timestamp of the order.
        https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_cancelorders

        """
        return await self._place_cancels(order_ids=[order_id])

    async def _place_cancels(self, order_ids: List[str]):
        """
        Cancels an order with the exchange and returns the order ID and the timestamp of the order.
        https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_cancelorders

        """
        api_data = {
            "order_ids": order_ids
        }
        cancel_result: Dict[str, Any] = await self._api_post(
            path_url=CONSTANTS.BATCH_CANCEL_EP,
            data=api_data,
            is_auth_required=True)

        return cancel_result["success"]

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """
        Queries Order status by order_id.
        https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_gethistoricalorder

        """
        updated_order_data = await self._api_get(
            path_url=CONSTANTS.GET_ORDER_STATUS_EP,
            params={"order_id": tracked_order.client_order_id},
            is_auth_required=True)

        status: str = updated_order_data["status"]
        completion: Decimal = Decimal(updated_order_data["completion_percentage"])
        if status == "OPEN" and completion < Decimal("100"):
            status = "PARTIALLY_FILLED"
        new_state = CONSTANTS.ORDER_STATE[status]

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(updated_order_data["order_id"]),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=self._time_s(),
            new_state=new_state,
        )

        return order_update

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        """
        Queries all trades for an order.
        https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getfills
        """
        trade_updates = []
        if order.exchange_order_id is not None:
            order_id = int(order.exchange_order_id)
            product_id = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            all_fills_response = await self._api_get(
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
                    trading_pair=product_id,
                    fee=fee,
                    fill_base_amount=Decimal(trade["size"]),
                    fill_quote_amount=Decimal("0" if trade["size_in_quote"] is True else trade["size"]),
                    fill_price=Decimal(trade["price"]),
                    fill_timestamp=trade["trade_time"] * 1e-3,
                )
                trade_updates.append(trade_update)

        return trade_updates
