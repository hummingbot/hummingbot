# Task 4 — Configuration & Additional Functions

This section explains the configuration for the required file, functions, and other optional settings to integrate your connector with Hummingbot.

## Configuration

In `setup.py`, include the new connector package into the `packages` list as shown:

```python
packages = [
   "hummingbot",
   .
   .
   "hummingbot.connector.exchange.xyz",
   "hummingbot.connector.exchange.[new_connector]",
]
```

In `hummingbot/templates/conf_global_TEMPLATE.yml`, add entries with `null` value for each key in your utils KEYS.
  You will also need to increment `template_version` by one. For example:

```python
template_version: [+1]

[new_connector]_api_key: null
[new_connector]_secret_key: null
```

In `hummingbot/templates/conf_fee_overrides_TEMPLATE.yml`, add maker and taker fee entries (use fee_amount when your FEE_TYPE is FlatFee).
  You will also need to increment `template_version` by one. For example:

```python
template_version: [+1]

[new_connector]_maker_fee:
[new_connector]_taker_fee:
```

## Additional Utility Functions

### (Optional) API Request Throttler

### (Optional) Add members for Ethereum type connector

| Member                           | Type   | Description                                                                                                                     |
| -------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------- |
| `USE_ETHEREUM_WALLET`            | `bool` | `True` if connector requires user's Ethereum wallet, which the user can set it up using `connect` command.                      |
| `FEE_TYPE`                       | `str`  | Set this to FlatFee if the trading fee is fixed flat fee per transaction, the `DEFAULT_FEES` will then be in the flat fee unit. |
| `FEE_TOKEN`                      | `str`  | Token name in FlatFee fee type, i.e. `ETH`.                                                                                     |

### (Optional) Add other API domains

This is only relevant if:

- Exchange supports different domains by changing API URLs domains, i.e. `binance.com` & `binance.us` or `probit.com` & `probit.kr`
- Exchange supports a `testnet` environment.

| Member                           | Type                              | Description                                                                                                                                                      |
| -------------------------------- | --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `OTHER_DOMAINS`                  | `List[str]`                       | A list of other domain connector names, will appear to users as new connectors they can choose.                                                                  |
| `OTHER_DOMAINS_PARAMETER`        | `Dict[str, str]`                  | A dictionary of additional `domain` parameter for each `OTHER_DOMAIN`, this parameter (string) is passed in during connector, and order book tracker `__init__`. |
| `OTHER_DOMAINS_EXAMPLE_PAIR`     | `Dict[str, str]`                  | An example of a supported trading pair for each domain.                                                                                                          |
| `OTHER_DOMAINS_DEFAULT_FEES`     | `Dict[str, List[Decimal]]`        | A dictionary of default trading fees \[maker fee and taker fee] for each domain.                                                                                 |
| `OTHER_DOMAINS_KEYS`             | `Dict[str, Dict[str, ConfigVar]]` | A dictionary of required keys for each domain.                                                                                                                   |

!!! warning
    If domain settings are used, ensure your connector uses the `domain` parameter to update base API URLs and set the exchange name correctly. Refer to `Binance` connector on how to achieve this.
