# distutils: language=c++

from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.strategy.strategy_base cimport StrategyBase
from libc.stdint cimport int64_t

cdef class CeloArbStrategy(StrategyBase):
    cdef:
        object _market_info
        object _min_profitability
        object _order_amount
        object _celo_slippage_buffer
        double _last_timestamp
        str _asset_trading_pair
        str _exchange
        bint _all_markets_ready
        double _status_report_interval
        double _last_no_arb_reported
        double _last_synced_checked
        bint _node_synced
        int64_t _logging_options
        list _celo_orders
        bint _hb_app_notification
        object _async_scheduler
        object _main_task
        bint _mock_celo_cli_mode
        object _trade_profits
        object _ev_loop

    cdef c_main(self)
    cdef c_execute_buy_celo_sell_ctp(self, object trade_profit)
    cdef c_execute_sell_celo_buy_ctp(self, object trade_profit)
