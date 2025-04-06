import pytest

from hummingbot.client.command.check_arb_command import (
    ExchangeInstrumentPair,
    InvalidUserInputError,
    sanitize_exchange_instrument_pair,
)

known_exchanges = {"binance", "kucoin", "bybit"}


@pytest.mark.parametrize(
    "input_str, expected_output, expected_exception",
    [
        # Valid formats
        ("binance:BTC-USDT", ExchangeInstrumentPair("binance", "BTC-USDT"), None),
        ("BINANCE:btc-usdt", ExchangeInstrumentPair("binance", "BTC-USDT"), None),
        ("KuCoin:eth-btc", ExchangeInstrumentPair("kucoin", "ETH-BTC"), None),

        # Whitespace should be trimmed
        (" binance : BTC-USDT ", ExchangeInstrumentPair("binance", "BTC-USDT"), None),
        ("\tkucoin:\neth-btc", ExchangeInstrumentPair("kucoin", "ETH-BTC"), None),
        ("  bybit :  btc-usdc  ", ExchangeInstrumentPair("bybit", "BTC-USDC"), None),

        # Missing colon
        ("binanceBTC-USDT", None, InvalidUserInputError),

        # Multiple colons
        ("binance:BTC:USDT", None, InvalidUserInputError),

        # No dash in instrument
        ("binance:BTCUSDT", None, InvalidUserInputError),

        # Multiple dashes
        ("binance:BTC-USDT-XYZ", None, InvalidUserInputError),

        # Invalid characters
        ("binance:BTC/USD", None, InvalidUserInputError),
        ("binance:BTC_USDT", None, InvalidUserInputError),
        ("binance:BTC.USDT", None, InvalidUserInputError),

        # Unknown exchange
        ("kraken:BTC-USDT", None, InvalidUserInputError),

        # Empty or malformed
        ("", None, InvalidUserInputError),
        (":", None, InvalidUserInputError),
        ("binance:", None, InvalidUserInputError),
        (":BTC-USDT", None, InvalidUserInputError),
    ]
)
def test_sanitize_exchange_instrument_pair(input_str, expected_output, expected_exception):
    if expected_exception:
        with pytest.raises(expected_exception):
            sanitize_exchange_instrument_pair(input_str, known_exchanges)
    else:
        result = sanitize_exchange_instrument_pair(input_str, known_exchanges)
        assert result == expected_output
