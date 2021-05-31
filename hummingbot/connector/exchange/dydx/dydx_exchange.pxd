from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.core.data_type.transaction_tracker cimport TransactionTracker

cdef class DydxExchange(ExchangeBase):
    cdef:
        str API_REST_ENDPOINT
        str WS_ENDPOINT
        TransactionTracker _tx_tracker
        object _poll_notifier
        double _poll_interval
        double _last_timestamp
        object _shared_client
        object _dydx_auth
        str _dydx_node
        str _dydx_private_key
        object dydx_client
        object _order_sign_param

        object _user_stream_tracker
        object _user_stream_tracker_task
        object _user_stream_event_listener_task
        public object _polling_update_task
        public object _token_configuration

        dict _fee_rules
        dict _trading_rules
        object _lock
        object _exchange_rates
        dict _in_flight_orders
        dict _next_order_id
        dict _dydx_tokenids
        list _trading_pairs
        object _dydx_order_sign_param
        bint _fee_override
        dict _reserved_balances
        object _unclaimed_fills
        dict _in_flight_orders_by_exchange_id
        set _orders_pending_ack

    cdef c_start_tracking_order(self,
                                object side,
                                str client_order_id,
                                object order_type,
                                long long created_at,
                                str hash,
                                str trading_pair,
                                object price,
                                object amount)
    cdef object c_get_order_by_exchange_id(self, str exchange_order_id)
