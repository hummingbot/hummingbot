# This exposes the eth-utils exception for backwards compatibility,
# for any library that catches eth_keys.exceptions.ValidationError
from eth_utils import ValidationError  # noqa: F401


class BadSignature(Exception):
    pass
