from decimal import Decimal
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Connector classification — KalqiX is an order-book DEX but Hummingbot's CEX
# connector model fits the surface (API key + HMAC, REST/WS, single-pair
# limit/market orders). CENTRALIZED=True hides DEX-specific UI knobs the user
# doesn't need.
CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDC"

# Conservative defaults; the connector reads the actual fees from
# `/markets/{ticker}` on every order placement.
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.001"),
    buy_percent_fee_deducted_from_returns=True,
)

# ---------------------------------------------------------------------------
# Trading-pair conversion
# ---------------------------------------------------------------------------
# KalqiX uses two ticker conventions on the same wire:
#   - URLs / query params:     BTC_USDC  (underscore)
#   - Request bodies / fields: BTC/USDC  (slash)
# Hummingbot expects pairs in BASE-QUOTE form (`BTC-USDC`). Translate at the
# connector boundary so the rest of the framework never sees KalqiX's dual
# convention.


def convert_to_exchange_ticker_path(hb_trading_pair: str) -> str:
    """`BTC-USDC` → `BTC_USDC` (URL form)."""
    return hb_trading_pair.replace("-", "_")


def convert_to_exchange_ticker_body(hb_trading_pair: str) -> str:
    """`BTC-USDC` → `BTC/USDC` (body form)."""
    return hb_trading_pair.replace("-", "/")


def convert_from_exchange_trading_pair(exchange_ticker: str) -> str:
    """`BTC/USDC` or `BTC_USDC` → `BTC-USDC` (Hummingbot form)."""
    return exchange_ticker.replace("/", "-").replace("_", "-")


# ---------------------------------------------------------------------------
# Exchange info validation
# ---------------------------------------------------------------------------

def is_exchange_information_valid(market: Dict[str, Any]) -> bool:
    """Filter for the markets/exchange-info response — only ACTIVE markets are tradable."""
    return market.get("status") == "ACTIVE"


# ---------------------------------------------------------------------------
# Config map — what the user enters on `connect kalqix`
# ---------------------------------------------------------------------------
# Two credentials are required for headless trading:
#   1. api_key + api_secret           — transport HMAC (per-request)
#   2. agent_index + agent_private_key — per-order Schnorr signing
#
# The user mints these once in the KalqiX UI.

class KalqixConfigMap(BaseConnectorConfigMap):
    connector: str = "kalqix"
    kalqix_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your KalqiX API key (api_key from PUT /v1/api-keys)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    kalqix_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your KalqiX API secret (api_secret, shown once)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    kalqix_agent_index: int = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter the agent-wallet slot index (export pool: 6..255)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    kalqix_agent_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter the agent-wallet private key (32-byte hex, shown once)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    model_config = ConfigDict(title="kalqix")


KEYS = KalqixConfigMap.model_construct()


# Sibling connector `kalqix_testnet` — Hummingbot's OTHER_DOMAINS framework hook
# routes domain_parameter="testnet" into KalqixExchange.__init__, which makes
# kalqix_constants.rest_url() return https://testnet-api.kalqix.com/v1.
class KalqixTestnetConfigMap(KalqixConfigMap):
    connector: str = "kalqix_testnet"
    model_config = ConfigDict(title="kalqix_testnet")


OTHER_DOMAINS = ["kalqix_testnet"]
OTHER_DOMAINS_PARAMETER = {"kalqix_testnet": "testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"kalqix_testnet": EXAMPLE_PAIR}
OTHER_DOMAINS_DEFAULT_FEES = {"kalqix_testnet": DEFAULT_FEES}
OTHER_DOMAINS_KEYS = {"kalqix_testnet": KalqixTestnetConfigMap.model_construct()}
