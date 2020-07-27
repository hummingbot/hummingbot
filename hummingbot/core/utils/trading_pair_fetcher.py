import aiohttp
import asyncio
from typing import (
    List,
    Dict,
    Any,
    Optional,
)
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger
import logging

from .async_utils import safe_ensure_future
from .ssl_client_request import SSLClientRequest

BINANCE_ENDPOINT = "https://api.binance.com/api/v1/exchangeInfo"
RADAR_RELAY_ENDPOINT = "https://api.radarrelay.com/v3/markets"
BAMBOO_RELAY_ENDPOINT = "https://rest.bamboorelay.com/main/0x/markets"
COINBASE_PRO_ENDPOINT = "https://api.pro.coinbase.com/products/"
HUOBI_ENDPOINT = "https://api.huobi.pro/v1/common/symbols"
LIQUID_ENDPOINT = "https://api.liquid.com/products"
BITTREX_ENDPOINT = "https://api.bittrex.com/v3/markets"
KUCOIN_ENDPOINT = "https://api.kucoin.com/api/v1/symbols"
DOLOMITE_ENDPOINT = "https://exchange-api.dolomite.io/v1/markets"
ETERBASE_ENDPOINT = "https://api.eterbase.exchange/api/markets"
KRAKEN_ENDPOINT = "https://api.kraken.com/0/public/AssetPairs"

API_CALL_TIMEOUT = 5


class TradingPairFetcher:
    _sf_shared_instance: "TradingPairFetcher" = None
    _tpf_logger: Optional[HummingbotLogger] = None
    _tpf_http_client: Optional[aiohttp.ClientSession] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._tpf_logger is None:
            cls._tpf_logger = logging.getLogger(__name__)
        return cls._tpf_logger

    @classmethod
    def get_instance(cls) -> "TradingPairFetcher":
        if cls._sf_shared_instance is None:
            cls._sf_shared_instance = TradingPairFetcher()
        return cls._sf_shared_instance

    @classmethod
    def http_client(cls) -> aiohttp.ClientSession:
        if cls._tpf_http_client is None:
            if not asyncio.get_event_loop().is_running():
                raise EnvironmentError("Event loop must be running to start HTTP client session.")
            cls._tpf_http_client = aiohttp.ClientSession(request_class=SSLClientRequest)
        return cls._tpf_http_client

    def __init__(self):
        self.ready = False
        self.trading_pairs: Dict[str, Any] = {}
        safe_ensure_future(self.fetch_all())

    async def fetch_binance_trading_pairs(self) -> List[str]:
        try:
            from hummingbot.market.binance.binance_market import BinanceMarket
            client: aiohttp.ClientSession = self.http_client()
            async with client.get(BINANCE_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    data = await response.json()
                    raw_trading_pairs = [d["symbol"] for d in data["symbols"] if d["status"] == "TRADING"]
                    trading_pair_list: List[str] = []
                    for raw_trading_pair in raw_trading_pairs:
                        converted_trading_pair: Optional[str] = \
                            BinanceMarket.convert_from_exchange_trading_pair(raw_trading_pair)
                        if converted_trading_pair is not None:
                            trading_pair_list.append(converted_trading_pair)
                        else:
                            self.logger().debug(f"Could not parse the trading pair {raw_trading_pair}, skipping it...")
                    return trading_pair_list

        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for binance trading pairs
            pass

        return []

    async def fetch_radar_relay_trading_pairs(self) -> List[str]:
        try:
            from hummingbot.market.radar_relay.radar_relay_market import RadarRelayMarket
            trading_pairs = set()
            page_count = 1
            client: aiohttp.ClientSession = self.http_client()
            while True:
                async with client.get(f"{RADAR_RELAY_ENDPOINT}?perPage=100&page={page_count}", timeout=API_CALL_TIMEOUT) \
                        as response:
                    if response.status == 200:
                        markets = await response.json()
                        new_trading_pairs = set(map(lambda details: details.get('id'), markets))
                        if len(new_trading_pairs) == 0:
                            break
                        else:
                            trading_pairs = trading_pairs.union(new_trading_pairs)
                        page_count += 1
                        trading_pair_list: List[str] = []
                        for raw_trading_pair in trading_pairs:
                            converted_trading_pair: Optional[str] = \
                                RadarRelayMarket.convert_from_exchange_trading_pair(raw_trading_pair)
                            if converted_trading_pair is not None:
                                trading_pair_list.append(converted_trading_pair)
                            else:
                                self.logger().debug(f"Could not parse the trading pair {raw_trading_pair}, skipping it...")
                        return trading_pair_list
                    else:
                        break
        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for radar trading pairs
            pass

        return []

    async def fetch_bamboo_relay_trading_pairs(self) -> List[str]:
        try:
            from hummingbot.market.bamboo_relay.bamboo_relay_market import BambooRelayMarket

            trading_pairs = set()
            page_count = 1
            client: aiohttp.ClientSession = self.http_client()
            while True:
                async with client.get(f"{BAMBOO_RELAY_ENDPOINT}?perPage=1000&page={page_count}",
                                      timeout=API_CALL_TIMEOUT) as response:
                    if response.status == 200:

                        markets = await response.json()
                        new_trading_pairs = set(map(lambda details: details.get("id"), markets))
                        if len(new_trading_pairs) == 0:
                            break
                        else:
                            trading_pairs = trading_pairs.union(new_trading_pairs)
                        page_count += 1
                        trading_pair_list: List[str] = []
                        for raw_trading_pair in trading_pairs:
                            converted_trading_pair: Optional[str] = \
                                BambooRelayMarket.convert_from_exchange_trading_pair(raw_trading_pair)
                            if converted_trading_pair is not None:
                                trading_pair_list.append(converted_trading_pair)
                            else:
                                self.logger().debug(f"Could not parse the trading pair {raw_trading_pair}, skipping it...")
                        return trading_pair_list
                    else:
                        break

        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for bamboo trading pairs
            pass

        return []

    async def fetch_coinbase_pro_trading_pairs(self) -> List[str]:
        try:
            from hummingbot.market.coinbase_pro.coinbase_pro_market import CoinbaseProMarket

            client: aiohttp.ClientSession = self.http_client()
            async with client.get(COINBASE_PRO_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    markets = await response.json()
                    raw_trading_pairs: List[str] = list(map(lambda details: details.get('id'), markets))
                    trading_pair_list: List[str] = []
                    for raw_trading_pair in raw_trading_pairs:
                        converted_trading_pair: Optional[str] = \
                            CoinbaseProMarket.convert_from_exchange_trading_pair(raw_trading_pair)
                        if converted_trading_pair is not None:
                            trading_pair_list.append(converted_trading_pair)
                        else:
                            self.logger().debug(f"Could not parse the trading pair {raw_trading_pair}, skipping it...")
                    return trading_pair_list

        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for coinbase trading pairs
            pass

        return []

    async def fetch_eterbase_trading_pairs(self) -> List[str]:
        try:
            from hummingbot.market.eterbase.eterbase_market import EterbaseMarket

            client: aiohttp.ClientSession() = self.http_client()
            async with client.get(ETERBASE_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    markets = await response.json()
                    raw_trading_pairs: List[str] = list(map(lambda trading_market: trading_market.get('symbol'), filter(lambda details: details.get('state') == 'Trading', markets)))
                    trading_pair_list: List[str] = []
                    for raw_trading_pair in raw_trading_pairs:
                        converted_trading_pair: Optional[str] = \
                            EterbaseMarket.convert_from_exchange_trading_pair(raw_trading_pair)
                        if converted_trading_pair is not None:
                            trading_pair_list.append(converted_trading_pair)
                        else:
                            self.logger().debug(f"Could not parse the trading pair {raw_trading_pair}, skipping it...")
                    return trading_pair_list
        except Exception:
            pass
            # Do nothing if the request fails -- there will be no autocomplete for eterbase trading pairs
        return []

    async def fetch_huobi_trading_pairs(self) -> List[str]:
        try:
            from hummingbot.market.huobi.huobi_market import HuobiMarket

            client: aiohttp.ClientSession = self.http_client()
            async with client.get(HUOBI_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    all_trading_pairs: Dict[str, Any] = await response.json()
                    valid_trading_pairs: list = []
                    for item in all_trading_pairs["data"]:
                        if item["state"] == "online":
                            valid_trading_pairs.append(item["symbol"])
                    trading_pair_list: List[str] = []
                    for raw_trading_pair in valid_trading_pairs:
                        converted_trading_pair: Optional[str] = \
                            HuobiMarket.convert_from_exchange_trading_pair(raw_trading_pair)
                        if converted_trading_pair is not None:
                            trading_pair_list.append(converted_trading_pair)
                        else:
                            self.logger().debug(f"Could not parse the trading pair {raw_trading_pair}, skipping it...")
                    return trading_pair_list

        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for huobi trading pairs
            pass

        return []

    @staticmethod
    async def fetch_liquid_trading_pairs() -> List[str]:
        try:
            # Returns a List of str, representing each active trading pair on the exchange.
            client: aiohttp.ClientSession = TradingPairFetcher.http_client()
            async with client.get(LIQUID_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    products: List[Dict[str, Any]] = await response.json()
                    for data in products:
                        data['trading_pair'] = '-'.join([data['base_currency'], data['quoted_currency']])
                    return [
                        product["trading_pair"] for product in products
                        if product['disabled'] is False
                    ]

        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete available
            pass

        return []

    @staticmethod
    async def fetch_bittrex_trading_pairs() -> List[str]:
        try:
            client: aiohttp.ClientSession = TradingPairFetcher.http_client()
            async with client.get(BITTREX_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    all_trading_pairs: List[Dict[str, Any]] = await response.json()
                    return [item["symbol"]
                            for item in all_trading_pairs
                            if item["status"] == "ONLINE"]
        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for bittrex trading pairs
            pass
        return []

    @staticmethod
    async def fetch_kucoin_trading_pairs() -> List[str]:
        async with aiohttp.ClientSession() as client:
            async with client.get(KUCOIN_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    try:
                        data: Dict[str, Any] = await response.json()
                        all_trading_pairs = data.get("data", [])
                        return [item["symbol"] for item in all_trading_pairs if item["enableTrading"] is True]
                    except Exception:
                        pass
                        # Do nothing if the request fails -- there will be no autocomplete for kucoin trading pairs
                return []

    @staticmethod
    async def fetch_kraken_trading_pairs() -> List[str]:
        try:
            async with aiohttp.ClientSession() as client:
                async with client.get(KRAKEN_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                    if response.status == 200:
                        from hummingbot.market.kraken.kraken_market import KrakenMarket
                        data: Dict[str, Any] = await response.json()
                        raw_pairs = data.get("result", [])
                        converted_pairs: List[str] = []
                        for pair, details in raw_pairs.items():
                            if "." not in pair:
                                try:
                                    wsname = details["wsname"]  # pair in format BASE/QUOTE
                                    converted_pairs.append(KrakenMarket.convert_from_exchange_trading_pair(wsname))
                                except IOError:
                                    pass
                        return [item for item in converted_pairs]
        except Exception:
            pass
            # Do nothing if the request fails -- there will be no autocomplete for kraken trading pairs
        return []

    async def fetch_dolomite_trading_pairs(self) -> List[str]:
        try:
            from hummingbot.market.dolomite.dolomite_market import DolomiteMarket
            client: aiohttp.ClientSession = TradingPairFetcher.http_client()
            async with client.get(DOLOMITE_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    all_trading_pairs: Dict[str, Any] = await response.json()
                    valid_trading_pairs: list = []
                    for item in all_trading_pairs["data"]:
                        valid_trading_pairs.append(item["market"])
                    trading_pair_list: List[str] = []
                    for raw_trading_pair in valid_trading_pairs:
                        converted_trading_pair: Optional[str] = \
                            DolomiteMarket.convert_from_exchange_trading_pair(raw_trading_pair)
                        if converted_trading_pair is not None:
                            trading_pair_list.append(converted_trading_pair)
                        else:
                            self.logger().debug(f"Could not parse the trading pair {raw_trading_pair}, skipping it...")
                    return trading_pair_list
        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for dolomite trading pairs
            pass

        return []

    async def fetch_all(self):
        tasks = [self.fetch_binance_trading_pairs(),
                 self.fetch_bamboo_relay_trading_pairs(),
                 self.fetch_coinbase_pro_trading_pairs(),
                 self.fetch_dolomite_trading_pairs(),
                 self.fetch_huobi_trading_pairs(),
                 self.fetch_liquid_trading_pairs(),
                 self.fetch_bittrex_trading_pairs(),
                 self.fetch_kucoin_trading_pairs(),
                 self.fetch_kraken_trading_pairs(),
                 self.fetch_radar_relay_trading_pairs(),
                 self.fetch_eterbase_trading_pairs()]

        # Radar Relay has not yet been migrated to a new version
        # Endpoint needs to be updated after migration
        # radar_relay_trading_pairs = await self.fetch_radar_relay_trading_pairs()

        results = await safe_gather(*tasks, return_exceptions=True)
        self.trading_pairs = {
            "binance": results[0],
            "bamboo_relay": results[1],
            "coinbase_pro": results[2],
            "dolomite": results[3],
            "huobi": results[4],
            "liquid": results[5],
            "bittrex": results[6],
            "kucoin": results[7],
            "kraken": results[8],
            "radar_relay": results[9],
            "eterbase": results[10],
        }
        self.ready = True
