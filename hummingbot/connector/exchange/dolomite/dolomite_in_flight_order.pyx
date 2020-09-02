import time
from typing import (Any, Dict, List)
from decimal import Decimal
from hummingbot.core.event.events import (OrderFilledEvent, TradeType, OrderType, TradeFee)
from hummingbot.connector.in_flight_order_base cimport InFlightOrderBase
from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.connector.exchange.dolomite.dolomite_util import (unpad)

s_decimal_0 = Decimal(0)


def now():
    return int(time.time()) * 1000


def ticker_for(padded_obj):
    return padded_obj["currency"]["ticker"]


def f_round(f, r):
    return Decimal(round(Decimal(f), r))


cdef class DolomiteInFlightOrder(InFlightOrderBase):
    @property
    def is_done(self) -> bool:
        return self.last_state == "FILLED"

    @property
    def is_cancelled(self) -> bool:
        return self.last_state == "CANCELLED"

    @property
    def is_failure(self) -> bool:
        return self.last_state == "REJECTED" or self.last_state == "RESUBMISSION_FAILURE"

    @property
    def is_expired(self) -> bool:
        return self.last_state == "EXPIRED"

    @property
    def description(self):
        _type = "limit" if self.order_type == OrderType.LIMIT else "limit_maker"
        _side = "buy" if self.trade_type == TradeType.BUY else "sell"
        return f"{_type} {_side}"

    @property
    def identifier(self):
        return f"{self.exchange_order_id} ({self.client_order_id})"

    @classmethod
    def from_json(cls, data: Dict[str, Any], market) -> DolomiteInFlightOrder:
        return DolomiteInFlightOrder(
            market,
            data["client_order_id"],
            data["exchange_order_id"],
            data["trading_pair"],
            getattr(OrderType, data["order_type"]),
            getattr(TradeType, data["trade_type"]),
            Decimal(data["price"]),
            Decimal(data["amount"]),
            data["last_state"]
        )

    @classmethod
    def from_dolomite_order(cls, dolomite_order: Dict[str, Any], client_order_id: str, market: ExchangeBase) -> DolomiteInFlightOrder:
        order_type = (OrderType.LIMIT, OrderType.LIMIT_MAKER)[dolomite_order["order_type"] == "LIMIT_MAKER"]
        order_side = (TradeType.SELL, TradeType.BUY)[dolomite_order["order_side"] == "BUY"]

        price = (order_type == OrderType.LIMIT
                 and unpad(dolomite_order["market_order_effective_price"])
                 or Decimal(dolomite_order["exchange_rate"]))

        return DolomiteInFlightOrder(
            client_order_id=client_order_id,
            exchange_order_id=dolomite_order["dolomite_order_id"],
            trading_pair=dolomite_order["market"],
            order_type=order_type,
            trade_type=order_side,
            price=price,
            amount=unpad(dolomite_order["primary_amount"]),
            initial_state=dolomite_order["order_status"]
        )

    def apply_update(self,
                     dolomite_order: Dict[str, Any],
                     fills: List[Dict[str, Any]],
                     exchange_info,
                     exchange_rates) -> List[OrderFilledEvent]:
        if self.tracked_fill_ids is None:
            self.tracked_fill_ids = []

        fill_events = []

        if self.order_type is OrderType.LIMIT_MAKER and len(fills) > 0:
            for fill in fills:
                if fill["dolomite_order_fill_id"] not in self.tracked_fill_ids:
                    primary_fill_amount = unpad(fill["primary_amount"])
                    secondary_fill_amount = unpad(fill["secondary_amount"])
                    execution_price = secondary_fill_amount / primary_fill_amount
                    fee_percentage = unpad(fill["fee_amount_usd"]) / unpad(fill["usd_amount"])

                    filled_event = OrderFilledEvent(
                        timestamp=now(),
                        order_id=self.client_order_id,
                        trading_pair=self.trading_pair,
                        trade_type=self.trade_type,
                        order_type=self.order_type,
                        price=Decimal(execution_price),
                        amount=Decimal(primary_fill_amount),
                        trade_fee=TradeFee(percent=f_round(fee_percentage, 4))
                    )

                    fill_events.append(filled_event)
                    self.tracked_fill_ids.append(fill["dolomite_order_fill_id"])

        elif self.order_type is OrderType.LIMIT and len(fills) > 0:
            order_fee_token = ticker_for(dolomite_order["base_taker_gas_fee_amount"])
            fee_token_burn_rate = Decimal(exchange_info.fee_burn_rates_table[order_fee_token])

            per_fill_base_fee = unpad(dolomite_order["base_taker_gas_fee_amount"])
            per_fill_base_fee_usd = exchange_rates.to_base(per_fill_base_fee, order_fee_token, "USD")

            excess_fills_count = int(dolomite_order["max_number_of_taker_matches"]) - len(fills)
            total_burned_excess_fee_usd = Decimal(excess_fills_count) * per_fill_base_fee_usd * (1 - fee_token_burn_rate)
            per_fill_burned_excess_fee_usd = total_burned_excess_fee_usd / Decimal(len(fills))

            # Flat network fee in terms of USD for each taker fill
            network_fee_per_fill_usd = per_fill_base_fee_usd + per_fill_burned_excess_fee_usd

            for fill in fills:
                if fill["dolomite_order_fill_id"] not in self.tracked_fill_ids:
                    primary_fill_amount = unpad(fill["primary_amount"])
                    secondary_fill_amount = unpad(fill["secondary_amount"])
                    execution_price = secondary_fill_amount / primary_fill_amount

                    service_fee_amount_usd = max(unpad(fill["fee_amount_usd"]) - network_fee_per_fill_usd, 0)
                    fee_percentage = service_fee_amount_usd / unpad(fill["usd_amount"])

                    fill_fee_token = ticker_for(fill["fee_amount"])
                    fill_total_fee_amount = unpad(fill["fee_amount"])
                    fill_network_fee = exchange_rates.from_base(network_fee_per_fill_usd, "USD", fill_fee_token)

                    filled_event = OrderFilledEvent(
                        timestamp=now(),
                        order_id=self.client_order_id,
                        trading_pair=self.trading_pair,
                        trade_type=self.trade_type,
                        order_type=self.order_type,
                        price=Decimal(execution_price),
                        amount=Decimal(primary_fill_amount),
                        trade_fee=TradeFee(percent=f_round(fee_percentage, 4), flat_fees=[(fill_fee_token, Decimal(fill_network_fee))])
                    )

                    fill_events.append(filled_event)
                    self.tracked_fill_ids.append(fill["dolomite_order_fill_id"])

        self.last_state = dolomite_order["order_status"]
        return fill_events
