
from decimal import Decimal

from pydantic import Field

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.client.config.strategy_config_data_types import BaseTradingStrategyMakerTakerConfigMap


class CrossExchangeMiningConfigMap(BaseTradingStrategyMakerTakerConfigMap):
    strategy: str = Field(default="cross_exchange_mining", client_data=None)

    min_profitability: Decimal = Field(
        default=...,
        description="The minimum estimated profitability required to open a position.",
        ge=-100.0,
        le=100.0,
        client_data=ClientFieldData(
            prompt=lambda mi: "What is the minimum profitability for you to make a trade? (Enter 1 to indicate 1%)",
            prompt_on_new=True,
        ),
    )
    order_amount: Decimal = Field(
        default=...,
        description="The amount of base currency for the strategy to maintain over exchanges.",
        ge=0.0,
        client_data=ClientFieldData(
            prompt=lambda mi: CrossExchangeMiningConfigMap.order_amount_prompt(mi),
            prompt_on_new=True,
        )
    )

    balance_adjustment_duration: float = Field(
        default=Decimal("5"),
        description="Time interval to rebalance portfolio >>> ",
        client_data=ClientFieldData(
            prompt=lambda mi: "Time interval between subsequent portfolio rebalances ",
            prompt_on_new=True,
        ),
    )

    slippage_buffer: Decimal = Field(
        default=Decimal("5.0"),
        description="Allowed slippage to fill ensure taker orders are filled.",
        ge=0.0,
        le=100.0,
        client_data=ClientFieldData(
            prompt=lambda mi: (
                "How much buffer do you want to add to the price to account for slippage for taker orders "
                "Enter 1 to indicate 1%"
            ),
            prompt_on_new=True,
        ),
    )

    min_prof_tol_low: Decimal = Field(
        default=Decimal("0.05"),
        description="Tolerance below min prof to cancel order.",
        ge=0.0,
        le=100.0,
        client_data=ClientFieldData(
            prompt=lambda mi: (
                "What percentage below the min profitability do you want to cancel the set order"
                "Enter 0.1 to indicate 0.1%"
            ),
            prompt_on_new=True,
        ),
    )

    min_prof_tol_high: Decimal = Field(
        default=Decimal("0.05"),
        description="Tolerance above min prof to cancel order.",
        ge=0.0,
        le=100.0,
        client_data=ClientFieldData(
            prompt=lambda mi: (
                "What percentage above the min profitability level do you want to cancel the set order"
                "Enter 0.1 to indicate 0.1%"
            ),
            prompt_on_new=True,
        ),
    )
    volatility_buffer_size: int = Field(
        default=Decimal("120"),
        description="The period in seconds to calulate volatility over: ",
        client_data=ClientFieldData(
            prompt=lambda mi: "The period in seconds to calulate volatility over: ",
            prompt_on_new=True,
        ),
    )

    min_prof_adj_timer: float = Field(
        default=Decimal("3600"),
        description="Time interval to adjust min profitability over",
        client_data=ClientFieldData(
            prompt=lambda mi: "Time interval to adjust min profitability over by using results of previous trades in last 24 hrs",
            prompt_on_new=True,
        ),
    )
    min_order_amount: Decimal = Field(
        default=Decimal("0.0"),
        description="What is the minimum order amount required for bid or ask orders?: ",
        ge=0.0,
        client_data=ClientFieldData(
            prompt=lambda mi: (
                    "What is the minimum order amount required for bid or ask orders?: "
            ),
            prompt_on_new=True,
        ),
    )
    rate_curve: Decimal = Field(
        default=Decimal("1.0"),
        description="Multiplier for rate curve for the adjustment of min profitability based on previous trades over last 24 hrs: ",
        ge=0.0,
        client_data=ClientFieldData(
            prompt=lambda mi: (
                    "Multiplier for rate curve for the adjustment of min profitability based on previous trades over last 24 hrs: "
            ),
            prompt_on_new=True,
        ),
    )
    trade_fee: Decimal = Field(
        default=Decimal("0.25"),
        description="Complete trade fee covering both taker and maker trades: ",
        ge=0.0,
        client_data=ClientFieldData(
            prompt=lambda mi: (
                    "Complete trade fee covering both taker and maker trades: "
            ),
            prompt_on_new=True,
        ),
    )
    # === prompts ===

    @classmethod
    def order_amount_prompt(cls, model_instance: 'CrossExchangeMiningConfigMap') -> str:
        trading_pair = model_instance.maker_market_trading_pair
        base_asset, quote_asset = trading_pair.split("-")
        return f"The amount of {base_asset} for the strategy to maintain in wallet over exchanges (Will autobalance by buying or selling to maintain amount).?"
