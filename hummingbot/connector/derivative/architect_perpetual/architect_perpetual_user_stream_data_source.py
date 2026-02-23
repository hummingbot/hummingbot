from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional

from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_derivative import ArchitectPerpetualDerivative


class ArchitectPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth,
        connector: 'ArchitectPerpetualDerivative',
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__()
        self._auth = auth
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._ws: Optional[WSAssistant] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = HummingbotLogger.logger_name_for_class(cls)
        return cls._logger

    async def listen_for_user_stream(self, output: asyncio.Queue):
        while True:
            try:
                self._ws = await self._api_factory.get_ws_assistant()
                await self._ws.connect(ws_url=self._connector.web_utils.private_ws_url(self._domain), ping_timeout=30)

                # Depending on the exchange, a login/auth message may be needed.
                # WebAssistantsFactory will call AuthBase.ws_authenticate for WSRequest objects.
                # Here we send a generic auth payload.
                from hummingbot.core.web_assistant.connections.data_types import WSRequest

                auth_req = WSRequest(payload={"op": "auth"}, is_auth_required=True)
                auth_req = await self._auth.ws_authenticate(auth_req)
                await self._ws.send(auth_req.payload)

                while True:
                    msg = await self._ws.receive()
                    if msg is None:
                        continue
                    await output.put(msg)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener. Retrying...")
                await asyncio.sleep(5)
