import logging
from decimal import Decimal
from math import floor
from typing import List, Union

from pyinjective.composer import Composer as InjectiveComposer
from pyinjective.core.network import Network
from pyinjective.orderhash import OrderHashResponse, build_eip712_msg, hash_order
from pyinjective.proto.injective.exchange.v1beta1 import (
    exchange_pb2 as injective_dot_exchange_dot_v1beta1_dot_exchange__pb2,
)
from pyinjective.proto.injective.exchange.v1beta1.exchange_pb2 import DerivativeOrder, SpotOrder
from pyinjective.utils.denom import Denom

from hummingbot.connector.gateway.clob_spot.data_sources.injective.injective_constants import (
    ACC_NONCE_PATH_RATE_LIMIT_ID,
    NONCE_PATH,
    RATE_LIMITS,
)
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class OrderHashManager:
    def __init__(self, network: Network, sub_account_id: str):
        self._sub_account_id = sub_account_id
        self._network = network
        self._sub_account_nonce = 0
        self._web_assistants_factory = WebAssistantsFactory(throttler=AsyncThrottler(rate_limits=RATE_LIMITS))

    @property
    def current_nonce(self) -> int:
        return self._sub_account_nonce

    async def start(self):
        url = f"{self._network.lcd_endpoint}/{NONCE_PATH}/{self._sub_account_id}"
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        res = await rest_assistant.execute_request(url=url, throttler_limit_id=ACC_NONCE_PATH_RATE_LIMIT_ID)
        nonce = res["nonce"]
        self._sub_account_nonce = nonce + 1

    def compute_order_hashes(
        self, spot_orders: List[SpotOrder], derivative_orders: List[DerivativeOrder]
    ) -> OrderHashResponse:
        order_hashes = OrderHashResponse(spot=[], derivative=[])

        for o in spot_orders:
            order_hash = hash_order(build_eip712_msg(o, self._sub_account_nonce))
            order_hashes.spot.append(order_hash)
            self._sub_account_nonce += 1

        for o in derivative_orders:
            order_hash = hash_order(build_eip712_msg(o, self._sub_account_nonce))
            order_hashes.derivative.append(order_hash)
            self._sub_account_nonce += 1

        return order_hashes


class Composer(InjectiveComposer):
    def DerivativeOrder(
        self,
        market_id: str,
        subaccount_id: str,
        fee_recipient: str,
        price: float,
        quantity: float,
        trigger_price: float = 0,
        **kwargs,
    ):
        """Changes the way the margin is computed to be synchronous with the approach used by Gateway."""
        # load denom metadata
        denom = Denom.load_market(self.network, market_id)
        logging.info("Loaded market metadata for:{}".format(denom.description))

        if kwargs.get("is_reduce_only") is None:
            margin = derivative_margin_to_backend_using_gateway_approach(
                price, quantity, kwargs.get("leverage"), denom
            )
        elif kwargs.get("is_reduce_only", True):
            margin = 0
        else:
            margin = derivative_margin_to_backend_using_gateway_approach(
                price, quantity, kwargs.get("leverage"), denom
            )

        # prepare values
        price = derivative_price_to_backend(price, denom)
        trigger_price = derivative_price_to_backend(trigger_price, denom)
        quantity = derivative_quantity_to_backend(quantity, denom)

        if kwargs.get("is_buy") and not kwargs.get("is_po"):
            order_type = injective_dot_exchange_dot_v1beta1_dot_exchange__pb2.OrderType.BUY

        elif not kwargs.get("is_buy") and not kwargs.get("is_po"):
            order_type = injective_dot_exchange_dot_v1beta1_dot_exchange__pb2.OrderType.SELL

        elif kwargs.get("is_buy") and kwargs.get("is_po"):
            order_type = injective_dot_exchange_dot_v1beta1_dot_exchange__pb2.OrderType.BUY_PO

        elif not kwargs.get("is_buy") and kwargs.get("is_po"):
            order_type = injective_dot_exchange_dot_v1beta1_dot_exchange__pb2.OrderType.SELL_PO

        elif kwargs.get("stop_buy"):
            order_type = injective_dot_exchange_dot_v1beta1_dot_exchange__pb2.OrderType.STOP_BUY

        elif kwargs.get("stop_sell"):
            order_type = injective_dot_exchange_dot_v1beta1_dot_exchange__pb2.OrderType.STOP_SEll

        elif kwargs.get("take_buy"):
            order_type = injective_dot_exchange_dot_v1beta1_dot_exchange__pb2.OrderType.TAKE_BUY

        elif kwargs.get("take_sell"):
            order_type = injective_dot_exchange_dot_v1beta1_dot_exchange__pb2.OrderType.TAKE_SELL

        return injective_dot_exchange_dot_v1beta1_dot_exchange__pb2.DerivativeOrder(
            market_id=market_id,
            order_info=injective_dot_exchange_dot_v1beta1_dot_exchange__pb2.OrderInfo(
                subaccount_id=subaccount_id,
                fee_recipient=fee_recipient,
                price=str(price),
                quantity=str(quantity),
            ),
            margin=str(margin),
            order_type=order_type,
            trigger_price=str(trigger_price),
        )


def derivative_margin_to_backend_using_gateway_approach(
    price: float, quantity: float, leverage: float, denom: Denom
) -> int:
    decimals = Decimal(18 + denom.quote)
    price_big = Decimal(str(price)) * 10 ** decimals
    quantity_big = Decimal(str(quantity)) * 10 ** decimals
    leverage_big = Decimal(str(leverage)) * 10 ** decimals
    decimals_big = 10 ** decimals

    numerator = price_big * quantity_big * decimals_big
    denominator = leverage_big * decimals_big
    res = int(numerator / denominator)

    return res


def floor_to(value: Union[float, Decimal], target: Union[float, Decimal]) -> Decimal:
    value_tmp = Decimal(str(value))
    target_tmp = Decimal(str(target))
    result = int(floor(value_tmp / target_tmp)) * target_tmp
    return result


def derivative_quantity_to_backend(quantity, denom) -> int:
    quantity_tick_size = float(denom.min_quantity_tick_size) / pow(10, denom.base)
    scale_quantity = Decimal(18 + denom.base)
    exchange_quantity = floor_to(quantity, quantity_tick_size) * pow(Decimal(10), scale_quantity)
    return int(exchange_quantity)


def derivative_price_to_backend(price, denom) -> int:
    price_tick_size = Decimal(denom.min_price_tick_size) / pow(10, denom.quote)
    exchange_price = floor_to(price, float(price_tick_size)) * pow(10, 18 + denom.quote)
    return int(exchange_price)
