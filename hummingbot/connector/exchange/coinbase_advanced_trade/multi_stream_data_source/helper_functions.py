import logging
from typing import Any, Callable, Dict, Generator, TypeVar

from hummingbot.logger import HummingbotLogger

T = TypeVar("T")


def sequence_verifier(
        event_message: Dict[str, Any],
        *,
        sequence_reader: Callable[[Dict[str, Any]], int],
        sequences: Dict[str, int],
        key: str,
        logger: HummingbotLogger | logging.Logger | None = None
) -> Generator[T, None, None]:
    """
    Sequence verification and update method
    :param event_message: The message received from the exchange.
    :param sequence_reader: The method to read the sequence number from the message.
    :param sequences: The dictionary of sequence numbers.
    :param key: The key to the sequence number in the dictionary.
    :param logger: The logger to use.
    :return: Generator of unmodified messages received from the exchange.
    """
    sequence = sequence_reader(event_message)
    if sequence != sequences[key] + 1:
        if logger:
            logger.warning(f"Sequence number mismatch. Expected {sequences[key] + 1}, received {sequence} for {key}")
        # This should never occur, it indicates a flaw in the code
        if sequence < sequences[key]:
            raise ValueError(f"Sequence number lower than expected {sequences[key] + 1}, received {sequence} for {key}")
    sequences[key] = sequence

    yield event_message
