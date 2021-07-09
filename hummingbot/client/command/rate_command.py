from decimal import Decimal
import threading
from typing import (
    TYPE_CHECKING,
)
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.exceptions import OracleRateUnavailable

s_float_0 = float(0)
s_decimal_0 = Decimal("0")

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class RateCommand:
    def rate(self,  # type: HummingbotApplication
             pair: str,
             token: str
             ):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.trades)
            return
        if pair:
            safe_ensure_future(self.show_rate(pair))
        elif token:
            safe_ensure_future(self.show_token_value(token))

    async def show_rate(self,  # type: HummingbotApplication
                        pair: str,
                        ):
        try:
            msg = await RateCommand.oracle_rate_msg(pair)
        except OracleRateUnavailable:
            msg = "Rate is not available."
        self._notify(msg)

    @staticmethod
    async def oracle_rate_msg(pair: str,
                              ):
        pair = pair.upper()
        rate = await RateOracle.rate_async(pair)
        if rate is None:
            raise OracleRateUnavailable
        base, quote = pair.split("-")
        return f"Source: {RateOracle.source.name}\n1 {base} = {rate} {quote}"

    async def show_token_value(self,  # type: HummingbotApplication
                               token: str
                               ):
        token = token.upper()
        self._notify(f"Source: {RateOracle.source.name}")
        rate = await RateOracle.global_rate(token)
        if rate is None:
            self._notify("Rate is not available.")
            return
        self._notify(f"1 {token} = {RateOracle.global_token_symbol} {rate} {RateOracle.global_token}")
