import logging
from typing import Callable, Dict, TypeVar

from hummingbot.logger import HummingbotLogger

from ..connecting_functions.exception_log_manager import log_exception

T = TypeVar("T")


def sequence_verifier(
        event_message: T,
        *,
        sequence_reader: Callable[[T], int],
        sequences: Dict[str, int],
        key: str,
        logger: HummingbotLogger | logging.Logger | None = None
) -> T:
    """
    Sequence verification and update method
    :param event_message: The message received from the exchange.
    :param sequence_reader: The method to read the sequence number from the message.
    :param sequences: The dictionary of sequence numbers.
    :param key: The key to the sequence number in the dictionary.
    :param logger: The logger to use.
    :return: Generator of unmodified messages received from the exchange.
    """
    # log_if_possible(logger, "DEBUG", f"Received {event_message}")
    try:
        sequence = sequence_reader(event_message)

        if sequence != sequences[key] + 1:
            if logger:
                logger.warning(
                    f"Sequence number mismatch. Expected {sequences[key] + 1}, received {sequence} for {key}")
            # This should never occur, it indicates a flaw in the code
            if sequence < sequences[key]:
                raise ValueError(
                    f"Sequence number lower than expected {sequences[key] + 1}, received {sequence} for {key}")
        sequences[key] = sequence
    except Exception as e:
        log_exception(e, logger, "ERROR", f"Error with the sequence_reader for {event_message}")

    return event_message
