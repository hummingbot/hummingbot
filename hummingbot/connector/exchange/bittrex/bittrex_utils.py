from decimal import Decimal

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True

EXAMPLE_PAIR = "ZRX-ETH"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0035"),
    taker_percent_fee_decimal=Decimal("0.0035"),
)

KEYS = {
    "bittrex_api_key":
        ConfigVar(key="bittrex_api_key",
                  prompt="Enter your Bittrex API key >>> ",
                  required_if=using_exchange("bittrex"),
                  is_secure=True,
                  is_connect_key=True),
    "bittrex_secret_key":
        ConfigVar(key="bittrex_secret_key",
                  prompt="Enter your Bittrex secret key >>> ",
                  required_if=using_exchange("bittrex"),
                  is_secure=True,
                  is_connect_key=True),
}
