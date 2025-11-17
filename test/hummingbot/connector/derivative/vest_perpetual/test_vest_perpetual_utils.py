from decimal import Decimal

from pydantic import SecretStr

from hummingbot.connector.derivative.vest_perpetual.vest_perpetual_utils import (
    DEFAULT_FEES,
    KEYS,
    VestPerpetualConfigMap,
    convert_from_exchange_trading_pair,
    convert_to_exchange_trading_pair,
)


def test_symbol_conversions_are_identity():
    pair = "BTC-PERP"
    assert convert_to_exchange_trading_pair(pair) == pair
    assert convert_from_exchange_trading_pair(pair) == pair


def test_default_fees_schema_contains_precise_decimals():
    assert DEFAULT_FEES.maker_percent_fee_decimal == Decimal("0.0001")
    assert DEFAULT_FEES.taker_percent_fee_decimal == Decimal("0.0001")


def test_config_keys_include_required_fields():
    config = VestPerpetualConfigMap.construct(
        vest_perpetual_api_key=SecretStr("key"),
        vest_perpetual_signing_key=SecretStr("sign"),
        vest_perpetual_account_group=1,
        vest_perpetual_use_testnet=False,
    )
    assert config.vest_perpetual_api_key.get_secret_value() == "key"
    assert KEYS.connector == "vest_perpetual"
