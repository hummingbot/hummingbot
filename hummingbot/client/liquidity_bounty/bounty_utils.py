#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../")))

import aiohttp
import asyncio
import logging
import pandas as pd
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
from sqlalchemy.orm import (
    Session,
)
from hummingbot.client.liquidity_bounty.liquidity_bounty_config_map import liquidity_bounty_config_map
from hummingbot.core.network_base import NetworkBase, NetworkStatus
from hummingbot.logger import HummingbotLogger
from hummingbot.model.sql_connection_manager import SQLConnectionManager
from hummingbot.model.trade_fill import TradeFill


class LiquidityBounty(NetworkBase):
    lb_logger: Optional[HummingbotLogger] = None
    _lb_shared_instance: Optional["LiquidityBounty"] = None
    LIQUIDITY_BOUNTY_REST_API = "http://localhost:16118/bounty"

    @classmethod
    def get_instance(cls) -> "LiquidityBounty":
        if cls._lb_shared_instance is None:
            cls._lb_shared_instance = LiquidityBounty()
        return cls._lb_shared_instance

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.lb_logger is None:
            cls.lb_logger = logging.getLogger(__name__)
        return cls.lb_logger

    def __init__(self, update_interval: int = 15):
        super().__init__()
        self._update_interval = update_interval
        self._ev_loop = asyncio.get_event_loop()
        self._shared_client: Optional[aiohttp.ClientSession] = None

        self._status: Dict[str, Any] = {}
        # timestamp = -1 when when no data has been fetched / timestamp = 0 when no trades have ever been submitted
        self._last_submitted_trade_timestamp: int = -1
        self.fetch_bounty_status_task: Optional[asyncio.Task] = None
        self.fetch_last_submitted_timestamp_task: Optional[asyncio.Task] = None
        self.submit_trades_task: Optional[asyncio.Task] = None

    def status(self) -> Dict[str, Any]:
        return self._status

    def formatted_status(self) -> str:
        return pd.DataFrame(self._status.items()).to_string(index=False, header=False)

    async def get_local_trades(self) -> List[Dict[str, Any]]:
        self.logger().error("in get_local_trades")
        trade_fill_sql: SQLConnectionManager = SQLConnectionManager.get_trade_fills_instance()
        trade_fill_session: Session = trade_fill_sql.get_shared_session()
        # TODO: filter by markets and trading pairs participating in liquidity bounties
        trade_fill_data = trade_fill_session \
            .query(TradeFill)\
            .filter(TradeFill.timestamp >= self._last_submitted_trade_timestamp)\
            .order_by(TradeFill.timestamp)\
            .all()
        self.logger().error("trade_fill_data")
        self.logger().error(trade_fill_data)
        return []

    async def _http_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def register(self) -> Dict[str, Any]:
        bounty_config: Dict[str, Any] = {key: cvar.value for key, cvar in liquidity_bounty_config_map.items()}
        assert bounty_config["liquidity_bounty_enabled"]
        assert bounty_config["agree_to_terms"]
        assert bounty_config["agree_to_data_collection"]
        assert bounty_config["final_confirmation"]

        email = bounty_config["email"]
        eth_address = bounty_config["eth_address"]
        try:
            client = await self._http_client()
            data = {"email": email, "eth_address": eth_address}
            async with client.request("POST", f"{self.LIQUIDITY_BOUNTY_REST_API}/client", json=data) as resp:
                # registration_status = "success" or <reason_for_failure>
                if resp.status not in {200, 400}:
                    raise Exception(f"Liquidity bounty server error. Server responded with status {resp.status}")

                results = await resp.json()
                if results["registration_status"] != "success":
                    raise Exception(f"Failed to register for liquidity bounty: {results['registration_status']}")
                return results
        except AssertionError:
            raise
        except asyncio.CancelledError:
            raise
        except Exception:
            raise

    async def authenticated_request(self, request_method: str, url: str, **kwargs) -> Dict[str, Any]:
        try:
            client = await self._http_client()
            client_id = liquidity_bounty_config_map.get("liquidity_bounty_client_id").value
            assert client_id is not None
            headers = {"Client-ID": client_id}

            async with client.request(request_method, url, headers=headers, **kwargs) as resp:
                results = await resp.json()
                if results.get("status", "") == "Unknown client id":
                    raise Exception("User not registered")
                return results
        except Exception as e:
            self.logger().network(f"Error fetching bounty status: {str(e)}", exc_info=True)
            raise

    async def fetch_bounty_status_loop(self):
        while True:
            try:
                self._status = await self.authenticated_request("GET", f"{self.LIQUIDITY_BOUNTY_REST_API}/client")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if "User not registered" in str(e):
                    self.logger().warning("User not registered. Aborting fetch_bounty_status_loop.")
                    break
            await asyncio.sleep(self._update_interval)

    async def fetch_last_timestamp_loop(self):
        while True:
            try:
                url = f"{self.LIQUIDITY_BOUNTY_REST_API}/trade/last_recorded_timestamp"
                results = await self.authenticated_request("GET", url)
                self._last_submitted_trade_timestamp = results.get("last_recorded_timestamp", -1)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if "User not registered" in str(e):
                    self.logger().warning("User not registered. Aborting fetch_last_timestamp_loop.")
                    break
            await asyncio.sleep(self._update_interval)

    async def submit_trades_loop(self):
        while True:
            try:
                self.logger().error("in submit_trades_loop")
                self.logger().error(self._last_submitted_trade_timestamp)
                if self._last_submitted_trade_timestamp >= 0:
                    self.logger().error("in 2")
                    trades = await self.get_local_trades()
                    self.logger().error("in 3")
                    self.logger().error(trades)
                    if len(trades) > 0:
                        url = f"{self.LIQUIDITY_BOUNTY_REST_API}/trade"
                        results = await self.authenticated_request("POST", url, json={"trades": trades})
                        self.logger().error(results)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if "User not registered" in str(e):
                    self.logger().warning("User not registered. Aborting submit_trades_loop.")
                    break
                self.logger().error(str(e))
            await asyncio.sleep(self._update_interval)

    async def start_network(self):
        await self.stop_network()
        self.fetch_bounty_status_task = asyncio.ensure_future(self.fetch_bounty_status_loop())
        self.fetch_last_submitted_timestamp_task = asyncio.ensure_future(self.fetch_last_timestamp_loop())
        self.submit_trades_task = asyncio.ensure_future(self.submit_trades_loop())

    async def stop_network(self):
        if self.fetch_bounty_status_task is not None:
            self.fetch_bounty_status_task.cancel()
            self.fetch_bounty_status_task = None
            self.fetch_last_submitted_timestamp_task.cancel()
            self.fetch_last_submitted_timestamp_task = None
            self.submit_trades_task.cancel()
            self.submit_trades_task = None

    async def check_network(self) -> NetworkStatus:
        try:
            async with aiohttp.ClientSession(loop=self._ev_loop,
                                             connector=aiohttp.TCPConnector(verify_ssl=False)) as session:
                async with session.get(self.LIQUIDITY_BOUNTY_REST_API) as resp:
                    if resp.status != 200:
                        raise Exception(f"Liquidity bounty server is down.")
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED




