from unittest import TestCase
from unittest.mock import patch

from hummingbot.core.utils.tracking_nonce import NonceCreator


class NonceCreatorTests(TestCase):

    @patch("hummingbot.core.utils.tracking_nonce.NonceCreator._time")
    def test_create_seconds_precision_nonce_from_machine_time(self, time_mock):
        time_mock.return_value = 1112223334.445556
        nonce_creator = NonceCreator.for_seconds()

        nonce = nonce_creator.get_tracking_nonce()
        self.assertEqual(int(time_mock.return_value), nonce)

    @patch("hummingbot.core.utils.tracking_nonce.NonceCreator._time")
    def test_create_milliseconds_precision_nonce_from_machine_time(self, time_mock):
        time_mock.return_value = 1112223334.445556
        nonce_creator = NonceCreator.for_milliseconds()

        nonce = nonce_creator.get_tracking_nonce()
        self.assertEqual(int(time_mock.return_value * 1e3), nonce)

    @patch("hummingbot.core.utils.tracking_nonce.NonceCreator._time")
    def test_create_microseconds_precision_nonce_from_machine_time(self, time_mock):
        time_mock.return_value = 1112223334.445556
        nonce_creator = NonceCreator.for_microseconds()

        nonce = nonce_creator.get_tracking_nonce()
        self.assertEqual(int(time_mock.return_value * 1e6), nonce)

    def test_create_seconds_precision_nonce_from_parameter(self):
        timestamp = 1112223334.445556
        nonce_creator = NonceCreator.for_seconds()

        nonce = nonce_creator.get_tracking_nonce(timestamp=timestamp)
        self.assertEqual(int(timestamp), nonce)

    def test_create_milliseconds_precision_nonce_from_parameter(self):
        timestamp = 1112223334.445556
        nonce_creator = NonceCreator.for_milliseconds()

        nonce = nonce_creator.get_tracking_nonce(timestamp=timestamp)
        self.assertEqual(int(timestamp * 1e3), nonce)

    def test_create_microseconds_precision_nonce_from_parameter(self):
        timestamp = 1112223334.445556
        nonce_creator = NonceCreator.for_microseconds()

        nonce = nonce_creator.get_tracking_nonce(timestamp=timestamp)
        self.assertEqual(int(timestamp * 1e6), nonce)

    @patch("hummingbot.core.utils.tracking_nonce.NonceCreator._time")
    def test_nonce_from_machine_time_is_not_repeated(self, time_mock):
        time_mock.return_value = 1112223334.445556
        nonce_creator = NonceCreator.for_seconds()

        first_nonce = nonce_creator.get_tracking_nonce()
        second_nonce = nonce_creator.get_tracking_nonce()
        self.assertEqual(second_nonce, first_nonce + 1)

    def test_nonce_from_same_base_number_is_not_repeated(self):
        nonce_creator = NonceCreator.for_seconds()

        first_nonce = nonce_creator.get_tracking_nonce(timestamp=1234567890)
        second_nonce = nonce_creator.get_tracking_nonce(timestamp=1234567890)
        self.assertEqual(second_nonce, first_nonce + 1)
