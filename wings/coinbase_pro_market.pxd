from libc.stdint cimport int64_t

from .market_base cimport MarketBase
from .transaction_tracker cimport TransactionTracker


cdef class CoinbaseProMarket(MarketBase):
    cdef:
        object _order_book_tracker
        object _user_stream_tracker
        object _coinbase_client
        dict _account_balances
        object _ev_loop
        object _poll_notifier
        double _last_timestamp
        double _poll_interval
        dict _in_flight_deposits
        dict _in_flight_orders
        TransactionTracker _tx_tracker
        object _w3
        dict _withdraw_rules
        dict _trading_rules
        object _data_source_type
        public object _status_polling_task
        public object _user_stream_event_listener_task
        public object _user_stream_tracker_task
        public object _order_tracker_task
        object _coro_queue
        public object _coro_scheduler_task

    cdef c_did_timeout_tx(self, str tracking_id)
    cdef c_did_fail_tx(self, str tracking_id)
    cdef c_start_tracking_deposit(self, str tracking_id, int64_t start_time_ms, str tx_hash, str from_address,
                                  str to_address)
    cdef c_stop_tracking_deposit(self, str tracking_id)
    cdef c_start_tracking_order(self, str order_id, int64_t exchange_order_id, str symbol, bint is_buy, object amount)
    cdef c_stop_tracking_order(self, str order_id)