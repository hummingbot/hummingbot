from wings.market.market_base cimport MarketBase
from wings.event_listener cimport EventListener
from wings.time_iterator cimport TimeIterator
from wings.transaction_tracker cimport TransactionTracker
from wings.wallet.wallet_base cimport WalletBase


cdef class StrategyTask(TimeIterator):
    cdef:
        bint _done
        bint _started
        WalletBase _local_wallet
        MarketBase _market
        double _timeout_seconds
        TransactionTracker _tx_tracker
        EventListener _wallet_tx_failure_listener
        EventListener _market_tx_failure_listener

    cdef c_set_done(self)
    cdef bint c_is_done(self)
    cdef bint c_is_started(self)
    cdef c_get_local_wallet(self)
    cdef c_set_local_wallet(self, WalletBase local_wallet)
    cdef c_set_market(self, MarketBase market)
    cdef double c_get_timeout_seconds(self)
    cdef c_set_timeout_seconds(self, double timeout_seconds)
    cdef c_start_tx_tracking(self, str tx_hash)
    cdef bint c_is_tx_tracked(self, str tx_hash)
    cdef c_did_timeout_tx(self, str tx_hash)
    cdef c_did_fail_tx(self, str tx_hash)
    cdef c_stop_tx_tracking(self, str tx_hash)
