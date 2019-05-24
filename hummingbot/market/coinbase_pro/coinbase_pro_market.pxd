from hummingbot.market.market_base cimport MarketBase
from hummingbot.core.data_type.transaction_tracker cimport TransactionTracker


cdef class CoinbaseProMarket(MarketBase):
    cdef:
        object _order_book_tracker
        object _user_stream_tracker
        object _coinbase_auth
        dict _account_balances
        object _ev_loop
        object _poll_notifier
        double _last_timestamp
        double _last_order_update_timestamp
        double _poll_interval
        dict _in_flight_deposits
        dict _in_flight_orders
        TransactionTracker _tx_tracker
        object _w3
        dict _trading_rules
        object _data_source_type
        object _coro_queue
        public object _status_polling_task
        public object _order_tracker_task
        public object _coro_scheduler_task
        public object _user_stream_tracker_task
        public object _user_stream_event_listener_task
        public object _trading_rules_polling_task
        public object _shared_client

    cdef c_start_tracking_order(self, str order_id, str exchange_order_id, str symbol, bint is_buy, object order_type,
                                object amount, object price)
    cdef c_stop_tracking_order(self, str order_id)
    cdef c_start_tracking_deposit(self, str tracking_id, str tx_hash, str from_address, str to_address, object amount, str currency)
    cdef c_stop_tracking_deposit(self, str tracking_id)
    cdef c_did_timeout_tx(self, str tracking_id)
    cdef c_did_fail_tx(self, str tracking_id)