#!/usr/bin/env python

def get_connector_status(connector_name: str) -> str:
    """
    Dictates whether a connector is working properly or not. Unknown means the connector is not in the dict
    Broken means a connector doesn't work, Warning means the connector works but has issues
    Ok means a connector is working properly. The connector_status dict is updated every new release
    """
    connector_status = {
        'binance': 'broken',
        'bitfinex': 'broken',
        'bittrex': 'warning',
        'celo': 'ok',
        'coinbase_pro': 'broken',
        'crypto_com': 'ok',
        'eterbase': 'ok',
        'ethereum': 'ok',
        'huobi': 'broken',
        'kraken': 'warning',
        'kucoin': 'broken',
        'liquid': 'warning',
        'loopring': 'ok'
    }
    if connector_name not in connector_status.keys():
        status = "Unknown"
    elif connector_status[connector_name] == 'broken':
        status = "Broken"
    elif connector_status[connector_name] == 'warning':
        status = "Warning"
    else:
        status = "Ok"
    return status
