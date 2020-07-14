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
