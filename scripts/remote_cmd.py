from datetime import datetime
from os.path import realpath, join
from hummingbot.script.script_base import ScriptBase
from hummingbot.core.event.events import (
    RemoteCmdEvent
)


LOGS_PATH = realpath(join(__file__, "../../logs/"))
SCRIPT_LOG_FILE = f"{LOGS_PATH}/logs_script.log"


def log_to_file(file_name, message):
    with open(file_name, "a+") as f:
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " - " + message + "\n")


class RemoteCmdScript(ScriptBase):
    """
    Demonstrates how to hook into remote command events.
    """

    def __init__(self):
        super().__init__()

    def on_remote_command_event(self, event: RemoteCmdEvent):
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

        # Log all received remote events to script log.
        log_to_file(SCRIPT_LOG_FILE, str(event))

        #
        # REMOTE COMMANDS EVENT EXAMPLE # 1
        #
        # If event descriptor matches, send new events via other descriptors to control other connected bots.
        if event.event_descriptor == "hbot_1":

            # Call balance command on `hbot_2`
            self.broadcast_remote_event(RemoteCmdEvent(event_descriptor="hbot_2",
                                                       command="balance"))

            # Stop `hbot_3`
            self.broadcast_remote_event(RemoteCmdEvent(event_descriptor="hbot_3",
                                                       command="stop"))

        #
        # REMOTE COMMANDS EVENT EXAMPLE # 2
        #
        # If event contains new PMM spread parameters, update the strategy.
        if event.event_descriptor == "hbot_1" and event.order_bid_spread:
            self.pmm_parameters.bid_spread = event.order_bid_spread
        if event.event_descriptor == "hbot_1" and event.order_ask_spread:
            self.pmm_parameters.ask_spread = event.order_ask_spread

        #
        # REMOTE COMMANDS EVENT EXAMPLE # 3
        #
        # If event contains new PMM order level parameters, update the strategy.
        if event.event_descriptor == "hbot_1" and event.order_levels:
            self.pmm_parameters.order_levels = event.order_levels

        #
        # REMOTE COMMANDS EVENT EXAMPLE # 4
        #
        # If event contains new PMM inventory percentage, update the strategy.
        if event.event_descriptor == "hbot_1" and event.inventory:
            self.pmm_parameters.inventory_target_base_pct = event.inventory
