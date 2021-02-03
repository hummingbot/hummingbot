#!/usr/bin/env python

import asyncio
import os
import json
import logging
from typing import (
    Dict,
    List,
    Union,
    Optional,
    Coroutine
)
from web3 import Web3
from web3.contract import (
    Contract,
)

from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger
from hummingbot.wallet.ethereum.ethereum_chain import EthereumChain


with open(os.path.join(os.path.dirname(__file__), 'token_abi/erc20_abi.json')) as erc20_abi:
    abi: Dict[str, any] = json.load(erc20_abi)

with open(os.path.join(os.path.dirname(__file__), 'token_abi/weth_contract_abi.json')) as weth_abi:
    w_abi: Dict[str, any] = json.load(weth_abi)

with open(os.path.join(os.path.dirname(__file__), 'token_abi/dai_abi.json')) as dai_abi:
    d_abi: Dict[str, any] = json.load(dai_abi)

with open(os.path.join(os.path.dirname(__file__), 'token_abi/mkr_abi.json')) as mkr_abi:
    m_abi: Dict[str, any] = json.load(mkr_abi)

MAINNET_WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
MAINNET_SAI_ADDRESS = "0x89d24A6b4CcB1B6fAA2625fE562bDD9a23260359"
MAINNET_MKR_ADDRESS = "0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2"
ROPSTEN_WETH_ADDRESS = "0xc778417E063141139Fce010982780140Aa0cD5Ab"
RINKEBY_WETH_ADDRESS = "0xc778417E063141139Fce010982780140Aa0cD5Ab"
KOVAN_WETH_ADDRESS = "0xd0A1E359811322d97991E03f863a0C30C2cF029C"
ZEROEX_TEST_WETH_ADDRESS = "0x0B1ba0af832d7C05fD64161E0Db78E85978E8082"


class ERC20Token:
    _e2t_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
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
            elif self._address == MAINNET_SAI_ADDRESS:
                self._abi = d_abi
            elif self._address == MAINNET_MKR_ADDRESS:
                self._abi = m_abi
        elif chain is EthereumChain.ROPSTEN:
            if self._address == ROPSTEN_WETH_ADDRESS:
                self._abi = w_abi
        elif chain is EthereumChain.RINKEBY:
            if self._address == RINKEBY_WETH_ADDRESS:
                self._abi = w_abi
        elif chain is EthereumChain.KOVAN:
            if self._address == KOVAN_WETH_ADDRESS:
                self._abi = w_abi
        elif chain is EthereumChain.ZEROEX_TEST:
            if self._address == ZEROEX_TEST_WETH_ADDRESS:
                self._abi = w_abi

        # By default token_overrides will be assigned an empty dictionary
        # This helps prevent breaking of market unit tests
        token_overrides: Dict[str, str] = global_config_map["ethereum_token_overrides"].value if "ethereum_token_overrides" in global_config_map else {}
        override_addr_to_token_name: Dict[str, str] = {value: key for key, value in token_overrides.items()}
        override_token_name: Optional[str] = override_addr_to_token_name.get(address)
        if override_token_name == "WETH":
            self._abi = w_abi
        elif override_token_name == "SAI":
            self._abi = d_abi
        elif override_token_name == "MKR":
            self._abi = m_abi

        self._contract: Contract = self._w3.eth.contract(address=self._address, abi=self._abi)
        self._name: Optional[str] = None
        self._symbol: Optional[str] = None
        self._decimals: Optional[int] = None

    @classmethod
    def get_symbol_from_contract(cls, contract: Contract) -> str:
        if contract.address == MAINNET_SAI_ADDRESS:
            # Special case... due to migration to multi-collateral DAI. The old DAI is now called SAI.
            return "SAI"
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

        tasks: List[Coroutine] = [
            AsyncCallScheduler.shared_instance().call_async(func, *args)
            for func, args in [
                (self.get_name_from_contract, [self._contract]),
                (self.get_symbol_from_contract, [self._contract]),
                (self._contract.functions.decimals().call, [])
            ]
        ]

        try:
            name, symbol, decimals = await safe_gather(*tasks)
            self._name = name
            self._symbol = symbol
            self._decimals = decimals
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().network(f"Error fetching token info for {self._contract.address}.", exc_info=True,
                                  app_warning_msg=f"Error fetching token info for {self._contract.address}. "
                                                  f"Check wallet network connection")

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
