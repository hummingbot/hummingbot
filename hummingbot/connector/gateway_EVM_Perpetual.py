import asyncio
import copy
import logging
import re
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

from hummingbot.connector.derivative.position import Position
from hummingbot.connector.gateway_EVM_AMM import GatewayEVMAMM
from hummingbot.connector.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.perpetual_trading import PerpetualTrading
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.events import AccountEvent, FundingInfo, PositionModeChangeEvent, TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger

from .gateway_price_shim import GatewayPriceShim

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

gp_logger = None
s_decimal_0 = Decimal("0")
s_decimal_NaN = Decimal("nan")

TRADING_PAIR_SPLITTER = re.compile(r"^(\w+)(USD)$")


class GatewayEVMPerpetual(GatewayEVMAMM, PerpetualTrading):
    """
    Defines basic funtions common to connectors that interract with perpetual contracts on Gateway.
    """

    _collateral_currency: str

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 connector_name: str,
                 chain: str,
                 network: str,
                 wallet_address: str,
                 trading_pairs: List[str] = [],
                 trading_required: bool = True
                 ):
        """
        :param connector_name: name of connector on gateway
        :param chain: refers to a block chain, e.g. ethereum or avalanche
        :param network: refers to a network of a particular blockchain e.g. mainnet or kovan
        :param wallet_address: the address of the eth wallet which has been added on gateway
        :param trading_pairs: a list of trading pairs
        :param trading_required: Whether actual trading is needed. Useful for some functionalities or commands like the balance command
        """
        GatewayEVMAMM.__init__(
            self,
            client_config_map = client_config_map,
            connector_name = connector_name,
            chain = chain,
            network = network,
            wallet_address = wallet_address,
            trading_pairs = trading_pairs,
            trading_required = trading_required
        )
        PerpetualTrading.__init__(self)

        # This values may not be applicable to all gateway perps, but applies to perp curie
        self._collateral_currency = "USD"

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global gp_logger
        if gp_logger is None:
            gp_logger = logging.getLogger(cls.__name__)
        return cast(HummingbotLogger, gp_logger)

    @staticmethod
    async def all_trading_pairs(chain: str, network: str, connector_name: str) -> List[str]:
        """
        Calls the get_perp_markets endpoint on Gateway.
        """
        try:
            response = await GatewayHttpClient.get_instance().get_perp_markets(chain, network, connector_name)
            trading_pairs = []
            for pair in response.get("pairs", []):
                split = TRADING_PAIR_SPLITTER.search(pair)
                trading_pairs.append(f"{split.group(1)}-{split.group(2)}")
            return trading_pairs
        except Exception:
            return []

    async def get_gas_estimate(self):
        """
        Gets the gas estimates for the connector.
        """
        try:
            response: Dict[Any] = await self._get_gateway_instance().amm_perp_estimate_gas(
                chain=self.chain, network=self.network, connector=self.connector_name
            )
            self.network_transaction_fee = TokenAmount(
                response.get("gasPriceToken"), Decimal(response.get("gasCost"))
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error getting gas price estimates for {self.connector_name} on {self.network}.",
                exc_info=True,
                app_warning_msg=str(e)
            )

    @async_ttl_cache(ttl=5, maxsize=10)
    async def get_quote_price(
            self,
            trading_pair: str,
            is_buy: bool,
            amount: Decimal,
            ignore_shim: bool = False
    ) -> Optional[Decimal]:
        """
        Retrieves a quote price.

        :param trading_pair: The market trading pair
        :param is_buy: True for an intention to buy, False for an intention to sell
        :param amount: The amount required (in base token unit)
        :param ignore_shim: Ignore the price shim, and return the real price on the network
        :return: The quote price.
        """

        base, quote = trading_pair.split("-")
        side: PositionSide = PositionSide.LONG if is_buy else PositionSide.SHORT

        # Get the price from gateway price shim for integration tests.
        if not ignore_shim:
            test_price: Optional[Decimal] = await GatewayPriceShim.get_instance().get_connector_price(
                self.connector_name,
                self.chain,
                self.network,
                trading_pair,
                is_buy,
                amount
            )
            if test_price is not None:
                # Grab the gas price for test net.
                try:
                    resp: Dict[str, Any] = await self._get_gateway_instance().get_price(
                        self.chain, self.network, self.connector_name, base, quote, amount, side
                    )
                    gas_price_token: str = resp["gasPriceToken"]
                    gas_cost: Decimal = Decimal(resp["gasCost"])
                    self.network_transaction_fee = TokenAmount(gas_price_token, gas_cost)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass
                return test_price

        # Pull the price from gateway.
        try:
            resp: Dict[str, Any] = await self._get_gateway_instance().get_perp_market_price(
                chain=self.chain,
                network=self.network,
                connector=self.connector_name,
                base_asset=base,
                quote_asset=quote,
                amount=amount,
                side=side,
            )
            """required_items = ["price", "gasLimit", "gasPrice", "gasCost", "gasPriceToken"]
            if any(item not in resp.keys() for item in required_items):
                if "info" in resp.keys():
                    self.logger().info(f"Unable to get price. {resp['info']}")
                else:
                    self.logger().info(f"Missing data from price result. Incomplete return result for ({resp.keys()})")
            else:
                gas_limit: int = int(resp["gasLimit"])
                gas_price_token: str = resp["gasPriceToken"]
                gas_cost: Decimal = Decimal(resp["gasCost"])
                price: Decimal = Decimal(resp["price"])
                self.network_transaction_fee = TokenAmount(gas_price_token, gas_cost)
                exceptions: List[str] = check_transaction_exceptions(
                    allowances=self._allowances,
                    balances=self._account_balances,
                    base_asset=base,
                    quote_asset=quote,
                    amount=amount,
                    side=side,
                    gas_limit=gas_limit,
                    gas_cost=gas_cost,
                    gas_asset=gas_price_token,
                    swaps_count=len(resp.get("swaps", []))
                )
                for index in range(len(exceptions)):
                    self.logger().warning(
                        f"Warning! [{index + 1}/{len(exceptions)}] {side} order - {exceptions[index]}"
                    )

                if price is not None and len(exceptions) == 0:
                    return Decimal(str(price))

            # Didn't pass all the checks - no price available."""

            price: Decimal = Decimal(resp["markPrice"])
            return Decimal(str(price))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error getting prices for {trading_pair} {side} order for {amount} amount.",
                exc_info=True,
                app_warning_msg=str(e)
            )

    async def _create_order(
            self,
            trade_type: TradeType,
            order_id: str,
            trading_pair: str,
            amount: Decimal,
            order_type: OrderType,
            position_action: PositionAction,
            price: Decimal,
            **request_args
    ):
        """
        This function is responsible for executing the API request to place the order on the exchange.
        :param trade_type: BUY or SELL
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The market to place order
        :param amount: The order amount (in base token value)
        order_type: LIMIT
        position_action: OPEN or CLOSE
        :param price: The order price
        """

        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)
        side = PositionSide.LONG if TradeType.BUY else PositionSide.SHORT
        base, quote = trading_pair.split("-")
        self.start_tracking_order(
            order_id=order_id,
            trading_pair=trading_pair,
            trading_type=trade_type,
            price=price,
            amount=amount,
        )
        try:
            if position_action == PositionAction.OPEN:
                order_result: Dict[str, Any] = await self._get_gateway_instance().amm_perp_open(
                    chain=self.chain,
                    network=self.network,
                    connector=self.connector_name,
                    address=self.address,
                    base_asset=base,
                    quote_asset=quote,
                    side=side,
                    amount=amount * Decimal(str(self.get_leverage(trading_pair))),
                    price= price,
                )
            else:
                # Note: Partial close request isn't supported yet.
                order_result: Dict[str, Any] = await self._get_gateway_instance().amm_perp_close(
                    chain=self.chain,
                    network=self.network,
                    connector=self.connector_name,
                    address=self.address,
                    base_asset=base,
                    quote_asset=quote,
                )
            transaction_hash: Optional[str] = order_result.get("txHash")
            if transaction_hash is not None:
                gas_cost: Decimal = Decimal(order_result.get("gasCost"))
                gas_price_token: str = order_result.get("gasPriceToken")
                self.network_transaction_fee = TokenAmount(gas_price_token, gas_cost)

                order_update: OrderUpdate = OrderUpdate(
                    client_order_id=order_id,
                    exchange_order_id=transaction_hash,
                    trading_pair=trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=OrderState.OPEN,  # Assume that the transaction has been successfully mined.
                    misc_updates={
                        "nonce": order_result.get("nonce"),
                        "gas_price": Decimal(order_result.get("gasPrice")),
                        "gas_limit": int(order_result.get("gasLimit")),
                        "gas_cost": Decimal(order_result.get("gasCost")),
                        "gas_price_token": order_result.get("gasPriceToken"),
                        "fee_asset": self._native_currency,
                        "leverage": self.get_leverage(trading_pair),
                        "position": position_action,

                    }
                )
                self._order_tracker.process_order_update(order_update)
            else:
                raise ValueError

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error submitting order to {self.connector_name} for {amount} {trading_pair} "
                f"{'' if order_type is OrderType.MARKET else price}.",
                exc_info=True,
                app_warning_msg=str(e),
            )
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                trading_pair=trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=OrderState.FAILED
            )
            self._order_tracker.process_order_update(order_update)

    def start_tracking_order(
        self,
        order_id: str,
        trading_pair: str,
        trading_type: TradeType,
        price: Decimal,
        amount: Decimal,
        order_type: OrderType = OrderType.LIMIT,
        gas_price: Decimal = s_decimal_0,
        exchange_order_id: Optional[str] = None,
    ):
        """
        Starts tracking an order by simply adding it into _in_flight_orders dictionary in ClientOrderTracker.
        """
        self._order_tracker.start_tracking_order(
            GatewayInFlightOrder(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=trading_type,
                price=price,
                amount=amount,
                gas_price=gas_price,
                creation_timestamp=self.current_timestamp,
                initial_state=OrderState.PENDING_CREATE
            )
        )

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "native_currency": self._native_currency is not None,
            "network_transaction_fee": self.network_transaction_fee is not None if self._trading_required else True,
        }

    async def start_network(self):
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._get_gas_estimate_task = safe_ensure_future(self.get_gas_estimate())
        self._get_chain_info_task = safe_ensure_future(self.get_chain_info())

    async def stop_network(self):
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._get_chain_info_task is not None:
            self._get_chain_info_task.cancel()
            self._get_chain_info_task = None
        if self._get_gas_estimate_task is not None:
            self._get_gas_estimate_task.cancel()
            self._get_chain_info_task = None

    async def check_network(self) -> NetworkStatus:
        try:
            if await self._get_gateway_instance().ping_gateway():
                return NetworkStatus.CONNECTED
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.NOT_CONNECTED

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock's tick (1 second by default).
        It checks if status polling task is due for execution.
        """
        if time.time() - self._last_poll_timestamp > self.POLL_INTERVAL:
            if self._poll_notifier is not None and not self._poll_notifier.is_set():
                self._poll_notifier.set()

    async def _status_polling_loop(self):
        await self.update_balances(on_interval=False)
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()
                await safe_gather(
                    self.update_balances(on_interval=True),
                    self.update_positions(),
                    self.update_canceling_transactions(self.canceling_orders),
                    self.update_order_status(self.amm_orders)
                )
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(str(e), exc_info=True)

    async def update_balances(self, on_interval=False):
        """
        Calls Eth API to update total and available balances.
        """
        if self._native_currency is None:
            await self.get_chain_info()
        last_tick = self._last_balance_poll_timestamp
        current_tick = self.current_timestamp
        if not on_interval or (current_tick - last_tick) > self.UPDATE_BALANCE_INTERVAL:
            self._last_balance_poll_timestamp = current_tick
            local_asset_names = set(self._account_balances.keys())
            remote_asset_names = set()
            native_bal_resp_json: Dict[str, Any] = await self._get_gateway_instance().get_balances(
                self.chain, self.network, self.address, [self._native_currency]
            )
            col_bal_resp_json: Dict[str, Any] = await self._get_gateway_instance().amm_perp_balance(
                chain = self.chain,
                network = self.network,
                connector = self.connector_name,
                address = self.address,
            )
            for token, bal in native_bal_resp_json["balances"].items():
                self._account_available_balances[token] = Decimal(str(bal))
                self._account_balances[token] = Decimal(str(bal))
                remote_asset_names.add(token)

            col_balance = col_bal_resp_json.get("balance", "0")
            self._account_available_balances[self._collateral_currency] = Decimal(str(col_balance))
            self._account_balances[self._collateral_currency] = Decimal(str(col_balance))
            remote_asset_names.add(self._collateral_currency)

            asset_names_to_remove = local_asset_names.difference(remote_asset_names)
            for asset_name in asset_names_to_remove:
                del self._account_available_balances[asset_name]
                del self._account_balances[asset_name]

            self._in_flight_orders_snapshot = {k: copy.copy(v) for k, v in self._order_tracker.all_orders.items()}
            self._in_flight_orders_snapshot_timestamp = self.current_timestamp

    def get_next_funding_timestamp(self):
        # We're returing a value of -1 because of the nature of block based funding payment
        return -1

    def set_leverage(self, trading_pair: str, leverage: int = 1):
        self._leverage[trading_pair] = leverage
        self.logger().info(f"Leverage Successfully set to {leverage} for {trading_pair}.")
        return leverage

    def set_position_mode(self, position_mode: PositionMode):
        for trading_pair in self._trading_pairs:
            self.trigger_event(AccountEvent.PositionModeChangeSucceeded,
                               PositionModeChangeEvent(
                                   self.current_timestamp,
                                   trading_pair,
                                   position_mode)
                               )
            self._position_mode = position_mode
            self.logger().info(f"Using {position_mode.name} position mode for pair {trading_pair}.")
        return position_mode

    def supported_position_modes(self):
        """
        This method needs to be overridden to provide the accurate information depending on the exchange.
        """
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        return self._collateral_currency

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        return self._collateral_currency

    async def update_positions(self):
        position_requests = []
        for trading_pair in self._trading_pairs:
            base, quote = trading_pair.split("-")
            position_requests.append(self._get_gateway_instance().get_perp_position(
                chain = self.chain,
                network = self.network,
                connector = self.connector_name,
                address = self.address,
                base_asset = base,
                quote_asset = quote,
            ))
        positions: Dict[str, Any] = await safe_gather(*position_requests, return_exceptions=True)

        for position in positions:
            trading_pair = f"{position['base']}-{position['quote']}"
            position_side = PositionSide.LONG if position.get("positionSide") == "LONG" else PositionSide.SHORT
            unrealized_pnl = Decimal(position.get("unrealizedProfit"))
            entry_price = Decimal(position.get("entryPrice"))
            amount = Decimal(position.get("positionAmt"))
            leverage = Decimal(position.get("leverage"))
            pos_key = self.position_key(trading_pair, position_side)
            if amount != s_decimal_0:
                self._account_positions[pos_key] = Position(
                    trading_pair=trading_pair,
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=amount,
                    leverage=leverage
                )
            else:
                if pos_key in self._account_positions:
                    del self._account_positions[pos_key]

    # To-dos:
    async def _fetch_funding_payment(self, trading_pair: str) -> bool:
        """
        Fetches the funding settlement details of all the active trading pairs and processes the responses.
        Triggers a FundingPaymentCompleted event as required.
        """
        try:
            return True
        except Exception as e:
            self.logger().error(f"Unexpected error occurred fetching funding payment for {trading_pair}. Error: {e}",
                                exc_info=True)
            return False

    def get_funding_info(self, trading_pair: str) -> Optional[FundingInfo]:
        """
        Retrieves the Funding Info for the specified trading pair.
        Note: This function should NOT be called when the connector is not yet ready.
        :param: trading_pair: The specified trading pair.
        """
        # self.logger().error(f"Funding Info for {trading_pair} not found. Proceeding to fetch using REST API.")
        return None
