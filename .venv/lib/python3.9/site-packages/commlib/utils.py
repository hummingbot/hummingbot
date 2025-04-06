import os
import re
import time
import uuid
import logging
from rich.logging import RichHandler


def camelcase_to_snakecase(_str: str) -> str:
    """camelcase_to_snakecase.
    Transform a camelcase string to  snakecase

    Args:
        _str (str): String to apply transformation.

    Returns:
        str: Transformed string
    """
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", _str)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def gen_timestamp() -> int:
    """gen_timestamp.
    Generate a timestamp.

    Args:

    Returns:
        int: Timestamp in integer representation. User `str()` to
            transform to string.
    """
    return int(1.0 * (time.time() + 0.5) * 1000)


def gen_random_id() -> str:
    """gen_random_id.
    Generates a random unique id, using the uuid library.

    Args:

    Returns:
        str: String representation of the random unique id
    """
    return str(uuid.uuid4()).replace("-", "")


class Rate:

    def __init__(self, hz: int):
        """__init__.
        Initializes a `Rate` object with the specified Hz (Hertz) rate.

        Args:
            hz (int): The rate in Hertz (Hz) to use for the `Rate` object.

        Attributes:
            _hz (int): The rate in Hertz (Hz) for the `Rate` object.
            _tsleep (float): The time in seconds to sleep between each iteration, calculated as 1.0 / `_hz`.
        """

        self._hz = hz
        self._tsleep = 1.0 / hz

    def sleep(self):
        """sleep.
        Sleeps for the time specified by the `_tsleep` attribute of the `Rate` object.

        This method is used to implement the desired rate specified by the `hz` parameter
        passed to the `Rate` constructor. It ensures that the code execution is paused for
        the appropriate amount of time between each iteration, in order to achieve the
        desired rate.
        """

        time.sleep(self._tsleep)


LOGGING_FORMAT = "%(message)s"
LOG_LEVEL = os.getenv("COMMLIB_LOG_LEVEL", "INFO")

logging.basicConfig(
    level=LOG_LEVEL, format=LOGGING_FORMAT, datefmt="[%X]", handlers=[RichHandler()]
)
