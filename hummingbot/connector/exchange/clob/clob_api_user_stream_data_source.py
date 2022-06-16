from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class CLOBAPIUserStreamDataSource(UserStreamTrackerDataSource):

    async def _connected_websocket_assistant(self) -> WSAssistant:
        # TODO do we need to override this method?!!!
        raise NotImplementedError

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        # TODO do we need to override this method?!!!
        raise NotImplementedError
