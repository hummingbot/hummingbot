import os
import tempfile
import unittest
from test.mock.client_session_recorder_utils import (
    ClientSessionRequestMethod,
    ClientSessionRequestType,
    ClientSessionResponseType,
    DatabaseMixin,
)

from sqlalchemy.orm import Session


class TestDatabaseMixin(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_database_mixin(self):
        db_mixin = DatabaseMixin(self.db_path)
        session = db_mixin.get_new_session()
        self.assertIsNotNone(session)
        self.assertIsInstance(session, Session)
        session.close()


class TestEnums(unittest.TestCase):
    def test_client_session_request_method(self):
        self.assertEqual(ClientSessionRequestMethod.POST.value, 1)
        self.assertEqual(ClientSessionRequestMethod.GET.value, 2)
        self.assertEqual(ClientSessionRequestMethod.PUT.value, 3)
        self.assertEqual(ClientSessionRequestMethod.PATCH.value, 4)
        self.assertEqual(ClientSessionRequestMethod.DELETE.value, 5)

    def test_client_session_request_type(self):
        self.assertEqual(ClientSessionRequestType.PLAIN.value, 1)
        self.assertEqual(ClientSessionRequestType.WITH_PARAMS.value, 2)
        self.assertEqual(ClientSessionRequestType.WITH_JSON.value, 3)

    def test_client_session_response_type(self):
        self.assertEqual(ClientSessionResponseType.ERROR.value, 0)
        self.assertEqual(ClientSessionResponseType.HEADER_ONLY.value, 1)
        self.assertEqual(ClientSessionResponseType.WITH_TEXT.value, 2)
        self.assertEqual(ClientSessionResponseType.WITH_JSON.value, 3)


if __name__ == "__main__":
    unittest.main()
