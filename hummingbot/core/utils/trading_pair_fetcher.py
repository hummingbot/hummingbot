import aiohttp
import asyncio
from typing import (
    List,
    Dict,
    Any,
    Optional,
)

from hummingbot.logger import HummingbotLogger
import logging

from .async_utils import safe_ensure_future
from .ssl_client_request import SSLClientRequest

BINANCE_ENDPOINT = "https://api.binance.com/api/v1/exchangeInfo"
DDEX_ENDPOINT = "https://api.ddex.io/v3/markets"
RADAR_RELAY_ENDPOINT = "https://api.radarrelay.com/v2/markets"
BAMBOO_RELAY_ENDPOINT = "https://rest.bamboorelay.com/main/0x/markets"
COINBASE_PRO_ENDPOINT = "https://api.pro.coinbase.com/products/"
IDEX_REST_ENDPOINT = "https://api.idex.market/returnTicker"
HUOBI_ENDPOINT = "https://api.huobi.pro/v1/common/symbols"
LIQUID_ENDPOINT = "https://api.liquid.com/products"
BITTREX_ENDPOINT = "https://api.bittrex.com/v3/markets"
DOLOMITE_ENDPOINT = "https://exchange-api.dolomite.io/v1/markets"
BITCOIN_COM_ENDPOINT = "https://api.exchange.bitcoin.com/api/2/public/symbol"

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
                    trading_pair_structs = data.get("symbols")
                    raw_trading_pairs = list(map(lambda details: details.get("symbol"), trading_pair_structs))
                    # Binance API has an error where they have a symbol called 123456
                    # The symbol endpoint is
                    # https://api.binance.com/api/v1/exchangeInfo
                    if "123456" in raw_trading_pairs:
                        raw_trading_pairs.remove("123456")
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

    async def fetch_ddex_trading_pairs(self) -> List[str]:
        try:
            from hummingbot.market.ddex.ddex_market import DDEXMarket
            client: aiohttp.ClientSession = self.http_client()
            async with client.get(DDEX_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    response = await response.json()
                    markets = response.get("data").get("markets")
                    raw_trading_pairs = list(map(lambda details: details.get('id'), markets))
                    trading_pair_list: List[str] = []
                    for raw_trading_pair in raw_trading_pairs:
                        converted_trading_pair: Optional[str] = \
                            DDEXMarket.convert_from_exchange_trading_pair(raw_trading_pair)
                        if converted_trading_pair is not None:
                            trading_pair_list.append(converted_trading_pair)
                        else:
                            self.logger().debug(f"Could not parse the trading pair {raw_trading_pair}, skipping it...")
                    return trading_pair_list

        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for ddex trading pairs
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

    async def fetch_idex_trading_pairs(self) -> List[str]:
        try:
            from hummingbot.market.idex.idex_market import IDEXMarket

            client: aiohttp.ClientSession = self.http_client()
            async with client.get(IDEX_REST_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:

                    market: Dict[Any] = await response.json()
                    raw_trading_pairs: List[str] = list(market.keys())
                    trading_pair_list: List[str] = []
                    for raw_trading_pair in raw_trading_pairs:
                        converted_trading_pair: Optional[str] = \
                            IDEXMarket.convert_from_exchange_trading_pair(raw_trading_pair)
                        if converted_trading_pair is not None:
                            trading_pair_list.append(converted_trading_pair)
                        else:
                            self.logger().debug(f"Could not parse the trading pair {raw_trading_pair}, skipping it...")
                    return trading_pair_list

        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for idex trading pairs
            pass

        return []

    async def fetch_huobi_trading_pairs(self) -> List[str]:
        try:
            from hummingbot.market.huobi.huobi_market import HuobiMarket

            client: aiohttp.ClientSession = self.http_client()
            async with client.get(HUOBI_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    all_trading_pairs: Dict[str, any] = await response.json()
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
                    products: List[Dict[str, any]] = await response.json()
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
                    all_trading_pairs: List[Dict[str, any]] = await response.json()
                    return [item["symbol"]
                            for item in all_trading_pairs
                            if item["status"] == "ONLINE"]
        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for bittrex trading pairs
            pass

        return []

    async def fetch_dolomite_trading_pairs(self) -> List[str]:
        try:
            from hummingbot.market.dolomite.dolomite_market import DolomiteMarket

            client: aiohttp.ClientSession = TradingPairFetcher.http_client()
            async with client.get(DOLOMITE_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    all_trading_pairs: Dict[str, any] = await response.json()
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

    async def fetch_bitcoin_com_trading_pairs(self) -> List[str]:
        try:
            from hummingbot.market.bitcoin_com.bitcoin_com_market import BitcoinComMarket

            client: aiohttp.ClientSession = TradingPairFetcher.http_client()
            async with client.get(BITCOIN_COM_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    raw_trading_pairs: List[Dict[str, any]] = await response.json()
                    trading_pairs: List[str] = list([item["id"] for item in raw_trading_pairs])
                    trading_pair_list: List[str] = []
                    for raw_trading_pair in trading_pairs:
                        converted_trading_pair: Optional[str] = \
                            BitcoinComMarket.convert_from_exchange_trading_pair(raw_trading_pair)
                        if converted_trading_pair is not None:
                            trading_pair_list.append(converted_trading_pair)
                        else:
                            self.logger().debug(f"Could not parse the trading pair {raw_trading_pair}, skipping it...")
                    return trading_pair_list
        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete available
            pass

        return []

    async def fetch_all(self):
        binance_trading_pairs = await self.fetch_binance_trading_pairs()
        ddex_trading_pairs = await self.fetch_ddex_trading_pairs()
        # Radar Relay has not yet been migrated to a new version
        # Endpoint needs to be updated after migration
        # radar_relay_trading_pairs = await self.fetch_radar_relay_trading_pairs()
        bamboo_relay_trading_pairs = await self.fetch_bamboo_relay_trading_pairs()
        coinbase_pro_trading_pairs = await self.fetch_coinbase_pro_trading_pairs()
        dolomite_trading_pairs = await self.fetch_dolomite_trading_pairs()
        huobi_trading_pairs = await self.fetch_huobi_trading_pairs()
        liquid_trading_pairs = await self.fetch_liquid_trading_pairs()
        idex_trading_pairs = await self.fetch_idex_trading_pairs()
        bittrex_trading_pairs = await self.fetch_bittrex_trading_pairs()
        bitcoin_com_trading_pairs = await self.fetch_bitcoin_com_trading_pairs()
        self.trading_pairs = {
            "binance": binance_trading_pairs,
            "dolomite": dolomite_trading_pairs,
            "idex": idex_trading_pairs,
            "ddex": ddex_trading_pairs,
            # "radar_relay": radar_relay_trading_pairs,
            "bamboo_relay": bamboo_relay_trading_pairs,
            "coinbase_pro": coinbase_pro_trading_pairs,
            "huobi": huobi_trading_pairs,
            "liquid": liquid_trading_pairs,
            "bittrex": bittrex_trading_pairs,
            "bitcoin_com": bitcoin_com_trading_pairs
        }
        self.ready = True
