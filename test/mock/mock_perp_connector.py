from decimal import Decimal
from typing import Optional

from hummingbot.connector.derivative.perpetual_budget_checker import PerpetualBudgetChecker
from hummingbot.connector.perpetual_trading import PerpetualTrading
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TradeFeeSchema
from hummingbot.core.event.events import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.utils.estimate_fee import build_perpetual_trade_fee
from test.mock.mock_paper_exchange import MockPaperExchange


class MockPerpConnector(MockPaperExchange, PerpetualTrading):
    def __init__(
        self,
        trade_fee_schema: Optional[TradeFeeSchema] = None,
        buy_collateral_token: Optional[str] = None,
        sell_collateral_token: Optional[str] = None,
    ):
        MockPaperExchange.__init__(self, trade_fee_schema)
        PerpetualTrading.__init__(self)
        self._budget_checker = PerpetualBudgetChecker(exchange=self)
        self._funding_payment_span = [0, 10]
        self._buy_collateral_token = buy_collateral_token
        self._sell_collateral_token = sell_collateral_token

    def supported_position_modes(self):
        return [PositionMode.ONEWAY, PositionMode.HEDGE]

    @property
    def name(self):
        return "MockPerpConnector"

    @property
    def budget_checker(self) -> PerpetualBudgetChecker:
        return self._budget_checker

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        token = (
            super().get_buy_collateral_token(trading_pair)
            if self._buy_collateral_token is None
            else self._buy_collateral_token
        )
        return token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        token = (
            super().get_sell_collateral_token(trading_pair)
            if self._sell_collateral_token is None
            else self._sell_collateral_token
        )
        return token

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = Decimal("0"),
                is_maker: Optional[bool] = None,
                position_action: PositionAction = PositionAction.OPEN) -> AddedToCostTradeFee:
        return build_perpetual_trade_fee(
            exchange=self.name,
            is_maker=is_maker,
            position_action=position_action,
            base_currency=base_currency,
            quote_currency=quote_currency,
            order_type=order_type,
            order_side=order_side,
            amount=amount,
            price=price,
        )
