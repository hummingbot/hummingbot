import logging


class HummingbotBaseException(Exception):
    """
    Most errors raised in Hummingbot should inherit this class so we can
    differentiate them from errors that come from dependencies.
    """

    def __init__(self, message: str = None):
        super().__init__(message)
        self.logger = logging.getLogger(__name__)

    def log(self, level: int = logging.ERROR):
        self.logger.log(level, self)


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

    def log(self, level: int = logging.ERROR):
        super().log(level)
        self.logger.error(f"Failed to parse command '{self.command}': {self.message}")

    @property
    def command_name(self):
        return self.command


class OracleRateUnavailable(HummingbotBaseException):
    """
    Asset value from third party is unavailable

    Args:
        asset (str): The asset for which the oracle rate is unavailable.
    """

    def __init__(self, asset: str):
        self.asset = asset
        super().__init__(f"Oracle rate for asset '{asset}' is unavailable")

    def log(self, level: int = logging.ERROR):
        super().log(level)
        self.logger.error(f"Oracle rate for asset '{self.asset}' is unavailable")


class InvalidScriptModule(HummingbotBaseException):
    """
    The file does not contain a ScriptBase subclass

    Args:
        filename (str): The filename of the script module.
    """

    def __init__(self, filename: str):
        self.filename = filename
        super().__init__(f"File '{filename}' does not contain a ScriptBase subclass")

    def log(self, level: int = logging.ERROR):
        super().log(level)
        self.logger.error(f"File '{self.filename}' does not contain a ScriptBase subclass")

    @property
    def filename(self):
        return self.filename


class InsufficientFunds(HummingbotBaseException):
    """
    Not enough funds to execute the requested action

    Args:
        asset (str): The asset for which there are insufficient funds.
        amount (float): The amount of the asset that is required.
    """

    def __init__(self, asset: str, amount: float):
        self.asset = asset
        self.amount = amount
        super().__init__(f"Insufficient funds for asset '{asset}'. Require {amount}")

    def log(self, level: int = logging.ERROR):
        super().log(level)
        self.logger.error(f"Insufficient funds for asset '{self.asset}'. Require {self.amount}")


class OrderNotFound(HummingbotBaseException):
    """
    The order could not be found

    Args:
        order_id (str): The ID of the order that could not be found.
    """

    def __init__(self, order_id: str):
        self.order_id = order_id
        super().__init__(f"Order with ID '{order_id}' could not be found")

    def log(self, level: int = logging.ERROR):
        super().log(level)
        self.logger.error(f"Order with ID '{self.order_id}' could not be found")
