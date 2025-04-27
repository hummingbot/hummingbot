# -*- coding: utf-8 -*-

from decimal import Decimal
from enum import StrEnum
from typing import List

import pandas as pd
from pydantic import Field

from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.core.data_type.common import OrderType, PositionAction, PriceType, TradeType
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy_v2.controllers.directional_trading_controller_base import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
)
from hummingbot.strategy_v2.executors.data_types import PositionSummary
from hummingbot.strategy_v2.executors.order_executor.data_types import ExecutionStrategy, OrderExecutorConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction, StopExecutorAction
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo

from .lp_management import (
    GatewayConnectionInfo,
    NoPoolAddress,
    NoPositionAddress,
    Pool,
    PoolConnectionError,
    PoolError,
    PoolType,
    check_gateway_status,
)


class RebalanceType(StrEnum):
    """
    Enum for rebalance types.
    """

    NOT_NEEDED = "not_needed"
    PERFORMING = "performing"
    NEEDED_BUT_TRADING_RULES_NOT_MET = "needed_but_trading_rules_not_met"


class LpHedgingControllerConfig(DirectionalTradingControllerConfigBase):
    controller_name: str = "lp_hedging"

    pool_address: str = Field(
        default="",
        json_schema_extra={
            "prompt": "Enter the pool address "
            "(e.g. 58oQChx4yWmvKdwLLZzBi4ChoCc2fqCUWBkwMihLYQo2): ",
            "prompt_on_new": True,
        },
    )

    connector: str = Field(
        default="raydium/clmm",
        json_schema_extra={
            "prompt": "AMM Connector (e.g. meteora/amm, raydium/amm)",
            "prompt_on_new": True,
        },
    )

    chain: str = Field(
        default="solana",
        json_schema_extra={
            "prompt": "Chain (e.g. solana)",
            "prompt_on_new": False,
        },
    )

    network: str = Field(
        default="mainnet-beta",
        json_schema_extra={
            "prompt": "Network (e.g. mainnet-beta)",
            "prompt_on_new": False,
        },
    )

    rebalance_pct: float = Field(
        default=0.05,
        json_schema_extra={
            "prompt": "Enter the rebalance percentage (e.g. 0.05): ",
            "prompt_on_new": True,
            "is_updatable": True,
        },
    )

    fetch_pool_info_interval: int = Field(
        default=5,
        json_schema_extra={
            "prompt": "Enter the interval to fetch pool info (in seconds): ",
            "prompt_on_new": True,
            "is_updatable": True,
        },
    )

    use_current_short_size: bool = Field(
        default=False,
        json_schema_extra={
            "prompt": "Use current short size as hedge (e.g. True): ",
            "prompt_on_new": True,
            "is_updatable": True,
        },
    )

    open_pool_if_not_found: bool = Field(
        default=False,
        json_schema_extra={
            "prompt": "Open pool if not found (e.g. True): ",
            "prompt_on_new": True,
            "is_updatable": True,
        },
    )

    base_amount: float = Field(
        default=0,
        json_schema_extra={
            "prompt": "Enter the base amount to open the pool (e.g. 100): ",
            "prompt_on_new": True,
            "is_updatable": True,
        },
    )

    quote_amount: float = Field(
        default=0,
        json_schema_extra={
            "prompt": "Enter the quote amount to open the pool (e.g. 100): ",
            "prompt_on_new": True,
            "is_updatable": True,
        },
    )

    lower_bound: float = Field(
        default=0,
        json_schema_extra={
            "prompt": "Enter the lower bound for the pool (e.g. 0): ",
            "prompt_on_new": True,
            "is_updatable": True,
        },
    )

    upper_bound: float = Field(
        default=0,
        json_schema_extra={
            "prompt": "Enter the upper bound for the pool (e.g. 0): ",
            "prompt_on_new": True,
            "is_updatable": True,
        },
    )

    close_short_on_stop: bool = Field(
        default=False,
        json_schema_extra={
            "prompt": "Close short position on stop (e.g. True): ",
            "prompt_on_new": True,
            "is_updatable": True,
        },
    )

    close_pool_position_on_stop: bool = Field(
        default=False,
        json_schema_extra={
            "prompt": "Close pool position on stop (e.g. True): ",
            "prompt_on_new": True,
            "is_updatable": True,
        },
    )

    is_pool_amm: bool = Field(
        default=False,
        json_schema_extra={
            "prompt": "Is the pool an AMM (e.g. True): ",
            "prompt_on_new": True,
            "is_updatable": True,
        },
    )


class LpHedgingError(Exception):
    pass


class LpHedgingNotReady(LpHedgingError, ConnectionError):
    pass


class PoolNotExisting(LpHedgingError, ValueError):
    pass


def calculate_apr_apy(
    initial_value: Decimal,
    current_value: Decimal,
    time_period_sec: float,
) -> tuple[Decimal, Decimal]:
    """
    Calculate APR and APY (assuming continuous compounding) based on initial and current values over a time period.

    Args:
        initial_value (Decimal): The starting principal amount.
        current_value (Decimal): The ending amount after interest.
        time_period_sec (float): Elapsed time in seconds.

    Returns:
        tuple[Decimal, Decimal]: A tuple containing:
            - APR as a percentage (Decimal)
            - APY as a percentage (Decimal, continuous compounding)
    """
    # Convert seconds in a year to Decimal
    # Compute simple rate over period
    rate_over_period = (current_value / initial_value) - Decimal(1)

    # APR: annualize the simple rate
    apr = (
        rate_over_period
        * 365
        / (Decimal(time_period_sec) / (Decimal(24) * Decimal(3600)))
    ) * Decimal(100)

    # APY: continuous compounding: exp(apr_fraction) - 1, then percentage
    apr_fraction = apr / Decimal(100)
    apy_fraction = apr_fraction.exp() - Decimal(1)
    apy = apy_fraction * Decimal(100)

    return apr, apy


class LpHedgingController(DirectionalTradingControllerBase):
    def __init__(self, config: LpHedgingControllerConfig, *args, **kwargs) -> None:  # type: ignore
        self.config = config
        super().__init__(config, *args, **kwargs)  # type: ignore
        self.gw_connection_info = GatewayConnectionInfo(
            connector=self.config.connector,
            chain=self.config.chain,
            network=self.config.network,
        )
        self.gw_status = None
        self.pool: Pool = Pool(
            gw_info=self.gw_connection_info,
            pool_address=self.config.pool_address,
            pool_type=PoolType.AMM if self.config.is_pool_amm else PoolType.CLMM,
        )
        self.last_update = 0
        self.cur_base_token_amount = Decimal(0)
        self.cur_quote_token_amount = Decimal(0)
        self.lower_bound = Decimal(0)
        self.upper_bound = Decimal(0)
        self.current_price = Decimal(0)
        self.hedging_amount = Decimal(0)
        self.base_value_usd = Decimal(0)
        self.base = self.config.trading_pair.split("-")[0]
        self.current_hedging_usd = Decimal(0)
        self.processed_data = {
            "signal": 0,
            "hedge_amount": 0,
            "stop_hedging": False,
            "position_action": PositionAction.CLOSE,
            "features": pd.DataFrame(),
        }
        self.initial_total_value_usd: Decimal | None = None
        self.initial_portfolio_value: Decimal | None = None
        self.entry_price: Decimal | None = None
        self.entry_datetime: float | None = None
        self.position_summary = None
        self.trading_rules = self.market_data_provider.get_connector(
            self.config.connector_name
        ).trading_rules[self.config.trading_pair]
        self.total_value_usd = Decimal(0)
        self.divergence_pct = Decimal(0)
        self.hedging_pnl = Decimal(0)
        self.calculated_margin = Decimal(0)
        self.total_portfolio_value = Decimal(0)
        self.rebalance_type = RebalanceType.NOT_NEEDED
        self.last_opening_attempt = 0
        self.profitability = Decimal(0)
        self.cumulative_fees = Decimal(0)
        self.num_short_adjustments = 0

    async def get_pool_info(self):
        self.gw_status = await check_gateway_status(
            self.gw_connection_info, self.logger()
        )
        if not self.gw_status.gateway_ready:
            raise LpHedgingNotReady(f"Gateway not connected: {self.gw_connection_info}")
        self.pool.wallet_address = self.gw_status.wallet_address

        try:
            await self.pool.fetch_pool_info()
            if self.config.is_pool_amm:
                if not self.pool.positions_owned:
                    raise NoPoolAddress(
                        f"Pool address not found: {self.config.pool_address} "
                        f"for pool address: {self.config.pool_address}"
                    )
                if not self.pool.positions_owned[0].get("lpTokenAmount"):
                    raise NoPositionAddress(
                        "No liquidity found in the pool, please add some liquidity"
                    )
        except PoolConnectionError as e:
            exc_description = f"Network error connecting to Gateway server: {str(e)}"
            self.logger().error(exc_description)
            raise LpHedgingNotReady(exc_description) from e
        except NoPoolAddress as e:
            exc_description = (
                f"Pool address not found: {self.config.pool_address} "
                f"for pool address: {self.config.pool_address}"
            )
            self.logger().error(exc_description)
            raise LpHedgingNotReady(exc_description) from e
        except NoPositionAddress as e:
            if self.config.open_pool_if_not_found:
                if self.market_data_provider.time() - self.last_opening_attempt < 180:
                    raise LpHedgingNotReady(
                        "Pool not found, but opening a new pool is not allowed yet."
                    ) from e
                self.logger().warning(
                    f"Pool not found, opening new pool: {self.config.pool_address}"
                )
                try:
                    self.last_opening_attempt = self.market_data_provider.time()
                    await self.pool.open_position(
                        base_amount=self.config.base_amount,
                        quote_amount=self.config.quote_amount,
                        lower_bound=self.config.lower_bound,
                        upper_bound=self.config.upper_bound,
                    )
                except PoolError as e2:
                    exc_description = (
                        f"Error opening new pool: {str(e2)} "
                        f"for pool address: {self.config.pool_address}"
                    )
                    self.logger().error(exc_description)
                    raise LpHedgingNotReady(exc_description) from e2

            else:
                exc_description = (
                    "Error processing pool data "
                    f"probably non-existing: {str(e)}"
                    f" for pool address: {self.config.pool_address} "
                    "and not allowed to open a new pool."
                )
                self.logger().error(exc_description)
                raise PoolNotExisting(exc_description) from e
        self.last_update = self.market_data_provider.time()

        if self.pool.positions_owned:
            cur_position = self.pool.positions_owned[0]
            self.cur_base_token_amount = Decimal(cur_position["baseTokenAmount"])
            self.cur_quote_token_amount = Decimal(cur_position["quoteTokenAmount"])
            if not self.config.is_pool_amm:
                self.lower_bound = Decimal(cur_position["lowerPrice"])
                self.upper_bound = Decimal(cur_position["upperPrice"])

    def get_executor_config(  # type: ignore
        self,
        trade_type: TradeType,
        price: Decimal,
        amount: Decimal,
    ):
        return OrderExecutorConfig(
            timestamp=self.market_data_provider.time(),
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            side=trade_type,
            amount=Decimal(amount),
            leverage=self.config.leverage,
            price=Decimal(price),
            execution_strategy=ExecutionStrategy.MARKET,
            position_action=self.processed_data["position_action"],  # type: ignore
        )

    def create_actions_proposal(self) -> List[ExecutorAction]:
        """
        Create actions based on the provided executor handler report.
        """
        create_actions = []
        signal: int = self.processed_data["signal"]
        if signal != 0 and self.can_create_executor(signal):  # type: ignore
            self.num_short_adjustments += 1
            price = Decimal(
                self.market_data_provider.get_price_by_type(  # type: ignore
                    self.config.connector_name,
                    self.config.trading_pair,
                    PriceType.MidPrice,
                )
            )
            # Default implementation distribute the total amount equally among the executors
            amount = Decimal(self.processed_data["hedge_amount"]) / Decimal(  # type: ignore
                self.config.max_executors_per_side
            )
            trade_type = TradeType.BUY if signal > 0 else TradeType.SELL

            create_actions.append(
                CreateExecutorAction(
                    controller_id=self.config.id,
                    executor_config=self.get_executor_config(
                        trade_type,
                        price,  # type: ignore
                        amount,  # type: ignore
                    ),
                )
            )
            self.logger().info(
                f"Create actions proposal: {create_actions}, signal: {signal}, "
                f"hedge amount: {self.processed_data['hedge_amount']}, "
                f"for price: {price}, "
                f"base token amount: {amount}, "
                f"quote token amount: {self.cur_quote_token_amount}, "
            )
        return create_actions

    def is_pool_in_range(self) -> bool:
        """
        Check if the pool is in range.
        """
        return (
            self.pool.pool_info.last_price >= self.lower_bound
            and self.pool.pool_info.last_price <= self.upper_bound
        )

    async def update_processed_data(self):
        cur_signal = 0
        cur_time = self.market_data_provider.time()

        n_active_executors = sum(
            1 for executor in self.executors_info if executor.is_active
        )
        if (
            n_active_executors == 0
            and cur_time - self.last_update > self.config.fetch_pool_info_interval
        ):
            # get value in USD from Oracle
            self.current_price = RateOracle.get_instance().get_pair_rate(
                f"{self.base}-USDT"
            )
            if self.entry_price is None:
                self.entry_price = self.current_price
            if self.entry_datetime is None:
                self.entry_datetime = cur_time
            self.logger().debug(
                "Current price from Rate Oracle: %s", self.current_price
            )
            if self.current_price is None:  # type: ignore
                self.logger().error("Price not found in Rate Oracle")
                return
            try:
                await self.get_pool_info()
            except LpHedgingError as e:
                self.logger().error("Error fetching pool info: %s", str(e))
                return
            self.base_value_usd = self.cur_base_token_amount * self.current_price
            self.hedging_amount = Decimal(0)
            self.current_hedging_usd = Decimal(0)
            self.rebalance_type = RebalanceType.NOT_NEEDED
            self.position_summary = self.get_position_summary()
            if self.position_summary:
                self.cumulative_fees = self.position_summary.cum_fees_quote
            if self.config.use_current_short_size:
                active_orders = self.market_data_provider.get_connector(
                    self.config.connector_name
                ).account_positions
                if active_orders:
                    for _, position in active_orders.items():
                        if position.trading_pair == self.config.trading_pair:
                            self.hedging_amount: Decimal = Decimal(position.amount)  # type: ignore
                            self.current_hedging_usd = (
                                self.hedging_amount * self.current_price
                            )
                            self.hedging_pnl = position.unrealized_pnl
                            self.logger().debug(
                                f"Active order found: {position}, "
                                f"hedging amount: {self.hedging_amount}, "
                                f"current hedging USD: {self.current_hedging_usd}"
                            )
                            break
                else:
                    self.logger().error("No active orders found")

                # self.logger().info(f"Active orders: {active_orders}")
                self.logger().debug("Positions held: %s", self.positions_held)
            else:
                if self.position_summary:
                    self.hedging_amount = Decimal(self.position_summary.amount)
                    if self.position_summary.side == TradeType.SELL:
                        self.hedging_amount = -self.hedging_amount
                    self.current_hedging_usd = Decimal(
                        self.position_summary.volume_traded_quote
                    )
                    self.hedging_pnl = self.position_summary.unrealized_pnl_quote
            self.total_value_usd = self.base_value_usd + self.cur_quote_token_amount
            if self.initial_total_value_usd is None:
                self.initial_total_value_usd = self.total_value_usd

            if self.base_value_usd <= 0:
                self.logger().error("Base value is 0, check gateway and oracle")
                return

            self.profitability = self.total_value_usd - self.initial_total_value_usd

            if not self.config.is_pool_amm and not self.is_pool_in_range():
                self.logger().warning("Pool is out of range")
                self.processed_data["signal"] = 0
                self.processed_data["hedge_amount"] = 0
                return

            # check if we fulfill the rebalance condition
            self.divergence_pct = (
                abs(self.current_hedging_usd) - self.base_value_usd
            ) / self.base_value_usd

            abs_amount_diff = (
                abs(self.cur_base_token_amount - abs(self.hedging_amount))
                if self.hedging_amount < 0
                else self.hedging_amount + self.cur_base_token_amount
            )

            self.calculated_margin = (
                abs(self.current_hedging_usd) / self.config.leverage
            )
            self.total_portfolio_value = (
                self.total_value_usd
                + self.hedging_pnl
                + self.calculated_margin
                - self.cumulative_fees
            )

            if self.initial_total_value_usd is None:
                self.initial_total_value_usd = self.total_value_usd

            if self.initial_portfolio_value is None and self.calculated_margin > 0:
                self.initial_portfolio_value = self.total_portfolio_value

            trading_rules_condition: bool = (
                abs_amount_diff > self.trading_rules.min_order_size
                and abs_amount_diff * self.current_price
                > self.trading_rules.min_notional_size
            )
            rebalance_needed = abs(self.divergence_pct) > self.config.rebalance_pct
            if rebalance_needed and not trading_rules_condition:
                self.rebalance_type = RebalanceType.NEEDED_BUT_TRADING_RULES_NOT_MET
                self.logger().info(
                    "Rebalance condition met but trading rules not met, divergence: %s, "
                    "signal: %s, hedge amount: %s",
                    self.divergence_pct,
                    cur_signal,
                    abs_amount_diff,
                )
            if rebalance_needed and trading_rules_condition:
                cur_signal = (
                    -1
                    if self.hedging_amount > 0
                    else 1
                    if self.divergence_pct > 0
                    else -1
                )
                self.processed_data["position_action"] = (
                    PositionAction.CLOSE
                    if self.hedging_amount > 0
                    else PositionAction.CLOSE
                    if self.divergence_pct > 0
                    else PositionAction.OPEN
                )
                self.rebalance_type = RebalanceType.PERFORMING
                self.processed_data["hedge_amount"] = abs_amount_diff
                self.logger().info(
                    "Rebalance condition met, divergence: %s, signal: %s, hedge amount: %s",
                    self.divergence_pct,
                    cur_signal,
                    self.processed_data["hedge_amount"],
                )

        last_update_readable = pd.to_datetime(self.last_update, unit="s").strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        entry_time_readable = (
            pd.to_datetime(self.entry_datetime, unit="s").strftime("%Y-%m-%d %H:%M:%S")
            if self.entry_datetime is not None
            else None
        )

        total_time_running_seconds = (
            (
                pd.to_datetime(cur_time, unit="s")
                - pd.to_datetime(self.entry_datetime, unit="s")
            ).total_seconds()
            if self.entry_datetime
            else 0
        )

        # Convert seconds to days, hours, minutes, seconds format
        days, remainder = divmod(int(total_time_running_seconds), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        total_time_running_readable = (
            f"{days} days {hours} hours {minutes} minutes {seconds} seconds"
        )

        apr_pool, apy_pool = (
            calculate_apr_apy(
                initial_value=self.initial_total_value_usd,
                current_value=self.total_value_usd,
                time_period_sec=total_time_running_seconds,
            )
            if self.initial_total_value_usd and total_time_running_seconds > 1
            else (Decimal(0), Decimal(0))
        )
        apr_portfolio, apy_portfolio = (
            calculate_apr_apy(
                initial_value=self.initial_portfolio_value,  # type: ignore
                current_value=self.total_portfolio_value,  # type: ignore
                time_period_sec=total_time_running_seconds,
            )
            if self.initial_portfolio_value and total_time_running_seconds > 1
            else (Decimal(0), Decimal(0))
        )

        apr_apy_note = ""
        if total_time_running_seconds < 24 * 3600:
            apr_apy_note = "(Not enough data to calculate APR / APY)"

        if apr_pool > 1000:
            apr_pool_percentage = f"{float(apr_pool):.2f}% (unlikely)"
        else:
            apr_pool_percentage = f"{float(apr_pool):.2f}%"
        apr_pool_percentage = f"{apr_pool_percentage} {apr_apy_note}"
        if apr_portfolio > 1000:
            apr_portfolio_percentage = f"{float(apr_portfolio):.2f}% (unlikely)"  # type: ignore
        else:
            apr_portfolio_percentage = f"{float(apr_portfolio):.2f}%"
        apr_portfolio_percentage = f"{apr_portfolio_percentage} {apr_apy_note}"

        if apy_pool > 10000:
            apy_pool_percentage = "Not stable yet"
        else:
            apy_pool_percentage = f"{float(apy_pool):.2f}%"

        if apy_portfolio > 10000:
            apy_portfolio_percentage = "Not stable yet"
        else:
            apy_portfolio_percentage = f"{float(apy_portfolio):.2f}%"

        # TWOPLACES = Decimal(10) ** -2

        # Create a dictionary of features and values for better readability
        features_dict = {
            "entry_price": self.entry_price,
            "entry_time": entry_time_readable,
            "initial_pool_total_value_usd": self.initial_total_value_usd,
            "difference_between_current_and_initial_pool_value_usd": (
                self.total_value_usd - self.initial_total_value_usd
                if self.initial_total_value_usd
                else 0
            ),
            "total_time_running": total_time_running_readable,
            "current_price": self.current_price,
            "pool_last_price": self.pool.pool_info.last_price,
            "volatile_coin_amount": self.cur_base_token_amount,
            "stable_coin_amount": self.cur_quote_token_amount,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "in_range": self.is_pool_in_range(),
            "size_shorted": self.hedging_amount,
            "rebalance_pct": f"{self.config.rebalance_pct * 100}%",
            "hedging_active": abs(self.current_hedging_usd) > 0,
            "pool_divergence_pct %": (
                f"{self.divergence_pct * 100:.2f}%"
                if self.divergence_pct != 0
                else "0.00%"
            ),
            "size_shorted_usd": self.current_hedging_usd,
            "base_value_usd": self.base_value_usd,
            "pool_total_value_usd": self.total_value_usd,
            "calculated_margin": self.calculated_margin,
            "divergence": f"{abs(self.current_hedging_usd) - self.base_value_usd}",
            "hedging_pnl": self.hedging_pnl,
            "short_adjustments": self.num_short_adjustments,
            "initial_portfolio_value": self.initial_portfolio_value,
            "total_portfolio_value": self.total_portfolio_value,
            "difference_between_current_and_initial_portfolio_value": (
                self.total_portfolio_value - self.initial_portfolio_value
                if self.initial_portfolio_value
                else 0
            ),
            "profitability": self.profitability,
            "cumulative_fees": self.cumulative_fees,
            "apr_pool": apr_pool_percentage,  # to quantize in 2 decimal places
            "apy_pool": apy_pool_percentage,
            "apr_portfolio": apr_portfolio_percentage,
            "apy_portfolio": apy_portfolio_percentage,
            "rebalance_type": self.rebalance_type,
            "last_update": last_update_readable,
        }

        # Convert dictionary to DataFrame with 'feature' and 'value' columns
        df = pd.DataFrame(
            {
                "feature": list(features_dict.keys()),  # type: ignore
                "value": list(features_dict.values()),  # type: ignore
            }
        )
        self.processed_data["features"] = df
        self.processed_data["signal"] = cur_signal

    def stop_actions_proposal(self) -> List[ExecutorAction]:
        """
        Stop actions based on the provided executor handler report.
        """
        if self.processed_data["stop_hedging"]:
            self.logger().info("Stop hedging signal received")
            self.processed_data["stop_hedging"] = False
            # Stop all active executors
            executors_to_stop = self.filter_executors(
                executors=self.executors_info,
                filter_func=lambda x: x.connector_name == self.config.connector_name
                and x.trading_pair == self.config.trading_pair
                and x.is_active,
            )
            return [
                StopExecutorAction(
                    controller_id=self.config.id,
                    executor_id=executor.id,
                    keep_position=False,
                )
                for executor in executors_to_stop
            ]

        signal = self.processed_data["signal"]
        # if signal == -1 stop active longs
        if signal == -1:
            executors_to_stop = self.get_active_executors(side=TradeType.BUY)
        # if signal == 1 stop active shorts
        elif signal == 1:
            executors_to_stop = self.filter_executors(
                executors=self.executors_info,
                filter_func=lambda x: x.connector_name == self.config.connector_name
                and x.trading_pair == self.config.trading_pair
                and x.side == TradeType.SELL
                and x.is_active,
            )
        else:
            return []

        return [
            StopExecutorAction(
                controller_id=self.config.id,
                executor_id=executor.id,
                keep_position=False,
            )
            for executor in executors_to_stop
        ]

    def get_active_executors(self, side: TradeType) -> List[ExecutorInfo]:
        return self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda x: x.connector_name == self.config.connector_name
            and x.trading_pair == self.config.trading_pair
            and x.side == side
            and x.is_active,
        )

    def get_position_summary(self) -> PositionSummary | None:
        summaries = [
            position
            for position in self.positions_held
            if position.trading_pair == self.config.trading_pair
        ]
        if len(summaries) > 1:
            self.logger().warning(
                f"Multiple positions found for trading pair {self.config.trading_pair}"
            )
        return summaries[0] if len(summaries) > 0 else None

    def to_format_status(self) -> List[str]:
        df: pd.DataFrame = self.processed_data.get("features", pd.DataFrame())
        if df.empty:
            return []
        return [
            format_df_for_printout(
                df,  # type: ignore
                table_format="psql",  # type: ignore
            )
        ]

    async def close_short_position(self) -> None:
        connector = self.market_data_provider.get_connector(self.config.connector_name)
        connector.buy(
            trading_pair=self.config.trading_pair,
            amount=max(abs(self.hedging_amount), self.trading_rules.min_order_size),  # type: ignore
            price=self.current_price,
            order_type=OrderType.MARKET,
            position_action=PositionAction.CLOSE,
        )

    async def close_pool_position(self) -> None:
        """
        Close the pool position.
        """
        try:
            await self.pool.close_position()
        except PoolError as e:
            self.logger().error(
                f"Error closing pool position: {str(e)} "
                f"for pool address: {self.config.pool_address}"
            )
            raise e

    def on_stop(self):
        """
        Stop the controller.
        """
        self.logger().info("Stopping LpHedgingController")
        if self.config.close_short_on_stop:
            self.logger().info("Closing short position")
            safe_ensure_future(self.close_short_position())
        if self.config.close_pool_position_on_stop:
            self.logger().info("Closing pool position")
            safe_ensure_future(self.close_pool_position())
