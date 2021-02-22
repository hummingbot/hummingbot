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
        elif command == "fly":
            safe_ensure_future(self.silly_victor())
            return True
        elif command == "rein":
            safe_ensure_future(self.silly_rein())
            return True
        elif command in ("jack", "nullably"):
            safe_ensure_future(self.silly_jack())
            return True
        elif command == "hodl":
            safe_ensure_future(self.silly_hodl())
            return True
        elif command == "dennis":
            safe_ensure_future(self.silly_dennis())
            return True
        else:
            return False

    async def silly_jack(self,  # type: HummingbotApplication
                         ):
        self.placeholder_mode = True
        self.app.hide_input = True
        await self.text_n_wait("Hi there,", 1)
        await self.text_n_wait("This is Jack.", 1)
        await self.text_n_wait("I am the lead developer of Hummingbot.", 1.5)
        await self.text_n_wait("If you are reading this.", 1.5)
        await self.text_n_wait("I'm probably dea...", 1.5)
        for _ in range(3):
            await self.text_n_wait(".", 1)
        await self.text_n_wait("I'm kidding.", 1.5)
        await self.text_n_wait("Don't call police.", 1.5)
        await self.text_n_wait("I'm well and busy coding for you all.", 2)
        await self.text_n_wait("Get in touch @nullably on Github and Twitter.", 2.5)
        await self.text_n_wait("Happy trading and don't get rekt.", 2.5)
        jack_1 = open(f"{RESOURCES_PATH}jack_1.txt").readlines()
        jack_2 = open(f"{RESOURCES_PATH}jack_2.txt").readlines()
        await self.cls_display_delay(jack_1, 1.5)
        await self.cls_display_delay(jack_2, 1.5)
        self.placeholder_mode = False
        self.app.hide_input = False

    async def silly_hodl(self,  # type: HummingbotApplication
                         ):
        self.placeholder_mode = True
        self.app.hide_input = True
        stay_calm = open(f"{RESOURCES_PATH}hodl_stay_calm.txt").readlines()
        and_hodl = open(f"{RESOURCES_PATH}hodl_and_hodl.txt").readlines()
        bitcoin = open(f"{RESOURCES_PATH}hodl_bitcoin.txt").readlines()
        await self.cls_display_delay(stay_calm, 1.75)
        await self.cls_display_delay(and_hodl, 1.75)
        for _ in range(3):
            await self.cls_display_delay("\n" * 50, 0.25)
            await self.cls_display_delay(bitcoin, 0.25)
        await self.cls_display_delay(bitcoin, 1.75)
        self.placeholder_mode = False
        self.app.hide_input = False

    async def silly_hummingbot(self,  # type: HummingbotApplication
                               ):
        self.placeholder_mode = True
        self.app.hide_input = True
        for _ in range(0, 3):
            await self.cls_display_delay(self.display_alert())
        hb_with_flower_1 = open(f"{RESOURCES_PATH}hb_with_flower_1.txt").readlines()
        hb_with_flower_2 = open(f"{RESOURCES_PATH}hb_with_flower_2.txt").readlines()
        hb_with_flower_up_close_1 = open(f"{RESOURCES_PATH}hb_with_flower_up_close_1.txt").readlines()
        hb_with_flower_up_close_2 = open(f"{RESOURCES_PATH}hb_with_flower_up_close_2.txt").readlines()
        for _ in range(0, 2):
            for _ in range(0, 5):
                await self.cls_display_delay(hb_with_flower_1, 0.125)
                await self.cls_display_delay(hb_with_flower_2, 0.125)
            for _ in range(0, 5):
                await self.cls_display_delay(hb_with_flower_up_close_1, 0.125)
                await self.cls_display_delay(hb_with_flower_up_close_2, 0.125)
        self.placeholder_mode = False
        self.app.hide_input = False

    async def silly_roger(self,  # type: HummingbotApplication
                          ):
        self.placeholder_mode = True
        self.app.hide_input = True
        for _ in range(0, 3):
            await self.cls_display_delay(self.display_alert("roger"))
        roger_1 = open(f"{RESOURCES_PATH}roger_1.txt").readlines()
        roger_2 = open(f"{RESOURCES_PATH}roger_2.txt").readlines()
        roger_3 = open(f"{RESOURCES_PATH}roger_3.txt").readlines()
        roger_4 = open(f"{RESOURCES_PATH}roger_4.txt").readlines()
        for _ in range(0, 2):
            for _ in range(0, 3):
                await self.cls_display_delay(roger_1, 0.1)
                # await asyncio.sleep(0.3)
                await self.cls_display_delay(roger_2, 0.35)
                await self.cls_display_delay(roger_1, 0.25)
                await self.cls_display_delay(roger_3, 0.35)
                await self.cls_display_delay(roger_1, 0.25)
                # await asyncio.sleep(0.4)
            for _ in range(0, 2):
                await self.cls_display_delay(roger_4, 0.125)
                await self.cls_display_delay(roger_1, 0.3)
                await self.cls_display_delay(roger_4, 0.2)
        await asyncio.sleep(0.15)
        self.placeholder_mode = False
        self.app.hide_input = False

    async def silly_victor(self,  # type: HummingbotApplication
                           ):
        self.placeholder_mode = True
        self.app.hide_input = True
        hb_with_flower_1 = open(f"{RESOURCES_PATH}money-fly_1.txt").readlines()
        hb_with_flower_2 = open(f"{RESOURCES_PATH}money-fly_2.txt").readlines()
        for _ in range(0, 5):
            for _ in range(0, 5):
                await self.cls_display_delay(hb_with_flower_1, 0.125)
                await self.cls_display_delay(hb_with_flower_2, 0.125)
        await asyncio.sleep(0.3)
        self.placeholder_mode = False
        self.app.hide_input = False

    async def silly_rein(self,  # type: HummingbotApplication
                         ):
        self.placeholder_mode = True
        self.app.hide_input = True
        for _ in range(0, 2):
            await self.cls_display_delay(self.display_alert("rein"))
        rein_1 = open(f"{RESOURCES_PATH}rein_1.txt").readlines()
        rein_2 = open(f"{RESOURCES_PATH}rein_2.txt").readlines()
        rein_3 = open(f"{RESOURCES_PATH}rein_3.txt").readlines()
        for _ in range(0, 2):
            await self.cls_display_delay(rein_1, 0.5)
            await self.cls_display_delay(rein_2, 0.5)
            await self.cls_display_delay(rein_3, 0.5)
        await asyncio.sleep(0.3)
        self.placeholder_mode = False
        self.app.hide_input = False

    async def text_n_wait(self, text, delay):
        self.app.log(text)
        await asyncio.sleep(delay)

    async def silly_dennis(self,  # type: HummingbotApplication
                           ):
        self.placeholder_mode = True
        self.app.hide_input = True
        dennis_loading_1 = open(f"{RESOURCES_PATH}dennis_loading_1.txt").readlines()
        dennis_loading_2 = open(f"{RESOURCES_PATH}dennis_loading_2.txt").readlines()
        dennis_loading_3 = open(f"{RESOURCES_PATH}dennis_loading_3.txt").readlines()
        dennis_loading_4 = open(f"{RESOURCES_PATH}dennis_loading_4.txt").readlines()
        for _ in range(0, 1):
            await self.cls_display_delay(dennis_loading_1, 1)
            await self.cls_display_delay(dennis_loading_2, 1)
            await self.cls_display_delay(dennis_loading_3, 1)
            await self.cls_display_delay(dennis_loading_4, 1)
            # await asyncio.sleep(0.5)
        dennis_1 = open(f"{RESOURCES_PATH}dennis_1.txt").readlines()
        dennis_2 = open(f"{RESOURCES_PATH}dennis_2.txt").readlines()
        dennis_3 = open(f"{RESOURCES_PATH}dennis_3.txt").readlines()
        dennis_4 = open(f"{RESOURCES_PATH}dennis_4.txt").readlines()
        for _ in range(0, 1):
            await self.cls_display_delay(dennis_1, 1)
            await self.cls_display_delay(dennis_2, 1)
            await self.cls_display_delay(dennis_3, 1)
            await self.cls_display_delay(dennis_4, 1)
        await asyncio.sleep(4)
        self.placeholder_mode = False
        self.app.hide_input = False

    async def cls_display_delay(self, lines, delay=0.5):
        self.app.output_field.buffer.save_to_undo_stack()
        self.app.log("".join(lines), save_log=False)
        await asyncio.sleep(delay)
        self.app.output_field.buffer.undo()

    async def stop_live_update(self):
        if self.app.live_updates is True:
            self.app.live_updates = False
            await asyncio.sleep(1)

    def display_alert(self, custom_alert = None):
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
