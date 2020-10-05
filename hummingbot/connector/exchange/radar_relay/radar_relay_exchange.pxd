from libc.stdint cimport int64_t
from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.core.data_type.transaction_tracker cimport TransactionTracker


cdef class RadarRelayExchange(ExchangeBase):
    cdef:
        str _wallet_spender_address
        object _wallet
        object _provider
        object _weth_token
        object _ev_loop
        object _poll_notifier
        double _last_timestamp
        double _last_update_limit_order_timestamp
        double _last_update_market_order_timestamp
        double _last_update_trading_rules_timestamp
        double _last_update_available_balance_timestamp
        double _poll_interval
        dict _in_flight_limit_orders
        dict _in_flight_market_orders
        object _order_expiry_queue
        TransactionTracker _tx_tracker
        object _w3
        object _exchange
        dict _withdraw_rules
        dict _trading_rules
        object _pending_approval_tx_hashes
        public object _status_polling_task
        public object _user_stream_event_listener_task
        public object _approval_tx_polling_task
        int64_t _latest_salt

    cdef c_start_tracking_limit_order(self,
                                      str order_id,
                                      str exchange_order_id,
                                      str trading_pair,
                                      object order_type,
                                      object trade_type,
                                      object price,
                                      object amount,
                                      object zero_ex_order)
    cdef c_start_tracking_market_order(self,
                                       str order_id,
                                       str trading_pair,
                                       object order_type,
                                       object trade_type,
                                       object price,
                                       object amount,
                                       str tx_hash)
    cdef c_expire_order(self, str order_id)
    cdef c_check_and_remove_expired_orders(self)
