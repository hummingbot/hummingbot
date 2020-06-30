import websockets
from websockets.exceptions import ConnectionClosedOK
import logging
import ujson
import asyncio

from async_timeout import timeout
from hexbytes import HexBytes
from web3.datastructures import AttributeDict
from cachetools import TTLCache

from typing import Optional

from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.wallet.ethereum.watcher.base_watcher import BaseWatcher
from hummingbot.logger import HummingbotLogger
from hummingbot.core.utils.ethereum import block_values_to_hex
from hummingbot.core.event.events import NewBlocksWatcherEvent


class EthWebSocket(BaseWatcher):
    def __init__(self, url):
        self._nonce: int = 0
        self._current_block_number: int = -1
        self._url = url
        self._node_address = None
        self._client: Optional[websockets.WebSocketClientProtocol] = None
        self._fetch_new_blocks_task: Optional[asyncio.Task] = None
        self._block_cache = TTLCache(maxsize=20, ttl=60)

    _nbw_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._nbw_logger is None:
            cls._nbw_logger = logging.getLogger(__name__)
        return cls._nbw_logger

    @property
    def block_number(self) -> int:
        return self._current_block_number

    async def start_network(self):
        if self._fetch_new_blocks_task is not None:
            await self.stop_network()
        self.logger().info("WESLEY TESTING --- NETWORK START")
        await self.connect()
        await self.subscribe(["newHeads"])
        self._fetch_new_blocks_task: asyncio.Task = safe_ensure_future(self.fetch_new_blocks_loop())

    async def stop_network(self):
        if self._fetch_new_blocks_task is not None:
            self.logger().info("WESLEY TESTING --- NETWORK STOP")
            await self.disconnect()
            self._fetch_new_blocks_task.cancel()
            self._fetch_new_blocks_task = None

    async def connect(self):
        try:
            self._client = await websockets.connect(uri=self._url)
            return self._client
        except Exception as e:
            print(f"ERROR in connection: {e}")

    async def disconnect(self):
        if self._client is not None:
            await self._client.close()
            # await self._client.wait_closed() #TODO: SHOULD I IMPLEMENT THIS???

    async def _send(self, emit_data) -> int:
        self._nonce += 1
        emit_data["id"] = self._nonce
        await self._client.send(ujson.dumps(emit_data))
        return self._nonce

    async def subscribe(self, params) -> bool:
        emit_data = {
            "method": "eth_subscribe",
            "params": params
        }
        nonce = await self._send(emit_data)
        raw_message = await self._client.recv()
        if raw_message is not None:
            resp = ujson.loads(raw_message)
            if resp.get("id", None) == nonce:
                self._node_address = resp.get("result")
                return True
        return False

    async def unsubscribe(self, params) -> bool:
        emit_data = {
            "method": "eth_unsubscribe",
            "params": params
        }
        nonce = await self._send(emit_data)
        raw_message = await self._client.recv()
        resp = ujson.loads(raw_message)
        if resp.get("id", None) == nonce:
            result = resp.get("result", None)
            return (result is not None) and result

    async def fetch_new_blocks_loop(self):
        try:
            while True:
                try:
                    async with timeout(30):
                        raw_message: AttributeDict = await self._client.recv()
                        self.logger().info(f"WESLEY TESTING --- RAW MESSAGE: {raw_message}")
                        message_json = ujson.loads(raw_message) if raw_message is not None else None
                        if message_json.get("method", None) == "eth_subscription":
                            subscription_result_params = message_json.get("params", None)
                            incoming_block = subscription_result_params.get("result", None) \
                                if subscription_result_params is not None else None
                            if incoming_block is not None:
                                hex_incoming_block = block_values_to_hex(incoming_block)
                                self._current_block_number = hex_incoming_block.get("number",
                                                                                    self._current_block_number)
                                self._block_cache[hex_incoming_block.get("hash")] = hex_incoming_block
                                self.trigger_event(NewBlocksWatcherEvent.NewBlocks, [hex_incoming_block])  # TODO: **** I MAY NEED TO PASS IN FULL Cache?
                except ConnectionClosedOK:
                    pass  # TODO: What should I do here????
                except asyncio.CancelledError:
                    raise
                except asyncio.TimeoutError:
                    self.logger().network("Timed out fetching new block.", exc_info=True,
                                          app_warning_msg="Timed out fetching new block. "
                                                          "Check wallet network connection")
                except Exception:
                    self.logger().network("Error fetching new block.", exc_info=True,
                                          app_warning_msg="Error fetching new block. "
                                                          "Check wallet network connection")
        except asyncio.CancelledError:
            raise

    async def get_timestamp_for_block(self, block_hash: HexBytes, max_tries: Optional[int] = 10) -> int:
        counter = 0
        block: AttributeDict = None
        if block_hash in self._block_cache.keys():
            block = self._block_cache.get(block_hash)
        else:
            while block is None:
                if counter == max_tries:
                    raise ValueError(f"Block hash {block_hash.hex()} does not exist.")
                counter += 1
                block = self._block_cache.get(block_hash)
                await asyncio.sleep(0.5)
        return block.get("timestamp")
