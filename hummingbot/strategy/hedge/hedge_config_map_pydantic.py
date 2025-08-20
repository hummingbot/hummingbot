from decimal import Decimal
from typing import Dict, List, Literal, Union

from pydantic import ConfigDict, Field, field_validator

from hummingbot.client.config.config_data_types import BaseClientModel, ClientConfigEnum
from hummingbot.client.config.config_validators import validate_bool
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
        json_schema_extra={"prompt": f"Do you want to monitor connector {i}? (y/n)", "prompt_on_new": True},
    )


MAX_CONNECTOR = 5


class EmptyMarketConfigMap(BaseClientModel):
    connector: Union[None, ExchangeEnum] = None
    markets: Union[None, List[str]] = None
    offsets: Union[None, List[Decimal]] = None
    model_config = ConfigDict(title="n")


class MarketConfigMap(BaseClientModel):
    connector: Union[None, ExchangeEnum] = Field(
        default=...,
        description="The name of the exchange connector.",
        json_schema_extra={"prompt": "Enter name of the exchange to use", "prompt_on_new": True}
    )
    markets: Union[None, List[str]] = Field(
        default=...,
        description="The name of the trading pair.",
        json_schema_extra={"prompt": lambda mi: MarketConfigMap.trading_pair_prompt(mi), "prompt_on_new": True},
    )
    offsets: Union[None, List[Decimal]] = Field(
        default=Decimal("0.0"),
        description="The offsets for each trading pair.",
        json_schema_extra={
            "prompt": "Enter the offsets to use to hedge the markets comma separated, the remainder will be assumed as 0 if no inputs. "
                      "e.g if markets is BTC-USDT,ETH-USDT,LTC-USDT, and offsets is 0.1, -0.2. "
                      "then the offset amount that will be added is 0.1 BTC, -0.2 ETH and 0 LTC. ",
            "prompt_on_new": True,
        }
    )

    @staticmethod
    def trading_pair_prompt(model_instance: "MarketConfigMap") -> str:
        exchange = model_instance.connector
        if exchange is None:
            return ""
        example = AllConnectorSettings.get_example_pairs().get(exchange)
        return (
            f"Enter the token trading pair you would like to hedge/monitor on comma separated"
            f" {exchange}{f' (e.g. {example})' if example else ''}"
        )
    model_config = ConfigDict(title="y")


market_config_map = Union[EmptyMarketConfigMap, MarketConfigMap]


class HedgeConfigMap(BaseStrategyConfigMap):
    strategy: str = Field(default="hedge")
    value_mode: bool = Field(
        default=True,
        description="Whether to hedge based on value or amount",
        json_schema_extra={
            "prompt": "Do you want to hedge by asset value [y] or asset amount[n] (y/n)?",
            "prompt_on_new": True,
        }
    )
    hedge_ratio: Decimal = Field(
        default=Decimal("1"),
        description="The ratio of the hedge amount to the total asset amount",
        json_schema_extra={
            "prompt": "Enter the ratio of asset to hedge, e.g 0.5 means 50 percent of the total asset value will be hedged.",
            "prompt_on_new": True,
        }
    )
    hedge_interval: int = Field(
        default=60,
        description="The interval in seconds to check for hedge.",
        json_schema_extra={"prompt": "Enter the interval in seconds to check for hedge", "prompt_on_new": True},
    )
    min_trade_size: Decimal = Field(
        default=Decimal("0.0"),
        description="The minimum trade size in quote asset.",
        ge=0,
        json_schema_extra={"prompt": "Enter the minimum trade size in quote asset", "prompt_on_new": True},
    )
    slippage: Decimal = Field(
        default=Decimal("0.02"),
        description="The slippage tolerance for the hedge order.",
        json_schema_extra={"prompt": "Enter the slippage tolerance for the hedge order", "prompt_on_new": True},
    )
    hedge_connector: ExchangeEnum = Field(
        default=...,
        description="The name of the hedge exchange connector.",
        json_schema_extra={"prompt": "Enter name of the exchange to hedge overall assets", "prompt_on_new": True},
    )
    hedge_markets: List[str] = Field(
        default=...,
        description="The name of the trading pair.",
        json_schema_extra={"prompt": lambda mi: HedgeConfigMap.hedge_markets_prompt(mi), "prompt_on_new": True},
    )
    hedge_offsets: List[Decimal] = Field(
        default=Decimal("0.0"),
        description="The offsets for each trading pair.",
        json_schema_extra={"prompt": lambda mi: HedgeConfigMap.hedge_offsets_prompt(mi), "prompt_on_new": True},
    )
    hedge_leverage: int = Field(
        default=1,
        description="The leverage to use for the market.",
        json_schema_extra={"prompt": "Enter the leverage to use for the hedge market", "prompt_on_new": True},
    )
    hedge_position_mode: Literal["ONEWAY", "HEDGE"] = Field(
        default="ONEWAY",
        description="The position mode to use for the market.",
        json_schema_extra={"prompt": "Enter the position mode to use for the hedge market", "prompt_on_new": True},
    )
    enable_auto_set_position_mode: bool = Field(
        default=False,
        description="Whether to automatically set the exchange position mode to one-way or hedge based  ratio.",
        json_schema_extra={"prompt": "Do you want to automatically set the exchange position mode to one-way or hedge based on the ratio [y/n]?"},
    )
    connector_0: market_config_map = get_field(0)
    connector_1: market_config_map = get_field(1)
    connector_2: market_config_map = get_field(2)
    connector_3: market_config_map = get_field(3)
    connector_4: market_config_map = get_field(4)

    @field_validator("connector_0", "connector_1", "connector_2", "connector_3", "connector_4", mode="before")
    @classmethod
    def construct_connector(cls, v: Union[str, bool, EmptyMarketConfigMap, MarketConfigMap, Dict]):
        if isinstance(v, (EmptyMarketConfigMap, MarketConfigMap, Dict)):
            return v
        if validate_bool(v):
            raise ValueError("enter a boolean value")
        if v.lower() in (True, "true", "yes", "y"):
            return MarketConfigMap.model_construct()
        return EmptyMarketConfigMap.model_construct()

    @staticmethod
    def hedge_markets_prompt(mi: "HedgeConfigMap") -> str:
        """prompts for the markets to hedge"""
        exchange = mi.hedge_connector
        if mi.value_mode:
            return f"Value mode: Enter the trading pair you would like to hedge on {exchange}. (Example: BTC-USDT)"
        return (
            f"Amount mode: Enter the list of trading pairs you would like to hedge on {exchange}, "
            f"comma-separated (e.g., BTC-USDT,ETH-USDT). Only markets with the same base asset as the hedge "
            f"markets will be hedged. WARNING: Currently only supports hedging of base assets."
        )

    @staticmethod
    def hedge_offsets_prompt(mi: "HedgeConfigMap") -> str:
        """prompts for the markets to hedge"""
        if mi.value_mode:
            trading_pair = mi.hedge_markets[0]
            base = trading_pair.split("-")[0]
            return f"Enter the offset for {base}. (Example: 0.1 = +0.1{base} used in calculation of hedged value)"
        return (
            "Enter the offsets to use to hedge the markets comma separated. "
            "(Example: 0.1,-0.2 = +0.1BTC,-0.2ETH, 0LTC will be offset for the exchange amount "
            "if markets is BTC-USDT,ETH-USDT,LTC-USDT)"
        )
