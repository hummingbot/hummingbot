BALANCES = {
    'id': 815129178419638016, 'method': 'private/get-account-summary', 'code': 0,
    'result': {
        'accounts': [{'balance': 50, 'available': 50, 'order': 0.0, 'stake': 0, 'currency': 'USDT'},
                     {'balance': 0.002, 'available': 0.002, 'order': 0, 'stake': 0, 'currency': 'BTC'}]
    }
}

INSTRUMENTS = {'id': -1, 'method': 'public/get-instruments', 'code': 0, 'result': {'instruments': [
    {'instrument_name': 'BTC_USDT', 'quote_currency': 'USDT', 'base_currency': 'BTC', 'price_decimals': 2,
     'quantity_decimals': 6},
    {'instrument_name': 'ETH_USDT', 'quote_currency': 'USDT', 'base_currency': 'ETH', 'price_decimals': 2,
     'quantity_decimals': 5},
]}}

TICKERS = {'code': 0, 'method': 'public/get-ticker', 'result': {
    'instrument_name': 'BTC_USDT',
    'data': [{'i': 'BTC_USDT', 'b': 11490.0, 'k': 11492.05,
              'a': 11490.0, 't': 1598674849297,
              'v': 754.531926, 'h': 11546.11, 'l': 11366.62,
              'c': 104.19}]}}

GET_BOOK = {
    "code": 0, "method": "public/get-book", "result": {
        "instrument_name": "BTC_USDT", "depth": 5, "data":
            [{"bids": [[11490.00, 0.010676, 1], [11488.34, 0.055374, 1], [11487.47, 0.003000, 1],
                       [11486.50, 0.031032, 1],
                       [11485.97, 0.087074, 1]],
              "asks": [[11492.05, 0.232044, 1], [11492.06, 0.497900, 1], [11493.12, 2.005693, 1],
                       [11494.12, 7.000000, 1],
                       [11494.41, 0.032853, 1]], "t": 1598676097390}]}}

PLACE_ORDER = {'id': 632194937848317440, 'method': 'private/create-order', 'code': 0,
               'result': {'order_id': '1', 'client_oid': 'buy-BTC-USDT-1598607082008742'}}

CANCEL = {'id': 31484728768575776, 'method': 'private/cancel-order', 'code': 0}

UNFILLED_ORDER = {
    'id': 798015906490506624,
    'method': 'private/get-order-detail',
    'code': 0,
    'result': {
        'trade_list': [],
        'order_info': {
            'status': 'ACTIVE',
            'side': 'BUY',
            'price': 9164.82,
            'quantity': 0.0001,
            'order_id': '1',
            'client_oid': 'buy-BTC-USDT-1598607082008742',
            'create_time': 1598607082329,
            'update_time': 1598607082332,
            'type': 'LIMIT',
            'instrument_name': 'BTC_USDT',
            'avg_price': 0.0,
            'cumulative_quantity': 0.0,
            'cumulative_value': 0.0,
            'fee_currency': 'BTC',
            'exec_inst': 'POST_ONLY',
            'time_in_force': 'GOOD_TILL_CANCEL'}
    }
}

WS_INITIATED = {'id': 317343764453238848, 'method': 'public/auth', 'code': 0}
WS_SUBSCRIBE = {'id': 802984382214439040, 'method': 'subscribe', 'code': 0}
WS_HEARTBEAT = {'id': 1598755526207, 'method': 'public/heartbeat'}

WS_ORDER_FILLED = {
    'id': -1, 'method': 'subscribe', 'code': 0,
    'result': {
        'instrument_name': 'BTC_USDT',
        'subscription': 'user.order.BTC_USDT',
        'channel': 'user.order',
        'data': [
            {'status': 'FILLED',
             'side': 'BUY',
             'price': 12080.9,
             'quantity': 0.0001,
             'order_id': '1',
             'client_oid': 'buy-BTC-USDT-1598681216010994',
             'create_time': 1598681216332,
             'update_time': 1598681216334,
             'type': 'LIMIT',
             'instrument_name': 'BTC_USDT',
             'avg_price': 11505.62,
             'cumulative_quantity': 0.0001,
             'cumulative_value': 11.50562,
             'fee_currency': 'BTC',
             'exec_inst': '',
             'time_in_force': 'GOOD_TILL_CANCEL'}]}}

WS_TRADE = {
    'id': -1, 'method': 'subscribe', 'code': 0,
    'result': {
        'instrument_name': 'BTC_USDT',
        'subscription': 'user.trade.BTC_USDT',
        'channel': 'user.trade',
        'data': [
            {'side': 'BUY',
             'fee': 1.6e-06,
             'trade_id': '699422550491763776',
             'instrument_name': 'BTC_USDT',
             'create_time': 1598681216334,
             'traded_price': 11505.62,
             'traded_quantity': 0.0001,
             'fee_currency': 'BTC',
             'order_id': '1'}]}}

WS_BALANCE = {
    'id': -1, 'method': 'subscribe', 'code': 0,
    'result': {
        'subscription': 'user.balance', 'channel': 'user.balance',
        'data': [{'balance': 47, 'available': 46,
                  'order': 1, 'stake': 0,
                  'currency': 'USDT'}]}}

WS_ORDER_CANCELLED = {
    'id': -1, 'method': 'subscribe', 'code': 0,
    'result': {
        'instrument_name': 'BTC_USDT', 'subscription': 'user.order.BTC_USDT',
        'channel': 'user.order', 'data': [
            {'status': 'CANCELED', 'side': 'BUY', 'price': 13918.12, 'quantity': 0.0001,
             'order_id': '1', 'client_oid': 'buy-BTC-USDT-1598757896008300',
             'create_time': 1598757896312, 'update_time': 1598757896312, 'type': 'LIMIT',
             'instrument_name': 'BTC_USDT', 'avg_price': 0.0, 'cumulative_quantity': 0.0,
             'cumulative_value': 0.0, 'fee_currency': 'BTC', 'exec_inst': 'POST_ONLY',
             'time_in_force': 'GOOD_TILL_CANCEL'}]}}
