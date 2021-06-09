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
