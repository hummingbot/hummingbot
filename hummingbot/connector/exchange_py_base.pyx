from decimal import Decimal
from hummingbot.connector.exchange_base import ExchangeBase

s_decimal_NaN = Decimal("NaN")


cdef class ExchangePyBase(ExchangeBase):

    cdef object c_quantize_order_price(self, str trading_pair, object price):
        return self.quantize_order_price(trading_pair, price)

    def quantize_order_price(self, trading_pair: str, price: Decimal) -> Decimal:
        if price.is_nan():
            return price
        price_quantum = self.c_get_order_price_quantum(trading_pair, price)
        return round(price / price_quantum) * price_quantum

    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=s_decimal_NaN):
        return self.quantize_order_amount(trading_pair, amount)

    def quantize_order_amount(self, trading_pair: str, amount: Decimal) -> Decimal:
        order_size_quantum = self.c_get_order_size_quantum(trading_pair, amount)
        return (amount // order_size_quantum) * order_size_quantum
