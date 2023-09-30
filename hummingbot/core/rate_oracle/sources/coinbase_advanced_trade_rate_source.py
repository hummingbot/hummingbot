from decimal import Decimal
from typing import Dict, Optional

from hummingbot.connector.exchange.coinbase_advanced_trade_v2.coinbase_advanced_trade_v2_exchange import (
    CoinbaseAdvancedTradeV2Exchange as CoinbaseExchange,
)
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_gather


class CoinbaseAdvancedTradeRateSource(RateSourceBase):
    def __init__(self):
        super().__init__()
        self._coinbase_exchange: Optional[CoinbaseExchange] = None  # delayed because of circular reference

    @property
    def name(self) -> str:
        return "coinbase_advanced_trade"

    @async_ttl_cache(ttl=30, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        self._ensure_exchanges()
        results = {}
        tasks = [
            self._get_coinbase_prices(exchange=self._coinbase_exchange, quote_token="USD"),
        ]
        task_results = await safe_gather(*tasks, return_exceptions=True)
        for task_result in task_results:
            if isinstance(task_result, Exception):
                self.logger().error(
                    msg="Unexpected error while retrieving rates from Coinbase. Check the log file for more info.",
                    exc_info=task_result,
                )
                break
            else:
                results |= task_result
        return results

    def _ensure_exchanges(self):
        if self._coinbase_exchange is None:
            self._coinbase_exchange = self._build_coinbase_connector_without_private_keys(domain="com")

    @staticmethod
    async def _get_coinbase_prices(exchange: CoinbaseExchange, quote_token: str = None) -> Dict[str, Decimal]:
        """
        Fetches coinbase prices

        :param exchange: The exchange instance from which to query prices.
        :param quote_token: A quote symbol, if specified only pairs with the quote symbol are included for prices
        :return: A dictionary of trading pairs and prices
        """
        token_price: Dict[str, str] = await exchange.get_exchange_rates(quote_token=quote_token)

        results = {}
        for token, price in token_price.items():
            results[token] = Decimal(price)
        return results

    @staticmethod
    def _build_coinbase_connector_without_private_keys(domain: str) -> CoinbaseExchange:
        from hummingbot.client.hummingbot_application import HummingbotApplication

        app = HummingbotApplication.main_application()
        client_config_map = app.client_config_map

        return CoinbaseExchange(
            client_config_map=client_config_map,
            coinbase_advanced_trade_v2_api_key="",
            coinbase_advanced_trade_v2_api_secret="",
            trading_pairs=[],
            trading_required=False,
            domain=domain,
        )
