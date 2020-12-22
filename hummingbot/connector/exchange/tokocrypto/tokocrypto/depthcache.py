# coding=utf-8

from operator import itemgetter
import time

from .websockets import BinanceSocketManager


class DepthCache(object):

    def __init__(self, symbol):
        """Initialise the DepthCache

        :param symbol: Symbol to create depth cache for
        :type symbol: string

        """
        self.symbol = symbol
        self._bids = {}
        self._asks = {}
        self.update_time = None

    def add_bid(self, bid):
        """Add a bid to the cache

        :param bid:
        :return:

        """
        self._bids[bid[0]] = float(bid[1])
        if bid[1] == "0.00000000":
            del self._bids[bid[0]]

    def add_ask(self, ask):
        """Add an ask to the cache

        :param ask:
        :return:

        """
        self._asks[ask[0]] = float(ask[1])
        if ask[1] == "0.00000000":
            del self._asks[ask[0]]

    def get_bids(self):
        """Get the current bids

        :return: list of bids with price and quantity as floats

        .. code-block:: python

            [
                [
                    0.0001946,  # Price
                    45.0        # Quantity
                ],
                [
                    0.00019459,
                    2384.0
                ],
                [
                    0.00019158,
                    5219.0
                ],
                [
                    0.00019157,
                    1180.0
                ],
                [
                    0.00019082,
                    287.0
                ]
            ]

        """
        return DepthCache.sort_depth(self._bids, reverse=True)

    def get_asks(self):
        """Get the current asks

        :return: list of asks with price and quantity as floats

        .. code-block:: python

            [
                [
                    0.0001955,  # Price
                    57.0'       # Quantity
                ],
                [
                    0.00019699,
                    778.0
                ],
                [
                    0.000197,
                    64.0
                ],
                [
                    0.00019709,
                    1130.0
                ],
                [
                    0.0001971,
                    385.0
                ]
            ]

        """
        return DepthCache.sort_depth(self._asks, reverse=False)

    @staticmethod
    def sort_depth(vals, reverse=False):
        """Sort bids or asks by price
        """
        lst = [[float(price), quantity] for price, quantity in vals.items()]
        lst = sorted(lst, key=itemgetter(0), reverse=reverse)
        return lst


class DepthCacheManager(object):

    _default_refresh = 60 * 30  # 30 minutes

    def __init__(self, client, symbol, callback=None, refresh_interval=_default_refresh, bm=None, limit=500):
        """Initialise the DepthCacheManager

        :param client: Binance API client
        :type client: binance.Client
        :param symbol: Symbol to create depth cache for
        :type symbol: string
        :param callback: Optional function to receive depth cache updates
        :type callback: function
        :param refresh_interval: Optional number of seconds between cache refresh, use 0 or None to disable
        :type refresh_interval: int
        :param limit: Optional number of orders to get from orderbook
        :type limit: int

        """
        self._client = client
        self._symbol = symbol
        self._limit = limit
        self._callback = callback
        self._last_update_id = None
        self._depth_message_buffer = []
        self._bm = bm
        self._depth_cache = DepthCache(self._symbol)
        self._refresh_interval = refresh_interval
        self._conn_key = None

        self._start_socket()
        self._init_cache()

    def _init_cache(self):
        """Initialise the depth cache calling REST endpoint

        :return:
        """
        self._last_update_id = None
        self._depth_message_buffer = []

        res = self._client.get_order_book(symbol=self._symbol, limit=self._limit)

        # process bid and asks from the order book
        for bid in res['bids']:
            self._depth_cache.add_bid(bid)
        for ask in res['asks']:
            self._depth_cache.add_ask(ask)

        # set first update id
        self._last_update_id = res['lastUpdateId']

        # set a time to refresh the depth cache
        if self._refresh_interval:
            self._refresh_time = int(time.time()) + self._refresh_interval

        # Apply any updates from the websocket
        for msg in self._depth_message_buffer:
            self._process_depth_message(msg, buffer=True)

        # clear the depth buffer
        self._depth_message_buffer = []

    def _start_socket(self):
        """Start the depth cache socket

        :return:
        """
        if self._bm is None:
            self._bm = BinanceSocketManager(self._client)

        self._conn_key = self._bm.start_depth_socket(self._symbol, self._depth_event)
        if not self._bm.is_alive():
            self._bm.start()

        # wait for some socket responses
        while not len(self._depth_message_buffer):
            time.sleep(1)

    def _depth_event(self, msg):
        """Handle a depth event

        :param msg:
        :return:

        """

        if 'e' in msg and msg['e'] == 'error':
            # close the socket
            self.close()

            # notify the user by returning a None value
            if self._callback:
                self._callback(None)

        if self._last_update_id is None:
            # Initial depth snapshot fetch not yet performed, buffer messages
            self._depth_message_buffer.append(msg)
        else:
            self._process_depth_message(msg)

    def _process_depth_message(self, msg, buffer=False):
        """Process a depth event message.

        :param msg: Depth event message.
        :return:

        """

        if buffer and msg['u'] <= self._last_update_id:
            # ignore any updates before the initial update id
            return
        elif msg['U'] != self._last_update_id + 1:
            # if not buffered check we get sequential updates
            # otherwise init cache again
            self._init_cache()

        # add any bid or ask values
        for bid in msg['b']:
            self._depth_cache.add_bid(bid)
        for ask in msg['a']:
            self._depth_cache.add_ask(ask)

        # keeping update time
        self._depth_cache.update_time = msg['E']

        # call the callback with the updated depth cache
        if self._callback:
            self._callback(self._depth_cache)

        self._last_update_id = msg['u']

        # after processing event see if we need to refresh the depth cache
        if self._refresh_interval and int(time.time()) > self._refresh_time:
            self._init_cache()

    def get_depth_cache(self):
        """Get the current depth cache

        :return: DepthCache object

        """
        return self._depth_cache

    def close(self, close_socket=False):
        """Close the open socket for this manager

        :return:
        """
        self._bm.stop_socket(self._conn_key)
        if close_socket:
            self._bm.close()
        time.sleep(1)
        self._depth_cache = None
