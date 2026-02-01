from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource


class EvedexUserStreamTracker(UserStreamTracker):
    def __init__(
        self,
        data_source: UserStreamTrackerDataSource,
        user_stream_tracker_data_source: UserStreamTrackerDataSource = None
    ):
        super().__init__(data_source=data_source, user_stream_tracker_data_source=user_stream_tracker_data_source)

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        return self._data_source

    @property
    def exchange_name(self) -> str:
        return "evedex"
