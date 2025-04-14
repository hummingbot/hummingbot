import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional

from hummingbot.connector.gateway.gateway_base import GatewayBase
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate, TradeFeeBase, TradeUpdate
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
from hummingbot.core.gateway import check_transaction_exceptions
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_ensure_future


class GatewaySwap(GatewayBase):
    """
    Handles swap-specific functionality including price quotes and trade execution.
    Maintains order tracking and wallet interactions in the base class.
    """

    @async_ttl_cache(ttl=5, maxsize=10)
    async def get_quote_price(
            self,
            trading_pair: str,
            is_buy: bool,
            amount: Decimal,
            slippage_pct: Optional[Decimal] = None,
            pool_address: Optional[str] = None
    ) -> Optional[Decimal]:
        """
        Retrieves the volume weighted average price. For an AMM DEX connectors, this is the swap price for a given amount.

        :param trading_pair: The market trading pair
        :param is_buy: True for an intention to buy, False for an intention to sell
        :param amount: The amount required (in base token unit)
        :return: The quote price.
        """
        base, quote = trading_pair.split("-")
        side: TradeType = TradeType.BUY if is_buy else TradeType.SELL

        # Pull the price from gateway.
        try:
            resp: Dict[str, Any] = await self._get_gateway_instance().quote_swap(
                network=self.network,
                connector=self.connector_name,
                base_asset=base,
                quote_asset=quote,
                amount=amount,
                side=side,
                slippage_pct=slippage_pct,
                pool_address=pool_address
            )
            return self.parse_price_response(base, quote, amount, side, price_response=resp)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error getting quote price for {trading_pair} {side} order for {amount} amount.",
                exc_info=True,
                app_warning_msg=str(e)
            )

    async def get_order_price(
            self,
            trading_pair: str,
            is_buy: bool,
            amount: Decimal,
    ) -> Decimal:
        """
        Retreives the price required for an order of a given amount. For AMM DEX connectors, this equals the quote price.
        """
        return await self.get_quote_price(trading_pair, is_buy, amount)

    def parse_price_response(
        self,
        base: str,
        quote: str,
        amount: Decimal,
        side: TradeType,
        price_response: Dict[str, Any],
        process_exception: bool = True
    ) -> Optional[Decimal]:
        """
        Parses price response
        :param base: The base asset
        :param quote: The quote asset
        :param amount: amount
        :param side: trade side
        :param price_response: Price response from Gateway.
        :param process_exception: Flag to trigger error on exception
        """
        required_items = ["price", "gasLimit", "gasPrice", "gasCost"]
        if any(item not in price_response.keys() for item in required_items):
            if "info" in price_response.keys():
                self.logger().info(f"Unable to get price. {price_response['info']}")
            else:
                self.logger().info(f"Missing data from price result. Incomplete return result for ({price_response.keys()})")
        else:
            gas_price_token: str = self._native_currency
            gas_cost: Decimal = Decimal(str(price_response["gasCost"]))
            price: Decimal = Decimal(str(price_response["price"]))
            gas_limit: int = int(price_response["gasLimit"])
            # self.network_transaction_fee = TokenAmount(gas_price_token, gas_cost)
            if process_exception is True:
                kwargs = {
                    "balances": self._account_balances,
                    "base_asset": base,
                    "quote_asset": quote,
                    "amount": amount,
                    "side": side,
                    "gas_limit": gas_limit,
                    "gas_cost": gas_cost,
                    "gas_asset": gas_price_token
                }
                # Add allowances for Ethereum
                if self.chain == "ethereum":
                    kwargs["allowances"] = self._allowances

                exceptions: List[str] = check_transaction_exceptions(**kwargs)
                for index in range(len(exceptions)):
                    self.logger().warning(
                        f"Warning! [{index + 1}/{len(exceptions)}] {side} order - {exceptions[index]}"
                    )
                if len(exceptions) > 0:
                    return None
            return price
        return None

    def buy(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal, **kwargs) -> str:
        """
        Buys an amount of base token for a given price (or cheaper).
        :param trading_pair: The market trading pair
        :param amount: The order amount (in base token unit)
        :param order_type: Any order type is fine, not needed for this.
        :param price: The maximum price for the order.
        :return: A newly created order id (internal).
        """
        return self.place_order(True, trading_pair, amount, price)

    def sell(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal, **kwargs) -> str:
        """
        Sells an amount of base token for a given price (or at a higher price).
        :param trading_pair: The market trading pair
        :param amount: The order amount (in base token unit)
        :param order_type: Any order type is fine, not needed for this.
        :param price: The minimum price for the order.
        :return: A newly created order id (internal).
        """
        return self.place_order(False, trading_pair, amount, price)

    def place_order(self, is_buy: bool, trading_pair: str, amount: Decimal, price: Decimal, **request_args) -> str:
        """
        Places an order.
        :param is_buy: True for buy order
        :param trading_pair: The market trading pair
        :param amount: The order amount (in base token unit)
        :param price: The minimum price for the order.
        :return: A newly created order id (internal).
        """
        side: TradeType = TradeType.BUY if is_buy else TradeType.SELL
        order_id: str = self.create_market_order_id(side, trading_pair)
        safe_ensure_future(self._create_order(side, order_id, trading_pair, amount, price, **request_args))
        return order_id

    async def _create_order(
            self,
            trade_type: TradeType,
            order_id: str,
            trading_pair: str,
            amount: Decimal,
            price: Decimal,
            **request_args
    ):
        """
        Calls buy or sell API end point to place an order, starts tracking the order and triggers relevant order events.
        :param trade_type: BUY or SELL
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The market to place order
        :param amount: The order amount (in base token value)
        :param price: The order price (TO-DO: add limit_price to Gateway execute-swap schema)
        """

        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)

        base, quote = trading_pair.split("-")
        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  trade_type=trade_type,
                                  price=price,
                                  amount=amount)
        try:
            order_result: Dict[str, Any] = await self._get_gateway_instance().execute_swap(
                self.network,
                self.connector_name,
                self.address,
                base,
                quote,
                trade_type,
                amount,
                # limit_price=price,
                **request_args
            )
            transaction_hash: Optional[str] = order_result.get("signature")
            if transaction_hash is not None and transaction_hash != "":

                order_update: OrderUpdate = OrderUpdate(
                    client_order_id=order_id,
                    exchange_order_id=transaction_hash,
                    trading_pair=trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=OrderState.OPEN,  # Assume that the transaction has been successfully mined.
                    misc_updates={
                        "nonce": order_result.get("nonce", 0),  # Default to 0 if nonce is not present
                        "gas_price": Decimal(order_result.get("gasPrice", 0)),
                        "gas_limit": int(order_result.get("gasLimit", 0)),
                        "gas_cost": Decimal(order_result.get("fee", 0)),
                        "gas_price_token": self._native_currency,
                        "fee_asset": self._native_currency
                    }
                )
                self._order_tracker.process_order_update(order_update)
            else:
                raise ValueError

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                f"Error submitting {trade_type.name} swap order to {self.connector_name} on {self.network} for "
                f"{amount} {trading_pair} "
                f"{price}.",
                exc_info=True
            )
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                trading_pair=trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=OrderState.FAILED
            )
            self._order_tracker.process_order_update(order_update)

    def process_trade_fill_update(self, tracked_order: GatewayInFlightOrder, fee: Decimal):
        trade_fee: TradeFeeBase = AddedToCostTradeFee(
            flat_fees=[TokenAmount(tracked_order.fee_asset, fee)]
        )

        trade_update: TradeUpdate = TradeUpdate(
            trade_id=tracked_order.exchange_order_id,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=tracked_order.exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            fill_timestamp=self.current_timestamp,
            fill_price=tracked_order.price,
            fill_base_amount=tracked_order.amount,
            fill_quote_amount=tracked_order.amount * tracked_order.price,
            fee=trade_fee
        )

        self._order_tracker.process_trade_update(trade_update)
