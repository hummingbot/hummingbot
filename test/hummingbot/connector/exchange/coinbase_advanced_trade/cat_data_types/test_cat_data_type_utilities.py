import unittest
from datetime import datetime, timezone
from typing import Optional, TypeVar

from pydantic.fields import Field
from pydantic.main import BaseModel

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_data_types_utilities import (
    UnixTimestampSecondFieldToDatetime,
    UnixTimestampSecondFieldToFloat,
    UnixTimestampSecondFieldToStr,
    _max_timestamp,
    _min_timestamp,
)

T = TypeVar('T')


class UnixTimestampSecondFieldTests(unittest.TestCase):
    class TestModel(BaseModel):
        timestamp: Optional[UnixTimestampSecondFieldToFloat] = Field(None, description="Unix timestamp in seconds.")

    class TestModelStr(BaseModel):
        timestamp: Optional[UnixTimestampSecondFieldToStr] = Field(None, description="Unix timestamp in seconds.")

    class TestModelDatetime(BaseModel):
        timestamp: Optional[UnixTimestampSecondFieldToDatetime] = Field(None, description="Unix timestamp in seconds.")

    def test_unix_timestamp_field_behavior_as_float(self):
        # Instantiate TestModel without providing a value for UnixTimestampSecondField
        model = self.TestModel()
        self.assertIsNone(model.timestamp)
        self.assertEqual({'timestamp': None}, model.dict())
        self.assertEqual('{"timestamp": null}', model.json())

        # Instantiate TestModel with UnixTimestampSecondField
        model = self.TestModel(timestamp=1609459200)
        print(repr(model))
        self.assertEqual(1609459200.0, model.timestamp)
        self.assertEqual({"timestamp": 1609459200.0}, model.dict())
        self.assertEqual('{"timestamp": 1609459200.0}', model.json())

    def test_unix_timestamp_field_behavior_as_datetime(self):
        # Instantiate TestModel without providing a value for UnixTimestampSecondField
        model = self.TestModel()
        self.assertIsNone(model.timestamp)
        self.assertEqual({'timestamp': None}, model.dict())
        self.assertEqual('{"timestamp": null}', model.json())

        # Instantiate TestModel with UnixTimestampSecondField
        model = self.TestModelDatetime(timestamp=1609459200)
        self.assertEqual("2021-01-01 00:00:00+00:00", str(model.timestamp))
        self.assertEqual('{"timestamp": "2021-01-01T00:00:00+00:00"}', model.json())
        self.assertEqual({"timestamp": datetime(2021, 1, 1, 0, 0, tzinfo=timezone.utc)}, model.dict())

    def test_unix_timestamp_field_behavior_as_str(self):
        # Instantiate TestModel without providing a value for UnixTimestampSecondField
        model = self.TestModelStr()
        self.assertIsNone(model.timestamp)
        self.assertEqual({'timestamp': None}, model.dict())
        self.assertEqual('{"timestamp": null}', model.json())

        # Instantiate TestModel with UnixTimestampSecondField
        model = self.TestModelStr(timestamp=1609459200)
        self.assertEqual("1609459200.0", model.timestamp)
        self.assertEqual({"timestamp": "1609459200.0"}, model.dict())
        self.assertEqual('{"timestamp": "1609459200.0"}', model.json())

    def test_invalid_timestamp_exceeds_current_time(self):
        self.TestModel(timestamp=_max_timestamp)
        with self.assertRaises(ValueError):
            self.TestModel(timestamp=_max_timestamp + 1)

    def test_invalid_timestamp_older_than_2000(self):
        self.TestModel(timestamp=_min_timestamp)
        with self.assertRaises(ValueError):
            self.TestModelStr(timestamp=_min_timestamp - 1)

    def test_str_with_extra_decimals(self):
        field = self.TestModel(timestamp='1609459200.123456')
        self.assertEqual(field.timestamp, 1609459200.123456)

    def test_str_with_missing_decimals(self):
        field = self.TestModel(timestamp='1609459200.1')
        self.assertEqual(field.timestamp, 1609459200.1)

    def test_str_truncated_microseconds(self):
        field = self.TestModel(timestamp='2021-01-01T00:00:00.123456789Z')
        self.assertEqual(field.timestamp, 1609459200.123456)


if __name__ == '__main__':
    unittest.main()
