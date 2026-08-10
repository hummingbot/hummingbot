"""
Exceptions used in the Kairos-2 codebase.
"""


class KairosBaseException(Exception):
    """
    Most errors raised in Kairos-2 should inherit this class so we can
    differentiate them from errors that come from dependencies.
    """


class ArgumentParserError(KairosBaseException):
    """
    Unable to parse a command (like start, stop, etc) from the Kairos-2 client
    """


class OracleRateUnavailable(KairosBaseException):
    """
    Asset value from third party is unavailable
    """


class InvalidScriptModule(KairosBaseException):
    """
    The file does not contain a ScriptBase subclass
    """


class InvalidController(KairosBaseException):
    """
    The file does not contain a ControllerBase subclass
    """
