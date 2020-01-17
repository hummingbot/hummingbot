from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class ExportPrivateKeyCommand:
    async def export_private_key(self,  # type: HummingbotApplication
                                 ):
        if self.acct is None:
            self._notify("Your wallet is currently locked. Please enter \"config\""
                         " to unlock your wallet first")
        else:
            self.placeholder_mode = True
            self.app.toggle_hide_input()

            ans = await self.app.prompt("Are you sure you want to print your private key in plain text? (Yes/No) >>> ")

            if ans.lower() in {"y", "yes"}:
                self._notify("\nWarning: Never disclose this key. Anyone with your private keys can steal any assets "
                             "held in your account.\n")
                self._notify("Your private key:")
                self._notify(self.acct.privateKey.hex())

            self.app.change_prompt(prompt=">>> ")
            self.app.toggle_hide_input()
            self.placeholder_mode = False
