#!/usr/bin/env python

import os
import json
from typing import (
    List,
    Union
)
from web3 import Web3
from web3.contract import (
    Contract,
)
from wings.ethereum_chain import EthereumChain


with open(os.path.join(os.path.dirname(__file__), 'abi/erc20_abi.json')) as erc20_abi:
    abi: json = json.load(erc20_abi)

with open(os.path.join(os.path.dirname(__file__), 'abi/weth_contract_abi.json')) as weth_abi:
    w_abi: json = json.load(weth_abi)

with open(os.path.join(os.path.dirname(__file__), 'abi/dai_abi.json')) as dai_abi:
    d_abi: json = json.load(dai_abi)


MAINNET_WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
MAINNET_DAI_ADDRESS = "0x89d24A6b4CcB1B6fAA2625fE562bDD9a23260359"


class ERC20Token:

    def __init__(self,
                 w3: Web3,
                 address: str,
                 chain: EthereumChain = EthereumChain.ROPSTEN):
        self._address = address
        self._w3: Web3 = w3
        self._chain = chain
        self._abi: List[any] = abi
        if chain is EthereumChain.MAIN_NET:
            if self._address == MAINNET_WETH_ADDRESS:
                self._abi = w_abi
            if self._address == MAINNET_DAI_ADDRESS:
                self._abi = d_abi

        self._contract = self._w3.eth.contract(address=self._address, abi=self._abi)
        self._name = self.get_name_from_contract(self._contract)
        self._symbol = self.get_symbol_from_contract(self._contract)
        self._decimals = self._contract.functions.decimals().call()

    @classmethod
    def get_symbol_from_contract(cls, contract: Contract) -> str:
        raw_symbol: Union[str, bytes] = contract.functions.symbol().call()
        if isinstance(raw_symbol, bytes):
            retval: str = raw_symbol.split(b"\x00")[0].decode("utf8")
        else:
            retval: str = raw_symbol
        return retval

    @classmethod
    def get_name_from_contract(cls, contract: Contract) -> str:
        raw_name: Union[str, bytes] = contract.functions.name().call()
        if isinstance(raw_name, bytes):
            retval: str = raw_name.split(b"\x00")[0].decode("utf8")
        else:
            retval: str = raw_name
        return retval

    @property
    def address(self) -> str:
        return self._address

    @property
    def chain(self) -> EthereumChain:
        return self._chain

    @property
    def is_weth(self) -> bool:
        return self._address == MAINNET_WETH_ADDRESS

    @property
    def name(self) -> str:
        return self._name

    @property
    def symbol(self) -> str:
        return self._symbol

    @property
    def decimals(self) -> str:
        return self._decimals

    @property
    def abi(self) -> json:
        return self._abi

    @property
    def contract(self) -> Contract:
        return self._contract
