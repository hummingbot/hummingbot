# DISABLE SELECT PYLINT TESTS
# pylint: disable=bad-continuation, broad-except, no-member, too-many-lines
# pylint: disable=no-name-in-module, too-many-arguments, too-many-public-methods
# pylint: disable=too-many-locals, too-many-instance-attributes, import-error
# pylint: disable=too-many-statements, useless-super-delegation
# pylint: disable=too-many-instance-attributes,
"""
 ╔════════════════════════════════════════════════════╗
 ║ ╔═╗╦═╗╔═╗╔═╗╦ ╦╔═╗╔╗╔╔═╗  ╔╦╗╔═╗╔╦╗╔═╗╔╗╔╔═╗╔╦╗╔═╗ ║
 ║ ║ ╦╠╦╝╠═╣╠═╝╠═╣║╣ ║║║║╣   ║║║║╣  ║ ╠═╣║║║║ ║ ║║║╣  ║
 ║ ╚═╝╩╚═╩ ╩╩  ╩ ╩╚═╝╝╚╝╚═╝  ╩ ╩╚═╝ ╩ ╩ ╩╝╚╝╚═╝═╩╝╚═╝ ║
 ║    DECENTRALIZED EXCHANGE HUMMINGBOT CONNECTOR     ║
 ╚════════════════════════════════════════════════════╝
~
forked from  binance_exchange v1.0.0
~
"""
# STANDARD MODULES
import asyncio
import json
import logging
import os
import time
from decimal import Decimal
from itertools import permutations
from multiprocessing import Process
from threading import Thread
from typing import AsyncIterable, Dict, List, Optional

# METANODE MODULES
from metanode.graphene_metanode_client import GrapheneTrustlessClient
from metanode.graphene_metanode_server import GrapheneMetanode
from metanode.graphene_rpc import RemoteProcedureCall

# HUMMINGBOT MODULES
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.exchange.graphene import graphene_utils
from hummingbot.connector.exchange.graphene.graphene_auth import GrapheneAuth
from hummingbot.connector.exchange.graphene.graphene_constants import GrapheneConstants
from hummingbot.connector.exchange.graphene.graphene_order_book_tracker import GrapheneOrderBookTracker
from hummingbot.connector.exchange.graphene.graphene_user_stream_tracker import GrapheneUserStreamTracker
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.trade_fee import (
    AddedToCostTradeFee,
    DeductedFromReturnsTradeFee,
    TokenAmount,
    TradeFeeBase,
)
from hummingbot.core.event.events import OrderType, TradeType
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger

# GLOBAL CONSTANTS
DEV = True


def dprint(*data):
    """print for development"""
    if DEV:
        print(*data)


def dinput(data):
    """input for development"""
    out = None
    if DEV:
        out = input(data)
    return out


def kill_metanode():
    for domain in ["bitshares", "bitshares_testnet", "peerplays", "peerplays_testnet"]:
        constants = GrapheneConstants(domain)
        with open(constants.DATABASE_FOLDER + "metanode_flags.json", "w+") as handle:
            handle.write(json.dumps({**json.loads(handle.read() or "{}"), domain.replace("_", " "): False}))


class GrapheneClientOrderTracker(ClientOrderTracker):
    """
    add swap_order_id method to ClientOrderTracker
    """

    def __init__(
        self,
        connector,
    ):
        # ~ print("GrapheneClientOrderTracker")
        super().__init__(connector)

    def swap_id(
        self,
        client_order_id: Optional[str] = None,
        exchange_order_id: Optional[str] = None,
    ) -> str:
        """
        given client_order_id return exchange_order_id
        given exchange_order_id return client_order_id
        """
        if client_order_id and client_order_id in self.all_orders:
            return self.all_orders[client_order_id].exchange_order_id

        if exchange_order_id:
            for order in self.all_orders.values():
                if order.exchange_order_id == exchange_order_id:
                    return order.client_order_id
        return None


class GrapheneExchange(ExchangeBase):
    """
    the master class which ties together all DEX connector components
    """

    # FIXME move to hummingbot constants
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0
    _logger = None

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        peerplays_wif: str,
        peerplays_user: str,
        peerplays_pairs: str,
        domain: str = "peerplays",
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
    ):
        # ~ print(__class__.__name__)
        # ~ print(
        # ~ "GrapheneExchange", peerplays_wif, domain, trading_pairs, trading_required
        # ~ )

        self._time_synchronizer = TimeSynchronizer()
        self.domain = domain
        super().__init__(client_config_map)
        self._username = peerplays_user
        self._pairs = peerplays_pairs.replace(" ", "").split(",")
        self._wif = peerplays_wif
        self._trading_pairs = trading_pairs
        self._trading_required = trading_required
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        # Dict[client_order_id:str, count:int]
        self._order_not_found_records = {}
        # Dict[trading_pair:str, TradingRule]
        self._trading_rules = {}
        # Dict[trading_pair:str, (maker_fee_percent:Dec, taker_fee_percent:Dec)]
        self._trade_fees = {}
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._user_stream_tracker_task = None
        self._status_polling_task = None
        self._metanode_process = None
        self._last_timestamp = 0
        self._last_poll_timestamp = 0
        self._last_update_trade_fees_timestamp = 0
        self._last_trades_poll_graphene_timestamp = 0

        # initialize Graphene class objects
        self.constants = GrapheneConstants(domain)

        with open(self.constants.DATABASE_FOLDER + domain + "_pairs.txt", "w+") as handle:
            # if there are new pairs, then change the file and signal to restart the metanode
            if handle.read() != json.dumps([self._pairs, self._username]):
                handle.write(json.dumps([self._pairs, self._username]))
                self.signal_metanode(False)

        self.constants = GrapheneConstants(domain)
        self.constants.process_pairs()

        self.metanode = GrapheneTrustlessClient(self.constants)
        self._metanode_server = GrapheneMetanode(self.constants)

        if not os.path.isfile(self.constants.chain.DATABASE):
            self._metanode_server.sql.restart()

        self._order_tracker: ClientOrderTracker = GrapheneClientOrderTracker(
            connector=self
        )
        self._order_book_tracker = GrapheneOrderBookTracker(
            trading_pairs=trading_pairs,
            domain=domain,
        )
        self._user_stream_tracker = GrapheneUserStreamTracker(
            domain=domain,
            order_tracker=self._order_tracker,
        )
        self._auth = GrapheneAuth(
            wif=peerplays_wif,
            domain=self.domain,
        )

    def dev_log(self, *args, **kwargs):
        """
        log only in dev mode
        """
        if DEV:
            self.logger().info(*args, **kwargs)

    @classmethod
    def logger(cls) -> HummingbotLogger:
        """
        a classmethod for logging
        """
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @property
    def name(self) -> str:
        """
        the name of this graphene blockchain
        """
        # self.dev_log("name")
        return self.domain

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        """
        a dictionary keyed by pair of subdicts keyed bids/asks
        """
        # self.dev_log("order_books")
        return self._order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        """
        a TradingRule object specific to a trading pair
        """
        # self.dev_log("trading_rules")
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, InFlightOrder]:
        """
        a dict of active orders keyed by client id with relevant order tracking info
        """
        # self.dev_log("in_flight_orders")
        return self._order_tracker.active_orders

    @property
    def limit_orders(self) -> List[LimitOrder]:
        """
        a list of LimitOrder objects
        """
        # self.dev_log("limit_orders")
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self.in_flight_orders.values()
        ]

    @property
    def tracking_states(self) -> Dict[str, any]:
        """
        Returns a dictionary associating current active orders client id
        to their JSON representation
        """
        # self.dev_log("tracking_states")
        return {key: value.to_json() for key, value in self.in_flight_orders.items()}

    @property
    def order_book_tracker(self) -> GrapheneOrderBookTracker:
        """
        the class that tracks bids and asks for each pair
        """
        # self.dev_log("order_book_tracker")
        return self._order_book_tracker

    @property
    def user_stream_tracker(self) -> GrapheneUserStreamTracker:
        """
        the class that tracks trades for each pair
        """
        # self.dev_log("user_stream_tracker")
        return self._user_stream_tracker

    @property
    def status_dict(self) -> Dict[str, bool]:
        """
        Returns a dictionary with the values of all the conditions
        that determine if the connector is ready to operate.
        The key of each entry is the condition name,
        and the value is True if condition is ready, False otherwise.
        """
        # self.dev_log("status_dict")
        # self._update_balances()
        # ~ self.dev_log(self._account_balances)
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(list(self._account_balances.values())) > 0
            if self._trading_required
            else True,
            "trading_rule_initialized": len(self._trading_rules) > 0,
            "metanode_live": 0 < time.time() - self.metanode.timing["blocktime"] < 100,
        }

    @property
    def ready(self) -> bool:
        """
        Returns True if the connector is ready to operate
        (all connections established with the DEX).
        If it is not ready it returns False.
        """
        self.dev_log("ready")
        self.dev_log(self.status_dict)
        return all(self.status_dict.values())

    @staticmethod
    def graphene_order_type(order_type: OrderType) -> str:
        """
        LIMIT
        """
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(graphene_type: str) -> OrderType:
        """
        OrderType.LIMIT
        """
        return OrderType[graphene_type]

    @staticmethod
    def supported_order_types():
        """
        a list containing only OrderType.LIMIT
        """
        return [OrderType.LIMIT]

    async def _initialize_trading_pair_symbol_map(self):
        rpc = RemoteProcedureCall(self.constants, self.metanode.whitelist)
        rpc.printing = False

        whitelisted_bases = self.constants.chain.BASES
        whitelist = []
        # for each whitelisted base
        for base in whitelisted_bases:
            # search the blockchain for tokens starting with that base
            whitelist.extend([i["symbol"] for i in rpc.list_assets(base) if "for_liquidity_pool" not in i])
            # if the list ends with a token containing the base, there may be more
            while whitelist[-1].startswith(base):
                # so keep going
                whitelist.extend([i["symbol"] for i in rpc.list_assets(whitelist[-1]) if "for_liquidity_pool" not in i])
        # make sure there are no duplicates, that they are all actually whitelisted, and sort them
        whitelist = sorted(list({i for i in whitelist if any(i.startswith(j + ".") for j in whitelisted_bases)}))
        whitelist.extend(whitelisted_bases + [self.constants.chain.CORE, *self.constants.chain.WHITELIST])
        # permutate all possible pairs and join in hummingbot format
        whitelist = ["-".join(i) for i in permutations(whitelist, 2)]
        # output
        self._set_trading_pair_symbol_map({i: i for i in whitelist})

    async def start_network(self):
        """
        Start all required tasks to update the status of the connector.
        Those tasks include:
        - The order book tracker
        - The polling loop to update the trading rules
        - The polling loop to update order status and balance status using REST API
        (backup for main update process)
        """
        dprint("GrapheneExchange.start_network")
        self._order_book_tracker.start()
        dprint("Order Book Started")
        self._trading_rules_polling_task = safe_ensure_future(
            self._trading_rules_polling_loop()
        )
        dprint("Trading Rules Started")
        # ~ if self._trading_required:
        self._status_polling_task = safe_ensure_future(self._status_polling_loop())
        dprint("Status Polling Started")
        self._user_stream_tracker_task = safe_ensure_future(
            self._user_stream_tracker.start()
        )
        dprint("User Stream Tracker Started")
        self._user_stream_event_listener_task = safe_ensure_future(
            self._user_stream_event_listener()
        )
        dprint("User Stream Listener Started")

        self.dev_log(f"Authenticating {self.domain}...")
        msg = (
            "Authenticated" if self._auth.login()["result"] is True else "Login Failed"
        )
        self.dev_log(msg)

    async def stop_network(self):
        """
        This function is executed when the connector is stopped.
        It perform a general cleanup and stops all background
        tasks that require the connection with the DEX to work.
        """
        await asyncio.sleep(0.1)
        self.dev_log("GrapheneExchange.stop_network")
        self.dev_log("Waiting for cancel_all...")
        await asyncio.sleep(30)
        self._last_timestamp = 0
        self._last_poll_timestamp = 0
        self._order_book_tracker.stop()
        self._poll_notifier = asyncio.Event()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
        self._status_polling_task = self._user_stream_tracker_task = None
        await asyncio.sleep(0.1)
        try:
            print("stopping metanode...")
            self.signal_metanode(False)
            if self.metanode:
                print("waiting for metanode")
                self._metanode_process.join()
        except Exception:
            self.dev_log("Failed to wait for metanode, must be in another instance.")

    def signal_metanode(self, signal):
        with open(self.constants.DATABASE_FOLDER + "metanode_flags.json", "w+") as handle:
            handle.write(json.dumps({**json.loads(handle.read() or "{}"), self.domain.replace("_", " "): signal}))

    async def check_network(self) -> NetworkStatus:
        """
        ensure metanode blocktime is not stale, if it is, restart the metanode
        """
        self.dev_log(str(self.in_flight_orders))
        # self.dev_log("check_network")
        status = NetworkStatus.NOT_CONNECTED
        self.dev_log("Checking Network...")
        try:
            # if the metanode is less than 2 minutes stale, we're connected
            # in practice, once live it should always pass this test
            try:
                blocktime = self.metanode.timing["blocktime"]
            except IndexError:  # the metanode has not created a database yet
                blocktime = 0
            latency = time.time() - blocktime
            if 0 < latency < 60:
                msg = f"Metanode Connected, latency {latency:.2f}"
                self.dev_log(msg)
                status = NetworkStatus.CONNECTED
            # otherwise attempt to restart the metanode; eg. on startup
            else:
                self.dev_log("Deploying Metanode Server Process, please wait...")
                self.dev_log(
                    "ALERT: Check your system monitor to ensure hardware compliance, "
                    "Metanode is cpu intensive, requires ram, and rapid read/write"
                )
                self.logger().info(
                    "This may hang for a moment while starting "
                    "the Metanode, please be patient."
                )
                await asyncio.sleep(0.1)  # display message to hummingbot ui
                try:
                    self.signal_metanode(False)
                    self._metanode_process.join()
                except Exception:
                    pass
                self.signal_metanode(True)
                self._metanode_process = Process(target=self._metanode_server.deploy)
                self._metanode_process.start()
                # do not proceed until metanode is running
                patience = 10
                while True:
                    patience -= 1
                    msg = f"Metanode Server Initializing... patience={patience}"
                    if patience == -10:
                        msg = (
                            "I am out of patience.\n"
                            + "It appears Metanode FAILED, check configuration and that"
                            + " DEV mode is off."
                        )
                        self.dev_log(msg)
                        status = NetworkStatus.NOT_CONNECTED
                        break
                    self.dev_log(msg)
                    try:
                        # wait until less than one minute stale
                        blocktime = self.metanode.timing["blocktime"]
                        latency = time.time() - blocktime
                        if 0 < latency < 60:
                            msg = f"Metanode Connected, latency {latency:.2f}"
                            self.dev_log(msg)
                            status = NetworkStatus.CONNECTED
                            await asyncio.sleep(10)
                            break
                    except Exception as error:
                        self.dev_log(error)
                    await asyncio.sleep(6)
        except asyncio.CancelledError:
            msg = f"asyncio.CancelledError {__name__}"
            self.logger().exception(msg)
        except Exception as error:
            msg = f"check network failed {__name__} {error.args}"
            self.logger().exception(msg)
        return status

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        """
        Restore in-flight orders from saved tracking states,
        this is so the connector result pick up on where it left off
        when it disconnects.
        :param saved_states: The saved tracking_states.
        """
        # self.dev_log("restore_tracking_states")
        self._order_tracker.restore_tracking_states(tracking_states=saved_states)

    def tick(self, timestamp: float):
        """
        Includes the logic processed every time a new tick happens in the bot.
        It enables execution of the status update polling loop using an event.
        """
        self.dev_log("tick")
        now = time.time()
        poll_interval = (
            self.SHORT_POLL_INTERVAL
            if now - self.user_stream_tracker.last_recv_time > 60.0
            else self.LONG_POLL_INTERVAL
        )
        last_tick = int(self._last_timestamp / poll_interval)
        current_tick = int(timestamp / poll_interval)

        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    def get_order_book(self, trading_pair: str) -> OrderBook:
        """
        Returns the current order book for a particular market
        :param trading_pair: BASE-QUOTE
        """
        # self.dev_log("get_order_book")
        if trading_pair not in self._order_book_tracker.order_books:
            inverted_pair = "-".join(trading_pair.split("-")[::-1])
            if inverted_pair in self._order_book_tracker.order_books:
                trading_pair = inverted_pair
                return self._order_book_tracker.order_books[trading_pair]
            else:
                raise ValueError(f"No order book exists for '{trading_pair}'.")
        return self._order_book_tracker.order_books[trading_pair]

    def start_tracking_order(
        self,
        order_id: str,
        exchange_order_id: Optional[str],
        trading_pair: str,
        trade_type: TradeType,
        price: Decimal,
        amount: Decimal,
        order_type: OrderType,
    ):
        """
        Starts tracking an order by adding it to the order tracker.
        :param order_id: the order identifier
        :param exchange_order_id: the identifier for the order in the DEX
        :param trading_pair: BASE-QUOTE
        :param trade_type: the type of order (buy or sell)
        :param price: the price for the order
        :param amount: the amount for the order
        :order type: type of execution for the order (MARKET, LIMIT, LIMIT_MAKER)
        """
        # self.dev_log("start_tracking_order")
        self._order_tracker.start_tracking_order(
            InFlightOrder(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=trade_type,
                amount=amount,
                creation_timestamp=int(time.time() * 1e3),
                price=price,
            )
        )

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order
        :param order_id: The id of the order that will not be tracked any more
        """
        # self.dev_log("stop_tracking_order")
        self._order_tracker.stop_tracking_order(client_order_id=order_id)

    def get_order_price_quantum(self, trading_pair: str, *_) -> Decimal:
        """
        Used by quantize_order_price() in _limit_order_create()
        Returns a price step, a minimum price increment for a given trading pair.
        :param trading_pair: the trading pair to check for market conditions
        :param price: the starting point price
        """
        # self.dev_log("get_order_price_quantum")
        trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    def get_order_size_quantum(self, trading_pair: str, *_) -> Decimal:
        """
        Used by quantize_order_price() in _limit_order_create()
        Returns an order amount step, a minimum amount increment for a given pair.
        :param trading_pair: the trading pair to check for market conditions
        :param order_size: the starting point order price
        """
        # self.dev_log("get_order_size_quantum")
        trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_base_amount_increment

    def quantize_order_amount(
        self,
        trading_pair: str,
        amount: Decimal,
        side: str,
        price: Decimal = Decimal(0),
    ) -> Decimal:
        """
        Applies the trading rules to calculate the correct order amount for the market
        :param trading_pair: the token pair for which the order will be created
        :param amount: the intended amount for the order
        :param price: the intended price for the order
        :return: the quantized order amount after applying the trading rules
        """
        # self.dev_log("quantize_order_amount")
        trading_rule = self._trading_rules[trading_pair]
        quantized_amount: Decimal = self.quantize_order_amount_by_side(trading_rule, amount, side)

        # Check against min_order_size and min_notional_size.
        # If not passing either check, return 0.
        min_size = trading_rule.min_order_value

        self.dev_log(f"QUANTIZE_ORDER_AMOUNT: quantized amount {quantized_amount}    minimum size {min_size}")

        if quantized_amount < min_size:
            return Decimal(0)

        if price == Decimal(0):
            current_price: Decimal = self.get_price(trading_pair, False)
            notional_size = current_price * quantized_amount
        else:
            notional_size = price * quantized_amount

        min_notional_size = trading_rule.min_order_size

        self.dev_log(f"QUANTIZE_ORDER_AMOUNT: notional size {notional_size}    minimum size plus 1% {min_notional_size * Decimal('1.01')}")
        # Add 1% as a safety factor in case the prices changed while making the order.
        if notional_size < min_notional_size * Decimal("1.01"):
            return Decimal(0)

        return quantized_amount

    def get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        _,  # order_type: OrderType,
        order_side: TradeType,  # TradeType.BUY TradeType.SELL
        __,  # amount: Decimal,
        ___,  # price: Decimal = Decimal("nan"),
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        """
        Calculates the estimated fee an order would pay
        Graphene fees include a added flat transaction fee paid in core token; 1.3.0
        AND a deducted percent based market fees paid in currency RECEIVED
        market fees MAY have maker/taker functionality
        """
        class GrapheneTradeFee(TradeFeeBase):
            """
            a trade fee class which includes both Added and Deducted fees
            """

            def get_fee_impact_on_order_cost(_):
                """
                Added Fees
                """
                return AddedToCostTradeFee.get_fee_impact_on_order_cost

            def get_fee_impact_on_order_returns(_):
                """
                Deducted Fees
                """
                return DeductedFromReturnsTradeFee.get_fee_impact_on_order_returns

            def type_descriptor_for_json(_):
                ...

        # self.dev_log("get_fee")
        account = dict(self.metanode.account)  # DISCRETE SQL QUERY
        objects = dict(self.metanode.objects)  # DISCRETE SQL QUERY
        assets = dict(self.metanode.assets)  # DISCRETE SQL QUERY
        tx_currency = objects["1.3.0"]["name"]
        tx_amount = account["fees_account"]["create"]
        # you pay trade fee on the currency you receive in the transaction
        trade_currency = quote_currency
        maker_pct = assets[quote_currency]["fees_asset"]["fees"]["maker"]
        taker_pct = assets[quote_currency]["fees_asset"]["fees"]["taker"]
        if order_side == TradeType.BUY:
            trade_currency = base_currency
            maker_pct = assets[base_currency]["fees_asset"]["fees"]["maker"]
            taker_pct = assets[base_currency]["fees_asset"]["fees"]["taker"]
        trade_pct = maker_pct if is_maker else taker_pct
        # build a TradeFeeBase class object
        flat_fee = TokenAmount(token=tx_currency, amount=Decimal(tx_amount))
        fee = GrapheneTradeFee(
            flat_fees=[flat_fee],
            percent=Decimal(trade_pct),
            # handle TradeFeeBase warning; do not specify token if its quote token
            percent_token=trade_currency if trade_currency != quote_currency else None,
        )
        # ##############################################################################
        # FIXME the hummingbot binance reference is a path to deprecation warning
        # ##############################################################################
        # there appears to be no functional reference material, see:
        # ~
        # ~ BitshareExchange
        #  ~ ExchangeBase
        #   ~ ConnectorBase
        #    ~ estimate_fee_pct
        #     ~ core.utils.estimate_fee.estimate_fee < binance ends here not implemented
        # ##############################################################################
        # FIXME just return ZERO like this?  peer review please
        # return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(False))
        # ##############################################################################
        return fee

    def buy(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType = OrderType.LIMIT,
        price: Decimal = Decimal("nan"),
        **__,
    ) -> str:
        """
        Creates a promise to create a buy order using the parameters.
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: all graphene orders are LIMIT type
        :param price: the order price
        :return: the id assigned by the connector to the order (the client id)
        """
        # self.dev_log("buy")
        order_id = graphene_utils.get_new_client_order_id(
            is_buy=True, trading_pair=trading_pair
        )
        safe_ensure_future(
            self._limit_order_create(
                TradeType.BUY, order_id, trading_pair, amount, order_type, price
            )
        )
        return order_id

    def sell(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType = OrderType.LIMIT,
        price: Decimal = Decimal("nan"),
        **__,
    ) -> str:
        """
        Creates a promise to create a sell order using the parameters.
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: all graphene orders are LIMIT type
        :param price: the order price
        :return: the id assigned by the connector to the order (the client id)
        """
        # self.dev_log("sell")
        order_id = graphene_utils.get_new_client_order_id(
            is_buy=False, trading_pair=trading_pair
        )
        safe_ensure_future(
            self._limit_order_create(
                TradeType.SELL, order_id, trading_pair, amount, order_type, price
            )
        )
        return order_id

    def cancel(self, trading_pair: str, order_id: str):
        """
        Creates a promise to cancel an order in the DEX
        :param trading_pair: the trading pair the order to cancel operates with
        :param order_id: the client id of the order to cancel
        :return: the client id of the order to cancel
        """
        # self.dev_log("cancel")
        safe_ensure_future(
            self._limit_order_cancel(
                trading_pair=trading_pair,
                client_order_id=order_id,
            )
        )
        return order_id

    async def cancel_all(self, _) -> List[CancellationResult]:
        """
        Cancels all currently active orders.
        The cancellations are batched at the core level into groups of 20 per tx
        Used by bot's top level stop and exit commands
        (cancelling outstanding orders on exit)
        :param timeout_seconds: the maximum time in seconds the cancel logic should run
        :return: a list of CancellationResult instances, one for each of the order
        """
        # self.dev_log("cancel_all")
        # get an order id set of known open orders hummingbot is tracking
        # change each OrderState to PENDING_CANCEL
        await asyncio.sleep(0.01)

        hummingbot_open_client_ids = {
            o.client_order_id for o in self.in_flight_orders.values() if not o.is_done
        }

        rpc = RemoteProcedureCall(self.constants)
        open_client_ids = [j for j in [self._order_tracker.swap_id(exchange_order_id=i) for i in rpc.open_order_ids()] if j is not None]

        await asyncio.sleep(0.01)

        # disregard unnecessary open orders; blockchain is gospel, not hummingbot
        for order_id in hummingbot_open_client_ids:
            if order_id not in open_client_ids:
                self.stop_tracking_order(order_id)

        msg = f"open_client_ids {len(open_client_ids)} {open_client_ids}"
        self.dev_log(msg)
        if not open_client_ids:
            return []
        open_exchange_ids = {
            self._order_tracker.swap_id(i)
            for i in open_client_ids
            if self._order_tracker.swap_id(i) is not None
        }
        open_ids = {
            self._order_tracker.swap_id(i): i
            for i in open_client_ids
            if self._order_tracker.swap_id(i) is not None
        }
        await asyncio.sleep(0.01)
        # log open orders in client and DEX terms
        msg = f"open_exchange_ids {len(open_exchange_ids)} {open_exchange_ids}"
        self.dev_log(msg)
        await asyncio.sleep(0.01)
        for order_id in open_client_ids:
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                trading_pair=self.in_flight_orders[order_id].trading_pair,
                update_timestamp=int(time.time() * 1e3),
                new_state=OrderState.PENDING_CANCEL,
            )
            self._order_tracker.process_order_update(order_update)
            await asyncio.sleep(0.01)

        cancelled_exchange_ids = []
        for pair in self._trading_pairs:
            # build a cancel all operation using the broker(order) method
            order = json.loads(self._auth.prototype_order(pair))
            # order["edicts"] = [{"op": "cancel", "ids": list(open_exchange_ids)}]
            order["edicts"] = [{"op": "cancel", "ids": ["1.7.X"]}]

            await asyncio.sleep(0.01)
            # cancel all and get a cancellation result list of DEX order ids
            self.dev_log(order["edicts"])
            cancelled_exchange_ids.extend((await self._broker(order))["result"])

        msg = (
            f"cancelled_exchange_ids {len(cancelled_exchange_ids)}"
            + f" {cancelled_exchange_ids}"
        )
        self.dev_log(msg)
        # swap the list to hummingbot client ids
        cancelled_client_ids = [open_ids[i] for i in cancelled_exchange_ids]
        await asyncio.sleep(0.01)
        # log cancelled orders in client and DEX terms
        msg = f"cancelled_client_ids {len(cancelled_client_ids)} {cancelled_client_ids}"
        self.dev_log(msg)

        await asyncio.sleep(0.01)
        # create a list of successful CancellationResult
        # change each OrderState to CANCELED
        successful_cancellations = []
        for order_id in cancelled_client_ids:
            successful_cancellations.append(CancellationResult(order_id, True))
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                trading_pair=self.in_flight_orders[order_id].trading_pair,
                update_timestamp=int(time.time() * 1e3),
                new_state=OrderState.CANCELED,
            )
            self._order_tracker.process_order_update(order_update)
            self.stop_tracking_order(order_id)
        msg = (
            f"successful_cancellations {len(successful_cancellations)}"
            + f" {successful_cancellations}"
        )
        self.dev_log(msg)

        # create a list of apparently failed CancellationResult
        # change each OrderState back to OPEN
        await asyncio.sleep(0.01)
        failed_cancellations = []
        for order_id in open_client_ids:  # client order ids
            if order_id not in cancelled_client_ids:
                failed_cancellations.append(CancellationResult(order_id, False))
                order_update: OrderUpdate = OrderUpdate(
                    client_order_id=order_id,
                    trading_pair=self.in_flight_orders[order_id].trading_pair,
                    update_timestamp=int(time.time() * 1e3),
                    new_state=OrderState.OPEN,
                )
                self._order_tracker.process_order_update(order_update)
        await asyncio.sleep(0.01)
        # log successful and failed cancellations

        msg = (
            f"failed_cancellations {len(failed_cancellations)}"
            + f" {failed_cancellations}"
        )
        self.dev_log(msg)
        await asyncio.sleep(0.01)
        # join the lists and return
        return successful_cancellations + failed_cancellations

    async def _broker(self, order):
        self.dev_log("self._broker")
        ret = {}
        borker = Thread(
            target=self._auth.broker,
            args=(
                order,
                ret,
            ),
        )
        borker.start()
        self.dev_log(ret)
        while not ret:
            await asyncio.sleep(1)
            self.dev_log("Waiting for manualSIGNING")
            self.dev_log(ret)
        return ret

    def quantize_order_amount_by_side(self, trading_rule, amount, side):
        """
        Applies trading rule to quantize order amount by side.
        """
        order_size_quantum = (
            trading_rule.min_base_amount_increment if side == "buy"
            else trading_rule.min_quote_amount_increment
        )
        return (amount // order_size_quantum) * order_size_quantum

    async def _limit_order_create(
        self,
        trade_type: TradeType,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType,
        price: Optional[Decimal] = Decimal("NaN"),
    ):
        """
        Creates a an order in the DEX using the parameters to configure it
        :param trade_type: the side of the order (BUY of SELL)
        :param order_id: the id that should be assigned to the order (the client id)
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        """
        # self.dev_log("_limit_order_create")
        self.dev_log("############### LIMIT ORDER CREATE ATTEMPT ###############")
        self.dev_log(trade_type)
        self.dev_log(order_type)
        self.dev_log(order_id)
        self.dev_log(trading_pair)
        self.dev_log(amount)
        self.dev_log(price)
        if self._wif == "":
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                exchange_order_id=order_id,
                trading_pair=trading_pair,
                update_timestamp=int(time.time() * 1e3),
                new_state=OrderState.OPEN,
            )
            self._order_tracker.process_order_update(order_update)
            return
        # get trading rules and normalize price and amount
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        price = self.quantize_order_price(trading_pair, price)
        quantize_amount_price = Decimal("0") if price.is_nan() else price
        amount = self.quantize_order_amount(
            trading_pair=trading_pair,
            amount=amount,
            side="buy" if trade_type == TradeType.BUY else "sell",
            price=quantize_amount_price,
        )
        # create an inflight order keyed by client order_id
        self.start_tracking_order(
            order_id=order_id,
            exchange_order_id=None,
            trading_pair=trading_pair,
            trade_type=trade_type,
            price=price,
            amount=amount,
            order_type=order_type,
        )
        # if the amount is too little disregard the order
        # update tracking status to FAILED
        if amount < trading_rule.min_order_value:
            msg = (
                f"{trade_type.name.title()} order amount {amount} is lower than the"
                f" minimum order size {trading_rule.min_order_value}. The order will not"
                " be created."
            )
            self.logger().warning(msg)
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                trading_pair=trading_pair,
                update_timestamp=int(time.time() * 1e3),
                new_state=OrderState.FAILED,
            )
            self._order_tracker.process_order_update(order_update)
            return
        # format an order, broadcast to the blockchain
        # update tracking status to OPEN
        try:
            order = json.loads(self._auth.prototype_order(trading_pair))
            self.dev_log(order)
            self.dev_log(trade_type)
            order["edicts"] = [
                {
                    "op": "buy" if trade_type == TradeType.BUY else "sell",
                    "amount": float(amount),
                    "price": float(price),
                    "expiration": 0,
                },
            ]
            self.dev_log(order["edicts"])
            await asyncio.sleep(0.01)
            result = await self._broker(order)
            # ~ {"method": "notice",
            # ~ "params": [1, [{
            # ~ "id": "9c91cd07aa2844473cc3c6047ec2c4f7ce40c8c1",
            # ~ "block_num": 66499124,
            # ~ "trx_num": 0,
            # ~ "trx": {
            # ~ "ref_block_num": 45619,
            # ~ "ref_block_prefix": 3851304488,
            # ~ "expiration": "2022-02-20T20:12:06",
            # ~ "operations": [
            # ~ [1, {
            # ~ "fee": {
            # ~ "amount": 48260,
            # ~ "asset_id": "1.3.0"
            # ~ },
            # ~ "seller": "1.2.743179",
            # ~ "amount_to_sell": {
            # ~ "amount": 5,
            # ~ "asset_id": "1.3.5640"
            # ~ },
            # ~ "min_to_receive": {
            # ~ "amount": 1000000,
            # ~ "asset_id": "1.3.0"
            # ~ },
            # ~ "expiration": "2096-10-02T07:06:40",
            # ~ "fill_or_kill": false,
            # ~ "extensions": []}],
            # ~ [1, {
            # ~ "fee": {
            # ~ "amount": 48260,
            # ~ "asset_id": "1.3.0"
            # ~ },
            # ~ "seller": "1.2.743179",
            # ~ "amount_to_sell": {
            # ~ "amount": 1000000,
            # ~ "asset_id": "1.3.0"
            # ~ },
            # ~ "min_to_receive": {
            # ~ "amount": 5,
            # ~ "asset_id": "1.3.5640"
            # ~ },
            # ~ "expiration": "2096-10-02T07:06:40",
            # ~ "fill_or_kill": false,
            # ~ "extensions": []}]],
            # ~ "extensions": [],
            # ~ "signatures": [
            # ~ "1f1fa0acde...d80f8254c6"
            # ~ ],
            # ~ "operation_results": [
            # ~ [1, {"1.7.490017546"],
            # ~ [1, {"1.7.490017547" ]]}}]]}
            ############################################################################
            if isinstance(result, dict) and result["status"]:
                exchange_order_id = result["result"]["params"][1][0]["trx"][
                    "operation_results"
                ][0][1]
                ########################################################################
                # update_timestamp = int(result["blocknum"])
                order_update: OrderUpdate = OrderUpdate(
                    client_order_id=order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=trading_pair,
                    update_timestamp=int(time.time() * 1e3),
                    new_state=OrderState.OPEN,
                )
                self._order_tracker.process_order_update(order_update)
            else:
                raise ValueError("DEX did not return an order id")
        except asyncio.CancelledError:
            msg = f"asyncio.CancelledError {__name__}"
            self.logger().exception(msg)
            raise
        # if anything goes wrong log stack trace
        # update tracking status to FAILED
        except Exception as error:
            self.logger().network(
                "Error submitting order to Graphene for "
                f"{amount} {trading_pair} "
                f"{price}.",
                exc_info=True,
                app_warning_msg=str(error),
            )
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                trading_pair=trading_pair,
                update_timestamp=int(time.time() * 1e3),
                new_state=OrderState.FAILED,
            )
            self._order_tracker.process_order_update(order_update)

    async def _limit_order_cancel(
        self,
        trading_pair: str,
        client_order_id: str,
    ) -> list:  # of exchange_order_id
        """
        Requests the DEX to cancel an active order
        :param trading_pair: the trading pair the order to cancel operates with
        :param client_order_id: the client id of the order to cancel
        """
        self.dev_log(f"CANCELLING ORDER #{client_order_id}")
        if self._wif == "":
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=client_order_id,
                trading_pair=trading_pair,
                update_timestamp=int(time.time() * 1e3),
                new_state=OrderState.CANCELED,
            )
            self._order_tracker.process_order_update(order_update)
            self.dev_log("############# PAPER #############")
            self.dev_log("ORDER STATUS UPDATED TO CANCELLED")
            self.dev_log("#################################")
            return [client_order_id]
        # self.dev_log("_limit_order_cancel")
        result = None
        tracked_order = self._order_tracker.fetch_tracked_order(client_order_id)
        # if this order was placed by hummingbot
        if tracked_order is not None:
            # change its status to pending cancellation
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=client_order_id,
                trading_pair=trading_pair,
                update_timestamp=int(time.time() * 1e3),
                new_state=OrderState.PENDING_CANCEL,
            )
            self._order_tracker.process_order_update(order_update)
            # attempt to cancel the order
            try:
                order = json.loads(self._auth.prototype_order(trading_pair))
                order["header"]["wif"] = self._wif
                order["edicts"] = [
                    {"op": "cancel", "ids": [tracked_order.exchange_order_id]}
                ]
                result = await self._broker(order)
                self.dev_log(f"CANCELLED ORDER #{client_order_id}")
            except asyncio.CancelledError:
                msg = f"asyncio.CancelledError {__name__}"
                self.logger().exception(msg)
                raise
            except Exception:
                msg = (
                    "There was a an error when requesting cancellation of order "
                    f"{client_order_id}"
                )
                self.logger().exception(msg)
                raise
        ################################################################################
        # if the result from the cancellation attempt contains the DEX order id
        # update the status to CANCELLED
        self.dev_log(result["result"])
        if (
            isinstance(result["result"], list)
            and result["result"]
            and result["result"][0] == tracked_order.exchange_order_id
        ):
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=client_order_id,
                trading_pair=trading_pair,
                update_timestamp=int(time.time() * 1e3),
                new_state=OrderState.CANCELED,
            )
            self._order_tracker.process_order_update(order_update)
            self.dev_log("ORDER STATUS UPDATED TO CANCELLED")
        # otherwise return the order state to open
        else:
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=client_order_id,
                trading_pair=trading_pair,
                update_timestamp=int(time.time() * 1e3),
                new_state=OrderState.OPEN,
            )
            self.dev_log("ORDER STATUS RETURNED TO OPEN")
            self._order_tracker.process_order_update(order_update)
        # return the list of cancellation results
        return result["result"]
        ################################################################################

    async def _status_polling_loop(self):
        """
        Performs all required operations to keep the connector synchronized
        with the DEX. It also updates the time synchronizer.
        Executes when the _poll_notifier event is enabled by the `tick` function.
        """
        while True:
            try:
                self.dev_log("###########STATUS#POLLING#LOOP#OCCOURING##########")
                while not self._poll_notifier.is_set():
                    await asyncio.sleep(1)
                    self.dev_log("LOOP IS " + str(self._poll_notifier))
                # ~ await self._poll_notifier.wait()
                self.dev_log("###################NOTIFIER#######################")
                await self._update_time_synchronizer()
                self.dev_log("###################TIME###########################")
                await self._update_balances()
                self.dev_log("###################BALANCES:######################")
                self.dev_log(self._account_balances)
                self._last_poll_timestamp = self.current_timestamp
                self.dev_log("###################TIMESTAMP######################")
                await asyncio.sleep(1)
                self.dev_log("###################END#LOOP#######################")
            except asyncio.CancelledError:
                msg = f"asyncio.CancelledError {__name__}"
                self.logger().exception(msg)
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching updates.",
                    exc_info=True,
                    app_warning_msg=(
                        "Could not fetch account updates. "
                        "Check metanode and network connection."
                    ),
                )
            except asyncio.CancelledError:
                break
            finally:
                self._poll_notifier = asyncio.Event()

    async def _trading_rules_polling_loop(self):
        """
        Performs all required operations to keep the connector synchronized
        with the DEX. It also updates the time synchronizer.
        Executes when the _poll_notifier event is enabled by the `tick` function.
        """
        # self.dev_log("_trading_rules_polling_loop")

        while True:
            try:
                await asyncio.sleep(1)
                await self._update_trading_rules()
            except asyncio.CancelledError:
                break
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching updates.",
                    exc_info=True,
                    app_warning_msg=(
                        "Could not fetch account updates. "
                        "Check metanode and network connection."
                    ),
                )

    async def _update_trading_rules(self):
        """
        gather DEX info from metanode.assets and pass on to _trading_rules
        """
        # self.dev_log("_update_trading_rules")
        try:
            graphene_max = self.constants.core.GRAPHENE_MAX
            metanode_assets = self.metanode.assets
            rules = []
            for trading_pair in self.constants.chain.PAIRS:
                base, quote = trading_pair.split("-")
                base_min = self.constants.core.DECIMAL_SATOSHI
                quote_min = self.constants.core.DECIMAL_SATOSHI
                supply = self.constants.core.DECIMAL_SATOSHI
                try:
                    base_min = Decimal(1) / 10 ** metanode_assets[base]["precision"]
                    quote_min = Decimal(1) / 10 ** metanode_assets[quote]["precision"]
                    supply = Decimal(metanode_assets[base]["supply"])
                except Exception:
                    pass
                rules.append(
                    TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=quote_min,
                        max_order_size=supply,
                        min_price_increment=Decimal(1) / int(graphene_max),
                        min_base_amount_increment=base_min,
                        min_quote_amount_increment=quote_min,
                        min_notional_size=base_min,
                        min_order_value=base_min,
                        max_price_significant_digits=Decimal(graphene_max),
                        supports_limit_orders=True,
                        supports_market_orders=False,  # OrderType.LIMIT *only*
                        buy_order_collateral_token=None,
                        sell_order_collateral_token=None,
                    )
                )
            self._trading_rules.clear()
            for trading_rule in rules:
                self._trading_rules[trading_rule.trading_pair] = trading_rule
        except Exception as error:
            msg = f"Error updating trading rules: {error.args}"
            self.logger().exception(msg)

    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events
        received from the DEX by the user stream data source.
        It keeps reading events from the queue until the task is interrupted.
        The events received are order updates and trade events.
        """
        # self.dev_log("_user_stream_event_listener")
        async def iter_user_event_queue() -> AsyncIterable[Dict[str, any]]:
            """
            fetch events from the user stream
            """
            while True:
                try:
                    user_streamer = await self._user_stream_tracker.user_stream.get()
                    self.dev_log("########################")
                    self.dev_log(user_streamer)
                    self.dev_log("########################")
                    yield user_streamer
                except asyncio.CancelledError:
                    break
                except Exception:
                    self.logger().network(
                        "Unknown error. Retrying after 1 seconds.",
                        exc_info=True,
                        app_warning_msg=(
                            "Could not fetch user events from Graphene."
                            "Check network connection."
                        ),
                    )
                    await asyncio.sleep(1.0)
                finally:
                    await asyncio.sleep(0.1)

        async for event_message in iter_user_event_queue():
            try:
                # localize and type cast values common to all event_messages
                trading_pair = str(event_message["trading_pair"])
                execution_type = str(event_message["execution_type"])
                client_order_id = str(event_message["client_order_id"])
                exchange_order_id = str(event_message["exchange_order_id"])
                # process trade event messages
                if execution_type == "FILL":
                    tracked_order = self._order_tracker.fetch_order(
                        client_order_id=client_order_id
                    )
                    if tracked_order is not None:
                        # localize and type cast fill order event message values
                        trade_id = str(event_message["trade_id"])
                        fee_asset = str(event_message["fee_asset"])
                        fee_paid = Decimal(event_message["fee_paid"])
                        fill_price = Decimal(event_message["price"])
                        fill_timestamp = int(event_message["fill_timestamp"])
                        fill_base_amount = Decimal(event_message["fill_base_amount"])
                        # estimate the quote amount
                        fill_quote_amount = fill_base_amount * fill_price
                        # process a trade update
                        trade_update = TradeUpdate(
                            client_order_id=client_order_id,
                            exchange_order_id=exchange_order_id,
                            trading_pair=trading_pair,
                            fill_base_amount=fill_base_amount,
                            fill_quote_amount=fill_quote_amount,
                            fill_price=fill_price,
                            trade_id=trade_id,
                            fee_asset=fee_asset,
                            fee_paid=fee_paid,
                            fill_timestamp=fill_timestamp,
                        )
                        self._order_tracker.process_trade_update(trade_update)
                # all other event messages just change order state
                # eg "CANCELLED" or "FILLED"
                in_flight_order = self.in_flight_orders.get(client_order_id)
                if in_flight_order is not None:
                    # localize order state event message values
                    update_timestamp = (int(event_message["update_timestamp"]),)
                    new_state = (
                        self.constants.ORDER_STATE[event_message["order_state"]],
                    )
                    # process an order update
                    order_update = OrderUpdate(
                        trading_pair=trading_pair,
                        client_order_id=client_order_id,
                        exchange_order_id=exchange_order_id,
                        update_timestamp=update_timestamp,
                        new_state=new_state,
                    )
                    self._order_tracker.process_order_update(order_update=order_update)
                await self._update_balances()
            except asyncio.CancelledError:
                msg = f"asyncio.CancelledError {__name__}"
                self.logger().exception(msg)
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error in user stream listener loop.", exc_info=True
                )
                await asyncio.sleep(1.0)

    async def _update_balances(self):
        """
        use metanode.assets 'total' and 'free' to update
            self._account_balances
            self._account_available_balances
        """
        # self.dev_log("Updating Balances")
        error_msg = None
        if self._account_balances == {}:
            self._auth.login()
        try:
            if await self.check_network() == NetworkStatus.NOT_CONNECTED:
                for asset in self.constants.chain.ASSETS:
                    self._account_available_balances[asset] = Decimal(0)
                    self._account_balances[asset] = Decimal(0)
                error_msg = "Error updating account balances: Metanode not connected.  Bad key?"
                self.logger().exception(error_msg)
            else:
                metanode_assets = self.metanode.assets
                for asset in self.constants.chain.ASSETS:
                    self._account_available_balances[asset] = Decimal(
                        str(metanode_assets[asset]["balance"]["free"])
                    )
                    self._account_balances[asset] = Decimal(
                        str(metanode_assets[asset]["balance"]["total"])
                    )
        except Exception as error:
            for asset in self.constants.chain.ASSETS:
                self._account_available_balances[asset] = Decimal(0)
                self._account_balances[asset] = Decimal(0)
            error_msg = f"Error updating account balances: {error.args}"
            self.logger().exception(error_msg)
        msgs = [
            "Available Balances",
            self._account_available_balances,
            "Total Balances",
            self._account_balances,
        ]
        for msg in msgs:
            self.dev_log(msg)
        if error_msg is not None:
            raise RuntimeError(error_msg)

    async def _update_time_synchronizer(self):
        """
        Used to synchronize the local time with the server's time.
        This class is useful when timestamp-based signatures
        are required by the DEX for authentication.
        Upon receiving a timestamped message from the server,
        use `update_server_time_offset_with_time_provider`
        to synchronize local time with the server's time.
        """
        # self.dev_log("_update_time_synchronizer")
        if self.constants.hummingbot.SYNCHRONIZE:
            synchro = self._time_synchronizer
            try:
                await synchro.update_server_time_offset_with_time_provider(
                    time_provider=self.metanode.timing["blocktime"]
                )
            except asyncio.CancelledError:
                msg = f"asyncio.CancelledError {__name__}"
                self.logger().exception(msg)
            except Exception:
                self.logger().exception("Error requesting server time")
                raise
