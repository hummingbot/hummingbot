import os
from decimal import Decimal
from typing import List, Optional

from pydantic import Field, ValidationError, field_validator

from hummingbot.core.data_type.common import MarketDict, OrderType, PriceType, TradeType
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase
from hummingbot.strategy_v2.executors.arbitrage_executor.data_types import ArbitrageExecutorConfig
from hummingbot.strategy_v2.executors.data_types import ConnectorPair, ExecutorConfigBase
from hummingbot.strategy_v2.executors.dca_executor.data_types import DCAExecutorConfig, DCAMode
from hummingbot.strategy_v2.executors.grid_executor.data_types import GridExecutorConfig
from hummingbot.strategy_v2.executors.order_executor.data_types import (
    ExecutionStrategy,
    LimitChaserConfig,
    OrderExecutorConfig,
)
from hummingbot.strategy_v2.executors.position_executor.data_types import (
    PositionExecutorConfig,
    TrailingStop,
    TripleBarrierConfig,
)
from hummingbot.strategy_v2.executors.twap_executor.data_types import TWAPExecutorConfig, TWAPMode
from hummingbot.strategy_v2.executors.xemm_executor.data_types import XEMMExecutorConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, StopExecutorAction

# Scenario catalog: executor_type -> {scenario_name: description}.
# Scenarios prefixed with "invalid_" are expected to FAIL config validation: the QA pass
# criterion is that the config is rejected with a clear error before any order is placed.
SCENARIOS = {
    "position": {
        "default": "LIMIT entry 0.1% inside the spread, TP 1% / SL 2% / time limit 10 min",
        "market_entry_trailing": "MARKET entry with trailing stop (activation 0.2%, delta 0.1%)",
        "resting_entry_timeout": "LIMIT entry 2% away that should never fill; time limit 60s cancels it",
        "invalid_amount": "amount=0, must be rejected by validation",
    },
    "order": {
        "default": "LIMIT order 0.5% away from mid price",
        "market": "MARKET order, fills immediately",
        "limit_chaser": "LIMIT_CHASER 0.1% behind the best price, re-pegs every 0.05%",
        "maker_cross": "LIMIT_MAKER priced across the book; exchange should reject it (failure handling)",
        "invalid_no_price": "LIMIT strategy without a price, must be rejected by validation",
    },
    "twap": {
        "default": "TAKER: 5 market orders over 60s (one every 15s)",
        "maker": "MAKER: limit orders over 120s, buffer 0.1%, resubmission every 20s",
        "single_order": "duration < interval, collapses to a single order",
        "invalid_interval": "order_interval=0, must be rejected by validation",
    },
    "dca": {
        "default": "MAKER: 3 levels at 0.1%/0.5%/1% away (20/30/50% of amount), TP 1% / SL 3%",
        "taker": "TAKER entries with trailing stop (activation 0.5%, delta 0.2%)",
        "far_levels_timeout": "levels 5/6/7% away that never fill; time limit 120s closes the executor",
        "invalid_levels": "2 amounts vs 3 prices, must be rejected by validation",
    },
    "grid": {
        "default": "grid +-1% around mid, level TP 0.2%, stop-out 4% beyond the losing edge",
        "tight_range": "grid +-0.2%: few levels, tests min spread / min order amount handling",
        "wide_sparse": "grid +-5% with 0.5% min spread and 10s order frequency throttle",
        "invalid_range": "start_price above end_price, must be rejected by validation",
    },
    "xemm": {
        "default": "maker on market 1 hedged on market 2, profitability band 0.1%/0.2%/0.4%",
        "tight_band": "narrow band 0.08%/0.10%/0.12%, exercises frequent maker re-pricing",
        "invalid_band": "min_profitability above target, must be rejected by validation",
    },
    "arbitrage": {
        "default": "scan both markets, trade only above 0.2% profitability (usually idles: QA watches the loop)",
        "force_trade": "min_profitability=-5% so both legs execute immediately (paper trading only!)",
        "invalid_same_market": "same market on both sides, must be rejected by validation",
    },
}


class ExecutorsQAConfig(StrategyV2ConfigBase):
    """
    Note: the LP executor is not covered here because it needs a Gateway connection and a real
    pool address; use scripts/xrpl_liquidity_example.py or a controller for LP QA.
    """
    script_file_name: str = os.path.basename(__file__)
    executor_type: str = Field(
        default="position",
        json_schema_extra={
            "prompt": lambda mi: f"Enter the executor type to test ({', '.join(SCENARIOS.keys())}): ",
            "prompt_on_new": True},
    )
    scenario: str = Field(
        default="default",
        json_schema_extra={
            "prompt": lambda mi: "Enter the scenario to run ('list' prints the available ones): ",
            "prompt_on_new": True},
    )
    total_amount_quote: Decimal = Field(
        default=Decimal("100"),
        json_schema_extra={
            "prompt": lambda mi: "Enter the total amount in quote asset (e.g. 100): ",
            "prompt_on_new": True},
    )
    connector_name: str = Field(
        default="binance_paper_trade",
        json_schema_extra={
            "prompt": lambda mi: "Enter the connector (e.g. binance_paper_trade): ",
            "prompt_on_new": True},
    )
    trading_pair: str = Field(
        default="ETH-USDT",
        json_schema_extra={
            "prompt": lambda mi: "Enter the trading pair (e.g. ETH-USDT): ",
            "prompt_on_new": True},
    )
    side: str = Field(
        default="BUY",
        json_schema_extra={
            "prompt": lambda mi: "Enter the side (BUY/SELL): ",
            "prompt_on_new": True},
    )
    # Second market, only used by the xemm and arbitrage executors
    connector_name_2: str = Field(
        default="kucoin_paper_trade",
        json_schema_extra={
            "prompt": lambda mi: "Enter the second connector, only used for xemm/arbitrage (e.g. kucoin_paper_trade): ",
            "prompt_on_new": True},
    )
    trading_pair_2: str = Field(
        default="ETH-USDT",
        json_schema_extra={
            "prompt": lambda mi: "Enter the second trading pair, only used for xemm/arbitrage (e.g. ETH-USDT): ",
            "prompt_on_new": True},
    )

    @field_validator("executor_type", mode="before")
    @classmethod
    def validate_executor_type(cls, v):
        v = str(v).lower().replace("_executor", "").strip()
        if v not in SCENARIOS:
            raise ValueError(f"Unknown executor type '{v}'. Available: {', '.join(SCENARIOS.keys())}")
        return v

    @field_validator("side", mode="before")
    @classmethod
    def validate_side(cls, v):
        v = str(v).upper().strip()
        if v not in ("BUY", "SELL"):
            raise ValueError("side must be BUY or SELL")
        return v

    def update_markets(self, markets: MarketDict) -> MarketDict:
        markets[self.connector_name] = markets.get(self.connector_name, set()) | {self.trading_pair}
        if self.executor_type in ("xemm", "arbitrage"):
            markets[self.connector_name_2] = markets.get(self.connector_name_2, set()) | {self.trading_pair_2}
        return markets


class ExecutorsQA(StrategyV2Base):
    """
    QA harness for the v2 executors: creates a single executor from a hardcoded scenario config so
    each executor type can be exercised end-to-end (creation, order placement, barriers/limits and
    shutdown). The "invalid_*" scenarios verify that broken configs are rejected by validation with
    a clear error instead of reaching the exchange.
    """

    def __init__(self, connectors, config: ExecutorsQAConfig):
        super().__init__(connectors, config)
        self.config = config
        self._executor_created = False
        self._qa_finished = False
        self._final_report_logged = False

    @property
    def trade_side(self) -> TradeType:
        return TradeType[self.config.side]

    def is_buy(self) -> bool:
        return self.trade_side == TradeType.BUY

    def passive_price(self, mid: Decimal, pct: Decimal) -> Decimal:
        """Price pct away from mid on the passive side of the configured trade side."""
        return mid * (Decimal("1") - pct) if self.is_buy() else mid * (Decimal("1") + pct)

    def aggressive_price(self, mid: Decimal, pct: Decimal) -> Decimal:
        """Price pct beyond mid on the aggressive (book-crossing) side."""
        return mid * (Decimal("1") + pct) if self.is_buy() else mid * (Decimal("1") - pct)

    def mid_price(self) -> Decimal:
        return self.market_data_provider.get_price_by_type(
            self.config.connector_name, self.config.trading_pair, PriceType.MidPrice)

    def create_actions_proposal(self) -> List[CreateExecutorAction]:
        if self._executor_created or self._qa_finished:
            return []
        scenarios = SCENARIOS[self.config.executor_type]
        if self.config.scenario == "list" or self.config.scenario not in scenarios:
            lines = [f"  - {name}: {desc}" for name, desc in scenarios.items()]
            self.logger().info(
                f"Scenarios for '{self.config.executor_type}' executor:\n" + "\n".join(lines))
            self._qa_finished = True
            return []
        try:
            mid = self.mid_price()
            if not mid or mid <= 0 or mid.is_nan():
                return []
        except Exception:
            return []  # market data not ready yet, retry next tick
        self.logger().info(
            f"QA run: executor={self.config.executor_type} scenario={self.config.scenario} "
            f"({scenarios[self.config.scenario]}) | mid price: {mid}")
        try:
            executor_config = self.build_executor_config(mid)
        except (ValidationError, ValueError) as e:
            if self.config.scenario.startswith("invalid_"):
                self.logger().info(f"QA PASSED: invalid config rejected as expected -> {e}")
            else:
                self.logger().error(f"QA FAILED: scenario config was rejected -> {e}")
            self._qa_finished = True
            return []
        if self.config.scenario.startswith("invalid_"):
            self.logger().error(
                "QA FAILED: an 'invalid_*' scenario config was accepted by validation, "
                "the executor will NOT be started")
            self._qa_finished = True
            return []
        self._executor_created = True
        self.logger().info(f"Creating executor with config: {executor_config}")
        return [CreateExecutorAction(executor_config=executor_config)]

    def stop_actions_proposal(self) -> List[StopExecutorAction]:
        # Executors stop themselves via their own barriers/limits; log a report once they are done.
        if self._executor_created and not self._final_report_logged:
            active = self.filter_executors(executors=self.get_all_executors(), filter_func=lambda e: e.is_active)
            done = self.filter_executors(executors=self.get_all_executors(), filter_func=lambda e: not e.is_active)
            if len(active) == 0 and len(done) > 0:
                for executor in done:
                    self.logger().info(
                        f"QA run finished: executor {executor.id} | status: {executor.status} | "
                        f"close type: {executor.close_type} | net pnl (quote): {executor.net_pnl_quote} | "
                        f"filled amount (quote): {executor.filled_amount_quote}")
                self._final_report_logged = True
        return []

    def build_executor_config(self, mid: Decimal) -> Optional[ExecutorConfigBase]:
        builder = getattr(self, f"{self.config.executor_type}_config")
        return builder(mid)

    def position_config(self, mid: Decimal) -> PositionExecutorConfig:
        scenario = self.config.scenario
        amount = self.config.total_amount_quote / mid
        entry_price = None
        if scenario == "default":
            entry_price = self.passive_price(mid, Decimal("0.001"))
            barriers = TripleBarrierConfig(
                stop_loss=Decimal("0.02"), take_profit=Decimal("0.01"), time_limit=600,
                open_order_type=OrderType.LIMIT, take_profit_order_type=OrderType.LIMIT)
        elif scenario == "market_entry_trailing":
            barriers = TripleBarrierConfig(
                stop_loss=Decimal("0.02"), time_limit=600, open_order_type=OrderType.MARKET,
                trailing_stop=TrailingStop(activation_price=Decimal("0.002"), trailing_delta=Decimal("0.001")))
        elif scenario == "resting_entry_timeout":
            entry_price = self.passive_price(mid, Decimal("0.02"))
            barriers = TripleBarrierConfig(
                stop_loss=Decimal("0.02"), take_profit=Decimal("0.01"), time_limit=60,
                open_order_type=OrderType.LIMIT)
        else:  # invalid_amount
            amount = Decimal("0")
            barriers = TripleBarrierConfig(stop_loss=Decimal("0.02"), take_profit=Decimal("0.01"))
        return PositionExecutorConfig(
            timestamp=self.current_timestamp, connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair, side=self.trade_side, amount=amount,
            entry_price=entry_price, triple_barrier_config=barriers, leverage=1)

    def order_config(self, mid: Decimal) -> OrderExecutorConfig:
        scenario = self.config.scenario
        amount = self.config.total_amount_quote / mid
        price = None
        chaser_config = None
        if scenario == "default":
            execution_strategy = ExecutionStrategy.LIMIT
            price = self.passive_price(mid, Decimal("0.005"))
        elif scenario == "market":
            execution_strategy = ExecutionStrategy.MARKET
        elif scenario == "limit_chaser":
            execution_strategy = ExecutionStrategy.LIMIT_CHASER
            chaser_config = LimitChaserConfig(distance=Decimal("0.001"), refresh_threshold=Decimal("0.0005"))
        elif scenario == "maker_cross":
            execution_strategy = ExecutionStrategy.LIMIT_MAKER
            price = self.aggressive_price(mid, Decimal("0.005"))
        else:  # invalid_no_price
            execution_strategy = ExecutionStrategy.LIMIT
        return OrderExecutorConfig(
            timestamp=self.current_timestamp, connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair, side=self.trade_side, amount=amount,
            price=price, chaser_config=chaser_config, execution_strategy=execution_strategy, leverage=1)

    def twap_config(self, mid: Decimal) -> TWAPExecutorConfig:
        scenario = self.config.scenario
        common = dict(
            timestamp=self.current_timestamp, connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair, side=self.trade_side,
            total_amount_quote=self.config.total_amount_quote, leverage=1)
        if scenario == "default":
            return TWAPExecutorConfig(total_duration=60, order_interval=15, mode=TWAPMode.TAKER, **common)
        elif scenario == "maker":
            return TWAPExecutorConfig(
                total_duration=120, order_interval=30, mode=TWAPMode.MAKER,
                limit_order_buffer=Decimal("0.001"), order_resubmission_time=20, **common)
        elif scenario == "single_order":
            return TWAPExecutorConfig(total_duration=10, order_interval=15, mode=TWAPMode.TAKER, **common)
        else:  # invalid_interval
            return TWAPExecutorConfig(total_duration=60, order_interval=0, mode=TWAPMode.TAKER, **common)

    def dca_config(self, mid: Decimal) -> DCAExecutorConfig:
        scenario = self.config.scenario
        weights = [Decimal("0.2"), Decimal("0.3"), Decimal("0.5")]
        amounts_quote = [self.config.total_amount_quote * w for w in weights]
        common = dict(
            timestamp=self.current_timestamp, connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair, side=self.trade_side, leverage=1)
        if scenario == "default":
            prices = [self.passive_price(mid, pct) for pct in
                      (Decimal("0.001"), Decimal("0.005"), Decimal("0.01"))]
            return DCAExecutorConfig(
                amounts_quote=amounts_quote, prices=prices, mode=DCAMode.MAKER,
                take_profit=Decimal("0.01"), stop_loss=Decimal("0.03"), time_limit=3600, **common)
        elif scenario == "taker":
            prices = [self.passive_price(mid, pct) for pct in
                      (Decimal("0.001"), Decimal("0.005"), Decimal("0.01"))]
            return DCAExecutorConfig(
                amounts_quote=amounts_quote, prices=prices, mode=DCAMode.TAKER,
                stop_loss=Decimal("0.03"), time_limit=3600,
                trailing_stop=TrailingStop(activation_price=Decimal("0.005"), trailing_delta=Decimal("0.002")),
                **common)
        elif scenario == "far_levels_timeout":
            prices = [self.passive_price(mid, pct) for pct in
                      (Decimal("0.05"), Decimal("0.06"), Decimal("0.07"))]
            return DCAExecutorConfig(
                amounts_quote=amounts_quote, prices=prices, mode=DCAMode.MAKER,
                take_profit=Decimal("0.01"), stop_loss=Decimal("0.03"), time_limit=120, **common)
        else:  # invalid_levels
            prices = [self.passive_price(mid, pct) for pct in
                      (Decimal("0.001"), Decimal("0.005"), Decimal("0.01"))]
            return DCAExecutorConfig(amounts_quote=amounts_quote[:2], prices=prices, mode=DCAMode.MAKER, **common)

    def grid_config(self, mid: Decimal) -> GridExecutorConfig:
        scenario = self.config.scenario
        barriers = TripleBarrierConfig(
            take_profit=Decimal("0.002"), open_order_type=OrderType.LIMIT,
            take_profit_order_type=OrderType.LIMIT_MAKER)
        common = dict(
            timestamp=self.current_timestamp, connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair, side=self.trade_side,
            total_amount_quote=self.config.total_amount_quote, triple_barrier_config=barriers, leverage=1)

        def limit_price(beyond_pct: Decimal) -> Decimal:
            # Stop-out sits beyond the losing edge of the range: below start for BUY, above end for SELL
            return mid * (Decimal("1") - beyond_pct) if self.is_buy() else mid * (Decimal("1") + beyond_pct)

        if scenario == "default":
            return GridExecutorConfig(
                start_price=mid * Decimal("0.99"), end_price=mid * Decimal("1.01"),
                limit_price=limit_price(Decimal("0.04")), min_order_amount_quote=Decimal("5"), **common)
        elif scenario == "tight_range":
            return GridExecutorConfig(
                start_price=mid * Decimal("0.998"), end_price=mid * Decimal("1.002"),
                limit_price=limit_price(Decimal("0.02")), min_order_amount_quote=Decimal("5"),
                max_open_orders=2, **common)
        elif scenario == "wide_sparse":
            return GridExecutorConfig(
                start_price=mid * Decimal("0.95"), end_price=mid * Decimal("1.05"),
                limit_price=limit_price(Decimal("0.08")), min_order_amount_quote=Decimal("5"),
                min_spread_between_orders=Decimal("0.005"), order_frequency=10, **common)
        else:  # invalid_range
            return GridExecutorConfig(
                start_price=mid * Decimal("1.01"), end_price=mid * Decimal("0.99"),
                limit_price=limit_price(Decimal("0.04")), **common)

    def xemm_config(self, mid: Decimal) -> XEMMExecutorConfig:
        scenario = self.config.scenario
        common = dict(
            timestamp=self.current_timestamp,
            buying_market=ConnectorPair(connector_name=self.config.connector_name,
                                        trading_pair=self.config.trading_pair),
            selling_market=ConnectorPair(connector_name=self.config.connector_name_2,
                                         trading_pair=self.config.trading_pair_2),
            maker_side=self.trade_side,
            order_amount=self.config.total_amount_quote / mid)
        if scenario == "default":
            return XEMMExecutorConfig(
                min_profitability=Decimal("0.001"), target_profitability=Decimal("0.002"),
                max_profitability=Decimal("0.004"), **common)
        elif scenario == "tight_band":
            return XEMMExecutorConfig(
                min_profitability=Decimal("0.0008"), target_profitability=Decimal("0.001"),
                max_profitability=Decimal("0.0012"), **common)
        else:  # invalid_band
            return XEMMExecutorConfig(
                min_profitability=Decimal("0.003"), target_profitability=Decimal("0.002"),
                max_profitability=Decimal("0.004"), **common)

    def arbitrage_config(self, mid: Decimal) -> ArbitrageExecutorConfig:
        scenario = self.config.scenario
        market_1 = ConnectorPair(connector_name=self.config.connector_name, trading_pair=self.config.trading_pair)
        market_2 = ConnectorPair(connector_name=self.config.connector_name_2, trading_pair=self.config.trading_pair_2)
        order_amount = self.config.total_amount_quote / mid
        if scenario == "default":
            return ArbitrageExecutorConfig(
                timestamp=self.current_timestamp, buying_market=market_1, selling_market=market_2,
                order_amount=order_amount, min_profitability=Decimal("0.002"))
        elif scenario == "force_trade":
            return ArbitrageExecutorConfig(
                timestamp=self.current_timestamp, buying_market=market_1, selling_market=market_2,
                order_amount=order_amount, min_profitability=Decimal("-0.05"))
        else:  # invalid_same_market
            return ArbitrageExecutorConfig(
                timestamp=self.current_timestamp, buying_market=market_1, selling_market=market_1,
                order_amount=order_amount, min_profitability=Decimal("0.002"))

    def format_status(self) -> str:
        scenario_desc = SCENARIOS[self.config.executor_type].get(self.config.scenario, "unknown scenario")
        header = (f"\nExecutors QA | executor: {self.config.executor_type} | scenario: {self.config.scenario} "
                  f"({scenario_desc}) | amount (quote): {self.config.total_amount_quote} | "
                  f"side: {self.config.side}\n")
        return header + super().format_status()
