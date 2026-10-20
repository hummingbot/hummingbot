from typing import Dict

from hummingbot.connector.derivative.bitget_perpetual import bitget_perpetual_constants as CONNECTOR_CONSTANTS
from hummingbot.data_feed.candles_feed.bitget_perpetual_candles.bitget_perpetual_candles import BitgetPerpetualCandles


class BitgetPerpetualDemoCandles(BitgetPerpetualCandles):
    """
    Candles for Bitget's demo-trading domain.

    Bitget serves demo trading from the SAME REST host as mainnet and distinguishes
    it with the ``paptrading: 1`` header alone -- there is no demo subdomain and no
    separate product type. That is true of the public candles endpoint as well: the
    same URL returns a DIFFERENT series depending on the header, because demo has
    its own order book.

    So this cannot be solved by registering the mainnet class under the demo name.
    That would quietly feed mainnet prices to a bot trading on demo, and nothing in
    the data would reveal it.

    Subclassed rather than added to the mainnet feed so mainnet behaviour cannot
    regress; the only difference is the header.
    """

    @property
    def name(self):
        return f"{CONNECTOR_CONSTANTS.DEMO_DOMAIN}_{self._trading_pair}"

    def _get_rest_candles_headers(self) -> Dict[str, str]:
        return {CONNECTOR_CONSTANTS.DEMO_TRADING_HEADER: "1"}
