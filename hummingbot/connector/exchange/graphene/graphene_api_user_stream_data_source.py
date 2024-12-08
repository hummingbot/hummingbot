# DISABLE SELECT PYLINT TESTS
# pylint: disable=bad-continuation, no-member, no-name-in-module, too-many-function-args
# pylint: disable=too-many-branches, broad-except, too-many-locals
# pylint: disable=too-many-nested-blocks, too-many-statements
"""
 ╔════════════════════════════════════════════════════╗
 ║ ╔═╗╦═╗╔═╗╔═╗╦ ╦╔═╗╔╗╔╔═╗  ╔╦╗╔═╗╔╦╗╔═╗╔╗╔╔═╗╔╦╗╔═╗ ║
 ║ ║ ╦╠╦╝╠═╣╠═╝╠═╣║╣ ║║║║╣   ║║║║╣  ║ ╠═╣║║║║ ║ ║║║╣  ║
 ║ ╚═╝╩╚═╩ ╩╩  ╩ ╩╚═╝╝╚╝╚═╝  ╩ ╩╚═╝ ╩ ╩ ╩╝╚╝╚═╝═╩╝╚═╝ ║
 ║    DECENTRALIZED EXCHANGE HUMMINGBOT CONNECTOR     ║
 ╚════════════════════════════════════════════════════╝
~
forked from  binance_api_user_stream_data_source v1.0.0
~
"""
# STANDARD MODULES
import asyncio
import logging
import time
from typing import Optional

# METANODE MODULES
from metanode.graphene_metanode_client import GrapheneTrustlessClient

# HUMMINGBOT MODULES
from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.exchange.graphene.graphene_constants import GrapheneConstants
from hummingbot.core.data_type.in_flight_order import OrderState
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.event.events import TradeType
from hummingbot.logger import HummingbotLogger

# GLOBAL CONSTANTS
DEV = False


class GrapheneAPIUserStreamDataSource(UserStreamTrackerDataSource):
    """
    connect to metanode to get open order updates
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        # auth: GrapheneAuth,
        domain: str,
        order_tracker: ClientOrderTracker,
    ):
        # print("GrapheneAPIUserStreamDataSource")
        super().__init__()
        self._current_listen_key = None
        self._last_recv_time: float = 0
        self._order_tracker = order_tracker
        self._ws_assistant = None
        self.domain = domain
        self.constants = GrapheneConstants(domain)
        self.metanode = GrapheneTrustlessClient(self.constants)

    @classmethod
    def logger(cls) -> HummingbotLogger:
        """
        a classmethod for logging
        """
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def dev_log(self, *args, **kwargs):
        """
        log only in dev mode
        """
        if DEV:
            self.logger().info(*args, **kwargs)

    @property
    def last_recv_time(self) -> float:
        """
        Returns the time of the last received message
        :return: the timestamp of the last received message in seconds
        """
        # print("GrapheneAPIUserStreamDataSource last_recv_time")
        if self._ws_assistant:
            return self._ws_assistant.last_recv_time
        return -1

    async def listen_for_user_stream(
        self, output: asyncio.Queue
    ):
        """
        Connects to the user private channel in the DEX
        With the established connection listens to all balance events
        and order updates provided by the DEX,
        and stores them in the output queue
        """

        def get_latest_events():

            metanode_pairs = self.metanode.pairs  # DISCRETE SQL QUERY
            metanode_account = self.metanode.account  # DISCRETE SQL QUERY
            events = {}
            for pair in self.constants.chain.PAIRS:
                events[pair] = {
                    "fills": list(metanode_pairs[pair]["fills"]),
                    "opens": list(metanode_pairs[pair]["opens"]),
                    "creates": list(metanode_pairs[pair]["ops"]["creates"]),
                    "cancels": list(metanode_account["cancels"]),
                }
            # self.dev_log(events)
            return events

        # print("GrapheneAPIUserStreamDataSource listen_for_user_stream")
        # wait for metanode to intialize
        while not 0 < time.time() - self.metanode.timing["blocktime"] < 60:
            await self.sleep(1)
            continue  # SQL QUERY WHILE LOOP
        # tare the scale upon initialization
        novel = {}
        latest = {}
        removed = {}
        previous = {}
        events = get_latest_events()
        for pair in self.constants.chain.PAIRS:
            novel[pair] = {}
            latest[pair] = {}
            removed[pair] = {}
            previous[pair] = {}
            for event in list(events[pair].keys()):
                previous[pair][event] = events[pair][event]

        while True:
            try:
                # create a 3 dimensional dataset; scope * pairs * events
                # we may not need all of it, but it allows for future logic
                events = get_latest_events()
                tracked_orders = self._order_tracker.all_orders
                self.dev_log(tracked_orders)

                for pair in self.constants.chain.PAIRS:
                    for event in list(events[pair].keys()):
                        # get the latest filled, opened, created, and cancelled  orders
                        latest[pair][event] = events[pair][event]
                        # sort out the novel and removed orders updates
                        novel[pair][event] = [
                            f
                            for f in latest[pair][event]
                            if f not in previous[pair][event]
                        ]
                        removed[pair][event] = [
                            f
                            for f in previous[pair][event]
                            if f not in latest[pair][event]
                        ]
                        # reset previous state to current state
                        previous[pair][event] = list(latest[pair][event])
                # process novel user stream order data for this pair
                for pair in self.constants.chain.PAIRS:
                    # handle recent partial
                    for fill_order in novel[pair]["fills"]:

                        if fill_order["exchange_order_id"] in [
                            tracked_order.exchange_order_id for tracked_order in tracked_orders.values()
                        ]:
                            self.dev_log("FILLS" + str(fill_order))
                            new_state = (
                                OrderState.PARTIALLY_FILLED
                                if fill_order in latest[pair]["opens"]
                                else OrderState.FILLED
                            )
                            event_msg = {
                                "trading_pair": pair,
                                "execution_type": "TRADE",
                                "client_order_id": self._order_tracker.swap_id(
                                    exchange_order_id=str(fill_order["exchange_order_id"])
                                ),
                                "exchange_order_id": fill_order["exchange_order_id"],
                                # rpc database get_trade_history
                                #
                                # {'sequence': 183490,
                                # 'date': '2022-01-21T20:41:36',
                                # 'price': '0.025376407606742865',
                                # 'amount': '414.76319',
                                # 'value': '10.5252',
                                # 'type': 'sell',
                                # 'side1_account_id':'1.2.1624289',
                                # 'side2_account_id': '1.2.883283'}
                                # rpc history get_fill_order_history
                                #
                                # {"id": "0.0.69",
                                # "key": {
                                # "base": "1.3.0",
                                # "quote": "1.3.8",
                                # "sequence": -5
                                # },
                                # "time.time": "2021-12-22T23:09:42",
                                # "op": {
                                # "fee": {
                                # "amount": 0,
                                # "asset_id": "1.3.8"
                                # },
                                # "order_id": "1.7.181",
                                # "account_id": "1.2.207",
                                # "pays": {
                                # "amount": 100000,
                                # "asset_id": "1.3.0"
                                # },
                                # "receives": {
                                # "amount": 60000000,
                                # "asset_id": "1.3.8"
                                # }}}
                                # fill_key_sequence = history_sequence ?
                                # else:
                                # trade_id = sha256(
                                # + oldest_asset
                                # + newest_asset
                                # + oldest_account
                                # + newest_account
                                # + price
                                # + amount*value
                                # + amount+value
                                # + unix
                                # )
                                "trade_id": str(time.time()),  # needs to match OrderBookMessage
                                "fee_asset": fill_order["fee"]["asset"],
                                "fee_paid": fill_order["fee"]["amount"],
                                "fill_price": fill_order["price"],
                                "update_timestamp": fill_order["unix"],
                                "fill_base_amount": fill_order["amount"],
                                "is_maker": fill_order["is_maker"],
                                "order_side": TradeType.BUY if fill_order["type"].upper() == "BUY" else TradeType.SELL,
                                "new_state": new_state,
                            }
                            output.put_nowait(event_msg)

                    # handle recent cancellations
                    for cancel_order in novel[pair]["cancels"]:

                        self.dev_log("CANCELS " + str(tracked_orders))
                        if cancel_order["order_id"] in [
                            v.exchange_order_id for k, v in tracked_orders.items()
                        ]:
                            event_msg = {
                                "trading_pair": pair,
                                "execution_type": None,
                                "client_order_id": self._order_tracker.swap_id(
                                    exchange_order_id=str(cancel_order["order_id"])
                                ),
                                "exchange_order_id": str(cancel_order["order_id"]),
                                "trade_id": str(time.time()),
                                "update_timestamp": int(time.time()),
                                "new_state": OrderState.CANCELED,
                            }
                            output.put_nowait(event_msg)
                            self.dev_log("CANCELS EVENT" + str(event_msg))
                    self.dev_log("NOVEL" + str(pair) + str(novel))
                    await self._sleep(1)

            except asyncio.CancelledError:
                msg = f"asyncio.CancelledError {__name__}"
                self.logger().exception(msg)
                raise

            except Exception:
                self.logger().exception(
                    "Unexpected error while listening to user stream. "
                    "Retrying after 5 seconds..."
                )
                await self._sleep(5)
