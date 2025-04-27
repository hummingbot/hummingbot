import asyncio
import logging
from decimal import Decimal
from typing import Dict, Literal, Optional, Union, cast

from pydantic import BaseModel, Field, field_serializer, field_validator, ConfigDict

from hummingbot.connector.gateway.common_types import ConnectorType, get_connector_type
from hummingbot.connector.gateway.gateway_lp import CLMMPoolInfo, CLMMPositionInfo, GatewayLp
from hummingbot.core.data_type.common import PositionAction, TradeType
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.executor_base import ExecutorBase
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType, TrackedOrder

from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


class PALMTresholdPrice(BaseModel):
    """
    This class represents a trigger price for a concentrated liquidity position.
    """
    treshold_price: float

    # This allows us to maintain the method interface while using Pydantic
    def set_treshold_price(self, treshold_price: float) -> None:
        self.treshold_price = treshold_price

    def get_treshold_price(self) -> float:
        return self.treshold_price

    # Custom serialization to make it compatible with existing code
    @field_serializer('treshold_price')
    def serialize_treshold_price(self, value: float, _info):
        return value


class PALMExecutorConfig(ExecutorConfigBase):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    type: Literal["palm_executor"] = "palm_executor"
    connector_name: str  # Field("raydium/clmm")
    chain: str  # = Field("solana")
    network: str  # = Field("mainnet-beta")
    # TODO make open position use the pool_address
    pool_address: str

    trading_pair: str
    upper_price: Decimal
    lower_price: Decimal
    quote_amt: Decimal
    base_amt: Decimal
    position_amt_scalar_pct: float = Field(
        default=0, description="Used in rebalancing the position (value between 0 and 1)")

    slippage_pct: float = float("0.01")

    # If treshold_price_low is crossed down, we will rebalance the position Upwards/ Increase liquidity (because the bottom PALM will become middle PALM)
    treshold_price_low: PALMTresholdPrice
    # If treshold_price_high is crossed up, we will rebalance the postion Downwards/ Decrease liquidity (because the top PALM will become middle PALM)
    treshold_price_high: PALMTresholdPrice
    executor_level_id: int = None  # Generally we have 3 levels. When a trigger price is crossed we will move the executor_level_id
    executors_total_levels: int = 3  # Generally we have 3 levels. When a trigger price is crossed we will move the executor_level_id

    @field_validator('position_amt_scalar_pct')
    def validate_position_amt_scalar_pct(cls, v):
        if not 0 <= v <= 1:
            raise ValueError('position_amt_scalar_pct must be between 0 and 1')
        return v


AnyExecutorConfig = Union[PALMExecutorConfig,]


class ExecutorInfoEx(ExecutorInfo):
    config: AnyExecutorConfig = Field(..., discriminator="type")


class PALMExecutor(ExecutorBase):
    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    # def get_trading_rules(self, connector_name: str, trading_pair: str) -> TradingRuleStub:
    #     """
    #     Retrieves the trading rules for the specified trading pair from the specified connector.

    #     :param connector_name: The name of the connector.
    #     :param trading_pair: The trading pair.
    #     :return: The trading rules.
    #     """
    #     # return self.connectors[connector_name].trading_rules[trading_pair]
    #     return TradingRuleStub(self.config.trading_pair)

    @property
    def executor_info(self) -> ExecutorInfoEx:
        """
        Returns the executor info.
        """
        ts = 0
        if self.config.timestamp:
            ts = self.config.timestamp

        ei = ExecutorInfoEx(
            id=self.config.id,
            timestamp=ts,
            type=self.config.type,
            status=self.status,
            close_type=self.close_type,
            close_timestamp=self.close_timestamp,
            config=self.config,
            net_pnl_pct=self.net_pnl_pct,
            net_pnl_quote=self.net_pnl_quote,
            cum_fees_quote=self.cum_fees_quote,
            filled_amount_quote=self.filled_amount_quote,
            is_active=self.is_active,
            is_trading=self.is_trading,
            custom_info=self.get_custom_info(),
            controller_id=self.config.controller_id,
        )
        ei.filled_amount_quote = ei.filled_amount_quote if not ei.filled_amount_quote.is_nan() else Decimal("0")
        ei.net_pnl_quote = ei.net_pnl_quote if not ei.net_pnl_quote.is_nan() else Decimal("0")
        ei.cum_fees_quote = ei.cum_fees_quote if not ei.cum_fees_quote.is_nan() else Decimal("0")
        ei.net_pnl_pct = ei.net_pnl_pct if not ei.net_pnl_pct.is_nan() else Decimal("0")
        return ei

    def __init__(self, strategy: ScriptStrategyBase, config: PALMExecutorConfig,
                 update_interval: float = 1.0, max_retries: int = 10):
        self.exchange = f"{config.connector_name}_{config.chain}_{config.network}"

        super().__init__(strategy=strategy, config=config, connectors=[self.exchange],
                         update_interval=update_interval)
        self.config: PALMExecutorConfig = config

        self._failed_orders: list[TrackedOrder] = []
        self._current_retries = 0
        self._max_retries = max_retries

        self.connector_type = get_connector_type(self.exchange)
        if self.connector_type != ConnectorType.CLMM:
            raise NotImplementedError

        # Position
        self.upper_price = config.upper_price
        self.lower_price = config.lower_price
        self.quote_amt = config.quote_amt
        self.base_amt = config.base_amt
        self.executor_level_id = config.executor_level_id

        # LP position tracking
        self.position_opening = False
        self.pos_address = None
        self.pool_info: CLMMPoolInfo = None
        self.position_info: Union[CLMMPositionInfo, None] = None
        self.current_price = 0.0

        if self.executor_level_id > config.executors_total_levels:
            raise ValueError(
                f"Level ID {self.executor_level_id} is greater than total levels {config.executors_total_levels}.")
        if self.executor_level_id < 1:
            raise ValueError(f"Level ID {self.executor_level_id} is less than 1.")

        # The cached tresholds will ensure the executor finishes the rebalancing process even if PALMTresholdPrice changes its price
        self.cached_treshold_low = config.treshold_price_low.get_treshold_price()
        self.cached_treshold_high = config.treshold_price_high.get_treshold_price()

        lp_connector: GatewayLp = self.connectors[self.exchange]
        self.lp_connector = cast(GatewayLp, lp_connector)

    @property
    def current_market_price(self) -> Decimal:
        return Decimal(self.current_price)

    async def control_task(self):
        """
        Control the order execution process based on the execution strategy.
        """
        if self.status == RunnableStatus.RUNNING:
            await self.fetch_pool_info()
            if not self.position_opening:
                self.open_position()

            elif self.position_opening:
                await self.update_position_info()
                await self.monitor_position()

        elif self.status == RunnableStatus.SHUTTING_DOWN:
            if self.pool_info is not None:
                await self.close_position_and_executor()

        self.evaluate_max_retries()

    def early_stop(self, keep_position: bool = True):
        """
        This method allows strategy to stop the executor early.

        :return: None
        """
        self._status = RunnableStatus.SHUTTING_DOWN

    def evaluate_max_retries(self):
        """
        Evaluate if the maximum number of retries has been reached.
        """
        if self._current_retries > self._max_retries:
            self.logger().error("Max retries reached. Stopping DCA executor.")
            self.close_execution_by(CloseType.FAILED)

    def process_order_failed_event(self, _, market, event: MarketOrderFailureEvent):
        """
        Process the order failed event.
        """
        self.logger().error(f"Order failed {event.order_id}. Retrying {self._current_retries}/{self._max_retries}")
        self._current_retries += 1
        self.position_opening = False

    async def update_position_info(self):
        """Fetch the latest position information if we have an open position"""
        if not self.pos_address:
            return

        try:
            self.position_info = await self.lp_connector.get_position_info(
                trading_pair=self.config.trading_pair,
                position_address=self.pos_address
            )
            if self.position_info:
                self.logger().debug(f"Updated position info: {self.position_info.address}")
                return

            self.logger().error(f"Position info not found for address: {self.pos_address}")
        except Exception as e:
            self.position_info = None
            self.logger().error(f"Error updating position info: {str(e)}")

    async def fetch_pool_info(self):
        """Fetch pool information to get tokens and current price"""
        self.logger().debug(f"Fetching pool info for {self.config.trading_pair} on {self.config.connector_name}")
        try:
            self.pool_info = await self.lp_connector.get_pool_info(
                trading_pair=self.config.trading_pair
            )
            self.current_price = self.pool_info.price
            return self.pool_info
        except Exception as e:
            self.logger().error(f"Error fetching pool info: {str(e)}")
            return None

    # Using custom open_position method to have access to "lower_price" and "upper_price"
    def open_position(self) -> str:
        """
        Opens a liquidity position - either concentrated (CLMM) or regular (AMM) based on the connector type.
        :param trading_pair: The market trading pair
        :param price: The center price for the position.
        :param request_args: Additional arguments for position opening
        :return: A newly created order id (internal).
        """

        trade_type: TradeType = TradeType.RANGE
        order_id: str = self.lp_connector.create_market_order_id(trade_type, self.config.trading_pair)

        self.position_opening = True
        if self.connector_type == ConnectorType.CLMM:
            safe_ensure_future(self._clmm_open_position(trade_type, order_id))
        else:
            raise NotImplementedError

        return order_id

    async def _clmm_open_position(
        self,
        trade_type: TradeType,
        order_id: str,
    ):
        gateway_instance = self.lp_connector._get_gateway_instance()

        # Split trading_pair to get base and quote tokens
        tokens = self.config.trading_pair.split("-")
        if len(tokens) != 2:
            raise ValueError(f"Invalid trading pair format: {self.config.trading_pair}. Expected format: 'base-quote'")

        base_token, quote_token = tokens
        base_amt = float(self.base_amt)
        quote_amt = float(self.quote_amt)
        base_token_amount, quote_token_amount = self.rebalance_base_quote_amts(base_amt, quote_amt)

        # TODO Order tracking is bugged in due ot custom executor. For now skip it.
        # self.lp_connector.start_tracking_order(order_id=order_id,
        #                         trading_pair=self.config.trading_pair,
        #                         trade_type=trade_type, #trade_type: TradeType = TradeType.BUY,
        #                         price=Decimal(self.current_price),
        #                         amount=Decimal(base_token_amount))

        # NOTICE Adding a small sleep between level_id openings because gatelay sometimes is unable to handle simultaneous requests
        await self._sleep(0.2*self.executor_level_id)
        try:
            transaction_result = await gateway_instance.clmm_open_position(
                connector=self.config.connector_name,
                network=self.config.network,
                wallet_address=self.lp_connector.address,
                base_token=base_token,
                quote_token=quote_token,
                lower_price=float(self.lower_price),
                upper_price=float(self.upper_price),
                base_token_amount=base_token_amount,
                quote_token_amount=quote_token_amount,
                slippage_pct=self.config.slippage_pct,
            )

            transaction_hash: Optional[str] = transaction_result.get("signature")
            if transaction_hash is not None and transaction_hash != "":
                self.pos_address = transaction_result.get("positionAddress")
                # TODO Order tracking is bugged in due ot custom executor. For now skip it.
                # self.lp_connector.update_order_from_hash(order_id, self.config.trading_pair, transaction_hash, transaction_result)
                return transaction_hash
            else:
                raise ValueError("No transaction hash returned from gateway")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.position_opening = False
            # TODO Order tracking is bugged in due ot custom executor. For now skip it.
            # self.lp_connector._handle_operation_failure(order_id, self.config.trading_pair, "opening CLMM position", e)

    # TODO This sends order for position close. Check how to terminate the executor, after order is done - call stop()

    async def close_position_and_executor(self):
        """Close the liquidity position"""
        if not self.position_info:
            # When the position is None, we stop the executors
            self.close_execution_by(CloseType.COMPLETED)
            return

        try:
            # Use the connector's close_position method
            self.logger().info(f"Closing position {self.position_info.address}...")
            order_id = self.lp_connector.close_position(
                trading_pair=self.config.trading_pair,
                position_address=self.position_info.address
            )
            self.logger().info(f"Position closing order submitted with ID: {order_id}")
            await self._sleep(15)  # Wait for the order to be processed

            # ckeck if position info is zeroed out
            await self.update_position_info()

        except Exception as e:
            self.logger().error(f"Error closing position: {str(e)}")

    def rebalance_base_quote_amts(self, base_amt: float, quote_amt: float) -> tuple[float, float]:
        price = float(self.current_price)
        mid_price = (float(self.upper_price) + float(self.lower_price)) / 2

        # if pool price is above my price range, deposit only quote:
        if price > float(mid_price):
            # convert all base -> quote
            quote_amt = ((base_amt * price) + quote_amt)
            base_amt = 0.0

        # if pool price is below my range, deposit only base:
        elif price < float(mid_price):
            # convert all quote -> base
            base_amt = (quote_amt / price + base_amt)
            quote_amt = 0.0

        if float(self.lower_price) < price < float(self.upper_price):
            # NOTICE
            # When the position is in range, gateway matches the bigger amount between base and quote
            # so we now need to DIVIDE both amts, to get correct values
            # otherwise the position will be doubled
            base_amt = base_amt / 2
            quote_amt = quote_amt / 2

        # else price is inside my [lower, upper] — keep both as is

        return base_amt, quote_amt

    async def monitor_position(self):
        """
        Rebalance when price moves up (i.e., the price crosses the right threshold - treshold_price_high).
        Steps (as described in the PALM example):
        1. The right position (R) becomes the new Middle: remove part of its liquidity.
        2. The middle position (M) shifts to the Left: remove a portion of liquidity.
        3. A new Right (R) position is opened using tokens from the reserve.
        4. The original Left (L) position is closed and its assets returned to the reserve.


        Rebalance when price moves down (i.e., the price crosses the left threshold - treshold_price_low).
        Steps (as described in the PALM example):
        1. Left (L) becomes the new Middle: add liquidity using reserve funds.
        2. Middle (M) shifts to the Right: optionally add additional liquidity.
        3. A new Left (L) position is created using base assets from the reserve.
        4. The original Right (R) position is closed and its assets are returned to the reserve.
        """
        if not self.position_info:
            return

        if float(self.current_price) > self.config.treshold_price_high.get_treshold_price() or float(self.current_price) > self.cached_treshold_high:
            # rebalance up
            self.logger().info(f"Rebalancing PALM up")
            self.executor_level_id -= 1  # shipt position to the left
            if self.executor_level_id < 1:
                self.logger().info(f"Level ID {self.executor_level_id} is below level 1. Closing position.")
                await self.close_position_and_executor()
                return

            # rebalance up if
            if self.config.position_amt_scalar_pct > 0:
                await self.lp_connector.amm_remove_liquidity(
                    trading_pair=self.config.trading_pair,
                    percentage=self.config.position_amt_scalar_pct * 100,
                    fail_silently=False
                )

            # Update the cached treshold price to prevent repeated rebalancing
            self.update_cached_treshold_prices()

        elif float(self.current_price) < self.config.treshold_price_low.get_treshold_price() or float(self.current_price) < self.cached_treshold_low:
            # rebalance down
            self.logger().info(f"Rebalancing PALM down")
            self.executor_level_id += 1  # shipt position to the right
            if self.executor_level_id > self.config.executors_total_levels:
                self.logger().error(
                    f"Level ID {self.executor_level_id} is above total levels {self.config.executors_total_levels}. Closing position.")
                await self.close_position_and_executor()
                return

            # implement rebalance down
            if self.config.position_amt_scalar_pct > 0:
                # TODO the base and quote amounts will differ from the actuall liqirity added when "pos_mid_price" is not equal to "current_price"

                half_scalar_pct = self.config.position_amt_scalar_pct  # / 2 # Half because we scale up both base and quote
                base_amt = float(float(self.base_amt) * (1 + half_scalar_pct))
                quote_amt = float(float(self.quote_amt) * (1 + half_scalar_pct))
                base_token_amount, quote_token_amount = self.rebalance_base_quote_amts(base_amt, quote_amt)

                await self.lp_connector.amm_add_liquidity(
                    trading_pair=self.config.trading_pair,
                    base_token_amount=base_token_amount,
                    quote_token_amount=quote_token_amount,
                    slippage_pct=self.config.slippage_pct,
                    fail_silently=False
                )

            # Update the cached treshold price to prevent repeated rebalancing
            self.update_cached_treshold_prices()

        else:
            self.logger().debug(f"Price is in range, no rebalancing needed")

        return

    def update_cached_treshold_prices(self):
        """
        Update the cached treshold prices.
        """
        self.cached_treshold_low = self.config.treshold_price_low.get_treshold_price()
        self.cached_treshold_high = self.config.treshold_price_high.get_treshold_price()

    async def validate_sufficient_balance(self):
        # if self.is_perpetual_connector(self.exchange):
        #     order_candidate = PerpetualOrderCandidate(
        #         trading_pair=self.config.trading_pair,
        #         is_maker=self.get_order_type().is_limit_type(),
        #         order_type=self.get_order_type(),
        #         order_side=self.config.side,
        #         amount=self.config.amount,
        #         price=self.config.price,
        #         leverage=Decimal(self.config.leverage),
        #     )
        # else:
        #     order_candidate = OrderCandidate(
        #         trading_pair=self.config.trading_pair,
        #         is_maker=self.get_order_type().is_limit_type(),
        #         order_type=self.get_order_type(),
        #         order_side=self.config.side,
        #         amount=self.config.amount,
        #         price=self.config.price,
        #     )
        # adjusted_order_candidates = self.adjust_order_candidates(self.exchange, [order_candidate])

        # if adjusted_order_candidates[0].amount == Decimal("0"):
        #     self.close_type = CloseType.INSUFFICIENT_BALANCE
        #     self.logger().error("Not enough budget to open position.")
        #     self.stop()

        # TODO check balances for the LP provision
        return

    async def _sleep(self, delay: float):
        """
        Sleep for a specified delay.

        :param delay: The delay in seconds.
        """
        await asyncio.sleep(delay)

    def close_execution_by(self, close_type):
        self.close_type = close_type
        self.stop()

    # ---------- Event handlers

    def update_tracked_order_with_order_id(self, order_id: str):
        """
        Update the tracked order with the information from the InFlightOrder.

        :param order_id: The order ID to update.
        """
        in_flight_order = self.get_in_flight_order(self.exchange, order_id)
        self.logger().info(f"Updating tracked order with order ID: {in_flight_order}")
        # if self._order and self._order.order_id == order_id:
        #     self._order.order = in_flight_order

    def process_order_created_event(self, _, market, event: Union[BuyOrderCreatedEvent, SellOrderCreatedEvent]):
        """
        Process the order created event.
        """
        self.update_tracked_order_with_order_id(event.order_id)

    def process_order_filled_event(self, _, market, event: OrderFilledEvent):
        """
        Process the order filled event.
        """
        self.update_tracked_order_with_order_id(event.order_id)

    def process_order_completed_event(self, _, market, event: Union[BuyOrderCompletedEvent, SellOrderCompletedEvent]):
        """
        Process the order completed event.
        """
        self.update_tracked_order_with_order_id(event.order_id)
        # if self._order and self._order.order_id == event.order_id:
        #     self._held_position_orders.append(self._order.order.to_json())
        #     self.close_type = CloseType.COMPLETED
        #     self.stop()

    def process_order_canceled_event(self, _, market, event: OrderCancelledEvent):
        """
        Process the order canceled event.
        """
        # TODO Check if i need this for a PALM
        # if self._order and event.order_id == self._order.order_id:
        #     if self._order.executed_amount_base > Decimal("0"):
        #         self._partially_filled_orders.append(self._order)
        #     else:
        #         self._canceled_orders.append(self._order)
        #     self._order = None
        return

    # ---------- Info classes
    def get_net_pnl_pct(self) -> Decimal:
        """
        Get the net profit and loss percentage.

        :return: The net profit and loss percentage.
        """
        return Decimal("0")

    def get_net_pnl_quote(self) -> Decimal:
        """
        Get the net profit and loss in quote currency.

        :return: The net profit and loss in quote currency.
        """
        return Decimal("0")

    def get_cum_fees_quote(self) -> Decimal:
        """
        Get the cumulative fees in quote currency.

        :return: The cumulative fees in quote currency.
        """
        return Decimal("0")

    def get_custom_info(self) -> Dict:
        """
        Get custom information about the executor.
        we can later filter by this info

        :return: A dictionary containing custom information.
        """
        return {
            "max_retries": self._max_retries,
            "pool_address": self.pool_info.address if self.pool_info else None,
            "pool_fee_pct": self.pool_info.feePct if self.pool_info else None,
        }

    def to_format_status(self, scale=1.0):
        """
        Format the status of the executor.

        :param scale: The scale for formatting.
        :return: A list of formatted status lines.
        """
        
        lines = [f"""
| level_id: {self.executor_level_id}
| lower_price: {self.lower_price} | upper_price: {self.upper_price}
| base_amt: {self.base_amt} | quote_amt: {self.quote_amt}
| pool_address: {self.pool_info.address if self.pool_info else None} | pool_fee_pct: {self.pool_info.feePct if self.pool_info else None}
| Retries: {self._current_retries}/{self._max_retries}
"""]
        return lines
