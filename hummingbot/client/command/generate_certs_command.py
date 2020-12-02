#!/usr/bin/env python

from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.ssl_cert import certs_files_exist, create_self_sign_certs
from hummingbot import cert_path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class GenerateCertsCommand:
    def generate_certs(self,  # type: HummingbotApplication
                       ):
        safe_ensure_future(self._generate_certs(), loop=self.ev_loop)

    async def _generate_certs(self,  # type: HummingbotApplication
                              ):
        if certs_files_exist():
            self.app.log(f"Gateway SSL certification files exist in {cert_path()}.")
            self.app.log("To create new certification files, please first manually delete those files.")
            return
        self.app.clear_input()
        self.placeholder_mode = True
        self.app.hide_input = True
        while True:
            pass_phase = await self.app.prompt(prompt='Enter pass phase to generate Gateway SSL certifications  >>> ',
                                               is_password=True)
            if pass_phase is not None and len(pass_phase) > 0:
                break
            self.app.log("Error: Invalid pass phase")
        create_self_sign_certs(pass_phase)
        self._notify(f"Gateway SSL certification files are created in {cert_path()}.")
        self.placeholder_mode = False
        self.app.hide_input = False
        self.app.change_prompt(prompt=">>> ")
