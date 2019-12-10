from hummingbot.market.market_base cimport MarketBase
from hummingbot.core.data_type.transaction_tracker cimport TransactionTracker


cdef class DDEXMarket(MarketBase):
    cdef:
        str _wallet_spender_address
        object _shared_client
        object _wallet
        object _weth_token
        object _ev_loop
        object _poll_notifier
        double _last_timestamp
        double _last_update_order_timestamp
        double _last_update_trade_fills_timestamp
        double _last_update_available_balance_timestamp
        double _last_update_trading_rules_timestamp
        double _last_update_trade_fees_timestamp
        double _poll_interval
        dict _in_flight_orders
        object _in_flight_cancels
        object _order_expiry_queue
        TransactionTracker _tx_tracker
        object _w3
        dict _withdraw_rules
        dict _trading_rules
        object _pending_approval_tx_hashes
        public object _status_polling_task
        public object _user_stream_event_listener_task
        public object _order_tracker_task
        public object _approval_tx_polling_task
        object _maker_trade_fee
        object _taker_trade_fee
        object _gas_fee_weth
        object _gas_fee_usd
        object _api_response_records

    cdef c_start_tracking_order(self,
                                str order_id,
                                str trading_pair,
                                object trade_type,
                                object order_type,
                                object amount,
                                object price)
    cdef c_expire_order(self, str order_id)
    cdef c_check_and_remove_expired_orders(self)
