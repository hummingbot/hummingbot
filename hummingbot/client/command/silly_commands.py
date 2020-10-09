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
        elif command == "roger":
            safe_ensure_future(self.silly_roger())
            return True
        elif command == "rein":
            safe_ensure_future(self.silly_rein())
            return True    
        elif command == "dennis":
            safe_ensure_future(self.silly_dennis())
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

    async def silly_roger(self,  # type: HummingbotApplication
                          ):
        last_output = "\n".join(self.app.output_field.document.lines)
        self.placeholder_mode = True
        self.app.hide_input = True
        self.clear_output_field()
        for _ in range(0, 3):
            await self.cls_n_display(self.yield_alert("roger"))
            await asyncio.sleep(0.4)
            self.clear_output_field()
        roger_1 = open(f"{RESOURCES_PATH}roger_1.txt").readlines()
        roger_2 = open(f"{RESOURCES_PATH}roger_2.txt").readlines()
        roger_3 = open(f"{RESOURCES_PATH}roger_3.txt").readlines()
        roger_4 = open(f"{RESOURCES_PATH}roger_4.txt").readlines()
        for _ in range(0, 2):
            for _ in range(0, 3):
                await self.cls_n_display(roger_1, 0.1)
                await asyncio.sleep(0.3)
                await self.cls_n_display(roger_2, 0.35)
                await self.cls_n_display(roger_1, 0.25)
                await self.cls_n_display(roger_3, 0.35)
                await self.cls_n_display(roger_1, 0.25)
                await asyncio.sleep(0.4)
            for _ in range(0, 2):
                await self.cls_n_display(roger_4, 0.125)
                await self.cls_n_display(roger_1, 0.3)
                await self.cls_n_display(roger_4, 0.2)
            await asyncio.sleep(0.15)
        self.app.log(last_output)
        self.placeholder_mode = False
        self.app.hide_input = False


    async def silly_rein(self,  # type: HummingbotApplication
                         ):
        last_output = "\n".join(self.app.output_field.document.lines)
        self.placeholder_mode = True
        self.app.hide_input = True
        self.clear_output_field()
        for _ in range(0, 2):
            await self.cls_n_display(self.yield_alert("rein"))
            await asyncio.sleep(0.4)
            self.clear_output_field()    
        rein_1 = open(f"{RESOURCES_PATH}rein_1.txt").readlines()
        rein_2 = open(f"{RESOURCES_PATH}rein_2.txt").readlines()
        rein_3 = open(f"{RESOURCES_PATH}rein_3.txt").readlines()
        for _ in range(0, 2):
                await self.cls_n_display(rein_1, 0.5)
                await self.cls_n_display(rein_2, 0.5)
                await self.cls_n_display(rein_3, 0.5)
        await asyncio.sleep(0.3)
        self.app.log(last_output)
        self.placeholder_mode = False
        self.app.hide_input = False
        
    async def silly_dennis(self,  # type: HummingbotApplication
                           ):
        last_output = "\n".join(self.app.output_field.document.lines)
        self.placeholder_mode = True
        self.app.hide_input = True
        self.clear_output_field()
        dennis_loading_1 = open(f"{RESOURCES_PATH}dennis_loading_1.txt").readlines()
        dennis_loading_2 = open(f"{RESOURCES_PATH}dennis_loading_2.txt").readlines()
        dennis_loading_3 = open(f"{RESOURCES_PATH}dennis_loading_3.txt").readlines()
        dennis_loading_4 = open(f"{RESOURCES_PATH}dennis_loading_4.txt").readlines()
        for _ in range(0, 1):
            await self.cls_n_display(dennis_loading_1, 1)
            await self.cls_n_display(dennis_loading_2, 1)
            await self.cls_n_display(dennis_loading_3, 1)
            await self.cls_n_display(dennis_loading_4, 1)
            await asyncio.sleep(0.5)
        dennis_1 = open(f"{RESOURCES_PATH}dennis_1.txt").readlines()
        dennis_2 = open(f"{RESOURCES_PATH}dennis_2.txt").readlines()
        dennis_3 = open(f"{RESOURCES_PATH}dennis_3.txt").readlines()
        dennis_4 = open(f"{RESOURCES_PATH}dennis_4.txt").readlines()
        for _ in range(0, 1):
            await self.cls_n_display(dennis_1, 1)
            await self.cls_n_display(dennis_2, 1)
            await self.cls_n_display(dennis_3, 1)
            await self.cls_n_display(dennis_4, 1)
        await asyncio.sleep(4)
        self.app.log(last_output)
        self.placeholder_mode = False
        self.app.hide_input = False

    async def cls_n_display(self, lines, delay=0.5):
        await asyncio.sleep(delay)
        self.clear_output_field()
        self.app.log("".join(lines))
        
    def clear_output_field(self):
        self.app.log("\n" * 50)

    def yield_alert(self, custom_alert = None):
        alert = """
                                ====================================
                                ║                                  ║
                                ║  OPEN SOFTWARE FOR OPEN FINANCE  ║
                                ║                                  ║
                                ====================================
        """
        if custom_alert is not None:
            try:
                lines = open(f"{RESOURCES_PATH}{custom_alert}_alert.txt").readlines()
                alert = "".join(lines)
            except Exception:
                pass
        return f"{alert}" + ("\n" * 18)
