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
    Optional,
)
from hummingbot.client.liquidity_bounty.liquidity_bounty_config_map import liquidity_bounty_config_map
from hummingbot.core.network_base import NetworkBase, NetworkStatus
from hummingbot.logger import HummingbotLogger


class LiquidityBounty(NetworkBase):
    lb_logger: Optional[HummingbotLogger] = None
    _lb_shared_instance: Optional["LiquidityBounty"] = None
    LIQUIDITY_BOUNTY_REST_API = "http://localhost:16118"

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

    def __init__(self, update_interval: int = 30):
        super().__init__()
        self._ev_loop = asyncio.get_event_loop()
        self._status: Dict[str, Any] = {}
        self._shared_client: Optional[aiohttp.ClientSession] = None
        self._update_interval = update_interval
        self.fetch_bounty_status_task: Optional[asyncio.Task] = None

    def status(self) -> Dict[str, Any]:
        return self._status

    def formatted_status(self) -> str:
        return pd.DataFrame(self._status.items()).to_string(index=False, header=False)

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
        except asyncio.CancelledError:
            raise
        except Exception:
            raise

    async def fetch_bounty_status_loop(self):
        while True:
            try:
                client = await self._http_client()
                client_id = liquidity_bounty_config_map.get("liquidity_bounty_client_id").value
                assert client_id is not None

                async with client.request("GET",
                                          f"{self.LIQUIDITY_BOUNTY_REST_API}/client",
                                          json={"client_id": client_id}) as resp:
                    results = await resp.json()
                    if results.get("status", "") == "Unknown client id":
                        raise Exception("User not registered")
                    self._status = results
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if "User not registered" in str(e):
                    self.logger().error("User not registered. Aborting.")
                    break
                else:
                    self.logger().network(f"Error fetching bounty status", exc_info=True)
            await asyncio.sleep(self._update_interval)

    async def start_network(self):
        await self.stop_network()
        self.fetch_bounty_status_task = asyncio.ensure_future(self.fetch_bounty_status_loop())

    async def stop_network(self):
        if self.fetch_bounty_status_task is not None:
            self.fetch_bounty_status_task.cancel()
            self.fetch_bounty_status_task = None

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




