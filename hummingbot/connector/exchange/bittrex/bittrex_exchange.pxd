from libc.stdint cimport int64_t

from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.core.data_type.transaction_tracker cimport TransactionTracker


cdef class BittrexExchange(ExchangeBase):
    cdef:
        str _account_id
        object _bittrex_auth
        object _coro_queue
        object _ev_loop
        dict _in_flight_orders
        double _last_timestamp
        double _last_poll_timestamp
        dict _order_not_found_records
        object _user_stream_tracker
        object _poll_notifier
        double _poll_interval
        dict _trading_rules
        public object _coro_scheduler_task
        public object _shared_client
        public object _status_polling_task
        public object _trading_rules_polling_task
        public object _user_stream_event_listener_task
        public object _user_stream_tracker_task
        TransactionTracker _tx_tracker

    cdef c_start_tracking_order(self,
                                str order_id,
                                str exchange_order_id,
                                str trading_pair,
                                object trade_type,
                                object order_type,
                                object price,
                                object amount)
    cdef c_did_timeout_tx(self, str tracking_id)
