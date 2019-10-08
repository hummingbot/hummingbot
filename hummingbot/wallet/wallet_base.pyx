from typing import Dict


cdef class WalletBase(NetworkIterator):
    @property
    def address(self) -> str:
        raise NotImplementedError

    def get_balance(self, asset_name: str) -> Decimal:
        return self.c_get_balance(asset_name)

    def get_raw_balance(self, asset_name: str) -> int:
        return self.c_get_raw_balance(asset_name)

    def get_all_balances(self) -> Dict[str, Decimal]:
        raise NotImplementedError

    def send(self, address: str, asset_name: str, amount: Decimal) -> str:
        return self.c_send(address, asset_name, amount)

    def to_nominal(self, asset_name: str, raw_amount: int) -> Decimal:
        raise NotImplementedError

    def to_raw(self, asset_name: str, nominal_amount: Decimal) -> int:
        raise NotImplementedError

    cdef object c_get_balance(self, str asset_name):
        raise NotImplementedError

    cdef object c_get_raw_balance(self, str asset_name):
        raise NotImplementedError

    cdef str c_send(self, str address, str asset_name, object amount):
        raise NotImplementedError
