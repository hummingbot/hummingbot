# distutils: language=c++

from hummingbot.strategy.strategy_base cimport StrategyBase
from libc.stdint cimport int64_t

cdef class CeloArbStrategy(StrategyBase):
    cdef:
        object _market_info
        object _min_profitability
        object _order_amount
        double _last_timestamp
        str _asset_trading_pair
        bint _all_markets_ready
        double _status_report_interval
        int64_t _logging_options

    cdef c_execute_buy_celo_sell_ctp(self, object trade_profit)
