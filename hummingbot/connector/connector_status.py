#!/usr/bin/env python

connector_status = {
    'altmarkets': 'bronze',
    'ascend_ex': 'silver',
    'binance': 'gold',
    'binance_perpetual': 'gold',
    'binance_perpetual_testnet': 'gold',
    'binance_us': 'bronze',
    'bitfinex': 'bronze',
    'bitget_perpetual': 'bronze',
    'bitmart': 'bronze',
    'bittrex': 'bronze',
    'bitmex': 'bronze',
    'bitmex_perpetual': 'bronze',
    'bitmex_testnet': 'bronze',
    'bitmex_perpetual_testnet': 'bronze',
    'bybit_perpetual': 'bronze',
    'bybit_perpetual_testnet': 'bronze',
    'bybit_testnet': 'bronze',
    'bybit': 'bronze',
    'coinbase_pro': 'bronze',
    'crypto_com': 'bronze',
    'dydx_perpetual': 'silver',
    'gate_io': 'silver',
    'gate_io_perpetual': 'silver',
    'hitbtc': 'bronze',
    'huobi': 'bronze',
    'kraken': 'bronze',
    'kucoin': 'silver',
    'kucoin_testnet': 'silver',
    'lbank': 'bronze',
    'loopring': 'bronze',
    'mexc': 'bronze',
    'ndax': 'bronze',
    'ndax_testnet': 'bronze',
    'okx': 'bronze',
    'perpetual_finance': 'bronze',
    'probit': 'bronze',
    'whitebit': 'bronze'
}

warning_messages = {
}


def get_connector_status(connector_name: str) -> str:
    """
    Indicator for the connector tier: GOLD / SILVER / BRONZE / UNKNOWN 
    """
    if connector_name not in connector_status.keys():
        status = "UNKNOWN"
    else:
        return f"&c{connector_status[connector_name].upper()}"
    return status
