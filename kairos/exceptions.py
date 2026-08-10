"""
Exceptions used in the Hummingbot codebase.
"""


class HummingbotBaseException(Exception):
    """
    Most errors raised in Hummingbot should inherit this class so we can
    differentiate them from errors that come from dependencies.
    """


class ArgumentParserError(HummingbotBaseException):
    """
    Unable to parse a command (like start, stop, etc) from the hummingbot client
    """


class OracleRateUnavailable(HummingbotBaseException):
    """
    Asset value from third party is unavailable
    """


class InvalidScriptModule(HummingbotBaseException):
    """
    The file does not contain a ScriptBase subclass
    """


class InvalidController(HummingbotBaseException):
    """
    The file does not contain a ControllerBase subclass
    """
