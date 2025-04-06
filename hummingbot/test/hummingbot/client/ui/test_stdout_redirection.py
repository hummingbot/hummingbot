import unittest

from hummingbot.client.ui.stdout_redirection import StdoutProxy


class StdoutProxyTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.stdout_proxy = StdoutProxy()

    def test_isatty(self):
        self.assertFalse(self.stdout_proxy.isatty())

    def test_fileno(self):
        self.assertEqual(1, self.stdout_proxy.fileno())
