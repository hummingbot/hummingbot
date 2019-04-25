#!/usr/bin/env python

import asyncio
from async_timeout import timeout
from collections import OrderedDict
import cytoolz
import functools
from hexbytes import HexBytes
import logging
import math
from typing import (
    List,
    Dict,
    Iterable,
    Set,
    Optional
)
from web3 import Web3
from web3.contract import Contract
from web3.datastructures import AttributeDict

import wings
from wings.events import (
    NewBlocksWatcherEvent,
    WalletReceivedAssetEvent,
    TokenApprovedEvent,
    ERC20WatcherEvent
)
from wings.erc20_token import ERC20Token
from wings.event_forwarder import EventForwarder
from .base_watcher import BaseWatcher
from .new_blocks_watcher import NewBlocksWatcher
from .contract_event_logs import ContractEventLogger

weth_dai_symbols: Set[str] = {"WETH", "DAI"}
TRANSFER_EVENT_NAME = "Transfer"
APPROVAL_EVENT_NAME = "Approval"


class ERC20EventsWatcher(BaseWatcher):
    _w2ew_logger: Optional[logging.Logger] = None

    @classmethod
    def logger(cls) -> logging.Logger:
        if cls._w2ew_logger is None:
            cls._w2ew_logger = logging.getLogger(__name__)
        return cls._w2ew_logger

    @staticmethod
    def is_weth_dai(symbol: str) -> bool:
        global weth_dai_symbols
        return symbol in weth_dai_symbols

    def __init__(self,
                 w3: Web3,
                 blocks_watcher: NewBlocksWatcher,
                 contract_addresses: List[str],
                 contract_abi: List[any],
                 watch_addresses: Iterable[str]):
        if len(contract_addresses) != len(contract_abi):
            raise ValueError("Each entry in contract_addresses must have a corresponding entry in contract_abi.")

        super().__init__(w3)
        self._blocks_watcher: NewBlocksWatcher = blocks_watcher
        self._addresses_to_contracts: Dict[str, Contract] = {
            address: w3.eth.contract(address=address, abi=abi)
            for address, abi in zip(contract_addresses, contract_abi)
        }
        self._watch_addresses: Set[str] = set(watch_addresses)
        self._address_to_asset_name_map: Dict[str, str] = {}
        self._asset_decimals: Dict[str, int] = {}
        self._contract_event_loggers: Dict[str, ContractEventLogger] = {}
        self._new_blocks_queue: asyncio.Queue = asyncio.Queue()
        self._event_forwarder: EventForwarder = EventForwarder(self.did_receive_new_blocks)
        self._poll_erc20_logs_task: Optional[asyncio.Task] = None

    async def start_network(self):
        if len(self._address_to_asset_name_map) < len(self._addresses_to_contracts):
            for address, contract in self._addresses_to_contracts.items():
                contract: Contract = contract
                asset_name: str = await self.async_call(ERC20Token.get_symbol_from_contract, contract)
                decimals: int = await self.async_call(contract.functions.decimals().call)
                self._address_to_asset_name_map[address] = asset_name
                self._asset_decimals[asset_name] = decimals
                self._contract_event_loggers[address] = ContractEventLogger(self._w3, address, contract.abi)

        if self._poll_erc20_logs_task is not None:
            await self.stop_network()

        self._blocks_watcher.add_listener(NewBlocksWatcherEvent.NewBlocks, self._event_forwarder)
        self._poll_erc20_logs_task = asyncio.ensure_future(self.poll_erc20_logs_loop())

    async def stop_network(self):

        if self._poll_erc20_logs_task is not None:
            self._poll_erc20_logs_task.cancel()
            self._poll_erc20_logs_task = None
        self._blocks_watcher.remove_listener(NewBlocksWatcherEvent.NewBlocks, self._event_forwarder)

    def did_receive_new_blocks(self, new_blocks: List[AttributeDict]):
        self._new_blocks_queue.put_nowait(new_blocks)

    async def poll_erc20_logs_loop(self):
        while True:
            try:
                new_blocks: List[AttributeDict] = await self._new_blocks_queue.get()
                block_hashes: List[HexBytes] = [block["hash"] for block in new_blocks]

                transfer_tasks = []
                approval_tasks = []
                for address in self._contract_addresses:
                    contract_event_logger: ContractEventLogger = self._contract_event_loggers[address]
                    transfer_tasks.append(
                        contract_event_logger.get_new_entries_from_logs(TRANSFER_EVENT_NAME,
                                                                        block_hashes)
                    )
                    approval_tasks.append(
                        contract_event_logger.get_new_entries_from_logs(APPROVAL_EVENT_NAME,
                                                                        block_hashes)
                    )

                raw_transfer_entries = await asyncio.gather(*transfer_tasks)
                raw_approval_entries = await asyncio.gather(*approval_tasks)
                transfer_entries = list(cytoolz.concat(raw_transfer_entries))
                approval_entries = list(cytoolz.concat(raw_approval_entries))
                for transfer_entry in transfer_entries:
                    await self._handle_event_data(transfer_entry)
                for approval_entry in approval_entries:
                    await self._handle_event_data(approval_entry)

            except asyncio.CancelledError:
                raise
            except asyncio.TimeoutError:
                continue
            except Exception:
                self.logger().error("Unknown error trying to fetch new events from ERC20 contracts.", exc_info=True)

    async def _handle_event_data(self, event_data: AttributeDict):
        event_type: str = event_data["event"]
        timestamp: float = float(await self._blocks_watcher.get_timestamp_for_block(event_data["blockHash"]))
        tx_hash: str = event_data["transactionHash"].hex()
        contract_address: str = event_data["address"]
        token_asset_name: str = self._address_to_asset_name_map.get(contract_address)
        if event_type == TRANSFER_EVENT_NAME:
            self.handle_incoming_tokens_event(timestamp, tx_hash, token_asset_name, event_data)
        elif event_type == APPROVAL_EVENT_NAME:
            self.handle_approve_tokens_event(timestamp, tx_hash, token_asset_name, event_data)
        else:
            self.logger().error(f"Received log with unrecognized event type - '{event_type}'.")

    def handle_incoming_tokens_event(self,
                                     timestamp: float, tx_hash: str, asset_name: str, event_data: AttributeDict):
        event_args: AttributeDict = event_data["args"]
        is_weth_dai: bool = self.is_weth_dai(asset_name)
        raw_amount: int = event_args["value"] if not is_weth_dai else event_args.wad
        decimals: int = self._asset_decimals[asset_name]
        normalized_amount: float = raw_amount * math.pow(10, -decimals)
        from_address: str = event_args["from"] if not is_weth_dai else event_args.src
        to_address: str = event_args["to"] if not is_weth_dai else event_args.dst

        if to_address not in self._watch_addresses:
            return

        self.trigger_event(ERC20WatcherEvent.ReceivedToken,
                           WalletReceivedAssetEvent(timestamp, tx_hash,
                                                    from_address, to_address,
                                                    asset_name, normalized_amount, raw_amount))

    def handle_approve_tokens_event(self, timestamp: float, tx_hash: str, asset_name: str, event_data: AttributeDict):
        event_args: AttributeDict = event_data["args"]
        is_weth_dai: bool = self.is_weth_dai(asset_name)
        raw_amount: int = event_args.value if not is_weth_dai else event_args.wad
        decimals: int = self._asset_decimals[asset_name]
        normalized_amount: float = raw_amount * math.pow(10, -decimals)
        owner_address: str = event_args["owner"] if not is_weth_dai else event_args.src
        spender_address: str = event_args["spender"] if not is_weth_dai else event_args.guy

        if owner_address not in self._watch_addresses:
            return

        self.trigger_event(ERC20WatcherEvent.ApprovedToken,
                           TokenApprovedEvent(timestamp, tx_hash,
                                              owner_address, spender_address,
                                              asset_name, normalized_amount, raw_amount))
