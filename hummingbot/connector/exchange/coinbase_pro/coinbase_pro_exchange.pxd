from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.core.data_type.transaction_tracker cimport TransactionTracker


cdef class CoinbaseProExchange(ExchangeBase):
    cdef:
        object _user_stream_tracker
        object _coinbase_auth
        object _ev_loop
        object _poll_notifier
        double _last_timestamp
        double _last_order_update_timestamp
        double _last_fee_percentage_update_timestamp
        object _maker_fee_percentage
        object _taker_fee_percentage
        double _poll_interval
        dict _in_flight_orders
        TransactionTracker _tx_tracker
        dict _trading_rules
        object _coro_queue
        public object _status_polling_task
        public object _coro_scheduler_task
        public object _user_stream_tracker_task
        public object _user_stream_event_listener_task
        public object _trading_rules_polling_task
        public object _shared_client

    cdef c_start_tracking_order(self,
                                str order_id,
                                str trading_pair,
                                object trade_type,
                                object order_type,
                                object price,
                                object amount)
    cdef c_did_timeout_tx(self, str tracking_id)
