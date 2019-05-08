from typing import Dict


cdef class WalletBase(NetworkIterator):
    @property
    def address(self) -> str:
        raise NotImplementedError

    def get_balance(self, asset_name: str) -> float:
        return self.c_get_balance(asset_name)

    def get_raw_balance(self, asset_name: str) -> int:
        return self.c_get_raw_balance(asset_name)

    def get_all_balances(self) -> Dict[str, float]:
        raise NotImplementedError

    def send(self, address: str, asset_name: str, amount: float) -> str:
        return self.c_send(address, asset_name, amount)

    def to_nominal(self, asset_name: str, raw_amount: int) -> float:
        raise NotImplementedError

    def to_raw(self, asset_name: str, nominal_amount: float) -> int:
        raise NotImplementedError

    cdef double c_get_balance(self, str asset_name) except? -1:
        raise NotImplementedError

    cdef object c_get_raw_balance(self, str asset_name):
        raise NotImplementedError

    cdef str c_send(self, str address, str asset_name, double amount):
        raise NotImplementedError
