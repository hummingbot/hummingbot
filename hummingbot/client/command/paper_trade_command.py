from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class PaperTradeCommand:
    def paper_trade(self,  # type: HummingbotApplication
                    ):
        self.config("paper_trade_enabled")
