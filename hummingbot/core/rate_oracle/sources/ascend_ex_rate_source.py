from decimal import Decimal
from typing import TYPE_CHECKING, Dict, Optional

from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache

if TYPE_CHECKING:
    from hummingbot.connector.exchange.ascend_ex.ascend_ex_exchange import AscendExExchange


class AscendExRateSource(RateSourceBase):
    def __init__(self):
        super().__init__()
        self._exchange: Optional[AscendExExchange] = None  # delayed because of circular reference

    @property
    def name(self) -> str:
        return "ascend_ex"

    @async_ttl_cache(ttl=30, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        self._ensure_exchange()
        results = {}
        try:
            records = await self._exchange.get_all_pairs_prices()
            for record in records["data"]:
                pair = await self._exchange.trading_pair_associated_to_exchange_symbol(record["symbol"])
                if Decimal(record["ask"][0]) > 0 and Decimal(record["bid"][0]) > 0:
                    results[pair] = (Decimal(str(record["ask"][0])) + Decimal(str(record["bid"][0]))) / Decimal("2")
        except Exception:
            self.logger().exception(
                msg="Unexpected error while retrieving rates from AscendEx. Check the log file for more info.",
            )
        return results

    def _ensure_exchange(self):
        if self._exchange is None:
            self._exchange = self._build_ascend_ex_connector_without_private_keys()

    @staticmethod
    def _build_ascend_ex_connector_without_private_keys() -> 'AscendExExchange':
        from hummingbot.client.hummingbot_application import HummingbotApplication
        from hummingbot.connector.exchange.ascend_ex.ascend_ex_exchange import AscendExExchange

        app = HummingbotApplication.main_application()
        client_config_map = app.client_config_map

        return AscendExExchange(
            client_config_map=client_config_map,
            ascend_ex_api_key="",
            ascend_ex_secret_key="",
            ascend_ex_group_id="",
            trading_pairs=[],
            trading_required=False,
        )
