"""
Exceptions used in the Hummingbot codebase.
"""


class HummingbotBaseException(Exception):
    """
    Most errors raised in Hummingbot should inherit this class so we can
    differentiate them from errors that come from dependencies.
    """

    def __init__(self):
        super().__init__()


class ArgumentParserError(HummingbotBaseException):
    """
    Unable to parse a command (like start, stop, etc) from the hummingbot client

    Args:
        command (str): The command that was unable to be parsed.
        message (str): The error message.
    """

    def __init__(self, command: str, message: str):
        self.command = command
        self.message = message
        super().__init__(f"Error while parsing command '{command}': {message}")


class OracleRateUnavailable(HummingbotBaseException):
    """
    Asset value from third party is unavailable

    Args:
        asset (str): The asset for which the oracle rate is unavailable.
    """

    def __init__(self, asset: str):
        self.asset = asset
        super().__init__(f"Oracle rate for asset '{asset}' is unavailable")


class InvalidScriptModule(HummingbotBaseException):
    """
    The file does not contain a ScriptBase subclass

    Args:
        filename (str): The filename of the script module.
    """

    def __init__(self, filename: str):
        self.filename = filename
        super().__init__(f"File '{filename}' does not contain a ScriptBase subclass")
