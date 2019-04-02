from libc.stdint cimport int64_t

from wings.clock cimport Clock
from wings.events import WalletEvent, MarketEvent
from wings.time_iterator import TimeIterator
from wings.time_iterator cimport TimeIterator
from wings.transaction_tracker import TransactionTracker


cdef class TxFailureListener(EventListener):
    cdef:
        StrategyTask _owner

    def __init__(self, owner: StrategyTask):
        self._owner = owner

    cdef c_call(self, object tx_hash):
        if self._owner.c_is_tx_tracked(tx_hash):
            self._owner.c_did_fail_tx(tx_hash)


cdef class TaskTransactionTracker(TransactionTracker):
    cdef:
        StrategyTask _owner

    def __init__(self, owner: StrategyTask):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)


cdef class StrategyTask(TimeIterator):
    def __init__(self, local_wallet: WalletBase, market: MarketBase):
        super().__init__()
        self._done = False
        self._started = False
        self._local_wallet = None
        self._market = None
        self._timeout_seconds = 3600.0
        self._tx_tracker = TaskTransactionTracker(self)
        self._wallet_tx_failure_listener = TxFailureListener(self)
        self._market_tx_failure_listener = TxFailureListener(self)
        self.c_set_local_wallet(local_wallet)
        self.c_set_market(market)

    @property
    def is_done(self) -> bool:
        return self._done

    cdef c_set_done(self):
        self._done = True

    cdef bint c_is_done(self):
        return self._done

    cdef bint c_is_started(self):
        return self._started

    cdef c_start(self, Clock clock, double timestamp):
        self._tx_tracker.c_start(clock, timestamp)
        TimeIterator.c_start(self, clock, timestamp)
        self._started = True

    cdef c_tick(self, double timestamp):
        self._tx_tracker.c_tick(timestamp)
        TimeIterator.c_tick(self, timestamp)

    cdef c_get_local_wallet(self):
        return self._local_wallet

    cdef c_set_local_wallet(self, WalletBase local_wallet):
        cdef:
            int64_t transaction_failure_event_tag = WalletEvent.TransactionFailure.value

        if self._local_wallet is not None:
            self._local_wallet.c_remove_listener(transaction_failure_event_tag, self._wallet_tx_failure_listener)
        self._local_wallet = local_wallet
        self._local_wallet.c_add_listener(transaction_failure_event_tag, self._wallet_tx_failure_listener)

    cdef c_set_market(self, MarketBase market):
        cdef:
            int64_t transaction_failure_event_tag = MarketEvent.TransactionFailure.value

        if self._market is not None:
            self._market.c_remove_listener(transaction_failure_event_tag, self._market_tx_failure_listener)
        self._market = market
        self._market.c_add_listener(transaction_failure_event_tag, self._market_tx_failure_listener)

    cdef double c_get_timeout_seconds(self):
        return self._timeout_seconds

    cdef c_set_timeout_seconds(self, double timeout_seconds):
        self._timeout_seconds = timeout_seconds

    cdef c_start_tx_tracking(self, str tx_hash):
        self._tx_tracker.c_start_tx_tracking(tx_hash, self._timeout_seconds)

    cdef bint c_is_tx_tracked(self, str tx_hash):
        return self._tx_tracker.c_is_tx_tracked(tx_hash)

    cdef c_did_timeout_tx(self, str tx_hash):
        pass

    cdef c_did_fail_tx(self, str tx_hash):
        self.c_stop_tx_tracking(tx_hash)

    cdef c_stop_tx_tracking(self, str tx_hash):
        self._tx_tracker.c_stop_tx_tracking(tx_hash)
