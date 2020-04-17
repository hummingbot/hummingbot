from typing import TYPE_CHECKING
from hummingbot.client.config.security import Security
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class ExportPrivateKeyCommand:
    async def export_private_key(self,  # type: HummingbotApplication
                                 ):
        if not Security.any_wallets():
            self._notify("There is no wallet in your conf folder, please connect wallet first.")
            return
        self.placeholder_mode = True
        self.app.toggle_hide_input()
        await self.check_password()
        await Security.wait_til_decryption_done()
        self._notify("\nWarning: Never disclose private key. Anyone with your private keys can steal any assets "
                     "held in your account.\n")
        for key, value in Security.private_keys().items():
            self._notify(f"Public Address: {key}\nPrivate Key: {value.hex()}\n")
        self.app.change_prompt(prompt=">>> ")
        self.app.toggle_hide_input()
        self.placeholder_mode = False
