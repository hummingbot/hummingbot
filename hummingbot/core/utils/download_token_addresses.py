#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../")))

import os
import json
import aiohttp
import asyncio
import logging
from typing import (
    Dict,
)
from web3 import Web3
from hummingbot.core.utils.async_utils import safe_gather

RADAR_RELAY_ENDPOINT = "https://api.radarrelay.com/v2/markets"
BAMBOO_RELAY_ENDPOINT = "https://rest.bamboorelay.com/main/0x/markets"
DOLOMITE_ENDPOINT = "https://exchange-api.dolomite.io/v1/tokens"
API_CALL_TIMEOUT = 5


async def download_dolomite_token_addresses(token_dict: Dict[str, str]):
    async with aiohttp.ClientSession() as client:
        async with client.get(DOLOMITE_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
            if response.status == 200:
                try:
                    response = await response.json()
                    tokens = response.get("data")
                    for token in tokens:
                        asset = token["ticker"]
                        if asset not in token_dict:
                            token_dict[asset] = Web3.toChecksumAddress(token["identifier"])
                        elif asset == "LRC":
                            # Other integrations use the wrong address for LRC
                            token_dict[asset] = Web3.toChecksumAddress(token["identifier"])
                except Exception as err:
                    logging.getLogger().error(err)


async def download_radar_relay_token_addresses(token_dict: Dict[str, str]):
    page_count = 1
    while True:
        url = f"{RADAR_RELAY_ENDPOINT}?perPage=100&page={page_count}"
        async with aiohttp.ClientSession() as client:
            async with client.get(url, timeout=API_CALL_TIMEOUT) as response:
                page_count += 1
                try:
                    if response.status == 200:
                        markets = await response.json()
                        if len(markets) == 0:
                            break
                        for market in markets:
                            market_id = market.get("id")
                            base, quote = market_id.split("-")
                            if base not in token_dict:
                                token_dict[base] = Web3.toChecksumAddress(market.get("baseTokenAddress"))
                            if quote not in token_dict:
                                token_dict[quote] = Web3.toChecksumAddress(market.get("quoteTokenAddress"))
                    else:
                        raise Exception(f"Call to {url} failed with status {response.status}")
                except Exception as err:
                    logging.getLogger().error(err)
                    break


async def download_bamboo_relay_token_addresses(token_dict: Dict[str, str]):
    page_count = 1
    while True:
        url = f"{BAMBOO_RELAY_ENDPOINT}?perPage=1000&page={page_count}"
        async with aiohttp.ClientSession() as client:
            async with client.get(url, timeout=API_CALL_TIMEOUT) as response:
                page_count += 1
                try:
                    if response.status == 200:
                        markets = await response.json()
                        if len(markets) == 0:
                            break
                        for market in markets:
                            market_id = market.get("id")
                            base, quote = market_id.split("-")
                            if base not in token_dict:
                                token_dict[base] = Web3.toChecksumAddress(market.get("baseTokenAddress"))
                            if quote not in token_dict:
                                token_dict[quote] = Web3.toChecksumAddress(market.get("quoteTokenAddress"))
                    else:
                        raise Exception(f"Call to {url} failed with status {response.status}")
                except Exception as err:
                    logging.getLogger().error(err)
                    break


def download_erc20_token_addresses():
    try:
        TOKEN_ADDRESS_PATH = "../../wallet/ethereum/erc20_tokens.json"
        logging.getLogger().info("Downloading ERC20 token addresses...")

        with open(os.path.join(os.path.dirname(__file__), TOKEN_ADDRESS_PATH)) as old_erc20:
            td = json.load(old_erc20)
            old_len = len(td.keys())
            asyncio.get_event_loop().run_until_complete(safe_gather(
                download_radar_relay_token_addresses(td),
                download_bamboo_relay_token_addresses(td),
                download_dolomite_token_addresses(td),
            ))
            new_len = len(td.keys())
            with open(os.path.join(os.path.dirname(__file__), TOKEN_ADDRESS_PATH), "w+") as new_erc20:
                new_erc20.write(json.dumps(td))
                logging.getLogger().info(f"Download Complete: {old_len} - {new_len}")

    except Exception as e:
        logging.getLogger().error(e)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    download_erc20_token_addresses()
