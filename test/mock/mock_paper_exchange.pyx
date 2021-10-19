from typing import List, Dict, Tuple
import asyncio
import numpy as np
from decimal import Decimal

from hummingbot.connector.exchange.paper_trade.paper_trade_exchange cimport PaperTradeExchange, QuantizationParams
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from hummingbot.connector.exchange.paper_trade.trading_pair import TradingPair
from hummingbot.core.event.events import TradeFee, TradeFeeType
from hummingbot.core.data_type.order_book import OrderBook, OrderBookRow
from hummingbot.core.data_type.composite_order_book cimport CompositeOrderBook
from hummingbot.connector.exchange.paper_trade.market_config import MarketConfig
from hummingbot.client.settings import CONNECTOR_SETTINGS, ConnectorSetting, ConnectorType, TradeFeeType
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import new_fee_config_var
from hummingbot.client.config.fee_overrides_config_map import fee_overrides_config_map
from hummingbot.connector.exchange_base cimport ExchangeBase
from .mock_order_tracker import MockOrderTracker

s_decimal_0 = Decimal("0")

cdef class MockPaperExchange(PaperTradeExchange):

    def __init__(self, fee_percent: Decimal = Decimal("0")):
        PaperTradeExchange.__init__(self, MockOrderTracker(), MarketConfig.default_config(), MockPaperExchange)
        CONNECTOR_SETTINGS[self.name] = ConnectorSetting(self.name, ConnectorType.Exchange,
                                                         "", True, False, TradeFeeType.Percent, "",
                                                         [fee_percent, fee_percent], None, None, None, None, None)

    def set_flat_fee(self, fee_amount: Decimal):
        maker_config = new_fee_config_var(f"{self.name}_maker_fee_amount")
        taker_config = new_fee_config_var(f"{self.name}_taker_fee_amount")
        maker_config.value = fee_amount
        taker_config.value = fee_amount
        fee_overrides_config_map[maker_config.key] = maker_config
        fee_overrides_config_map[maker_config.key] = taker_config

    @property
    def name(self) -> str:
        return "MockPaperExchange"

    @property
    def display_name(self) -> str:
        return self.name

    @property
    def ready(self):
        return True

    def split_trading_pair(self, trading_pair: str) -> Tuple[str, str]:
        return trading_pair.split("-")

    def set_balanced_order_book(self,
                                str trading_pair,
                                double mid_price,
                                double min_price,
                                double max_price,
                                double price_step_size,
                                double volume_step_size):
        self.c_set_balanced_order_book(trading_pair, mid_price, min_price, max_price, price_step_size, volume_step_size)

    cdef c_set_balanced_order_book(self,
                                   str trading_pair,
                                   double mid_price,
                                   double min_price,
                                   double max_price,
                                   double price_step_size,
                                   double volume_step_size):
        cdef:
            list bids = []
            list asks = []
            double current_price
            double current_size
            CompositeOrderBook order_book
        order_book = CompositeOrderBook()
        current_price = mid_price - price_step_size / 2
        current_size = volume_step_size
        while current_price >= min_price:
            bids.append(OrderBookRow(current_price, current_size, 1))
            current_price -= price_step_size
            current_size += volume_step_size

        current_price = mid_price + price_step_size / 2
        current_size = volume_step_size
        while current_price <= max_price:
            asks.append(OrderBookRow(current_price, current_size, 1))
            current_price += price_step_size
            current_size += volume_step_size

        order_book.apply_snapshot(bids, asks, 1)
        order_book.c_add_listener(self.ORDER_BOOK_TRADE_EVENT_TAG, self._order_book_trade_listener)
        base_asset, quote_asset = self.split_trading_pair(trading_pair)
        self._trading_pairs[trading_pair] = TradingPair(trading_pair, base_asset, quote_asset)
        self.order_book_tracker._order_books[trading_pair] = order_book

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        cdef:
            QuantizationParams q_params
        if trading_pair in self._quantization_params:
            q_params = self._quantization_params[trading_pair]
            decimals_quantum = Decimal(f"1e-{q_params.price_decimals}")
            if price > s_decimal_0:
                precision_quantum = Decimal(f"1e{np.ceil(np.log10(price)) - q_params.price_precision}")
            else:
                precision_quantum = s_decimal_0
            print(f"c_get_order_price_quantum: {price}  {q_params.price_decimals}  {q_params.price_precision}")
            return max(precision_quantum, decimals_quantum)
        else:
            return Decimal(f"1e-15")

    cdef object c_get_order_size_quantum(self, str trading_pair, object order_size):
        cdef:
            QuantizationParams q_params
        if trading_pair in self._quantization_params:
            q_params = self._quantization_params[trading_pair]
            decimals_quantum = Decimal(f"1e-{q_params.order_size_decimals}")
            if order_size > s_decimal_0:
                precision_quantum = Decimal(f"1e{np.ceil(np.log10(order_size)) - q_params.order_size_precision}")
            else:
                precision_quantum = s_decimal_0
            print(f"c_get_order_size_quantum: {order_size}  {q_params.price_decimals}  {q_params.price_precision}")
            return max(precision_quantum, decimals_quantum)
        else:
            return Decimal(f"1e-15")

    cdef object c_quantize_order_price(self,
                                       str trading_pair,
                                       object price):
        return ExchangeBase.c_quantize_order_price(self, trading_pair, price)

    cdef object c_quantize_order_amount(self,
                                        str trading_pair,
                                        object amount,
                                        object price=s_decimal_0):
        return ExchangeBase.c_quantize_order_amount(self, trading_pair, amount, price)

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        return self.c_get_order_price_quantum(trading_pair, price)

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        return self.c_get_order_size_quantum(trading_pair, order_size)

    def quantize_order_price(self, trading_pair: str, price: Decimal) -> Decimal:
        return self.c_quantize_order_price(trading_pair, price)

    def quantize_order_amount(self, trading_pair: str, amount: Decimal) -> Decimal:
        return self.c_quantize_order_amount(trading_pair, amount)
