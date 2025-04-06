import asyncio
import time
from dataclasses import dataclass, fields
from enum import Enum
from typing import Optional, Set

import pandas as pd
from bidict import bidict
from pandas import DataFrame

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.network_base import NetworkBase
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class LiquidationSide(Enum):
    SHORT = "SHORT"  # Short position got liquidated (=> price went long)
    LONG = "LONG"  # Long position got liquidated (=> price went short)

    def __str__(self):
        return '%s' % self.value


@dataclass
class Liquidation:
    """
    Represents the information of a single liquidation
    """
    timestamp: int
    trading_pair: str
    quantity: float
    price: float
    side: LiquidationSide


class LiquidationsBase(NetworkBase):
    """
    This class serves as a base class for fetching and storing liquidation data from crypto exchanges. The storage
    is done in a time based manner - meaning an aggregation happens and you can decide how much history you wanto to keep.
    The class uses the WS Assistants for all the IO operations,
    """

    def __init__(self, trading_pairs: Set[str], max_retention_seconds: int):
        super().__init__()
        async_throttler = AsyncThrottler(rate_limits=self.rate_limits)
        self._api_factory = WebAssistantsFactory(throttler=async_throttler)
        self._max_retention_seconds = max_retention_seconds
        self._trading_pairs = trading_pairs
        self._liquidations = {}
        self._listen_liquidations_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._subscribed_to_channels = False
        self._trading_pairs_map = bidict()

    async def start_network(self):
        """
        This method starts the network and starts a task for listen_for_subscriptions.
        """
        await self.stop_network()
        await self._fetch_and_map_trading_pairs()
        self._listen_liquidations_task = safe_ensure_future(self.listen_for_subscriptions())
        self._cleanup_task = safe_ensure_future(self._cleanup_old_liquidations_loop())
        self.logger().info("Liquidations feed ({}) started, keeping the last {}s of data".format(self.name,
                                                                                                 self._max_retention_seconds))
        self._subscribed_to_channels = True

    async def stop_network(self):
        """
        This method stops the network by canceling the _listen_liquidations_task and _cleanup_task.
        """
        if self._listen_liquidations_task is not None:
            self._listen_liquidations_task.cancel()
            self._listen_liquidations_task = None

        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            self._cleanup_task = None

    @property
    def ready(self):
        """
        Turns True if websockets are subscribed to the liquidations feed and network is basically started / up
        """
        return self._subscribed_to_channels

    @property
    def name(self):
        raise NotImplementedError

    @property
    def rest_url(self):
        raise NotImplementedError

    @property
    def health_check_url(self):
        raise NotImplementedError

    @property
    def wss_url(self):
        raise NotImplementedError

    @property
    def rate_limits(self):
        raise NotImplementedError

    async def check_network(self) -> NetworkStatus:
        raise NotImplementedError

    async def _cleanup_old_liquidations_loop(self):
        while True:
            self._cleanup_old_liquidations()
            await self._sleep(1.0)

    def _cleanup_old_liquidations(self):
        try:
            current_time_ms = int(time.time() * 1000)
            if self._liquidations:
                for trading_pair, liquidations in list(self._liquidations.items()):
                    self._liquidations[trading_pair] = [
                        liq for liq in liquidations if
                        current_time_ms - liq.timestamp < self._max_retention_seconds * 1000
                    ]
        except Exception:
            self.logger().exception(
                "Unexpected error occurred when cleaning up outdated liquidations. Retrying in 1 seconds...",
            )

    def liquidations_df(self, trading_pair=None) -> DataFrame:
        """
        This method returns the liquidations stored as a Pandas DataFrame.
        If no trading_pair is specified, all liquidations are returned in a single DataFrame.
        If the specified trading_pair has no data, an empty DataFrame is returned.
        """
        # Dynamically retrieve column names from the Liquidation dataclass
        column_names = [f.name for f in fields(Liquidation)]

        # Check if a specific trading pair is requested
        if trading_pair:
            # Retrieve the list of Liquidation objects for the specified trading pair
            liquidations = self._liquidations.get(trading_pair)
            # If no liquidations are found for the trading pair, return an empty DataFrame
            if not liquidations:
                return pd.DataFrame(columns=column_names)
            # Convert the list of dataclass instances to a DataFrame
            return pd.DataFrame([liq.__dict__ for liq in liquidations])
        else:
            # No specific trading pair is requested, combine all pairs
            all_liquidations = []
            # Iterate over all trading pairs and collect their liquidations
            for pair_liquidations in self._liquidations.values():
                all_liquidations.extend(pair_liquidations)
            # If no liquidations are collected, return an empty DataFrame
            if not all_liquidations:
                return pd.DataFrame(columns=column_names)
            # Convert the list of all liquidations to a DataFrame
            return pd.DataFrame([liq.__dict__ for liq in all_liquidations])

    def get_exchange_trading_pair(self, trading_pair):
        raise NotImplementedError

    async def listen_for_subscriptions(self):
        """
        Connects to the liquidations (=forceOrder) websocket endpoint and listens to the messages sent by the
        exchange.
        """
        ws: Optional[WSAssistant] = None
        while True:
            try:
                ws: WSAssistant = await self._connected_websocket_assistant()
                await self._subscribe_channels(ws)
                await self._process_websocket_messages(websocket_assistant=ws)
            except asyncio.CancelledError:
                raise
            except ConnectionError as connection_exception:
                self.logger().warning(f"The websocket connection was closed ({connection_exception})")
            except Exception:
                self.logger().exception(
                    "Unexpected error occurred when listening to public liquidations. Retrying in 1 seconds...",
                )
                await self._sleep(1.0)
            finally:
                await self._on_order_stream_interruption(websocket_assistant=ws)

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=self.wss_url,
                         ping_timeout=30)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the liquidation events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        raise NotImplementedError

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        raise NotImplementedError

    async def _fetch_and_map_trading_pairs(self):
        """
        Used to fetch the trading pairs from the exchange and create the bidict mapping for hummingbot which is
        later used in _process_websocket_messages to be able to give the right reverse mapping from the exchange native
        pair (e.g. "BTC-USDT" is "BTCUSDT" on binance)
        """
        raise NotImplementedError

    async def _sleep(self, delay):
        """
        Function added only to facilitate patching the sleep in unit tests without affecting the asyncio module
        """
        await asyncio.sleep(delay)

    async def _on_order_stream_interruption(self, websocket_assistant: Optional[WSAssistant] = None):
        websocket_assistant and await websocket_assistant.disconnect()
