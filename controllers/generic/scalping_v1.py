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
from hummingbot.strategy_v2.executors.scalping_executor.data_types import (
    ProfitTargetAction,
    ScalpingBoundExecutorConfig,
    ScalpingExecutorConfig,
    TripleBarrierConfig,
)
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction


class ScalpingConfig(ControllerConfigBase):
    controller_name: str = "scalping_v1"

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
            prompt=lambda
                mi: "Enter the connector for the candles data, leave empty to use the same exchange as the connector: ", )
    )
    candles_trading_pair: str = Field(
        default="BTC-USDT",
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda
                mi: "Enter the trading pair for the candles data, leave empty to use the same trading pair as the connector: ", )
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
            prompt=lambda
                mi: "Specify the cooldown time in seconds after executing a signal (e.g., 300 for 5 minutes):"))

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
        if self.connector_name not in markets:
            markets[self.connector_name] = set()
        markets[self.connector_name].add(self.candles_trading_pair)
        return markets


class Scalping(ControllerBase):
    def __init__(self, config: ScalpingConfig, *args, **kwargs):
        self.config = config
        self.max_records = 50
        if len(self.config.candles_config) == 0:
            self.config.candles_config = [CandlesConfig(
                connector=config.candles_connector,
                trading_pair=config.candles_trading_pair,
                interval="1m",
                max_records=self.max_records
            )]
        super().__init__(config, *args, **kwargs)

    async def update_processed_data(self):
        """
        Process trades from the TRADE table.

        For trades with STATUS = "NEW":
          - Check if the trade already contains orders.
            If so, remove any existing orders linked to the trade.
          - Validate the order configuration.
          - If valid, obtain the current market price and generate orders.
          - Insert the generated orders into the TRADE_ORDER table with STATUS = "TO_BE_CONFIRMED".
          - Update the trade status to "TO_BE_CONFIRMED".
          - No signal is sent at this point.

        For trades with STATUS = "CONFIRMED":
          - Retrieve orders from the TRADE_ORDER table (with STATUS = "TO_BE_CONFIRMED").
          - Update both the TRADE and TRADE_ORDER statuses to "PROCESSED".
          - Pass the stored orders directly as the signal.
        """
        self.processed_data["signal"] = 0
        self.processed_data.pop("orders", None)  # Clear any previous orders
        cnx = mysql.connector.connect(
            host="127.0.0.1",
            port=3306,
            user="scalping",
            password="scalping",
            database="scalping"
        )
        cur = cnx.cursor(dictionary=True)

        # Select trades with STATUS in ('NEW', 'CONFIRMED')
        cur.execute(
            "SELECT ID, PAIR, DIRECTION, UPPER_BOUND, LOWER_BOUND, STOP_LOSS, TP_PERCENTAGE, STOP_LOSS_FACTOR, "
            "TAKER_FEE_PERCENTAGE,MAKER_FEE_PERCENTAGE, ACTION_ON_TP, MAX_LOSS, TP_PRICE, QTY, STATUS "
            "FROM TRADE WHERE STATUS IN ('NEW', 'CONFIRMED')"
        )
        trades = cur.fetchall()

        for row in trades:
            if row["DIRECTION"] == 'BUY':
                side = TradeType.BUY
            elif row["DIRECTION"] == 'SELL':
                side = TradeType.SELL
            else:
                raise RuntimeError("wrong side in db")

            scalping_config = ScalpingBoundExecutorConfig(
                timestamp=self.market_data_provider.time(),
                connector_name=self.config.connector_name,
                trading_pair=row["PAIR"],
                side=side,
                upper_bound=row["UPPER_BOUND"],
                lower_bound=row["LOWER_BOUND"],
                stop_price=row["STOP_LOSS"],
                profit_target_action=ProfitTargetAction(
                    percentage=row["TP_PERCENTAGE"],
                    stop_loss_factor=row["STOP_LOSS_FACTOR"],
                    taker_fee_percentage=Decimal(row["TAKER_FEE_PERCENTAGE"]),
                    maker_fee_percentage=Decimal(row["MAKER_FEE_PERCENTAGE"]),
                    action=row["ACTION_ON_TP"],
                    tp_price=row["TP_PRICE"],
                ),
                max_loss=row["MAX_LOSS"],
                price=0,
                qty=row["QTY"]
            )
            trade_status = row["STATUS"]

            if trade_status == "NEW":
                # If orders already exist for this trade, remove them.
                cur.execute("SELECT COUNT(*) AS order_count FROM TRADE_ORDER WHERE TRADE_ID = %s", (row["ID"],))
                count_row = cur.fetchone()
                if count_row and count_row["order_count"] > 0:
                    cur.execute("DELETE FROM TRADE_ORDER WHERE TRADE_ID = %s", (row["ID"],))

                # Validate the order configuration.
                if not self._validate_order_config(scalping_config.upper_bound,
                                                   scalping_config.lower_bound,
                                                   scalping_config.stop_price,
                                                   scalping_config.side):
                    update_trade_sql = "UPDATE TRADE SET STATUS = %s WHERE ID = %s"
                    cur.execute(update_trade_sql, ("INVALID", row["ID"]))
                    continue  # Skip processing if invalid.


                # Generate orders and insert them into TRADE_ORDER with status "TO_BE_CONFIRMED".
                orders = self._generate_orders_from_signal(
                    scalping_config.profit_target_action,
                    scalping_config.max_loss,
                    self.config.max_executors_per_side,
                    scalping_config.trading_pair,
                    scalping_config.side,
                    scalping_config.qty,
                    scalping_config.upper_bound,
                    scalping_config.lower_bound,
                    scalping_config.stop_price,
                    scalping_config.profit_target_action.taker_fee_percentage,
                    scalping_config.profit_target_action.maker_fee_percentage
                )
                # Inside the loop over orders in update_processed_data, when status is "NEW":
                for order in orders:
                    order_config_json = order.json()  # Serialize the full configuration as JSON.
                    # Prepare the additional fields.
                    # If order.side is an enum (e.g., TradeType), you may want to use order.side.value.
                    amount_str = str(order.amount)
                    trading_pair_val = order.trading_pair
                    side_val = order.side.value if hasattr(order.side, "value") else order.side

                    insert_sql = (
                        "INSERT INTO TRADE_ORDER (TRADE_ID, ORDER_CONFIG, AMOUNT, TRADING_PAIR, SIDE, STATUS) "
                        "VALUES (%s, %s, %s, %s, %s, %s)"
                    )
                    cur.execute(insert_sql, (
                    row["ID"], order_config_json, amount_str, trading_pair_val, side_val, "TO_BE_CONFIRMED"))
                    update_trade_sql = "UPDATE TRADE SET STATUS = %s WHERE ID = %s"
                    cur.execute(update_trade_sql, ("TO_BE_CONFIRMED", row["ID"]))
            elif trade_status == "CONFIRMED":
                self.logger().info(
                    f"trade status: {trade_status}"
                )
                # Retrieve orders for this trade that are still "TO_BE_CONFIRMED".
                cur.execute("SELECT * FROM TRADE_ORDER WHERE TRADE_ID = %s AND STATUS = %s",
                            (row["ID"], "TO_BE_CONFIRMED"))
                order_rows = cur.fetchall()
                if order_rows:
                    # Update statuses to "PROCESSED".
                    update_trade_sql = "UPDATE TRADE SET STATUS = %s WHERE ID = %s"
                    cur.execute(update_trade_sql, ("PROCESSED", row["ID"]))
                    update_order_sql = "UPDATE TRADE_ORDER SET STATUS = %s WHERE TRADE_ID = %s AND STATUS = %s"
                    cur.execute(update_order_sql, ("PROCESSED", row["ID"], "TO_BE_CONFIRMED"))

                    # Reconstruct orders from stored JSON.
                    orders = []
                    for order_row in order_rows:
                        order = ScalpingExecutorConfig.parse_raw(order_row["ORDER_CONFIG"])
                        orders.append(order)
                    signal = 1 if scalping_config.side == TradeType.BUY else -1
                    self.logger().info("create proposal:Signal from processed data: %s", signal)
                    self.logger().info("create proposal:Number of orders in processed data: %d", len(orders))
                    self.processed_data["signal"] = signal
                    # Pass the stored orders directly as part of the signal.
                    self.processed_data["orders"] = orders
                    self.processed_data["signal_config"] = scalping_config

        cnx.commit()
        cnx.close()

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
        orders = self.processed_data.get("orders", [])
        self.logger().debug("create proposal:Signal from processed data: %s", signal)
        self.logger().debug("create proposal:Number of orders in processed data: %d", len(orders))
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

    def _validate_order_config(self, upper_bound, lower_bound, stop_price, side) -> bool:
        """
        Validate the order bounds and stop price based on the trade side.
        Returns True if the configuration is valid; otherwise, logs the issue and returns False.
        """
        if upper_bound < lower_bound:
            self.logger().info("Upper bound is lower than lower bound, no action taken")
            return False
        if side == TradeType.BUY:
            if lower_bound < stop_price:
                self.logger().info(
                    f"Wrong configuration, no action taken: lower bound: {lower_bound}, "
                    f"upper_bound: {upper_bound}, stop price: {stop_price}"
                )
                return False
        elif side == TradeType.SELL:
            if upper_bound > stop_price:
                self.logger().info(
                    f"Wrong configuration, no action taken: lower bound: {lower_bound}, "
                    f"upper_bound: {upper_bound}, stop price: {stop_price}"
                )
                return False
        return True

    def _generate_orders_from_signal(self, action, max_loss, max_order_number, trading_pair, side, qty, upper_bound, lower_bound,stop_price,taker_fee_percentage,maker_fee_percentage) -> List[
        ScalpingExecutorConfig]:
        """
        Generate and return a list of order configurations based on the provided signal parameters.
        This method returns ScalpingExecutorConfig objects without wrapping them into executor actions.
        """

        orders = self.create_orders_within_bounds(
            upper_bound, lower_bound, action, stop_price, max_loss,
            max_order_number, trading_pair, side,taker_fee_percentage,maker_fee_percentage
        )
        return orders

    def stop_actions_proposal(self) -> List[ExecutorAction]:
        """
        Stop actions based on the provided executor handler report.
        """
        return []

    def create_orders_within_bounds(self, upper_bound, lower_bound, profit_target_action, stop_price, max_loss,
                                    max_order_number, local_trading_pair, trade_type, taker_fee_percentage,maker_fee_percentage) -> List[
        ScalpingExecutorConfig]:
        """
        Create orders within the given price bounds, distributing leverage across orders.
        """
        self.logger().info(
            f"Creating orders: Upper Bound: {upper_bound}, Lower Bound: {lower_bound}, "
            f"TP: {profit_target_action}, Stop Price: {stop_price}, Max Loss: {max_loss}, "
            f"Max Orders: {max_order_number}, Taker Fee: {taker_fee_percentage} Maker Fee: {maker_fee_percentage}"
        )
        orders = []
        price_range = Decimal(upper_bound) - Decimal(lower_bound)


        if max_order_number <= 0:
            self.logger().info("Invalid bounds or max order number.")
            raise ValueError("Invalid bounds or number of orders.")

        if upper_bound == lower_bound:
            scalping_executor_config = self.calculate_order_value(
                lower_bound, stop_price, max_loss, taker_fee_percentage, trade_type,
                profit_target_action, local_trading_pair
            )
            if scalping_executor_config:
                orders.append(scalping_executor_config)
                self.logger().info(f"Single order generated: {scalping_executor_config}")
                return orders

        step = price_range / Decimal(max_order_number - 1)
        risk_per_order = Decimal(max_loss) / Decimal(max_order_number)
        self.logger().info(f"Price Range: {price_range}, Step: {step}, Risk per Order: {risk_per_order}")

        for i in range(max_order_number):
            order_price = Decimal(lower_bound) + (Decimal(i) * step)
            scalping_executor_config = self.calculate_order_value(
                order_price, stop_price, risk_per_order, taker_fee_percentage, trade_type,
                profit_target_action, local_trading_pair
            )
            if scalping_executor_config:
                orders.append(scalping_executor_config)
                self.logger().info(f"Order {i + 1} generated: {scalping_executor_config}")
        return orders

    def calculate_order_value(self, order_price, stop_price, risk_per_order, taker_fee_decimal, trade_type,
                              profit_target_action, local_trading_pair) -> Optional[ScalpingExecutorConfig]:
        distance_to_stop = abs(order_price - Decimal(stop_price))
        if distance_to_stop == 0:
            self.logger().info(
                f"Error: Stop price equals order price (order_price: {order_price}, stop price: {stop_price}, "
                f"risk per order: {risk_per_order}, taker fee: {taker_fee_decimal})"
            )
            raise ValueError("Stop price cannot be the same as order price.")
        self.logger().info(f"Order price: {order_price}, Risk per Order: {risk_per_order}")
        temporary_size = risk_per_order / distance_to_stop
        order_size_in_usdt = order_price * temporary_size
        fee_ = taker_fee_decimal * order_size_in_usdt
        adjusted_risk = risk_per_order - fee_
        self.logger().info(
            f"Temporary size: {temporary_size}, Order size in USDT: {order_size_in_usdt}, "
            f"Fee: {fee_}, Adjusted risk: {adjusted_risk}"
        )
        if adjusted_risk <= 0:
            self.logger().info(
                f"Error: Non-positive adjusted risk for order_price: {order_price}, stop price: {stop_price}, "
                f"risk per order: {risk_per_order}, taker fee: {taker_fee_decimal}"
            )
            return None

        leverage = adjusted_risk / distance_to_stop
        size = leverage  # For simplicity; adjust as needed.
        barrier_config = TripleBarrierConfig(
            stop_loss_price=Decimal(stop_price),
            open_order_price=order_price
        )
        return ScalpingExecutorConfig(
            timestamp=self.market_data_provider.time(),
            connector_name=self.config.connector_name,
            trading_pair=local_trading_pair,
            side=trade_type,
            amount=size,
            action="",
            triple_barrier_config=barrier_config,
            profit_target_action=profit_target_action
        )

    def can_create_executor(self, signal: int) -> bool:
        active_executors_by_signal_side = self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda x: x.is_active and (x.side == TradeType.BUY)
        )
        for executor in active_executors_by_signal_side:
            self.logger().info(
                f"Active executor - Side: {executor.side}, Amount: {executor.config.amount}, "
                f"Trading Pair: {executor.trading_pair}, Timestamp: {executor.timestamp}"
            )
        return True
