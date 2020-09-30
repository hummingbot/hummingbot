from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.core.data_type.transaction_tracker cimport TransactionTracker


cdef class EterbaseExchange(ExchangeBase):
    cdef:
        object _user_stream_tracker
        object _eterbase_auth
        object _ev_loop
        object _poll_notifier
        double _last_timestamp
        double _last_order_update_timestamp
        double _poll_interval
        dict _in_flight_orders
        TransactionTracker _tx_tracker
        dict _trading_rules
        object _coro_queue
        public object _status_polling_task
        public object _order_tracker_task
        public object _coro_scheduler_task
        public object _user_stream_tracker_task
        public object _user_stream_event_listener_task
        public object _trading_rules_polling_task
        public object _shared_client
        object _eterbase_account
        object _eterbase_tier
        object _maker_fee
        object _taker_fee
        object _order_not_found_records

    cdef c_start_tracking_order(self,
                                str order_id,
                                str trading_pair,
                                object trade_type,
                                object order_type,
                                object price,
                                object amount,
                                object cost)
    cdef c_stop_tracking_order(self, str order_id)
    cdef c_did_timeout_tx(self, str tracking_id)
    cdef c_round_to_sig_digits(self, object number, int sigdit, object maxdecimal=*)
    cdef object c_quantize_cost(self, str trading_pair, object amount, object price)
