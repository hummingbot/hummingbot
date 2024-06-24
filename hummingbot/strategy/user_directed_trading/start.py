from typing import TYPE_CHECKING

from hummingbot.strategy.user_directed_trading.user_directed_trading import UserDirectedTradingStrategy

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


def start(self: "HummingbotApplication"):
    self.strategy = UserDirectedTradingStrategy()
    self.strategy.init_params()
