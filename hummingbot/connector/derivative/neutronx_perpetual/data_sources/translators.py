import time
from decimal import Decimal
from typing import Iterable, Optional, Union

from bidict import bidict
from neutronx_sdk.indexer import FillV1, OrderbookV1, OrderV1, PositionV1, TickerV1, TradeV1, compact_pair
from neutronx_sdk.models import POSITION_SIDE_LONG, Market, Order, Position as ChainPosition
from neutronx_sdk.orders import Side

from hummingbot.connector.derivative.neutronx_perpetual import neutronx_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionSide, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase, TradeFeeSchema


def to_trading_pair(exchange_pair: str) -> str:
    return exchange_pair.replace("/", "-")


def to_exchange_pair(trading_pair: str) -> str:
    return trading_pair.replace("-", "/")


def active_markets(markets: Iterable[Market]) -> list:
    return [market for market in markets if market.is_active]


def symbol_map(markets: Iterable[Market]) -> bidict:
    return bidict({market.pair: to_trading_pair(market.pair) for market in active_markets(markets)})


def compact_lookup(markets: Iterable[Market]) -> dict:
    return {compact_pair(market.pair): to_trading_pair(market.pair) for market in markets}


def to_side(trade_type: TradeType) -> Side:
    return Side.BUY if trade_type is TradeType.BUY else Side.SELL


def trading_rule(market: Market, min_notional: Decimal) -> TradingRule:
    return TradingRule(
        trading_pair=to_trading_pair(market.pair),
        min_order_size=market.min_quantity,
        min_price_increment=market.tick_size if market.tick_size > 0 else CONSTANTS.DEFAULT_PRICE_INCREMENT,
        min_base_amount_increment=CONSTANTS.QUANTITY_INCREMENT,
        min_notional_size=min_notional,
        supports_market_orders=True,
        buy_order_collateral_token=CONSTANTS.QUOTE_ASSET,
        sell_order_collateral_token=CONSTANTS.QUOTE_ASSET,
    )


def order_state(status: str) -> OrderState:
    return CONSTANTS.ORDER_STATE.get(status.upper(), OrderState.OPEN)


def settled_state(status: str, chain_quantity: Decimal, requested_amount: Decimal) -> OrderState:
    state = order_state(status)
    if state is OrderState.FILLED and requested_amount - chain_quantity >= CONSTANTS.QUANTITY_INCREMENT:
        return OrderState.CANCELED
    return state


def filled_amount(status: str, quantity: Decimal, filled: Decimal) -> Decimal:
    return quantity if order_state(status) is OrderState.FILLED else filled


def order_update(order: Union[Order, OrderV1], in_flight: InFlightOrder, timestamp: float) -> OrderUpdate:
    return OrderUpdate(
        trading_pair=in_flight.trading_pair,
        update_timestamp=timestamp,
        new_state=settled_state(order.status, order.quantity, in_flight.amount),
        client_order_id=in_flight.client_order_id,
        exchange_order_id=str(order.order_id),
    )


def trade_update(fill: FillV1, order: InFlightOrder, fee_schema: TradeFeeSchema) -> TradeUpdate:
    is_taker = fill.is_taker if fill.is_taker is not None else order.order_type is not OrderType.LIMIT_MAKER
    fee = TradeFeeBase.new_perpetual_fee(
        fee_schema=fee_schema,
        position_action=PositionAction.CLOSE if order.position is PositionAction.CLOSE else PositionAction.OPEN,
        percent_token=CONSTANTS.QUOTE_ASSET,
        flat_fees=[TokenAmount(token=CONSTANTS.QUOTE_ASSET, amount=fill.fee)],
    )
    return TradeUpdate(
        trade_id=fill.fill_id,
        client_order_id=order.client_order_id,
        exchange_order_id=str(fill.order_id),
        trading_pair=order.trading_pair,
        fill_timestamp=fill.time.timestamp(),
        fill_price=fill.price,
        fill_base_amount=fill.quantity,
        fill_quote_amount=fill.price * fill.quantity,
        fee=fee,
        is_taker=is_taker,
    )


def to_position(position: Union[ChainPosition, PositionV1], trading_pair: str) -> Position:
    side = PositionSide.LONG if position.side == POSITION_SIDE_LONG else PositionSide.SHORT
    return Position(
        trading_pair=trading_pair,
        position_side=side,
        unrealized_pnl=position.unrealized_pnl if position.unrealized_pnl is not None else Decimal(0),
        entry_price=position.entry_price,
        amount=position.quantity if side is PositionSide.LONG else -position.quantity,
        leverage=position.leverage,
    )


def funding_info(ticker: TickerV1, trading_pair: str) -> FundingInfo:
    mark = ticker.mark_price if ticker.mark_price is not None else ticker.last_price or Decimal(0)
    return FundingInfo(
        trading_pair=trading_pair,
        index_price=mark,
        mark_price=mark,
        next_funding_utc_timestamp=int(ticker.next_funding_at.timestamp()) if ticker.next_funding_at else 0,
        rate=ticker.funding_rate if ticker.funding_rate is not None else Decimal(0),
    )


def funding_info_update(ticker: TickerV1, trading_pair: str) -> FundingInfoUpdate:
    return FundingInfoUpdate(
        trading_pair=trading_pair,
        index_price=ticker.mark_price,
        mark_price=ticker.mark_price,
        next_funding_utc_timestamp=int(ticker.next_funding_at.timestamp()) if ticker.next_funding_at else None,
        rate=ticker.funding_rate,
    )


def snapshot_message(book: OrderbookV1, trading_pair: str, update_id: int, timestamp: float) -> OrderBookMessage:
    return OrderBookMessage(
        OrderBookMessageType.SNAPSHOT,
        {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": [[float(level.price), float(level.quantity)] for level in book.bids],
            "asks": [[float(level.price), float(level.quantity)] for level in book.asks],
        },
        timestamp=timestamp,
    )


def trade_side(trade: TradeV1, mid_price: Optional[Decimal]) -> TradeType:
    if trade.taker_side is not None:
        return TradeType.BUY if trade.taker_side == Side.BUY else TradeType.SELL
    if mid_price is None or not mid_price.is_finite():
        return TradeType.BUY
    return TradeType.BUY if trade.price >= mid_price else TradeType.SELL


def trade_message(trade: TradeV1, trading_pair: str, mid_price: Optional[Decimal]) -> OrderBookMessage:
    timestamp = trade.time.timestamp()
    return OrderBookMessage(
        OrderBookMessageType.TRADE,
        {
            "trading_pair": trading_pair,
            "trade_type": float(trade_side(trade, mid_price).value),
            "trade_id": trade.trade_id,
            "update_id": int(timestamp * 1e3),
            "price": float(trade.price),
            "amount": float(trade.quantity),
        },
        timestamp=timestamp,
    )


def next_update_id(previous: int) -> int:
    return max(previous + 1, int(time.time() * 1e3))


def reduce_only(position_action: PositionAction) -> bool:
    return position_action is PositionAction.CLOSE
