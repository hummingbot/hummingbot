from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, Tuple, Union

from pydantic import ConfigDict, Field, field_validator

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.client.config.config_validators import validate_bool
from hummingbot.client.config.strategy_config_data_types import BaseTradingStrategyMakerTakerConfigMap
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.strategy.maker_taker_market_pair import MakerTakerMarketPair


class ConversionRateModel(BaseClientModel, ABC):
    @abstractmethod
    def get_conversion_rates(
            self, market_pair: MakerTakerMarketPair
    ) -> Tuple[str, str, Decimal, str, str, Decimal]:
        pass


class OracleConversionRateMode(ConversionRateModel):
    model_config = ConfigDict(title="rate_oracle_conversion_rate")

    def get_conversion_rates(
            self, market_pair: MakerTakerMarketPair
    ) -> Tuple[str, str, Decimal, str, str, Decimal]:
        """
        Find conversion rates from taker market to maker market
        :param market_pair: maker and taker trading pairs for which to do conversion
        :return: A tuple of quote pair symbol, quote conversion rate source, quote conversion rate,
        base pair symbol, base conversion rate source, base conversion rate
        """
        from .cross_exchange_market_making import CrossExchangeMarketMakingStrategy
        quote_pair = f"{market_pair.taker.quote_asset}-{market_pair.maker.quote_asset}"
        if market_pair.taker.quote_asset != market_pair.maker.quote_asset:
            quote_rate_source = RateOracle.get_instance().source.name
            quote_rate = RateOracle.get_instance().get_pair_rate(quote_pair)
        else:
            quote_rate_source = "fixed"
            quote_rate = Decimal("1")

        base_pair = f"{market_pair.taker.base_asset}-{market_pair.maker.base_asset}"
        if market_pair.taker.base_asset != market_pair.maker.base_asset:
            base_rate_source = RateOracle.get_instance().source.name
            base_rate = RateOracle.get_instance().get_pair_rate(base_pair)
        else:
            base_rate_source = "fixed"
            base_rate = Decimal("1")

        gas_pair = None
        if CrossExchangeMarketMakingStrategy.is_gateway_market(market_pair.taker):
            if hasattr(market_pair.taker.market, "network_transaction_fee"):
                transaction_fee: TokenAmount = market_pair.taker.market.network_transaction_fee
                if transaction_fee is not None:
                    gas_pair = f"{transaction_fee.token}-{market_pair.maker.quote_asset}"

        if gas_pair is not None and transaction_fee.token != market_pair.maker.quote_asset:
            gas_rate_source = RateOracle.get_instance().source.name
            gas_rate = RateOracle.get_instance().get_pair_rate(gas_pair)
        else:
            gas_rate_source = "fixed"
            gas_rate = Decimal("1")

        return quote_pair, quote_rate_source, quote_rate, base_pair, base_rate_source, base_rate, gas_pair, gas_rate_source, gas_rate


class TakerToMakerConversionRateMode(ConversionRateModel):
    taker_to_maker_base_conversion_rate: Decimal = Field(
        default=Decimal("1.0"),
        description="A fixed conversion rate between the maker and taker trading pairs based on the maker base asset.",
        gt=0.0,
        json_schema_extra={
            "prompt": "Enter conversion rate for taker base asset value to maker base asset value, e.g. "
                      "if maker base asset is USD and the taker is DAI, 1 DAI is valued at 1.25 USD, "
                      "the conversion rate is 1.25",
            "prompt_on_new": True
        }
    )
    taker_to_maker_quote_conversion_rate: Decimal = Field(
        default=Decimal("1.0"),
        description="A fixed conversion rate between the maker and taker trading pairs based on the maker quote asset.",
        gt=0.0,
        json_schema_extra={
            "prompt": "Enter conversion rate for taker quote asset value to maker quote asset value, e.g. "
                      "if maker quote asset is USD and the taker is DAI, 1 DAI is valued at 1.25 USD, "
                      "the conversion rate is 1.25",
            "prompt_on_new": True
        }
    )
    gas_to_maker_base_conversion_rate: Decimal = Field(
        default=Decimal("1.0"),
        description="A fixed conversion rate between the maker quote asset and taker gas asset.",
        gt=0.0,
        json_schema_extra={
            "prompt": "Enter conversion rate for gas token value of taker gateway exchange to maker base asset value, e.g. "
                      "if maker base asset is USD and the gas token is DAI, 1 DAI is valued at 1.25 USD, "
                      "the conversion rate is 1.25",
            "prompt_on_new": True
        }
    )
    model_config = ConfigDict(title="fixed_conversion_rate")

    def get_conversion_rates(
            self, market_pair: MakerTakerMarketPair
    ) -> Tuple[str, str, Decimal, str, str, Decimal]:
        """
        Find conversion rates from taker market to maker market
        :param market_pair: maker and taker trading pairs for which to do conversion
        :return: A tuple of quote pair symbol, quote conversion rate source, quote conversion rate,
        base pair symbol, base conversion rate source, base conversion rate
        """
        from .cross_exchange_market_making import CrossExchangeMarketMakingStrategy
        quote_pair = f"{market_pair.taker.quote_asset}-{market_pair.maker.quote_asset}"
        quote_rate_source = "fixed"
        quote_rate = self.taker_to_maker_quote_conversion_rate

        base_pair = f"{market_pair.taker.base_asset}-{market_pair.maker.base_asset}"
        base_rate_source = "fixed"
        base_rate = self.taker_to_maker_base_conversion_rate

        gas_pair = None
        if CrossExchangeMarketMakingStrategy.is_gateway_market(market_pair.taker):
            if hasattr(market_pair.taker.market, "network_transaction_fee"):
                transaction_fee: TokenAmount = market_pair.taker.market.network_transaction_fee
                if transaction_fee is not None:
                    gas_pair = f"{transaction_fee.token}-{market_pair.maker.quote_asset}"

        gas_rate_source = "fixed"
        gas_rate = self.taker_to_maker_base_conversion_rate

        return quote_pair, quote_rate_source, quote_rate, base_pair, base_rate_source, base_rate, gas_pair, gas_rate_source, gas_rate


CONVERSION_RATE_MODELS = {
    OracleConversionRateMode.model_config["title"]: OracleConversionRateMode,
    TakerToMakerConversionRateMode.model_config["title"]: TakerToMakerConversionRateMode,
}


class OrderRefreshMode(BaseClientModel, ABC):
    @abstractmethod
    def get_cancel_order_threshold(self) -> Decimal:
        pass

    @abstractmethod
    def get_expiration_seconds(self) -> Decimal:
        pass


class PassiveOrderRefreshMode(OrderRefreshMode):
    cancel_order_threshold: Decimal = Field(
        default=Decimal("5.0"),
        description="Profitability threshold to cancel a trade.",
        gt=-100.0,
        lt=100.0,
        json_schema_extra={
            "prompt": "What is the profitability threshold to cancel a trade? (Enter 1 to indicate 1%)",
            "prompt_on_new": True
        }
    )

    limit_order_min_expiration: Decimal = Field(
        default=130.0,
        description="Limit order expiration time limit.",
        gt=0.0,
        json_schema_extra={
            "prompt": "How long do you want limit orders to expire? (in seconds)",
            "prompt_on_new": True
        }
    )
    model_config = ConfigDict(title="passive_order_refresh")

    def get_cancel_order_threshold(self) -> Decimal:
        return self.cancel_order_threshold / Decimal("100")

    def get_expiration_seconds(self) -> Decimal:
        return self.limit_order_min_expiration


class ActiveOrderRefreshMode(OrderRefreshMode):
    model_config = ConfigDict(title="active_order_refresh")

    def get_cancel_order_threshold(self) -> Decimal:
        return Decimal('nan')

    def get_expiration_seconds(self) -> Decimal:
        return Decimal('nan')


ORDER_REFRESH_MODELS = {
    PassiveOrderRefreshMode.model_config["title"]: PassiveOrderRefreshMode,
    ActiveOrderRefreshMode.model_config["title"]: ActiveOrderRefreshMode,
}


class CrossExchangeMarketMakingConfigMap(BaseTradingStrategyMakerTakerConfigMap):
    strategy: str = Field(default="cross_exchange_market_making")

    min_profitability: Decimal = Field(
        default=...,
        description="The minimum estimated profitability required to open a position.",
        ge=-100.0,
        le=100.0,
        json_schema_extra={
            "prompt": "What is the minimum profitability for you to make a trade? (Enter 1 to indicate 1%)",
            "prompt_on_new": True
        }
    )
    order_amount: Decimal = Field(
        default=...,
        description="The strategy order amount.",
        ge=0.0,
        json_schema_extra={
            "prompt": lambda mi: CrossExchangeMarketMakingConfigMap.order_amount_prompt(mi),
            "prompt_on_new": True
        }
    )
    adjust_order_enabled: bool = Field(
        default=True,
        description="Adjust order price to be one tick above the top bid or below the top ask.",
        json_schema_extra={"prompt": "Do you want to enable adjust order? (Yes/No)"},
    )
    order_refresh_mode: Union[ActiveOrderRefreshMode, PassiveOrderRefreshMode] = Field(
        default=ActiveOrderRefreshMode.model_construct(),
        description="Refresh orders by cancellation or by letting them expire.",
        json_schema_extra={
            "prompt": lambda mi: f"Select the order refresh mode ({'/'.join(list(ORDER_REFRESH_MODELS.keys()))})",
            "prompt_on_new": True
        }
    )
    top_depth_tolerance: Decimal = Field(
        default=Decimal("0.0"),
        description="Volume requirement for determining a possible top bid or ask price from the order book.",
        ge=0.0,
        json_schema_extra={"prompt": lambda mi: CrossExchangeMarketMakingConfigMap.top_depth_tolerance_prompt(mi)}
    )
    anti_hysteresis_duration: float = Field(
        default=60.0,
        description="Minimum time limit between two subsequent order adjustments.",
        gt=0.0,
        json_schema_extra={
            "prompt": "What is the minimum time interval you want limit orders to be adjusted? (in seconds)"}
    )
    order_size_taker_volume_factor: Decimal = Field(
        default=Decimal("25.0"),
        description="Taker order size as a percentage of volume.",
        ge=0.0,
        le=100.0,
        json_schema_extra={
            "prompt": "What percentage of hedge-able volume would you like to be traded on the taker market? (Enter 1 to indicate 1%)"
        }
    )
    order_size_taker_balance_factor: Decimal = Field(
        default=Decimal("99.5"),
        description="Taker order size as a percentage of the available balance.",
        ge=0.0,
        le=100.0,
        json_schema_extra={
            "prompt": "What percentage of asset balance would you like to use for hedging trades on the taker market? (Enter 1 to indicate 1%)"
        }
    )
    order_size_portfolio_ratio_limit: Decimal = Field(
        default=Decimal("16.67"),
        description="Order size as a maker and taker account balance ratio.",
        ge=0.0,
        le=100.0,
        json_schema_extra={
            "prompt": "What ratio of your total portfolio value would you like to trade on the maker and taker markets? Enter 50 for 50%"
        }
    )
    conversion_rate_mode: Union[OracleConversionRateMode, TakerToMakerConversionRateMode] = Field(
        default=OracleConversionRateMode.model_construct(),
        description="Convert between different trading pairs using fixed conversion rates or using the rate oracle.",
        json_schema_extra={
            "prompt": f"Select the conversion rate mode ({'/'.join(list(CONVERSION_RATE_MODELS.keys()))})",
            "prompt_on_new": True
        }
    )
    slippage_buffer: Decimal = Field(
        default=Decimal("5.0"),
        description="Allowed slippage to fill ensure taker orders are filled.",
        ge=0.0,
        le=100.0,
        json_schema_extra={
            "prompt": "How much buffer do you want to add to the price to account for slippage for taker orders. "
                      "Enter 1 to indicate 1%",
            "prompt_on_new": True
        }
    )
    taker_market: str = Field(
        default=...,
        description="The name of the taker exchange connector.",
        json_schema_extra={"prompt": "Enter your taker connector (Exchange/AMM/CLOB)", "prompt_on_new": True}
    )

    # === prompts ===

    @classmethod
    def top_depth_tolerance_prompt(cls, model_instance: 'CrossExchangeMarketMakingConfigMap') -> str:
        maker_market = model_instance.maker_market_trading_pair
        base_asset, quote_asset = maker_market.split("-")
        return f"What is your top depth tolerance? (in {base_asset})"

    @classmethod
    def order_amount_prompt(cls, model_instance: 'CrossExchangeMarketMakingConfigMap') -> str:
        trading_pair = model_instance.maker_market_trading_pair
        base_asset, quote_asset = trading_pair.split("-")
        return f"What is the amount of {base_asset} per order?"

    # === specific validations ===
    @field_validator("order_refresh_mode", mode="before")
    @classmethod
    def validate_order_refresh_mode(cls, v: Union[str, ActiveOrderRefreshMode, PassiveOrderRefreshMode]):
        if isinstance(v, (ActiveOrderRefreshMode, PassiveOrderRefreshMode, Dict)):
            sub_model = v
        elif v not in ORDER_REFRESH_MODELS:
            raise ValueError(
                f"Invalid order refresh mode, please choose value from {list(ORDER_REFRESH_MODELS.keys())}."
            )
        else:
            sub_model = ORDER_REFRESH_MODELS[v].model_construct()
        return sub_model

    @field_validator("conversion_rate_mode", mode="before")
    @classmethod
    def validate_conversion_rate_mode(cls, v: Union[str, OracleConversionRateMode, TakerToMakerConversionRateMode]):
        if isinstance(v, (OracleConversionRateMode, TakerToMakerConversionRateMode, Dict)):
            sub_model = v
        elif v not in CONVERSION_RATE_MODELS:
            raise ValueError(
                f"Invalid conversion rate mode, please choose value from {list(CONVERSION_RATE_MODELS.keys())}."
            )
        else:
            sub_model = CONVERSION_RATE_MODELS[v].model_construct()
        return sub_model

    # === generic validations ===

    @field_validator("adjust_order_enabled", mode="before")
    @classmethod
    def validate_bool(cls, v: str):
        """Used for client-friendly error output."""
        if isinstance(v, str):
            ret = validate_bool(v)
            if ret is not None:
                raise ValueError(ret)
        return v
