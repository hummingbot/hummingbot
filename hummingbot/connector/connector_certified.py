from prompt_toolkit import print_formatted_text as print
from prompt_toolkit.formatted_text import FormattedText, to_formatted_text

certified_connector = (
    'binance',
    'binance_perpetual',
    'ascendex',
    'gate_io',
    'kucoin',
    'kucoin_testnet',
    'hitbtc',
    'okx',
    'ftx',
    'bybit',
    'bybit_perpetual',
    'huobi'
)


def get_connector_certified(connector_name):
    """
    Filters connectors that are certified by adding background of GREEN color
    """
    if connector_name in certified_connector:
        text = FormattedText([
            ('#000000', connector_name)
        ])
        return print(to_formatted_text(text, style='bg:#1CD085'))
    else:
        return connector_name
