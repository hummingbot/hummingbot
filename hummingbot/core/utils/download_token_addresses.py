import os
import json
import aiohttp
import asyncio
import logging
from typing import (
    Dict,
)
from web3 import Web3


DDEX_ENDPOINT = "https://api.ddex.io/v3/markets"
RADAR_RELAY_ENDPOINT = "https://api.radarrelay.com/v2/markets?perPage=100&page=1"
BAMBOO_RELAY_ENDPOINT = "https://api.radarrelay.com/v2/markets?perPage=1000&page=1"
API_CALL_TIMEOUT = 5


async def download_ddex_token_addresses(token_dict: Dict[str, str]):
    async with aiohttp.ClientSession() as client:
        async with client.get(DDEX_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
            if response.status == 200:
                try:
                    response = await response.json()
                    markets = response.get("data").get("markets")
                    for market in markets:
                        base = market.get("baseToken")
                        quote = market.get("quoteToken")
                        if base not in token_dict:
                            token_dict[base] = Web3.toChecksumAddress(market.get("baseTokenAddress"))
                        if quote not in token_dict:
                            token_dict[quote] = Web3.toChecksumAddress(market.get("quoteTokenAddress"))
                except Exception as err:
                    logging.getLogger().error(err)


async def download_radar_relay_token_addresses(token_dict: Dict[str, str]):
    async with aiohttp.ClientSession() as client:
        async with client.get(RADAR_RELAY_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
            if response.status == 200:
                try:
                    markets = await response.json()
                    for market in markets:
                        market_id = market.get("id")
                        base, quote = market_id.split("-")
                        if base not in token_dict:
                            token_dict[base] = Web3.toChecksumAddress(market.get("baseTokenAddress"))
                        if quote not in token_dict:
                            token_dict[quote] = Web3.toChecksumAddress(market.get("quoteTokenAddress"))
                except Exception as err:
                    logging.getLogger().error(err)


async def download_bamboo_relay_token_addresses(token_dict: Dict[str, str]):
    async with aiohttp.ClientSession() as client:
        async with client.get(BAMBOO_RELAY_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
            if response.status == 200:
                try:
                    markets = await response.json()
                    for market in markets:
                        market_id = market.get("id")
                        base, quote = market_id.split("-")
                        if base not in token_dict:
                            token_dict[base] = Web3.toChecksumAddress(market.get("baseTokenAddress"))
                        if quote not in token_dict:
                            token_dict[quote] = Web3.toChecksumAddress(market.get("quoteTokenAddress"))
                except Exception as err:
                    logging.getLogger().error(err)


async def download_erc20_token_addresses(token_dict: Dict[str, str] = {}):
    await download_radar_relay_token_addresses(token_dict)
    await download_ddex_token_addresses(token_dict)
    await download_bamboo_relay_token_addresses(token_dict)


if __name__ == "__main__":
    try:
        TOKEN_ADDRESS_PATH = "../../wallet/ethereum/erc20_tokens.json"
        with open(os.path.join(os.path.dirname(__file__), TOKEN_ADDRESS_PATH)) as old_erc20:
            td = json.load(old_erc20)
            old_len = len(td.keys())
            asyncio.get_event_loop().run_until_complete(download_erc20_token_addresses(td))
            new_len = len(td.keys())
            with open(os.path.join(os.path.dirname(__file__), TOKEN_ADDRESS_PATH), "w+") as new_erc20:
                new_erc20.write(json.dumps(td))
                print(f"Download Complete: {old_len} - {new_len}")

    except Exception as e:
        logging.getLogger().error(e)
