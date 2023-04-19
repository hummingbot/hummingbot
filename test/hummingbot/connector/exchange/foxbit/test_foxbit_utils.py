import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

from hummingbot.connector.exchange.foxbit import foxbit_utils as utils
from hummingbot.core.data_type.in_flight_order import OrderState


class FoxbitUtilTestCases(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.hb_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"

    def test_is_exchange_information_valid(self):
        valid_info = {
            "status": "TRADING",
            "permissions": ["SPOT"],
        }
        self.assertTrue(utils.is_exchange_information_valid(valid_info))

    def test_get_client_order_id(self):
        now = 1234567890.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now

        retValue = utils.get_client_order_id(True)
        self.assertLess(retValue, utils.get_client_order_id(True))
        retValue = utils.get_client_order_id(False)
        self.assertLess(retValue, utils.get_client_order_id(False))

    def test_get_ws_message_frame(self):
        _msg_A = utils.get_ws_message_frame('endpoint_A')
        _msg_B = utils.get_ws_message_frame('endpoint_B')
        self.assertEqual(_msg_A['m'], _msg_B['m'])
        self.assertNotEqual(_msg_A['n'], _msg_B['n'])
        self.assertLess(_msg_A['i'], _msg_B['i'])

    def test_ws_data_to_dict(self):
        _expectedValue = [{'Key': 'field0', 'Value': 'Google'}, {'Key': 'field2', 'Value': None}, {'Key': 'field3', 'Value': 'São Paulo'}, {'Key': 'field4', 'Value': False}, {'Key': 'field5', 'Value': 'SAO PAULO'}, {'Key': 'field6', 'Value': '00000001'}, {'Key': 'field7', 'Value': True}]
        _msg = '[{"Key":"field0","Value":"Google"},{"Key":"field2","Value":null},{"Key":"field3","Value":"São Paulo"},{"Key":"field4","Value":false},{"Key":"field5","Value":"SAO PAULO"},{"Key":"field6","Value":"00000001"},{"Key":"field7","Value":true}]'
        _retValue = utils.ws_data_to_dict(_msg)
        self.assertEqual(_expectedValue, _retValue)

    def test_datetime_val_or_now(self):
        self.assertIsNone(utils.datetime_val_or_now('NotValidDate', '', False))
        self.assertLessEqual(datetime.now(), utils.datetime_val_or_now('NotValidDate', '', True))
        self.assertLessEqual(datetime.now(), utils.datetime_val_or_now('NotValidDate', ''))
        _now = '2023-04-19T18:53:17.981Z'
        _fNow = datetime.strptime(_now, '%Y-%m-%dT%H:%M:%S.%fZ')
        self.assertEqual(_fNow, utils.datetime_val_or_now(_now))

    def test_decimal_val_or_none(self):
        self.assertIsNone(utils.decimal_val_or_none('NotValidDecimal'))
        self.assertIsNone(utils.decimal_val_or_none('NotValidDecimal', True))
        self.assertEqual(0, utils.decimal_val_or_none('NotValidDecimal', False))
        _dec = '2023.0419'
        self.assertEqual(Decimal(_dec), utils.decimal_val_or_none(_dec))

    def test_int_val_or_none(self):
        self.assertIsNone(utils.int_val_or_none('NotValidInt'))
        self.assertIsNone(utils.int_val_or_none('NotValidInt', True))
        self.assertEqual(0, utils.int_val_or_none('NotValidInt', False))
        _dec = '2023'
        self.assertEqual(2023, utils.int_val_or_none(_dec))

    def test_get_order_state(self):
        self.assertIsNone(utils.get_order_state('NotValidOrderState'))
        self.assertIsNone(utils.get_order_state('NotValidOrderState', False))
        self.assertEqual(OrderState.FAILED, utils.get_order_state('NotValidOrderState', True))
        self.assertEqual(OrderState.PENDING_CREATE, utils.get_order_state('PENDING'))
        self.assertEqual(OrderState.OPEN, utils.get_order_state('ACTIVE'))
        self.assertEqual(OrderState.OPEN, utils.get_order_state('NEW'))
        self.assertEqual(OrderState.FILLED, utils.get_order_state('FILLED'))
        self.assertEqual(OrderState.PARTIALLY_FILLED, utils.get_order_state('PARTIALLY_FILLED'))
        self.assertEqual(OrderState.OPEN, utils.get_order_state('PENDING_CANCEL'))
        self.assertEqual(OrderState.CANCELED, utils.get_order_state('CANCELED'))
        self.assertEqual(OrderState.PARTIALLY_FILLED, utils.get_order_state('PARTIALLY_CANCELED'))
        self.assertEqual(OrderState.FAILED, utils.get_order_state('REJECTED'))
        self.assertEqual(OrderState.FAILED, utils.get_order_state('EXPIRED'))
        self.assertEqual(OrderState.PENDING_CREATE, utils.get_order_state('Unknown'))
        self.assertEqual(OrderState.OPEN, utils.get_order_state('Working'))
        self.assertEqual(OrderState.FAILED, utils.get_order_state('Rejected'))
        self.assertEqual(OrderState.CANCELED, utils.get_order_state('Canceled'))
        self.assertEqual(OrderState.FAILED, utils.get_order_state('Expired'))
        self.assertEqual(OrderState.FILLED, utils.get_order_state('FullyExecuted'))

    def test_get_base_quote_from_trading_pair(self):
        base, quote = utils.get_base_quote_from_trading_pair('')
        self.assertEqual('', base)
        self.assertEqual('', quote)
        base, quote = utils.get_base_quote_from_trading_pair('ALPHACOIN')
        self.assertEqual('', base)
        self.assertEqual('', quote)
        base, quote = utils.get_base_quote_from_trading_pair('ALPHA_COIN')
        self.assertEqual('', base)
        self.assertEqual('', quote)
        base, quote = utils.get_base_quote_from_trading_pair('ALPHA/COIN')
        self.assertEqual('', base)
        self.assertEqual('', quote)
        base, quote = utils.get_base_quote_from_trading_pair('alpha-coin')
        self.assertEqual('ALPHA', base)
        self.assertEqual('COIN', quote)
        base, quote = utils.get_base_quote_from_trading_pair('ALPHA-COIN')
        self.assertEqual('ALPHA', base)
        self.assertEqual('COIN', quote)
