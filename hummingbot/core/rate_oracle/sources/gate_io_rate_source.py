from decimal import Decimal
from typing import TYPE_CHECKING, Dict, Optional

from hummingbot.connector.exchange.gate_io import gate_io_constants as CONSTANTS
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache

if TYPE_CHECKING:
    from hummingbot.connector.exchange.gate_io.gate_io_exchange import GateIoExchange


class GateIoRateSource(RateSourceBase):
    def __init__(self):
        super().__init__()
        self._exchange: Optional[GateIoExchange] = None  # delayed because of circular reference

    @property
    def name(self) -> str:
        return "gate_io"

    @async_ttl_cache(ttl=30, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        self._ensure_exchange()
        results = {}
        try:
            records = await self._exchange._api_get(
                path_url=CONSTANTS.TICKER_PATH_URL,
                is_auth_required=False,
                limit_id=CONSTANTS.TICKER_PATH_URL
            )
            for record in records:
                try:
                    pair = await self._exchange.trading_pair_associated_to_exchange_symbol(record["currency_pair"])
                except KeyError:
                    # Ignore results for which their symbols is not tracked by the connector
                    continue

                if str(record["lowest_ask"]) == '' or str(record["highest_bid"]) == '':
                    # Ignore results for which the order book is empty
                    continue

                if Decimal(str(record["lowest_ask"])) > 0 and Decimal(str(record["highest_bid"])) > 0:
                    results[pair] = (Decimal(str(record["lowest_ask"])) +
                                     Decimal(str(record["highest_bid"]))) / Decimal("2")
        except Exception:
            self.logger().exception(
                msg="Unexpected error while retrieving rates from Gate.IO. Check the log file for more info.",
            )
        return results

    def _ensure_exchange(self):
        if self._exchange is None:
            self._exchange = self._build_gate_io_connector_without_private_keys()

    @staticmethod
    def _build_gate_io_connector_without_private_keys() -> 'GateIoExchange':
        from hummingbot.client.hummingbot_application import HummingbotApplication
        from hummingbot.connector.exchange.gate_io.gate_io_exchange import GateIoExchange

        app = HummingbotApplication.main_application()
        client_config_map = app.client_config_map

        return GateIoExchange(
            client_config_map=client_config_map,
            gate_io_api_key="",
            gate_io_secret_key="",
            trading_pairs=[],
            trading_required=False,
        )
