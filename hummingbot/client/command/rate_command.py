from decimal import Decimal
import threading
from typing import (
    TYPE_CHECKING,
)
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.rate_oracle.rate_oracle import RateOracle, RateOracleSource

s_float_0 = float(0)
s_decimal_0 = Decimal("0")

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class RateCommand:
    def rate(self,  # type: HummingbotApplication
             pair: str,
             ):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.trades)
            return
        safe_ensure_future(self.show_rate(pair))

    async def show_rate(self,  # type: HummingbotApplication
                        pair: str,
                        ):
        pair = pair.upper()
        self._notify(f"Source: {RateOracleSource.binance.name}")
        rate = await RateOracle.get_rate_from_source(RateOracleSource.binance, pair)
        if rate is None:
            self._notify("Rate is not available.")
            return
        base, quote = pair.split("-")
        self._notify(f"1 {base} = {rate} {quote}")
