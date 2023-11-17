from typing import Any


class ExceptionWithFunctionCall(Exception):
    """Exception raised to signal an error that allows for a reconnect attempt."""

    def __init__(self, *args, item: Any = None):
        super().__init__(*args)
        self.item = item

    def __str__(self):
        return f"{self.__class__.__name__}({super().__str__()}, item={self.item})"


class ExceptionWithItem(Exception):
    """Exception raised to signal an error that allows for a reconnect attempt."""

    def __init__(self, *args, item: Any = None):
        super().__init__(*args)
        self.item = item

    def __str__(self):
        return f"{self.__class__.__name__}({super().__str__()}, item={self.item})"


class ConditionalPutError(ExceptionWithItem):
    """Exception raised when an error occurs while putting an item into a pipe."""
    pass


class ConditionalGetError(ExceptionWithItem):
    """Exception raised when an error occurs while putting an item into a pipe."""
    pass


class DataGeneratorError(ExceptionWithItem):
    """Exception raised when an error occurs while transferring an item from pipe to pipe."""
    pass


class SourceGetError(ExceptionWithItem):
    """Exception raised when an error occurs while getting an item from a pipe."""
    pass


class DestinationPutError(ExceptionWithItem):
    """Exception raised when an error occurs while putting an item into a pipe."""
    pass


class DataTransformerError(ExceptionWithItem):
    """Exception raised when an error occurs with a DataHandler."""
    pass


class _ShieldingException(ExceptionWithItem):
    pass


class _CancelledSilencedException(ExceptionWithItem):
    pass


class _ReconnectError(Exception):
    """Exception raised to signal an error that allows for a reconnect attempt."""
    pass
