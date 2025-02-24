import logging
import time
from datetime import datetime
from decimal import Decimal
from test.hummingbot.strategy.amm_arb.test_utils import trading_pair
from typing import Dict, List, Optional, Set

import mysql.connector
import pandas_ta as ta  # noqa: F401
from mysql.connector.plugins import caching_sha2_password
from numpy.f2py.auxfuncs import throw_error
from pydantic import Field, validator

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.core.data_type.common import PriceType, TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.range_executor.data_types import RangingExecutorConfig
from hummingbot.strategy_v2.executors.scalping_executor.data_types import (
    ProfitTargetAction,
    ScalpingBoundExecutorConfig,
    ScalpingExecutorConfig,
    TripleBarrierConfig,
)
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction

# Create a module-level logger
logger = logging.getLogger(__name__)


class RangingConfig(ControllerConfigBase):
    controller_name: str = "ranging"

    candles_config: List[CandlesConfig] = []
    connector_name: str = Field(
        default="bybit_perpetual_test",
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter the name of the exchange to trade on (e.g., binance_perpetual):"))
    candles_connector: str = Field(
        default="bybit_perpetual",
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter the connector for the candles data, leave empty to use the same exchange as the connector: ",)
    )
    candles_trading_pair: str = Field(
        default="BTC-USDT",
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter the trading pair for the candles data, leave empty to use the same trading pair as the connector: ",)
    )
    max_executors_per_side: int = Field(
        default=2,
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter the maximum number of executors per side (e.g., 2):"))
    cooldown_time: int = Field(
        default=60 * 5, gt=0,
        client_data=ClientFieldData(
            is_updatable=True,
            prompt_on_new=False,
            prompt=lambda mi: "Specify the cooldown time in seconds after executing a signal (e.g., 300 for 5 minutes):"))
    # New field: seconds before the end of the candle interval to trigger an action.
    second_trigger: int = Field(
        default=3,
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter the number of seconds before the end of the interval to trigger an action:"))

    @validator("candles_connector", pre=True, always=True)
    def set_candles_connector(cls, v, values):
        if v is None or v == "":
            return values.get("connector_name")
        return v

    @validator("candles_trading_pair", pre=True, always=True)
    def set_candles_trading_pair(cls, v, values):
        if v is None or v == "":
            return values.get("trading_pair")
        return v

    def update_markets(self, markets: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
        logger.info(f"Updating markets: current connector_name = {self.connector_name}, "
                    f"candles_trading_pair = {self.candles_trading_pair}")
        if self.connector_name not in markets:
            logger.debug(f"Connector {self.connector_name} not found in markets, adding it.")
            markets[self.connector_name] = set()
        markets[self.connector_name].add(self.candles_trading_pair)
        logger.info(f"Updated markets: {markets}")
        return markets


class Ranging(ControllerBase):
    def __init__(self, config: RangingConfig, *args, **kwargs):
        self.config = config
        self.max_records = 50
        # Initialize last triggered candle index to None.
        self._last_triggered_candle_index = None
        if len(self.config.candles_config) == 0:
            self.config.candles_config = [CandlesConfig(
                connector=config.candles_connector,
                trading_pair=config.candles_trading_pair,
                interval="1m",
                max_records=self.max_records
            )]
        super().__init__(config, *args, **kwargs)

    async def update_processed_data(self):
        # Retrieve the latest candle data as a DataFrame.
        df = self.market_data_provider.get_candles_df(
            connector_name=self.config.candles_connector,
            trading_pair=self.config.candles_trading_pair,
            interval=self.config.candles_config[0].interval,
            max_records=self.max_records
        )

        current_ts = time.time()
        dt = datetime.fromtimestamp(current_ts)
        # Format timestamp as epoch with microsecond precision and as date/time including seconds.
        timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        if df is not None and not df.empty:
            current_candle = df.iloc[-1]
            logger.info(f"Timestamp: {current_ts:.6f} ({timestamp_str}) - Current Candle: {current_candle.to_dict()}")
        else:
            logger.warning("No candle data available to log.")

        # Check trigger condition.
        trigger_met = self.is_trigger()
        logger.info(f"Is trigger condition met? {trigger_met}")

        # If trigger condition is met, check the trade record.
        if trigger_met and df is not None and not df.empty:
            current_candle_dict = df.iloc[-1].to_dict()
            record_found, record_data = self.check_and_update_trade_record(current_candle_dict)
            if record_found:
                logger.info(f"Trade record found and updated: {record_data}")
                # Update the record_data with candle information.
                record_data["upperbound"] = current_candle_dict.get("high")
                record_data["lowerbound"] = current_candle_dict.get("low")
                # Set signal value: 1 for BUY, -1 for SELL.
                signal_value = 1 if self.config.side.upper() == "BUY" else -1
                logger.info(f"Prepared signal: {signal_value}")
                logger.info(f"Updated signal config (record data): {record_data}")
                self.processed_data["signal"] = signal_value
                self.processed_data["signal_config"] = record_data
                # Further processing of the signal can be done here.


    def parse_interval_seconds(self, interval: str) -> int:
        """
        Parses an interval string (e.g., '1m', '5m', '1h') into its equivalent number of seconds.
        """
        try:
            unit = interval[-1].lower()
            value = int(interval[:-1])
            if unit == "m":
                return value * 60
            elif unit == "h":
                return value * 3600
            elif unit == "s":
                return value
            else:
                logger.warning(f"Unrecognized interval unit: {unit}. Defaulting to seconds.")
                return value
        except Exception as e:
            logger.error(f"Error parsing interval '{interval}': {e}")
            return 60  # default to 60 seconds

    def is_trigger(self) -> bool:
        """
        Returns True if the current time is within `second_trigger` seconds before the end of the candle interval,
        and the trigger has not yet fired for the current candle.
        """
        interval_str = self.config.candles_config[0].interval
        interval_seconds = self.parse_interval_seconds(interval_str)
        current_ts = time.time()
        elapsed = current_ts % interval_seconds
        remaining = interval_seconds - elapsed
        logger.info(f"Current timestamp: {current_ts:.6f}. Elapsed in current interval: {elapsed}s, remaining: {remaining}s.")
        # Determine the index of the current candle (epoch-aligned)
        current_candle_index = int(current_ts // interval_seconds)
        if remaining <= self.config.second_trigger:
            if self._last_triggered_candle_index != current_candle_index:
                logger.info(f"Trigger condition met: remaining seconds ({remaining}) <= second_trigger ({self.config.second_trigger}).")
                self._last_triggered_candle_index = current_candle_index
                return True
            else:
                logger.debug("Trigger condition met but already triggered for the current candle.")
        return False

    def check_and_update_trade_record(self, candle_data: dict) -> (bool, Optional[RangingExecutorConfig]):
        """
        Checks if a row exists in the TRADE table with:
          STRATEGY = 'RANGING', STRATEGY_INTERVAL = '1M', STATUS = 'NEW', LOADED = 0.
        If such a row exists, updates it to set STATUS = 'PROCESSED' and LOADED = 1,
        then returns (True, record_data) where record_data is a TradeRecord instance.
        Otherwise, returns (False, None).
        """
        record_data = None
        try:
            # Adjust connection parameters as needed.
            conn = mysql.connector.connect(
                host="127.0.0.1",
                port=3306,
                user="scalping",
                password="scalping",
                database="scalping"
            )
            # Use a dictionary cursor to fetch records as dictionaries.
            cursor = conn.cursor(dictionary=True)
            query = (
                "SELECT * FROM TRADE "
                "WHERE STRATEGY = 'RANGING' AND STRATEGY_INTERVAL = '1M' AND STATUS = 'NEW' AND LOADED = 0 LIMIT 1"
            )
            cursor.execute(query)
            row = cursor.fetchone()
            if row:
                trade_id = row["id"]
                update_query = "UPDATE TRADE SET STATUS = 'PROCESSED', LOADED = 1 WHERE id = %s"
                cursor.execute(update_query, (trade_id,))
                conn.commit()
                logger.info(f"Trade record {trade_id} updated to PROCESSED and LOADED=1.")
                # Parse the row into a TradeRecord instance.
                from pydantic import ValidationError
                try:
                    record_data = RangingExecutorConfig.parse_obj(row)
                except ValidationError as ve:
                    logger.error(f"Error parsing trade record: {ve}")
                    return False, None
                return True, record_data
            else:
                logger.info("No matching trade record found.")
                return False, None
        except Exception as e:
            logger.error(f"Error checking/updating trade record: {e}")
            return False, None
        finally:
            try:
                cursor.close()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass

    def determine_executor_actions(self) -> List[ExecutorAction]:
        """
        Determine actions based on the processed signal.
        """
        actions = []
        actions.extend(self.create_actions_proposal())
        actions.extend(self.stop_actions_proposal())
        return actions

    def create_actions_proposal(self) -> List[ExecutorAction]:
        """
        Create executor actions based on orders stored in processed_data.
        Since orders are now generated only once and stored, they are passed directly.
        """
        create_actions = []
        signal = self.processed_data.get("signal", 0)
        signal_config = self.processed_data.get("signal_config", [])
        self.logger().info("create proposal:Signal from processed data: %s", signal)
        self.logger().info("create proposal:Number of orders in processed data: %d", len(orders))
        if signal != 0 and self.can_create_executor(signal) and orders:
            for order in orders:
                self.logger().info(
                    f"open price: {order.triple_barrier_config.open_order_price}, "
                    f"stop price: {order.triple_barrier_config.stop_loss_price}, "
                    f"take profit: {order.triple_barrier_config.take_profit_price}, "
                    f"leverage: {order.amount}"
                )
                create_actions.append(
                    CreateExecutorAction(
                        controller_id=self.config.id,
                        executor_config=order
                    )
                )
        return create_actions

    def stop_actions_proposal(self) -> List[ExecutorAction]:
        """
        Stop actions based on the provided executor handler report.
        """
        return []
