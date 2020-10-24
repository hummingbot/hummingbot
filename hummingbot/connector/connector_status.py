#!/usr/bin/env python

connector_status = {
    'binance': 'ok',
    'bitfinex': 'ok',
    'bittrex': 'warning',
    'celo': 'ok',
    'coinbase_pro': 'ok',
    'crypto_com': 'warning',
    'eterbase': 'unavailable',
    'ethereum': 'unavailable',
    'huobi': 'ok',
    'kraken': 'warning',
    'kucoin': 'ok',
    'liquid': 'ok',
    'loopring': 'ok'
}


def get_connector_status(connector_name: str) -> str:
    """
    Indicator whether a connector is working properly or not. Unknown means the connector is not in the dict.
    Unavailable means a connector doesn't work, Warning means the connector works but has issues.
    Ok means a connector is working properly. The connector_status dict is updated every new release.
    """
    if connector_name not in connector_status.keys():
        status = "Unknown"
    else:
        return connector_status[connector_name].capitalize()
    return status
