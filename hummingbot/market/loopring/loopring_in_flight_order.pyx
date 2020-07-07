import copy
import json
import time
from typing import (Any, Dict, List, Tuple)
from decimal import Decimal
from hummingbot.market.loopring.loopring_order_status import LoopringOrderStatus
from hummingbot.core.event.events import (OrderFilledEvent, TradeType, OrderType, TradeFee, MarketEvent)
from hummingbot.market.in_flight_order_base cimport InFlightOrderBase
from hummingbot.market.loopring.loopring_market cimport LoopringMarket

cdef class LoopringInFlightOrder(InFlightOrderBase):
    def __init__(self, 
                 market: LoopringMarket,
                 client_order_id: str,
                 exchange_order_id: str,
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 initial_state: LoopringOrderStatus,
                 filled_size: Decimal,
                 filled_volume: Decimal,
                 filled_fee: Decimal,
                 created_at: int):

        super().__init__(market_class=LoopringMarket,
                client_order_id=client_order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=trade_type,
                price=price,
                amount=amount,
                initial_state = str(initial_state))
        self.market = market
        self.status = initial_state
        self.created_at = created_at
        self.executed_amount_base = filled_size
        self.executed_amount_quote = filled_volume
        self.fee_paid = filled_fee

    @property
    def is_done(self) -> bool:
        return self.status >= LoopringOrderStatus.DONE

    @property
    def is_cancelled(self) -> bool:
        # TODO: should this represent marked for cancelation, or fully canceled in hummingbot?
        return self.status == LoopringOrderStatus.cancelled

    @property
    def is_failure(self) -> bool:
        return self.status >= LoopringOrderStatus.FAILED

    @property
    def is_expired(self) -> bool:
        return self.status == LoopringOrderStatus.expired
    
    @property
    def description(self):
        return f"{str(self.order_type).lower()} {str(self.trade_type).lower()}"

    def to_json(self):
        return json.dumps({
           "client_order_id" : self.client_order_id,
           "exchange_order_id" : self.exchange_order_id,
           "trading_pair" : self.trading_pair,
           "order_type" : str(self.order_type),
           "trade_type" : str(self.trade_type),
           "price" : str(self.price),
           "amount" : str(self.amount),
           "status" : str(self.status),
           "executed_amount_base" : str(self.executed_amount_base),
           "executed_amount_quote" : str(self.executed_amount_quote),
           "fee_paid" : str(self.fee_paid),
           "created_at" : self.created_at
        })

    @classmethod
    def from_json(cls, market, data: Dict[str, Any]) -> LoopringInFlightOrder:
        return LoopringInFlightOrder(
            market,
            data["client_order_id"],
            data["exchange_order_id"],
            data["trading_pair"],
            OrderType[data["order_type"]],
            TradeType[data["trade_type"]],
            Decimal(data["price"]),
            Decimal(data["amount"]),
            LoopringOrderStatus[data["status"]],
            Decimal(data["executed_amount_base"]),
            Decimal(data["executed_amount_quote"]),
            Decimal(data["fee_paid"]),
            data["created_at"]
        )

    @classmethod
    def from_loopring_order(cls, 
                            market : LoopringMarket, 
                            side : TradeType,
                            client_order_id : str, 
                            created_at : int, 
                            hash: str, 
                            trading_pair: str, 
                            price: float, 
                            amount: float) -> LoopringInFlightOrder:
        return LoopringInFlightOrder(
            market,
            client_order_id,
            hash,
            trading_pair,
            OrderType.LIMIT,
            side,
            Decimal(price),
            Decimal(amount),
            LoopringOrderStatus.waiting,
            Decimal(0),
            Decimal(0),
            Decimal(0),
            created_at
        )
        

    def update(self, data : Dict[str, Any]) -> List[Any]:
        events : List[Any] = []

        base : str
        quote : str
        trading_pair : str =  data["market"]
        (base, quote) = self.market.split_trading_pair(trading_pair)
        base_id : int = self.market.token_configuration.get_tokenid(base)
        quote_id : int = self.market.token_configuration.get_tokenid(quote)
        
        new_status : LoopringOrderStatus = LoopringOrderStatus[data["status"]]
        new_executed_amount_base : Decimal = self.market.token_configuration.unpad(data["filledSize"], base_id)
        new_executed_amount_quote : Decimal = self.market.token_configuration.unpad(data["filledVolume"], quote_id)
        new_fee_paid : Decimal = Decimal(data["filledFee"])
    
        if new_executed_amount_base > self.executed_amount_base or new_executed_amount_quote > self.executed_amount_quote:
            diff_base : Decimal = new_executed_amount_base - self.executed_amount_base
            diff_quote : Decimal = new_executed_amount_quote - self.executed_amount_quote
            diff_fee : Decimal = new_fee_paid - self.fee_paid
            if diff_quote > Decimal(0):
                price : Decimal = diff_base / diff_quote
            else:
                price : Decimal = self.executed_amount_base / self.executed_amount_quote
                
            events.append( (MarketEvent.OrderFilled, diff_base, price, diff_fee) )

        if not self.is_done and new_status == LoopringOrderStatus.cancelled:
            events.append( (MarketEvent.OrderCancelled, None, None, None) )

        if not self.is_done and new_status == LoopringOrderStatus.expired:
            events.append( (MarketEvent.OrderExpired, None, None, None) )

        self.status = new_status
        self.last_state = str(new_status)
        self.executed_amount_base = new_executed_amount_base
        self.executed_amount_quote = new_executed_amount_quote
        self.fee_paid = new_fee_paid

        return events
