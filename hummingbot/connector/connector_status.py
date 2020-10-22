#!/usr/bin/env python

def get_connector_status(connector_name: str) -> str:
    """
    Indicator whether a connector is working properly or not. Unknown means the connector is not in the dict.
    Unavailable means a connector doesn't work, Warning means the connector works but has issues.
    Ok means a connector is working properly. The connector_status dict is updated every new release.
    """
    connector_status = {
        'binance': 'unavailable',
        'bitfinex': 'unavailable',
        'bittrex': 'warning',
        'celo': 'ok',
        'coinbase_pro': 'unavailable',
        'crypto_com': 'ok',
        'eterbase': 'ok',
        'ethereum': 'ok',
        'huobi': 'unavailable',
        'kraken': 'warning',
        'kucoin': 'unavailable',
        'liquid': 'warning',
        'loopring': 'ok'
    }
    if connector_name not in connector_status.keys():
        status = "Unknown"
    elif connector_status[connector_name] == 'unavailable':
        status = "Unavailable"
    elif connector_status[connector_name] == 'warning':
        status = "Warning"
    else:
        status = "Ok"
    return status
