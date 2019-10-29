from libc.stdint cimport int64_t
from hummingbot.market.market_base cimport MarketBase
from hummingbot.core.data_type.transaction_tracker cimport TransactionTracker


cdef class StablecoinswapMarket(MarketBase):
    cdef:
        str _wallet_spender_address
        object _wallet
        object _ev_loop
        object _poll_notifier
        double _last_timestamp
        double _last_update_fee_timestamp
        double _last_update_market_order_timestamp
        double _last_update_asset_info_timestamp
        double _poll_interval
        object _contract_fees
        dict _assets_decimals
        dict _in_flight_orders
        TransactionTracker _tx_tracker
        object _w3
        object _pending_approval_tx_hashes
        object _stl_cont
        object _oracle_cont
        public object _status_polling_task
        public object _user_stream_event_listener_task
        public object _approval_tx_polling_task
        public object _order_tracker_task

    cdef c_start_tracking_order(self,
                                str order_id,
                                str symbol,
                                object trade_type,
                                object order_type,
                                object amount,
                                object price,
                                str tx_hash,
                                str fee_asset,
                                object fee_percent)
    cdef c_stop_tracking_order(self, str order_id)
