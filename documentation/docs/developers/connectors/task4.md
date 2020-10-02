# Task 4. Required Connector Configuration

This section will explain the necessary and concluding part to allow developer make the new exchange connector usable in Hummingbot.

The following table details the **required** constants that have to be present in the new connector's utils file.

Directory: `hummingbot/connector/[connector type]/[connector name]/[connector name]_utils.py`

Name<div style="width:200px"/> | Type | Description
---|---|---|---
`CENTRALIZED` | `bool` | Return `True` if connector is for a decentralized exchange, otherwise return false.
`EXAMPLE_PAIR` | `str` | Give an example of a supported trading pair on the exchange in [BASE]-[QUOTE] format.
`DEFAULT_FEES` | `List[Decimal]` | Return a list with the first index as the default maker fee and the second index as default taker fee.
`KEYS` | `Dict[str, ConfigVar]` | Return a dictionary containing required keys for connecting to the exchange.


## Example of required content in [connector name]_utils_.py

```python
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange

CENTRALIZED = True  # True for centralized exchange and false for decentralized exchange

EXAMPLE_PAIR = "ZRX-ETH"  # Example of supported pair on exchange

DEFAULT_FEES = [0.1, 0.1]  # [maker fee, taker fee]

KEYS = {
    "[connector name]_api_key":
        ConfigVar(key="[connector name]_api_key",
                  prompt="Enter your Binance API key >>> ",
                  required_if=using_exchange("[connector name]"),
                  is_secure=True,
                  is_connect_key=True),
    "[connector name]_api_secret":
        ConfigVar(key="[connector name]_api_secret",
                  prompt="Enter your Binance API secret >>> ",
                  required_if=using_exchange("[connector name]"),
                  is_secure=True,
                  is_connect_key=True),
    ...
}
```

<table><tbody><tr><td bgcolor="#ecf3ff">
**Note**: If the exchange does not provide trading pairs in `[Base]-[Quote]` format, the following functions should be implemented in addition to the above constants:

Function<div style="width:200px"/> | Input Parameter(s) | Expected Output(s) | Description
---|---|---|---
`convert_from_exchange_trading_pair` | exchange_trading_pair: `str` | `str` | Converts the exchange's trading pair to `[Base]-[Quote]` format and return the output.
`convert_to_exchange_trading_pair` | hb_trading_pair: `str` | `str` | Converts HB's `[Base]-[Quote]` trading pair format to the exchange's trading pair format and return the output.

</td></tr></tbody></table>
