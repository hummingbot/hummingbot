from decimal import Decimal
import os
from typing import Optional

# Using relative imports for Hummingbot modules
from hummingbot.client.config.config_data_types import BaseConfigMap, ConfigVar, required_exchanges
from hummingbot.client.config.config_validators import validate_decimal, validate_exchange, validate_trading_pair
from hummingbot.client.settings import AllConnectorSettings, required_exchanges

# Get the current script's directory to ensure relative paths work
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
CONFIG_DIR = os.path.dirname(SCRIPT_DIR)
SCRIPT_FILE_PATH = os.path.join(os.path.dirname(CONFIG_DIR), "scripts", "precision_trading.py")

def exchange_on_validated(value: str) -> Optional[str]:
    required_exchanges.append(value)
    return None

def validate_risk_level(value: str) -> Optional[str]:
    if value not in ["high", "medium", "low"]:
        return "Risk level must be one of: high, medium, low"
    return None

def validate_time_horizon(value: str) -> Optional[str]:
    if value not in ["short", "medium", "long"]:
        return "Time horizon must be one of: short, medium, long"
    return None

def trading_pair_prompt() -> str:
    exchange = "binance_perpetual"
    example = AllConnectorSettings.get_example_pairs().get(exchange)
    return "Enter the trading pair to trade on Binance Perpetual (e.g. %s) >>> " % example

def str2bool(value: str):
    return str(value).lower() in ("yes", "true", "t", "1")

class PrecisionTradingConfigMap(BaseConfigMap):
    KEY = "precision_trading"
    OTHER_DEFAULTS = {
        # Use path that can be resolved relative to current location
        "script_file_name": os.path.relpath(SCRIPT_FILE_PATH, os.path.join(CONFIG_DIR, "..")),
    }

    DEFAULTS = {
        "exchange": "binance_perpetual",
        "trading_pair": None,
        "risk_level": "medium",
        "time_horizon": "medium",
        "position_size_pct": 0.05,
        "leverage": 2,
        "rsi_length": 14,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "ema_short_len": 50,
        "ema_long_len": 200,
        "bb_length": 20,
        "bb_std": 2.0,
        "atr_length": 14,
        "sr_window": 10,
        "sr_group_threshold": 0.005,
        "update_interval": 60,
        "secondary_tf_update_multiplier": 5,
        "long_tf_update_multiplier": 15,
    }

    @classmethod
    def get_other_fields(cls):
        return {
            "exchange": ConfigVar(
                key="exchange",
                prompt="Enter the name of the exchange >>> ",
                validator=validate_exchange,
                on_validated=exchange_on_validated,
            ),
            "trading_pair": ConfigVar(
                key="trading_pair",
                prompt=trading_pair_prompt,
                validator=validate_trading_pair,
            ),
            "risk_level": ConfigVar(
                key="risk_level",
                prompt="Enter the risk level (high/medium/low) >>> ",
                validator=validate_risk_level,
                default="medium",
            ),
            "time_horizon": ConfigVar(
                key="time_horizon",
                prompt="Enter the time horizon (short/medium/long) >>> ",
                validator=validate_time_horizon,
                default="medium",
            ),
            "position_size_pct": ConfigVar(
                key="position_size_pct",
                prompt="Enter the position size as a percentage of available balance (e.g. 0.05 for 5%) >>> ",
                type_str="decimal",
                validator=lambda v: validate_decimal(v, min_value=0, max_value=1),
                default=0.05,
            ),
            "leverage": ConfigVar(
                key="leverage",
                prompt="Enter the leverage to use (1-10) >>> ",
                type_str="int",
                validator=lambda v: validate_decimal(v, min_value=1, max_value=10),
                default=2,
            ),
            "rsi_length": ConfigVar(
                key="rsi_length",
                prompt="Enter the RSI period length >>> ",
                type_str="int",
                validator=lambda v: validate_decimal(v, min_value=1),
                default=14,
            ),
            "macd_fast": ConfigVar(
                key="macd_fast",
                prompt="Enter the MACD fast period >>> ",
                type_str="int",
                validator=lambda v: validate_decimal(v, min_value=1),
                default=12,
            ),
            "macd_slow": ConfigVar(
                key="macd_slow",
                prompt="Enter the MACD slow period >>> ",
                type_str="int",
                validator=lambda v: validate_decimal(v, min_value=1),
                default=26,
            ),
            "macd_signal": ConfigVar(
                key="macd_signal",
                prompt="Enter the MACD signal period >>> ",
                type_str="int",
                validator=lambda v: validate_decimal(v, min_value=1),
                default=9,
            ),
            "ema_short_len": ConfigVar(
                key="ema_short_len",
                prompt="Enter the short EMA period >>> ",
                type_str="int",
                validator=lambda v: validate_decimal(v, min_value=1),
                default=50,
            ),
            "ema_long_len": ConfigVar(
                key="ema_long_len",
                prompt="Enter the long EMA period >>> ",
                type_str="int",
                validator=lambda v: validate_decimal(v, min_value=1),
                default=200,
            ),
            "bb_length": ConfigVar(
                key="bb_length",
                prompt="Enter the Bollinger Bands period >>> ",
                type_str="int",
                validator=lambda v: validate_decimal(v, min_value=1),
                default=20,
            ),
            "bb_std": ConfigVar(
                key="bb_std",
                prompt="Enter the Bollinger Bands standard deviation multiplier >>> ",
                type_str="decimal",
                validator=lambda v: validate_decimal(v, min_value=0),
                default=2.0,
            ),
            "atr_length": ConfigVar(
                key="atr_length",
                prompt="Enter the ATR period >>> ",
                type_str="int",
                validator=lambda v: validate_decimal(v, min_value=1),
                default=14,
            ),
            "sr_window": ConfigVar(
                key="sr_window",
                prompt="Enter the support/resistance window size >>> ",
                type_str="int",
                validator=lambda v: validate_decimal(v, min_value=1),
                default=10,
            ),
            "sr_group_threshold": ConfigVar(
                key="sr_group_threshold",
                prompt="Enter the support/resistance grouping threshold >>> ",
                type_str="decimal",
                validator=lambda v: validate_decimal(v, min_value=0),
                default=0.005,
            ),
            "update_interval": ConfigVar(
                key="update_interval",
                prompt="Enter the update interval in seconds >>> ",
                type_str="int",
                validator=lambda v: validate_decimal(v, min_value=1),
                default=60,
            ),
            "secondary_tf_update_multiplier": ConfigVar(
                key="secondary_tf_update_multiplier",
                prompt="Enter the secondary timeframe update multiplier >>> ",
                type_str="int",
                validator=lambda v: validate_decimal(v, min_value=1),
                default=5,
            ),
            "long_tf_update_multiplier": ConfigVar(
                key="long_tf_update_multiplier",
                prompt="Enter the long timeframe update multiplier >>> ",
                type_str="int",
                validator=lambda v: validate_decimal(v, min_value=1),
                default=15,
            ),
        }

    @classmethod
    def validate_config_map(cls, config_map: dict) -> Optional[str]:
        """
        Validates the config map.
        """
        if config_map.get("leverage") > config_map.get("max_leverage", 10):
            return "Leverage cannot be higher than max_leverage"
        return None

def get_connector_class(module_name: str):
    try:
        from importlib import import_module
        module = import_module(f"hummingbot.connector.{module_name}")
        return module.get_connector_class()
    except ImportError as e:
        print(f"Error importing connector module: {e}")
        # Fallback mechanism in case the module path changed
        try:
            module = import_module(module_name)
            return module.get_connector_class()
        except ImportError:
            raise ImportError(f"Could not import connector {module_name}")

def config_apply(strategy: "PrecisionTradingStrategy", config_map: PrecisionTradingConfigMap, **kwargs):
    """
    Apply the configuration to the strategy object.
    """
    for key, value in strategy_config_to_dict(config_map).items():
        setattr(strategy, key, value)
    
    # Initialize markets
    market = strategy.markets.get(config_map.exchange)
    if market is None:
        strategy.markets = {config_map.exchange: {config_map.trading_pair}}

def strategy_config_to_dict(config_map: PrecisionTradingConfigMap) -> dict:
    """
    Convert the config map to a dictionary that can be applied to the strategy.
    """
    return {
        "exchange": config_map.exchange,
        "trading_pair": config_map.trading_pair,
        "risk_level": config_map.risk_level,
        "time_horizon": config_map.time_horizon,
        "position_size_pct": config_map.position_size_pct,
        "leverage": config_map.leverage,
        "rsi_length": config_map.rsi_length,
        "macd_fast": config_map.macd_fast,
        "macd_slow": config_map.macd_slow,
        "macd_signal": config_map.macd_signal,
        "ema_short_len": config_map.ema_short_len,
        "ema_long_len": config_map.ema_long_len,
        "bb_length": config_map.bb_length,
        "bb_std": config_map.bb_std,
        "atr_length": config_map.atr_length,
        "sr_window": config_map.sr_window,
        "sr_group_threshold": config_map.sr_group_threshold,
        "update_interval": config_map.update_interval,
        "secondary_tf_update_multiplier": config_map.secondary_tf_update_multiplier,
        "long_tf_update_multiplier": config_map.long_tf_update_multiplier,
    } 