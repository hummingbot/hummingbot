#!/usr/bin/env python

import asyncio
import logging
import math
from typing import (
    List,
    Dict,
    Optional
)
from web3 import Web3
from web3.contract import Contract
from web3.datastructures import AttributeDict

import wings
from wings.erc20_token import ERC20Token
from wings.events import NewBlocksWatcherEvent
from wings.event_forwarder import EventForwarder
from .base_watcher import BaseWatcher
from .new_blocks_watcher import NewBlocksWatcher


class AccountBalanceWatcher(BaseWatcher):
    _abw_logger: Optional[logging.Logger] = None

    @classmethod
    def logger(cls) -> logging.Logger:
        if cls._abw_logger is None:
            cls._abw_logger = logging.getLogger(__name__)
        return cls._abw_logger

    def __init__(self,
                 w3: Web3,
                 blocks_watcher: NewBlocksWatcher,
                 account_address: str,
                 erc20_addresses: List[str],
                 erc20_abis: List[any]):
        super().__init__(w3)
        self._blocks_watcher: NewBlocksWatcher = blocks_watcher
        self._account_address: str = account_address
        self._addresses_to_contracts: Dict[str, Contract] = {
            address: w3.eth.contract(address=address, abi=abi)
            for address, abi in zip(erc20_addresses, erc20_abis)
        }

        self._erc20_contracts: Dict[str, Contract] = {}
        self._erc20_decimals: Dict[str, int] = {}
        self._event_forwarder: EventForwarder = EventForwarder(self.did_receive_new_blocks)
        self._raw_account_balances: Dict[str, int] = {}

    async def start_network(self):
        account_address: str = self._account_address
        w3: Web3 = self._w3

        self._blocks_watcher.add_listener(NewBlocksWatcherEvent.NewBlocks, self._event_forwarder)
        self._raw_account_balances: Dict[str, int] = {
            "ETH": await self.call_async(w3.eth.getBalance, account_address)
        }

        if len(self._erc20_contracts) < len(self._addresses_to_contracts):
            for address, contract in self._addresses_to_contracts.items():
                contract: Contract = contract
                asset_name: str = await self.call_async(ERC20Token.get_symbol_from_contract, contract)
                decimals: int = await self.call_async(contract.functions.decimals().call)
                self._erc20_contracts[asset_name] = contract
                self._erc20_decimals[asset_name] = decimals
                self._raw_account_balances[asset_name] = await self.call_async(
                    contract.functions.balanceOf(account_address).call
                )

        await self.update_balances()

    async def stop_network(self):
        self._blocks_watcher.remove_listener(NewBlocksWatcherEvent.NewBlocks, self._event_forwarder)

    @property
    def address(self) -> str:
        return self._account_address

    def get_raw_balances(self) -> Dict[str, int]:
        return self._raw_account_balances.copy()

    def get_all_balances(self) -> Dict[str, float]:
        return dict((asset_name, self._raw_account_balances[asset_name] * math.pow(10, -self.get_decimals(asset_name)))
                    for asset_name in self._raw_account_balances.keys())

    def get_raw_balance(self, asset_name: str) -> int:
        return self._raw_account_balances.get(asset_name, 0)

    def get_balance(self, asset_name: str) -> float:
        if asset_name not in self._raw_account_balances:
            return 0.0
        decimals: int = self.get_decimals(asset_name)
        raw_balance: int = self._raw_account_balances[asset_name]
        return raw_balance * math.pow(10, -decimals)

    def get_decimals(self, asset_name: str) -> int:
        if asset_name == "ETH":
            return 18
        if asset_name not in self._erc20_decimals:
            raise ValueError(f"{asset_name} is not a recognized asset in this watcher.")
        return self._erc20_decimals[asset_name]

    def did_receive_new_blocks(self, _: List[AttributeDict]):
        asyncio.ensure_future(self.update_balances())

    async def update_balances(self):
        asset_symbols: List[str] = []
        asset_update_tasks: List[asyncio.Task] = []

        for asset_name, contract in self._erc20_contracts.items():
            asset_symbols.append(asset_name)
            asset_update_tasks.append(
                self._ev_loop.run_in_executor(
                    wings.get_executor(),
                    contract.functions.balanceOf(self._account_address).call
                )
            )

        asset_symbols.append("ETH")
        asset_update_tasks.append(self._ev_loop.run_in_executor(
            wings.get_executor(),
            self._w3.eth.getBalance, self._account_address
        ))

        try:
            asset_raw_balances: List[int] = await asyncio.gather(*asset_update_tasks)
            for asset_name, raw_balance in zip(asset_symbols, asset_raw_balances):
                self._raw_account_balances[asset_name] = raw_balance
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected error fetching account balance updates.", exc_info=True)
