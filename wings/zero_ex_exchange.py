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

from wings.wallet.web3_wallet import Web3Wallet
from wings.zero_ex_custom_utils import convert_order_to_tuple

with open(os.path.join(os.path.dirname(__file__), "abi/zero_ex_exchange_abi.json")) as exchange_abi_json:
    exchange_abi: List[any] = ujson.load(exchange_abi_json)


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

    def market_buy_orders(self, orders: List[Order], maker_asset_fill_amount: Decimal, signatures: List[str]) -> str:
        order_tuples: List[Tuple] = [convert_order_to_tuple(order) for order in orders]
        signatures: List[bytes] = [self._w3.toBytes(hexstr=signature) for signature in signatures]
        tx_hash: str = self._wallet.execute_transaction(
            self._contract.functions.marketBuyOrders(order_tuples,
                                                     int(maker_asset_fill_amount),
                                                     signatures))
        return tx_hash

    def market_sell_orders(self, orders: List[Order], taker_asset_fill_amount: Decimal, signatures: List[str]) -> str:
        order_tuples: List[Tuple] = [convert_order_to_tuple(order) for order in orders]
        signatures: List[bytes] = [self._w3.toBytes(hexstr=signature) for signature in signatures]
        tx_hash: str = self._wallet.execute_transaction(
            self._contract.functions.marketSellOrders(order_tuples,
                                                      int(taker_asset_fill_amount),
                                                      signatures))
        return tx_hash

    def cancel_order(self, order: Order) -> str:
        order_tuple = convert_order_to_tuple(order)
        tx_hash: str = self._wallet.execute_transaction(self._contract.functions.cancelOrder(order_tuple))
        return tx_hash

    def cancel_orders_up_to(self, target_order_epoch: int) -> str:
        tx_hash: str = self._wallet.execute_transaction(self._contract.functions.cancelOrdersUpTo(target_order_epoch))
        return tx_hash

    def estimate_transaction_cost(self,
                                  orders: List[Order],
                                  asset_fill_amount: Decimal,
                                  signatures: List[str],
                                  is_buy: bool) -> int:
        order_tuples: List[Tuple] = [convert_order_to_tuple(order) for order in orders]
        signatures: List[bytes] = [self._w3.toBytes(hexstr=signature) for signature in signatures]
        if is_buy:
            return self._wallet.estimate_transaction_cost(
                self._contract.functions.marketBuyOrders(order_tuples,
                                                        int(asset_fill_amount),
                                                        signatures)
                )
        else:
            return self._wallet.estimate_transaction_cost(
                self._contract.functions.marketSellOrders(order_tuples,
                                                        int(asset_fill_amount),
                                                        signatures)
            )
