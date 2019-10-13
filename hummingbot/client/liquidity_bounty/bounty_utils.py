#!/usr/bin/env python
import json
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../")))

import aiohttp
import asyncio
import logging
import pandas as pd
from datetime import datetime
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
from sqlalchemy import (
    and_,
    or_,
)
from sqlalchemy.orm import (
    Session,
    Query,
)
from sqlalchemy.sql.elements import BooleanClauseList
from hummingbot.client.liquidity_bounty.liquidity_bounty_config_map import liquidity_bounty_config_map
from hummingbot.core.network_base import NetworkBase, NetworkStatus
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.model.sql_connection_manager import SQLConnectionManager
from hummingbot.model.trade_fill import TradeFill
from hummingbot.model.order import Order
from hummingbot.model.order_status import OrderStatus


class LiquidityBounty(NetworkBase):
    lb_logger: Optional[HummingbotLogger] = None
    _lb_shared_instance: Optional["LiquidityBounty"] = None
    LIQUIDITY_BOUNTY_REST_API = "https://api.hummingbot.io/bounty"
    ACCEPTED_ORDER_STATUS_UPDATES = ["BuyOrderCreated", "SellOrderCreated", "OrderFilled", "OrderCancelled",
                                     "OrderFailure", "OrderExpired"]

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

    def __init__(self,
                 update_interval: int = 60,
                 active_bounties_update_interval: int = 3600  # Fetch for active bounties every hour
                 ):
        super().__init__()
        self._update_interval = update_interval
        self._active_bounties_update_interval = active_bounties_update_interval
        self._ev_loop = asyncio.get_event_loop()
        self._shared_client: Optional[aiohttp.ClientSession] = None
        self._status: Dict[str, Any] = {}
        self._active_bounties: List[Dict[str, Any]] = []
        # timestamp = -1 when when no data has been fetched / timestamp = 0 when no trades have ever been submitted
        self._last_submitted_trade_timestamp: int = -1
        self._last_submitted_order_timestamp: int = -1
        self._last_submitted_order_status_timestamp: int = -1

        self._last_timestamp_fetched_event = asyncio.Event()
        self._active_bounties_fetched_event = asyncio.Event()

        self.fetch_active_bounties_task: Optional[asyncio.Task] = None
        self.status_polling_task: Optional[asyncio.Task] = None
        self.submit_data_task: Optional[asyncio.Task] = None

    def status(self) -> Dict[str, Any]:
        return self._status

    def formatted_status(self) -> str:
        status_dict = self._status.copy()
        del status_dict["status_codes"]
        df: pd.DataFrame = pd.DataFrame(status_dict.items())
        lines = ["", "  Client Status:"] + ["    " + line for line in df.to_string(index=False, header=False).split("\n")]
        return "\n".join(lines)

    def active_bounties(self) -> List[Dict[str, Any]]:
        return self._active_bounties

    def formatted_bounties(self) -> str:
        rows = [[
            bounty["market"],
            bounty["base_asset"],
            datetime.fromtimestamp(bounty["start_timestamp"] / 1e3).strftime("%m/%d/%Y %H:%M") if bounty["start_timestamp"] > 0 else "TBA",
            datetime.fromtimestamp(bounty["end_timestamp"] / 1e3).strftime("%m/%d/%Y %H:%M") if bounty["end_timestamp"] > 0 else "TBA",
            bounty["link"]
        ] for bounty in self._active_bounties]
        df: pd.DataFrame = pd.DataFrame(
            rows,
            columns=["Market", "Asset", "Start (MM/DD/YYYY)", "End (MM/DD/YYYY)", "Leaderboard link"]
        )
        lines = ["", "  Bounties:"] + ["    " + line for line in df.to_string(index=False).split("\n")]
        return "\n".join(lines)

    async def _wait_till_ready(self):
        if not self._last_timestamp_fetched_event.is_set():
            await self._last_timestamp_fetched_event.wait()
        if not self._active_bounties_fetched_event.is_set():
            await self._active_bounties_fetched_event.wait()

    async def get_unsubmitted_trades(self) -> List[TradeFill]:
        """ Get locally saved trades that have not been submitted to liquidity bounties """
        await self._wait_till_ready()
        session: Session = SQLConnectionManager.get_trade_fills_instance().get_shared_session()

        try:
            and_conditions: BooleanClauseList = [and_(
                TradeFill.base_asset == ab["base_asset"],
                TradeFill.market == ab["market"],
                TradeFill.timestamp >= ab["start_timestamp"],  # does not matter if start_timestamp == -1
                TradeFill.timestamp <= (ab["end_timestamp"] if ab["end_timestamp"] > 0 else 1e14)
            ) for ab in self._active_bounties]

            query: Query = (session
                            .query(TradeFill)
                            .filter(TradeFill.timestamp > self._last_submitted_trade_timestamp)
                            .filter(or_(*and_conditions))
                            .order_by(TradeFill.timestamp))

            new_trades: List[TradeFill] = query.all()
            return new_trades
        except Exception as e:
            self.logger().error(f"Failed to query for unsubmitted trades: {str(e)}", exc_info=True)

    def get_order_filter(self) -> BooleanClauseList:
        and_conditions: BooleanClauseList = [and_(
            Order.base_asset == ab["base_asset"],
            Order.market == ab["market"],
            Order.creation_timestamp >= ab["start_timestamp"],  # does not matter if start_timestamp == -1
            Order.creation_timestamp <= (ab["end_timestamp"] if ab["end_timestamp"] > 0 else 1e14)
        ) for ab in self._active_bounties]
        return and_conditions

    async def get_unsubmitted_orders(self) -> List[Order]:
        """ Get locally saved orders that have not been submitted to liquidity bounties """
        await self._wait_till_ready()
        session: Session = SQLConnectionManager.get_trade_fills_instance().get_shared_session()

        try:
            and_conditions: BooleanClauseList = self.get_order_filter()

            query: Query = (session
                            .query(Order)
                            .filter(Order.creation_timestamp > self._last_submitted_order_timestamp)
                            .filter(or_(*and_conditions))
                            .order_by(Order.creation_timestamp))

            new_orders: List[Order] = query.all()
            return new_orders
        except Exception as e:
            self.logger().error(f"Failed to query for unsubmitted orders: {str(e)}", exc_info=True)

    async def get_unsubmitted_order_statuses(self) -> List[OrderStatus]:
        """ Get locally saved order statuses that have not been submitted to liquidity bounties """
        await self._wait_till_ready()
        session: Session = SQLConnectionManager.get_trade_fills_instance().get_shared_session()

        try:
            and_conditions: BooleanClauseList = self.get_order_filter()

            query: Query = (session
                            .query(OrderStatus)
                            .filter(Order.id == OrderStatus.order_id)
                            .filter(OrderStatus.timestamp > self._last_submitted_order_status_timestamp)
                            .filter(OrderStatus.status.in_(self.ACCEPTED_ORDER_STATUS_UPDATES))
                            .filter(or_(*and_conditions))
                            .order_by(OrderStatus.timestamp))

            new_order_statuses: List[OrderStatus] = query.all()
            return new_order_statuses
        except Exception as e:
            self.logger().error(f"Failed to query for unsubmitted order statuses: {str(e)}", exc_info=True)

    async def _http_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def fetch_active_bounties(self):
        """ fetch a list of active bounties from server. """
        try:
            client: aiohttp.ClientSession = await self._http_client()
            async with client.request("GET", f"{self.LIQUIDITY_BOUNTY_REST_API}/list") as resp:
                if resp.status not in {200, 400}:
                    raise Exception(f"Liquidity bounty server error. Server responded with status {resp.status}")
                results = await resp.json()
                self.logger().debug(results)
                self._active_bounties = results.get("bounties", [])
                if not self._active_bounties_fetched_event.is_set():
                    self._active_bounties_fetched_event.set()
        except Exception:
            raise

    async def fetch_active_bounties_loop(self):
        """ Repeatedly polling for active bounties  """
        while True:
            try:
                await self.fetch_active_bounties()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Failed to fetch active bounties: {str(e)}", exc_info=True)
            await asyncio.sleep(self._active_bounties_update_interval)

    async def register(self, email: Optional[str] = None, eth_address: Optional[str] = None) -> Dict[str, Any]:
        if email is None or eth_address is None:
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
                if resp.status not in {200, 400}:
                    raise Exception(f"Liquidity bounty server error. Server responded with status {resp.status}")

                results = await resp.json()
                status: str = results.get("status") or results.get("registration_status")
                # registration_status is for backwards compatibility
                if status != "success":
                    raise Exception(f"Failed to register for liquidity bounty: {status}")
                return results
        except AssertionError:
            raise
        except asyncio.CancelledError:
            raise
        except Exception:
            raise

    async def restore_id(self, email: str) -> str:
        try:
            client = await self._http_client()
            data = {"email": email}
            async with client.request("POST", f"{self.LIQUIDITY_BOUNTY_REST_API}/client/restore_id", json=data) as resp:
                if resp.status not in {200, 400}:
                    raise Exception(f"Liquidity bounty server error. Server responded with status {resp.status}")

                results = await resp.json()
                if results["status"] != "success":
                    raise Exception(f"Failed to restore liquidity bounty: {results['status']}")
                return results["message"]
        except asyncio.CancelledError:
            raise
        except Exception:
            raise

    async def send_verification_code(self, email: str, verification_code: str) -> str:
        try:
            client = await self._http_client()
            data = {"email": email, "verification_code": verification_code}
            async with client.request("POST", f"{self.LIQUIDITY_BOUNTY_REST_API}/client/verify_client", json=data) as resp:
                if resp.status not in {200, 400}:
                    raise Exception(f"Liquidity bounty server error. Server responded with status {resp.status}")

                results = await resp.json()
                if results["status"] != "success":
                    raise Exception(f"Failed to verify client: {results['status']}")
                return results["client_id"]
        except asyncio.CancelledError:
            raise
        except Exception:
            raise

    async def authenticated_request(self, request_method: str, url: str, **kwargs) -> Dict[str, Any]:
        try:
            # Set default data value here in case an assertion error occurs
            data = None
            client = await self._http_client()
            client_id = liquidity_bounty_config_map.get("liquidity_bounty_client_id").value
            assert client_id is not None
            headers = {"Client-ID": client_id}

            async with client.request(request_method, url, headers=headers, **kwargs) as resp:
                data = await resp.text()
                self.logger().debug(f"{url} {resp.status} {data} {kwargs}")
                results = json.loads(data)
                if "error" in results:
                    raise Exception(results.get("error"))
                if resp.status == 500:
                    raise Exception(f"Server side error when submitting to {url}")
                if results.get("status", "") == "Unknown client id":
                    raise Exception("User not registered")
                return results
        except Exception as e:
            self.logger().network(f"Error in authenticated request: {str(e)}, data: {data}", exc_info=True)
            raise

    async def fetch_client_status(self):
        try:
            self._status = await self.authenticated_request("GET", f"{self.LIQUIDITY_BOUNTY_REST_API}/client")
        except Exception:
            raise

    async def fetch_last_timestamp(self):
        try:
            url = f"{self.LIQUIDITY_BOUNTY_REST_API}/last_recorded_timestamp"
            results = await self.authenticated_request("GET", url)
            self._last_submitted_trade_timestamp = int(results.get("last_recorded_trade_timestamp", -1))
            self._last_submitted_order_timestamp = int(results.get("last_recorded_order_timestamp", -1))
            self._last_submitted_order_status_timestamp = int(results.get("last_recorded_order_status_timestamp", -1))
            self._last_timestamp_fetched_event.set()
        except Exception:
            raise

    async def status_polling_loop(self):
        while True:
            try:
                await safe_gather(*[
                    self.fetch_client_status(),
                    self.fetch_last_timestamp(),
                ], loop=self._ev_loop, return_exceptions=True)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if "User not registered" in str(e):
                    self.logger().warning("User not registered. Aborting fetch_client_status_loop.")
                    break
                self.logger().error(f"Error getting bounty status: {e}", exc_info=True)
            await asyncio.sleep(self._update_interval)

    async def submit_trades(self):
        try:
            trades: List[TradeFill] = await self.get_unsubmitted_trades()
            # only submit 5000 at a time
            formatted_trades: List[Dict[str, Any]] = [TradeFill.to_bounty_api_json(trade) for trade in trades[:5000]]

            if self._last_submitted_trade_timestamp >= 0 and len(formatted_trades) > 0:
                url = f"{self.LIQUIDITY_BOUNTY_REST_API}/trade"
                results = await self.authenticated_request("POST", url, json={"trades": formatted_trades})
                num_submitted = results.get("trades_submitted", 0)
                num_recorded = results.get("trades_recorded", 0)
                if num_submitted != num_recorded:
                    self.logger().warning(f"Failed to submit {num_submitted - num_recorded} trade(s)")
                if num_recorded > 0:
                    self.logger().info(f"Successfully sent {num_recorded} trade(s) to claim bounty")
        except Exception:
            raise

    async def submit_orders(self):
        try:
            orders: List[Order] = await self.get_unsubmitted_orders()
            # only submit 5000 at a time
            formatted_orders: List[Dict[str, Any]] = [Order.to_bounty_api_json(order) for order in orders[:5000]]

            if self._last_submitted_order_timestamp >= 0 and len(formatted_orders) > 0:
                url = f"{self.LIQUIDITY_BOUNTY_REST_API}/order"
                results = await self.authenticated_request("POST", url, json={"orders": formatted_orders})
                num_submitted = results.get("orders_submitted", 0)
                num_recorded = results.get("orders_recorded", 0)
                if num_submitted != num_recorded:
                    self.logger().warning(f"Failed to submit {num_submitted - num_recorded} order(s)")
                if num_recorded > 0:
                    self.logger().info(f"Successfully sent {num_recorded} order(s) to claim bounty")
        except Exception:
            raise

    async def submit_order_statuses(self):
        try:
            order_statuses: List[OrderStatus] = await self.get_unsubmitted_order_statuses()
            # only submit 5000 at a time
            formatted_order_statuses: List[Dict[str, Any]] = [OrderStatus.to_bounty_api_json(order_status)
                                                              for order_status in order_statuses[:5000]]
            if self._last_submitted_order_status_timestamp >= 0 and len(formatted_order_statuses) > 0:
                url = f"{self.LIQUIDITY_BOUNTY_REST_API}/order_status"
                results = await self.authenticated_request("POST", url,
                                                           json={"order_statuses": formatted_order_statuses})
                self.logger().debug(results)
                num_submitted = results.get("order_status_submitted", 0)
                num_recorded = results.get("order_status_recorded", 0)
                if num_submitted != num_recorded:
                    self.logger().warning(f"Failed to submit {num_submitted - num_recorded} order status(es)")
                if num_recorded > 0:
                    self.logger().info(f"Successfully sent {num_recorded} order status(es) to claim bounty")
        except Exception:
            raise

    async def submit_data_loop(self):
        await self._wait_till_ready()
        while True:
            try:
                # Not using safe_gather here because orders need to be submitted before order status
                await self.submit_trades()
                await self.submit_orders()
                await self.submit_order_statuses()
            except asyncio.CancelledError:
                raise
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                if "User not registered" in str(e):
                    self.logger().warning("User not registered. Aborting submit_data_loop.")
                    break
                else:
                    self.logger().error(f"Error submitting data: {str(e)}", exc_info=True)
            await asyncio.sleep(self._update_interval)

    async def start_network(self):
        await self.stop_network()
        self.fetch_active_bounties_task = safe_ensure_future(self.fetch_active_bounties_loop(), loop=self._ev_loop)
        self.status_polling_task = safe_ensure_future(self.status_polling_loop(), loop=self._ev_loop)
        self.submit_data_task = safe_ensure_future(self.submit_data_loop(), loop=self._ev_loop)

    async def stop_network(self):
        if self.fetch_active_bounties_task is not None:
            self.fetch_active_bounties_task.cancel()
            self.fetch_active_bounties_task = None
        if self.status_polling_task is not None:
            self.status_polling_task.cancel()
            self.status_polling_task = None
        if self.submit_data_task is not None:
            self.submit_data_task.cancel()
            self.submit_data_task = None

    async def check_network(self) -> NetworkStatus:
        try:
            client = await self._http_client()
            async with client.request("GET", f"{self.LIQUIDITY_BOUNTY_REST_API}/") as resp:
                if resp.status != 200:
                    self.logger().error(resp.status)
                    raise Exception(f"Liquidity bounty server is down.")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().error(str(e))
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    def start(self):
        NetworkBase.start(self)

    def stop(self):
        NetworkBase.stop(self)
