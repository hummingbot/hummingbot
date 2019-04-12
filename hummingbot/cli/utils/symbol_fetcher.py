import aiohttp
import asyncio
from typing import (
    List,
    Dict,
)


BINANCE_ENDPOINT = "https://api.binance.com/api/v1/exchangeInfo"
DDEX_ENDPOINT = "https://api.ddex.io/v3/markets"
RADAR_RELAY_ENDPOINT = "https://api.radarrelay.com/v2/markets/"
COINBASE_PRO_ENDPOINT = "https://api.pro.coinbase.com/products/"
API_CALL_TIMEOUT = 5


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
                    # Do nothing if the request fails -- there will be no autocomplete for binance symbols
                    return []


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
                    # Do nothing if the request fails -- there will be no autocomplete for ddex symbols
                    return []


async def fetch_radar_relay_symbols() -> List[str]:
    async with aiohttp.ClientSession() as client:
        async with client.get(RADAR_RELAY_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
            if response.status == 200:
                try:
                    markets = await response.json()
                    symbols = list(map(lambda symbol_details: symbol_details.get('id'), markets))
                    return symbols
                except Exception:
                    # Do nothing if the request fails -- there will be no autocomplete for ddex symbols
                    return []


async def fetch_coinbase_pro_symbols() -> List[str]:
    async with aiohttp.ClientSession() as client:
        async with client.get(COINBASE_PRO_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
            if response.status == 200:
                try:
                    markets = await response.json()
                    symbols = list(map(lambda symbol_details: symbol_details.get('id'), markets))
                    return symbols
                except Exception:
                    # Do nothing if the request fails -- there will be no autocomplete for ddex symbols
                    return []


async def fetch_all() -> Dict[str, List[str]]:
    binance_symbols = await fetch_binance_symbols()
    ddex_symbols = await fetch_ddex_symbols()
    radar_relay_symbols = await fetch_radar_relay_symbols()
    coinbase_pro_symbols = await fetch_coinbase_pro_symbols()
    return {
        "binance": binance_symbols,
        "ddex": ddex_symbols,
        "radar_relay": radar_relay_symbols,
        "coinbase_pro": coinbase_pro_symbols,
    }
