import abc


class Atomic(metaclass=abc.ABCMeta):
    """ABC for objects that can be RLP encoded as is."""


Atomic.register(bytes)
Atomic.register(bytearray)
