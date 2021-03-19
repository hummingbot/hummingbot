# coding=utf-8

import hashlib
import hmac
import requests
import time
from operator import itemgetter
from .helpers import date_to_milliseconds, interval_to_milliseconds
from .exceptions import MandalaAPIException, MandalaRequestException, MandalaWithdrawException


class Client(object):

    API_URL = 'https://trade.mandala.exchange/open'
    BINANCE_API_URL = 'https://api.binance.com/api'
    WITHDRAW_API_URL = 'https://trade.mandala.exchange/open'
    MARGIN_API_URL = 'https://trade.mandala.exchange/open'
    WEBSITE_URL = 'https://trade.mandala.exchange/'
    FUTURES_URL = 'https://trade.mandala.exchange/open'
    PUBLIC_API_VERSION = 'v1'
    BINANCE_PUBLIC_API_VERSION = 'v3'
    PRIVATE_API_VERSION = 'v1'
    BINANCE_PRIVATE_API_VERSION = 'v3'
    WITHDRAW_API_VERSION = 'v1'
    MARGIN_API_VERSION = 'v1'
    FUTURES_API_VERSION = 'v1'

    SYMBOL_TYPE_SPOT = 'SPOT'

    ORDER_STATUS_SYSTEM_PROCESSING = '-2'
    ORDER_STATUS_NEW = '0'
    ORDER_STATUS_PARTIALLY_FILLED = '1'
    ORDER_STATUS_FILLED = '2'
    ORDER_STATUS_CANCELED = '3'
    ORDER_STATUS_PENDING_CANCEL = '4'
    ORDER_STATUS_REJECTED = '5'
    ORDER_STATUS_EXPIRED = '6'

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

    SIDE_BUY = '0'
    SIDE_SELL = '1'

    ORDER_TYPE_LIMIT = '1'
    ORDER_TYPE_MARKET = '2'
    ORDER_TYPE_STOP_LOSS = '3'
    ORDER_TYPE_STOP_LOSS_LIMIT = '4'
    ORDER_TYPE_TAKE_PROFIT = '5'
    ORDER_TYPE_TAKE_PROFIT_LIMIT = '6'
    ORDER_TYPE_LIMIT_MAKER = '7'

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

    def __init__(self, api_key=None, api_secret=None, requests_params=None, tld='com'):
        """Mandala API Client constructor

        :param api_key: Api Key
        :type api_key: str.
        :param api_secret: Api Secret
        :type api_secret: str.
        :param requests_params: optional - Dictionary of requests params to use for all calls
        :type requests_params: dict.

        """

        self.API_URL = self.API_URL.format(tld)
        self.BINANCE_API_URL = self.BINANCE_API_URL.format(tld)
        self.WITHDRAW_API_URL = self.WITHDRAW_API_URL.format(tld)
        self.MARGIN_API_URL = self.MARGIN_API_URL.format(tld)
        self.WEBSITE_URL = self.WEBSITE_URL.format(tld)
        self.FUTURES_URL = self.FUTURES_URL.format(tld)

        self.API_KEY = api_key
        self.API_SECRET = api_secret
        self.session = self._init_session()
        self._requests_params = requests_params
        self.response = None

        # init DNS and SSL cert
        self.ping()

    def _init_session(self):

        session = requests.session()
        session.headers.update({'Accept': 'application/json',
                                'User-Agent': 'binance/python',
                                'X-MBX-APIKEY': self.API_KEY})
        return session

    def _create_api_uri(self, path, signed=True, version=PUBLIC_API_VERSION):
        v = self.PRIVATE_API_VERSION if signed else version
        return self.API_URL + '/' + v + '/' + path

    def _create_binance_api_uri(self, path, signed=True, version=BINANCE_PUBLIC_API_VERSION):
        v = self.BINANCE_PRIVATE_API_VERSION if signed else version
        return self.BINANCE_API_URL + '/' + v + '/' + path

    def _create_withdraw_api_uri(self, path):
        return self.WITHDRAW_API_URL + '/' + self.WITHDRAW_API_VERSION + '/' + path

    def _create_margin_api_uri(self, path):
        return self.MARGIN_API_URL + '/' + self.MARGIN_API_VERSION + '/' + path

    def _create_website_uri(self, path):
        return self.WEBSITE_URL + '/' + path

    def _create_futures_api_uri(self, path):
        return self.FUTURES_URL + '/' + self.FUTURES_API_VERSION + '/' + path

    def _generate_signature(self, data):

        ordered_data = self._order_params(data)
        query_string = '&'.join(["{}={}".format(d[0], d[1]) for d in ordered_data])
        m = hmac.new(self.API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256)
        return m.hexdigest()

    def _order_params(self, data):
        """Convert params to list with signature as last element

        :param data:
        :return:

        """
        has_signature = False
        params = []
        for key, value in data.items():
            if key == 'signature':
                has_signature = True
            else:
                params.append((key, value))
        # sort parameters by key
        params.sort(key=itemgetter(0))
        if has_signature:
            params.append(('signature', data['signature']))
        return params

    def _request(self, method, uri, signed, force_params=False, **kwargs):
        # set default requests timeout
        kwargs['timeout'] = 10

        # add our global requests params
        if self._requests_params:
            kwargs.update(self._requests_params)

        data = kwargs.get('data', None)
        if data and isinstance(data, dict):
            kwargs['data'] = data
            # kwargs['data']['recvWindow'] = int(5000)
            # find any requests params passed and apply them
            if 'requests_params' in kwargs['data']:
                # merge requests params into kwargs
                kwargs.update(kwargs['data']['requests_params'])
                del(kwargs['data']['requests_params'])

        if signed:
            # generate signature
            kwargs['data']['timestamp'] = int(time.time() * 1000)
            kwargs['data']['signature'] = self._generate_signature(kwargs['data'])

        # print('_request', kwargs)

        # sort get and post params to match signature order
        if data:
            # sort post params
            kwargs['data'] = self._order_params(kwargs['data'])
            # Remove any arguments with values of None.
            null_args = [i for i, (key, value) in enumerate(kwargs['data']) if value is None]
            for i in reversed(null_args):
                del kwargs['data'][i]

        # if get request assign data array to params value for requests lib
        if data and (method == 'get' or force_params):
            kwargs['params'] = '&'.join('%s=%s' % (data[0], data[1]) for data in kwargs['data'])
            del(kwargs['data'])

        # print('_request', kwargs)

        self.response = getattr(self.session, method)(uri, **kwargs)
        return self._handle_response()

    def _request_api(self, method, path, signed=False, version=PUBLIC_API_VERSION, **kwargs):
        uri = self._create_api_uri(path, signed, version)
        print('uri', uri)
        # test = self._request(method, uri, signed, **kwargs)
        return self._request(method, uri, signed, True, **kwargs)

    def _request_binance_api(self, method, path, signed=False, version=BINANCE_PUBLIC_API_VERSION, **kwargs):
        uri = self._create_binance_api_uri(path, signed, version)
        print('uri', uri)
        # test = self._request(method, uri, signed, **kwargs)
        return self._request(method, uri, signed, True, **kwargs)

    def _request_withdraw_api(self, method, path, signed=False, **kwargs):
        uri = self._create_withdraw_api_uri(path)

        return self._request(method, uri, signed, True, **kwargs)

    def _request_margin_api(self, method, path, signed=False, **kwargs):
        uri = self._create_margin_api_uri(path)

        return self._request(method, uri, signed, **kwargs)

    def _request_website(self, method, path, signed=False, **kwargs):
        uri = self._create_website_uri(path)

        return self._request(method, uri, signed, **kwargs)

    def _request_futures_api(self, method, path, signed=False, **kwargs):
        uri = self._create_futures_api_uri(path)

        return self._request(method, uri, signed, True, **kwargs)

    def _handle_response(self):
        """Internal helper for handling API responses from the Mandala server.
        Raises the appropriate exceptions when necessary; otherwise, returns the
        response.
        """
        if not str(self.response.status_code).startswith('2'):
            raise MandalaAPIException(self.response)
        try:
            # print('response', self.response.json())
            return self.response.json()
        except ValueError:
            raise MandalaRequestException('Invalid Response: %s' % self.response.text)

    # Mandala Endpoints

    def _get(self, path, signed=False, version=PUBLIC_API_VERSION, **kwargs):
        return self._request_api('get', path, signed, version, **kwargs)

    def _post(self, path, signed=False, version=PUBLIC_API_VERSION, **kwargs):
        return self._request_api('post', path, signed, version, **kwargs)

    def _put(self, path, signed=False, version=PUBLIC_API_VERSION, **kwargs):
        return self._request_api('put', path, signed, version, **kwargs)

    def _delete(self, path, signed=False, version=PUBLIC_API_VERSION, **kwargs):
        return self._request_api('delete', path, signed, version, **kwargs)

    # Binance Endpoints

    def _binance_get(self, path, signed=False, version=BINANCE_PUBLIC_API_VERSION, **kwargs):
        return self._request_binance_api('get', path, signed, version, **kwargs)

    # Exchange Endpoints

    def get_products(self):
        products = self._request_website('get', 'exchange/public/product')
        return products

    def get_exchange_info(self):
        return self._get('common/symbols').get("data", [])

    def get_symbol_info(self, symbol):
        res = self._get('common/symbols').get("data", [])

        for item in res['list']:
            if item['symbol'] == symbol.upper():
                return item

        return None

    # General Endpoints

    def ping(self):
        return self._binance_get('ping')

    def get_server_time(self):
        return self._get('common/time')

    # Market Data Endpoints

    def get_orderbook_tickers(self):
        """Best price/qty on the order book for all symbols.

        https://www.binance.com/restapipub.html#symbols-order-book-ticker

        :returns: List of order book market entries

        .. code-block:: python

            [
                {
                    "symbol": "LTCBTC",
                    "bidPrice": "4.00000000",
                    "bidQty": "431.00000000",
                    "askPrice": "4.00000200",
                    "askQty": "9.00000000"
                },
                {
                    "symbol": "ETHBTC",
                    "bidPrice": "0.07946700",
                    "bidQty": "9.00000000",
                    "askPrice": "100000.00000000",
                    "askQty": "1000.00000000"
                }
            ]

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._get('ticker/allBookTickers')

    def get_order_book(self, **params):
        """Get the Order Book for the market

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#order-book

        :param symbol: required
        :type symbol: str
        :param limit:  Default 100; max 1000
        :type limit: int

        :returns: API response

        .. code-block:: python

            {
                "lastUpdateId": 1027024,
                "bids": [
                    [
                        "4.00000000",     # PRICE
                        "431.00000000",   # QTY
                        []                # Can be ignored
                    ]
                ],
                "asks": [
                    [
                        "4.00000200",
                        "12.00000000",
                        []
                    ]
                ]
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._get('market/depth', data=params).get("data")

    def get_recent_trades(self, **params):
        """Get recent trades (up to last 500).

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#recent-trades-list

        :param symbol: required
        :type symbol: str
        :param limit:  Default 500; max 500.
        :type limit: int

        :returns: API response

        .. code-block:: python

            [
                {
                    "id": 28457,
                    "price": "4.00000100",
                    "qty": "12.00000000",
                    "time": 1499865549590,
                    "isBuyerMaker": true,
                    "isBestMatch": true
                }
            ]

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._get('market/trades', data=params).get("data")

    def get_historical_trades(self, **params):
        """Get older trades.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#recent-trades-list

        :param symbol: required
        :type symbol: str
        :param limit:  Default 500; max 500.
        :type limit: int
        :param fromId:  TradeId to fetch from. Default gets most recent trades.
        :type fromId: str

        :returns: API response

        .. code-block:: python

            [
                {
                    "id": 28457,
                    "price": "4.00000100",
                    "qty": "12.00000000",
                    "time": 1499865549590,
                    "isBuyerMaker": true,
                    "isBestMatch": true
                }
            ]

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._get('historicalTrades', data=params)

    def get_aggregate_trades(self, **params):
        """Get compressed, aggregate trades. Trades that fill at the time,
        from the same order, with the same price will have the quantity aggregated.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#compressedaggregate-trades-list

        :param symbol: required
        :type symbol: str
        :param fromId:  ID to get aggregate trades from INCLUSIVE.
        :type fromId: str
        :param startTime: Timestamp in ms to get aggregate trades from INCLUSIVE.
        :type startTime: int
        :param endTime: Timestamp in ms to get aggregate trades until INCLUSIVE.
        :type endTime: int
        :param limit:  Default 500; max 500.
        :type limit: int

        :returns: API response

        .. code-block:: python

            [
                {
                    "a": 26129,         # Aggregate tradeId
                    "p": "0.01633102",  # Price
                    "q": "4.70443515",  # Quantity
                    "f": 27781,         # First tradeId
                    "l": 27781,         # Last tradeId
                    "T": 1498793709153, # Timestamp
                    "m": true,          # Was the buyer the maker?
                    "M": true           # Was the trade the best price match?
                }
            ]

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._get('aggTrades', data=params)

    def aggregate_trade_iter(self, symbol, start_str=None, last_id=None):
        """Iterate over aggregate trade data from (start_time or last_id) to
        the end of the history so far.

        If start_time is specified, start with the first trade after
        start_time. Meant to initialise a local cache of trade data.

        If last_id is specified, start with the trade after it. This is meant
        for updating a pre-existing local trade data cache.

        Only allows start_str or last_id—not both. Not guaranteed to work
        right if you're running more than one of these simultaneously. You
        will probably hit your rate limit.

        See dateparser docs for valid start and end string formats http://dateparser.readthedocs.io/en/latest/

        If using offset strings for dates add "UTC" to date string e.g. "now UTC", "11 hours ago UTC"

        :param symbol: Symbol string e.g. ETHBTC
        :type symbol: str
        :param start_str: Start date string in UTC format or timestamp in milliseconds. The iterator will
        return the first trade occurring later than this time.
        :type start_str: str|int
        :param last_id: aggregate trade ID of the last known aggregate trade.
        Not a regular trade ID. See https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#compressedaggregate-trades-list.

        :returns: an iterator of JSON objects, one per trade. The format of
        each object is identical to Client.aggregate_trades().

        :type last_id: int
        """
        if start_str is not None and last_id is not None:
            raise ValueError(
                'start_time and last_id may not be simultaneously specified.')

        # If there's no last_id, get one.
        if last_id is None:
            # Without a last_id, we actually need the first trade.  Normally,
            # we'd get rid of it. See the next loop.
            if start_str is None:
                trades = self.get_aggregate_trades(symbol=symbol, fromId=0)
            else:
                # The difference between startTime and endTime should be less
                # or equal than an hour and the result set should contain at
                # least one trade.
                if type(start_str) == int:
                    start_ts = start_str
                else:
                    start_ts = date_to_milliseconds(start_str)
                # If the resulting set is empty (i.e. no trades in that interval)
                # then we just move forward hour by hour until we find at least one
                # trade or reach present moment
                while True:
                    end_ts = start_ts + (60 * 60 * 1000)
                    trades = self.get_aggregate_trades(
                        symbol=symbol,
                        startTime=start_ts,
                        endTime=end_ts)
                    if len(trades) > 0:
                        break
                    # If we reach present moment and find no trades then there is
                    # nothing to iterate, so we're done
                    if end_ts > int(time.time() * 1000):
                        return
                    start_ts = end_ts
            for t in trades:
                yield t
            last_id = trades[-1][self.AGG_ID]

        while True:
            # There is no need to wait between queries, to avoid hitting the
            # rate limit. We're using blocking IO, and as long as we're the
            # only thread running calls like this, Mandala will automatically
            # add the right delay time on their end, forcing us to wait for
            # data. That really simplifies this function's job. Mandala is
            # fucking awesome.
            trades = self.get_aggregate_trades(symbol=symbol, fromId=last_id)
            # fromId=n returns a set starting with id n, but we already have
            # that one. So get rid of the first item in the result set.
            trades = trades[1:]
            if len(trades) == 0:
                return
            for t in trades:
                yield t
            last_id = trades[-1][self.AGG_ID]

    def get_klines(self, **params):
        """Kline/candlestick bars for a symbol. Klines are uniquely identified by their open time.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#klinecandlestick-data

        :param symbol: required
        :type symbol: str
        :param interval: -
        :type interval: str
        :param limit: - Default 500; max 500.
        :type limit: int
        :param startTime:
        :type startTime: int
        :param endTime:
        :type endTime: int

        :returns: API response

        .. code-block:: python

            [
                [
                    1499040000000,      # Open time
                    "0.01634790",       # Open
                    "0.80000000",       # High
                    "0.01575800",       # Low
                    "0.01577100",       # Close
                    "148976.11427815",  # Volume
                    1499644799999,      # Close time
                    "2434.19055334",    # Quote asset volume
                    308,                # Number of trades
                    "1756.87402397",    # Taker buy base asset volume
                    "28.46694368",      # Taker buy quote asset volume
                    "17928899.62484339" # Can be ignored
                ]
            ]

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._get('klines', data=params)

    def _get_earliest_valid_timestamp(self, symbol, interval):
        """Get earliest valid open timestamp from Mandala

        :param symbol: Name of symbol pair e.g BNBBTC
        :type symbol: str
        :param interval: Mandala Kline interval
        :type interval: str

        :return: first valid timestamp

        """
        kline = self.get_klines(
            symbol=symbol,
            interval=interval,
            limit=1,
            startTime=0,
            endTime=None
        )
        return kline[0][0]

    async def get_historical_klines(self, symbol, interval, start_str, end_str=None,
                              limit=500):
        """Get Historical Klines from Mandala

        See dateparser docs for valid start and end string formats http://dateparser.readthedocs.io/en/latest/

        If using offset strings for dates add "UTC" to date string e.g. "now UTC", "11 hours ago UTC"

        :param symbol: Name of symbol pair e.g BNBBTC
        :type symbol: str
        :param interval: Mandala Kline interval
        :type interval: str
        :param start_str: Start date string in UTC format or timestamp in milliseconds
        :type start_str: str|int
        :param end_str: optional - end date string in UTC format or timestamp in milliseconds (default will fetch everything up to now)
        :type end_str: str|int
        :param limit: Default 500; max 1000.
        :type limit: int

        :return: list of OHLCV values

        """
        # init our list
        output_data = []

        # setup the max limit
        limit = limit

        # convert interval to useful value in seconds
        timeframe = interval_to_milliseconds(interval)

        # convert our date strings to milliseconds
        if type(start_str) == int:
            start_ts = start_str
        else:
            start_ts = date_to_milliseconds(start_str)

        # establish first available start timestamp
        first_valid_ts = self._get_earliest_valid_timestamp(symbol, interval)
        start_ts = max(start_ts, first_valid_ts)

        # if an end time was passed convert it
        end_ts = None
        if end_str:
            if type(end_str) == int:
                end_ts = end_str
            else:
                end_ts = date_to_milliseconds(end_str)

        idx = 0
        while True:
            # fetch the klines from start_ts up to max 500 entries or the end_ts if set
            temp_data = self.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit,
                startTime=start_ts,
                endTime=end_ts
            )

            # handle the case where exactly the limit amount of data was returned last loop
            if not len(temp_data):
                break

            # append this loops data to our output data
            output_data += temp_data

            # set our start timestamp using the last value in the array
            start_ts = temp_data[-1][0]

            idx += 1
            # check if we received less than the required limit and exit the loop
            if len(temp_data) < limit:
                # exit the while loop
                break

            # increment next call by our timeframe
            start_ts += timeframe

            # sleep after every 3rd call to be kind to the API
            if idx % 3 == 0:
                await asyncio.sleep(1)

        return output_data

    async def get_historical_klines_generator(self, symbol, interval, start_str, end_str=None):
        """Get Historical Klines from Mandala

        See dateparser docs for valid start and end string formats http://dateparser.readthedocs.io/en/latest/

        If using offset strings for dates add "UTC" to date string e.g. "now UTC", "11 hours ago UTC"

        :param symbol: Name of symbol pair e.g BNBBTC
        :type symbol: str
        :param interval: Mandala Kline interval
        :type interval: str
        :param start_str: Start date string in UTC format or timestamp in milliseconds
        :type start_str: str|int
        :param end_str: optional - end date string in UTC format or timestamp in milliseconds (default will fetch everything up to now)
        :type end_str: str|int

        :return: generator of OHLCV values

        """

        # setup the max limit
        limit = 500

        # convert interval to useful value in seconds
        timeframe = interval_to_milliseconds(interval)

        # convert our date strings to milliseconds
        if type(start_str) == int:
            start_ts = start_str
        else:
            start_ts = date_to_milliseconds(start_str)

        # establish first available start timestamp
        first_valid_ts = self._get_earliest_valid_timestamp(symbol, interval)
        start_ts = max(start_ts, first_valid_ts)

        # if an end time was passed convert it
        end_ts = None
        if end_str:
            if type(end_str) == int:
                end_ts = end_str
            else:
                end_ts = date_to_milliseconds(end_str)

        idx = 0
        while True:
            # fetch the klines from start_ts up to max 500 entries or the end_ts if set
            output_data = self.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit,
                startTime=start_ts,
                endTime=end_ts
            )

            # handle the case where exactly the limit amount of data was returned last loop
            if not len(output_data):
                break

            # yield data
            for o in output_data:
                yield o

            # set our start timestamp using the last value in the array
            start_ts = output_data[-1][0]

            idx += 1
            # check if we received less than the required limit and exit the loop
            if len(output_data) < limit:
                # exit the while loop
                break

            # increment next call by our timeframe
            start_ts += timeframe

            # sleep after every 3rd call to be kind to the API
            if idx % 3 == 0:
                await asyncio.sleep(1)

    def get_avg_price(self, **params):
        """Current average price for a symbol.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#current-average-price

        :param symbol:
        :type symbol: str

        :returns: API response

        .. code-block:: python

            {
                "mins": 5,
                "price": "9.35751834"
            }
"""
        return self._get('avgPrice', data=params, version=self.PRIVATE_API_VERSION)

    def get_ticker(self, **params):
        """24 hour price change statistics.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#24hr-ticker-price-change-statistics

        :param symbol:
        :type symbol: str

        :returns: API response

        .. code-block:: python

            {
                "priceChange": "-94.99999800",
                "priceChangePercent": "-95.960",
                "weightedAvgPrice": "0.29628482",
                "prevClosePrice": "0.10002000",
                "lastPrice": "4.00000200",
                "bidPrice": "4.00000000",
                "askPrice": "4.00000200",
                "openPrice": "99.00000000",
                "highPrice": "100.00000000",
                "lowPrice": "0.10000000",
                "volume": "8913.30000000",
                "openTime": 1499783499040,
                "closeTime": 1499869899040,
                "fristId": 28385,   # First tradeId
                "lastId": 28460,    # Last tradeId
                "count": 76         # Trade count
            }

        OR

        .. code-block:: python

            [
                {
                    "priceChange": "-94.99999800",
                    "priceChangePercent": "-95.960",
                    "weightedAvgPrice": "0.29628482",
                    "prevClosePrice": "0.10002000",
                    "lastPrice": "4.00000200",
                    "bidPrice": "4.00000000",
                    "askPrice": "4.00000200",
                    "openPrice": "99.00000000",
                    "highPrice": "100.00000000",
                    "lowPrice": "0.10000000",
                    "volume": "8913.30000000",
                    "openTime": 1499783499040,
                    "closeTime": 1499869899040,
                    "fristId": 28385,   # First tradeId
                    "lastId": 28460,    # Last tradeId
                    "count": 76         # Trade count
                }
            ]

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._get('ticker/24hr', data=params)

    def get_symbol_ticker(self, **params):
        """Latest price for a symbol or symbols.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#24hr-ticker-price-change-statistics

        :param symbol:
        :type symbol: str

        :returns: API response

        .. code-block:: python

            {
                "symbol": "LTCBTC",
                "price": "4.00000200"
            }

        OR

        .. code-block:: python

            [
                {
                    "symbol": "LTCBTC",
                    "price": "4.00000200"
                },
                {
                    "symbol": "ETHBTC",
                    "price": "0.07946600"
                }
            ]

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._get('ticker/price', data=params, version=self.PRIVATE_API_VERSION)

    def get_orderbook_ticker(self, **params):
        """Latest price for a symbol or symbols.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#symbol-order-book-ticker

        :param symbol:
        :type symbol: str

        :returns: API response

        .. code-block:: python

            {
                "symbol": "LTCBTC",
                "bidPrice": "4.00000000",
                "bidQty": "431.00000000",
                "askPrice": "4.00000200",
                "askQty": "9.00000000"
            }

        OR

        .. code-block:: python

            [
                {
                    "symbol": "LTCBTC",
                    "bidPrice": "4.00000000",
                    "bidQty": "431.00000000",
                    "askPrice": "4.00000200",
                    "askQty": "9.00000000"
                },
                {
                    "symbol": "ETHBTC",
                    "bidPrice": "0.07946700",
                    "bidQty": "9.00000000",
                    "askPrice": "100000.00000000",
                    "askQty": "1000.00000000"
                }
            ]

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._get('ticker/bookTicker', data=params, version=self.PRIVATE_API_VERSION)

    # Account Endpoints

    def create_order(self, **params):
        """Send in a new order

        Any order with an icebergQty MUST have timeInForce set to GTC.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#new-order--trade

        :param symbol: required
        :type symbol: str
        :param side: required
        :type side: str
        :param type: required
        :type type: str
        :param timeInForce: required if limit order
        :type timeInForce: str
        :param quantity: required
        :type quantity: decimal
        :param quoteOrderQty: amount the user wants to spend (when buying) or receive (when selling)
            of the quote asset, applicable to MARKET orders
        :type quoteOrderQty: decimal
        :param price: required
        :type price: str
        :param clientId: A unique id for the order. Automatically generated if not sent.
        :type clientId: str
        :param icebergQty: Used with LIMIT, STOP_LOSS_LIMIT, and TAKE_PROFIT_LIMIT to create an iceberg order.
        :type icebergQty: decimal
        :param newOrderRespType: Set the response JSON. ACK, RESULT, or FULL; default: RESULT.
        :type newOrderRespType: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        Response ACK:

        .. code-block:: python

            {
                "symbol":"LTCBTC",
                "orderId": 1,
                "clientOrderId": "myOrder1" # Will be clientId
                "transactTime": 1499827319559
            }

        Response RESULT:

        .. code-block:: python

            {
                "symbol": "BTCUSDT",
                "orderId": 28,
                "clientOrderId": "6gCrw2kRUAF9CvJDGP16IP",
                "transactTime": 1507725176595,
                "price": "0.00000000",
                "origQty": "10.00000000",
                "executedQty": "10.00000000",
                "status": "FILLED",
                "timeInForce": "GTC",
                "type": "MARKET",
                "side": "SELL"
            }

        Response FULL:

        .. code-block:: python

            {
                "symbol": "BTCUSDT",
                "orderId": 28,
                "clientOrderId": "6gCrw2kRUAF9CvJDGP16IP",
                "transactTime": 1507725176595,
                "price": "0.00000000",
                "origQty": "10.00000000",
                "executedQty": "10.00000000",
                "status": "FILLED",
                "timeInForce": "GTC",
                "type": "MARKET",
                "side": "SELL",
                "fills": [
                    {
                        "price": "4000.00000000",
                        "qty": "1.00000000",
                        "commission": "4.00000000",
                        "commissionAsset": "USDT"
                    },
                    {
                        "price": "3999.00000000",
                        "qty": "5.00000000",
                        "commission": "19.99500000",
                        "commissionAsset": "USDT"
                    },
                    {
                        "price": "3998.00000000",
                        "qty": "2.00000000",
                        "commission": "7.99600000",
                        "commissionAsset": "USDT"
                    },
                    {
                        "price": "3997.00000000",
                        "qty": "1.00000000",
                        "commission": "3.99700000",
                        "commissionAsset": "USDT"
                    },
                    {
                        "price": "3995.00000000",
                        "qty": "1.00000000",
                        "commission": "3.99500000",
                        "commissionAsset": "USDT"
                    }
                ]
            }

        :raises: MandalaRequestException, MandalaAPIException, MandalaOrderException, MandalaOrderMinAmountException, MandalaOrderMinPriceException, MandalaOrderMinTotalException, MandalaOrderUnknownSymbolException, MandalaOrderInactiveSymbolException

        """
        return self._post('orders', True, data=params)

    def order_limit(self, timeInForce=TIME_IN_FORCE_GTC, **params):
        """Send in a new limit order

        Any order with an icebergQty MUST have timeInForce set to GTC.

        :param symbol: required
        :type symbol: str
        :param side: required
        :type side: str
        :param quantity: required
        :type quantity: decimal
        :param price: required
        :type price: str
        :param timeInForce: default Good till cancelled
        :type timeInForce: str
        :param clientId: A unique id for the order. Automatically generated if not sent.
        :type clientId: str
        :param icebergQty: Used with LIMIT, STOP_LOSS_LIMIT, and TAKE_PROFIT_LIMIT to create an iceberg order.
        :type icebergQty: decimal
        :param newOrderRespType: Set the response JSON. ACK, RESULT, or FULL; default: RESULT.
        :type newOrderRespType: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        See order endpoint for full response options

        :raises: MandalaRequestException, MandalaAPIException, MandalaOrderException, MandalaOrderMinAmountException, MandalaOrderMinPriceException, MandalaOrderMinTotalException, MandalaOrderUnknownSymbolException, MandalaOrderInactiveSymbolException

        """
        params.update({
            'type': self.ORDER_TYPE_LIMIT,
            'timeInForce': timeInForce
        })
        return self.create_order(**params)

    def order_limit_buy(self, timeInForce=TIME_IN_FORCE_GTC, **params):
        """Send in a new limit buy order

        Any order with an icebergQty MUST have timeInForce set to GTC.

        :param symbol: required
        :type symbol: str
        :param quantity: required
        :type quantity: decimal
        :param price: required
        :type price: str
        :param timeInForce: default Good till cancelled
        :type timeInForce: str
        :param clientId: A unique id for the order. Automatically generated if not sent.
        :type clientId: str
        :param stopPrice: Used with stop orders
        :type stopPrice: decimal
        :param icebergQty: Used with iceberg orders
        :type icebergQty: decimal
        :param newOrderRespType: Set the response JSON. ACK, RESULT, or FULL; default: RESULT.
        :type newOrderRespType: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        See order endpoint for full response options

        :raises: MandalaRequestException, MandalaAPIException, MandalaOrderException, MandalaOrderMinAmountException, MandalaOrderMinPriceException, MandalaOrderMinTotalException, MandalaOrderUnknownSymbolException, MandalaOrderInactiveSymbolException

        """
        params.update({
            'side': self.SIDE_BUY,
        })
        return self.order_limit(timeInForce=timeInForce, **params)

    def order_limit_sell(self, timeInForce=TIME_IN_FORCE_GTC, **params):
        """Send in a new limit sell order

        :param symbol: required
        :type symbol: str
        :param quantity: required
        :type quantity: decimal
        :param price: required
        :type price: str
        :param timeInForce: default Good till cancelled
        :type timeInForce: str
        :param clientId: A unique id for the order. Automatically generated if not sent.
        :type clientId: str
        :param stopPrice: Used with stop orders
        :type stopPrice: decimal
        :param icebergQty: Used with iceberg orders
        :type icebergQty: decimal
        :param newOrderRespType: Set the response JSON. ACK, RESULT, or FULL; default: RESULT.
        :type newOrderRespType: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        See order endpoint for full response options

        :raises: MandalaRequestException, MandalaAPIException, MandalaOrderException, MandalaOrderMinAmountException, MandalaOrderMinPriceException, MandalaOrderMinTotalException, MandalaOrderUnknownSymbolException, MandalaOrderInactiveSymbolException

        """
        params.update({
            'side': self.SIDE_SELL
        })
        return self.order_limit(timeInForce=timeInForce, **params)

    def order_market(self, **params):
        """Send in a new market order

        :param symbol: required
        :type symbol: str
        :param side: required
        :type side: str
        :param quantity: required
        :type quantity: decimal
        :param quoteOrderQty: amount the user wants to spend (when buying) or receive (when selling)
            of the quote asset
        :type quoteOrderQty: decimal
        :param clientId: A unique id for the order. Automatically generated if not sent.
        :type clientId: str
        :param newOrderRespType: Set the response JSON. ACK, RESULT, or FULL; default: RESULT.
        :type newOrderRespType: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        See order endpoint for full response options

        :raises: MandalaRequestException, MandalaAPIException, MandalaOrderException, MandalaOrderMinAmountException, MandalaOrderMinPriceException, MandalaOrderMinTotalException, MandalaOrderUnknownSymbolException, MandalaOrderInactiveSymbolException

        """
        params.update({
            'type': self.ORDER_TYPE_MARKET
        })
        return self.create_order(**params)

    def order_market_buy(self, **params):
        """Send in a new market buy order

        :param symbol: required
        :type symbol: str
        :param quantity: required
        :type quantity: decimal
        :param quoteOrderQty: the amount the user wants to spend of the quote asset
        :type quoteOrderQty: decimal
        :param clientId: A unique id for the order. Automatically generated if not sent.
        :type clientId: str
        :param newOrderRespType: Set the response JSON. ACK, RESULT, or FULL; default: RESULT.
        :type newOrderRespType: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        See order endpoint for full response options

        :raises: MandalaRequestException, MandalaAPIException, MandalaOrderException, MandalaOrderMinAmountException, MandalaOrderMinPriceException, MandalaOrderMinTotalException, MandalaOrderUnknownSymbolException, MandalaOrderInactiveSymbolException

        """
        params.update({
            'side': self.SIDE_BUY
        })
        return self.order_market(**params)

    def order_market_sell(self, **params):
        """Send in a new market sell order

        :param symbol: required
        :type symbol: str
        :param quantity: required
        :type quantity: decimal
        :param quoteOrderQty: the amount the user wants to receive of the quote asset
        :type quoteOrderQty: decimal
        :param clientId: A unique id for the order. Automatically generated if not sent.
        :type clientId: str
        :param newOrderRespType: Set the response JSON. ACK, RESULT, or FULL; default: RESULT.
        :type newOrderRespType: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        See order endpoint for full response options

        :raises: MandalaRequestException, MandalaAPIException, MandalaOrderException, MandalaOrderMinAmountException, MandalaOrderMinPriceException, MandalaOrderMinTotalException, MandalaOrderUnknownSymbolException, MandalaOrderInactiveSymbolException

        """
        params.update({
            'side': self.SIDE_SELL
        })
        return self.order_market(**params)

    def create_oco_order(self, **params):
        """Send in a new OCO order

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#new-oco-trade

        :param symbol: required
        :type symbol: str
        :param listClientOrderId: A unique id for the list order. Automatically generated if not sent.
        :type listClientOrderId: str
        :param side: required
        :type side: str
        :param quantity: required
        :type quantity: decimal
        :param limitClientOrderId: A unique id for the limit order. Automatically generated if not sent.
        :type limitClientOrderId: str
        :param price: required
        :type price: str
        :param limitIcebergQty: Used to make the LIMIT_MAKER leg an iceberg order.
        :type limitIcebergQty: decimal
        :param stopClientOrderId: A unique id for the stop order. Automatically generated if not sent.
        :type stopClientOrderId: str
        :param stopPrice: required
        :type stopPrice: str
        :param stopLimitPrice: If provided, stopLimitTimeInForce is required.
        :type stopLimitPrice: str
        :param stopIcebergQty: Used with STOP_LOSS_LIMIT leg to make an iceberg order.
        :type stopIcebergQty: decimal
        :param stopLimitTimeInForce: Valid values are GTC/FOK/IOC.
        :type stopLimitTimeInForce: str
        :param newOrderRespType: Set the response JSON. ACK, RESULT, or FULL; default: RESULT.
        :type newOrderRespType: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        Response ACK:

        .. code-block:: python

            {
            }

        Response RESULT:

        .. code-block:: python

            {
            }

        Response FULL:

        .. code-block:: python

            {
            }

        :raises: MandalaRequestException, MandalaAPIException, MandalaOrderException, MandalaOrderMinAmountException, MandalaOrderMinPriceException, MandalaOrderMinTotalException, MandalaOrderUnknownSymbolException, MandalaOrderInactiveSymbolException

        """
        return self._post('orders/oco', True, data=params)

    def order_oco_buy(self, **params):
        """Send in a new OCO buy order

        :param symbol: required
        :type symbol: str
        :param listClientOrderId: A unique id for the list order. Automatically generated if not sent.
        :type listClientOrderId: str
        :param quantity: required
        :type quantity: decimal
        :param limitClientOrderId: A unique id for the limit order. Automatically generated if not sent.
        :type limitClientOrderId: str
        :param price: required
        :type price: str
        :param limitIcebergQty: Used to make the LIMIT_MAKER leg an iceberg order.
        :type limitIcebergQty: decimal
        :param stopClientOrderId: A unique id for the stop order. Automatically generated if not sent.
        :type stopClientOrderId: str
        :param stopPrice: required
        :type stopPrice: str
        :param stopLimitPrice: If provided, stopLimitTimeInForce is required.
        :type stopLimitPrice: str
        :param stopIcebergQty: Used with STOP_LOSS_LIMIT leg to make an iceberg order.
        :type stopIcebergQty: decimal
        :param stopLimitTimeInForce: Valid values are GTC/FOK/IOC.
        :type stopLimitTimeInForce: str
        :param newOrderRespType: Set the response JSON. ACK, RESULT, or FULL; default: RESULT.
        :type newOrderRespType: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        See OCO order endpoint for full response options

        :raises: MandalaRequestException, MandalaAPIException, MandalaOrderException, MandalaOrderMinAmountException, MandalaOrderMinPriceException, MandalaOrderMinTotalException, MandalaOrderUnknownSymbolException, MandalaOrderInactiveSymbolException

        """
        params.update({
            'side': self.SIDE_BUY
        })
        return self.create_oco_order(**params)

    def order_oco_sell(self, **params):
        """Send in a new OCO sell order

        :param symbol: required
        :type symbol: str
        :param listClientOrderId: A unique id for the list order. Automatically generated if not sent.
        :type listClientOrderId: str
        :param quantity: required
        :type quantity: decimal
        :param limitClientOrderId: A unique id for the limit order. Automatically generated if not sent.
        :type limitClientOrderId: str
        :param price: required
        :type price: str
        :param limitIcebergQty: Used to make the LIMIT_MAKER leg an iceberg order.
        :type limitIcebergQty: decimal
        :param stopClientOrderId: A unique id for the stop order. Automatically generated if not sent.
        :type stopClientOrderId: str
        :param stopPrice: required
        :type stopPrice: str
        :param stopLimitPrice: If provided, stopLimitTimeInForce is required.
        :type stopLimitPrice: str
        :param stopIcebergQty: Used with STOP_LOSS_LIMIT leg to make an iceberg order.
        :type stopIcebergQty: decimal
        :param stopLimitTimeInForce: Valid values are GTC/FOK/IOC.
        :type stopLimitTimeInForce: str
        :param newOrderRespType: Set the response JSON. ACK, RESULT, or FULL; default: RESULT.
        :type newOrderRespType: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        See OCO order endpoint for full response options

        :raises: MandalaRequestException, MandalaAPIException, MandalaOrderException, MandalaOrderMinAmountException, MandalaOrderMinPriceException, MandalaOrderMinTotalException, MandalaOrderUnknownSymbolException, MandalaOrderInactiveSymbolException

        """
        params.update({
            'side': self.SIDE_SELL
        })
        return self.create_oco_order(**params)

    def create_test_order(self, **params):
        """Test new order creation and signature/recvWindow long. Creates and validates a new order but does not send it into the matching engine.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#test-new-order-trade

        :param symbol: required
        :type symbol: str
        :param side: required
        :type side: str
        :param type: required
        :type type: str
        :param timeInForce: required if limit order
        :type timeInForce: str
        :param quantity: required
        :type quantity: decimal
        :param price: required
        :type price: str
        :param clientId: A unique id for the order. Automatically generated if not sent.
        :type clientId: str
        :param icebergQty: Used with iceberg orders
        :type icebergQty: decimal
        :param newOrderRespType: Set the response JSON. ACK, RESULT, or FULL; default: RESULT.
        :type newOrderRespType: str
        :param recvWindow: The number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        .. code-block:: python

            {}

        :raises: MandalaRequestException, MandalaAPIException, MandalaOrderException, MandalaOrderMinAmountException, MandalaOrderMinPriceException, MandalaOrderMinTotalException, MandalaOrderUnknownSymbolException, MandalaOrderInactiveSymbolException


        """
        return self._post('order/test', True, data=params)

    def get_order(self, **params):
        """Check an order's status. Either orderId or orderId must be sent.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#query-order-user_data

        :param symbol: required
        :type symbol: str
        :param orderId: The unique order id
        :type orderId: int
        :param orderId: optional
        :type orderId: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        .. code-block:: python

            {
                "symbol": "LTCBTC",
                "orderId": 1,
                "clientOrderId": "myOrder1",
                "price": "0.1",
                "origQty": "1.0",
                "executedQty": "0.0",
                "status": "NEW",
                "timeInForce": "GTC",
                "type": "LIMIT",
                "side": "BUY",
                "stopPrice": "0.0",
                "icebergQty": "0.0",
                "time": 1499827319559
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._get('orders/detail', True, data=params)

    def get_all_orders(self, **params):
        """Get all account orders; active, canceled, or filled.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#all-orders-user_data

        :param symbol: required
        :type symbol: str
        :param orderId: The unique order id
        :type orderId: int
        :param limit: Default 500; max 500.
        :type limit: int
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        .. code-block:: python

            [
                {
                    "symbol": "LTCBTC",
                    "orderId": 1,
                    "clientOrderId": "myOrder1",
                    "price": "0.1",
                    "origQty": "1.0",
                    "executedQty": "0.0",
                    "status": "NEW",
                    "timeInForce": "GTC",
                    "type": "LIMIT",
                    "side": "BUY",
                    "stopPrice": "0.0",
                    "icebergQty": "0.0",
                    "time": 1499827319559
                }
            ]

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._get('orders', True, data=params)

    def cancel_order(self, **params):
        """Cancel an active order. orderId must be sent.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#cancel-order-trade

        :param symbol: required
        :type symbol: str
        :param orderId: The unique order id
        :type orderId: int
        :param orderId: optional
        :type orderId: str
        :param clientId: Used to uniquely identify this cancel. Automatically generated by default.
        :type clientId: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        .. code-block:: python

            {
                "code": 0,
                "message": "success",
                "data": {
                    "orderId": 4,
                    "orderListId": -1 // Unless part of an OCO, the value will always be -1.
                    "clientId": "myOrder1",
                    "symbol": "BTC_USDT",
                    "side": 1,
                    "type": 1,
                    "price": 1,
                    "status": 0,
                    "origQty": 10.88,
                    "origQuoteQty": 0,
                    "executedQty": 0,
                    "executedPrice": 0,
                    "executedQuoteQty": 0,
                    "createTime": 1550130502000
                },
                "timestamp": 1550130554182
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._post('orders/cancel', True, data=params)

    def get_open_orders(self, **params):
        """Get all open orders on a symbol.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#current-open-orders-user_data

        :param symbol: optional
        :type symbol: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        .. code-block:: python

            [
                {
                    "symbol": "LTCBTC",
                    "orderId": 1,
                    "clientOrderId": "myOrder1",
                    "price": "0.1",
                    "origQty": "1.0",
                    "executedQty": "0.0",
                    "status": "NEW",
                    "timeInForce": "GTC",
                    "type": "LIMIT",
                    "side": "BUY",
                    "stopPrice": "0.0",
                    "icebergQty": "0.0",
                    "time": 1499827319559
                }
            ]

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._get('orders', True, data=params)

    # User Stream Endpoints
    def get_account(self, **params):
        """Get current account information.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#account-information-user_data

        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        .. code-block:: python

            {
                "makerCommission": 15,
                "takerCommission": 15,
                "buyerCommission": 0,
                "sellerCommission": 0,
                "canTrade": true,
                "canWithdraw": true,
                "canDeposit": true,
                "balances": [
                    {
                        "asset": "BTC",
                        "free": "4723846.89208129",
                        "locked": "0.00000000"
                    },
                    {
                        "asset": "LTC",
                        "free": "4763368.68006011",
                        "locked": "0.00000000"
                    }
                ]
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        # print('params', params)
        return self._get('account/spot', True, data=params)

    def get_asset_balance(self, asset, **params):
        """Get current asset balance.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#account-information-user_data

        :param asset: required
        :type asset: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: dictionary or None if not found

        .. code-block:: python

            {
                "asset": "BTC",
                "free": "4723846.89208129",
                "locked": "0.00000000"
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        res = self.get_account(**params)
        res = res.data
        # find asset balance in list of balances
        if "accountAssets" in res:
            for bal in res['accountAssets']:
                if bal['asset'].lower() == asset.lower():
                    return bal
        return None

    def get_my_trades(self, **params):
        """Get trades for a specific symbol.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#account-trade-list-user_data

        :param symbol: required
        :type symbol: str
        :param limit: Default 500; max 500.
        :type limit: int
        :param fromId: TradeId to fetch from. Default gets most recent trades.
        :type fromId: int
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        .. code-block:: python

            [
                {
                    "id": 28457,
                    "price": "4.00000100",
                    "qty": "12.00000000",
                    "commission": "10.10000000",
                    "commissionAsset": "BNB",
                    "time": 1499865549590,
                    "isBuyer": true,
                    "isMaker": false,
                    "isBestMatch": true
                }
            ]

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._get('orders/trades', True, data=params)

    def get_system_status(self):
        """Get system status detail.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/wapi-api.md#system-status-system

        :returns: API response

        .. code-block:: python

            {
                "status": 0,        # 0: normal，1：system maintenance
                "msg": "normal"     # normal or System maintenance.
            }

        :raises: MandalaAPIException

        """
        return self._request_withdraw_api('get', 'systemStatus.html')

    def get_account_status(self, **params):
        """Get account status detail.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/wapi-api.md#account-status-user_data

        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        .. code-block:: python

            {
                "msg": "Order failed:Low Order fill rate! Will be reactivated after 5 minutes.",
                "success": true,
                "objs": [
                    "5"
                ]
            }

        :raises: MandalaWithdrawException

        """
        res = self._request_withdraw_api('get', 'accountStatus.html', True, data=params)
        if not res['success']:
            raise MandalaWithdrawException(res['msg'])
        return res

    def get_dust_log(self, **params):
        """Get log of small amounts exchanged for BNB.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/wapi-api.md#dustlog-user_data

        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        .. code-block:: python

            {
                "success": true,
                "results": {
                    "total": 2,   //Total counts of exchange
                    "rows": [
                        {
                            "transfered_total": "0.00132256", # Total transfered BNB amount for this exchange.
                            "service_charge_total": "0.00002699",   # Total service charge amount for this exchange.
                            "tran_id": 4359321,
                            "logs": [           # Details of  this exchange.
                                {
                                    "tranId": 4359321,
                                    "serviceChargeAmount": "0.000009",
                                    "uid": "10000015",
                                    "amount": "0.0009",
                                    "operateTime": "2018-05-03 17:07:04",
                                    "transferedAmount": "0.000441",
                                    "fromAsset": "USDT"
                                },
                                {
                                    "tranId": 4359321,
                                    "serviceChargeAmount": "0.00001799",
                                    "uid": "10000015",
                                    "amount": "0.0009",
                                    "operateTime": "2018-05-03 17:07:04",
                                    "transferedAmount": "0.00088156",
                                    "fromAsset": "ETH"
                                }
                            ],
                            "operate_time": "2018-05-03 17:07:04" //The time of this exchange.
                        },
                        {
                            "transfered_total": "0.00058795",
                            "service_charge_total": "0.000012",
                            "tran_id": 4357015,
                            "logs": [       // Details of  this exchange.
                                {
                                    "tranId": 4357015,
                                    "serviceChargeAmount": "0.00001",
                                    "uid": "10000015",
                                    "amount": "0.001",
                                    "operateTime": "2018-05-02 13:52:24",
                                    "transferedAmount": "0.00049",
                                    "fromAsset": "USDT"
                                },
                                {
                                    "tranId": 4357015,
                                    "serviceChargeAmount": "0.000002",
                                    "uid": "10000015",
                                    "amount": "0.0001",
                                    "operateTime": "2018-05-02 13:51:11",
                                    "transferedAmount": "0.00009795",
                                    "fromAsset": "ETH"
                                }
                            ],
                            "operate_time": "2018-05-02 13:51:11"
                        }
                    ]
                }
            }

        :raises: MandalaWithdrawException

        """
        res = self._request_withdraw_api('get', 'userAssetDribbletLog.html', True, data=params)
        if not res['success']:
            raise MandalaWithdrawException(res['msg'])
        return res

    def transfer_dust(self, **params):
        """Convert dust assets to BNB.

        https://github.com/binance-exchange/binance-official-api-docs/blob/9dbe0e961b80557bb19708a707c7fad08842b28e/wapi-api.md#dust-transfer-user_data

        :param asset: The asset being converted. e.g: 'ONE'
        :type asset: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        .. code:: python

            result = client.transfer_dust(asset='ONE')

        :returns: API response

        .. code-block:: python

            {
                "totalServiceCharge":"0.02102542",
                "totalTransfered":"1.05127099",
                "transferResult":[
                    {
                        "amount":"0.03000000",
                        "fromAsset":"ETH",
                        "operateTime":1563368549307,
                        "serviceChargeAmount":"0.00500000",
                        "tranId":2970932918,
                        "transferedAmount":"0.25000000"
                    }
                ]
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._request_margin_api('post', 'asset/dust', True, data=params)

    def get_asset_dividend_history(self, **params):
        """Query asset dividend record.

        https://github.com/binance-exchange/binance-official-api-docs/blob/9dbe0e961b80557bb19708a707c7fad08842b28e/wapi-api.md#asset-dividend-record-user_data

        :param asset: optional
        :type asset: str
        :param startTime: optional
        :type startTime: long
        :param endTime: optional
        :type endTime: long
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        .. code:: python

            result = client.get_asset_dividend_history()

        :returns: API response

        .. code-block:: python

            {
                "rows":[
                    {
                        "amount":"10.00000000",
                        "asset":"BHFT",
                        "divTime":1563189166000,
                        "enInfo":"BHFT distribution",
                        "tranId":2968885920
                    },
                    {
                        "amount":"10.00000000",
                        "asset":"BHFT",
                        "divTime":1563189165000,
                        "enInfo":"BHFT distribution",
                        "tranId":2968885920
                    }
                ],
                "total":2
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._request_margin_api('post', 'asset/assetDividend', True, data=params)

    def get_trade_fee(self, **params):
        """Get trade fee.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/wapi-api.md#trade-fee-user_data

        :param symbol: optional
        :type symbol: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        .. code-block:: python

            {
                "tradeFee": [
                    {
                        "symbol": "ADABNB",
                        "maker": 0.9000,
                        "taker": 1.0000
                    }, {
                        "symbol": "BNBBTC",
                        "maker": 0.3000,
                        "taker": 0.3000
                    }
                ],
                "success": true
            }

        :raises: MandalaWithdrawException

        """
        res = self._request_withdraw_api('get', 'tradeFee.html', True, data=params)
        if not res['success']:
            raise MandalaWithdrawException(res['msg'])
        return res

    def get_asset_details(self, **params):
        """Fetch details on assets.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/wapi-api.md#asset-detail-user_data

        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        .. code-block:: python

            {
                "success": true,
                "assetDetail": {
                    "CTR": {
                        "minWithdrawAmount": "70.00000000", //min withdraw amount
                        "depositStatus": false,//deposit status
                        "withdrawFee": 35, // withdraw fee
                        "withdrawStatus": true, //withdraw status
                        "depositTip": "Delisted, Deposit Suspended" //reason
                    },
                    "SKY": {
                        "minWithdrawAmount": "0.02000000",
                        "depositStatus": true,
                        "withdrawFee": 0.01,
                        "withdrawStatus": true
                    }
                }
            }

        :raises: MandalaWithdrawException

        """
        res = self._request_withdraw_api('get', 'assetDetail.html', True, data=params)
        if not res['success']:
            raise MandalaWithdrawException(res['msg'])
        return res

    # Withdraw Endpoints

    def withdraw(self, **params):
        """Submit a withdraw request.

        https://www.binance.com/restapipub.html

        Assumptions:

        - You must have Withdraw permissions enabled on your API key
        - You must have withdrawn to the address specified through the website and approved the transaction via email

        :param asset: required
        :type asset: str
        :type address: required
        :type address: str
        :type addressTag: optional - Secondary address identifier for coins like XRP,XMR etc.
        :type address: str
        :param amount: required
        :type amount: decimal
        :param name: optional - Description of the address, default asset value passed will be used
        :type name: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        .. code-block:: python

            {
                "msg": "success",
                "success": true,
                "id":"7213fea8e94b4a5593d507237e5a555b"
            }

        :raises: MandalaRequestException, MandalaAPIException, MandalaWithdrawException

        """
        # force a name for the withdrawal if one not set
        if 'asset' in params and 'name' not in params:
            params['name'] = params['asset']
        res = self._request_withdraw_api('post', 'withdraw.html', True, data=params)
        if not res['success']:
            raise MandalaWithdrawException(res['msg'])
        return res

    def get_deposit_history(self, **params):
        """Fetch deposit history.

        https://www.binance.com/restapipub.html

        :param asset: optional
        :type asset: str
        :type status: 0(0:pending,1:success) optional
        :type status: int
        :param startTime: optional
        :type startTime: long
        :param endTime: optional
        :type endTime: long
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        .. code-block:: python

            {
                "depositList": [
                    {
                        "insertTime": 1508198532000,
                        "amount": 0.04670582,
                        "asset": "ETH",
                        "status": 1
                    }
                ],
                "success": true
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._request_withdraw_api('get', 'depositHistory.html', True, data=params)

    def get_withdraw_history(self, **params):
        """Fetch withdraw history.

        https://www.binance.com/restapipub.html

        :param asset: optional
        :type asset: str
        :type status: 0(0:Email Sent,1:Cancelled 2:Awaiting Approval 3:Rejected 4:Processing 5:Failure 6Completed) optional
        :type status: int
        :param startTime: optional
        :type startTime: long
        :param endTime: optional
        :type endTime: long
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        .. code-block:: python

            {
                "withdrawList": [
                    {
                        "amount": 1,
                        "address": "0x6915f16f8791d0a1cc2bf47c13a6b2a92000504b",
                        "asset": "ETH",
                        "applyTime": 1508198532000
                        "status": 4
                    },
                    {
                        "amount": 0.005,
                        "address": "0x6915f16f8791d0a1cc2bf47c13a6b2a92000504b",
                        "txId": "0x80aaabed54bdab3f6de5868f89929a2371ad21d666f20f7393d1a3389fad95a1",
                        "asset": "ETH",
                        "applyTime": 1508198532000,
                        "status": 4
                    }
                ],
                "success": true
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._request_withdraw_api('get', 'withdrawHistory.html', True, data=params)

    def get_deposit_address(self, **params):
        """Fetch a deposit address for a symbol

        https://www.binance.com/restapipub.html

        :param asset: required
        :type asset: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        .. code-block:: python

            {
                "address": "0x6915f16f8791d0a1cc2bf47c13a6b2a92000504b",
                "success": true,
                "addressTag": "1231212",
                "asset": "BNB"
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._request_withdraw_api('get', 'depositAddress.html', True, data=params)

    # User Stream Endpoints

    def stream_get_listen_key(self):
        """Start a new user data stream and return the listen key
        If a stream already exists it should return the same key.
        If the stream becomes invalid a new key is returned.

        Can be used to keep the user stream alive.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#start-user-data-stream-user_stream

        :returns: API response

        .. code-block:: python

            {
                "listenKey": "pqia91ma19a5s61cv6a81va65sdf19v8a65a1a5s61cv6a81va65sdf19v8a65a1"
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        res = self._post('userDataStream', False, data={})
        return res['listenKey']

    def stream_keepalive(self, listenKey):
        """PING a user data stream to prevent a time out.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#keepalive-user-data-stream-user_stream

        :param listenKey: required
        :type listenKey: str

        :returns: API response

        .. code-block:: python

            {}

        :raises: MandalaRequestException, MandalaAPIException

        """
        params = {
            'listenKey': listenKey
        }
        return self._put('userDataStream', False, data=params)

    def stream_close(self, listenKey):
        """Close out a user data stream.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#close-user-data-stream-user_stream

        :param listenKey: required
        :type listenKey: str

        :returns: API response

        .. code-block:: python

            {}

        :raises: MandalaRequestException, MandalaAPIException

        """
        params = {
            'listenKey': listenKey
        }
        return self._delete('userDataStream', False, data=params)

    # Margin Trading Endpoints

    def get_margin_account(self, **params):
        """Query margin account details

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/margin-api.md#query-margin-account-details-user_data

        :returns: API response

        .. code-block:: python

            {
                "borrowEnabled": true,
                "marginLevel": "11.64405625",
                "totalAssetOfBtc": "6.82728457",
                "totalLiabilityOfBtc": "0.58633215",
                "totalNetAssetOfBtc": "6.24095242",
                "tradeEnabled": true,
                "transferEnabled": true,
                "userAssets": [
                    {
                        "asset": "BTC",
                        "borrowed": "0.00000000",
                        "free": "0.00499500",
                        "interest": "0.00000000",
                        "locked": "0.00000000",
                        "netAsset": "0.00499500"
                    },
                    {
                        "asset": "BNB",
                        "borrowed": "201.66666672",
                        "free": "2346.50000000",
                        "interest": "0.00000000",
                        "locked": "0.00000000",
                        "netAsset": "2144.83333328"
                    },
                    {
                        "asset": "ETH",
                        "borrowed": "0.00000000",
                        "free": "0.00000000",
                        "interest": "0.00000000",
                        "locked": "0.00000000",
                        "netAsset": "0.00000000"
                    },
                    {
                        "asset": "USDT",
                        "borrowed": "0.00000000",
                        "free": "0.00000000",
                        "interest": "0.00000000",
                        "locked": "0.00000000",
                        "netAsset": "0.00000000"
                    }
                ]
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._request_margin_api('get', 'margin/account', True, data=params)

    def get_margin_asset(self, **params):
        """Query margin asset

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/margin-api.md#query-margin-asset-market_data

        :param asset: name of the asset
        :type asset: str

        .. code:: python

            asset_details = client.get_margin_asset(asset='BNB')

        :returns: API response

        .. code-block:: python

            {
                "assetFullName": "Mandala Coin",
                "assetName": "BNB",
                "isBorrowable": false,
                "isMortgageable": true,
                "userMinBorrow": "0.00000000",
                "userMinRepay": "0.00000000"
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._request_margin_api('get', 'margin/asset', data=params)

    def get_margin_symbol(self, **params):
        """Query margin symbol info

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/margin-api.md#query-margin-pair-market_data

        :param symbol: name of the symbol pair
        :type symbol: str

        .. code:: python

            pair_details = client.get_margin_symbol(symbol='BTCUSDT')

        :returns: API response

        .. code-block:: python

            {
                "id":323355778339572400,
                "symbol":"BTCUSDT",
                "base":"BTC",
                "quote":"USDT",
                "isMarginTrade":true,
                "isBuyAllowed":true,
                "isSellAllowed":true
            }


        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._request_margin_api('get', 'margin/pair', data=params)

    def get_margin_price_index(self, **params):
        """Query margin priceIndex

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/margin-api.md#query-margin-priceindex-market_data

        :param symbol: name of the symbol pair
        :type symbol: str

        .. code:: python

            price_index_details = client.get_margin_pair(symbol='BTCUSDT')

        :returns: API response

        .. code-block:: python

            {
                "calcTime": 1562046418000,
                "price": "0.00333930",
                "symbol": "BNBBTC"
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._request_margin_api('get', 'margin/priceIndex', data=params)

    def transfer_margin_to_spot(self, **params):
        """Execute transfer between margin account and spot account.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/margin-api.md#margin-account-transfer-margin

        :param asset: name of the asset
        :type asset: str
        :param amount: amount to transfer
        :type amount: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        .. code:: python

            transfer = client.transfer_margin_to_spot(asset='BTC', amount='1.1')

        :returns: API response

        .. code-block:: python

            {
                "tranId": 100000001
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        params['type'] = 2
        return self._request_margin_api('post', 'margin/transfer', signed=True, data=params)

    def transfer_spot_to_margin(self, **params):
        """Execute transfer between spot account and margin account.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/margin-api.md#margin-account-transfer-margin

        :param asset: name of the asset
        :type asset: str
        :param amount: amount to transfer
        :type amount: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        .. code:: python

            transfer = client.transfer_spot_to_margin(asset='BTC', amount='1.1')

        :returns: API response

        .. code-block:: python

            {
                "tranId": 100000001
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        params['type'] = 1
        return self._request_margin_api('post', 'margin/transfer', signed=True, data=params)

    def create_margin_loan(self, **params):
        """Apply for a loan.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/margin-api.md#margin-account-borrow-margin

        :param asset: name of the asset
        :type asset: str
        :param amount: amount to transfer
        :type amount: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        .. code:: python

            transaction = client.margin_create_loan(asset='BTC', amount='1.1')

        :returns: API response

        .. code-block:: python

            {
                "tranId": 100000001
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._request_margin_api('post', 'margin/loan', signed=True, data=params)

    def repay_margin_loan(self, **params):
        """Repay loan for margin account.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/margin-api.md#margin-account-repay-margin

        :param asset: name of the asset
        :type asset: str
        :param amount: amount to transfer
        :type amount: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        .. code:: python

            transaction = client.margin_repay_loan(asset='BTC', amount='1.1')

        :returns: API response

        .. code-block:: python

            {
                "tranId": 100000001
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._request_margin_api('post', 'margin/repay', signed=True, data=params)

    def create_margin_order(self, **params):
        """Post a new order for margin account.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/margin-api.md#margin-account-new-order-trade

        :param symbol: required
        :type symbol: str
        :param side: required
        :type side: str
        :param type: required
        :type type: str
        :param quantity: required
        :type quantity: decimal
        :param price: required
        :type price: str
        :param stopPrice: Used with STOP_LOSS, STOP_LOSS_LIMIT, TAKE_PROFIT, and TAKE_PROFIT_LIMIT orders.
        :type stopPrice: str
        :param timeInForce: required if limit order GTC,IOC,FOK
        :type timeInForce: str
        :param clientId: A unique id for the order. Automatically generated if not sent.
        :type clientId: str
        :param icebergQty: Used with LIMIT, STOP_LOSS_LIMIT, and TAKE_PROFIT_LIMIT to create an iceberg order.
        :type icebergQty: str
        :param newOrderRespType: Set the response JSON. ACK, RESULT, or FULL; MARKET and LIMIT order types default to
            FULL, all other orders default to ACK.
        :type newOrderRespType: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

        Response ACK:

        .. code-block:: python

            {
                "symbol": "BTCUSDT",
                "orderId": 28,
                "clientOrderId": "6gCrw2kRUAF9CvJDGP16IP",
                "transactTime": 1507725176595
            }

        Response RESULT:

        .. code-block:: python

            {
                "symbol": "BTCUSDT",
                "orderId": 28,
                "clientOrderId": "6gCrw2kRUAF9CvJDGP16IP",
                "transactTime": 1507725176595,
                "price": "1.00000000",
                "origQty": "10.00000000",
                "executedQty": "10.00000000",
                "cummulativeQuoteQty": "10.00000000",
                "status": "FILLED",
                "timeInForce": "GTC",
                "type": "MARKET",
                "side": "SELL"
            }

        Response FULL:

        .. code-block:: python

            {
                "symbol": "BTCUSDT",
                "orderId": 28,
                "clientOrderId": "6gCrw2kRUAF9CvJDGP16IP",
                "transactTime": 1507725176595,
                "price": "1.00000000",
                "origQty": "10.00000000",
                "executedQty": "10.00000000",
                "cummulativeQuoteQty": "10.00000000",
                "status": "FILLED",
                "timeInForce": "GTC",
                "type": "MARKET",
                "side": "SELL",
                "fills": [
                    {
                        "price": "4000.00000000",
                        "qty": "1.00000000",
                        "commission": "4.00000000",
                        "commissionAsset": "USDT"
                    },
                    {
                        "price": "3999.00000000",
                        "qty": "5.00000000",
                        "commission": "19.99500000",
                        "commissionAsset": "USDT"
                    },
                    {
                        "price": "3998.00000000",
                        "qty": "2.00000000",
                        "commission": "7.99600000",
                        "commissionAsset": "USDT"
                    },
                    {
                        "price": "3997.00000000",
                        "qty": "1.00000000",
                        "commission": "3.99700000",
                        "commissionAsset": "USDT"
                    },
                    {
                        "price": "3995.00000000",
                        "qty": "1.00000000",
                        "commission": "3.99500000",
                        "commissionAsset": "USDT"
                    }
                ]
            }

        :raises: MandalaRequestException, MandalaAPIException, MandalaOrderException, MandalaOrderMinAmountException,
            MandalaOrderMinPriceException, MandalaOrderMinTotalException, MandalaOrderUnknownSymbolException,
            MandalaOrderInactiveSymbolException

        """
        return self._request_margin_api('post', 'margin/order', signed=True, data=params)

    def cancel_margin_order(self, **params):
        """Cancel an active order for margin account.

        Either orderId or origClientOrderId must be sent.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/margin-api.md#margin-account-cancel-order-trade

        :param symbol: required
        :type symbol: str
        :param orderId:
        :type orderId: str
        :param origClientOrderId:
        :type origClientOrderId: str
        :param clientId: Used to uniquely identify this cancel. Automatically generated by default.
        :type clientId: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

            {
                "symbol": "LTCBTC",
                "orderId": 28,
                "origClientOrderId": "myOrder1",
                "clientOrderId": "cancelMyOrder1",
                "transactTime": 1507725176595,
                "price": "1.00000000",
                "origQty": "10.00000000",
                "executedQty": "8.00000000",
                "cummulativeQuoteQty": "8.00000000",
                "status": "CANCELED",
                "timeInForce": "GTC",
                "type": "LIMIT",
                "side": "SELL"
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._request_margin_api('delete', 'margin/order', signed=True, data=params)

    def get_margin_loan_details(self, **params):
        """Query loan record

        txId or startTime must be sent. txId takes precedence.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/margin-api.md#margin-account-cancel-order-trade

        :param asset: required
        :type asset: str
        :param txId: the tranId in of the created loan
        :type txId: str
        :param startTime:
        :type startTime: str
        :param endTime: Used to uniquely identify this cancel. Automatically generated by default.
        :type endTime: str
        :param current: Currently querying page. Start from 1. Default:1
        :type current: str
        :param size: Default:10 Max:100
        :type size: int
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

            {
                "rows": [
                    {
                        "asset": "BNB",
                        "principal": "0.84624403",
                        "timestamp": 1555056425000,
                        //one of PENDING (pending to execution), CONFIRMED (successfully loaned), FAILED (execution failed, nothing happened to your account);
                        "status": "CONFIRMED"
                    }
                ],
                "total": 1
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._request_margin_api('get', 'margin/loan', signed=True, data=params)

    def get_margin_repay_details(self, **params):
        """Query repay record

        txId or startTime must be sent. txId takes precedence.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/margin-api.md#margin-account-cancel-order-trade

        :param asset: required
        :type asset: str
        :param txId: the tranId in of the created loan
        :type txId: str
        :param startTime:
        :type startTime: str
        :param endTime: Used to uniquely identify this cancel. Automatically generated by default.
        :type endTime: str
        :param current: Currently querying page. Start from 1. Default:1
        :type current: str
        :param size: Default:10 Max:100
        :type size: int
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

            {
                "rows": [
                    {
                        //Total amount repaid
                        "amount": "14.00000000",
                        "asset": "BNB",
                        //Interest repaid
                        "interest": "0.01866667",
                        //Principal repaid
                        "principal": "13.98133333",
                        //one of PENDING (pending to execution), CONFIRMED (successfully loaned), FAILED (execution failed, nothing happened to your account);
                        "status": "CONFIRMED",
                        "timestamp": 1563438204000,
                        "txId": 2970933056
                    }
                ],
                "total": 1
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._request_margin_api('get', 'margin/repay', signed=True, data=params)

    def get_margin_order(self, **params):
        """Query margin accounts order

        Either orderId or origClientOrderId must be sent.

        For some historical orders cummulativeQuoteQty will be < 0, meaning the data is not available at this time.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/margin-api.md#query-margin-accounts-order-user_data

        :param symbol: required
        :type symbol: str
        :param orderId:
        :type orderId: str
        :param origClientOrderId:
        :type origClientOrderId: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

            {
                "clientOrderId": "ZwfQzuDIGpceVhKW5DvCmO",
                "cummulativeQuoteQty": "0.00000000",
                "executedQty": "0.00000000",
                "icebergQty": "0.00000000",
                "isWorking": true,
                "orderId": 213205622,
                "origQty": "0.30000000",
                "price": "0.00493630",
                "side": "SELL",
                "status": "NEW",
                "stopPrice": "0.00000000",
                "symbol": "BNBBTC",
                "time": 1562133008725,
                "timeInForce": "GTC",
                "type": "LIMIT",
                "updateTime": 1562133008725
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._request_margin_api('get', 'margin/order', signed=True, data=params)

    def get_open_margin_orders(self, **params):
        """Query margin accounts open orders

        If the symbol is not sent, orders for all symbols will be returned in an array.

        When all symbols are returned, the number of requests counted against the rate limiter is equal to the number
        of symbols currently trading on the exchange.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/margin-api.md#query-margin-accounts-open-order-user_data

        :param symbol: optional
        :type symbol: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

            [
                {
                    "clientOrderId": "qhcZw71gAkCCTv0t0k8LUK",
                    "cummulativeQuoteQty": "0.00000000",
                    "executedQty": "0.00000000",
                    "icebergQty": "0.00000000",
                    "isWorking": true,
                    "orderId": 211842552,
                    "origQty": "0.30000000",
                    "price": "0.00475010",
                    "side": "SELL",
                    "status": "NEW",
                    "stopPrice": "0.00000000",
                    "symbol": "BNBBTC",
                    "time": 1562040170089,
                    "timeInForce": "GTC",
                    "type": "LIMIT",
                    "updateTime": 1562040170089
                }
            ]

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._request_margin_api('get', 'margin/openOrders', signed=True, data=params)

    def get_all_margin_orders(self, **params):
        """Query all margin accounts orders

        If orderId is set, it will get orders >= that orderId. Otherwise most recent orders are returned.

        For some historical orders cummulativeQuoteQty will be < 0, meaning the data is not available at this time.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/margin-api.md#query-margin-accounts-open-order-user_data

        :param symbol: required
        :type symbol: str
        :param orderId: optional
        :type orderId: str
        :param startTime: optional
        :type startTime: str
        :param endTime: optional
        :type endTime: str
        :param limit: Default 500; max 1000
        :type limit: int
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

            [
                {
                    "id": 43123876,
                    "price": "0.00395740",
                    "qty": "4.06000000",
                    "quoteQty": "0.01606704",
                    "symbol": "BNBBTC",
                    "time": 1556089977693
                },
                {
                    "id": 43123877,
                    "price": "0.00395740",
                    "qty": "0.77000000",
                    "quoteQty": "0.00304719",
                    "symbol": "BNBBTC",
                    "time": 1556089977693
                },
                {
                    "id": 43253549,
                    "price": "0.00428930",
                    "qty": "23.30000000",
                    "quoteQty": "0.09994069",
                    "symbol": "BNBBTC",
                    "time": 1556163963504
                }
            ]


        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._request_margin_api('get', 'margin/allOrders', signed=True, data=params)

    def get_margin_trades(self, **params):
        """Query margin accounts trades

        If fromId is set, it will get orders >= that fromId. Otherwise most recent orders are returned.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/margin-api.md#query-margin-accounts-trade-list-user_data

        :param symbol: required
        :type symbol: str
        :param fromId: optional
        :type fromId: str
        :param startTime: optional
        :type startTime: str
        :param endTime: optional
        :type endTime: str
        :param limit: Default 500; max 1000
        :type limit: int
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

            [
                {
                    "commission": "0.00006000",
                    "commissionAsset": "BTC",
                    "id": 34,
                    "isBestMatch": true,
                    "isBuyer": false,
                    "isMaker": false,
                    "orderId": 39324,
                    "price": "0.02000000",
                    "qty": "3.00000000",
                    "symbol": "BNBBTC",
                    "time": 1561973357171
                }, {
                    "commission": "0.00002950",
                    "commissionAsset": "BTC",
                    "id": 32,
                    "isBestMatch": true,
                    "isBuyer": false,
                    "isMaker": true,
                    "orderId": 39319,
                    "price": "0.00590000",
                    "qty": "5.00000000",
                    "symbol": "BNBBTC",
                    "time": 1561964645345
                }
            ]


        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._request_margin_api('get', 'margin/myTrades', signed=True, data=params)

    def get_max_margin_loan(self, **params):
        """Query max borrow amount for an asset

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/margin-api.md#query-max-borrow-user_data

        :param asset: required
        :type asset: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

            {
                "amount": "1.69248805"
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._request_margin_api('get', 'margin/maxBorrowable', signed=True, data=params)

    def get_max_margin_transfer(self, **params):
        """Query max transfer-out amount

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/margin-api.md#query-max-transfer-out-amount-user_data

        :param asset: required
        :type asset: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int

        :returns: API response

            {
                "amount": "3.59498107"
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._request_margin_api('get', 'margin/maxTransferable', signed=True, data=params)

    def margin_stream_get_listen_key(self):
        """Start a new margin data stream and return the listen key
        If a stream already exists it should return the same key.
        If the stream becomes invalid a new key is returned.

        Can be used to keep the user stream alive.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/margin-api.md#start-user-data-stream-for-margin-account-user_stream

        :returns: API response

        .. code-block:: python

            {
                "listenKey": "pqia91ma19a5s61cv6a81va65sdf19v8a65a1a5s61cv6a81va65sdf19v8a65a1"
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        res = self._request_margin_api('post', 'userDataStream', signed=True, data={})
        return res['listenKey']

    def margin_stream_keepalive(self, listenKey):
        """PING a margin data stream to prevent a time out.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/margin-api.md#ping-user-data-stream-for-margin-account--user_stream

        :param listenKey: required
        :type listenKey: str

        :returns: API response

        .. code-block:: python

            {}

        :raises: MandalaRequestException, MandalaAPIException

        """
        params = {
            'listenKey': listenKey
        }
        return self._request_margin_api('put', 'userDataStream', signed=True, data=params)

    def margin_stream_close(self, listenKey):
        """Close out a margin data stream.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/margin-api.md#delete-user-data-stream-for-margin-account--user_stream

        :param listenKey: required
        :type listenKey: str

        :returns: API response

        .. code-block:: python

            {}

        :raises: MandalaRequestException, MandalaAPIException

        """
        params = {
            'listenKey': listenKey
        }
        return self._request_margin_api('delete', 'userDataStream', signed=True, data=params)

    # Lending Endpoints

    def get_lending_product_list(self, **params):
        """Get Lending Product List

        https://binance-docs.github.io/apidocs/spot/en/#get-flexible-product-list-user_data

        """
        return self._request_margin_api('get', 'lending/daily/product/list ', signed=True, data=params)

    def get_lending_daily_quota_left(self, **params):
        """Get Left Daily Purchase Quota of Flexible Product.

        https://binance-docs.github.io/apidocs/spot/en/#get-left-daily-purchase-quota-of-flexible-product-user_data

        """
        return self._request_margin_api('get', 'lending/daily/userLeftQuota', signed=True, data=params)

    def purchase_lending_product(self, **params):
        """Purchase Flexible Product

        https://binance-docs.github.io/apidocs/spot/en/#purchase-flexible-product-user_data

        """
        return self._request_margin_api('post', 'lending/daily/purchase', signed=True, data=params)

    def get_lending_daily_redemption_quota(self, **params):
        """Get Left Daily Redemption Quota of Flexible Product

        https://binance-docs.github.io/apidocs/spot/en/#get-left-daily-redemption-quota-of-flexible-product-user_data

        """
        return self._request_margin_api('get', 'lending/daily/userRedemptionQuota', signed=True, data=params)

    def redeem_lending_product(self, **params):
        """Redeem Flexible Product

        https://binance-docs.github.io/apidocs/spot/en/#redeem-flexible-product-user_data

        """
        return self._request_margin_api('post', 'lending/daily/redeem', signed=True, data=params)

    def get_lending_position(self, **params):
        """Get Flexible Product Position

        https://binance-docs.github.io/apidocs/spot/en/#get-flexible-product-position-user_data

        """
        return self._request_margin_api('get', 'lending/daily/token/position', signed=True, data=params)

    def get_lending_account(self, **params):
        """Get Lending Account Details

        https://binance-docs.github.io/apidocs/spot/en/#lending-account-user_data

        """
        return self._request_margin_api('get', 'lending/union/account', signed=True, data=params)

    def get_lending_purchase_history(self, **params):
        """Get Lending Purchase History

        https://binance-docs.github.io/apidocs/spot/en/#get-purchase-record-user_data

        """
        return self._request_margin_api('get', 'lending/union/purchaseRecord', signed=True, data=params)

    def get_lending_redemption_history(self, **params):
        """Get Lending Redemption History

        https://binance-docs.github.io/apidocs/spot/en/#get-redemption-record-user_data

        """
        return self._request_margin_api('get', 'lending/union/redemptionRecord', signed=True, data=params)

    def get_lending_interest_history(self, **params):
        """Get Lending Interest History

        https://binance-docs.github.io/apidocs/spot/en/#get-interest-history-user_data-2

        """
        return self._request_margin_api('get', 'lending/union/interestHistory', signed=True, data=params)

    # Sub Accounts

    def get_sub_account_list(self, **params):
        """Query Sub-account List.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/wapi-api.md#query-sub-account-listfor-master-account

        :param email: optional
        :type email: str
        :param startTime: optional
        :type startTime: int
        :param endTime: optional
        :type endTime: int
        :param page: optional
        :type page: int
        :param limit: optional
        :type limit: int
        :param recvWindow: optional
        :type recvWindow: int

        :returns: API response

        .. code-block:: python

            {
                "success":true,
                "subAccounts":[
                    {
                        "email":"123@test.com",
                        "status":"enabled",
                        "activated":true,
                        "mobile":"91605290",
                        "gAuth":true,
                        "createTime":1544433328000
                    },
                    {
                        "email":"321@test.com",
                        "status":"disabled",
                        "activated":true,
                        "mobile":"22501238",
                        "gAuth":true,
                        "createTime":1544433328000
                    }
                ]
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._request_withdraw_api('get', 'sub-account/list.html', True, data=params)

    def get_sub_account_transfer_history(self, **params):
        """Query Sub-account Transfer History.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/wapi-api.md#query-sub-account-transfer-historyfor-master-account

        :param email: required
        :type email: str
        :param startTime: optional
        :type startTime: int
        :param endTime: optional
        :type endTime: int
        :param page: optional
        :type page: int
        :param limit: optional
        :type limit: int
        :param recvWindow: optional
        :type recvWindow: int

        :returns: API response

        .. code-block:: python

            {
                "success":true,
                "transfers":[
                    {
                        "from":"aaa@test.com",
                        "to":"bbb@test.com",
                        "asset":"BTC",
                        "qty":"1",
                        "time":1544433328000
                    },
                    {
                        "from":"bbb@test.com",
                        "to":"ccc@test.com",
                        "asset":"ETH",
                        "qty":"2",
                        "time":1544433328000
                    }
                ]
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._request_withdraw_api('get', 'sub-account/transfer/history.html', True, data=params)

    def create_sub_account_transfer(self, **params):
        """Execute sub-account transfer

        https://github.com/binance-exchange/binance-official-api-docs/blob/9dbe0e961b80557bb19708a707c7fad08842b28e/wapi-api.md#sub-account-transferfor-master-account

        :param fromEmail: required - Sender email
        :type fromEmail: str
        :param toEmail: required - Recipient email
        :type toEmail: str
        :param asset: required
        :type asset: str
        :param amount: required
        :type amount: decimal
        :param recvWindow: optional
        :type recvWindow: int

        :returns: API response

        .. code-block:: python

            {
                "success":true,
                "txnId":"2966662589"
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._request_withdraw_api('post', 'sub-account/transfer.html', True, data=params)

    def get_sub_account_assets(self, **params):
        """Fetch sub-account assets

        https://github.com/binance-exchange/binance-official-api-docs/blob/9dbe0e961b80557bb19708a707c7fad08842b28e/wapi-api.md#query-sub-account-assetsfor-master-account

        :param email: required
        :type email: str
        :param symbol: optional
        :type symbol: str
        :param recvWindow: optional
        :type recvWindow: int

        :returns: API response

        .. code-block:: python

            {
                "success":true,
                "balances":[
                    {
                        "asset":"ADA",
                        "free":10000,
                        "locked":0
                    },
                    {
                        "asset":"BNB",
                        "free":10003,
                        "locked":0
                    },
                    {
                        "asset":"BTC",
                        "free":11467.6399,
                        "locked":0
                    },
                    {
                        "asset":"ETH",
                        "free":10004.995,
                        "locked":0
                    },
                    {
                        "asset":"USDT",
                        "free":11652.14213,
                        "locked":0
                    }
                ]
            }

        :raises: MandalaRequestException, MandalaAPIException

        """
        return self._request_withdraw_api('get', 'sub-account/assets.html', True, data=params)

    # Futures API

    def futures_ping(self):
        """Test connectivity to the Rest API

        https://binance-docs.github.io/apidocs/futures/en/#test-connectivity

        """
        return self._request_futures_api('get', 'ping')

    def futures_time(self):
        """Test connectivity to the Rest API and get the current server time.

        https://binance-docs.github.io/apidocs/futures/en/#check-server-time

        """
        return self._request_futures_api('get', 'time')

    def futures_exchange_info(self):
        """Current exchange trading rules and symbol information

        https://binance-docs.github.io/apidocs/futures/en/#exchange-information-market_data

        """
        return self._request_futures_api('get', 'exchangeInfo')

    def futures_order_book(self, **params):
        """Get the Order Book for the market

        https://binance-docs.github.io/apidocs/futures/en/#order-book-market_data

        """
        return self._request_futures_api('get', 'depth', data=params)

    def futures_recent_trades(self, **params):
        """Get recent trades (up to last 500).

        https://binance-docs.github.io/apidocs/futures/en/#recent-trades-list-market_data

        """
        return self._request_futures_api('get', 'trades', data=params)

    def futures_historical_trades(self, **params):
        """Get older market historical trades.

        https://binance-docs.github.io/apidocs/futures/en/#old-trades-lookup-market_data

        """
        return self._request_futures_api('get', 'historicalTrades', data=params)

    def futures_aggregate_trades(self, **params):
        """Get compressed, aggregate trades. Trades that fill at the time, from the same order, with the same
        price will have the quantity aggregated.

        https://binance-docs.github.io/apidocs/futures/en/#compressed-aggregate-trades-list-market_data

        """
        return self._request_futures_api('get', 'aggTrades', data=params)

    def futures_klines(self, **params):
        """Kline/candlestick bars for a symbol. Klines are uniquely identified by their open time.

        https://binance-docs.github.io/apidocs/futures/en/#kline-candlestick-data-market_data

        """
        return self._request_futures_api('get', 'klines', data=params)

    def futures_mark_price(self, **params):
        """Get Mark Price and Funding Rate

        https://binance-docs.github.io/apidocs/futures/en/#mark-price-market_data

        """
        return self._request_futures_api('get', 'premiumIndex', data=params)

    def futures_funding_rate(self, **params):
        """Get funding rate history

        https://binance-docs.github.io/apidocs/futures/en/#get-funding-rate-history-market_data

        """
        return self._request_futures_api('get', 'fundingRate', data=params)

    def futures_ticker(self, **params):
        """24 hour rolling window price change statistics.

        https://binance-docs.github.io/apidocs/futures/en/#24hr-ticker-price-change-statistics-market_data

        """
        return self._request_futures_api('get', 'ticker/24hr', data=params)

    def futures_symbol_ticker(self, **params):
        """Latest price for a symbol or symbols.

        https://binance-docs.github.io/apidocs/futures/en/#symbol-price-ticker-market_data

        """
        return self._request_futures_api('get', 'ticker/price', data=params)

    def futures_orderbook_ticker(self, **params):
        """Best price/qty on the order book for a symbol or symbols.

        https://binance-docs.github.io/apidocs/futures/en/#symbol-order-book-ticker-market_data

        """
        return self._request_futures_api('get', 'ticker/bookTicker', data=params)

    def futures_liquidation_orders(self, **params):
        """Get all liquidation orders

        https://binance-docs.github.io/apidocs/futures/en/#get-all-liquidation-orders-market_data

        """
        return self._request_futures_api('get', 'ticker/allForceOrders', data=params)

    def futures_open_interest(self, **params):
        """Get present open interest of a specific symbol.

        https://binance-docs.github.io/apidocs/futures/en/#open-interest-market_data

        """
        return self._request_futures_api('get', 'ticker/openInterest', data=params)

    def futures_leverage_bracket(self, **params):
        """Notional and Leverage Brackets

        https://binance-docs.github.io/apidocs/futures/en/#notional-and-leverage-brackets-market_data

        """
        return self._request_futures_api('get', 'ticker/leverageBracket', data=params)

    def transfer_history(self, **params):
        """Get future account transaction history list

        https://binance-docs.github.io/apidocs/futures/en/#new-future-account-transfer

        """
        return self._request_margin_api('get', 'futures/transfer', True, data=params)

    def futures_create_order(self, **params):
        """Send in a new order.

        https://binance-docs.github.io/apidocs/futures/en/#new-order-trade

        """
        return self._request_futures_api('post', 'order', True, data=params)

    def futures_get_order(self, **params):
        """Check an order's status.

        https://binance-docs.github.io/apidocs/futures/en/#query-order-user_data

        """
        return self._request_futures_api('get', 'order', True, data=params)

    def futures_get_open_orders(self, **params):
        """Get all open orders on a symbol.

        https://binance-docs.github.io/apidocs/futures/en/#current-open-orders-user_data

        """
        return self._request_futures_api('get', 'openOrders', True, data=params)

    def futures_get_all_orders(self, **params):
        """Get all futures account orders; active, canceled, or filled.

        https://binance-docs.github.io/apidocs/futures/en/#all-orders-user_data

        """
        return self._request_futures_api('get', 'allOrders', True, data=params)

    def futures_cancel_order(self, **params):
        """Cancel an active futures order.

        https://binance-docs.github.io/apidocs/futures/en/#cancel-order-trade

        """
        return self._request_futures_api('delete', 'order', True, data=params)

    def futures_cancel_all_open_orders(self, **params):
        """Cancel all open futures orders

        https://binance-docs.github.io/apidocs/futures/en/#cancel-all-open-orders-trade

        """
        return self._request_futures_api('delete', 'allOpenOrders', True, data=params)

    def futures_cancel_orders(self, **params):
        """Cancel multiple futures orders

        https://binance-docs.github.io/apidocs/futures/en/#cancel-multiple-orders-trade

        """
        return self._request_futures_api('delete', 'batchOrders', True, data=params)

    def futures_account_balance(self, **params):
        """Get futures account balance

        https://binance-docs.github.io/apidocs/futures/en/#future-account-balance-user_data

        """
        return self._request_futures_api('get', 'account/spot', True, data=params)

    def futures_account(self, **params):
        """Get current account information.

        https://binance-docs.github.io/apidocs/futures/en/#account-information-user_data

        """
        return self._request_futures_api('get', 'account', True, data=params)

    def futures_change_leverage(self, **params):
        """Change user's initial leverage of specific symbol market

        https://binance-docs.github.io/apidocs/futures/en/#change-initial-leverage-trade

        """
        return self._request_futures_api('post', 'leverage', True, data=params)

    def futures_change_margin_type(self, **params):
        """Change the margin type for a symbol

        https://binance-docs.github.io/apidocs/futures/en/#change-margin-type-trade

        """
        return self._request_futures_api('post', 'marginType', True, data=params)

    def futures_change_position_margin(self, **params):
        """Change the position margin for a symbol

        https://binance-docs.github.io/apidocs/futures/en/#modify-isolated-position-margin-trade

        """
        return self._request_futures_api('post', 'positionMargin', True, data=params)

    def futures_position_margin_history(self, **params):
        """Get position margin change history

        https://binance-docs.github.io/apidocs/futures/en/#get-postion-margin-change-history-trade

        """
        return self._request_futures_api('get', 'positionMargin/history', True, data=params)

    def futures_position_information(self, **params):
        """Get position information

        https://binance-docs.github.io/apidocs/futures/en/#position-information-user_data

        """
        return self._request_futures_api('get', 'positionRisk', True, data=params)

    def futures_account_trades(self, **params):
        """Get trades for the authenticated account and symbol.

        https://binance-docs.github.io/apidocs/futures/en/#account-trade-list-user_data

        """
        return self._request_futures_api('get', 'userTrades', True, data=params)

    def futures_income_history(self, **params):
        """Get income history for authenticated account

        https://binance-docs.github.io/apidocs/futures/en/#get-income-history-user_data

        """
        return self._request_futures_api('get', 'income', True, data=params)
