import asyncio
from typing import (
    TYPE_CHECKING,
)
from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication

RESOURCES_PATH = "hummingbot/client/command/silly_resources/"


class SillyCommands:

    def be_silly(self,  # type: HummingbotApplication
                 raw_command: str) -> bool:
        command = raw_command.split(" ")[0]
        if command == "hummingbot":
            safe_ensure_future(self.silly_hummingbot())
            return True
        else:
            return False

    async def silly_hummingbot(self,  # type: HummingbotApplication
                               ):
        last_output = "\n".join(self.app.output_field.document.lines)
        self.placeholder_mode = True
        self.app.hide_input = True
        self.clear_output_field()
        for _ in range(0, 3):
            await self.cls_n_display(self.yield_alert())
            await asyncio.sleep(0.5)
            self.clear_output_field()
        hb_with_flower_1 = open(f"{RESOURCES_PATH}hb_with_flower_1.txt").readlines()
        hb_with_flower_2 = open(f"{RESOURCES_PATH}hb_with_flower_2.txt").readlines()
        hb_with_flower_up_close_1 = open(f"{RESOURCES_PATH}hb_with_flower_up_close_1.txt").readlines()
        hb_with_flower_up_close_2 = open(f"{RESOURCES_PATH}hb_with_flower_up_close_2.txt").readlines()
        for _ in range(0, 2):
            for _ in range(0, 5):
                await self.cls_n_display(hb_with_flower_1, 0.125)
                await self.cls_n_display(hb_with_flower_2, 0.125)
            for _ in range(0, 5):
                await self.cls_n_display(hb_with_flower_up_close_1, 0.125)
                await self.cls_n_display(hb_with_flower_up_close_2, 0.125)
        self.app.log(last_output)
        self.placeholder_mode = False
        self.app.hide_input = False

    async def cls_n_display(self, lines, delay=0.5):
        await asyncio.sleep(delay)
        self.clear_output_field()
        self.app.log("".join(lines))

    def clear_output_field(self):
        self.app.log("\n" * 50)

    def yield_alert(self):
        return """
                                ====================================
                                ║                                  ║
                                ║  OPEN SOFTWARE FOR OPEN FINANCE  ║
                                ║                                  ║
                                ====================================
        """ + ("\n" * 18)
