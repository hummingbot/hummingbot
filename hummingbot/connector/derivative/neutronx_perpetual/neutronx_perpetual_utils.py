from decimal import Decimal
from typing import Any, Dict, Type

from pydantic import ConfigDict, Field, SecretStr, create_model

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.connector.derivative.neutronx_perpetual import neutronx_perpetual_constants as CONSTANTS
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = False
EXAMPLE_PAIR = "BTC-USDC"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),
    taker_percent_fee_decimal=Decimal("0.0005"),
    buy_percent_fee_deducted_from_returns=True,
)


def _prompt(text: str, secure: bool = False) -> Dict[str, Any]:
    return {"prompt": text, "is_secure": secure, "is_connect_key": True, "prompt_on_new": True}


def _config_map(connector: str, network_label: str) -> Type[BaseConnectorConfigMap]:
    config_map = create_model(
        "".join(part.capitalize() for part in connector.split("_")) + "ConfigMap",
        __base__=BaseConnectorConfigMap,
        connector=(str, connector),
        **{
            f"{connector}_account_address": (
                str,
                Field(default=..., json_schema_extra=_prompt(f"Enter your NeutronX {network_label} account address")),
            ),
            f"{connector}_private_key": (
                SecretStr,
                Field(
                    default=...,
                    json_schema_extra=_prompt(
                        f"Enter the hex private key that signs for the {network_label} account "
                        "(an agent key is recommended)",
                        secure=True,
                    ),
                ),
            ),
            f"{connector}_agent_key_id": (
                int,
                Field(
                    default=0,
                    ge=0,
                    json_schema_extra=_prompt("Enter the agent key id, or 0 if the account's own key signs"),
                ),
            ),
            f"{connector}_subaccount_id": (
                int,
                Field(default=0, ge=0, json_schema_extra=_prompt("Enter the subaccount id to trade from")),
            ),
            f"{connector}_indexer_api_key": (
                SecretStr,
                Field(
                    default="",
                    json_schema_extra=_prompt(
                        f"Enter your NeutronX {network_label} indexer API key (leave blank for the anonymous limits)",
                        secure=True,
                    ),
                ),
            ),
        },
    )
    config_map.model_config = ConfigDict(**{**config_map.model_config, "title": connector})
    config_map.model_rebuild(force=True)
    return config_map


NeutronxPerpetualConfigMap = _config_map(CONSTANTS.DOMAIN, "mainnet")
NeutronxPerpetualTestnetConfigMap = _config_map(CONSTANTS.TESTNET_DOMAIN, "testnet")

KEYS = NeutronxPerpetualConfigMap.model_construct()

OTHER_DOMAINS = [CONSTANTS.TESTNET_DOMAIN]
OTHER_DOMAINS_PARAMETER = {CONSTANTS.TESTNET_DOMAIN: CONSTANTS.TESTNET_DOMAIN}
OTHER_DOMAINS_EXAMPLE_PAIR = {CONSTANTS.TESTNET_DOMAIN: EXAMPLE_PAIR}
OTHER_DOMAINS_DEFAULT_FEES = {CONSTANTS.TESTNET_DOMAIN: DEFAULT_FEES}
OTHER_DOMAINS_KEYS = {CONSTANTS.TESTNET_DOMAIN: NeutronxPerpetualTestnetConfigMap.model_construct()}
