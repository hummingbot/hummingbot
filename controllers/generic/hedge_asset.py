"""
Explanation:

This strategy tracks the spot balance of a single asset on one exchange and maintains a hedge on a perpetual exchange
using a fixed, user-defined hedge ratio. It continuously compares the target hedge size (spot_balance × hedge_ratio)
with the actual short position and adjusts only when the difference exceeds a minimum notional threshold and enough
time has passed since the last order. This prevents overtrading while keeping the exposure appropriately hedged. The
user can manually update the hedge ratio in the config, and the controller will rebalance toward the new target size,
reducing or increasing the short position as needed. This allows safe, controlled management of spot inventory with
minimal noise and predictable hedge behavior.
"""
from decimal import Decimal
from typing import List

from pydantic import Field

from hummingbot.core.data_type.common import MarketDict, PositionAction, PositionMode, TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.order_executor.data_types import ExecutionStrategy, OrderExecutorConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction


class HedgeAssetConfig(ControllerConfigBase):
    """
    Configuration required to run the GridStrike strategy for one connector and trading pair.
    """
    controller_type: str = "generic"
    controller_name: str = "hedge_asset"
    candles_config: List[CandlesConfig] = []
    total_amount_quote: Decimal = Decimal(0)

    # Spot connector
    spot_connector_name: str = "binance"
    asset_to_hedge: str = "SOL"

    # Perpetual connector
    hedge_connector_name: str = "binance_perpetual"
    hedge_trading_pair: str = "SOL-USDT"
    leverage: int = 20
    position_mode: PositionMode = PositionMode.HEDGE

    # Hedge params
    hedge_ratio: Decimal = Field(default=Decimal("0"), ge=0, le=1, json_schema_extra={"is_updatable": True})
    min_notional_size: float = Field(default=10, ge=0)
    cooldown_time: float = Field(default=10.0, ge=0)

    def update_markets(self, markets: MarketDict) -> MarketDict:
        markets.add_or_update(self.spot_connector_name, self.asset_to_hedge + "-USDC")
        markets.add_or_update(self.hedge_connector_name, self.hedge_trading_pair)
        return markets


class HedgeAssetController(ControllerBase):
    def __init__(self, config: HedgeAssetConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        self.perp_collateral_asset = self.config.hedge_trading_pair.split("-")[1]
        self.set_leverage_and_position_mode()

    def set_leverage_and_position_mode(self):
        connector = self.market_data_provider.get_connector(self.config.hedge_connector_name)
        connector.set_leverage(leverage=self.config.leverage, trading_pair=self.config.hedge_trading_pair)
        connector.set_position_mode(self.config.position_mode)

    @property
    def hedge_position_size(self) -> Decimal:
        hedge_positions = [position for position in self.positions_held if
                           position.connector_name == self.config.hedge_connector_name and
                           position.trading_pair == self.config.hedge_trading_pair and
                           position.side == TradeType.SELL]
        if len(hedge_positions) > 0:
            hedge_position = hedge_positions[0]
            hedge_position_size = hedge_position.amount
        else:
            hedge_position_size = Decimal("0")
        return hedge_position_size

    @property
    def last_hedge_timestamp(self) -> float:
        if len(self.executors_info) > 0:
            return self.executors_info[-1].timestamp
        return 0

    async def update_processed_data(self):
        """
        Compute current spot balance, hedge position size, current hedge ratio, last hedge time, current hedge gap quote
        """
        current_price = self.market_data_provider.get_price_by_type(self.config.hedge_connector_name, self.config.hedge_trading_pair)
        spot_balance = self.market_data_provider.get_balance(self.config.spot_connector_name, self.config.asset_to_hedge)
        perp_available_balance = self.market_data_provider.get_available_balance(self.config.hedge_connector_name, self.perp_collateral_asset)
        hedge_position_size = self.hedge_position_size
        hedge_position_gap = spot_balance * self.config.hedge_ratio - hedge_position_size
        hedge_position_gap_quote = hedge_position_gap * current_price
        last_hedge_timestamp = self.last_hedge_timestamp

        # if these conditions are true we are allowed to execute a trade
        cool_down_time_condition = last_hedge_timestamp + self.config.cooldown_time < self.market_data_provider.time()
        min_notional_size_condition = abs(hedge_position_gap_quote) >= self.config.min_notional_size
        self.processed_data.update({
            "current_price": current_price,
            "spot_balance": spot_balance,
            "perp_available_balance": perp_available_balance,
            "hedge_position_size": hedge_position_size,
            "hedge_position_gap": hedge_position_gap,
            "hedge_position_gap_quote": hedge_position_gap_quote,
            "last_hedge_timestamp": last_hedge_timestamp,
            "cool_down_time_condition": cool_down_time_condition,
            "min_notional_size_condition": min_notional_size_condition,
        })

    def determine_executor_actions(self) -> List[ExecutorAction]:
        if self.processed_data["cool_down_time_condition"] and self.processed_data["min_notional_size_condition"]:
            side = TradeType.SELL if self.processed_data["hedge_position_gap"] >= 0 else TradeType.BUY
            order_executor_config = OrderExecutorConfig(
                timestamp=self.market_data_provider.time(),
                connector_name=self.config.hedge_connector_name,
                trading_pair=self.config.hedge_trading_pair,
                side=side,
                amount=abs(self.processed_data["hedge_position_gap"]),
                price=self.processed_data["current_price"],
                leverage=self.config.leverage,
                position_action=PositionAction.CLOSE if side == TradeType.BUY else PositionAction.OPEN,
                execution_strategy=ExecutionStrategy.MARKET
            )
            return [CreateExecutorAction(controller_id=self.config.id, executor_config=order_executor_config)]
        return []

    def to_format_status(self) -> List[str]:
        """
        These report will be showing the metrics that are important to determine the state of the hedge.
        """
        lines = []

        # Get data
        spot_balance = self.processed_data.get("spot_balance", Decimal("0"))
        hedge_position = self.processed_data.get("hedge_position_size", Decimal("0"))
        perp_balance = self.processed_data.get("perp_available_balance", Decimal("0"))
        current_price = self.processed_data.get("current_price", Decimal("0"))
        gap = self.processed_data.get("hedge_position_gap", Decimal("0"))
        gap_quote = self.processed_data.get("hedge_position_gap_quote", Decimal("0"))
        cooldown_ok = self.processed_data.get("cool_down_time_condition", False)
        notional_ok = self.processed_data.get("min_notional_size_condition", False)

        # Calculate theoretical hedge
        theoretical_hedge = spot_balance * self.config.hedge_ratio

        # Status indicators
        cooldown_status = "✓" if cooldown_ok else "✗"
        notional_status = "✓" if notional_ok else "✗"

        # Header
        lines.append(f"\n{'=' * 65}")
        lines.append(f"  HEDGE ASSET CONTROLLER: {self.config.asset_to_hedge} @ {current_price:.4f} {self.perp_collateral_asset}")
        lines.append(f"{'=' * 65}")

        # Calculation flow
        lines.append(f"  Spot Balance:      {spot_balance:>10.4f} {self.config.asset_to_hedge}")
        lines.append(f"  × Hedge Ratio:     {self.config.hedge_ratio:>10.1%}")
        lines.append(f"  {'─' * 61}")
        lines.append(f"  = Target Hedge:    {theoretical_hedge:>10.4f} {self.config.asset_to_hedge}")
        lines.append(f"  - Current Hedge:   {hedge_position:>10.4f} {self.config.asset_to_hedge}")
        lines.append(f"  {'─' * 61}")
        lines.append(f"  = Gap:             {gap:>10.4f} {self.config.asset_to_hedge}  ({gap_quote:>8.2f} {self.perp_collateral_asset})")
        lines.append("")
        lines.append(f"  Perp Balance:      {perp_balance:>10.2f} {self.perp_collateral_asset}")
        lines.append("")

        # Trading conditions
        lines.append("  Trading Conditions:")
        lines.append(f"    Cooldown ({self.config.cooldown_time:.0f}s):      {cooldown_status}")
        lines.append(f"    Min Notional (≥{self.config.min_notional_size:.0f} {self.perp_collateral_asset}): {notional_status}")

        lines.append(f"{'=' * 65}\n")

        return lines
