from decimal import Decimal

from pydantic import ConfigDict, Field

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = False

EXAMPLE_PAIR = "SOL-PERP"

# Drift perpetual taker fee tier base is ~0.10% with a maker rebate at the
# top tier; conservative defaults below are refined from /v2/marginInfo +
# the live fee schedule during integration testing (the generic test base
# only checks fee *plumbing*, not the absolute rate).
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0000"),
    taker_percent_fee_decimal=Decimal("0.0010"),
)


class DriftPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "drift_perpetual"

    # Drift uses a self-hosted gateway that holds the Solana keypair
    # (DRIFT_GATEWAY_KEY env, set when the operator launches the gateway).
    # The connector therefore does NOT take a private key — it takes the
    # gateway connection parameters + the sub-account to trade.
    drift_perpetual_gateway_host: str = Field(
        default="127.0.0.1",
        json_schema_extra={
            "prompt": "Enter the Drift Gateway host (default 127.0.0.1)",
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    drift_perpetual_gateway_rest_port: int = Field(
        default=8080,
        json_schema_extra={
            "prompt": "Enter the Drift Gateway REST port (default 8080)",
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    drift_perpetual_gateway_ws_port: int = Field(
        default=1337,
        json_schema_extra={
            "prompt": "Enter the Drift Gateway WS port (default 1337)",
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    drift_perpetual_sub_account_id: int = Field(
        default=0,
        json_schema_extra={
            "prompt": "Enter the Drift sub-account id to trade (default 0)",
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    model_config = ConfigDict(title="drift_perpetual")


KEYS = DriftPerpetualConfigMap.model_construct()
