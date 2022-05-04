from typing import Optional, Tuple

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData

CENTRALIZED = True


EXAMPLE_PAIR = "BTC-USD"


DEFAULT_FEES = [0.02, 0.07]


def split_trading_pair(trading_pair: str) -> Optional[Tuple[str, str]]:
    try:
        m = trading_pair.split("/")
        return m[0], m[1]
    # Exceptions are now logged as warnings in trading pair fetcher
    except Exception:
        return None


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> Optional[str]:
    if split_trading_pair(exchange_trading_pair) is None:
        return None
    # Blocktane does not split BASEQUOTE (fthusd)
    base_asset, quote_asset = split_trading_pair(exchange_trading_pair)
    return f"{base_asset}-{quote_asset}".upper()


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "/")


class FtxConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="ftx", client_data=None)
    ftx_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your FTX API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    ftx_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your FTX API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    ftx_subaccount_name: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your FTX subaccount name (if this is not a subaccount, leave blank)",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )


KEYS = FtxConfigMap.construct()
