import time
from decimal import Decimal
from typing import Dict, List, Set

# import pandas as pd
from pydantic import Field, validator

from hummingbot.client.config.config_data_types import ClientFieldData

# from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PriceType, TradeType
from hummingbot.core.event.events import FundingPaymentCompletedEvent
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.controllers.controller_base import ControllerBase, ControllerConfigBase
from hummingbot.smart_components.executors.position_executor.data_types import (
    PositionExecutorConfig,
    TripleBarrierConfig,
)
from hummingbot.smart_components.models.executor_actions import CreateExecutorAction, ExecutorAction, StopExecutorAction


class SpotPerpArbitrageConfig(ControllerConfigBase):
    controller_name: str = "spot_perp_arbitrage"
    candles_config: List[CandlesConfig] = []
    controllers_config: List[str] = []

    spot_connector_name: str = Field(
        default="binance",
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the spot connector (e.g., binance): ",
            prompt_on_new=True
        ))
    spot_trading_pair: str = Field(
        default="DOGE-USDT",
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the spot trading pair (e.g., BTC-USDT): ",
            prompt_on_new=True
        ))
    connector_name: str = Field(
        default="binance_perpetual",
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the perp connector (e.g., binance Perpetual): ",
            prompt_on_new=True
        ))
    trading_pair: str = Field(
        default="DOGE-USDT",
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the perp trading pair (e.g., BTC-USDT): ",
            prompt_on_new=True
        ))
    leverage: int = Field(
        default=3, gt=0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the leverage (e.g. 3): ",
            prompt_on_new=True
        ))
    position_mode: PositionMode = Field(
        default="HEDGE",
        client_data=ClientFieldData(
            prompt=lambda msg: "Enter the position mode (HEDGE/ONEWAY): ",
            prompt_on_new=False
        )
    )
    position_size_quote: float = Field(
        default=50,
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the position size in quote currency: ",
            prompt_on_new=True
        ))
    entry: Decimal = Field(
        default=0.001,
        client_data=ClientFieldData(
            prompt=lambda e: "Minimum difference between spot and perpetual markets to enter a position: ",
            prompt_on_new=True
        ))
    profitability_to_take_profit: float = Field(
        default=0.01,
        client_data=ClientFieldData(
            prompt=lambda e: "Enter the profitability to take profit (including PNL of positions and fundings received) ",
            prompt_on_new=True
        ))

    @validator('position_mode', pre=True, allow_reuse=True)
    def validate_position_mode(cls, value: str) -> PositionMode:
        if isinstance(value, str) and value.upper() in PositionMode.__members__:
            return PositionMode[value.upper()]
        raise ValueError(f"Invalid position mode: {value}. Valid options are: {', '.join(PositionMode.__members__)}")

    def update_markets(self, markets: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
        if self.spot_connector_name not in markets:
            markets[self.spot_connector_name] = set()
        markets[self.spot_connector_name].add(self.spot_trading_pair)
        if self.connector_name not in markets:
            markets[self.connector_name] = set()
        markets[self.connector_name].add(self.trading_pair)
        return markets


class SpotPerpArbitrage(ControllerBase):

    def __init__(self, config: SpotPerpArbitrageConfig, *args, **kwargs):
        self.config = config
        super().__init__(config, *args, **kwargs)
        self.funding_payments = Decimal('0.0')
        self.funding_payments_list = []

    @property
    def connector_name(self):
        return self.market_data_provider.connectors[self.config.connector_name]

    @property
    def spot_connector_name(self):
        return self.market_data_provider.connectors[self.config.spot_connector_name]

    def get_current_profitability_after_fees(self):
        spot_trading_pair = self.config.spot_trading_pair
        trading_pair = self.config.trading_pair

        connector_spot_price = Decimal(self.market_data_provider.get_price_for_quote_volume(
            connector_name=self.config.spot_connector_name,
            trading_pair=spot_trading_pair,
            quote_volume=self.config.position_size_quote,
            is_buy=True,
        ).result_price)
        connector_perp_price = Decimal(self.market_data_provider.get_price_for_quote_volume(
            connector_name=self.config.connector_name,
            trading_pair=trading_pair,
            quote_volume=self.config.position_size_quote,
            is_buy=False,
        ).result_price)
        estimated_fees_spot_connector_name = self.spot_connector_name.get_fee(
            base_currency=spot_trading_pair.split("-")[0],
            quote_currency=spot_trading_pair.split("-")[1],
            order_type=OrderType.MARKET,
            order_side=TradeType.BUY,
            amount=self.config.position_size_quote / float(connector_spot_price),
            price=connector_spot_price,
            is_maker=False,
        ).percent
        estimated_fees_connector_name = self.connector_name.get_fee(
            base_currency=trading_pair.split("-")[0],
            quote_currency=trading_pair.split("-")[1],
            order_type=OrderType.MARKET,
            order_side=TradeType.BUY,
            amount=self.config.position_size_quote / float(connector_perp_price),
            price=connector_perp_price,
            is_maker=False,
            position_action=PositionAction.OPEN
        ).percent

        estimated_trade_pnl_pct = (connector_perp_price - connector_spot_price) / connector_spot_price
        return estimated_trade_pnl_pct - estimated_fees_spot_connector_name - estimated_fees_connector_name

    def is_active_arbitrage(self):
        executors = self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda e: e.is_active
        )
        return len(executors) > 0

    def current_pnl_pct(self):
        executors = self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda e: e.is_active
        )
        filled_amount = sum(e.filled_amount_quote for e in executors)
        total_pnl_from_trades = sum(e.net_pnl_quote for e in executors)
        total_pnl_including_funding = total_pnl_from_trades + self.funding_payments
        return total_pnl_including_funding / filled_amount if filled_amount > 0 else 0

    async def update_processed_data(self):
        self.processed_data = {
            "profitability": self.get_current_profitability_after_fees(),
            "active_arbitrage": self.is_active_arbitrage(),
            "current_pnl": self.current_pnl_pct(),
            "funding_rate": self.get_funding_info_by_token(),
            "funding_payments": self.funding_payments
        }

    def determine_executor_actions(self) -> List[ExecutorAction]:
        executor_actions = []
        executor_actions.extend(self.create_new_arbitrage_actions())
        executor_actions.extend(self.stop_arbitrage_actions())
        return executor_actions

    def create_new_arbitrage_actions(self):
        create_actions = []
        if not self.processed_data["active_arbitrage"] and self.processed_data["profitability"] > self.config.entry:
            mid_price = self.market_data_provider.get_price_by_type(self.config.spot_connector_name,
                                                                    self.config.spot_trading_pair, PriceType.MidPrice)
            create_actions.append(CreateExecutorAction(
                controller_id=self.config.id,
                executor_config=PositionExecutorConfig(
                    timestamp=time.time(),
                    connector_name=self.config.spot_connector_name,
                    trading_pair=self.config.spot_trading_pair,
                    side=TradeType.BUY,
                    amount=Decimal(self.config.position_size_quote) / mid_price,
                    triple_barrier_config=TripleBarrierConfig(open_order_type=OrderType.MARKET),
                )
            ))
            create_actions.append(CreateExecutorAction(
                controller_id=self.config.id,
                executor_config=PositionExecutorConfig(
                    timestamp=time.time(),
                    connector_name=self.config.connector_name,
                    trading_pair=self.config.trading_pair,
                    leverage=self.config.leverage,
                    side=TradeType.SELL,
                    amount=Decimal(self.config.position_size_quote) / mid_price,
                    triple_barrier_config=TripleBarrierConfig(open_order_type=OrderType.MARKET),
                )
            ))
        return create_actions

    def stop_arbitrage_actions(self):
        stop_actions = []
        if self.processed_data["current_pnl"] > self.config.profitability_to_take_profit:
            executors = self.filter_executors(
                executors=self.executors_info,
                filter_func=lambda e: e.is_active
            )
            for executor in executors:
                stop_actions.append(StopExecutorAction(controller_id=self.config.id, executor_id=executor.id))
        return stop_actions

    def get_funding_info_by_token(self):
        funding_rates = {}
        connector = self.connector_name
        trading_pair = self.config.trading_pair
        funding_rates = connector.get_funding_info(trading_pair).rate
        return funding_rates

    def did_complete_funding_payment(self, funding_completed_event: FundingPaymentCompletedEvent):
        self.funding_payments_list.append(funding_completed_event.amount)
        self.funding_payments = sum(self.funding_payments_list)

    def to_format_status(self) -> List[str]:
        return [f"Current profitability: {self.processed_data['profitability']:.4f} | Entry limit: {self.config.entry}",
                f"Active arbitrage: {self.processed_data['active_arbitrage']}",
                f"Current PnL: {self.current_pnl_pct():.4f}",
                f"Current funding rate (8h) for {self.config.trading_pair}: {self.processed_data['funding_rate']:.4f}",
                f"Cumulative total of funding payments received : {self.processed_data['funding_payments']:.4f}"]
