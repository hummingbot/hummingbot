
import asyncio
from os.path import (
    join,
    dirname
)
from typing import (
    List,
    Dict,
    Any,
)

from hummingbot.client.liquidity_bounty.liquidity_bounty_config_map import liquidity_bounty_config_map
from hummingbot.client.config.config_helpers import (
    parse_cvar_value,
    save_to_yml,
)
from hummingbot.client.liquidity_bounty.bounty_utils import LiquidityBounty
from hummingbot.client.settings import LIQUIDITY_BOUNTY_CONFIG_PATH
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class BountyCommand:
    def bounty(self,  # type: HummingbotApplication
               register: bool = False,
               status: bool = False,
               terms: bool = False,
               list: bool = False):
        """ Router function for `bounty` command """
        if terms:
            asyncio.ensure_future(self.bounty_print_terms(), loop=self.ev_loop)
        elif register:
            asyncio.ensure_future(self.bounty_registration(), loop=self.ev_loop)
        elif list:
            asyncio.ensure_future(self.bounty_list(), loop=self.ev_loop)
        else:
            asyncio.ensure_future(self.bounty_show_status(), loop=self.ev_loop)

    async def print_doc(self,  # type: HummingbotApplication
                        doc_path: str):
        with open(doc_path) as doc:
            data = doc.read()
            self._notify(str(data))

    async def bounty_show_status(self,  # type: HummingbotApplication
                                 ):
        """ Show bounty status """
        if self.liquidity_bounty is None:
            self._notify("Liquidity bounty not active. Please register for the bounty by entering `bounty --register`.")
            return
        else:
            status_table: str = self.liquidity_bounty.formatted_status()
            self._notify(status_table)

            volume_metrics: List[Dict[str, Any]] = \
                await self.liquidity_bounty.fetch_filled_volume_metrics(start_time=self.start_time or -1)
            self._notify(self.liquidity_bounty.format_volume_metrics(volume_metrics))

    async def bounty_print_terms(self,  # type: HummingbotApplication
                                 ):
        """ Print bounty Terms and Conditions to output pane """
        await self.print_doc(join(dirname(__file__), "./liquidity_bounty/terms_and_conditions.txt"))

    async def bounty_registration(self,  # type: HummingbotApplication
                                  ):
        """ Register for the bounty program """
        if self.liquidity_bounty:
            self._notify("You are already registered to collect bounties.")
            return
        await self.bounty_config_loop()
        self._notify("Registering for liquidity bounties...")
        self.liquidity_bounty = LiquidityBounty.get_instance()
        try:
            registration_results = await self.liquidity_bounty.register()
            self._notify("Registration successful.")
            client_id = registration_results["client_id"]
            liquidity_bounty_config_map.get("liquidity_bounty_client_id").value = client_id
            await save_to_yml(LIQUIDITY_BOUNTY_CONFIG_PATH, liquidity_bounty_config_map)
            self.liquidity_bounty.start()
            self._notify("Hooray! You are now collecting bounties. ")
        except Exception as e:
            self._notify(str(e))

    async def bounty_list(self,  # type: HummingbotApplication
                          ):
        """ List available bounties """
        if self.liquidity_bounty is None:
            self.liquidity_bounty = LiquidityBounty.get_instance()
        await self.liquidity_bounty.fetch_active_bounties()
        self._notify(self.liquidity_bounty.formatted_bounties())

    async def bounty_config_loop(self,  # type: HummingbotApplication
                                 ):
        """ Configuration loop for bounty registration """
        self.placeholder_mode = True
        self.app.toggle_hide_input()
        self._notify("Starting registration process for liquidity bounties:")

        try:
            for key, cvar in liquidity_bounty_config_map.items():
                if key == "liquidity_bounty_enabled":
                    await self.print_doc(join(dirname(__file__), "./liquidity_bounty/requirements.txt"))
                elif key == "agree_to_terms":
                    await self.bounty_print_terms()
                elif key == "agree_to_data_collection":
                    await self.print_doc(join(dirname(__file__), "./liquidity_bounty/data_collection_policy.txt"))
                elif key == "eth_address":
                    self._notify("\nYour wallets:")
                    self.list("wallets")

                value = await self.config_single_variable(cvar)
                cvar.value = parse_cvar_value(cvar, value)
                if cvar.type == "bool" and cvar.value is False:
                    raise ValueError(f"{cvar.key} is required.")
                await save_to_yml(LIQUIDITY_BOUNTY_CONFIG_PATH, liquidity_bounty_config_map)
        except ValueError as e:
            self._notify(f"Registration aborted: {str(e)}")
        except Exception as e:
            self.logger().error(f"Error configuring liquidity bounty: {str(e)}")

        self.app.change_prompt(prompt=">>> ")
        self.app.toggle_hide_input()
        self.placeholder_mode = False
