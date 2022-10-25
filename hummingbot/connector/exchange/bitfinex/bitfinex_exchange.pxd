from libcpp cimport bool
from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.core.data_type.transaction_tracker cimport TransactionTracker


cdef class BitfinexExchange(ExchangeBase):
    cdef:
        object _ev_loop
        object _poll_notifier
        public object _user_stream_tracker
        public object _bitfinex_auth
        list trading_pairs
        public object _user_stream_tracker_task
        TransactionTracker _tx_tracker

        double _last_timestamp
        double _last_order_update_timestamp
        double _poll_interval
        dict _in_flight_orders
        dict _trading_rules
        dict _order_not_found_records
        object _data_source_type
        object _coro_queue
        public object _status_polling_task
        public object _order_tracker_task
        public object _coro_scheduler_task
        public object _user_stream_event_listener_task
        public object _trading_rules_polling_task
        public object _shared_client
        public list _pending_requests
        public object _ws
        public object _ws_task

    cdef c_start_tracking_order(self,
                                str order_id,
                                str trading_pair,
                                object trade_type,
                                object order_type,
                                object price,
                                object amount)
    cdef c_stop_tracking_order(self, str order_id)
