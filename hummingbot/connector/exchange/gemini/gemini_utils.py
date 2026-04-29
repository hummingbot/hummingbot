from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USD"

# Gemini ActiveTrader base-tier fees effective March 13, 2026.
# Higher-volume tiers pay less; actual fill fees from the exchange are used
# for P&L tracking, so these defaults only affect pre-trade estimates.
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.006"),
    taker_percent_fee_decimal=Decimal("0.012"),
    buy_percent_fee_deducted_from_returns=False
)

# Quote currencies Gemini lists pairs against. Order matters for split heuristic:
# longest first to prefer multi-char quotes, but USD-prefixed bases (USDC, GUSD…)
# are peeled separately below to avoid mis-splitting symbols like "usdcusd".
_KNOWN_QUOTES = ("USDT", "USDC", "GUSD", "EUR", "GBP", "SGD", "USD", "BTC", "ETH", "FIL", "JPY", "KRW")
_QUOTES_LONGEST_FIRST = tuple(sorted(_KNOWN_QUOTES, key=len, reverse=True))
# Bases whose ticker contains "USD" — peeled as base before quote matching.
_USD_PREFIX_BASES = ("RLUSD", "PYUSD", "FDUSD", "BUSD", "USDC", "USDT", "GUSD", "PAXG", "FRAX", "LUSD")


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information.
    Gemini returns status "open" for active pairs. Perpetual swaps share base/quote with
    their spot counterparts (e.g. AVAXGUSD vs AVAXGUSDPERP), so we restrict to product_type "spot".
    """
    return (
        exchange_info.get("status", "") == "open"
        and exchange_info.get("product_type", "") == "spot"
    )


def split_gemini_symbol(symbol: str) -> Optional[Tuple[str, str]]:
    """
    Best-effort split of a Gemini symbol string ("btcusd", "usdcusd", "avaxgusd")
    into (base, quote). Used for the bulk /v1/symbols path which only returns names.
    Returns None for symbols that can't be confidently split.
    """
    s = symbol.upper()
    for prefix in _USD_PREFIX_BASES:
        if s.startswith(prefix):
            tail = s[len(prefix):]
            if tail in _KNOWN_QUOTES:
                return prefix, tail
    for q in _QUOTES_LONGEST_FIRST:
        if s.endswith(q) and len(s) - len(q) >= 2:
            return s[: -len(q)], q
    return None


class GeminiConfigMap(BaseConnectorConfigMap):
    connector: str = "gemini"
    gemini_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your Gemini API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    gemini_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your Gemini API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    gemini_account_name: str = Field(
        default="primary",
        json_schema_extra={
            "prompt": lambda cm: "Enter the Gemini account name (only needed for master API keys)",
            "prompt_on_new": False,
        }
    )
    model_config = ConfigDict(title="gemini")


KEYS = GeminiConfigMap.model_construct()

OTHER_DOMAINS = ["gemini_sandbox"]
OTHER_DOMAINS_PARAMETER = {"gemini_sandbox": "gemini_sandbox"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"gemini_sandbox": "BTC-USD"}
OTHER_DOMAINS_DEFAULT_FEES = {"gemini_sandbox": DEFAULT_FEES}


class GeminiSandboxConfigMap(BaseConnectorConfigMap):
    connector: str = "gemini_sandbox"
    gemini_sandbox_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your Gemini Sandbox API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    gemini_sandbox_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your Gemini Sandbox API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    gemini_sandbox_account_name: str = Field(
        default="primary",
        json_schema_extra={
            "prompt": lambda cm: "Enter the Gemini Sandbox account name (only needed for master API keys)",
            "prompt_on_new": False,
        }
    )
    model_config = ConfigDict(title="gemini_sandbox")


OTHER_DOMAINS_KEYS = {"gemini_sandbox": GeminiSandboxConfigMap.model_construct()}
