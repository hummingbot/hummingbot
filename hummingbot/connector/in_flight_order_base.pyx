import asyncio
from decimal import Decimal
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.event.events import (
    OrderType,
    TradeType
)
from async_timeout import timeout

s_decimal_0 = Decimal(0)

GET_EX_ORDER_ID_TIMEOUT = 10  # seconds

cdef class InFlightOrderBase:
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 initial_state: str):

        self.client_order_id = client_order_id
        self.exchange_order_id = exchange_order_id
        self.trading_pair = trading_pair
        self.order_type = order_type
        self.trade_type = trade_type
        self.price = price
        self.amount = amount
        self.executed_amount_base = s_decimal_0
        self.executed_amount_quote = s_decimal_0
        self.fee_asset = None
        self.fee_paid = s_decimal_0
        self.last_state = initial_state
        self.exchange_order_id_update_event = asyncio.Event()
        self.completely_filled_event = asyncio.Event()

    def __repr__(self) -> str:
        return f"InFlightOrder(" \
               f"client_order_id='{self.client_order_id}', " \
               f"exchange_order_id='{self.exchange_order_id}', " \
               f"trading_pair='{self.trading_pair}', " \
               f"order_type={self.order_type}, " \
               f"trade_type={self.trade_type}, " \
               f"price={self.price}, " \
               f"amount={self.amount}, " \
               f"executed_amount_base={self.executed_amount_base}, " \
               f"executed_amount_quote={self.executed_amount_quote}, " \
               f"fee_asset='{self.fee_asset}', " \
               f"fee_paid={self.fee_paid}, " \
               f"last_state='{self.last_state}')"

    @property
    def is_done(self) -> bool:
        raise NotImplementedError

    @property
    def is_cancelled(self) -> bool:
        raise NotImplementedError

    @property
    def is_failure(self) -> bool:
        raise NotImplementedError

    @property
    def base_asset(self) -> str:
        return self.trading_pair.split("-")[0]

    @property
    def quote_asset(self) -> str:
        return self.trading_pair.split("-")[1]

    def update_exchange_order_id(self, exchange_id: str):
        self.exchange_order_id = exchange_id
        self.exchange_order_id_update_event.set()

    async def get_exchange_order_id(self):
        if self.exchange_order_id is None:
            async with timeout(GET_EX_ORDER_ID_TIMEOUT):
                await self.exchange_order_id_update_event.wait()
        return self.exchange_order_id

    def to_limit_order(self) -> LimitOrder:
        return LimitOrder(
            self.client_order_id,
            self.trading_pair,
            self.trade_type is TradeType.BUY,
            self.base_asset,
            self.quote_asset,
            self.price,
            self.amount
        )

    def to_json(self) -> Dict[str, Any]:
        return {
            "client_order_id": self.client_order_id,
            "exchange_order_id": self.exchange_order_id,
            "trading_pair": self.trading_pair,
            "order_type": self.order_type.name,
            "trade_type": self.trade_type.name,
            "price": str(self.price),
            "amount": str(self.amount),
            "executed_amount_base": str(self.executed_amount_base),
            "executed_amount_quote": str(self.executed_amount_quote),
            "fee_asset": self.fee_asset,
            "fee_paid": str(self.fee_paid),
            "last_state": self.last_state
        }

    @classmethod
    def _instance_creation_parameters_from_json(cls, data: Dict[str, Any]) -> List[Any]:
        return [
            data["client_order_id"],
            data["exchange_order_id"],
            data["trading_pair"],
            getattr(OrderType, data["order_type"]),
            getattr(TradeType, data["trade_type"]),
            Decimal(data["price"]),
            Decimal(data["amount"]),
            data["last_state"]]

    @classmethod
    def _basic_from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        """
        :param data: json data from API
        :return: formatted InFlightOrder
        """
        arguments = cls._instance_creation_parameters_from_json(data)
        order = cls(*arguments)
        order.executed_amount_base = Decimal(data["executed_amount_base"])
        order.executed_amount_quote = Decimal(data["executed_amount_quote"])
        order.fee_asset = data["fee_asset"]
        order.fee_paid = Decimal(data["fee_paid"])
        return order

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        raise NotImplementedError

    def check_filled_condition(self):
        if (abs(self.amount) - self.executed_amount_base).quantize(Decimal('1e-8')) <= 0:
            self.completely_filled_event.set()

    async def wait_until_completely_filled(self):
        await self.completely_filled_event.wait()
