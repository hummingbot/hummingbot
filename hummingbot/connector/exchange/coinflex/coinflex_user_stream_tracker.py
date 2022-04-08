import logging
from typing import Optional

import hummingbot.connector.exchange.coinflex.coinflex_constants as CONSTANTS
from hummingbot.connector.exchange.coinflex.coinflex_api_user_stream_data_source import CoinflexAPIUserStreamDataSource
from hummingbot.connector.exchange.coinflex.coinflex_auth import CoinflexAuth
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger


class CoinflexUserStreamTracker(UserStreamTracker):
    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: CoinflexAuth,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 throttler: Optional[AsyncThrottler] = None,
                 api_factory: Optional[WebAssistantsFactory] = None):
        self._auth: CoinflexAuth = auth
        self._domain = domain
        self._throttler = throttler
        self._api_factory = api_factory
        super().__init__(
            data_source=CoinflexAPIUserStreamDataSource(
                auth=self._auth,
                domain=self._domain,
                throttler=self._throttler,
                api_factory=self._api_factory
            ))

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger
