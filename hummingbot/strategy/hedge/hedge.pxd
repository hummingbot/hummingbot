# distutils: language=c++

from libc.stdint cimport int64_t
from hummingbot.strategy.strategy_base cimport StrategyBase
cdef class HedgeStrategy(StrategyBase):
    cdef:
        object _exchanges
        dict _market_infos
        dict _assets
        object _hedge_ratio
        object _minimum_trade
        bint _all_markets_ready
        double _last_timestamp
        double _status_report_interval
        object _position_mode
        object _leverage
        object _last_trade_time
        dict _shadow_taker_balance
        float _update_shadow_balance_interval
        float _hedge_interval
        object _slippage
        object _max_order_age

    cdef object check_and_hedge_asset(self,
                                      str maker_asset,
                                      object maker_balance,
                                      object market_pair,
                                      str trading_pair,
                                      object taker_balance,
                                      object hedge_amount,
                                      bint is_buy,
                                      object price
                                      )

    cdef object place_order(self,
                            str maker_asset,
                            bint is_buy,
                            object difference,
                            object price,)

    cdef c_apply_initial_settings(self,
                                  object market_pair,
                                  object position,
                                  int64_t leverage)

    cdef object check_and_cancel_active_orders(self,
                                               object market_pair,
                                               object hedge_amount
                                               )
