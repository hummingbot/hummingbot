from hummingbot.connector.exchange.paper_trade.paper_trade_exchange cimport PaperTradeExchange

cdef class MockPaperExchange(PaperTradeExchange):
    cdef object c_get_fee(self,
                          str base_asset,
                          str quote_asset,
                          object order_type,
                          object order_side,
                          object amount,
                          object price)
    cdef c_set_balanced_order_book(self,
                                   str trading_pair,
                                   double mid_price,
                                   double min_price,
                                   double max_price,
                                   double price_step_size,
                                   double volume_step_size)
