from test.mock.client_session_context_mixin import ClientSessionContextMixin
from test.mock.client_session_recorder_utils import DatabaseMixin


class ClientSessionPlayerBase(DatabaseMixin, ClientSessionContextMixin):
    """
    A base class for recording and replaying HTTP conversations using an aiohttp.ClientSession object.

    This class extends the `DatabaseMixin` and `ClientSessionContextMixin` classes to provide the functionality
    required for recording and replaying HTTP conversations.

    Attributes:
    -----------
    db_path: str
        The path to the SQLite database to use for storing HTTP conversations.

    Methods:
    --------
    __init__(self, db_path: str)
        Constructs a new `ClientSessionPlayerBase` instance.

    async def __aenter__(self, *client_args, **client_kwargs) -> Any:
        Enter the context of this `ClientSessionPlayerBase` instance and return an asyncio task.

    async def __aexit__(self, *args, **kwargs) -> None:
        Exit the context of this `ClientSessionPlayerBase` instance.

    """

    def __init__(self, db_path: str):
        DatabaseMixin.__init__(self, db_path)
        ClientSessionContextMixin.__init__(self)
