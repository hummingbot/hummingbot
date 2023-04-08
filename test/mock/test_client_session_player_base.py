import os
import tempfile
import unittest
from test.mock.client_session_context_mixin import ClientSessionContextMixin
from test.mock.client_session_player_base import ClientSessionPlayerBase
from test.mock.client_session_recorder_utils import DatabaseMixin


class TestClientSessionPlayerBase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_client_session_player_base(self):
        player_base = ClientSessionPlayerBase(self.db_path)
        self.assertIsInstance(player_base, DatabaseMixin)
        self.assertIsInstance(player_base, ClientSessionContextMixin)


if __name__ == "__main__":
    unittest.main()
