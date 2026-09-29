"""
Derive spot connector configuration.

Setting up an account on the v3 API
-----------------------------------
v3 settles on Ethereum L1 (mainnet) and Sepolia (testnet) rather than the old Derive L2.

1. Create the account by depositing on L1. v3 removed ``private/create_subaccount``, so there is
   no API call that creates one; the deposit does it.
2. Register a **scoped** session key at derive.xyz. v3 session keys carry a scope, an expiry and
   optionally a subaccount allow-list and an IP allow-list. Spot trading needs
   ``trade:orderbook:spot`` (4) or ``trade:orderbook:all`` (3), plus the off-chain
   ``account_info`` scope so balances and orders can be read.
3. The key's expiry has to outlast the signatures the connector produces. Signatures are valid
   for SIGNATURE_VALIDITY_SEC (one hour by default); a shorter-lived key is rejected with 14038.

Errors 14026 (key not registered), 14030 (expired) and 14031 (scope does not permit the action)
are reported with that guidance attached.

Existing v2 users are migrating, not upgrading: funds move to L1, and a new session key is
needed because the v2 key is not valid against the v3 domain separator.
"""

from decimal import Decimal

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Maker rebates(-0.02%) are paid out continuously on each trade directly to the trading wallet.(https://derive.gitbook.io/derive-docs/trading/fees)
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0015"),
    taker_percent_fee_decimal=Decimal("0.0015"),
    buy_percent_fee_deducted_from_returns=True
)

CENTRALIZED = False

EXAMPLE_PAIR = "OP-USDC"

BROKER_ID = "HBOT"


class DeriveConfigMap(BaseConnectorConfigMap):
    connector: str = "derive"
    derive_wallet_address: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Derive Wallet address",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    session_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your session private key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    subacct_id: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Subaccount Id",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    account_type: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Derive Account Type (trader/market_maker)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )


KEYS = DeriveConfigMap.model_construct()

OTHER_DOMAINS = ["derive_testnet"]
OTHER_DOMAINS_PARAMETER = {"derive_testnet": "derive_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"derive_testnet": "BTC-USD"}
OTHER_DOMAINS_DEFAULT_FEES = {"derive_testnet": [0, 0.025]}


class DeriveTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "derive_testnet"
    derive_testnet_wallet_address: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Derive Wallet address",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    session_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your session private key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    subacct_id: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Subaccount Id",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    account_type: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Derive Account Type (trader/market_maker)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="derive")


OTHER_DOMAINS_KEYS = {"derive_testnet": DeriveTestnetConfigMap.model_construct()}
