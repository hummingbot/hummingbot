"""
A collection of utility functions for querying and checking Ethereum data
"""

import aiohttp
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.core.utils import async_ttl_cache
import itertools as it
import logging
from typing import List
from web3 import Web3


def is_connected_to_web3(ethereum_rpc_url: str) -> bool:
    """
    This is abstracted out of check_web3 to make mock testing easier
    """
    w3: Web3 = Web3(Web3.HTTPProvider(ethereum_rpc_url, request_kwargs={"timeout": 2.0}))
    return w3.isConnected()


def check_web3(ethereum_rpc_url: str) -> bool:
    """
    Confirm that the provided url is a valid Ethereum RPC url.
    """
    try:
        ret = is_connected_to_web3(ethereum_rpc_url)
    except Exception:
        ret = False

    if not ret:
        if ethereum_rpc_url.startswith("http://mainnet.infura.io"):
            logging.getLogger().warning("You are connecting to an Infura using an insecure network protocol "
                                        "(\"http\"), which may not be allowed by Infura. "
                                        "Try using \"https://\" instead.")
        if ethereum_rpc_url.startswith("mainnet.infura.io"):
            logging.getLogger().warning("Please add \"https://\" to your Infura node url.")
    return ret


def check_transaction_exceptions(trade_data: dict) -> list:
    """
    Check trade data for Ethereum decentralized exchanges
    """
    exception_list = []

    gas_limit = trade_data["gas_limit"]
    gas_cost = trade_data["gas_cost"]
    amount = trade_data["amount"]
    side = trade_data["side"]
    base = trade_data["base"]
    quote = trade_data["quote"]
    balances = trade_data["balances"]
    allowances = trade_data["allowances"]
    swaps_message = f"Total swaps: {trade_data['swaps']}" if "swaps" in trade_data.keys() else ''

    eth_balance = balances["ETH"]

    # check for sufficient gas
    if eth_balance < gas_cost:
        exception_list.append(f"Insufficient ETH balance to cover gas:"
                              f" Balance: {eth_balance}. Est. gas cost: {gas_cost}. {swaps_message}")

    trade_token = base if side == "side" else quote
    trade_allowance = allowances[trade_token]

    # check for gas limit set to low
    gas_limit_threshold = 21000
    if gas_limit < gas_limit_threshold:
        exception_list.append(f"Gas limit {gas_limit} below recommended {gas_limit_threshold} threshold.")

    # check for insufficient token allowance
    if allowances[trade_token] < amount:
        exception_list.append(f"Insufficient {trade_token} allowance {trade_allowance}. Amount to trade: {amount}")

    return exception_list


async def get_token_list():
    """
    This is abstracted out of fetch_trading_pairs to make mock testing easier
    """
    token_list_url = global_config_map.get("ethereum_token_list_url").value
    async with aiohttp.ClientSession() as client:
        resp = await client.get(token_list_url)
        return await resp.json()


@async_ttl_cache(ttl=30)
async def fetch_trading_pairs() -> List[str]:
    """
    List of all trading pairs in all permutations, for example:
    ETH-BTC, BTC-ETH, BNB-ETH, ETH-BNB
    """
    tokens = set()
    resp_json = await get_token_list()
    for token in resp_json["tokens"]:
        tokens.add(token["symbol"])
    trading_pairs = []
    for base, quote in it.permutations(tokens, 2):
        trading_pairs.append(f"{base}-{quote}")
    return trading_pairs
