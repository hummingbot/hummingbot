import aiohttp
import asyncio
from typing import (
    List,
    Dict,
    Any,
)


BINANCE_ENDPOINT = "https://api.binance.com/api/v1/exchangeInfo"
DDEX_ENDPOINT = "https://api.ddex.io/v3/markets"
DOLOMITE_ENDPOINT = "https://exchange-api.dolomite.io/v1/markets"
RADAR_RELAY_ENDPOINT = "https://api.radarrelay.com/v2/markets"
BAMBOO_RELAY_ENDPOINT = "https://rest.bamboorelay.com/main/0x/markets"
COINBASE_PRO_ENDPOINT = "https://api.pro.coinbase.com/products/"
IDEX_REST_ENDPOINT = "https://api.idex.market/returnTicker"
API_CALL_TIMEOUT = 5


class SymbolFetcher:
    _sf_shared_instance: "SymbolFetcher" = None

    @classmethod
    def get_instance(cls) -> "SymbolFetcher":
        if cls._sf_shared_instance is None:
            cls._sf_shared_instance = SymbolFetcher()
        return cls._sf_shared_instance

    def __init__(self):
        self.ready = False
        self.symbols: Dict[str, Any] = {}
        asyncio.ensure_future(self.fetch_all())

    @staticmethod
    async def fetch_binance_symbols() -> List[str]:
        async with aiohttp.ClientSession() as client:
            async with client.get(BINANCE_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    try:
                        data = await response.json()
                        symbol_structs = data.get("symbols")
                        symbols = list(map(lambda symbol_details: symbol_details.get('symbol'), symbol_structs))
                        return symbols
                    except Exception:
                        pass
                        # Do nothing if the request fails -- there will be no autocomplete for binance symbols
                return []

    @staticmethod
    async def fetch_ddex_symbols() -> List[str]:
        async with aiohttp.ClientSession() as client:
            async with client.get(DDEX_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    try:
                        response = await response.json()
                        markets = response.get("data").get("markets")
                        symbols = list(map(lambda symbol_details: symbol_details.get('id'), markets))
                        return symbols
                    except Exception:
                        pass
                        # Do nothing if the request fails -- there will be no autocomplete for binance symbols
                return []

    @staticmethod
    async def fetch_dolomite_symbols() -> List[str]:
        async with aiohttp.ClientSession() as client:
            async with client.get(DOLOMITE_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    try:
                        response = await response.json()
                        markets = response.get("data")
                        symbols = list(map(lambda symbol_details: symbol_details.get('market'), markets))
                        return symbols
                    except Exception:
                        pass
                        # Do nothing if the request fails -- there will be no autocomplete for dolomite symbols
                return []

    @staticmethod
    async def fetch_radar_relay_symbols() -> List[str]:
        symbols = set()
        page_count = 1
        while True:
            async with aiohttp.ClientSession() as client:
                async with client.get(f"{RADAR_RELAY_ENDPOINT}?perPage=100&page={page_count}", timeout=API_CALL_TIMEOUT) \
                        as response:
                    if response.status == 200:
                        try:
                            markets = await response.json()
                            new_symbols = set(map(lambda symbol_details: symbol_details.get('id'), markets))
                            if len(new_symbols) == 0:
                                break
                            else:
                                symbols = symbols.union(new_symbols)
                            page_count += 1
                        except Exception:
                            # Do nothing if the request fails -- there will be no autocomplete for radar symbols
                            break
        return list(symbols)

    @staticmethod
    async def fetch_bamboo_relay_symbols() -> List[str]:
        symbols = set()
        page_count = 1
        while True:
            async with aiohttp.ClientSession() as client:
                async with client.get(f"{BAMBOO_RELAY_ENDPOINT}?perPage=1000&page={page_count}", timeout=API_CALL_TIMEOUT) \
                        as response:
                    if response.status == 200:
                        try:
                            markets = await response.json()
                            new_symbols = set(map(lambda symbol_details: symbol_details.get('id'), markets))
                            if len(new_symbols) == 0:
                                break
                            else:
                                symbols = symbols.union(new_symbols)
                            page_count += 1
                        except Exception:
                            # Do nothing if the request fails -- there will be no autocomplete for bamboo symbols
                            break
        return list(symbols)

    @staticmethod
    async def fetch_coinbase_pro_symbols() -> List[str]:
        async with aiohttp.ClientSession() as client:
            async with client.get(COINBASE_PRO_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    try:
                        markets = await response.json()
                        symbols = list(map(lambda symbol_details: symbol_details.get('id'), markets))
                        return symbols
                    except Exception:
                        pass
                        # Do nothing if the request fails -- there will be no autocomplete for binance symbols
                return []

    @staticmethod
    async def fetch_idex_symbols() -> List[str]:
        async with aiohttp.ClientSession() as client:
            async with client.get(IDEX_REST_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    try:
                        market: Dict[Any] = await response.json()
                        symbols = list(market.keys())
                        return symbols
                    except Exception:
                        pass
                        # Do nothing if the request fails -- there will be no autocomplete for binance symbols
                return []

    async def fetch_all(self):
        binance_symbols = await self.fetch_binance_symbols()
        ddex_symbols = await self.fetch_ddex_symbols()
        dolomite_symbols = await self.fetch_dolomite_symbols()
        radar_relay_symbols = await self.fetch_radar_relay_symbols()
        bamboo_relay_symbols = await self.fetch_bamboo_relay_symbols()
        coinbase_pro_symbols = await self.fetch_coinbase_pro_symbols()
        idex_symbols = await self.fetch_idex_symbols()
        self.symbols = {
            "binance": binance_symbols,
            "idex": idex_symbols,
            "ddex": ddex_symbols,
            "dolomite": dolomite_symbols,
            "radar_relay": radar_relay_symbols,
            "bamboo_relay": bamboo_relay_symbols,
            "coinbase_pro": coinbase_pro_symbols,
        }
        self.ready = True

