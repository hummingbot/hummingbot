from decimal import Decimal
from typing import TYPE_CHECKING, Dict, Optional

from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache

if TYPE_CHECKING:
    from hummingbot.connector.exchange.kucoin.kucoin_exchange import KucoinExchange


class KucoinRateSource(RateSourceBase):
    def __init__(self):
        super().__init__()
        self._exchange: Optional[KucoinExchange] = None  # delayed because of circular reference

    @property
    def name(self) -> str:
        return "kucoin"

    @async_ttl_cache(ttl=30, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        self._ensure_exchange()
        results = {}
        try:
            records = await self._exchange.get_all_pairs_prices()
            for record in records["data"]["ticker"]:
                try:
                    pair = await self._exchange.trading_pair_associated_to_exchange_symbol(record["symbolName"])
                except KeyError:
                    # Ignore results for which their symbols is not tracked by the connector
                    continue
                if Decimal(record["buy"]) > 0 and Decimal(record["sell"]) > 0:
                    results[pair] = (Decimal(str(record["buy"])) + Decimal(str(record["sell"]))) / Decimal("2")
        except Exception:
            self.logger().exception(
                msg="Unexpected error while retrieving rates from KuCoin. Check the log file for more info.",
            )
        return results

    def _ensure_exchange(self):
        if self._exchange is None:
            self._exchange = self._build_kucoin_connector_without_private_keys()

    @staticmethod
    def _build_kucoin_connector_without_private_keys() -> 'KucoinExchange':
        from hummingbot.client.hummingbot_application import HummingbotApplication
        from hummingbot.connector.exchange.kucoin.kucoin_exchange import KucoinExchange

        app = HummingbotApplication.main_application()
        client_config_map = app.client_config_map

        return KucoinExchange(
            client_config_map=client_config_map,
            kucoin_api_key="",
            kucoin_passphrase="",
            kucoin_secret_key="",
            trading_pairs=[],
            trading_required=False,
        )
