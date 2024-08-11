# DISABLE SELECT PYLINT TESTS
# pylint: disable=bad-continuation, no-member, broad-except
"""
 ╔════════════════════════════════════════════════════╗
 ║ ╔═╗╦═╗╔═╗╔═╗╦ ╦╔═╗╔╗╔╔═╗  ╔╦╗╔═╗╔╦╗╔═╗╔╗╔╔═╗╔╦╗╔═╗ ║
 ║ ║ ╦╠╦╝╠═╣╠═╝╠═╣║╣ ║║║║╣   ║║║║╣  ║ ╠═╣║║║║ ║ ║║║╣  ║
 ║ ╚═╝╩╚═╩ ╩╩  ╩ ╩╚═╝╝╚╝╚═╝  ╩ ╩╚═╝ ╩ ╩ ╩╝╚╝╚═╝═╩╝╚═╝ ║
 ║    DECENTRALIZED EXCHANGE HUMMINGBOT CONNECTOR     ║
 ╚════════════════════════════════════════════════════╝
~
forked from binance_user_stream_tracker v1.0.0
~
"""
# STANDARD MODULES
import asyncio
import logging
from typing import Optional

# METANODE MODULES
from metanode.graphene_metanode_client import GrapheneTrustlessClient

# HUMMINGBOT MODULES
from hummingbot.connector.exchange.graphene.graphene_api_user_stream_data_source import GrapheneAPIUserStreamDataSource
from hummingbot.connector.exchange.graphene.graphene_constants import GrapheneConstants
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger


class GrapheneUserStreamTracker(UserStreamTracker):
    """
    tracks fill orders, open orders, created orders, and cancelled orders
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(self, domain: str, order_tracker: UserStreamTracker, *_, **__):
        # ~ print("GrapheneUserStreamTracker")
        super().__init__(GrapheneAPIUserStreamDataSource(domain=domain, order_tracker=order_tracker))
        self._ev_loop: asyncio.events.AbstractEventLoop = asyncio.get_event_loop()
        self._data_source: Optional[UserStreamTrackerDataSource] = None
        self._user_stream_tracking_task: Optional[asyncio.Task] = None
        self._order_tracker = order_tracker
        self.domain = domain
        self.constants = GrapheneConstants(domain)
        self.metanode = GrapheneTrustlessClient(self.constants)

    @classmethod
    def logger(cls) -> HummingbotLogger:
        """
        a classmethod for logging
        """
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        """
        Returns the instance of the data source that listens to the private user channel
        to receive updates from the DEX. If the instance is not initialized it will
        be created.
        :return: the user stream instance that is listening to user updates
        """
        # ~ print("GrapheneUserStreamTracker data_source")
        if not self._data_source:
            self._data_source = GrapheneAPIUserStreamDataSource(
                domain=self.domain, order_tracker=self._order_tracker
            )
        return self._data_source

    async def start(self):
        """
        Starts the background task that connects to the DEX
        and listens to user activity updates
        """
        # ~ print("GrapheneUserStreamTracker start")
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._ev_loop, self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
