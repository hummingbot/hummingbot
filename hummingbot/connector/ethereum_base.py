import logging
from decimal import Decimal
import asyncio
from typing import Dict, List, Optional

from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.event.events import (
    MarketEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    MarketOrderFailureEvent,
    OrderFilledEvent,
    OrderType,
    TradeType,
    TradeFee
)
from hummingbot.connector.gateway_base import GatewayBase
from hummingbot.connector.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.utils.ethereum import check_transaction_exceptions, fetch_trading_pairs

s_logger = None
s_decimal_0 = Decimal("0")
s_decimal_NaN = Decimal("nan")
logging.basicConfig(level=METRICS_LOG_LEVEL)


class EthereumBase(GatewayBase):
    """
    Defines basic functions common to connectors that interact with Ethereum through Gateway.
    """

    API_CALL_TIMEOUT = 10.0
    POLL_INTERVAL = 1.0
    UPDATE_BALANCE_INTERVAL = 30.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(cls.__name__)
        return s_logger

    def __init__(self,
                 trading_pairs: List[str],
                 wallet_private_key: str,
                 trading_required: bool = True
                 ):
        """
        :param trading_pairs: a list of trading pairs
        :param wallet_private_key: a private key for eth wallet
        :param trading_required: Whether actual trading is needed. Useful for some functionalities or commands like the balance command
        """
        super().__init__(trading_pairs, trading_required)
        self._tokens = set()
        for trading_pair in trading_pairs:
            self._tokens.update(set(trading_pair.split("-")))
        self._wallet_private_key = wallet_private_key
        self._last_est_gas_cost_reported = 0
        self._allowances = {}
        self._nonce = None

    @property
    def name(self):
        raise NotImplementedError

    @property
    def network_base_path(self):
        return "eth"

    @property
    def base_path(self):
        raise NotImplementedError

    @property
    def private_key(self):
        if self._wallet_private_key[:2] != "0x":
            self._wallet_private_key = "0x" + self._wallet_private_key
        return self._wallet_private_key

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        return await fetch_trading_pairs()

    async def init(self):
        await self.auto_approve()

    @property
    def ready(self):
        return all(self.status_dict.values())

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "allowances": self.has_allowances() if self._trading_required else True
        }

    @property
    def approval_orders(self) -> List[GatewayInFlightOrder]:
        return [
            approval_order
            for approval_order in self._in_flight_orders.values() if approval_order.client_order_id.split("_")[0] == "approve"
        ]

    def is_pending_approval(self, token: str) -> bool:
        pending_approval_tokens = [tk.split("_")[2] for tk in self._in_flight_orders.keys()]
        return True if token in pending_approval_tokens else False

    async def auto_approve(self):
        """
        Automatically approves trading pair tokens for contract(s).
        It first checks if there are any already approved amount (allowance)
        """
        self._allowances = await self.get_allowances()
        for token, amount in self._allowances.items():
            if amount <= s_decimal_0 and not self.is_pending_approval(token):
                await self.approve_token(token)

    async def approve_token(self, token_symbol: str):
        """
        Approves contract as a spender for a token.
        :param token_symbol: token to approve.
        """
        order_id = f"approve_{self.name}_{token_symbol}"
        await self._update_nonce()
        resp = await self._api_request("post",
                                       "eth/approve",
                                       {"token": token_symbol,
                                        "spender": self.name,
                                        "nonce": self._nonce})
        self.start_tracking_order(order_id, None, token_symbol)

        if "hash" in resp.get("approval", {}).keys():
            hash = resp["approval"]["hash"]
            tracked_order = self._in_flight_orders.get(order_id)
            tracked_order.update_exchange_order_id(hash)
            self.logger().info(f"Maximum {token_symbol} approval for {self.name} contract sent, hash: {hash}.")
        else:
            self.stop_tracking_order(order_id)
            self.logger().info(f"Approval for {token_symbol} on {self.name} failed.")

    async def get_allowances(self) -> Dict[str, Decimal]:
        """
        Retrieves allowances for token in trading_pairs
        :return: A dictionary of token and its allowance.
        """
        ret_val = {}
        resp = await self._api_request("post", "eth/allowances",
                                       {"tokenSymbols": list(self._tokens),
                                        "spender": self.name})
        for token, amount in resp["approvals"].items():
            ret_val[token] = Decimal(str(amount))
        return ret_val

    def has_allowances(self) -> bool:
        """
        Checks if all tokens have allowance (an amount approved)
        """
        return len(self._allowances.values()) == len(self._tokens) and \
            all(amount > s_decimal_0 for amount in self._allowances.values())

    @async_ttl_cache(ttl=5, maxsize=10)
    async def get_quote_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Optional[Decimal]:
        """
        Retrieves a quote price.
        :param trading_pair: The market trading pair
        :param is_buy: True for an intention to buy, False for an intention to sell
        :param amount: The amount required (in base token unit)
        :return: The quote price.
        """

        try:
            base, quote = trading_pair.split("-")
            side = "buy" if is_buy else "sell"
            resp = await self._api_request("post",
                                           f"{self.base_path}/price",
                                           {"base": base,
                                            "quote": quote,
                                            "amount": str(amount),
                                            "side": side.upper()})
            required_items = ["price", "gasLimit", "gasPrice", "gasCost"]
            if any(item not in resp.keys() for item in required_items):
                if "info" in resp.keys():
                    self.logger().info(f"Unable to get price. {resp['info']}")
                else:
                    self.logger().info(f"Missing data from price result. Incomplete return result for ({resp.keys()})")
            else:
                gas_limit = resp["gasLimit"]
                gas_price = resp["gasPrice"]
                gas_cost = resp["gasCost"]
                price = resp["price"]
                account_standing = {
                    "allowances": self._allowances,
                    "balances": self._account_balances,
                    "base": base,
                    "quote": quote,
                    "amount": amount,
                    "side": side,
                    "gas_limit": gas_limit,
                    "gas_price": gas_price,
                    "gas_cost": gas_cost,
                    "price": price,
                    "swaps": len(resp["swaps"])
                }
                exceptions = check_transaction_exceptions(account_standing)
                for index in range(len(exceptions)):
                    self.logger().info(f"Warning! [{index+1}/{len(exceptions)}] {side} order - {exceptions[index]}")

                if price is not None and len(exceptions) == 0:
                    return Decimal(str(price))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error getting quote price for {trading_pair}  {side} order for {amount} amount.",
                exc_info=True,
                app_warning_msg=str(e)
            )

    async def get_order_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Decimal:
        """
        This is simply the quote price
        """
        return await self.get_quote_price(trading_pair, is_buy, amount)

    def buy(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal) -> str:
        """
        Buys an amount of base token for a given price (or cheaper).
        :param trading_pair: The market trading pair
        :param amount: The order amount (in base token unit)
        :param order_type: Any order type is fine, not needed for this.
        :param price: The maximum price for the order.
        :return: A newly created order id (internal).
        """
        return self.place_order(True, trading_pair, amount, price)

    def sell(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal) -> str:
        """
        Sells an amount of base token for a given price (or at a higher price).
        :param trading_pair: The market trading pair
        :param amount: The order amount (in base token unit)
        :param order_type: Any order type is fine, not needed for this.
        :param price: The minimum price for the order.
        :return: A newly created order id (internal).
        """
        return self.place_order(False, trading_pair, amount, price)

    def place_order(self, is_buy: bool, trading_pair: str, amount: Decimal, price: Decimal) -> str:
        """
        Places an order.
        :param is_buy: True for buy order
        :param trading_pair: The market trading pair
        :param amount: The order amount (in base token unit)
        :param price: The minimum price for the order.
        :return: A newly created order id (internal).
        """
        side = TradeType.BUY if is_buy else TradeType.SELL
        order_id = f"{side.name.lower()}-{trading_pair}-{get_tracking_nonce()}"
        safe_ensure_future(self._create_order(side, order_id, trading_pair, amount, price))
        return order_id

    async def _create_order(self,
                            trade_type: TradeType,
                            order_id: str,
                            trading_pair: str,
                            amount: Decimal,
                            price: Decimal):
        """
        Calls buy or sell API end point to place an order, starts tracking the order and triggers relevant order events.
        :param trade_type: BUY or SELL
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The market to place order
        :param amount: The order amount (in base token value)
        :param price: The order price
        """

        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)
        base, quote = trading_pair.split("-")
        await self._update_nonce()
        api_params = {"base": base,
                      "quote": quote,
                      "side": trade_type.name.upper(),
                      "amount": str(amount),
                      "limitPrice": str(price),
                      "nonce": self._nonce,
                      }
        try:
            order_result = await self._api_request("post", f"{self.base_path}/trade", api_params)
            hash = order_result.get("txHash")
            gas_price = order_result.get("gasPrice")
            gas_limit = order_result.get("gasLimit")
            gas_cost = order_result.get("gasCost")
            self.start_tracking_order(order_id, None, trading_pair, OrderType.LIMIT, trade_type, price, amount, gas_price)
            tracked_order = self._in_flight_orders.get(order_id)

            if tracked_order is not None:
                self.logger().info(f"Created {trade_type.name} order {order_id} txHash: {hash} "
                                   f"for {amount} {trading_pair} on {self._chain_info.get('name', '--')}. Estimated Gas Cost: {gas_cost} "
                                   f" (gas limit: {gas_limit}, gas price: {gas_price})")
                tracked_order.update_exchange_order_id(hash)
                tracked_order.gas_price = gas_price
            if hash is not None:
                tracked_order.fee_asset = self._chain_info["nativeCurrency"]["symbol"]
                tracked_order.executed_amount_base = amount
                tracked_order.executed_amount_quote = amount * price
                event_tag = MarketEvent.BuyOrderCreated if trade_type is TradeType.BUY else MarketEvent.SellOrderCreated
                event_class = BuyOrderCreatedEvent if trade_type is TradeType.BUY else SellOrderCreatedEvent
                self.trigger_event(event_tag, event_class(self.current_timestamp, OrderType.LIMIT, trading_pair, amount,
                                                          price, order_id, hash))
            else:
                self.trigger_event(MarketEvent.OrderFailure,
                                   MarketOrderFailureEvent(self.current_timestamp, order_id, OrderType.LIMIT))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting {trade_type.name} swap order to {self.name} on {self._chain_info['name']} for "
                f"{amount} {trading_pair} "
                f"{price}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(self.current_timestamp, order_id, OrderType.LIMIT))

    async def _update_approval_order_status(self, tracked_orders: GatewayInFlightOrder):
        """
        Calls REST API to get status update for each in-flight order.
        This function can also be used to update status of simple swap orders.
        """
        if len(tracked_orders) > 0:
            tasks = []
            for tracked_order in tracked_orders:
                order_id = await tracked_order.get_exchange_order_id()
                tasks.append(self._api_request("post",
                                               "eth/poll",
                                               {"txHash": order_id}))
            update_results = await safe_gather(*tasks, return_exceptions=True)
            for tracked_order, update_result in zip(tracked_orders, update_results):
                self.logger().info(f"Polling for order status updates of {len(tasks)} orders.")
                if isinstance(update_result, Exception):
                    raise update_result
                if "txHash" not in update_result:
                    self.logger().info(f"_update_order_status txHash not in resp: {update_result}")
                    continue
                if update_result["confirmed"] is True:
                    if update_result["receipt"]["status"] == 1:
                        if tracked_order in self.approval_orders:
                            self.logger().info(f"Approval transaction id {update_result['txHash']} confirmed.")
                        else:
                            gas_used = update_result["receipt"]["gasUsed"]
                            gas_price = tracked_order.gas_price
                            fee = Decimal(str(gas_used)) * Decimal(str(gas_price)) / Decimal(str(1e9))
                            self.trigger_event(
                                MarketEvent.OrderFilled,
                                OrderFilledEvent(
                                    self.current_timestamp,
                                    tracked_order.client_order_id,
                                    tracked_order.trading_pair,
                                    tracked_order.trade_type,
                                    tracked_order.order_type,
                                    Decimal(str(tracked_order.price)),
                                    Decimal(str(tracked_order.amount)),
                                    TradeFee(0.0, [(tracked_order.fee_asset, Decimal(str(fee)))]),
                                    exchange_trade_id=order_id
                                )
                            )
                            tracked_order.last_state = "FILLED"
                            self.logger().info(f"The {tracked_order.trade_type.name} order "
                                               f"{tracked_order.client_order_id} has completed "
                                               f"according to order status API.")
                            event_tag = MarketEvent.BuyOrderCompleted if tracked_order.trade_type is TradeType.BUY \
                                else MarketEvent.SellOrderCompleted
                            event_class = BuyOrderCompletedEvent if tracked_order.trade_type is TradeType.BUY \
                                else SellOrderCompletedEvent
                            self.trigger_event(event_tag,
                                               event_class(self.current_timestamp,
                                                           tracked_order.client_order_id,
                                                           tracked_order.base_asset,
                                                           tracked_order.quote_asset,
                                                           tracked_order.fee_asset,
                                                           tracked_order.executed_amount_base,
                                                           tracked_order.executed_amount_quote,
                                                           float(fee),
                                                           tracked_order.order_type))
                        self.stop_tracking_order(tracked_order.client_order_id)
                    else:
                        self.logger().info(
                            f"The market order {tracked_order.client_order_id} has failed according to order status API. ")
                        self.trigger_event(MarketEvent.OrderFailure,
                                           MarketOrderFailureEvent(
                                               self.current_timestamp,
                                               tracked_order.client_order_id,
                                               tracked_order.order_type
                                           ))
                        self.stop_tracking_order(tracked_order.client_order_id)

    async def _update_order_status(self, tracked_orders: GatewayInFlightOrder):
        """
        Calls REST API to get status update for each in-flight amm orders.
        """
        await self._update_approval_order_status(tracked_orders)

    def get_taker_order_type(self):
        return OrderType.LIMIT

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        return Decimal("1e-15")

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        return Decimal("1e-15")

    async def _update_nonce(self):
        """
        Call the gateway API to get the current nonce for self._wallet_private_key
        """
        resp_json = await self._api_request("post", "eth/nonce", {})
        self._nonce = resp_json['nonce']

    async def _update(self):
        await safe_gather(
            self._update_balances(on_interval=True),
            self._update_approval_order_status(self.approval_orders),
            self._update_order_status(self.amm_orders)
        )

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        return []
