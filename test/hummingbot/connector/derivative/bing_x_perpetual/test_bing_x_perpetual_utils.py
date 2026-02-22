import gzip
import io
import json
import sys
import time
from decimal import Decimal
from unittest import TestCase
from unittest.mock import MagicMock

# Mock hummingbot modules
_mocked_modules = [
    'hummingbot', 'hummingbot.core', 'hummingbot.core.data_type',
    'hummingbot.core.data_type.trade_fee', 'hummingbot.client',
    'hummingbot.client.config', 'hummingbot.client.config.config_data_types',
    'hummingbot.connector', 'hummingbot.connector.derivative',
    'hummingbot.connector.derivative.bing_x_perpetual',
    'pydantic',
]
for mod in _mocked_modules:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

# Mock TradeFeeSchema to capture constructor args
class FakeTradeFeeSchema:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

sys.modules['hummingbot.core.data_type.trade_fee'].TradeFeeSchema = FakeTradeFeeSchema

# Mock pydantic classes
class FakeField:
    def __call__(self, **kwargs):
        return None
sys.modules['pydantic'].Field = FakeField()
sys.modules['pydantic'].ConfigDict = lambda **kw: {}
sys.modules['pydantic'].SecretStr = str

# Mock BaseConnectorConfigMap
class FakeBaseConfig:
    @classmethod
    def model_construct(cls):
        return cls()
sys.modules['hummingbot.client.config.config_data_types'].BaseConnectorConfigMap = FakeBaseConfig

import importlib, os
spec_path = os.path.join(os.path.dirname(__file__), '..', 'bing_x_perpetual', 'bing_x_perpetual_utils.py')
spec = importlib.util.spec_from_file_location("bing_x_perpetual_utils", spec_path)
utils_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(utils_module)


class TestBingXPerpetualUtils(TestCase):

    def test_trading_pair_conversion_btc_usdt(self):
        self.assertEqual(utils_module.get_trading_pair_from_exchange_symbol("BTC-USDT"), "BTC-USDT")

    def test_trading_pair_conversion_eth_usdt(self):
        self.assertEqual(utils_module.get_exchange_symbol_from_trading_pair("ETH-USDT"), "ETH-USDT")

    def test_round_trip_conversion(self):
        pair = "SOL-USDT"
        self.assertEqual(
            utils_module.get_trading_pair_from_exchange_symbol(
                utils_module.get_exchange_symbol_from_trading_pair(pair)), pair)

    def test_is_exchange_information_valid_with_valid_data(self):
        self.assertTrue(utils_module.is_exchange_information_valid({"status": 1}))

    def test_is_exchange_information_valid_missing_fields(self):
        self.assertFalse(utils_module.is_exchange_information_valid({}))

    def test_is_exchange_information_valid_wrong_status(self):
        self.assertFalse(utils_module.is_exchange_information_valid({"status": 0}))

    def test_fee_schema_maker(self):
        self.assertEqual(utils_module.DEFAULT_FEES.maker_percent_fee_decimal, Decimal("0.0002"))

    def test_fee_schema_taker(self):
        self.assertEqual(utils_module.DEFAULT_FEES.taker_percent_fee_decimal, Decimal("0.0005"))

    def test_fee_schema_buy_deducted(self):
        self.assertTrue(utils_module.DEFAULT_FEES.buy_percent_fee_deducted_from_returns)

    def test_decompress_ws_message_bytes(self):
        data = {"test": "value"}
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode='wb') as f:
            f.write(json.dumps(data).encode('utf-8'))
        compressed = buf.getvalue()
        result = utils_module.decompress_ws_message(compressed)
        self.assertEqual(result, data)

    def test_decompress_ws_message_passthrough(self):
        data = {"already": "decoded"}
        result = utils_module.decompress_ws_message(data)
        self.assertEqual(result, data)

    def test_decompress_ws_message_string_passthrough(self):
        result = utils_module.decompress_ws_message("hello")
        self.assertEqual(result, "hello")

    def test_get_next_funding_time_is_future(self):
        result = utils_module.get_next_funding_time()
        self.assertGreater(result, time.time())

    def test_get_next_funding_time_is_8h_aligned(self):
        result = utils_module.get_next_funding_time()
        hour = int(result // 3600) % 24
        self.assertIn(hour, [0, 8, 16])

    def test_example_pair(self):
        self.assertEqual(utils_module.EXAMPLE_PAIR, "BTC-USDT")

    def test_centralized(self):
        self.assertTrue(utils_module.CENTRALIZED)
