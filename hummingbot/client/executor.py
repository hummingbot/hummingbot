import asyncio
import logging
from typing import TYPE_CHECKING

from hummingbot import init_logging
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.core.event.events import HummingbotUIEvent
from hummingbot.core.pubsub import PubSub

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


# Monkey patching here as _handle_exception gets the UI hanged into Press ENTER screen mode
def _handle_exception_patch(self, loop, context):
    if "exception" in context:
        logging.getLogger(__name__).error(f"Unhandled error in prompt_toolkit: {context.get('exception')}",
                                          exc_info=True)


class HeadlessExecutor(PubSub):
    def __init__(self,
                 hb_app: "HummingbotApplication"):
        super().__init__()
        # add self.to_stop_config to know if cancel is triggered
        self.to_stop_config: bool = False

        self.live_updates = False
        self.hb_app = hb_app

        # settings
        self.input_event = None

    def clear_input(self):
        """clear_input
        Mock to fake call from ConfigCommand so it does not crash

        Args:

        """
        pass

    def change_prompt(self, prompt: str, is_password: bool = False):
        pass

    def did_start(self):
        log_level = global_config_map.get("log_level").value
        init_logging("hummingbot_logs.yml", override_log_level=log_level)
        self.trigger_event(HummingbotUIEvent.Start, self)

    async def run(self):
        # asyncio.get_event_loop()
        self.did_start()
        if not self.hb_app.ev_loop.is_running():
            self.hb_app.ev_loop.run_forever()
        else:
            while True:
                await asyncio.sleep(0.001)

    def log(self, text: str, save_log: bool = True):
        self.logger().info(text)

    def exit(self):
        pass
