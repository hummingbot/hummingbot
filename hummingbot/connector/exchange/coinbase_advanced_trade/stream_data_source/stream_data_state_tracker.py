import logging
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, TypeVar

from hummingbot.logger import HummingbotLogger

StreamDataStateT = TypeVar("StreamDataStateT", bound=Enum)


class StreamDataStateVerifier(Generic[StreamDataStateT]):
    _logger: HummingbotLogger | logging.Logger | None = None

    @classmethod
    def logger(cls) -> HummingbotLogger | logging.Logger:
        if cls._logger is None:
            name: str = HummingbotLogger.logger_name_for_class(cls)
            cls._logger = logging.getLogger(name)
        return cls._logger

    def __init__(
            self,
            initial_state: StreamDataStateT,
            transitions: Dict[StreamDataStateT, List[StreamDataStateT]],
            verify_func: Callable[[StreamDataStateT, Dict[str, Any]], StreamDataStateT | None]):
        """
        :param initial_state: The initial state of the connection.
        :param transitions: A dictionary defining allowed state transitions.
        :param verify_func: A function to extract the state from a message.
        """
        self._state: StreamDataStateT = initial_state
        self._transitions: Dict[StreamDataStateT, List[StreamDataStateT]] = transitions
        self._verify_func: Callable[[StreamDataStateT, Dict[str, Any]], StreamDataStateT | None] = verify_func

    @property
    def state(self) -> StreamDataStateT:
        return self._state

    def verify_and_update_state(self, message: Dict[str, Any]) -> None:
        """
        Verify the incoming message and update the connection state.

        :param message: The incoming message from the server.
        """
        next_state: StreamDataStateT | None = self._verify_func(self._state, message)

        if next_state is None:
            self.logger().warning("Received message that could not be verified.")
            return

        if next_state in self._transitions.get(self._state, []):
            self._state: StreamDataStateT = next_state
        else:
            self.logger().warning(f"Invalid state transition from {self.state} to {next_state}")

    def __repr__(self) -> str:
        return f"StreamDataStateVerifier(state={self._state})"

    def __str__(self) -> str:
        return repr(self)


if __name__ == "__main__":
    class ConnectionState(Enum):
        NOT_CONNECTED = "NOT_CONNECTED"
        HEARTBEAT_SUBSCRIBED = "HEARTBEAT_SUBSCRIBED"
        SNAPSHOT_RECEIVED = "USER_SNAPSHOT_RECEIVED"
        SUBSCRIBED = "USER_SUBSCRIBED"
        STREAMING = "STREAMING"

    i_state = ConnectionState.NOT_CONNECTED
    ts: Dict[ConnectionState, List[ConnectionState]] = {
        ConnectionState.NOT_CONNECTED: [
            ConnectionState.HEARTBEAT_SUBSCRIBED,
            ConnectionState.SNAPSHOT_RECEIVED,
            ConnectionState.SUBSCRIBED,
        ],
        ConnectionState.HEARTBEAT_SUBSCRIBED: [
            ConnectionState.SNAPSHOT_RECEIVED,
            ConnectionState.SUBSCRIBED,
        ],
        ConnectionState.SNAPSHOT_RECEIVED: [ConnectionState.SUBSCRIBED],
        ConnectionState.SUBSCRIBED: [ConnectionState.STREAMING],
    }

    # Define your verification function
    def verify_func_on_sequence(current_state: ConnectionState, message: Dict[str, int]) -> ConnectionState | None:
        sequence_num: int | None = message.get("sequence_num")
        if sequence_num == 0:
            return ConnectionState.HEARTBEAT_SUBSCRIBED
        elif sequence_num == 1:
            return ConnectionState.SNAPSHOT_RECEIVED
        elif sequence_num == 2:
            return ConnectionState.SUBSCRIBED
        elif sequence_num >= 3:
            return ConnectionState.STREAMING
        else:
            return None

    # Usage
    verifier = StreamDataStateVerifier(i_state, ts, verify_func_on_sequence)

    # Simulate incoming messages
    verifier.verify_and_update_state({"sequence_num": 0})
    print(verifier.state)
    verifier.verify_and_update_state({"sequence_num": 1})
    print(verifier.state)
    verifier.verify_and_update_state({"sequence_num": 2})
    print(verifier.state)
