from libc.stdint cimport int64_t
from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.core.data_type.transaction_tracker cimport TransactionTracker


cdef class BambooRelayExchange(ExchangeBase):
    cdef:
        str _wallet_spender_address
        object _wallet
        int _chain_id
        object _provider
        object _weth_token
        object _ev_loop
        object _poll_notifier
        double _last_timestamp
        double _last_failed_limit_order_timestamp
        double _last_update_limit_order_timestamp
        double _last_update_market_order_timestamp
        double _last_update_trading_rules_timestamp
        double _last_update_available_balance_timestamp
        double _poll_interval
        dict _in_flight_limit_orders
        dict _in_flight_market_orders
        object _in_flight_pending_limit_orders
        object _in_flight_cancels
        object _in_flight_pending_cancels
        list _filled_order_hashes
        object _order_expiry_queue
        TransactionTracker _tx_tracker
        object _w3
        object _exchange
        object _coordinator
        bint _use_coordinator
        bint _pre_emptive_soft_cancels
        dict _trading_rules
        object _pending_approval_tx_hashes
        public object _status_polling_task
        public object _user_stream_event_listener_task
        public object _approval_tx_polling_task
        int64_t _latest_salt
        str _api_endpoint
        str _api_prefix
        str _exchange_address
        str _coordinator_address
        str _fee_recipient_address

    cdef c_start_tracking_limit_order(self,
                                      str order_id,
                                      str exchange_order_id,
                                      str trading_pair,
                                      object order_type,
                                      bint is_coordinated,
                                      object trade_type,
                                      object price,
                                      object amount,
                                      int expires,
                                      object zero_ex_order)
    cdef c_start_tracking_market_order(self,
                                       str order_id,
                                       str trading_pair,
                                       object order_type,
                                       bint is_coordinated,
                                       object trade_type,
                                       object price,
                                       object amount,
                                       str tx_hash,
                                       object protocol_fee_amount)
    cdef c_expire_order(self, str order_id, int seconds)
    cdef c_check_and_remove_expired_orders(self)
    cdef list c_get_orders_for_amount_price(self,
                                            str trading_pair,
                                            object trade_type,
                                            object amount,
                                            object price)
