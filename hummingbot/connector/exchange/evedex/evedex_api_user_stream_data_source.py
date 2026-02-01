import asyncio
import logging
import time
from typing import Optional

from eth_account.messages import encode_defunct
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.connector.exchange.evedex.evedex_auth import EvedexAuth
from hummingbot.connector.exchange.evedex import evedex_constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class EvedexAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: EvedexAuth,
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN
    ):
        super().__init__()
        self._auth = auth
        self._api_factory = api_factory
        self._domain = domain
        self._message_id = 1
        self._ws_assistant: Optional[WSAssistant] = None
        self._last_listen_timestamp = 0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @property
    def last_recv_time(self) -> float:
        if self._ws_assistant:
            return self._ws_assistant.last_recv_time
        return 0

    async def listen_for_user_stream(self, output: asyncio.Queue):
        while True:
            try:
                self._ws_assistant = await self._api_factory.get_ws_assistant()
                rest_assistant = await self._api_factory.get_rest_assistant()

                # 1. Authenticate and get Token
                token = await self._get_auth_token(rest_assistant)

                # 2. Connect to WS
                await self._ws_assistant.connect(ws_url=CONSTANTS.WSS_URL, ping_timeout=CONSTANTS.WS_PING_TIMEOUT)

                # 3. Centrifuge Connect with Token
                connect_payload = {
                    "id": self._get_next_message_id(),
                    "method": "connect",
                    "params": {
                        "token": token
                    }
                }
                await self._ws_assistant.send(WSRequest(payload=connect_payload))

                # 4. Subscribe to private channels
                # Assuming channel names pattern based on user ID or just generic private channels
                # Usually "orders" or "account" are user-specific channels handled by the server based on token
                # Evedex SDK suggests specific user channels might be used.
                # For now, subscribing to standard names.
                user_channels = ["orders", "positions", "balance", "fills"]
                for channel in user_channels:
                    subscribe_payload = {
                        "id": self._get_next_message_id(),
                        "method": "subscribe",
                        "params": {
                            "channel": channel
                        }
                    }
                    await self._ws_assistant.send(WSRequest(payload=subscribe_payload))

                await self._process_websocket_messages(output)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error while listening to user stream. Retrying after 5 seconds...")
                await asyncio.sleep(5.0)
            finally:
                if self._ws_assistant and self._ws_assistant.connected:
                    await self._ws_assistant.disconnect()

    async def _get_auth_token(self, rest_assistant: RESTAssistant) -> str:
        # Get Nonce
        # Assuming /auth/nonce endpoint based on common patterns and SDK "authGateway"
        nonce_response = await rest_assistant.execute_request(
            url=f"{CONSTANTS.AUTH_URL}/auth/nonce",
            method=RESTMethod.GET,
        )
        nonce_data = await nonce_response.json()
        nonce = nonce_data.get("nonce")

        # Create SIWE Message
        address = self._auth.get_public_key()
        chain_id = CONSTANTS.CHAIN_ID
        domain = "evedex.com"
        uri = "https://evedex.com"
        statement = "Sign in to evedex.com"
        issued_at = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

        # Format matches SiweMessage (EIP-4361)
        message = f"""{domain} wants you to sign in with your Ethereum account:
{address}

{statement}

URI: {uri}
Version: 1
Chain ID: {chain_id}
Nonce: {nonce}
Issued At: {issued_at}"""

        # Sign Message
        # eth_account sign_message handles the prefix automatically
        signed_message = self._auth._account.sign_message(encode_defunct(text=message))
        signature = signed_message.signature.hex()

        # Login
        login_payload = {
            "wallet": address,
            "message": message,
            "nonce": nonce,
            "signature": signature
        }

        login_response = await rest_assistant.execute_request(
            url=f"{CONSTANTS.AUTH_URL}/auth/signin",
            method=RESTMethod.POST,
            data=login_payload
        )
        login_data = await login_response.json()
        return login_data.get("token") or login_data.get("accessToken")

    async def _process_websocket_messages(self, output: asyncio.Queue):
        async for ws_response in self._ws_assistant.iter_messages():
            data = ws_response.data

            if data == {}:
                await self._ws_assistant.send(WSRequest(payload={}))
                continue

            if "push" in data:
                push = data["push"]
                # channel = push.get("channel", "")  # Unused variable
                pub = push.get("pub", {})
                content = pub.get("data", {})

                output.put_nowait(content)

    def _get_next_message_id(self) -> int:
        mid = self._message_id
        self._message_id += 1
        return mid
