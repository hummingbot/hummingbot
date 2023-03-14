from decimal import Decimal
from typing import Dict, List, Literal, Union

from pydantic import Field, validator

from hummingbot.client.config.config_data_types import BaseClientModel, ClientConfigEnum, ClientFieldData
from hummingbot.client.config.config_validators import validate_bool, validate_decimal, validate_market_trading_pair
from hummingbot.client.config.strategy_config_data_types import BaseStrategyConfigMap
from hummingbot.client.settings import AllConnectorSettings

ExchangeEnum = ClientConfigEnum(  # rebuild the exchanges enum
    value="Exchanges",  # noqa: F821
    # using get_connector_settings instead of get_all_connector_names
    # due to all_connector_names does not include testnet
    names={e: e for e in AllConnectorSettings.get_connector_settings()},
    type=str,
)


def get_field(i: int) -> Field:
    return Field(
        default="",
        description="The name of the hedge exchange connector.",
        client_data=ClientFieldData(
            prompt=lambda mi: f"Do you want to monitor connector {i}? (y/n)",
            prompt_on_new=True,
        ),
    )


MAX_CONNECTOR = 5


class EmptyMarketConfigMap(BaseClientModel):
    connector: Union[None, ExchangeEnum] = None
    markets: Union[None, List[str]] = None
    offsets: Union[None, List[Decimal]] = None

    class Config:
        title = "n"


class MarketConfigMap(BaseClientModel):
    connector: Union[None, ExchangeEnum] = Field(
        default=...,
        description="The name of the exchange connector.",
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter name of the exchange to use",
            prompt_on_new=True,
        ),
    )
    markets: Union[None, List[str]] = Field(
        default=...,
        description="The name of the trading pair.",
        client_data=ClientFieldData(
            prompt=lambda mi: MarketConfigMap.trading_pair_prompt(mi),
            prompt_on_new=True,
        ),
    )
    offsets: Union[None, List[Decimal]] = Field(
        default=Decimal("0.0"),
        description="The offsets for each trading pair.",
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the offsets to use to hedge the markets comma seperated. "
            "the remainder will be assumed as 0 if no inputs. "
            "e.g if markets is BTC-USDT,ETH-USDT,LTC-USDT. "
            "and offsets is 0.1, -0.2. "
            "then the offset amount that will be added is 0.1 BTC, -0.2 ETH and 0 LTC. ",
            prompt_on_new=True,
        ),
    )

    @validator("offsets", pre=True)
    def validate_offsets(cls, offsets: Union[str, List[Decimal]], values: Dict):
        """checks and ensure offsets are of decimal type"""
        if offsets is None:
            return None
        if isinstance(offsets, str):
            offsets = offsets.split(",")
        for offset in offsets:
            if validate_decimal(offset):
                return validate_decimal(offset)
        markets = values["markets"]
        if len(offsets) >= len(markets):
            return offsets[: len(markets)]
        return offsets + ["0"] * (len(markets) - len(offsets))

    @validator("markets", pre=True)
    def validate_markets(cls, markets: Union[str, List[str]], values: Dict):
        """checks and ensure offsets are of decimal type"""
        if markets is None:
            return None
        if isinstance(markets, str):
            markets = markets.split(",")
        for market in markets:
            validated = validate_market_trading_pair(values["connector"], market)
            if validated:
                return validated
        return markets

    @staticmethod
    def trading_pair_prompt(model_instance: "MarketConfigMap") -> str:
        exchange = model_instance.connector
        if exchange is None:
            return ""
        example = AllConnectorSettings.get_example_pairs().get(exchange)
        return (
            f"Enter the token trading pair you would like to hedge/monitor on comma seperated"
            f" {exchange}{f' (e.g. {example})' if example else ''}"
        )

    class Config:
        title = "y"


market_config_map = Union[EmptyMarketConfigMap, MarketConfigMap]


class HedgeConfigMap(BaseStrategyConfigMap):
    strategy: str = Field(default="hedge", client_data=None)
    value_mode: bool = Field(
        default=True,
        description="Whether to hedge based on value or amount",
        client_data=ClientFieldData(
            prompt=lambda mi: "Do you want to hedge by asset value [y] or asset amount[n] (y/n)?",
            prompt_on_new=True,
        ),
    )
    hedge_ratio: Decimal = Field(
        default=Decimal("1"),
        description="The ratio of the hedge amount to the total asset amount",
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter ratio of asset to hedge, e.g 0.5 means 50 percent of the total asset value will be hedged.",
            prompt_on_new=True,
        ),
    )
    hedge_interval: int = Field(
        default=60,
        description="The interval in seconds to check for hedge.",
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the interval in seconds to check for hedge",
            prompt_on_new=True,
        ),
    )
    min_trade_size: Decimal = Field(
        default=Decimal("0.0"),
        description="The minimum trade size in quote asset.",
        ge=0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the minimum trade size in quote asset",
            prompt_on_new=True,
        ),
    )
    slippage: Decimal = Field(
        default=Decimal("0.02"),
        description="The slippage tolerance for the hedge order.",
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the slippage tolerance for the hedge order",
            prompt_on_new=True,
        ),
    )
    hedge_connector: ExchangeEnum = Field(
        default=...,
        description="The name of the hedge exchange connector.",
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter name of the exchange to hedge overall assets",
            prompt_on_new=True,
        ),
    )
    hedge_markets: List[str] = Field(
        default=...,
        description="The name of the trading pair.",
        client_data=ClientFieldData(
            prompt=lambda mi: HedgeConfigMap.hedge_markets_prompt(mi),
            prompt_on_new=True,
        ),
    )
    hedge_offsets: List[Decimal] = Field(
        default=Decimal("0.0"),
        description="The offsets for each trading pair.",
        client_data=ClientFieldData(
            prompt=lambda mi: HedgeConfigMap.hedge_offsets_prompt(mi),
            prompt_on_new=True,
        ),
    )
    hedge_leverage: int = Field(
        default=1,
        description="The leverage to use for the market.",
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the leverage to use for the hedge market",
            prompt_on_new=True,
        ),
    )
    hedge_position_mode: Literal["ONEWAY", "HEDGE"] = Field(
        default="ONEWAY",
        description="The position mode to use for the market.",
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the position mode to use for the hedge market",
            prompt_on_new=True,
        ),
    )
    enable_auto_set_position_mode: bool = Field(
        default=False,
        description="Whether to automatically set the exchange position mode to one-way or hedge based  ratio.",
        client_data=ClientFieldData(
            prompt=lambda mi: "Do you want to automatically set the exchange position mode to one-way or hedge [y/n]?",
            prompt_on_new=False,
        )
    )
    connector_0: market_config_map = get_field(0)
    connector_1: market_config_map = get_field(1)
    connector_2: market_config_map = get_field(2)
    connector_3: market_config_map = get_field(3)
    connector_4: market_config_map = get_field(4)

    @validator("connector_0", "connector_1", "connector_2", "connector_3", "connector_4", pre=True)
    def construct_connector(cls, v: Union[str, bool, EmptyMarketConfigMap, MarketConfigMap, Dict]):
        if isinstance(v, (EmptyMarketConfigMap, MarketConfigMap, Dict)):
            return v
        if validate_bool(v):
            raise ValueError("enter a boolean value")
        if v.lower() in (True, "true", "yes", "y"):
            return MarketConfigMap.construct()
        return EmptyMarketConfigMap.construct()

    @validator("hedge_offsets", pre=True)
    def validate_offsets(cls, offsets: Union[str, List[Decimal]], values: Dict):
        """checks and ensure offsets are of decimal type"""
        if isinstance(offsets, str):
            offsets = offsets.split(",")
        for offset in offsets:
            if validate_decimal(offset):
                return validate_decimal(offset)
        markets = values["hedge_markets"]
        if len(offsets) >= len(markets):
            return offsets[: len(markets)]
        return offsets + ["0"] * (len(markets) - len(offsets))

    @validator("hedge_markets", pre=True)
    def validate_markets(cls, markets: Union[str, List[str]], values: Dict):
        """checks and ensure offsets are of decimal type"""
        if isinstance(markets, str):
            markets = markets.split(",")
        for market in markets:
            validated = validate_market_trading_pair(values["hedge_connector"], market)
            if validated:
                raise ValueError(validated)
        if len(markets) == 0:
            raise ValueError("No market entered")
        if values["value_mode"] and len(markets) > 1:
            raise ValueError("Only one market can be used for value mode")
        return markets

    @staticmethod
    def hedge_markets_prompt(mi: "HedgeConfigMap") -> str:
        """prompts for the markets to hedge"""
        exchange = mi.hedge_connector
        if mi.value_mode:
            return f"Value mode: Enter the trading pair you would like to hedge on {exchange}. (Example: BTC-USDT)"
        return f"Amount mode: Enter the list of trading pair you would like to hedge on {exchange}. comma seperated. \
            (Example: BTC-USDT,ETH-USDT) Only markets with the same base as the hedge markets will be hedged." \
                "WARNING: currently only supports hedging of base assets."

    @staticmethod
    def hedge_offsets_prompt(mi: "HedgeConfigMap") -> str:
        """prompts for the markets to hedge"""
        if mi.value_mode:
            trading_pair = mi.hedge_markets[0]
            base = trading_pair.split("-")[0]
            return f"Enter the offset for {base}. (Example: 0.1 = +0.1{base} used in calculation of hedged value)"
        return (
            "Enter the offsets to use to hedge the markets comma seperated. "
            "(Example: 0.1,-0.2 = +0.1BTC,-0.2ETH, 0LTC will be offset for the exchange amount "
            "if markets is BTC-USDT,ETH-USDT,LTC-USDT)"
        )
