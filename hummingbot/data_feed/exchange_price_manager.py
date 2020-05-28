from typing import (
    Dict,
    List,
    Optional
)
from decimal import Decimal
from hummingbot.data_feed.data_feed_base import DataFeedBase
from hummingbot.data_feed.binance_price_feed import BinancePriceFeed
from hummingbot.data_feed.liquid_price_feed import LiquidPriceFeed
from hummingbot.data_feed.kucoin_price_feed import KucoinPriceFeed
from hummingbot.core.utils.async_utils import safe_gather


class ExchangePriceManager:
    supported_exchanges: Dict[str, DataFeedBase] = {'binance': BinancePriceFeed.get_instance(),
                                                    'liquid': LiquidPriceFeed.get_instance(),
                                                    'kucoin': KucoinPriceFeed.get_instance()}
    ex_feeds: Dict[str, DataFeedBase] = {}

    @staticmethod
    def set_exchanges_to_feed(exchange_names: List[str], use_binance_when_none_supported=True):
        ExchangePriceManager.stop()
        for name in exchange_names:
            if name in ExchangePriceManager.supported_exchanges:
                ExchangePriceManager.ex_feeds[name] = ExchangePriceManager.supported_exchanges[name]
        if len(ExchangePriceManager.ex_feeds) == 0 and use_binance_when_none_supported:
            ExchangePriceManager.ex_feeds['binance'] = ExchangePriceManager.supported_exchanges['binance']

    @staticmethod
    def start():
        for ex_feed in ExchangePriceManager.ex_feeds.values():
            ex_feed.stop()
            ex_feed.start()

    @staticmethod
    async def wait_til_ready():
        await safe_gather(*[feed.get_ready() for feed in ExchangePriceManager.ex_feeds.values()])

    @staticmethod
    def stop():
        for ex_feed in ExchangePriceManager.ex_feeds.values():
            ex_feed.stop()
        ExchangePriceManager.ex_feeds.clear()

    @staticmethod
    def get_price(base_asset: str, quote_asset: str) -> Optional[Decimal]:
        trading_pair = f"{base_asset}-{quote_asset}"
        for ex_feed in ExchangePriceManager.ex_feeds.values():
            if trading_pair in ex_feed.price_dict:
                return ex_feed.price_dict[trading_pair]

        return None
