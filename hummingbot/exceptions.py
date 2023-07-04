"""
Exceptions used in the Hummingbot codebase.
"""


class HummingbotBaseException(Exception):
    """
    Most errors raised in Hummingbot should inherit this class so we can
    differentiate them from errors that come from dependencies.
    """


class ArgumentParserError(HummingbotBaseException):
    def __init__(self, command: str, message: str):
        self.command = command
        self.message = message
        super().__init__(f"Error while parsing command '{command}': {message}")
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
