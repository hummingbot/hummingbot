#!/usr/bin/env python

import asyncio
from async_timeout import timeout
from collections import OrderedDict
import functools
from hexbytes import HexBytes
import logging
import time
from typing import (
    Dict,
    List,
    Optional
)
from web3 import Web3
from web3.datastructures import AttributeDict
from web3.exceptions import BlockNotFound

from hummingbot.logger import HummingbotLogger
from hummingbot.core.event.events import NewBlocksWatcherEvent
from hummingbot.core.utils.async_utils import safe_ensure_future
from .base_watcher import BaseWatcher

DEFAULT_BLOCK_WINDOW_SIZE = 30


class NewBlocksWatcher(BaseWatcher):
    _nbw_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._nbw_logger is None:
            cls._nbw_logger = logging.getLogger(__name__)
        return cls._nbw_logger

    def __init__(self, w3: Web3, block_window_size: Optional[int] = DEFAULT_BLOCK_WINDOW_SIZE):
        super().__init__(w3)
        self._block_window_size = block_window_size
        self._current_block_number: int = -1
        self._block_number_to_fetch: int = -1
        self._blocks_window: Dict = {}
        self._block_number_to_hash_map: OrderedDict = OrderedDict()
        self._fetch_new_blocks_task: Optional[asyncio.Task] = None

    @property
    def web3(self) -> Web3:
        return self._w3

    @property
    def block_number(self) -> int:
        return self._current_block_number

    async def start_network(self):
        if self._fetch_new_blocks_task is not None:
            await self.stop_network()

        try:
            self._current_block_number = await self.call_async(getattr, self._w3.eth, "blockNumber")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().network("Error fetching newest Ethereum block number.",
                                  app_warning_msg="Error fetching newest Ethereum block number. "
                                                  "Check Ethereum node connection",
                                  exc_info=True)
        self._block_number_to_fetch = self._current_block_number
        self._fetch_new_blocks_task: asyncio.Task = safe_ensure_future(self.fetch_new_blocks_loop())

    async def stop_network(self):
        if self._fetch_new_blocks_task is not None:
            self._fetch_new_blocks_task.cancel()
            self._fetch_new_blocks_task = None

    async def get_timestamp_for_block(self, block_hash: HexBytes, max_tries: Optional[int] = 10) -> int:
        counter = 0
        block: AttributeDict = None
        if block_hash in self._blocks_window:
            block = self._blocks_window[block_hash]
            return block.timestamp
        else:
            while block is None:
                try:
                    if counter == max_tries:
                        raise ValueError(f"Block hash {block_hash.hex()} does not exist.")
                    counter += 1
                    async with timeout(10.0):
                        block = await self.call_async(
                            functools.partial(
                                self._w3.eth.getBlock,
                                block_hash,
                                full_transactions=False)
                        )
                except TimeoutError:
                    self.logger().network(f"Timed out fetching new block - '{block_hash}'.", exc_info=True,
                                          app_warning_msg=f"Timed out fetching new block - '{block_hash}'. "
                                                          f"Check wallet network connection")
                except BlockNotFound:
                    pass
                finally:
                    await asyncio.sleep(0.5)
            return block.timestamp

    async def fetch_new_blocks_loop(self):
        last_timestamp_received_blocks: float = 0.0
        block_hash = ""
        try:
            while True:
                try:
                    async with timeout(30.0):
                        incoming_block: AttributeDict = await self.call_async(
                            functools.partial(
                                self._w3.eth.getBlock,
                                self._block_number_to_fetch,
                                full_transactions=True)
                        )
                        if incoming_block is not None:
                            current_block_hash: HexBytes = self._block_number_to_hash_map.get(
                                self._current_block_number,
                                None)
                            incoming_block_hash: HexBytes = incoming_block.hash
                            incoming_block_parent_hash: HexBytes = incoming_block.parentHash
                            new_blocks: List[AttributeDict] = []
                            if current_block_hash is not None and current_block_hash != incoming_block_parent_hash:
                                block_reorganization: List[AttributeDict] = await self.get_block_reorganization(incoming_block)
                                new_blocks += block_reorganization

                            self._block_number_to_hash_map[self._block_number_to_fetch] = incoming_block_hash
                            self._blocks_window[incoming_block_hash] = incoming_block
                            new_blocks.append(incoming_block)
                            self._current_block_number = self._block_number_to_fetch
                            self._block_number_to_fetch += 1
                            self.trigger_event(NewBlocksWatcherEvent.NewBlocks, new_blocks)
                            last_timestamp_received_blocks = time.time()

                            while len(self._blocks_window) > self._block_window_size:
                                block_hash = self._block_number_to_hash_map.popitem(last=False)[1]
                                del self._blocks_window[block_hash]

                except asyncio.CancelledError:
                    raise
                except asyncio.TimeoutError:
                    self.logger().network("Timed out fetching new block.", exc_info=True,
                                          app_warning_msg="Timed out fetching new block. "
                                                          "Check wallet network connection")
                except BlockNotFound:
                    pass
                except Exception:
                    self.logger().network("Error fetching new block.", exc_info=True,
                                          app_warning_msg="Error fetching new block. "
                                                          "Check wallet network connection")
                sleep_time: int = 1
                seconds_since_last_received_blocks: float = time.time() - last_timestamp_received_blocks
                if seconds_since_last_received_blocks < 5:
                    sleep_time = 5
                elif seconds_since_last_received_blocks < 15:
                    sleep_time = 4
                elif seconds_since_last_received_blocks < 30:
                    sleep_time = 3
                elif seconds_since_last_received_blocks < 45:
                    sleep_time = 2
                await asyncio.sleep(sleep_time)
        except asyncio.CancelledError:
            raise

    async def get_block_reorganization(self, incoming_block: AttributeDict) -> List[AttributeDict]:
        block_reorganization: List[AttributeDict] = []
        expected_parent_hash: HexBytes = incoming_block.parentHash
        try:
            while expected_parent_hash not in self._blocks_window and len(block_reorganization) < len(self._blocks_window):
                replacement_block = None
                while replacement_block is None:
                    try:
                        block = await self.call_async(
                            functools.partial(
                                self._w3.eth.getBlock,
                                expected_parent_hash,
                                full_transactions=True)
                        )
                        replacement_block = block
                    except BlockNotFound:
                        pass
                    if replacement_block is None:
                        await asyncio.sleep(0.5)

                replacement_block_number: int = replacement_block.number
                replacement_block_hash: HexBytes = replacement_block.hash
                replacement_block_parent_hash: HexBytes = replacement_block.parentHash
                self._block_number_to_hash_map[replacement_block_number] = replacement_block_hash
                self._blocks_window[replacement_block_hash] = replacement_block
                block_reorganization.append(replacement_block)
                expected_parent_hash = replacement_block_parent_hash

            block_reorganization.reverse()
            return block_reorganization
        except asyncio.CancelledError:
            raise
