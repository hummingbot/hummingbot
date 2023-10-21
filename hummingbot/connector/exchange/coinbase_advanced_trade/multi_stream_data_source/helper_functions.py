import logging
from typing import Any, Callable, Dict, Generator, TypeVar

from hummingbot.logger import HummingbotLogger

from ..coinbase_advanced_trade_web_utils import get_timestamp_from_exchange_time

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


def stamptime_filter_sequence(
        event_message: Dict[str, Any],
        *,
        sequencer: Callable[[int, str], Any],
        logger: HummingbotLogger | logging.Logger | None = None,
) -> Generator[T, None, None]:
    """
    Reformat the timestamp to seconds.
    Filter out heartbeat and (subscriptions?) messages.
    Call the sequencer to track the sequence number.
    :param event_message: The message received from the exchange.
    :param sequencer: The method to track the sequence number.
    :param logger: The logger to use.
    """
    """
    https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-channels#user-channel
    {
      "channel": "user",
      "client_id": "",
      "timestamp": "2023-02-09T20:33:57.609931463Z",
      "sequence_num": 0,
      "events": [...]
    }
    """
    if logger:
        if event_message["channel"] == "user":
            logger.debug(f"Sequence handler {event_message['channel']}:{event_message['sequence_num']}:{event_message}")
        else:
            logger.debug(f"Sequence handler {event_message['channel']}:{event_message['sequence_num']}")
            logger.debug(f"{event_message}")

    # sequence_num = 0: subscriptions message for heartbeats
    # sequence_num = 1: user snapshot message
    # sequence_num = 2: subscriptions message for user
    sequencer(event_message["sequence_num"], event_message["channel"])

    if event_message["channel"] == "user":
        # logging.debug(f"      DEBUG: Filter {event_message}")
        if isinstance(event_message["timestamp"], str):
            event_message["timestamp"] = get_timestamp_from_exchange_time(event_message["timestamp"], "s")
        yield event_message
    # else:
    #     logging.debug(f"*** DEBUG: Filtering message {event_message} {event_message['channel']} not user")
