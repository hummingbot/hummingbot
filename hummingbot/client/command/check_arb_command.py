from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


class CheckArbCommand:
    def check_arb(
        self,  # type: HummingbotApplication
        exchange_1_market_1: str,
        exchange_2_market_2: str,
    ):
        self.notify(f"check arb called with {exchange_1_market_1}, {exchange_2_market_2}")
