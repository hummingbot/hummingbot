"""
Exception types raised in web3's libraries.
"""


class ValidationError(Exception):
    """
    Raised when something does not pass a validation check.
    """


class MismatchedABI(ValidationError):
    """
    Raised when an ABI does not match with supplied parameters, or when an
    attempt is made to access a function/event that does not exist in the ABI.
    """
