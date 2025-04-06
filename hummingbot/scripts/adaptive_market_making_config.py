from decimal import Decimal
from typing import Dict, Any

from hummingbot.client.settings import AllConnectorSettings
from hummingbot.client.config.config_validators import validate_exchange, validate_market_trading_pair
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.strategy_config_data_types import BaseTradingStrategyConfigMap, StrategyTarget
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


def maker_trading_pair_prompt(trading_pairs: str) -> str:
    example = AllConnectorSettings.get_example_pairs().get(trading_pairs)
    return f"Enter the token trading pair you would like to trade on {trading_pairs}{(' e.g. ' + example) if example else ''}"


class AdaptiveMarketMakingConfigMap(BaseTradingStrategyConfigMap):
    strategy_name: str = "adaptive_market_making"
    
    # Exchange and Market Parameters
    connector_name: str = ConfigVar(
        key="connector_name",
        prompt="Enter the name of the exchange connector >>> ",
        validator=validate_exchange,
        default="binance_paper_trade",
    )
    trading_pair: str = ConfigVar(
        key="trading_pair",
        prompt=maker_trading_pair_prompt,
        validator=validate_market_trading_pair,
        default="ETH-USDT",
    )
    
    # Basic Market Making Parameters
    order_amount: Decimal = ConfigVar(
        key="order_amount",
        prompt="Enter the order amount (denominated in the base asset) >>> ",
        type_str="decimal",
        default=Decimal("0.1"),
    )
    min_spread: Decimal = ConfigVar(
        key="min_spread",
        prompt="Enter the minimum spread (as percentage of mid price, e.g., 1 = 1%) >>> ",
        type_str="decimal",
        default=Decimal("0.1"),
    )
    max_spread: Decimal = ConfigVar(
        key="max_spread",
        prompt="Enter the maximum spread (as percentage of mid price, e.g., 1 = 1%) >>> ",
        type_str="decimal",
        default=Decimal("1.0"),
    )
    order_refresh_time: float = ConfigVar(
        key="order_refresh_time",
        prompt="How often do you want to refresh orders (in seconds)? >>> ",
        type_str="float",
        default=30.0,
    )
    max_order_age: float = ConfigVar(
        key="max_order_age",
        prompt="How long do you want orders to remain open (in seconds)? >>> ",
        type_str="float",
        default=60.0 * 60.0,  # 1 hour
    )
    
    # Technical Indicator Parameters
    rsi_length: int = ConfigVar(
        key="rsi_length",
        prompt="Enter the RSI period length >>> ",
        type_str="int",
        default=14,
    )
    rsi_overbought: Decimal = ConfigVar(
        key="rsi_overbought",
        prompt="Enter the RSI overbought threshold >>> ",
        type_str="decimal",
        default=Decimal("70"),
    )
    rsi_oversold: Decimal = ConfigVar(
        key="rsi_oversold",
        prompt="Enter the RSI oversold threshold >>> ",
        type_str="decimal",
        default=Decimal("30"),
    )
    ema_short: int = ConfigVar(
        key="ema_short",
        prompt="Enter the short EMA period length >>> ",
        type_str="int",
        default=12,
    )
    ema_long: int = ConfigVar(
        key="ema_long",
        prompt="Enter the long EMA period length >>> ",
        type_str="int",
        default=120,
    )
    bb_length: int = ConfigVar(
        key="bb_length",
        prompt="Enter the Bollinger Bands period length >>> ",
        type_str="int",
        default=20,
    )
    bb_std: float = ConfigVar(
        key="bb_std",
        prompt="Enter the Bollinger Bands standard deviation multiplier >>> ",
        type_str="float",
        default=2.0,
    )
    
    # Risk Management Parameters
    target_inventory_ratio: Decimal = ConfigVar(
        key="target_inventory_ratio",
        prompt="Enter the target ratio of base to quote assets (0 = all quote, 1 = all base, 0.5 = equal) >>> ",
        type_str="decimal",
        default=Decimal("0.5"),
    )
    min_order_amount: Decimal = ConfigVar(
        key="min_order_amount",
        prompt="Enter the minimum order amount (denominated in the base asset) >>> ",
        type_str="decimal",
        default=Decimal("0.01"),
    )
    volatility_adjustment: Decimal = ConfigVar(
        key="volatility_adjustment",
        prompt="Enter the multiplier for volatility-based spread adjustments >>> ",
        type_str="decimal",
        default=Decimal("1.0"),
    )
    trailing_stop_pct: Decimal = ConfigVar(
        key="trailing_stop_pct",
        prompt="Enter the trailing stop percentage for positions >>> ",
        type_str="decimal",
        default=Decimal("2.0"),
    )
    signal_threshold: Decimal = ConfigVar(
        key="signal_threshold",
        prompt="Enter the minimum signal score (0-100) required to place orders >>> ",
        type_str="decimal",
        default=Decimal("50"),
    )


def strategy_config_to_dict(strategy_config: AdaptiveMarketMakingConfigMap) -> Dict[str, Any]:
    """
    Convert the strategy configuration to a dictionary that can be used to initialize the strategy.
    """
    return {
        "connector_name": strategy_config.connector_name,
        "trading_pair": strategy_config.trading_pair,
        "order_amount": strategy_config.order_amount,
        "min_spread": strategy_config.min_spread / Decimal("100"),  # Convert from percentage to decimal
        "max_spread": strategy_config.max_spread / Decimal("100"),  # Convert from percentage to decimal
        "order_refresh_time": strategy_config.order_refresh_time,
        "max_order_age": strategy_config.max_order_age,
        "rsi_length": strategy_config.rsi_length,
        "rsi_overbought": strategy_config.rsi_overbought,
        "rsi_oversold": strategy_config.rsi_oversold,
        "ema_short": strategy_config.ema_short,
        "ema_long": strategy_config.ema_long,
        "bb_length": strategy_config.bb_length,
        "bb_std": strategy_config.bb_std,
        "target_inventory_ratio": strategy_config.target_inventory_ratio,
        "min_order_amount": strategy_config.min_order_amount,
        "volatility_adjustment": strategy_config.volatility_adjustment,
        "trailing_stop_pct": strategy_config.trailing_stop_pct / Decimal("100"),  # Convert from percentage to decimal
        "signal_threshold": strategy_config.signal_threshold,
    }


def config_apply(strategy: ScriptStrategyBase, config_map: AdaptiveMarketMakingConfigMap, **kwargs):
    """
    Apply the configuration to the strategy object.
    """
    for key, value in strategy_config_to_dict(config_map).items():
        setattr(strategy, key, value)
    
    # Initialize markets
    market = strategy.markets.get(config_map.connector_name)
    if market is None:
        strategy.markets = {config_map.connector_name: {config_map.trading_pair}} 