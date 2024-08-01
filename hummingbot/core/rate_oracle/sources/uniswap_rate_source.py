import asyncio
import functools
from decimal import Decimal
from typing import Dict, List, Optional

from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_gather


class UniswapRateSource(RateSourceBase):
    def __init__(self, extra_token_ids: List[str]):
        super().__init__()
        from hummingbot.data_feed.amm_gateway_data_feed import AmmGatewayDataFeed
        self._uniswap_data_feed: Optional[AmmGatewayDataFeed] = None
        from hummingbot.connector.exchange.binance.binance_exchange import BinanceExchange
        self._binance_exchange: Optional[BinanceExchange] = None  # delayed because of circular reference
        self._binance_us_exchange: Optional[BinanceExchange] = None  # delayed because of circular reference
        self._extra_token_ids = extra_token_ids

    @property
    def extra_token_ids(self) -> List[str]:
        return self._extra_token_ids

    @extra_token_ids.setter
    def extra_token_ids(self, new_ids: List[str]):
        self._extra_token_ids = new_ids

    @property
    def name(self) -> str:
        return "uniswap"

    def try_event(self, fn):
        @functools.wraps(fn)
        async def try_raise_event(*args, **kwargs):
            while True:
                try:
                    res = await fn(*args, **kwargs)
                    return res
                except IOError as e:
                    self.logger().warning(f"IOError:{e}")
                except Exception as e:
                    self.logger().error(f"Unhandled error in uniswap rate source response: {str(e)}", exc_info=True)
                    raise Exception(f"Unhandled error in CoinGecko rate source response: {str(e)}")

        return try_raise_event

    @async_ttl_cache(ttl=30, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        """
        :param quote_token: The quote token for which to fetch prices
        :return A dictionary of trading pairs and prices
        """
        results = dict()
        results["USDT-CUSD"] = Decimal("1.0")
        results["USDT-USDCET"] = Decimal("1.0")
        if quote_token is None:
            raise NotImplementedError("Must supply a quote token to fetch prices for Uniswap")
        self._ensure_data_feed()

        for token, price in self._uniswap_data_feed.price_dict.items():
            results[token] = price.sell_price

        tasks = [
            self._get_binance_prices(exchange=self._binance_exchange),
        ]
        task_results = await safe_gather(*tasks, return_exceptions=True)
        for task_result in task_results:
            if isinstance(task_result, Exception):
                self.logger().error(
                    msg="Unexpected error while retrieving rates from Binance. Check the log file for more info.",
                    exc_info=task_result,
                )
                break
            else:
                results.update(task_result)

        return results

    def _ensure_data_feed(self):
        # from hummingbot.client.hummingbot_application import HummingbotApplication
        # app = HummingbotApplication.main_application()
        # client_config_map = app.client_config_map
        if self._uniswap_data_feed is None:
            gateway, binance = self._build_gateway()
            self._binance_exchange = binance

            from hummingbot.data_feed.amm_gateway_data_feed import AmmGatewayDataFeed

            self._uniswap_data_feed = AmmGatewayDataFeed(
                gateway,
                connector_chain_network="uniswap_celo_mainnet",
                trading_pairs=set(self.extra_token_ids),
                order_amount_in_base=Decimal("1"),
                update_interval=30.0
            )
            self._uniswap_data_feed.start()

    async def _sleep(self, delay: float):
        await asyncio.sleep(delay)

    @staticmethod
    def _build_binance_connector_without_private_keys(domain: str, client_config_map):
        from hummingbot.connector.exchange.binance.binance_exchange import BinanceExchange

        return BinanceExchange(
            client_config_map=client_config_map,
            binance_api_key="",
            binance_api_secret="",
            trading_pairs=[],
            trading_required=False,
            domain=domain,
        )

    @staticmethod
    def _build_gateway():
        from hummingbot.client.hummingbot_application import HummingbotApplication

        app = HummingbotApplication.main_application()
        client_config_map = app.client_config_map

        from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient

        gateway = GatewayHttpClient.get_instance(client_config_map)

        binance_exchange = UniswapRateSource._build_binance_connector_without_private_keys("com", client_config_map)

        return gateway, binance_exchange

    @staticmethod
    async def _get_binance_prices(exchange, quote_token: str = None) -> Dict[str, Decimal]:
        """
        Fetches binance prices

        :param exchange: The exchange instance from which to query prices.
        :param quote_token: A quote symbol, if specified only pairs with the quote symbol are included for prices
        :return: A dictionary of trading pairs and prices
        """
        pairs_prices = await exchange.get_all_pairs_prices()
        results = {}
        for pair_price in pairs_prices:
            try:
                trading_pair = await exchange.trading_pair_associated_to_exchange_symbol(symbol=pair_price["symbol"])
            except KeyError:
                continue  # skip pairs that we don't track
            if quote_token is not None:
                base, quote = split_hb_trading_pair(trading_pair=trading_pair)
                if quote != quote_token:
                    continue
            bid_price = pair_price.get("bidPrice")
            ask_price = pair_price.get("askPrice")
            if bid_price is not None and ask_price is not None and 0 < Decimal(bid_price) <= Decimal(ask_price):
                results[trading_pair] = (Decimal(bid_price) + Decimal(ask_price)) / Decimal("2")

        return results
