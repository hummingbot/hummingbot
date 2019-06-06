from hummingbot.market.market_base cimport MarketBase
from hummingbot.core.data_type.transaction_tracker cimport TransactionTracker


cdef class IDEXMarket(MarketBase):
    cdef:
        str _wallet_spender_address
        object _shared_client
        object _wallet
        object _weth_token
        object _order_book_tracker
        dict _account_balances
        object _ev_loop
        object _poll_notifier
        double _last_timestamp
        double _last_update_balances_timestamp
        double _last_update_order_timestamp
        double _last_update_asset_info_timestamp
        double _last_update_next_nonce_timestamp
        double _last_update_contract_address_timestamp
        double _poll_interval
        dict _in_flight_orders
        object _in_flight_cancels
        object _order_expiry_queue
        TransactionTracker _tx_tracker
        object _w3
        dict _withdraw_rules
        object _pending_approval_tx_hashes
        public object _status_polling_task
        public object _user_stream_event_listener_task
        public object _order_tracker_task
        public object _approval_tx_polling_task
        double _maker_trade_fee
        double _taker_trade_fee
        double _gas_fee_weth
        double _gas_fee_usd
        object _api_response_records
        object _assets_info
        object _next_nonce
        object _contract_address

    cdef c_start_tracking_order(self,
                                str order_id,
                                str symbol,
                                bint is_buy,
                                object order_type,
                                object amount,
                                object price)
    cdef c_expire_order(self, str order_id)
    cdef c_check_and_remove_expired_orders(self)
    cdef c_stop_tracking_order(self, str order_id)
