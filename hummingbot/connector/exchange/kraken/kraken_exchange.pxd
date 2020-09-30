from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.core.data_type.transaction_tracker cimport TransactionTracker
from libc.stdint cimport int32_t


cdef class KrakenExchange(ExchangeBase):
    cdef:
        object _user_stream_tracker
        object _ev_loop
        object _poll_notifier
        double _last_timestamp
        double _poll_interval
        double _last_pull_timestamp
        dict _in_flight_orders
        dict _order_not_found_records
        TransactionTracker _tx_tracker
        dict _trading_rules
        dict _trade_fees
        double _last_update_trade_fees_timestamp
        public object _status_polling_task
        public object _user_stream_event_listener_task
        public object _user_stream_tracker_task
        public object _trading_rules_polling_task
        object _async_scheduler
        object _set_server_time_offset_task
        public object _kraken_auth
        object _shared_client
        dict _asset_pairs
        int32_t _last_userref
        object _throttler

    cdef c_did_timeout_tx(self, str tracking_id)
    cdef c_start_tracking_order(self,
                                str order_id,
                                str exchange_order_id,
                                str trading_pair,
                                object trade_type,
                                object price,
                                object amount,
                                object order_type,
                                int userref)
