"""
Types for the Discovery Protocol.
"""

from typing import (
    NewType,
)

NodeID = NewType("NodeID", bytes)
r"""
A 32-byte identifier for a node in the Discovery DHT.

.. doctest::

    >>> from eth_typing import NodeID
    >>> NodeID(b'\x01' * 32)
    b'\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01'
"""
