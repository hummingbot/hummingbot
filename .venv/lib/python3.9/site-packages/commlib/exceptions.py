"""
Defines a set of custom exceptions used throughout the commlib module.

The `BaseException` class provides a common base for all custom exceptions, with
support for storing additional error information.

The other exception classes inherit from `BaseException` and provide more
specific error types, such as `ConnectionError`, `AMQPError`, `MQTTError`, etc.
These exceptions can be raised by various components of the commlib module to
indicate specific error conditions.
"""

class BaseException(Exception):
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors


class ConnectionError(BaseException):
    def __init__(self, message, errors=None):
       super().__init__(message, errors)


class AMQPError(BaseException):
    def __init__(self, message, errors=None):
        super().__init__(message, errors)


class MQTTError(BaseException):
    def __init__(self, message, errors=None):
        super().__init__(message, errors)


class RedisError(BaseException):
    def __init__(self, message, errors=None):
        super().__init__(message, errors)


class RPCClientError(Exception):
    def __init__(self, message, errors=None):
        super().__init__(message, errors)


class RPCServiceError(Exception):
    def __init__(self, message, errors=None):
        super().__init__(message, errors)


class RPCRequestError(Exception):
    def __init__(self, message, errors=None):
        super().__init__(message, errors)


class RPCClientTimeoutError(RPCClientError):
    def __init__(self, message, errors=None):
        super().__init__(message, errors)


class RPCServerError(Exception):
    def __init__(self, message, errors=None):
        super().__init__(message, errors)


class PublisherError(Exception):
    def __init__(self, message, errors=None):
        super().__init__(message, errors)


class SubscriberError(Exception):
    def __init__(self, message, errors=None):
        super().__init__(message, errors)


class NodeError(Exception):
    def __init__(self, message, errors=None):
        super().__init__(message, errors)


class SerializationError(Exception):
    def __init__(self, message, errors=None):
        super().__init__(message, errors)
