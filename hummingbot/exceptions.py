class HummingbotException(Exception):
    """
    The base exception used by all Hummingbot exceptions
    """


class ArgumentParserError(HummingbotException):
    """
    Unable to parse a command (like start, stop, etc) from the hummingbot client
    """


class OracleRateUnavailable(HummingbotException):
    """
    Asset value from third party is unavailable
    """


class UnsupportedAsset(HummingbotException):
    """
    The hummingbot client or third party exchange does not support this asset.
    """


class UnsupportedOrderType(HummingbotException):
    """
    The order type is not supported for an exchange.
    """


class SingletonException(HummingbotException):
    """
    There can only be one instance of the class.
    """
