import unittest

from hummingbot.connector.connector_status import get_connector_status


class ConnectorStatusTestCase(unittest.TestCase):

    def test_unknown_connector(self):
        connector_name = 'unknown_connector'
        expected_status = 'UNKNOWN'
        actual_status = get_connector_status(connector_name)
        self.assertEqual(actual_status, expected_status)

    def test_red_connector(self):
        connector_name = 'bitmex'
        expected_status = '&cBRONZE'
        actual_status = get_connector_status(connector_name)
        self.assertEqual(actual_status, expected_status)

    def test_yellow_connector(self):
        connector_name = 'kucoin'
        expected_status = '&cSILVER'
        actual_status = get_connector_status(connector_name)
        self.assertEqual(actual_status, expected_status)

    def test_green_connector(self):
        connector_name = 'binance'
        expected_status = '&cGOLD'
        actual_status = get_connector_status(connector_name)
        self.assertEqual(actual_status, expected_status)


if __name__ == '__main__':
    unittest.main()
