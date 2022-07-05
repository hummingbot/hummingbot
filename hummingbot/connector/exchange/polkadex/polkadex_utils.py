from decimal import Decimal

from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "PDEX-1"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.002"),
    taker_percent_fee_decimal=Decimal("0.002"),
    buy_percent_fee_deducted_from_returns=True
)

KEYS = {
    "polkadex_seed_phrase":
        ConfigVar(key="polkadex_seed_phrase",
                  prompt="Enter polkadex_seed_phrase>>> ",
                  required_if=using_exchange("polkadex"),
                  is_secure=False,
                  is_connect_key=True),
}