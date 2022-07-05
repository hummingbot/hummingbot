from collections import namedtuple

from pydantic import Field, SecretStr

import hummingbot.connector.exchange.bitmex.bitmex_web_utils as web_utils
import hummingbot.connector.exchange.bitmex.constants as CONSTANTS
from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData

CENTRALIZED = True


EXAMPLE_PAIR = "ETH-XBT"


DEFAULT_FEES = [0.1, 0.1]


class BitmexConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="bitmex", const=True, client_data=None)
    bitmex_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Bitmex API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    bitmex_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Bitmex API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "bitmex"


KEYS = BitmexConfigMap.construct()

OTHER_DOMAINS = ["bitmex_testnet"]
OTHER_DOMAINS_PARAMETER = {"bitmex_testnet": "bitmex_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"bitmex_testnet": "ETH-XBT"}
OTHER_DOMAINS_DEFAULT_FEES = {"bitmex_testnet": [0.02, 0.04]}


class BitmexTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="bitmex_testnet", const=True, client_data=None)
    bitmex_testnet_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Bitmex Testnet API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    bitmex_testnet_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Bitmex Testnet API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "bitmex_testnet"


OTHER_DOMAINS_KEYS = {"bitmex_testnet": BitmexTestnetConfigMap.construct()}


TRADING_PAIR_INDICES: dict = {}
TRADING_PAIR_INDEX = namedtuple('TradingPairIndex', 'index tick_size')
TRADING_PAIR_MULTIPLIERS: dict = {}
TRADING_PAIR_MULTIPLIERS_TUPLE = namedtuple('TradingPairMultipliersTuple', 'base_multiplier quote_multiplier')


async def get_trading_pair_multipliers(exchange_trading_pair):
    if exchange_trading_pair in TRADING_PAIR_MULTIPLIERS:
        return TRADING_PAIR_MULTIPLIERS[exchange_trading_pair]
    else:
        instrument = await web_utils.api_request(
            path = CONSTANTS.EXCHANGE_INFO_URL,
            domain = "bitmex_testnet",
            params = {"symbol": exchange_trading_pair}
        )
        trading_pair_info = instrument[0]
        base_multiplier = trading_pair_info.get("underlyingToPositionMultiplier")
        quote_multiplier = trading_pair_info.get("quoteToSettleMultiplier")
        TRADING_PAIR_MULTIPLIERS[exchange_trading_pair] = TRADING_PAIR_MULTIPLIERS_TUPLE(base_multiplier, quote_multiplier)

        return TRADING_PAIR_MULTIPLIERS[exchange_trading_pair]


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
                domain = "bitmex",
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
