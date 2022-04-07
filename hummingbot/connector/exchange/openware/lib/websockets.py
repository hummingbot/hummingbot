# coding=utf-8

import hashlib
import hmac
import time
import json
import threading

from autobahn.twisted.websocket import WebSocketClientFactory, \
    WebSocketClientProtocol, \
    connectWS
from twisted.internet import reactor, ssl
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.internet.error import ReactorAlreadyRunning

from hummingbot.market.openware.lib.client import Client

from hummingbot.openware_settings import API_SECRET, API_KEY


class OpenwareClientProtocol(WebSocketClientProtocol):

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


class OpenwareReconnectingClientFactory(ReconnectingClientFactory):

    # set initial delay to a short time
    initialDelay = 0.1

    maxDelay = 10

    maxRetries = 5


class OpenwareClientFactory(WebSocketClientFactory, OpenwareReconnectingClientFactory):

    protocol = OpenwareClientProtocol
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


class OpenwareSocketManager(threading.Thread):

    WEBSOCKET_DEPTH_5 = '5'
    WEBSOCKET_DEPTH_10 = '10'
    WEBSOCKET_DEPTH_20 = '20'

    _user_timeout = 30 * 60  # 30 minutes

    def __init__(self, client):
        threading.Thread.__init__(self)
        self._conns = {}
        self._user_timer = None
        self._user_callback = None
        self._client = client
        timestamp = str(time.time() * 1000)
        signature = self._generate_signature(timestamp)
        self._header = {
            'X-Auth-Apikey': API_KEY,
            'X-Auth-Nonce': timestamp,
            'X-Auth-Signature': signature
        }

    def _generate_signature(self, timestamp):
        query_string = "%s%s" % (timestamp, API_KEY)
        m = hmac.new(API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256)
        return m.hexdigest()

    def _start_socket(self, factory_url, path, auth, callback):
        if path in self._conns:
            return False

        factory = OpenwareClientFactory(factory_url)
        factory.protocol = OpenwareClientProtocol
        factory.callback = callback
        factory.reconnect = True
        context_factory = ssl.ClientContextFactory()

        self._conns[path] = connectWS(factory, context_factory)
        return path

    def start_kline_socket(self, market, callback, interval=Client.KLINE_INTERVAL_1MINUTE):
        socket_name = '{}.kline_{}'.format(market.lower(), interval)
        return self._start_socket(socket_name, False, callback)

    def start_trade_socket(self, market, callback):
        return self._start_socket(market.lower() + '.trades', False, callback)
    
    def start_orderbook_socket(self, market, callback):
        return self._start_socket(market.lower() + '.update', False, callback)
    
    def start_ticker_socket(self, callback):
        return self._start_socket('global.tickers', callback)

    def start_multiplex_socket(self, streams, callback):
        stream_path = 'streams={}'.format('/'.join(streams))
        return self._start_socket(stream_path, callback, False, 'stream?')

    def start_user_trade_socket(self, callback):
        return self._start_socket('trade', True, callback)
    
    def start_user_order_socket(self, callback):
        return self._start_socket('order', True, callback)

    def stop_socket(self, conn_key):
        if conn_key not in self._conns:
            return

        # disable reconnecting if we are closing
        self._conns[conn_key].factory = WebSocketClientFactory(self.STREAM_URL + 'tmp_path')
        self._conns[conn_key].disconnect()
        del(self._conns[conn_key])

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
