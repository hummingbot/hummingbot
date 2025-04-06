"""
A collection of optional backends that implement hashing.

You must manually select and install the backend you want. If the backend is
not installed, then trying to import the module for that backend will cause an
:class:`ImportError`.

See :ref:`Choose a hashing backend` for more.
"""

SUPPORTED_BACKENDS = [
    "pycryptodome",
    "pysha3",
]
