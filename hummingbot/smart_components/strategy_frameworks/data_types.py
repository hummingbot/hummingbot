from decimal import Decimal
from enum import Enum
from typing import Dict, Optional

import pandas as pd
from pydantic import BaseModel, validator

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.executors.dca_executor.data_types import DCAConfig
from hummingbot.smart_components.executors.position_executor.data_types import PositionConfig


class ExecutorHandlerStatus(Enum):
    NOT_STARTED = 1
    ACTIVE = 2
    TERMINATED = 3


class TripleBarrierConf(BaseModel):
    # Configure the parameters for the position
    stop_loss: Optional[Decimal]
    take_profit: Optional[Decimal]
    time_limit: Optional[int]
    trailing_stop_activation_price_delta: Optional[Decimal]
    trailing_stop_trailing_delta: Optional[Decimal]
    # Configure the parameters for the order
    open_order_type: OrderType = OrderType.LIMIT
    take_profit_order_type: OrderType = OrderType.MARKET
    stop_loss_order_type: OrderType = OrderType.MARKET
    time_limit_order_type: OrderType = OrderType.MARKET


class OrderLevel(BaseModel):
    level: int
    side: TradeType
    order_amount_usd: Decimal
    spread_factor: Decimal = Decimal("0.0")
    order_refresh_time: int = 60
    cooldown_time: int = 0
    triple_barrier_conf: TripleBarrierConf

    @property
    def level_id(self):
        return f"{self.side.name}_{self.level}"

    @validator("order_amount_usd", "spread_factor", pre=True, allow_reuse=True)
    def float_to_decimal(cls, v):
        return Decimal(v)


class ExecutorHandlerReport(BaseModel):
    status: ExecutorHandlerStatus
    active_position_executors: pd.DataFrame
    active_position_executors_info: Dict
    closed_position_executors_info: Dict
    active_dca_executors: pd.DataFrame

    @validator('active_position_executors', 'active_dca_executors', allow_reuse=True)
    def validate_dataframe(cls, v):
        if not isinstance(v, pd.DataFrame):
            raise ValueError('active_executors must be a pandas DataFrame')
        return v

    class Config:
        arbitrary_types_allowed = True


class DataRequest(BaseModel):
    """
    Base class for data requests.
    """
    pass


class CandlesRequest(DataRequest):
    """
    Request for candlestick data using CandlesConfig.
    """
    config: CandlesConfig

    class Config:
        schema_extra = {
            "example": {
                "config": {
                    "connector": "binance",
                    "trading_pair": "BTC-USD",
                    "interval": "1m",
                    "max_records": 500
                }
            }
        }


class ActiveExecutorsInfoRequest(DataRequest):
    """
    Request for information about active executors.
    """
    # Additional fields can be added here if needed for specific requests.

    class Config:
        schema_extra = {
            "example": {}
        }


class StoredExecutorsInfoRequest(DataRequest):
    """
    Request for information about stored executors.
    """
    # Additional fields can be added here if needed for specific requests.

    class Config:
        schema_extra = {
            "example": {}
        }


class BotAction(BaseModel):
    """
    Base class for bot actions.
    """
    pass


class CreatePositionExecutorAction(BotAction):
    """
    Action to create an executor.
    """
    level_id: str
    position_config: PositionConfig

    class Config:
        schema_extra = {
            "example": {
                "level_id": "BUY_1",
                "position_config": {
                    "timestamp": 0,
                    "trading_pair": "BTC-USDT",
                    "exchange": "binance",
                    "side": "BUY",
                    "amount": 100,
                    "take_profit": 0.0,
                    "stop_loss": 0.0,
                    "trailing_stop": {
                        "activation_price_delta": 0.0,
                        "trailing_delta": 0.0
                    },
                    "time_limit": 0,
                    "entry_price": 0.0,
                    "open_order_type": "LIMIT",
                    "take_profit_order_type": "MARKET",
                    "stop_loss_order_type": "MARKET",
                    "time_limit_order_type": "MARKET",
                    "leverage": 1
                }
            }
        }


class StopExecutorAction(BotAction):
    """
    Action to stop an executor.
    """
    executor_id: str

    class Config:
        schema_extra = {
            "example": {
                "executor_id": "executor_1"
            }
        }


class StoreExecutorAction(BotAction):
    """
    Action to store an executor.
    """
    executor_id: str

    class Config:
        schema_extra = {
            "example": {
                "executor_id": "executor_1"
            }
        }


class CreateDCAExecutorAction(BotAction):
    """
    Action to create a DCA executor.
    """
    dca_config: DCAConfig
    dca_id: str

    class Config:
        schema_extra = {
            "example": {
                "dca_config": {
                    "id": "dca_1",
                    "timestamp": 0,
                    "exchange": "binance",
                    "trading_pair": "BTC-USDT",
                    "side": "BUY",
                    "initial_price": 0.0,
                    "order_levels": [
                        {
                            "level": 1,
                            "side": "BUY",
                            "order_amount_usd": 100,
                            "spread_factor": 0.0,
                            "order_refresh_time": 60,
                            "cooldown_time": 0,
                            "triple_barrier_conf": {
                                "time_limit": 240000,
                                "open_order_type": "LIMIT",
                                "take_profit_order_type": "MARKET",
                                "stop_loss_order_type": "MARKET",
                                "time_limit_order_type": "MARKET"
                            }
                        }
                    ],
                    "global_take_profit": 0.05,
                    "global_stop_loss": 0.05,
                    "global_trailing_stop": {
                        "activation_price_delta": 0.025,
                        "trailing_delta": 0.005
                    },
                    "time_limit": 240000,
                    "activation_threshold": 0.01,
                    "open_order_type": "LIMIT",
                    "take_profit_order_type": "MARKET",
                    "stop_loss_order_type": "MARKET",
                    "time_limit_order_type": "MARKET",
                    "leverage": 1
                },
                "dca_id": "BUY_1"
            }
        }


class StopDCAExecutorAction(BotAction):
    """
    Action to stop a DCA executor.
    """
    dca_id: str

    class Config:
        schema_extra = {
            "example": {
                "dca_id": "dca_1"
            }
        }


class StoreDCAExecutorAction(BotAction):
    """
    Action to store a DCA executor.
    """
    dca_id: str

    class Config:
        schema_extra = {
            "example": {
                "dca_id": "dca_1"
            }
        }
