import logging
import os
from decimal import Decimal
from typing import Dict, List

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel, ClientFieldData
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class SimplePMMConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    exchange: str = Field("binance_paper_trade", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Exchange where the bot will trade"))
    trading_pair: str = Field("ETH-USDT", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Trading pair in which the bot will place orders"))
    order_amount: Decimal = Field(0.01, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Order amount (denominated in base asset)"))
    bid_spread: Decimal = Field(0.001, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Bid order spread (in percent)"))
    ask_spread: Decimal = Field(0.001, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Ask order spread (in percent)"))
    order_refresh_time: int = Field(15, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Order refresh time (in seconds)"))
    price_type: str = Field("mid", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Price type to use (mid or last)"))


class SimplePMM(ScriptStrategyBase):
    """
    BotCamp Cohort: Sept 2022
    Design Template: https://hummingbot-foundation.notion.site/Simple-PMM-63cc765486dd42228d3da0b32537fc92
    Video: -
    Description:
    The bot will place two orders around the price_source (mid price or last traded price) in a trading_pair on
    exchange, with a distance defined by the ask_spread and bid_spread. Every order_refresh_time in seconds,
    the bot will cancel and replace the orders.
    """

    create_timestamp = 0
    price_source = PriceType.MidPrice

    @classmethod
    def init_markets(cls, config: SimplePMMConfig):
        cls.markets = {config.exchange: {config.trading_pair}}
        cls.price_source = PriceType.LastTrade if config.price_type == "last" else PriceType.MidPrice

    def __init__(self, connectors: Dict[str, ConnectorBase], config: SimplePMMConfig):
        super().__init__(connectors)
        self.config = config

    def on_tick(self):
        if self.create_timestamp <= self.current_timestamp:
            self.cancel_all_orders()
            proposal: List[OrderCandidate] = self.create_proposal()
            proposal_adjusted: List[OrderCandidate] = self.adjust_proposal_to_budget(proposal)
            self.place_orders(proposal_adjusted)
            self.create_timestamp = self.config.order_refresh_time + self.current_timestamp

    def create_proposal(self) -> List[OrderCandidate]:
        ref_price = self.connectors[self.config.exchange].get_price_by_type(self.config.trading_pair, self.price_source)
        buy_price = ref_price * Decimal(1 - self.config.bid_spread)
        sell_price = ref_price * Decimal(1 + self.config.ask_spread)

        buy_order = OrderCandidate(trading_pair=self.config.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                   order_side=TradeType.BUY, amount=Decimal(self.config.order_amount), price=buy_price)

        sell_order = OrderCandidate(trading_pair=self.config.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                    order_side=TradeType.SELL, amount=Decimal(self.config.order_amount), price=sell_price)

        return [buy_order, sell_order]

    def adjust_proposal_to_budget(self, proposal: List[OrderCandidate]) -> List[OrderCandidate]:
        proposal_adjusted = self.connectors[self.config.exchange].budget_checker.adjust_candidates(proposal, all_or_none=True)
        return proposal_adjusted

    def place_orders(self, proposal: List[OrderCandidate]) -> None:
        for order in proposal:
            self.place_order(connector_name=self.config.exchange, order=order)

    def place_order(self, connector_name: str, order: OrderCandidate):
        if order.order_side == TradeType.SELL:
            self.sell(connector_name=connector_name, trading_pair=order.trading_pair, amount=order.amount,
                      order_type=order.order_type, price=order.price)
        elif order.order_side == TradeType.BUY:
            self.buy(connector_name=connector_name, trading_pair=order.trading_pair, amount=order.amount,
                     order_type=order.order_type, price=order.price)

    def cancel_all_orders(self):
        for order in self.get_active_orders(connector_name=self.config.exchange):
            self.cancel(self.config.exchange, order.trading_pair, order.client_order_id)

    def did_fill_order(self, event: OrderFilledEvent):
        msg = (f"{event.trade_type.name} {round(event.amount, 2)} {event.trading_pair} {self.config.exchange} at {round(event.price, 2)}")
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)
