"""
Derive spot connector configuration.

Setting up an account on the v3 API
-----------------------------------
v3 settles on Ethereum L1 (mainnet) and Sepolia (testnet) rather than the old Derive L2.

1. Create the account by depositing on L1. v3 removed ``private/create_subaccount``, so there is
   no API call that creates one; the deposit does it.
2. The wallet address is your own EOA or multisig. v3 has no intermediate "Derive Wallet": every
   wallet/owner field is the owner's own address, and existing Derive Wallets are transferred to
   it during the v2 to v3 state migration. Enter that address: not the old Derive Wallet one,
   and not the address of the session key, which has one of its own.
3. Register a **scoped** session key at derive.xyz. v3 session keys carry scopes, an expiry and
   optionally a subaccount allow-list and an IP allow-list. Scopes form a tree in which a grant
   covers everything beneath it, so spot trading needs ``trade:orderbook:spot`` or any grant above
   it: ``trade:orderbook:all``, ``trade:all`` or ``admin``. Reading balances and orders needs no
   scope of its own. The owner wallet's own key can be used in place of a session key.
4. Orders live only as long as the session key. v3 expires an order when its signature does,
   whatever its time in force, and an action may not outlive the key that signed it (14038). The
   connector reads the key's expiry at startup and signs each resting order for as long as the
   API allows - about 119 days - or until just before the key expires, whichever comes first.

Errors 14026 (key not registered), 14030 (expired) and 14031 (scope does not permit the action)
are reported with that guidance attached.

Existing v2 users are migrating, not upgrading: funds move to L1 under the owner's own address.
Whether a v2 session key carries over is not documented, so the connector checks at startup that
the key is registered to the configured wallet and says so when it is not.
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
            "prompt": "Enter the address of the wallet that owns your Derive account (not the session key's address)",
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
            "prompt": "Enter the address of the wallet that owns your Derive account (not the session key's address)",
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
