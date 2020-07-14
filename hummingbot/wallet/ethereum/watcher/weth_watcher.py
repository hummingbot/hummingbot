#!/usr/bin/env python

import asyncio
from decimal import Decimal
import logging
from typing import (
    List,
    Dict,
    Iterable,
    Set,
    Optional
)
from web3 import Web3
from web3.datastructures import AttributeDict

from hummingbot.wallet.ethereum.erc20_token import ERC20Token
from hummingbot.logger import HummingbotLogger
from hummingbot.core.event.events import (
    NewBlocksWatcherEvent,
    WalletWrappedEthEvent,
    WalletUnwrappedEthEvent,
    WalletEvent
)
from hummingbot.core.event.event_forwarder import EventForwarder
from hummingbot.core.utils.async_utils import safe_ensure_future
from .base_watcher import BaseWatcher
from .websocket_watcher import WSNewBlocksWatcher
from .contract_event_logs import ContractEventLogger

DEPOSIT_EVENT_NAME = "Deposit"
WITHDRAWAL_EVENT_NAME = "Withdrawal"


class WethWatcher(BaseWatcher):
    _w2ew_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._w2ew_logger is None:
            cls._w2ew_logger = logging.getLogger(__name__)
        return cls._w2ew_logger

    def __init__(self,
                 w3: Web3,
                 weth_token: ERC20Token,
                 blocks_watcher: WSNewBlocksWatcher,
                 watch_addresses: Iterable[str]):
        super().__init__(w3)
        self._blocks_watcher: WSNewBlocksWatcher = blocks_watcher
        self._watch_addresses: Set[str] = set(watch_addresses)
        self._asset_decimals: Dict[str, int] = {}
        self._weth_token = weth_token
        self._weth_contract = weth_token.contract
        self._contract_event_logger = ContractEventLogger(w3, weth_token.address, weth_token.abi)
        self._poll_weth_logs_task: asyncio.Task = None
        self._event_forwarder: EventForwarder = EventForwarder(self.did_receive_new_blocks)
        self._new_blocks_queue: asyncio.Queue = asyncio.Queue()

    async def start_network(self):
        if self._poll_weth_logs_task is not None:
            await self.stop_network()
        self._blocks_watcher.add_listener(NewBlocksWatcherEvent.NewBlocks, self._event_forwarder)
        self._poll_weth_logs_task = safe_ensure_future(self.poll_weth_logs_loop())

    async def stop_network(self):
        if self._poll_weth_logs_task is not None:
            self._poll_weth_logs_task.cancel()
            self._poll_weth_logs_task = None
        self._blocks_watcher.remove_listener(NewBlocksWatcherEvent.NewBlocks, self._event_forwarder)

    def did_receive_new_blocks(self, new_blocks: List[AttributeDict]):
        self._new_blocks_queue.put_nowait(new_blocks)

    async def poll_weth_logs_loop(self):
        while True:
            try:
                new_blocks: List[AttributeDict] = await self._new_blocks_queue.get()

                deposit_entries = await self._contract_event_logger.get_new_entries_from_logs(
                    DEPOSIT_EVENT_NAME,
                    new_blocks
                )

                withdrawal_entries = await self._contract_event_logger.get_new_entries_from_logs(
                    WITHDRAWAL_EVENT_NAME,
                    new_blocks
                )
                for deposit_entry in deposit_entries:
                    await self._handle_event_data(deposit_entry)
                for withdrawal_entry in withdrawal_entries:
                    await self._handle_event_data(withdrawal_entry)

            except asyncio.CancelledError:
                raise
            except asyncio.TimeoutError:
                continue
            except Exception:
                self.logger().network("Unknown error trying to fetch new events from WETH contract.", exc_info=True,
                                      app_warning_msg="Unknown error trying to fetch new events from WETH contract. "
                                                      "Check wallet network connection")

    async def _handle_event_data(self, event_data: AttributeDict):
        event_type: str = event_data["event"]
        timestamp: float = float(await self._blocks_watcher.get_timestamp_for_block(event_data["blockHash"]))
        tx_hash: str = event_data["transactionHash"].hex()
        if event_type == DEPOSIT_EVENT_NAME:
            self.handle_wrapping_eth_event(timestamp, tx_hash, event_data)
        elif event_type == WITHDRAWAL_EVENT_NAME:
            self.handle_unwrapping_eth_event(timestamp, tx_hash, event_data)
        else:
            self.logger().warning(f"Received log with unrecognized event type - '{event_type}'.")

    def handle_wrapping_eth_event(self,
                                  timestamp: float, tx_hash: str, event_data: AttributeDict):
        event_args: AttributeDict = event_data["args"]
        if event_args["dst"] not in self._watch_addresses:
            return
        raw_amount: int = event_args["wad"]
        normalized_amount: Decimal = Decimal(raw_amount) * Decimal("1e-18")
        address: str = event_args["dst"]

        self.trigger_event(WalletEvent.WrappedEth,
                           WalletWrappedEthEvent(timestamp, tx_hash, address, normalized_amount, raw_amount))

    def handle_unwrapping_eth_event(self,
                                    timestamp: float, tx_hash: str, event_data: AttributeDict):
        event_args: AttributeDict = event_data["args"]
        if event_args["src"] not in self._watch_addresses:
            return
        raw_amount: int = event_args["wad"]
        normalized_amount: Decimal = Decimal(raw_amount) * Decimal("1e-18")
        address: str = event_args["src"]

        self.trigger_event(WalletEvent.UnwrappedEth,
                           WalletUnwrappedEthEvent(timestamp, tx_hash, address, normalized_amount, raw_amount))
