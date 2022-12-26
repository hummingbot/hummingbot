#!/usr/bin/env python

connector_status = {
    'altmarkets': 'green',
    'ascend_ex': 'yellow',
    'balancer': 'green',
    'beaxy': 'green',
    'binance': 'green',
    'binance_perpetual': 'yellow',
    'binance_perpetual_testnet': 'yellow',
    'binance_us': 'green',
    'bitfinex': 'yellow',
    'bitget_perpetual': 'yellow',
    'bitmart': 'yellow',
    'bittrex': 'yellow',
    'bitmex': 'green',
    'bitmex_perpetual': 'green',
    'bitmex_testnet': 'yellow',
    'bitmex_perpetual_testnet': 'yellow',
    'btc_markets': 'yellow',
    'bybit_perpetual': 'green',
    'bybit_perpetual_testnet': 'yellow',
    'bybit_testnet': 'yellow',
    'bybit': 'green',
    'celo': 'yellow',
    'coinbase_pro': 'yellow',
    'coinzoom': 'yellow',
    'crypto_com': 'green',
    'digifinex': "yellow",
    'dydx_perpetual': 'yellow',
    'ethereum': 'red',
    'eve': 'yellow',
    'eve_staging': 'yellow',
    'gate_io': 'yellow',
    'gate_io_perpetual': 'yellow',
    'hitbtc': 'green',
    'huobi': 'green',
    'kraken': 'green',
    'kucoin': 'yellow',
    'kucoin_testnet': 'yellow',
    'k2': 'red',
    'latoken': 'green',
    'lbank': 'yellow',
    'liquid': 'green',
    'loopring': 'yellow',
    'mexc': 'yellow',
    'ndax': 'yellow',
    'ndax_testnet': 'yellow',
    'okx': 'green',
    'perpetual_finance': 'yellow',
    'probit': 'yellow',
    'probit_kr': 'yellow',
    'terra': 'red',
    'uniswap': 'yellow',
    'uniswap_v3': 'yellow',
    'wazirx': 'yellow',
    'whitebit': 'yellow'
}

warning_messages = {
}


def get_connector_status(connector_name: str) -> str:
    """
    Indicator whether a connector is working properly or not.
    UNKNOWN means the connector is not in connector_status dict.
    RED means a connector doesn't work.
    YELLOW means the connector is either new or has one or more issues.
    GREEN means a connector is working properly.
    """
    if connector_name not in connector_status.keys():
        status = "UNKNOWN"
    else:
        return f"&c{connector_status[connector_name].upper()}"
    return status
