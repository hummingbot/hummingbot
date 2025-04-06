from decimal import Decimal

import requests
from eip712.messages import EIP712Message, EIP712Type
from eth_account.messages import _hash_eip191_message as hash_eip191_message
from hexbytes import HexBytes

from pyinjective.core.token import Token


class OrderInfo(EIP712Type):
    SubaccountId: "string"  # noqa: F821
    FeeRecipient: "string"  # noqa: F821
    Price: "string"  # noqa: F821
    Quantity: "string"  # noqa: F821


class SpotOrder(EIP712Message):
    _name_ = "Injective Protocol"
    _version_ = "2.0.0"
    _chainId_ = 888
    _verifyingContract_ = "0xCcCCccccCCCCcCCCCCCcCcCccCcCCCcCcccccccC"
    _salt_ = HexBytes("0x0000000000000000000000000000000000000000000000000000000000000000")

    MarketId: "string"  # noqa: F821
    OrderInfo: OrderInfo
    Salt: "string"  # noqa: F821
    OrderType: "string"  # noqa: F821
    TriggerPrice: "string"  # noqa: F821


class DerivativeOrder(EIP712Message):
    _name_ = "Injective Protocol"
    _version_ = "2.0.0"
    _chainId_ = 888
    _verifyingContract_ = "0xCcCCccccCCCCcCCCCCCcCcCccCcCCCcCcccccccC"
    _salt_ = HexBytes("0x0000000000000000000000000000000000000000000000000000000000000000")

    MarketId: "string"  # noqa: F821
    OrderInfo: OrderInfo
    OrderType: "string"  # noqa: F821
    Margin: "string"  # noqa: F821
    TriggerPrice: "string"  # noqa: F821
    Salt: "string"  # noqa: F821


# domain_separator = EIP712_domain.hash_struct()
order_type_dict = {0: "\x00", 1: "\x01", 2: "\x02", 3: "\x03", 4: "\x04", 5: "\x05", 6: "\x06", 7: "\x07", 8: "\x08"}


class OrderHashResponse:
    def __init__(
        self,
        spot: [str] = None,
        derivative: [str] = None,
    ):
        self.spot = spot
        self.derivative = derivative


class OrderHashManager:
    def __init__(
        self,
        address,
        network,
        subaccount_indexes: [int] = None,
    ):
        self.address = address
        self.subacc_nonces = dict()

        for i in subaccount_indexes:
            subaccount_id = address.get_subaccount_id(index=i)
            url = network.lcd_endpoint + "/injective/exchange/v1beta1/exchange/" + subaccount_id
            res = requests.get(url=url)
            nonce = res.json()["nonce"]
            self.subacc_nonces[i] = [subaccount_id, nonce + 1]

    def compute_order_hashes(self, spot_orders, derivative_orders, subaccount_index) -> [str]:
        if len(spot_orders) + len(derivative_orders) == 0:
            return []

        order_hashes = OrderHashResponse(spot=[], derivative=[])

        for o in spot_orders:
            msg = build_eip712_msg(o, self.subacc_nonces[subaccount_index][1])
            order_hash = hash_order(msg)
            order_hashes.spot.append(order_hash)
            self.subacc_nonces[subaccount_index][1] += 1

        for o in derivative_orders:
            msg = build_eip712_msg(o, self.subacc_nonces[subaccount_index][1])
            order_hash = hash_order(msg)
            order_hashes.derivative.append(order_hash)
            self.subacc_nonces[subaccount_index][1] += 1

        return order_hashes


def param_to_backend_go(param: str) -> str:
    go_param = Token.convert_value_from_extended_decimal_format(value=Decimal(param))
    return f"{go_param.normalize():.18f}"


def parse_order_type(order):
    return order_type_dict[order.order_type]


def build_eip712_msg(order, nonce):
    if order.__class__.__name__ == "SpotOrder":
        go_price = param_to_backend_go(order.order_info.price)
        go_trigger_price = param_to_backend_go(order.trigger_price)
        go_quantity = param_to_backend_go(order.order_info.quantity)
        go_order_type = parse_order_type(order)
        return SpotOrder(
            MarketId=order.market_id,
            OrderInfo=OrderInfo(
                SubaccountId=order.order_info.subaccount_id,
                FeeRecipient=order.order_info.fee_recipient,
                Price=go_price,
                Quantity=go_quantity,
            ),
            Salt=str(nonce),
            OrderType=go_order_type,
            TriggerPrice=go_trigger_price,
        )
    if order.__class__.__name__ == "DerivativeOrder":
        go_price = param_to_backend_go(order.order_info.price)
        go_trigger_price = param_to_backend_go(order.trigger_price)
        go_quantity = param_to_backend_go(order.order_info.quantity)
        go_margin = param_to_backend_go(order.margin)
        go_order_type = parse_order_type(order)
        return DerivativeOrder(
            MarketId=order.market_id,
            OrderInfo=OrderInfo(
                SubaccountId=order.order_info.subaccount_id,
                FeeRecipient=order.order_info.fee_recipient,
                Price=go_price,
                Quantity=go_quantity,
            ),
            Salt=str(nonce),
            OrderType=go_order_type,
            TriggerPrice=go_trigger_price,
            Margin=go_margin,
        )


def hash_order(msg):
    signable_message = msg.signable_message
    hex_digest = hash_eip191_message(signable_message=signable_message).hex()
    return "0x" + hex_digest
