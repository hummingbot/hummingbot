from collections import namedtuple

from pydantic import Field, SecretStr

import hummingbot.connector.derivative.bitmex_perpetual.bitmex_perpetual_web_utils as web_utils
import hummingbot.connector.derivative.bitmex_perpetual.constants as CONSTANTS
from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData

CENTRALIZED = True


EXAMPLE_PAIR = "ETH-XBT"


DEFAULT_FEES = [0.01, 0.075]


class BitmexPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="bitmex_perpetual", client_data=None)
    bitmex_perpetual_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Bitmex Perpetual API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    bitmex_perpetual_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Bitmex Perpetual API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )


KEYS = BitmexPerpetualConfigMap.construct()

OTHER_DOMAINS = ["bitmex_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"bitmex_perpetual_testnet": "bitmex_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"bitmex_perpetual_testnet": "ETH-XBT"}
OTHER_DOMAINS_DEFAULT_FEES = {"bitmex_perpetual_testnet": [0.02, 0.04]}


class BitmexPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="bitmex_perpetual_testnet", client_data=None)
    bitmex_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Bitmex Perpetual testnet API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    bitmex_perpetual_testnet_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Bitmex Perpetual testnet API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "bitmex_perpetual"


OTHER_DOMAINS_KEYS = {"bitmex_perpetual_testnet": BitmexPerpetualTestnetConfigMap.construct()}


TRADING_PAIR_INDICES: dict = {}
TRADING_PAIR_INDEX = namedtuple('TradingPairIndex', 'index tick_size')
TRADING_PAIR_SIZE_CURRENCY: dict = {}
TRADING_PAIR_SIZE = namedtuple('TradingPairSize', 'currency is_base multiplier')


async def get_trading_pair_size_currency(exchange_trading_pair):
    if exchange_trading_pair in TRADING_PAIR_SIZE_CURRENCY:
        return TRADING_PAIR_SIZE_CURRENCY[exchange_trading_pair]
    else:
        instrument = await web_utils.api_request(
            path = CONSTANTS.EXCHANGE_INFO_URL,
            domain = "bitmex_perpetual",
            params = {"symbol": exchange_trading_pair}
        )
        trading_pair_info = instrument[0]
        base, quote = trading_pair_info['rootSymbol'], trading_pair_info['quoteCurrency']
        multiplier = trading_pair_info.get("underlyingToPositionMultiplier")
        if trading_pair_info['positionCurrency'] == quote:
            TRADING_PAIR_SIZE_CURRENCY[exchange_trading_pair] = TRADING_PAIR_SIZE(quote, False, multiplier)
        else:
            TRADING_PAIR_SIZE_CURRENCY[exchange_trading_pair] = TRADING_PAIR_SIZE(base, True, multiplier)
        return TRADING_PAIR_SIZE_CURRENCY[exchange_trading_pair]


async def get_trading_pair_index_and_tick_size(exchange_trading_pair):
    if exchange_trading_pair in TRADING_PAIR_INDICES:
        return TRADING_PAIR_INDICES[exchange_trading_pair]
    else:
        index = 0
        multiplier = 0
        while True:
            offset = 500 * multiplier
            instruments = await web_utils.api_request(
                path = CONSTANTS.EXCHANGE_INFO_URL,
                domain = "bitmex_perpetual",
                params = {
                    "count": 500,
                    "start": offset
                }
            )
            for instrument in instruments:
                if instrument['symbol'] == exchange_trading_pair:
                    TRADING_PAIR_INDICES[exchange_trading_pair] = TRADING_PAIR_INDEX(
                        index,
                        instrument['tickSize']
                    )
                    return TRADING_PAIR_INDICES[exchange_trading_pair]
                else:
                    index += 1
            if len(instruments) < 500:
                return False
            else:
                multiplier += 1
