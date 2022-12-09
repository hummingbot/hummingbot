from unittest import TestCase
from unittest.mock import MagicMock, patch

from hummingbot.notifier.telegram_notifier import TelegramNotifier


class TelegramNotifierTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.app = MagicMock()
        self.telegram = TelegramNotifier(token="000:token", chat_id="", hb=None)

    @patch("telegram.ext.Updater.stop")
    @patch("telegram.ext.Updater.start_polling")
    def test_start_after_stop(self, start_polling: MagicMock, stop: MagicMock):
        self.telegram.start()
        start_polling.assert_called_once()
        start_polling.reset_mock()
        self.telegram.stop()
        stop.assert_called_once()
        self.telegram.start()
        start_polling.assert_called_once()
