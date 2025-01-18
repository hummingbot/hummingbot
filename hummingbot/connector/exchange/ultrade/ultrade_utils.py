import re
from decimal import Decimal
from typing import Any, Dict

import base58
from algosdk.encoding import is_valid_address as is_valid_algorand_address
from bip_utils import AlgorandMnemonicValidator
from pydantic import Field, SecretStr, validator

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "ALGO-USDC"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.001"),
    buy_percent_fee_deducted_from_returns=True
)

UUID_V4_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


def is_valid_evm_address(address: str) -> bool:
    return re.match(r"^0x[a-fA-F0-9]{40}$", address) is not None


def is_valid_solana_address(address: str) -> bool:
    try:
        decoded = base58.b58decode(address)
        return len(decoded) == 32
    except Exception:
        return False


WALLET_VALIDATORS = {
    "Algorand": is_valid_algorand_address,
    "EVM": is_valid_evm_address,
    "Solana": is_valid_solana_address,
}


def check_is_wallet_address_valid(wallet_address: str) -> bool:
    """
    Verifies if a wallet address is valid
    :param wallet_address: the wallet address to verify
    :return: True if the wallet address is valid, False otherwise
    """
    return any(WALLET_VALIDATORS[wallet_type](wallet_address) for wallet_type in WALLET_VALIDATORS)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is active, False otherwise
    """
    return exchange_info.get("is_active", False)


class UltradeConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="ultrade", const=True, client_data=None)
    ultrade_trading_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Ultrade Trading Key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    ultrade_wallet_address: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Ultrade Login Wallet Address",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    ultrade_mnemonic_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Ultrade Algorand Mnemonic or EVM Private Key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    ultrade_session_token: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Ultrade Session Token",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    @validator("ultrade_trading_key")
    def check_trading_key(cls, v):
        is_trading_key_valid = is_valid_algorand_address(v.get_secret_value())
        if not is_trading_key_valid and len(v.get_secret_value()) > 0:
            raise ValueError("Invalid Ultrade Trading Key provided.")
        return v

    @validator("ultrade_wallet_address", always=True)
    def check_wallet_address(cls, v, values):
        wallet_address = v.get_secret_value()
        is_valid = check_is_wallet_address_valid(wallet_address)
        if not is_valid:
            raise ValueError(
                f"Invalid Ultrade Wallet Address provided. "
                f"Please provide a valid {'/'.join(WALLET_VALIDATORS.keys())} Wallet Address"
            )
        return v

    @validator("ultrade_mnemonic_key", always=True)
    def check_mnemonic(cls, v, values):
        mnemonic_or_key = v.get_secret_value()

        algorand_ok = AlgorandMnemonicValidator().IsValid(mnemonic_or_key)

        evm_ok = False
        mk = mnemonic_or_key.strip().lower()
        if mk.startswith("0x"):
            mk = mk[2:]
        if re.match(r"^[0-9a-f]{64}$", mk):
            evm_ok = True

        if not (algorand_ok or evm_ok):
            raise ValueError(
                "Invalid Ultrade Algorand Mnemonic or EVM Private Key provided."
            )
        return v

    @validator("ultrade_session_token", always=True)
    def check_session_token(cls, v, values):
        token = v.get_secret_value().strip()
        if not UUID_V4_REGEX.match(token):
            raise ValueError("Invalid Ultrade Session Token. Must be a valid UUID.")
        return v

    class Config:
        title = "ultrade"


KEYS = UltradeConfigMap.construct()

OTHER_DOMAINS = ["ultrade_testnet"]
OTHER_DOMAINS_PARAMETER = {"ultrade_testnet": "testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"ultrade_testnet": "ALGO-USDC"}
OTHER_DOMAINS_DEFAULT_FEES = {"ultrade_testnet": DEFAULT_FEES}


class UltradeTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="ultrade_testnet", const=True, client_data=None)
    ultrade_trading_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Ultrade Testnet Trading Key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    ultrade_wallet_address: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Ultrade Testnet Login Wallet Address",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    ultrade_mnemonic_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Ultrade Testnet Algorand Mnemonic or EVM Private Key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    ultrade_session_token: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Ultrade Testnet Session Token",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    @validator("ultrade_trading_key")
    def check_trading_key(cls, v):
        is_trading_key_valid = is_valid_algorand_address(v.get_secret_value())
        if not is_trading_key_valid and len(v.get_secret_value()) > 0:
            raise ValueError("Invalid Ultrade Testnet Trading Key provided.")
        return v

    @validator("ultrade_wallet_address", always=True)
    def check_wallet_address(cls, v, values):
        wallet_address = v.get_secret_value()
        is_valid = check_is_wallet_address_valid(wallet_address)
        if not is_valid:
            raise ValueError(
                f"Invalid Ultrade Testnet Wallet Address provided. "
                f"Please provide a valid {'/'.join(WALLET_VALIDATORS.keys())} Wallet Address"
            )
        return v

    @validator("ultrade_mnemonic_key", always=True)
    def check_mnemonic(cls, v, values):
        mnemonic_or_key = v.get_secret_value()

        algorand_ok = AlgorandMnemonicValidator().IsValid(mnemonic_or_key)

        evm_ok = False
        mk = mnemonic_or_key.strip().lower()
        if mk.startswith("0x"):
            mk = mk[2:]
        if re.match(r"^[0-9a-f]{64}$", mk):
            evm_ok = True

        if not (algorand_ok or evm_ok):
            raise ValueError(
                "Invalid Ultrade Testnet Algorand Mnemonic or EVM Private Key provided."
            )
        return v

    @validator("ultrade_session_token", always=True)
    def check_session_token_testnet(cls, v, values):
        token = v.get_secret_value().strip()
        if not UUID_V4_REGEX.match(token):
            raise ValueError("Invalid Ultrade Testnet Session Token. Must be a valid UUID.")
        return v

    class Config:
        title = "ultrade_testnet"


OTHER_DOMAINS_KEYS = {"ultrade_testnet": UltradeTestnetConfigMap.construct()}
