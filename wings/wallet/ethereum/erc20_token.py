#!/usr/bin/env python

import asyncio
import os
import json
import logging
from typing import (
    List,
    Union,
    Optional
)
from web3 import Web3
from web3.contract import (
    Contract,
)

import wings
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
    _e2t_logger: Optional[logging.Logger] = None

    @classmethod
    def logger(cls) -> logging.Logger:
        if cls._e2t_logger is None:
            cls._e2t_logger = logging.getLogger(__name__)
        return cls._e2t_logger

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

        self._contract: Contract = self._w3.eth.contract(address=self._address, abi=self._abi)
        self._name: Optional[str] = None
        self._symbol: Optional[str] = None
        self._decimals: Optional[int] = None

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

    async def _get_contract_info(self):
        if self._name is not None and self._symbol is not None and self._decimals is not None:
            return

        ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        tasks: List[asyncio.Task] = [
            ev_loop.run_in_executor(wings.get_executor(), func, *args)
            for func, args in [
                (self.get_name_from_contract, [self._contract]),
                (self.get_symbol_from_contract, [self._contract]),
                (self._contract.functions.decimals().call, [])
            ]
        ]

        try:
            name, symbol, decimals = await asyncio.gather(*tasks)
            self._name = name
            self._symbol = symbol
            self._decimals = decimals
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(f"Could not fetch token info for {self._contract.address}.", exc_info=True)

    async def get_name(self) -> str:
        if self._name is None:
            await self._get_contract_info()
        return self._name

    async def get_symbol(self) -> str:
        if self._symbol is None:
            await self._get_contract_info()
        return self._symbol

    async def get_decimals(self) -> int:
        if self._decimals is None:
            await self._get_contract_info()
        return self._decimals

    @property
    def abi(self) -> json:
        return self._abi

    @property
    def contract(self) -> Contract:
        return self._contract
