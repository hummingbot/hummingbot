import binascii
import logging
from hexbytes import HexBytes
from web3 import Web3
from web3.datastructures import AttributeDict
from typing import Dict


def check_web3(ethereum_rpc_url: str) -> bool:
    try:
        w3: Web3 = Web3(Web3.HTTPProvider(ethereum_rpc_url, request_kwargs={"timeout": 2.0}))
        ret = w3.isConnected()
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


def block_values_to_hex(block: AttributeDict) -> AttributeDict:
    formatted_block: Dict = {}
    for key in block.keys():
        value = block[key]
        try:
            formatted_block[key] = HexBytes(value)
        except binascii.Error:
            formatted_block[key] = value
    return AttributeDict(formatted_block)


def check_transaction_execptions(trade_data: dict) -> dict:

    exception_list = []

    # gas_limit = trade_data["gas_limit"]
    # gas_price = trade_data["gas_price"]
    gas_cost = trade_data["gas_cost"]
    # price = trade_data["price"]
    amount = trade_data["amount"]
    side = trade_data["side"]
    base = trade_data["base"]
    quote = trade_data["quote"]
    balances = trade_data["balances"]
    allowances = trade_data["allowances"]

    eth_balance = balances["ETH"]
    # base_balance = balances[base]
    # quote_balance = balances[quote]

    # check for sufficient gas
    if eth_balance < gas_cost:
        exception_list.append(f"Insufficient ETH balance to cover gas:"
                              f" Balance: {eth_balance}. Est. gas cost: {gas_cost}")

    trade_token = base if side == "side" else quote
    trade_balance = balances[trade_token]
    trade_allowance = allowances[trade_token]

    # check for insufficient balance
    if trade_balance < amount:
        exception_list.append(f"Insufficient ETH balance to {side}:"
                              f" Balance: {trade_balance}. Amount to trade: {amount}")

    # check for insufficient token allowance
    if allowances[trade_token] < amount:
        exception_list.append(f"Insufficient {trade_token} allowance {trade_allowance}. Amount to trade: {amount}")

    return exception_list
