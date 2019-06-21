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
    Query
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
        self._new_trades_queue: asyncio.Queue = asyncio.Queue()
        self._status: Dict[str, Any] = {}
        # timestamp = -1 when when no data has been fetched / timestamp = 0 when no trades have ever been submitted
        self._last_submitted_trade_timestamp: int = -1
        self._last_timestamp_fetched_event = asyncio.Event()

        self.add_unsubmitted_trades_task: Optional[asyncio.Task] = None
        self.fetch_bounty_status_task: Optional[asyncio.Task] = None
        self.fetch_last_submitted_timestamp_task: Optional[asyncio.Task] = None
        self.submit_trades_task: Optional[asyncio.Task] = None

    def status(self) -> Dict[str, Any]:
        return self._status

    def formatted_status(self) -> str:
        return pd.DataFrame(self._status.items()).to_string(index=False, header=False)

    def did_receive_new_trade_records(self, new_trades: List[TradeFill]):
        self._new_trades_queue.put_nowait(new_trades)

    async def add_unsubmitted_trades_to_queue(self):
        """ Get locally saved trades that have not been submitted to liquidity bounties """
        if not self._last_timestamp_fetched_event.is_set():
            await self._last_timestamp_fetched_event.wait()
        session: Session = SQLConnectionManager.get_trade_fills_instance().get_shared_session()
        if self._last_submitted_trade_timestamp > -1:
            # TODO: add filters so that only trades from certain markets and certain trading_pairs get sent
            query: Query = (session
                            .query(TradeFill)
                            .filter(TradeFill.timestamp >= self._last_submitted_trade_timestamp)
                            .order_by(TradeFill.timestamp))
            new_trades: List[TradeFill] = query.all()
            self.did_receive_new_trade_records(new_trades)

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
                self._last_timestamp_fetched_event.set()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if "User not registered" in str(e):
                    self.logger().warning("User not registered. Aborting fetch_last_timestamp_loop.")
                    break
            await asyncio.sleep(self._update_interval)

    async def submit_trades_loop(self):
        if not self._last_timestamp_fetched_event.is_set():
            await self._last_timestamp_fetched_event.wait()
        while True:
            try:
                new_trades_records: List[TradeFill] = await self._new_trades_queue.get()
                formatted_trades: List[Dict[str, Any]] = [
                    TradeFill.to_bounty_api_json(trade) for trade in new_trades_records
                ]
                if self._last_submitted_trade_timestamp >= 0:
                    if len(formatted_trades) > 0:
                        url = f"{self.LIQUIDITY_BOUNTY_REST_API}/trade"
                        results = await self.authenticated_request("POST", url, json={"trades": formatted_trades})
                        # {'trades_submitted': 44, 'trades_recorded': 44}
                        num_submitted = results.get("trades_submitted", 0)
                        num_recorded = results.get("trades_recorded", 0)
                        if num_submitted != num_recorded:
                            self.logger().warning(f"Failed to submit {num_submitted - num_recorded} trades")
                        self.logger().info(f"Successfully sent {num_recorded} trades to claim bounty")
            except asyncio.CancelledError:
                    raise
            except asyncio.TimeoutError:
                    continue
            except Exception as e:
                if "User not registered" in str(e):
                    self.logger().warning("User not registered. Aborting submit_trades_loop.")
                    break
                else:
                    self.logger().error(f"Error submitting trades: {str(e)}")
            await asyncio.sleep(self._update_interval)

    async def start_network(self):
        await self.stop_network()
        self.add_unsubmitted_trades_task = asyncio.ensure_future(self.add_unsubmitted_trades_to_queue())
        self.fetch_last_submitted_timestamp_task = asyncio.ensure_future(self.fetch_last_timestamp_loop())
        self.fetch_bounty_status_task = asyncio.ensure_future(self.fetch_bounty_status_loop())
        self.submit_trades_task = asyncio.ensure_future(self.submit_trades_loop())

    async def stop_network(self):
        if self.fetch_bounty_status_task is not None:
            self.add_unsubmitted_trades_task.cancel()
            self.add_unsubmitted_trades_task = None
            self.fetch_last_submitted_timestamp_task.cancel()
            self.fetch_last_submitted_timestamp_task = None
            self.fetch_bounty_status_task.cancel()
            self.fetch_bounty_status_task = None
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




