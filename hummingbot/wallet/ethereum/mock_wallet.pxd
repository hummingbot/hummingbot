from hummingbot.wallet.wallet_base cimport WalletBase


cdef class MockWallet(WalletBase):
    cdef:
        object _account
        object _w3
        int _local_nonce
        dict _erc20_contracts
        int _chain_id
