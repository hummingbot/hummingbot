import logging
from decimal import Decimal
from typing import List, Tuple, Union

from hummingbot.core.remote_control.remote_command_executor import RemoteCommandExecutor
from hummingbot.core.event.event_forwarder import SourceInfoEventForwarder
from hummingbot.core.event.events import (
    RemoteEvent,
    RemoteCmdEvent)
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.strategy_base import StrategyBase

s_decimal_zero = Decimal(0)
rt_logger = None


class RemoteCommandsDelegateBase:
    """
    Base class for RemoteCommandsDelegate classes to be used inside strategies.
    Use the `on_remote_cmd` method to handle all received remote events and access the strategy via `self.strategy`
    """

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global rt_logger
        if rt_logger is None:
            rt_logger = logging.getLogger(__name__)
        return rt_logger

    def __init__(self,
                 strategy: StrategyBase):
        # Add strategy property to allow strategy control from delegate.
        self.strategy: StrategyBase = strategy

        # One forwarder for all remote command events.
        self._process_remote_cmd_forwarder: SourceInfoEventForwarder = SourceInfoEventForwarder(self.on_remote_cmd)
        self._event_pairs: List[Tuple[RemoteEvent, SourceInfoEventForwarder]] = [
            (RemoteEvent.RemoteCmdEvent, self._process_remote_cmd_forwarder)]

    def register_events(self):
        """
        Should be called during `strategy.start()`
        """
        executor = RemoteCommandExecutor.get_instance()
        for event_pair in self._event_pairs:
            executor.add_listener(event_pair[0], event_pair[1])

    def unregister_events(self):
        """
        Should be called during `strategy.stop()`
        """
        executor = RemoteCommandExecutor.get_instance()
        for event_pair in self._event_pairs:
            executor.remove_listener(event_pair[0], event_pair[1])

    def on_remote_cmd(self,
                      event_tag: int,
                      executor: RemoteCommandExecutor,
                      event: Union[RemoteCmdEvent]):
        """
        Is called upon a remote command received.

        Remote command events have the following properties:
            event.event_descriptor
            event.command
            event.timestamp_received
            event.timestamp_event
            event.exchange
            event.symbol
            event.interval
            event.price
            event.volume
            event.inventory
            event.order_bid_spread
            event.order_ask_spread
            event.order_amount
            event.order_levels
            event.order_level_spread
        """

        # Implement this function within the strategy class
        raise NotImplementedError("Remote Commands not implemented.")
