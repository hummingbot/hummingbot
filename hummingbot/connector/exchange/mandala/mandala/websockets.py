# coding=utf-8

import json
import threading

from autobahn.twisted.websocket import WebSocketClientFactory, \
    WebSocketClientProtocol, \
    connectWS
from twisted.internet import reactor, ssl
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.internet.error import ReactorAlreadyRunning

from mandala.client import Client


class MandalaClientProtocol(WebSocketClientProtocol):

    def __init__(self):
        super(WebSocketClientProtocol, self).__init__()

    def onConnect(self, response):
        # reset the delay after reconnecting
        self.factory.resetDelay()

    def onMessage(self, payload, isBinary):
        if not isBinary:
            try:
                payload_obj = json.loads(payload.decode('utf8'))
            except ValueError:
                pass
            else:
                self.factory.callback(payload_obj)


class MandalaReconnectingClientFactory(ReconnectingClientFactory):

    # set initial delay to a short time
    initialDelay = 0.1

    maxDelay = 10

    maxRetries = 5


class MandalaClientFactory(WebSocketClientFactory, MandalaReconnectingClientFactory):

    protocol = MandalaClientProtocol
    _reconnect_error_payload = {
        'e': 'error',
        'm': 'Max reconnect retries reached'
    }

    def clientConnectionFailed(self, connector, reason):
        self.retry(connector)
        if self.retries > self.maxRetries:
            self.callback(self._reconnect_error_payload)

    def clientConnectionLost(self, connector, reason):
        self.retry(connector)
        if self.retries > self.maxRetries:
            self.callback(self._reconnect_error_payload)


class MandalaSocketManager(threading.Thread):

    STREAM_URL = 'wss://stream.binance.cc:9443/'
    FSTREAM_URL = 'wss://fstream.binance.cc/'

    WEBSOCKET_DEPTH_5 = '5'
    WEBSOCKET_DEPTH_10 = '10'
    WEBSOCKET_DEPTH_20 = '20'

    DEFAULT_USER_TIMEOUT = 30 * 60  # 30 minutes

    def __init__(self, client, user_timeout=DEFAULT_USER_TIMEOUT):
        """Initialise the MandalaSocketManager

        :param client: Mandala API client
        :type client: binance.Client
        :param user_timeout: Custom websocket timeout
        :type user_timeout: int

        """
        threading.Thread.__init__(self)
        self._conns = {}
        self._client = client
        self._user_timeout = user_timeout
        self._timers = {'user': None, 'margin': None}
        self._listen_keys = {'user': None, 'margin': None}
        self._account_callbacks = {'user': None, 'margin': None}

    def _start_socket(self, path, callback, prefix='ws/'):
        if path in self._conns:
            return False

        factory_url = self.STREAM_URL + prefix + path
        factory = MandalaClientFactory(factory_url)
        factory.protocol = MandalaClientProtocol
        factory.callback = callback
        factory.reconnect = True
        context_factory = ssl.ClientContextFactory()

        self._conns[path] = connectWS(factory, context_factory)
        return path

    def _start_futures_socket(self, path, callback, prefix='stream?streams='):
        if path in self._conns:
            return False

        factory_url = self.FSTREAM_URL + prefix + path
        factory = MandalaClientFactory(factory_url)
        factory.protocol = MandalaClientProtocol
        factory.callback = callback
        factory.reconnect = True
        context_factory = ssl.ClientContextFactory()

        self._conns[path] = connectWS(factory, context_factory)
        return path

    def start_depth_socket(self, symbol, callback, depth=None):
        """Start a websocket for symbol market depth returning either a diff or a partial book

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/web-socket-streams.md#partial-book-depth-streams

        :param symbol: required
        :type symbol: str
        :param callback: callback function to handle messages
        :type callback: function
        :param depth: optional Number of depth entries to return, default None. If passed returns a partial book instead of a diff
        :type depth: str

        :returns: connection key string if successful, False otherwise

        Partial Message Format

        .. code-block:: python

            {
                "lastUpdateId": 160,  # Last update ID
                "bids": [             # Bids to be updated
                    [
                        "0.0024",     # price level to be updated
                        "10",         # quantity
                        []            # ignore
                    ]
                ],
                "asks": [             # Asks to be updated
                    [
                        "0.0026",     # price level to be updated
                        "100",        # quantity
                        []            # ignore
                    ]
                ]
            }


        Diff Message Format

        .. code-block:: python

            {
                "e": "depthUpdate", # Event type
                "E": 123456789,     # Event time
                "s": "BNBBTC",      # Symbol
                "U": 157,           # First update ID in event
                "u": 160,           # Final update ID in event
                "b": [              # Bids to be updated
                    [
                        "0.0024",   # price level to be updated
                        "10",       # quantity
                        []          # ignore
                    ]
                ],
                "a": [              # Asks to be updated
                    [
                        "0.0026",   # price level to be updated
                        "100",      # quantity
                        []          # ignore
                    ]
                ]
            }

        """
        socket_name = symbol.lower() + '@depth'
        if depth and depth != '1':
            socket_name = '{}{}'.format(socket_name, depth)
        return self._start_socket(socket_name, callback)

    def start_kline_socket(self, symbol, callback, interval=Client.KLINE_INTERVAL_1MINUTE):
        """Start a websocket for symbol kline data

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/web-socket-streams.md#klinecandlestick-streams

        :param symbol: required
        :type symbol: str
        :param callback: callback function to handle messages
        :type callback: function
        :param interval: Kline interval, default KLINE_INTERVAL_1MINUTE
        :type interval: str

        :returns: connection key string if successful, False otherwise

        Message Format

        .. code-block:: python

            {
                "e": "kline",					# event type
                "E": 1499404907056,				# event time
                "s": "ETHBTC",					# symbol
                "k": {
                    "t": 1499404860000, 		# start time of this bar
                    "T": 1499404919999, 		# end time of this bar
                    "s": "ETHBTC",				# symbol
                    "i": "1m",					# interval
                    "f": 77462,					# first trade id
                    "L": 77465,					# last trade id
                    "o": "0.10278577",			# open
                    "c": "0.10278645",			# close
                    "h": "0.10278712",			# high
                    "l": "0.10278518",			# low
                    "v": "17.47929838",			# volume
                    "n": 4,						# number of trades
                    "x": false,					# whether this bar is final
                    "q": "1.79662878",			# quote volume
                    "V": "2.34879839",			# volume of active buy
                    "Q": "0.24142166",			# quote volume of active buy
                    "B": "13279784.01349473"	# can be ignored
                    }
            }
        """
        socket_name = '{}@kline_{}'.format(symbol.lower(), interval)
        return self._start_socket(socket_name, callback)

    def start_miniticker_socket(self, callback, update_time=1000):
        """Start a miniticker websocket for all trades

        This is not in the official Mandala api docs, but this is what
        feeds the right column on a ticker page on Mandala.

        :param callback: callback function to handle messages
        :type callback: function
        :param update_time: time between callbacks in milliseconds, must be 1000 or greater
        :type update_time: int

        :returns: connection key string if successful, False otherwise

        Message Format

        .. code-block:: python

            [
                {
                    'e': '24hrMiniTicker',  # Event type
                    'E': 1515906156273,     # Event time
                    's': 'QTUMETH',         # Symbol
                    'c': '0.03836900',      # close
                    'o': '0.03953500',      # open
                    'h': '0.04400000',      # high
                    'l': '0.03756000',      # low
                    'v': '147435.80000000', # volume
                    'q': '5903.84338533'    # quote volume
                }
            ]
        """
        return self._start_socket('!miniTicker@arr@{}ms'.format(update_time), callback)

    def start_trade_socket(self, symbol, callback):
        """Start a websocket for symbol trade data

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/web-socket-streams.md#trade-streams

        :param symbol: required
        :type symbol: str
        :param callback: callback function to handle messages
        :type callback: function

        :returns: connection key string if successful, False otherwise

        Message Format

        .. code-block:: python

            {
                "e": "trade",     # Event type
                "E": 123456789,   # Event time
                "s": "BNBBTC",    # Symbol
                "t": 12345,       # Trade ID
                "p": "0.001",     # Price
                "q": "100",       # Quantity
                "b": 88,          # Buyer order Id
                "a": 50,          # Seller order Id
                "T": 123456785,   # Trade time
                "m": true,        # Is the buyer the market maker?
                "M": true         # Ignore.
            }

        """
        return self._start_socket(symbol.lower() + '@trade', callback)

    def start_aggtrade_socket(self, symbol, callback):
        """Start a websocket for symbol trade data

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/web-socket-streams.md#aggregate-trade-streams

        :param symbol: required
        :type symbol: str
        :param callback: callback function to handle messages
        :type callback: function

        :returns: connection key string if successful, False otherwise

        Message Format

        .. code-block:: python

            {
                "e": "aggTrade",		# event type
                "E": 1499405254326,		# event time
                "s": "ETHBTC",			# symbol
                "a": 70232,				# aggregated tradeid
                "p": "0.10281118",		# price
                "q": "8.15632997",		# quantity
                "f": 77489,				# first breakdown trade id
                "l": 77489,				# last breakdown trade id
                "T": 1499405254324,		# trade time
                "m": false,				# whether buyer is a maker
                "M": true				# can be ignored
            }

        """
        return self._start_socket(symbol.lower() + '@aggTrade', callback)

    def start_symbol_ticker_socket(self, symbol, callback):
        """Start a websocket for a symbol's ticker data

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/web-socket-streams.md#individual-symbol-ticker-streams

        :param symbol: required
        :type symbol: str
        :param callback: callback function to handle messages
        :type callback: function

        :returns: connection key string if successful, False otherwise

        Message Format

        .. code-block:: python

            {
                "e": "24hrTicker",  # Event type
                "E": 123456789,     # Event time
                "s": "BNBBTC",      # Symbol
                "p": "0.0015",      # Price change
                "P": "250.00",      # Price change percent
                "w": "0.0018",      # Weighted average price
                "x": "0.0009",      # Previous day's close price
                "c": "0.0025",      # Current day's close price
                "Q": "10",          # Close trade's quantity
                "b": "0.0024",      # Best bid price
                "B": "10",          # Bid bid quantity
                "a": "0.0026",      # Best ask price
                "A": "100",         # Best ask quantity
                "o": "0.0010",      # Open price
                "h": "0.0025",      # High price
                "l": "0.0010",      # Low price
                "v": "10000",       # Total traded base asset volume
                "q": "18",          # Total traded quote asset volume
                "O": 0,             # Statistics open time
                "C": 86400000,      # Statistics close time
                "F": 0,             # First trade ID
                "L": 18150,         # Last trade Id
                "n": 18151          # Total number of trades
            }

        """
        return self._start_socket(symbol.lower() + '@ticker', callback)

    def start_ticker_socket(self, callback):
        """Start a websocket for all ticker data

        By default all markets are included in an array.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/web-socket-streams.md#all-market-tickers-stream

        :param callback: callback function to handle messages
        :type callback: function

        :returns: connection key string if successful, False otherwise

        Message Format

        .. code-block:: python

            [
                {
                    'F': 278610,
                    'o': '0.07393000',
                    's': 'BCCBTC',
                    'C': 1509622420916,
                    'b': '0.07800800',
                    'l': '0.07160300',
                    'h': '0.08199900',
                    'L': 287722,
                    'P': '6.694',
                    'Q': '0.10000000',
                    'q': '1202.67106335',
                    'p': '0.00494900',
                    'O': 1509536020916,
                    'a': '0.07887800',
                    'n': 9113,
                    'B': '1.00000000',
                    'c': '0.07887900',
                    'x': '0.07399600',
                    'w': '0.07639068',
                    'A': '2.41900000',
                    'v': '15743.68900000'
                }
            ]
        """
        return self._start_socket('!ticker@arr', callback)

    def start_symbol_mark_price_socket(self, symbol, callback, fast=True):
        """Start a websocket for a symbol's futures mark price
        https://binance-docs.github.io/apidocs/futures/en/#mark-price-stream
        :param symbol: required
        :type symbol: str
        :param callback: callback function to handle messages
        :type callback: function
        :returns: connection key string if successful, False otherwise
        Message Format
        .. code-block:: python
            {
                "e": "markPriceUpdate",  // Event type
                "E": 1562305380000,      // Event time
                "s": "BTCUSDT",          // Symbol
                "p": "11185.87786614",   // Mark price
                "r": "0.00030000",       // Funding rate
                "T": 1562306400000       // Next funding time
            }
        """
        stream_name = '@markPrice@1s' if fast else '@markPrice'
        return self._start_futures_socket(symbol.lower() + stream_name, callback)

    def start_all_mark_price_socket(self, callback, fast=True):
        """Start a websocket for all futures mark price data
        By default all symbols are included in an array.
        https://binance-docs.github.io/apidocs/futures/en/#mark-price-stream-for-all-market
        :param callback: callback function to handle messages
        :type callback: function
        :returns: connection key string if successful, False otherwise
        Message Format
        .. code-block:: python

            [
                {
                    "e": "markPriceUpdate",  // Event type
                    "E": 1562305380000,      // Event time
                    "s": "BTCUSDT",          // Symbol
                    "p": "11185.87786614",   // Mark price
                    "r": "0.00030000",       // Funding rate
                    "T": 1562306400000       // Next funding time
                }
            ]
        """
        stream_name = '!markPrice@arr@1s' if fast else '!markPrice@arr'
        return self._start_futures_socket(stream_name, callback)

    def start_symbol_ticker_futures_socket(self, symbol, callback):
        """Start a websocket for a symbol's ticker data
        By default all markets are included in an array.
        https://binance-docs.github.io/apidocs/futures/en/#individual-symbol-book-ticker-streams
        :param symbol: required
        :type symbol: str
        :param callback: callback function to handle messages
        :type callback: function
        :returns: connection key string if successful, False otherwise
        .. code-block:: python
            [
                {
                  "u":400900217,     // order book updateId
                  "s":"BNBUSDT",     // symbol
                  "b":"25.35190000", // best bid price
                  "B":"31.21000000", // best bid qty
                  "a":"25.36520000", // best ask price
                  "A":"40.66000000"  // best ask qty
                }
            ]
        """
        return self._start_futures_socket(symbol.lower() + '@bookTicker', callback)

    def start_all_ticker_futures_socket(self, callback):
        """Start a websocket for all ticker data
        By default all markets are included in an array.
        https://binance-docs.github.io/apidocs/futures/en/#all-book-tickers-stream
        :param callback: callback function to handle messages
        :type callback: function
        :returns: connection key string if successful, False otherwise
        Message Format
        .. code-block:: python
            [
                {
                  "u":400900217,     // order book updateId
                  "s":"BNBUSDT",     // symbol
                  "b":"25.35190000", // best bid price
                  "B":"31.21000000", // best bid qty
                  "a":"25.36520000", // best ask price
                  "A":"40.66000000"  // best ask qty
                }
            ]
        """
        return self._start_futures_socket('!bookTicker', callback)

    def start_symbol_book_ticker_socket(self, symbol, callback):
        """Start a websocket for the best bid or ask's price or quantity for a specified symbol.
        https://github.com/binance-exchange/binance-official-api-docs/blob/master/web-socket-streams.md#individual-symbol-book-ticker-streams

        :param symbol: required
        :type symbol: str
        :param callback: callback function to handle messages
        :type callback: function

        :returns: connection key string if successful, False otherwise

        Message Format

        .. code-block:: python

            {
                "u":400900217,     // order book updateId
                "s":"BNBUSDT",     // symbol
                "b":"25.35190000", // best bid price
                "B":"31.21000000", // best bid qty
                "a":"25.36520000", // best ask price
                "A":"40.66000000"  // best ask qty
            }

        """
        return self._start_socket(symbol.lower() + '@bookTicker', callback)

    def start_book_ticker_socket(self, callback):
        """Start a websocket for the best bid or ask's price or quantity for all symbols.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/web-socket-streams.md#all-book-tickers-stream

        :param callback: callback function to handle messages
        :type callback: function

        :returns: connection key string if successful, False otherwise

        Message Format

        .. code-block:: python

            {
                // Same as <symbol>@bookTicker payload
            }

        """
        return self._start_socket('!bookTicker', callback)

    def start_multiplex_socket(self, streams, callback):
        """Start a multiplexed socket using a list of socket names.
        User stream sockets can not be included.

        Symbols in socket name must be lowercase i.e bnbbtc@aggTrade, neobtc@ticker

        Combined stream events are wrapped as follows: {"stream":"<streamName>","data":<rawPayload>}

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/web-socket-streams.md

        :param streams: list of stream names in lower case
        :type streams: list
        :param callback: callback function to handle messages
        :type callback: function

        :returns: connection key string if successful, False otherwise

        Message Format - see Mandala API docs for all types

        """
        stream_path = 'streams={}'.format('/'.join(streams))
        return self._start_socket(stream_path, callback, 'stream?')

    def start_user_socket(self, callback):
        """Start a websocket for user data

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/user-data-stream.md

        :param callback: callback function to handle messages
        :type callback: function

        :returns: connection key string if successful, False otherwise

        Message Format - see Mandala API docs for all types
        """
        # Get the user listen key
        user_listen_key = self._client.stream_get_listen_key()
        # and start the socket with this specific key
        return self._start_account_socket('user', user_listen_key, callback)

    def start_margin_socket(self, callback):
        """Start a websocket for margin data

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/user-data-stream.md

        :param callback: callback function to handle messages
        :type callback: function

        :returns: connection key string if successful, False otherwise

        Message Format - see Mandala API docs for all types
        """
        # Get the user margin listen key
        margin_listen_key = self._client.margin_stream_get_listen_key()
        # and start the socket with this specific key
        return self._start_account_socket('margin', margin_listen_key, callback)

    def _start_account_socket(self, socket_type, listen_key, callback):
        """Starts one of user or margin socket"""
        self._check_account_socket_open(listen_key)
        self._listen_keys[socket_type] = listen_key
        self._account_callbacks[socket_type] = callback
        conn_key = self._start_socket(listen_key, callback)
        if conn_key:
            # start timer to keep socket alive
            self._start_socket_timer(socket_type)
        return conn_key

    def _check_account_socket_open(self, listen_key):
        if not listen_key:
            return
        for conn_key in self._conns:
            if len(conn_key) >= 60 and conn_key[:60] == listen_key:
                self.stop_socket(conn_key)
                break

    def _start_socket_timer(self, socket_type):
        callback = self._keepalive_account_socket

        self._timers[socket_type] = threading.Timer(self._user_timeout, callback, [socket_type])
        self._timers[socket_type].setDaemon(True)
        self._timers[socket_type].start()

    def _keepalive_account_socket(self, socket_type):
        if socket_type == 'user':
            listen_key_func = self._client.stream_get_listen_key
            callback = self._account_callbacks[socket_type]
        else:
            listen_key_func = self._client.margin_stream_get_listen_key
            callback = self._account_callbacks[socket_type]
        listen_key = listen_key_func()
        if listen_key != self._listen_keys[socket_type]:
            self._start_account_socket(socket_type, listen_key, callback)

    def stop_socket(self, conn_key):
        """Stop a websocket given the connection key

        :param conn_key: Socket connection key
        :type conn_key: string

        :returns: connection key string if successful, False otherwise
        """
        if conn_key not in self._conns:
            return

        # disable reconnecting if we are closing
        self._conns[conn_key].factory = WebSocketClientFactory(self.STREAM_URL + 'tmp_path')
        self._conns[conn_key].disconnect()
        del(self._conns[conn_key])

        # check if we have a user stream socket
        if len(conn_key) >= 60 and conn_key[:60] == self._listen_keys['user']:
            self._stop_account_socket('user')

        # or a margin stream socket
        if len(conn_key) >= 60 and conn_key[:60] == self._listen_keys['margin']:
            self._stop_account_socket('margin')

    def _stop_account_socket(self, socket_type):
        if not self._listen_keys[socket_type]:
            return
        if self._timers[socket_type]:
            self._timers[socket_type].cancel()
            self._timers[socket_type] = None
        self._listen_keys[socket_type] = None

    def run(self):
        try:
            reactor.run(installSignalHandlers=False)
        except ReactorAlreadyRunning:
            # Ignore error about reactor already running
            pass

    def close(self):
        """Close all connections

        """
        keys = set(self._conns.keys())
        for key in keys:
            self.stop_socket(key)

        self._conns = {}
