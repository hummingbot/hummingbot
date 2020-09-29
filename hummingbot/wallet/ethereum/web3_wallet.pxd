from libc.stdint cimport int64_t

from hummingbot.wallet.wallet_base cimport WalletBase
from hummingbot.core.event.event_listener cimport EventListener


cdef class Web3Wallet(WalletBase):
    cdef:
        object _local_account
        list _wallet_backends
        list _last_backend_network_states
        object _best_backend
        object _select_best_backend_task
        object _chain
        object _event_dedup_window
        object _erc20_token
        EventListener _received_asset_forwarder
        EventListener _gas_used_forwarder
        EventListener _token_approved_forwarder
        EventListener _eth_wrapped_forwarder
        EventListener _eth_unwrapped_forwarder
        EventListener _transaction_failure_forwarder
        EventListener _zeroex_fill_forwarder

    cdef c_receive_forwarded_event(self, int64_t event_tag, object args)
