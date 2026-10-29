"""
Derive perpetual connector configuration.

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
   covers everything beneath it, so perpetual trading needs ``trade:orderbook:perp`` or any grant above
   it: ``trade:orderbook:all``, ``trade:all`` or ``admin``. Reading balances and orders needs no
   scope of its own. The owner wallet's own key can be used in place of a session key.
4. Orders live only as long as the session key. v3 expires an order when its signature does,
   whatever its time in force, and an action may not outlive the key that signed it (14038). The
   connector reads the key's expiry at startup and signs each resting order for as long as the
   API allows - about 119 days - or until just before the key expires, whichever comes first.
5. A resting close is not reduce-only. v3 accepts ``reduce_only`` only on orders that cannot rest
   (market, IOC, FOK) and refuses it on a limit or post-only order with 11024, so a take-profit
   limit left on the book after its position has been closed another way would open a position
   in the opposite direction. Market closes are sent reduce-only.

6. A subaccount trades only the instruments of its risk universe. Each subaccount is created
   under one - PRIME holds BTC and ETH, for instance; ``public/get_risk_universes`` lists them -
   and an order for an instrument outside it is refused with -32602, the reason given in the
   error's detail. To trade another universe's pairs, deposit into a new subaccount created
   under it.

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

# Maker rebates(-0.02%) are paid out continuously on each trade directly to the trading wallet.(https://derive_perpetual.gitbook.io/derive_perpetual-docs/trading/fees)
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0001"),
    taker_percent_fee_decimal=Decimal("0.0003"),
    buy_percent_fee_deducted_from_returns=True
)

CENTRALIZED = False

EXAMPLE_PAIR = "OP-USDC"

BROKER_ID = "HBOT"


class DerivePerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "derive_perpetual"
    derive_perpetual_wallet_address: SecretStr = Field(
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


KEYS = DerivePerpetualConfigMap.model_construct()

OTHER_DOMAINS = ["derive_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"derive_perpetual_testnet": "derive_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"derive_perpetual_testnet": "BTC-USD"}
OTHER_DOMAINS_DEFAULT_FEES = {"derive_perpetual_testnet": [0, 0.025]}


class DerivePerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "derive_perpetual_testnet"
    derive_perpetual_testnet_wallet_address: SecretStr = Field(
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
    model_config = ConfigDict(title="derive_perpetual")


OTHER_DOMAINS_KEYS = {"derive_perpetual_testnet": DerivePerpetualTestnetConfigMap.model_construct()}
