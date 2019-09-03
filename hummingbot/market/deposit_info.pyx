cdef class DepositInfo:
    def __init__(self, address: str, **extras):
        self.address = address
        self.extras = extras

    def __repr__(self) -> str:
        if len(self.extras) > 0:
            return f"DepositInfo(address='{self.address}', extras={self.extras})"
        else:
            return f"DepositInfo(address='{self.address}')"
