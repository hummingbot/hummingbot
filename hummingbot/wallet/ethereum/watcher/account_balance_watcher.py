#!/usr/bin/env python

import asyncio
import logging
from typing import (
    List,
    Dict,
    Optional,
    Coroutine
)
from decimal import Decimal

from web3 import Web3
from web3.contract import Contract
from web3.datastructures import AttributeDict

from hummingbot.logger import HummingbotLogger
from hummingbot.wallet.ethereum.erc20_token import ERC20Token
from hummingbot.core.event.events import NewBlocksWatcherEvent
from hummingbot.core.event.event_forwarder import EventForwarder
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from .base_watcher import BaseWatcher
from .websocket_watcher import WSNewBlocksWatcher

s_decimal_0 = Decimal(0)


class AccountBalanceWatcher(BaseWatcher):
    _abw_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._abw_logger is None:
            cls._abw_logger = logging.getLogger(__name__)
        return cls._abw_logger

    def __init__(self,
                 w3: Web3,
                 blocks_watcher: WSNewBlocksWatcher,
                 account_address: str,
                 erc20_addresses: List[str],
                 erc20_abis: List[any]):
        super().__init__(w3)
        self._blocks_watcher: WSNewBlocksWatcher = blocks_watcher
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

        app_warning_msg: str = "Could not get ETH balance. Check Ethereum node connection."
        try:
            self._raw_account_balances: Dict[str, int] = {
                "ETH": await self.call_async(w3.eth.getBalance, account_address, app_warning_msg=app_warning_msg)
            }
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().network("Failed to update ETH balance.", app_warning_msg=app_warning_msg, exc_info=True)

        try:
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
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().network(
                "Failed to get initial tokens information.",
                app_warning_msg="Failed to get initial tokens information. Check Ethereum node connection.",
                exc_info=True
            )

        await self.update_balances()

    async def stop_network(self):
        self._blocks_watcher.remove_listener(NewBlocksWatcherEvent.NewBlocks, self._event_forwarder)

    @property
    def address(self) -> str:
        return self._account_address

    def get_raw_balances(self) -> Dict[str, int]:
        return self._raw_account_balances.copy()

    def get_all_balances(self) -> Dict[str, Decimal]:
        return dict((asset_name, self.get_balance(asset_name))
                    for asset_name in self._raw_account_balances.keys())

    def get_raw_balance(self, asset_name: str) -> int:
        return self._raw_account_balances.get(asset_name, 0)

    def get_balance(self, asset_name: str) -> Decimal:
        if asset_name not in self._raw_account_balances:
            return s_decimal_0
        decimals: int = self.get_decimals(asset_name)
        raw_balance: int = self._raw_account_balances[asset_name]
        raw_balance_in_decimal = Decimal(raw_balance)
        balance_in_decimal = raw_balance_in_decimal * Decimal(f"1e-{decimals}")
        return balance_in_decimal

    def get_decimals(self, asset_name: str) -> int:
        if asset_name == "ETH":
            return 18
        if asset_name not in self._erc20_decimals:
            raise ValueError(f"{asset_name} is not a recognized asset in this watcher.")
        return self._erc20_decimals[asset_name]

    def did_receive_new_blocks(self, _: List[AttributeDict]):
        safe_ensure_future(self.update_balances())

    async def update_balances(self):
        asset_symbols: List[str] = []
        asset_update_tasks: List[Coroutine] = []

        for asset_name, contract in self._erc20_contracts.items():
            asset_symbols.append(asset_name)
            asset_update_tasks.append(self.call_async(contract.functions.balanceOf(self._account_address).call))

        asset_symbols.append("ETH")
        asset_update_tasks.append(self.call_async(self._w3.eth.getBalance, self._account_address))

        try:
            asset_raw_balances: List[int] = await safe_gather(*asset_update_tasks)
            for asset_name, raw_balance in zip(asset_symbols, asset_raw_balances):
                self._raw_account_balances[asset_name] = raw_balance
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().network("Error fetching account balance updates.",
                                  exc_info=True,
                                  app_warning_msg="Error account balance updates. "
                                                  "Check Ethereum node connection.")
