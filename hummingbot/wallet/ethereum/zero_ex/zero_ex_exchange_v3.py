import os
from decimal import Decimal
from typing import (
    List,
    Tuple
)
import ujson
from web3 import Web3
from web3.contract import Contract
from zero_ex.order_utils import Order

from hummingbot.wallet.ethereum.web3_wallet import Web3Wallet
from hummingbot.wallet.ethereum.zero_ex.zero_ex_custom_utils_v3 import convert_order_to_tuple

with open(os.path.join(os.path.dirname(__file__), "zero_ex_exchange_abi_v3.json")) as exchange_abi_json:
    exchange_abi: List[any] = ujson.load(exchange_abi_json)

# 150,000 per order by gas
PROTOCOL_FEE_MULTIPLIER = 150000


class ZeroExExchange:
    def __init__(self,
                 w3: Web3,
                 exchange_address: str,
                 wallet: Web3Wallet):
        self._w3: Web3 = w3
        self._contract: Contract = w3.eth.contract(address=exchange_address, abi=exchange_abi)
        self._exchange_address: str = exchange_address
        self._wallet: Web3Wallet = wallet

    @property
    def contract(self) -> Contract:
        return self._contract

    @property
    def exchange_address(self) -> str:
        return self._exchange_address

    @property
    def wallet(self) -> Web3Wallet:
        return self._wallet

    def get_order_epoch(self, maker_address: str, sender_address: str) -> int:
        order_epoch: int = self._contract.functions.orderEpoch(maker_address, sender_address).call()
        return order_epoch

    def fill_order(self, order: Order, taker_asset_fill_amount: Decimal, signature: str) -> Tuple[str, Decimal]:
        order_tuple: Tuple = convert_order_to_tuple(order)
        signature: bytes = self._w3.toBytes(hexstr=signature)
        # Add 10 wei to the standard price to beat the default gas price ppl.
        gas_price: int = self._wallet.gas_price + 10
        protocol_fee = PROTOCOL_FEE_MULTIPLIER * gas_price
        tx_hash: str = self._wallet.execute_transaction(
            self._contract.functions.fillOrder(
                order_tuple,
                int(taker_asset_fill_amount),
                signature
            ),
            gasPrice=gas_price,
            value=protocol_fee
        )
        return tx_hash, Decimal(protocol_fee)

    def batch_fill_orders(self, orders: List[Order], taker_asset_fill_amounts: List[Decimal], signatures: List[str]) -> Tuple[str, Decimal]:
        order_tuples: List[Tuple] = [convert_order_to_tuple(order) for order in orders]
        signatures: List[bytes] = [self._w3.toBytes(hexstr=signature) for signature in signatures]
        taker_asset_fill_amounts: List[int] = [int(taker_asset_fill_amount) for taker_asset_fill_amount in taker_asset_fill_amounts]
        # Add 10 wei to the standard price to beat the default gas price ppl.
        gas_price: int = self._wallet.gas_price + 10
        protocol_fee = PROTOCOL_FEE_MULTIPLIER * len(orders) * gas_price
        tx_hash: str = self._wallet.execute_transaction(
            self._contract.functions.batchFillOrders(
                order_tuples,
                taker_asset_fill_amounts,
                signatures
            ),
            gasPrice=gas_price,
            value=protocol_fee
        )
        return tx_hash, Decimal(protocol_fee)

    def market_buy_orders(self, orders: List[Order], maker_asset_fill_amount: Decimal, signatures: List[str]) -> Tuple[str, Decimal]:
        order_tuples: List[Tuple] = [convert_order_to_tuple(order) for order in orders]
        signatures: List[bytes] = [self._w3.toBytes(hexstr=signature) for signature in signatures]
        # Add 10 wei to the standard price to beat the default gas price ppl.
        gas_price: int = self._wallet.gas_price + 10
        protocol_fee = PROTOCOL_FEE_MULTIPLIER * len(orders) * gas_price
        tx_hash: str = self._wallet.execute_transaction(
            self._contract.functions.marketBuyOrdersFillOrKill(
                order_tuples,
                int(maker_asset_fill_amount),
                signatures
            ),
            gasPrice=gas_price,
            value=protocol_fee
        )
        return tx_hash, Decimal(protocol_fee)

    def market_sell_orders(self, orders: List[Order], taker_asset_fill_amount: Decimal, signatures: List[str]) -> Tuple[str, Decimal]:
        order_tuples: List[Tuple] = [convert_order_to_tuple(order) for order in orders]
        signatures: List[bytes] = [self._w3.toBytes(hexstr=signature) for signature in signatures]
        # Add 10 wei to the standard price to beat the default gas price ppl.
        gas_price: int = self._wallet.gas_price + 10
        protocol_fee = PROTOCOL_FEE_MULTIPLIER * len(orders) * gas_price
        tx_hash: str = self._wallet.execute_transaction(
            self._contract.functions.marketSellOrdersFillOrKill(
                order_tuples,
                int(taker_asset_fill_amount),
                signatures
            ),
            gasPrice=gas_price,
            value=protocol_fee
        )
        return tx_hash, Decimal(protocol_fee)

    def cancel_order(self, order: Order) -> str:
        order_tuple = convert_order_to_tuple(order)
        tx_hash: str = self._wallet.execute_transaction(self._contract.functions.cancelOrder(order_tuple))
        return tx_hash

    def cancel_orders_up_to(self, target_order_epoch: int) -> str:
        tx_hash: str = self._wallet.execute_transaction(self._contract.functions.cancelOrdersUpTo(target_order_epoch))
        return tx_hash
