import asyncio
import copy
import itertools as it
import logging
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, cast

from hummingbot.client.settings import GatewayConnectionSetting
from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.gateway.gateway_price_shim import GatewayPriceShim
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate, TradeFeeBase, TradeUpdate
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_logger = None
s_decimal_0 = Decimal("0")
s_decimal_NaN = Decimal("nan")


class GatewayAMMBase(ConnectorBase):
    """
    Defines basic functions common to all Gateway AMM connectors
    """

    API_CALL_TIMEOUT = 10.0
    POLL_INTERVAL = 1.0
    UPDATE_BALANCE_INTERVAL = 30.0

    _connector_name: str
    _name: str
    _chain: str
    _network: str
    _address: str
    _trading_pairs: List[str]
    _tokens: Set[str]
    _trading_required: bool
    _last_poll_timestamp: float
    _last_balance_poll_timestamp: float
    _last_est_gas_cost_reported: float
    _poll_notifier: Optional[asyncio.Event]
    _status_polling_task: Optional[asyncio.Task]
    _get_chain_info_task: Optional[asyncio.Task]
    _get_gas_estimate_task: Optional[asyncio.Task]
    _chain_info: Dict[str, Any]
    _network_transaction_fee: Optional[TokenAmount]
    _order_tracker: ClientOrderTracker
    _native_currency: str
    _amount_quantum_dict: Dict[str, Decimal]

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 connector_name: str,
                 chain: str,
                 network: str,
                 address: str,
                 trading_pairs: List[str] = [],
                 trading_required: bool = True
                 ):
        """
        :param connector_name: name of connector on gateway
        :param chain: refers to a block chain, e.g. solana
        :param network: refers to a network of a particular blockchain e.g. mainnet or devnet
        :param address: the address of the sol wallet which has been added on gateway
        :param trading_pairs: a list of trading pairs
        :param trading_required: Whether actual trading is needed. Useful for some functionalities or commands like the balance command
        """
        self._connector_name = connector_name
        self._name = f"{connector_name}_{chain}_{network}"
        super().__init__(client_config_map)
        self._chain = chain
        self._network = network
        self._trading_pairs = trading_pairs
        self._tokens = set()
        [self._tokens.update(set(trading_pair.split("_")[0].split("-"))) for trading_pair in trading_pairs]
        self._wallet_address = address
        self._trading_required = trading_required
        self._last_poll_timestamp = 0.0
        self._last_balance_poll_timestamp = time.time()
        self._last_est_gas_cost_reported = 0
        self._chain_info = {}
        self._status_polling_task = None
        self._get_chain_info_task = None
        self._get_gas_estimate_task = None
        self._network_transaction_fee = None
        self._poll_notifier = None
        self._native_currency = None
        self._order_tracker: ClientOrderTracker = ClientOrderTracker(connector=self, lost_order_count_limit=10)
        self._amount_quantum_dict = {}
        safe_ensure_future(self.load_token_data())

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(cls.__name__)
        return cast(HummingbotLogger, s_logger)

    @property
    def connector_name(self):
        """
        Returns the name of connector/protocol to be connected to on Gateway.
        """
        return self._connector_name

    @property
    def chain(self):
        return self._chain

    @property
    def network(self):
        return self._network

    @property
    def name(self):
        return self._name

    @property
    def address(self):
        return self._wallet_address

    async def all_trading_pairs(self) -> List[str]:
        """
        Calls the tokens endpoint on Gateway.
        """
        try:
            tokens = await GatewayHttpClient.get_instance().get_tokens(self._chain, self._network)
            token_symbols = [t["symbol"] for t in tokens["tokens"]]
            trading_pairs = []
            for base, quote in it.permutations(token_symbols, 2):
                trading_pairs.append(f"{base}-{quote}")
            return trading_pairs
        except Exception:
            return []

    @property
    def amm_orders(self) -> List[GatewayInFlightOrder]:
        return [
            in_flight_order
            for in_flight_order in self._order_tracker.active_orders.values()
            if in_flight_order.is_open
        ]

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self.amm_orders
        ]

    @property
    def network_transaction_fee(self) -> TokenAmount:
        return self._network_transaction_fee

    @network_transaction_fee.setter
    def network_transaction_fee(self, new_fee: TokenAmount):
        self._network_transaction_fee = new_fee

    @property
    def in_flight_orders(self) -> Dict[str, GatewayInFlightOrder]:
        return self._order_tracker.active_orders

    @property
    def tracking_states(self) -> Dict[str, Any]:
        return {
            key: value.to_json()
            for key, value in self.in_flight_orders.items()
        }

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        self._order_tracker._in_flight_orders.update({
            key: GatewayInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    @staticmethod
    def create_market_order_id(side: TradeType, trading_pair: str) -> str:
        return f"{side.name.lower()}-{trading_pair}-{get_tracking_nonce()}"

    async def load_token_data(self):
        tokens = await GatewayHttpClient.get_instance().get_tokens(self.chain, self.network)
        for t in tokens.get("tokens", []):
            self._amount_quantum_dict[t["symbol"]] = Decimal(str(10 ** -t["decimals"]))

    async def get_chain_info(self):
        """
        Calls the base endpoint of the connector on Gateway to know basic info about chain being used.
        """
        try:
            self._chain_info = await self._get_gateway_instance().get_network_status(
                chain=self.chain, network=self.network
            )
            if not isinstance(self._chain_info, list):
                self._native_currency = self._chain_info.get("nativeCurrency", "SOL")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                "Error fetching chain info",
                exc_info=True,
                app_warning_msg=str(e)
            )

    async def get_gas_estimate(self):
        """
        Gets the gas estimates for the connector.
        """
        try:
            response: Dict[Any] = await self._get_gateway_instance().amm_estimate_gas(
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
        pool_id = None

        try:
            trading_pair, pool_id = trading_pair.split("_")
        except Exception:
            pass
        base, quote = trading_pair.split("-")
        side: TradeType = TradeType.BUY if is_buy else TradeType.SELL

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
                    # gas_price_token: str = resp["gasPriceToken"]
                    # gas_cost: Decimal = Decimal(resp["gasCost"])
                    # self.network_transaction_fee = TokenAmount(gas_price_token, gas_cost)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass
                return test_price

        # Pull the price from gateway.
        try:
            resp: Dict[str, Any] = await self._get_gateway_instance().get_price(
                self.chain, self.network, self.connector_name, base, quote, amount, side, pool_id=pool_id
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
            ignore_shim: bool = False
    ) -> Decimal:

        """
        This is simply the quote price
        """
        return await self.get_quote_price(trading_pair, is_buy, amount, ignore_shim=ignore_shim)

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
        :param price: The order price
        """
        pool_id = None

        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)
        try:
            trading_pair, pool_id = trading_pair.split("_")
        except Exception:
            pass
        base, quote = trading_pair.split("-")
        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  trade_type=trade_type,
                                  price=price,
                                  amount=amount)
        try:
            order_result: Dict[str, Any] = await self._get_gateway_instance().amm_trade(
                self.chain,
                self.network,
                self.connector_name,
                self.address,
                base,
                quote,
                trade_type,
                amount,
                price,
                pool_id=pool_id,
                **request_args
            )
            transaction_hash: Optional[str] = order_result.get("txHash")
            if transaction_hash is not None and transaction_hash != "":
                # gas_cost: Decimal = Decimal(order_result.get("gasCost"))
                # gas_price_token: str = order_result.get("gasPriceToken")
                # self.network_transaction_fee = TokenAmount(gas_price_token, gas_cost)

                order_update: OrderUpdate = OrderUpdate(
                    client_order_id=order_id,
                    exchange_order_id=transaction_hash,
                    trading_pair=trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=OrderState.OPEN,  # Assume that the transaction has been successfully mined.
                    misc_updates={
                        "nonce": order_result.get("nonce", 0),  # Default to 0 if nonce is not present
                        "gas_price": Decimal(order_result.get("gasPrice")),
                        "gas_limit": int(order_result.get("gasLimit")),
                        "gas_cost": Decimal(order_result.get("gasCost")),
                        "gas_price_token": order_result.get("gasPriceToken"),
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

    def start_tracking_order(self,
                             order_id: str,
                             exchange_order_id: Optional[str] = None,
                             trading_pair: str = "",
                             trade_type: TradeType = TradeType.BUY,
                             price: Decimal = s_decimal_0,
                             amount: Decimal = s_decimal_0,
                             gas_price: Decimal = s_decimal_0,
                             is_approval: bool = False):
        """
        Starts tracking an order by simply adding it into _in_flight_orders dictionary in ClientOrderTracker.
        """
        self._order_tracker.start_tracking_order(
            GatewayInFlightOrder(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=trade_type,
                price=price,
                amount=amount,
                gas_price=gas_price,
                creation_timestamp=self.current_timestamp,
                initial_state=OrderState.PENDING_APPROVAL if is_approval else OrderState.PENDING_CREATE
            )
        )

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order by simply removing it from _in_flight_orders dictionary in ClientOrderTracker.
        """
        self._order_tracker.stop_tracking_order(client_order_id=order_id)

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

    def get_taker_order_type(self):
        return OrderType.LIMIT

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        return Decimal("1e-15")

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        base, quote = trading_pair.split("_")[0].split("-")
        return max(self._amount_quantum_dict[base], self._amount_quantum_dict[quote])

    @property
    def ready(self):
        return all(self.status_dict.values())

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "native_currency": self._native_currency is not None,
            "network_transaction_fee": self.network_transaction_fee is not None if self._trading_required else True,
        }

    async def check_network(self) -> NetworkStatus:
        """
        Checks if the gateway is up and running.
        """
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

    async def update_balances(self, on_interval: bool = False):
        """
        Calls Solana API to update total and available balances.
        """
        if self._native_currency is None:
            await self.get_chain_info()
        connector_tokens = GatewayConnectionSetting.get_connector_spec_from_market_name(self._name).get("tokens", "").split(",")
        last_tick = self._last_balance_poll_timestamp
        current_tick = self.current_timestamp
        if not on_interval or (current_tick - last_tick) > self.UPDATE_BALANCE_INTERVAL:
            self._last_balance_poll_timestamp = current_tick
            local_asset_names = set(self._account_balances.keys())
            remote_asset_names = set()
            token_list = list(self._tokens) + [self._native_currency] + connector_tokens
            resp_json: Dict[str, Any] = await self._get_gateway_instance().get_balances(
                chain=self.chain,
                network=self.network,
                address=self.address,
                token_symbols=token_list
            )
            for token, bal in resp_json["balances"].items():
                self._account_available_balances[token] = Decimal(str(bal))
                self._account_balances[token] = Decimal(str(bal))
                remote_asset_names.add(token)
            asset_names_to_remove = local_asset_names.difference(remote_asset_names)
            for asset_name in asset_names_to_remove:
                del self._account_available_balances[asset_name]
                del self._account_balances[asset_name]
            self._in_flight_orders_snapshot = {k: copy.copy(v) for k, v in self._order_tracker.all_orders.items()}
            self._in_flight_orders_snapshot_timestamp = self.current_timestamp

    async def _update_balances(self):
        """
        This is called by UserBalances.
        """
        await self.update_balances()

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        """
        This is intentionally left blank, because cancellation is expensive on blockchains. It's not worth it for
        Hummingbot to force cancel all orders whenever Hummingbot quits.
        """
        return []

    def _get_gateway_instance(self) -> GatewayHttpClient:
        """
        Returns the Gateway HTTP instance.
        """
        gateway_instance = GatewayHttpClient.get_instance(self._client_config)
        return gateway_instance
