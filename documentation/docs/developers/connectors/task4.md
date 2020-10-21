# Task 4. Required Connector Configuration

This section explains the configuration for the required file, functions and other optional settings to integrate your connector with Hummingbot.

## \[new_connector]_utils.py ##

1. Create the [new_connector]_utils.py file (in your connector folder) and add the following **required** members in the new utils file. 

    Member<div style="width:200px"/> | Type | Description
    ---|---|---
    `CENTRALIZED` | `bool` | `True` if connector is for a centralized exchange, otherwise return false.
    `EXAMPLE_PAIR` | `str` | An example of a supported trading pair on the exchange in [BASE]-[QUOTE] format.
    `DEFAULT_FEES` | `List[Decimal]` | A list trading fees with the first index as the default maker fee and the second index as default taker fee.
    `KEYS` | `Dict[str, ConfigVar]` | A dictionary containing required keys for connecting to the exchange.

    See `hummingbot/connector/exchange/binance/binance_utils.py` for example.

    **Trading pair conversion functions**

2. If the exchange does not provide trading pairs in `[Base]-[Quote]` format, you will need to convert the trading pairs using the following functions:

    Function<div style="width:200px"/> | Input Parameter(s) | Expected Output(s) | Description
    ---|---|---|---
    `convert_from_exchange_trading_pair` | exchange_trading_pair: `str` | `str` | Converts the exchange's trading pair to `[Base]-[Quote]` formats and return the output.
    `convert_to_exchange_trading_pair` | hb_trading_pair: `str` | `str` | Converts HB's `[Base]-[Quote]` trading pair format to the exchange's trading pair format and return the output.

3. (Optional) Add members for Ethereum type connector.

    Member<div style="width:200px"/> | Type | Description
    ---|---|---
    `USE_ETHEREUM_WALLET` | `bool` | `True` if connector requires user's Ethereum wallet, which the user can set it up using `connect` command.
    `FEE_TYPE` | `str` | Set this to FlatFee if trading fee is fixed flat fee per transaction, the `DEFAULT_FEES` will then be in flat fee unit.
    `FEE_TOKEN` | `str` | Token name in FlatFee fee type, e.g. `ETH`. 

4. (Optional) Add other domains settings if:
    - your connector is able to connect to different domains by changing API URLs, e.g. Binance.com -> Binance.us. 
    - your exchange/protocol supports `testnet` environment.
  
    Member<div style="width:200px"/> | Type | Description
    ---|---|---
    `OTHER_DOMAINS` | `List[str]` | A list of other domain connector names, these will appear to users as new connectors they can choose.
    `OTHER_DOMAINS_PARAMETER` | `Dict[str, str]` | A dictionary of additional `domain` parameter for each `OTHER_DOMAIN`, this parameter (string) is passed in during connector, and order book tracker `__init__`.   
    `OTHER_DOMAINS_EXAMPLE_PAIR` | `Dict[str, str]` | An example of a supported trading pair for each domain.
    `OTHER_DOMAINS_DEFAULT_FEES` | `Dict[str, List[Decimal]]` | A dictionary of default trading fees \[maker fee and taker fee] for each domain.
    `OTHER_DOMAINS_KEYS` | `Dict[str, Dict[str, ConfigVar]]` | A dictionary of required keys for each domain.

    !!! Important
        If domain settings are used, ensure your connector uses the `domain` parameter to update base API URLs, and set the exchange name correctly. Refer to `Binance` connector on how to achieve this.  

## Changes in Hummingbot ##

* In `setup.py`, add your new connector package in `packages` variable as shown:

```python
    packages = [
        "hummingbot",
        .
        .
        "hummingbot.connector.exchange.kucoin",
        "hummingbot.connector.exchange.[new_connector]",
``` 

* In `hummingbot/templates/conf_global_TEMPLATE.yml`, add entries (with null value) for each key in your utils KEYS. 
You will also need to increment `template_version` by one. For example:

```python
template_version: [+1] 

[new_connector]_api_key: null
[new_connector]_secret_key: null
``` 

* In `hummingbot/templates/conf_fee_overrides_TEMPLATE.yml`, add maker and taker fee entries (use fee_amount when your FEE_TYPE is FlatFee). 
You will also need to increment `template_version` by one. For example:

```python
template_version: [+1] 

[new_connector]_maker_fee:
[new_connector]_taker_fee:
``` 