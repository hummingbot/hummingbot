#!/usr/bin/env python

connector_status = {
    'binance': 'green',
    'binance_us': 'yellow',
    'bitfinex': 'green',
    'bittrex': 'yellow',
    'celo': 'green',
    'coinbase_pro': 'green',
    'crypto_com': 'yellow',
    'eterbase': 'red',
    'ethereum': 'red',
    'huobi': 'green',
    'kraken': 'yellow',
    'kucoin': 'green',
    'liquid': 'green',
    'loopring': 'green'
}


def get_connector_status(connector_name: str) -> str:
    """
    Indicator whether a connector is working properly or not. Unknown means the connector is not in the dict.
    Unavailable means a connector doesn't work, Warning means the connector works but has issues.
    Ok means a connector is working properly. The connector_status dict is updated every new release.
    """
    if connector_name not in connector_status.keys():
        status = "UNKNOWN"
    else:
        return connector_status[connector_name].upper()
    return status
