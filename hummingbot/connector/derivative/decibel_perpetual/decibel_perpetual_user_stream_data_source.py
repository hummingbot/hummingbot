import asyncio
import time
from typing import Any, Dict, List, Optional

import aiohttp

import hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_auth import DecibelPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger


class DecibelPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    """
    Provides user-specific data (account, positions, open orders, fills) for Decibel.

    Since Decibel does not document a WebSocket API, this class polls the REST
    endpoints at regular intervals and emits synthetic event messages that the
    connector processes via ``_user_stream_event_listener``.
    """

    _logger: Optional[HummingbotLogger] = None

    POLL_INTERVAL = 5.0    # seconds between account/position polls
    ORDER_POLL_INTERVAL = 5.0  # seconds between order status polls

    def __init__(
        self,
        connector,
        api_factory: WebAssistantsFactory,
        auth: DecibelPerpetualAuth,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._connector = connector
        self._api_factory = api_factory
        self._auth = auth
        self._domain = domain
        self._base_url = web_utils.get_rest_url(domain)
        self._last_recv_time: float = 0.0

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    def _get_auth_headers(self) -> Dict[str, str]:
        return self._auth.get_auth_headers()

    async def _poll_account_state(self, output: asyncio.Queue):
        """Fetch account balances and emit balance_update events."""
        account_addr = self._auth.main_wallet_address
        headers = self._get_auth_headers()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._base_url}{CONSTANTS.GET_ACCOUNT_OVERVIEW_PATH_URL}",
                    params={"account": account_addr},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
                    self._last_recv_time = time.time()

            event = {
                "type": "balance_update",
                "asset": "USDC",
                "total": str(data.get("perp_equity_balance", "0")),
                "available": str(data.get("usdc_cross_withdrawable_balance", "0")),
                "timestamp": time.time() * 1000,
            }
            await output.put(event)
        except Exception:
            self.logger().exception("Error polling account state")

    async def _poll_positions(self, output: asyncio.Queue):
        """Fetch open positions and emit position_update events."""
        account_addr = self._auth.main_wallet_address
        headers = self._get_auth_headers()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._base_url}{CONSTANTS.GET_ACCOUNT_POSITIONS_PATH_URL}",
                    params={"account": account_addr},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
                    self._last_recv_time = time.time()

            positions = data if isinstance(data, list) else data.get("positions", [])

            for position in positions:
                event = {
                    "type": "position_update",
                    "market": position.get("market", ""),
                    "size": str(position.get("size", "0")),
                    "entry_price": str(position.get("entry_price", "0")),
                    "unrealized_pnl": str(position.get("unrealized_pnl", "0")),
                    "leverage": str(position.get("leverage", "1")),
                    "timestamp": time.time() * 1000,
                }
                await output.put(event)
        except Exception:
            self.logger().exception("Error polling positions")

    async def _poll_open_orders(self, output: asyncio.Queue):
        """Fetch open orders and emit order_update events."""
        account_addr = self._auth.main_wallet_address
        headers = self._get_auth_headers()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._base_url}{CONSTANTS.GET_ACCOUNT_OPEN_ORDERS_PATH_URL}",
                    params={"account": account_addr},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
                    self._last_recv_time = time.time()

            orders = data if isinstance(data, list) else data.get("orders", [])

            for order in orders:
                event = {
                    "type": "order_update",
                    "order_id": str(order.get("order_id", "")),
                    "client_order_id": str(order.get("client_order_id", "")),
                    "market": order.get("market", ""),
                    "status": order.get("status", "Open"),
                    "size": str(order.get("size", "0")),
                    "filled_size": str(order.get("filled_size", "0")),
                    "price": str(order.get("price", "0")),
                    "is_buy": order.get("is_buy", True),
                    "timestamp": float(order.get("timestamp", time.time() * 1000)),
                }
                await output.put(event)
        except Exception:
            self.logger().exception("Error polling open orders")

    async def _poll_trade_history(self, output: asyncio.Queue):
        """Fetch recent trades and emit trade events."""
        account_addr = self._auth.main_wallet_address
        headers = self._get_auth_headers()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._base_url}{CONSTANTS.GET_USER_TRADE_HISTORY_PATH_URL}",
                    params={"account": account_addr, "limit": 50},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
                    self._last_recv_time = time.time()

            trades = data if isinstance(data, list) else data.get("trades", [])

            for trade in trades:
                event = {
                    "type": "trade",
                    "trade_id": str(trade.get("trade_id", "")),
                    "order_id": str(trade.get("order_id", "")),
                    "market": trade.get("market", ""),
                    "price": str(trade.get("price", "0")),
                    "size": str(trade.get("size", "0")),
                    "is_buy": trade.get("is_buy", True),
                    "fee": str(trade.get("fee", "0")),
                    "fee_asset": trade.get("fee_asset", "USDC"),
                    "timestamp": float(trade.get("timestamp", time.time() * 1000)),
                }
                await output.put(event)
        except Exception:
            self.logger().exception("Error polling trade history")

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        Main loop: poll all REST endpoints at regular intervals and push
        synthetic event messages to the output queue.
        """
        while True:
            try:
                await self._poll_account_state(output)
                await self._poll_positions(output)
                await self._poll_open_orders(output)
                await self._poll_trade_history(output)
                await asyncio.sleep(self.POLL_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Error in user stream polling loop")
                await asyncio.sleep(self.POLL_INTERVAL)
