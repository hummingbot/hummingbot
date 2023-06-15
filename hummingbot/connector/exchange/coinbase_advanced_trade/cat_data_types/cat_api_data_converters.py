import decimal
from decimal import Decimal
from typing import Any, Callable, Coroutine, List, Optional

from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase

from ..cat_data_types.cat_api_v3_mappings import COINBASE_ADVANCED_TRADE_WSS_ORDER_STATE_MAPPING
from ..cat_data_types.cat_api_v3_response_types import (
    CoinbaseAdvancedTradeGetProductResponse,
    CoinbaseAdvancedTradeListProductsResponse,
    is_product_tradable,
)
from ..cat_data_types.cat_api_wss_message_types import (
    CoinbaseAdvancedTradeLevel2EventMessage,
    CoinbaseAdvancedTradeWSSLevel2Update,
    CoinbaseAdvancedTradeWSSUserFill,
)
from ..cat_data_types.cat_cumulative_trade import CoinbaseAdvancedTradeCumulativeUpdate
from ..cat_web_utils import get_timestamp_from_exchange_time, symbol_to_pair
from ..coinbase_advanced_trade_utils import DEFAULT_FEES
from .cat_api_custom_types import OrderBookAsksBidsType
from .cat_api_v3_enums import CoinbaseAdvancedTradeWSSOrderBidAskSide


def cat_product_to_trading_rule(
        product: CoinbaseAdvancedTradeGetProductResponse,
        *,
        trading_pair: Optional[str] = None
) -> TradingRule:
    """
    Converts a Coinbase Advanced Trade product to a Hummingbot TradingRule.
    :param product: The Coinbase Advanced Trade product to convert.
    :param trading_pair: Optional trading_pair that can be obtained by a more robust method
                         than the simplistic non-async method implemented internally
    :return: The converted Hummingbot TradingRule.
    """
    if trading_pair is None:
        trading_pair = symbol_to_pair(product.product_id)

    return TradingRule(
        trading_pair=trading_pair,
        min_order_size=Decimal(product.base_min_size),
        max_order_size=Decimal(product.base_max_size),
        min_price_increment=Decimal(product.quote_increment),
        min_base_amount_increment=Decimal(product.base_increment),
        min_quote_amount_increment=Decimal(product.quote_increment),
        min_notional_size=Decimal(product.quote_min_size),
        min_order_value=Decimal(product.base_min_size) * Decimal(product.price),
        max_price_significant_digits=Decimal(product.quote_increment),
        supports_limit_orders=product.supports_limit_orders,
        supports_market_orders=product.supports_market_orders,
        buy_order_collateral_token=None,
        sell_order_collateral_token=None
    )


def cat_tradable_products_to_trading_rules(
        products: CoinbaseAdvancedTradeListProductsResponse
) -> List[TradingRule]:
    """
    Converts a Coinbase Advanced Trade products to a Hummingbot list TradingRule.
    :param products: The Coinbase Advanced Trade product to convert.
    :return: The converted Hummingbot TradingRule.
    """
    return [cat_product_to_trading_rule(product) for product in products.products if is_product_tradable(product)]


def cat_wss_user_fill_to_cumulative_update(
        wss_user_fill: CoinbaseAdvancedTradeWSSUserFill,
        timestamp_s: float,
        *,
        trading_pair: Optional[str] = None
) -> CoinbaseAdvancedTradeCumulativeUpdate:
    """
    Converts a Coinbase Advanced Trade WSS user order to a Hummingbot CumulativeUpdate.
    :param wss_user_fill: The Coinbase Advanced Trade WSS user order to convert.
    :param timestamp_s: The timestamp of the update.
    :param trading_pair: Optional trading_pair that can be obtained by a more robust method
                            than the simplistic non-async method implemented internally
    """
    if trading_pair is None:
        trading_pair = symbol_to_pair(wss_user_fill.product_id)

    new_state: OrderState = COINBASE_ADVANCED_TRADE_WSS_ORDER_STATE_MAPPING[wss_user_fill.status]

    cumulative_update: CoinbaseAdvancedTradeCumulativeUpdate = CoinbaseAdvancedTradeCumulativeUpdate(
        exchange_order_id=wss_user_fill.order_id,
        client_order_id=wss_user_fill.client_order_id,
        status=new_state.value,
        trading_pair=trading_pair,
        fill_timestamp=timestamp_s,
        average_price=Decimal(wss_user_fill.avg_price),
        cumulative_base_amount=Decimal(wss_user_fill.cumulative_quantity),
        remainder_base_amount=Decimal(wss_user_fill.leaves_quantity),
        cumulative_fee=Decimal(wss_user_fill.total_fees),
    )

    return cumulative_update


async def cat_async_wss_user_fill_to_cumulative_update(
        wss_user_fill: CoinbaseAdvancedTradeWSSUserFill,
        timestamp_s: float,
        symbol_to_pair: Callable[[str], Coroutine[Any, Any, str]]
) -> CoinbaseAdvancedTradeCumulativeUpdate:
    """
    Converts a Coinbase Advanced Trade WSS user order to a Hummingbot CumulativeUpdate.
    :param wss_user_fill: The Coinbase Advanced Trade WSS user order to convert.
    :param timestamp_s: The timestamp of the update.
    :param symbol_to_pair: Async function that converts a symbol to a trading pair
    """
    trading_pair: str = await symbol_to_pair(wss_user_fill.product_id)
    return cat_wss_user_fill_to_cumulative_update(wss_user_fill, timestamp_s, trading_pair=trading_pair)


def cat_wss_user_fill_to_order_update(
        wss_user_fill: CoinbaseAdvancedTradeWSSUserFill,
        timestamp_s: float,
        *,
        trading_pair: Optional[str] = None
) -> OrderUpdate:
    """
    Converts a Coinbase Advanced Trade WSS user order to a Hummingbot OrderUpdate.
    :param wss_user_fill: The Coinbase Advanced Trade WSS user order to convert.
    :param timestamp_s: The timestamp of the update.
    :param trading_pair: Optional trading_pair that can be obtained by a more robust method
                            than the simplistic non-async method implemented internally
    """
    if trading_pair is None:
        trading_pair = symbol_to_pair(wss_user_fill.product_id)

    new_state: OrderState = COINBASE_ADVANCED_TRADE_WSS_ORDER_STATE_MAPPING[wss_user_fill.status]
    partial: bool = float(wss_user_fill.leaves_quantity) > 0 and new_state == OrderState.OPEN
    new_state = OrderState.PARTIALLY_FILLED if partial else new_state

    order_update: OrderUpdate = OrderUpdate(
        exchange_order_id=wss_user_fill.order_id,
        client_order_id=wss_user_fill.client_order_id,
        new_state=new_state,
        trading_pair=trading_pair,
        update_timestamp=timestamp_s,
    )
    return order_update


async def cat_async_wss_user_fill_to_order_update(
        wss_user_fill: CoinbaseAdvancedTradeWSSUserFill,
        timestamp_s: float,
        symbol_to_pair: Callable[[str], Coroutine[Any, Any, str]]
) -> OrderUpdate:
    """
    Converts a Coinbase Advanced Trade WSS user order to a Hummingbot OrderUpdate.
    :param wss_user_fill: The Coinbase Advanced Trade WSS user order to convert.
    :param timestamp_s: The timestamp of the update.
    :param symbol_to_pair: Async function that converts a Coinbase Advanced Trade symbol to a Hummingbot trading pair.
    """
    trading_pair: str = await symbol_to_pair(wss_user_fill.product_id)
    return cat_wss_user_fill_to_order_update(wss_user_fill, timestamp_s, trading_pair=trading_pair)


def cat_wss_user_fill_to_trade_update(
        wss_user_fill: CoinbaseAdvancedTradeWSSUserFill,
        timestamp_s: float,
        if_order: InFlightOrder,
) -> TradeUpdate:
    """
    Converts a Coinbase Advanced Trade WSS user order to a Hummingbot TradeUpdate.
    :param wss_user_fill: The Coinbase Advanced Trade WSS user order to convert.
    :param timestamp_s: The timestamp of the update.
    :param if_order: The Hummingbot InFlightOrder that corresponds to the Coinbase Advanced Trade WSS user order.
    """
    quantity: Decimal = Decimal(wss_user_fill.cumulative_quantity)
    fill_base_amount: Decimal = quantity - if_order.executed_amount_base
    transaction_fee: Decimal = Decimal(wss_user_fill.total_fees) - if_order.cumulative_fee_paid("USD")
    total_price: Decimal = Decimal(wss_user_fill.avg_price) * quantity

    fee = TradeFeeBase.new_spot_fee(
        fee_schema=DEFAULT_FEES,
        trade_type=if_order.trade_type,
        percent_token="USD",
        flat_fees=[TokenAmount(amount=Decimal(transaction_fee), token="USD")]
    )
    try:
        fill_price: Decimal = (total_price - if_order.average_executed_price) / fill_base_amount
    except (ZeroDivisionError, decimal.InvalidOperation):
        raise ValueError("Fill base amount is zero for an InFlightOrder, this is unexpected")

    trade_update = TradeUpdate(
        trade_id="",  # Coinbase does not provide matching trade id
        client_order_id=wss_user_fill.client_order_id,
        exchange_order_id=wss_user_fill.order_id,
        trading_pair=if_order.trading_pair,
        fee=fee,
        fill_base_amount=fill_base_amount,
        fill_quote_amount=fill_base_amount * fill_price,
        fill_price=fill_price,
        fill_timestamp=timestamp_s,
    )

    return trade_update


def cat_level2_update_to_order_book_update(
        level2_update: CoinbaseAdvancedTradeWSSLevel2Update,
) -> OrderBookRow:
    """
    Converts a Coinbase Advanced Trade Level2 update to a Hummingbot OrderBookRow.
    :param level2_update: The Coinbase Advanced Trade Level2 update to convert.
    """
    order_book_row: OrderBookRow = OrderBookRow(
        float(level2_update.price_level),
        float(level2_update.new_quantity),
        get_timestamp_from_exchange_time(level2_update.event_time, "s"),
    )
    return order_book_row


def cat_level2_event_to_order_book_asks_bids(
        level2_event: CoinbaseAdvancedTradeLevel2EventMessage,
) -> OrderBookAsksBidsType:
    """
    Converts a Coinbase Advanced Trade Level2 event to a Hummingbot OrderBookRow.
    :param level2_event: The Coinbase Advanced Trade Level2 event to convert.
    """
    asks: List[OrderBookRow] = []
    bids: List[OrderBookRow] = []
    for update in level2_event.iter():
        row = cat_level2_update_to_order_book_update(update)
        if update.side == CoinbaseAdvancedTradeWSSOrderBidAskSide.bid:
            bids.append(row)
        else:
            asks.append(row)
    return {"asks": tuple(asks), "bids": tuple(bids)}
