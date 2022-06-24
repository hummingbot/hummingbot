# TODO remove this file!!!
from hummingbot.connector.gateway.clob.clob_exchange import CLOBExchange


def test_01():
    trading_pairs = ['SOL-USDT', 'SOL-USDC', 'SRM-SOL']

    exchange = CLOBExchange(
        trading_pairs
    )

    print('domain', exchange.domain)


if __name__ == '__main__':
    test_01()
