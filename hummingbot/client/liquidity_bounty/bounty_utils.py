import aiohttp
import asyncio
from typing import (
    Any,
    Dict,
    Optional,
)
from hummingbot.client.liquidity_bounty.liquidity_bounty_config_map import liquidity_bounty_config_map
from hummingbot.core.network_base import NetworkBase, NetworkStatus


class LiquidityBounty(NetworkBase):
    LIQUIDITY_BOUNTY_REST_API = "http://localhost:7000"

    def __init__(self):
        super().__init__()
        self._ev_loop = asyncio.get_event_loop()
        self._status: Dict[str, Any] = {}
        self.fetch_bounty_status_task: Optional[asyncio.Task] = None

    def status(self) -> Dict[Any]:
        return self._status

    def formatted_status(self) -> str:
        raise NotImplementedError

    async def _http_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def register(self):
        bounty_config: Dict[str, Any] = {key: cvar["value"] for key, cvar in liquidity_bounty_config_map.items()}
        assert bounty_config["liquidity_bounty_enabled"]
        assert bounty_config["agree_to_terms"]
        assert bounty_config["agree_to_data_collection"]
        assert bounty_config["final_confirmation"]

        email = bounty_config["email"]
        eth_address = bounty_config["public_ethereum_wallet_address"]

        try:
            client = await self._http_client()
            data = {"email": email, "eth_address": eth_address}
            async with client.request("POST", f"{self.LIQUIDITY_BOUNTY_REST_API}", data=data) as resp:
                if resp.status != 200:
                    raise Exception(f"Liquidity bounty server error. Server responded with status {resp.status}")

                results = await resp.json()
                if results["registration_status"] != "success":
                    raise Exception(f"Failed to register for liquidity bounty due to {results['registration_status']}")

        except asyncio.CancelledError:
            raise
        except Exception:
            raise

    async def fetch_bounty_status(self):
        try:
            raise NotImplementedError
        except asyncio.CancelledError:
            raise
        except Exception:
            raise

    async def fetch_bounty_status_loop(self):
        while True:
            try:
                self._status = await self.fetch_bounty_status()
            except Exception as e:
                if "not registered" in str(e):
                    break
                else:
                    await asyncio.sleep(30)

    async def start_network(self):
        await self.stop_network()
        self.fetch_bounty_status_task = asyncio.ensure_future(self.fetch_bounty_status_loop())

    async def stop_network(self):
        if self.fetch_bounty_status_task is not None:
            self.fetch_bounty_status_task.cancel()
            self.fetch_bounty_status_task = None

    async def check_network(self) -> NetworkStatus:
        try:
            loop = asyncio.get_event_loop()
            async with aiohttp.ClientSession(loop=loop,
                                             connector=aiohttp.TCPConnector(verify_ssl=False)) as session:
                async with session.get(self.LIQUIDITY_BOUNTY_REST_API) as resp:
                    if resp.status != 200:
                        raise Exception(f"Liquidity bounty server is down.")
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED



