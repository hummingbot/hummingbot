import decimal
from typing import Any, AsyncIterable, Optional

from _decimal import Decimal
from pydantic.annotated_types import Dict

from hummingbot.connector.exchange.coinbase_advanced_trade import cat_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_cumulative_trade import (
    CoinbaseAdvancedTradeCumulativeUpdate,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_exchange_mixins.cat_exchange_protocols import (
    CoinbaseAdvancedTradeUtilitiesMixinProtocol,
    CoinbaseAdvancedTradeWebsocketMixinProtocol,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_utils import DEFAULT_FEES
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase


class _WebLoggerProtocol(
    CoinbaseAdvancedTradeWebsocketMixinProtocol,
    CoinbaseAdvancedTradeUtilitiesMixinProtocol,
):
    pass


class WebsocketMixin:
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def iter_user_event_queue(self: CoinbaseAdvancedTradeWebsocketMixinProtocol) -> AsyncIterable[Dict[str, Any]]:
        return self._iter_user_event_queue()

    async def _user_stream_event_listener(self: _WebLoggerProtocol):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are order updates.
        """
        async for event_message in self.iter_user_event_queue():
            try:
                assert isinstance(event_message, CoinbaseAdvancedTradeCumulativeUpdate)
            except AssertionError:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)
                continue

            fillable_order: InFlightOrder = self.order_tracker.all_fillable_orders.get(event_message.client_order_id)
            updatable_order: InFlightOrder = self.order_tracker.all_updatable_orders.get(
                event_message.client_order_id)

            new_state: OrderState = CONSTANTS.ORDER_STATE[event_message.status]
            partial: bool = all((event_message.cumulative_base_amount > Decimal("0"),
                                 event_message.remainder_base_amount > Decimal("0"),
                                 new_state == OrderState.OPEN))
            new_state = OrderState.PARTIALLY_FILLED if partial else new_state

            if fillable_order is not None and any((
                    new_state == OrderState.OPEN,
                    new_state == OrderState.PARTIALLY_FILLED,
                    new_state == OrderState.FILLED,
            )):
                transaction_fee: Decimal = Decimal(event_message.cumulative_fee) - fillable_order.cumulative_fee_paid(
                    "USD")
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=DEFAULT_FEES,
                    trade_type=fillable_order.trade_type,
                    percent_token="USD",
                    flat_fees=[TokenAmount(amount=Decimal(transaction_fee), token="USD")]
                )

                avg_exc_price: Optional[Decimal] = fillable_order.average_executed_price
                avg_exc_price: Decimal = avg_exc_price if avg_exc_price is not None else Decimal("0")
                fill_base_amount: Decimal = event_message.cumulative_base_amount - fillable_order.executed_amount_base
                if fill_base_amount == Decimal("0"):
                    fill_price: Decimal = avg_exc_price
                else:
                    total_price: Decimal = event_message.average_price * event_message.cumulative_base_amount
                    try:
                        fill_price: Decimal = (total_price - avg_exc_price) / fill_base_amount
                    except (ZeroDivisionError, decimal.InvalidOperation):
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
