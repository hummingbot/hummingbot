from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.core.data_type.transaction_tracker cimport TransactionTracker

cdef class DolomiteExchange(ExchangeBase):
    cdef:
        str API_REST_ENDPOINT
        str WS_ENDPOINT
        TransactionTracker _tx_tracker
        object _poll_notifier
        double _poll_interval
        double _last_timestamp
        object _wallet
        object _web3
        object _shared_client

        public object _polling_update_task

        dict _trading_rules
        object _exchange_info
        object _exchange_rates
        object _pending_approval_tx_hashes
        dict _in_flight_orders
