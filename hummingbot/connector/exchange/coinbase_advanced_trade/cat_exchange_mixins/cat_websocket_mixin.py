from typing import Any, AsyncIterable, Dict

from _decimal import Decimal

from hummingbot.connector.exchange.coinbase_advanced_trade import cat_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_cumulative_trade import (
    CoinbaseAdvancedTradeCumulativeUpdate,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_exchange_mixins.cat_exchange_protocols import (
    WebsocketMixinProtocol,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utils import DEFAULT_FEES
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase


class _WebsocketMixinSuperCalls:
    """
    This class is used to call the methods of the super class of a subclass of its Mixin.
    It allows a dynamic search of the methods in the super classes of its Mixin.
    The methods must be defined in one of the super classes defined after its Mixin class.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def iter_user_event_queue(self) -> AsyncIterable[Dict[str, Any]]:
        return super()._iter_user_event_queue()


class WebsocketMixin(_WebsocketMixinSuperCalls):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def _user_stream_event_listener(self: WebsocketMixinProtocol):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are order updates.
        """
        """
        https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-channels#user-channel
        {
          "channel": "user",
          "client_id": "",
          "timestamp": "2023-02-09T20:33:57.609931463Z",
          "sequence_num": 0,
          "events": [
            {
              "type": "snapshot",
              "orders": [
                {
                  "order_id": "XXX",
                  "client_order_id": "YYY",
                  "cumulative_quantity": "0",
                  "leaves_quantity": "0.000994",
                  "avg_price": "0",
                  "total_fees": "0",
                  "status": "OPEN",
                  "product_id": "BTC-USD",
                  "creation_time": "2022-12-07T19:42:18.719312Z",
                  "order_side": "BUY",
                  "order_type": "Limit"
                },
              ]
            }
          ]
        }
        """
        async for event_message in self.iter_user_event_queue():
            print(event_message)
            assert isinstance(event_message, CoinbaseAdvancedTradeCumulativeUpdate)

            fillable_order: InFlightOrder = self.order_tracker.all_fillable_orders.get(event_message.client_order_id)
            updatable_order: InFlightOrder = self.order_tracker.all_updatable_orders.get(
                event_message.client_order_id)

            new_state: OrderState = CONSTANTS.ORDER_STATE[event_message.status]
            partial: bool = event_message.remainder_base_amount > 0
            new_state = OrderState.PARTIALLY_FILLED if partial else new_state

            if fillable_order is not None and any((new_state == OrderState.PARTIALLY_FILLED,
                                                   new_state == OrderState.OPEN)):
                fill_base_amount: Decimal = event_message.cumulative_base_amount - fillable_order.executed_amount_base
                transaction_fee: Decimal = Decimal(event_message.cumulative_fee) - fillable_order.cumulative_fee_paid(
                    "USD")
                total_price: Decimal = event_message.average_price * event_message.cumulative_base_amount
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=DEFAULT_FEES,
                    trade_type=fillable_order.trade_type,
                    percent_token="USD",
                    flat_fees=[TokenAmount(amount=Decimal(transaction_fee), token="USD")]
                )

                try:
                    fill_price: Decimal = (total_price - fillable_order.average_executed_price) / fill_base_amount
                except ZeroDivisionError:
                    raise ValueError("Fill base amount is zero for an InFlightOrder, this is unexpected")

                trade_update = TradeUpdate(
                    trade_id="",  # Coinbase does not provide matching trade id
                    client_order_id=event_message.client_order_id,
                    exchange_order_id=event_message.exchange_order_id,
                    trading_pair=fillable_order.trading_pair,
                    fee=fee,
                    fill_base_amount=fill_base_amount,
                    fill_quote_amount=fill_base_amount * fill_price,
                    fill_price=fill_price,
                    fill_timestamp=event_message.fill_timestamp,
                )
                # Maybe we should not emit a TradeUpdate?
                # TODO: Check if we should emit a TradeUpdate in this case
                self.order_tracker.process_trade_update(trade_update)

            if updatable_order is not None:
                order_update = OrderUpdate(
                    trading_pair=updatable_order.trading_pair,
                    update_timestamp=event_message.fill_timestamp,
                    new_state=new_state,
                    client_order_id=event_message.client_order_id,
                    exchange_order_id=event_message.exchange_order_id,
                )
                self.order_tracker.process_order_update(order_update)
