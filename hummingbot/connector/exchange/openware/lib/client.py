# coding=utf-8

import hashlib
import hmac
import requests
import time
import urllib
from operator import itemgetter
from hummingbot.market.openware.lib.helpers import date_to_milliseconds, interval_to_milliseconds
from hummingbot.market.openware.lib.exceptions import OpenwareAPIException, OpenwareRequestException, OpenwareWithdrawException


class Client(object):

    ORDER_STATUS_NEW = 'NEW'
    ORDER_STATUS_PARTIALLY_FILLED = 'PARTIALLY_FILLED'
    ORDER_STATUS_FILLED = 'FILLED'
    ORDER_STATUS_CANCELED = 'CANCELED'
    ORDER_STATUS_PENDING_CANCEL = 'PENDING_CANCEL'
    ORDER_STATUS_REJECTED = 'REJECTED'
    ORDER_STATUS_EXPIRED = 'EXPIRED'

    KLINE_INTERVAL_1MINUTE = '1m'
    KLINE_INTERVAL_3MINUTE = '3m'
    KLINE_INTERVAL_5MINUTE = '5m'
    KLINE_INTERVAL_15MINUTE = '15m'
    KLINE_INTERVAL_30MINUTE = '30m'
    KLINE_INTERVAL_1HOUR = '1h'
    KLINE_INTERVAL_2HOUR = '2h'
    KLINE_INTERVAL_4HOUR = '4h'
    KLINE_INTERVAL_6HOUR = '6h'
    KLINE_INTERVAL_8HOUR = '8h'
    KLINE_INTERVAL_12HOUR = '12h'
    KLINE_INTERVAL_1DAY = '1d'
    KLINE_INTERVAL_3DAY = '3d'
    KLINE_INTERVAL_1WEEK = '1w'
    KLINE_INTERVAL_1MONTH = '1M'

    SIDE_BUY = 'buy'
    SIDE_SELL = 'sell'

    ORDER_TYPE_LIMIT = 'limit'
    ORDER_TYPE_MARKET = 'market'

    TIME_IN_FORCE_GTC = 'GTC'  # Good till cancelled
    TIME_IN_FORCE_IOC = 'IOC'  # Immediate or cancel
    TIME_IN_FORCE_FOK = 'FOK'  # Fill or kill

    ORDER_RESP_TYPE_ACK = 'ACK'
    ORDER_RESP_TYPE_RESULT = 'RESULT'
    ORDER_RESP_TYPE_FULL = 'FULL'

    # For accessing the data returned by Client.aggregate_trades().
    AGG_ID = 'a'
    AGG_PRICE = 'p'
    AGG_QUANTITY = 'q'
    AGG_FIRST_TRADE_ID = 'f'
    AGG_LAST_TRADE_ID = 'l'
    AGG_TIME = 'T'
    AGG_BUYER_MAKES = 'm'
    AGG_BEST_MATCH = 'M'

    def __init__(self, api_key, api_secret, api_url):
        """Openware API Client constructor
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_url = api_url
        self.session = self._init_session()
        self.version()

    def _init_session(self):

        timestamp = str(time.time() * 1000)
        signature = self._generate_signature(timestamp)
        session = requests.session()
        session.headers.update({'Accept': 'application/json',
                                'User-Agent': 'openware/python',
                                'X-Auth-Apikey': self.api_key,
                                'X-Auth-Nonce': timestamp,
                                'X-Auth-Signature': signature})
        return session
    
    def update_headers(self):
        
        timestamp = str(time.time() * 1000)
        signature = self._generate_signature(timestamp)
        self.session.headers.update({'Accept': 'application/json',
                                'User-Agent': 'openware/python',
                                'X-Auth-Apikey': self.api_key,
                                'X-Auth-Nonce': timestamp,
                                'X-Auth-Signature': signature})
        return self.session

    def _create_api_uri(self, path):
        return "%s%s" % (self.api_url, path)

    def _generate_signature(self, timestamp):
        query_string = "%s%s" % (timestamp, self.api_key)
        m = hmac.new(self.api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256)
        return m.hexdigest()

    def _request(self, method, uri, force_params=False, **kwargs):

        data = kwargs.get('data', None)
        if data and isinstance(data, dict):
            kwargs['data'] = data
        # if get request assign data array to params value for requests lib
        if data and (method == 'get' or force_params):
            kwargs['params'] = kwargs['data']
            del(kwargs['data'])
        self.update_headers()
        response = getattr(self.session, method)(uri, **kwargs)
        return self._handle_response(response)

    def _request_api(self, method, path, **kwargs):
        uri = self._create_api_uri(path)
        return self._request(method, uri, **kwargs)

    def _handle_response(self, response):
        
        if not str(response.status_code).startswith('2'):
            raise OpenwareAPIException(response)
        try:
            resp = response.json()
            return resp
        except ValueError:
            raise OpenwareRequestException('Invalid Response: %s' % response.text)

    def _get(self, path, **kwargs):
        return self._request_api('get', path, **kwargs)

    def _post(self, path, **kwargs):
        return self._request_api('post', path, **kwargs)

    def _put(self, path, **kwargs):
        return self._request_api('put', path, **kwargs)

    def _delete(self, path, **kwargs):
        return self._request_api('delete', path, signed, version, **kwargs)

    def version(self):
        return self._get("/public/timestamp")

    def get_markets(self):
        return self._get('/public/markets')

    def get_currencies(self):
        return self._get('/public/currencies')

    def get_server_time(self):
        return self._get('/public/timestamp')
    
    def get_balances(self):
        return self._get('/account/balances')

    def get_trade_fee(self):
        return self._get('/public/trading_fees')
    
    async def get_my_trades(self, **params):
        return self._get("/market/trades", data=params)
    
    async def get_order_by_id(self, **params):
        id = params.get('id')
        result = self._get("/market/orders/{}".format(id))
        return result
    
    async def get_order(self, **params):
        return self._get("/market/orders", data=params)

    def get_deposit_address(self, currency):
        return self._get("/account/deposit_address/%s" % currency)
    
    def withdraw(self, **params):
        return self._post("/account/withdraws", data=params)

    def create_order(self, **params):
        """
        Send in a new order
        """
        return self._post('/market/orders', data=params)

    def order_market(self, **params):
        """
        Send in a new market order
        """
        params.update({
            'ord_type': self.ORDER_TYPE_MARKET
        })
        return self.create_order(**params)
    
    def order_limit(self, **params):
        """
        Send in a new market order
        """
        params.update({
            'ord_type': self.ORDER_TYPE_LIMIT
        })
        return self.create_order(**params)
    
    def order_market_buy(self, **params):
        """
        Send in a new market buy order
        """
        params.update({
            'side': self.SIDE_BUY
        })
        return self.order_market(**params)

    def order_limit_buy(self, **params):
        """
        Send in a new market buy order
        """
        params.update({
            'side': self.SIDE_BUY
        })
        return self.order_limit(**params)
    
    def order_market_sell(self, **params):
        """
        Send in a new market sell order
        """
        params.update({
            'side': self.SIDE_SELL
        })
        return self.order_market(**params)

    def order_limit_sell(self, **params):
        """
        Send in a new market sell order
        """
        params.update({
            'side': self.SIDE_SELL
        })
        return self.order_limit(**params)

    async def cancel_order(self, **params):
        """
        Cancel order
        """
        id = params.get('id')
        return self._post('/market/orders/%s/cancel' % id)
