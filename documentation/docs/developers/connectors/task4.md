# Task 4. Configure Hummingbot Client

This section will define the necessary files that need to be modified to allow users configure Hummingbot to use the new exchange connector.

The following list displays the files that **require** to be modified.

- __init_.py
- global_config_map.py
- fee_overrides_config_map.py
- hummingbot_application.py
- settings.py
- user_balances.py
- trading_pair_fetcher.py
- market_mid_price.py
- estimate_fee.py

The following displays where the files are located and the respective code changes that **require** to be modified.

## __init_.py

Directory: `connector/__init_.py`

```python
new_market_api_key = os.getenv("NEW_MARKET_API_KEY")
new_market_secret_key = os.getenv("NEW_MARKET_SECRET_KEY")
```

## global_config_map.py

Directory: `hummingbot/client/config/global_config_map.py`

```python
"new_market_api_key": ConfigVar(key="new_market_api_key",
                             prompt="Enter your NewMarket API key >>> ",
                             required_if=using_exchange("new_market"),
                             is_secure=True),
"new_market_secret_key": ConfigVar(key="new_market_secret_key",
                                prompt="Enter your NewMarket secret key >>> ",
                                required_if=using_exchange("new_market"),
                                is_secure=True),
```

## fee_overrides_config_map.py

Directory: `hummingbot/client/config/fee_overrides_config_map.py`


```python
fee_overrides_config_map = {
    "binance_maker_fee": new_fee_config_var("binance_maker_fee"),
    "binance_taker_fee": new_fee_config_var("binance_taker_fee"),
    .
    .
    .
    "new_exchange_maker_fee": new_fee_config_var("new_exchange_maker_fee"),
    "new_exchange_taker_fee": new_fee_config_var("new_exchange_taker_fee"),
```

##  hummingbot_application.py

Directory: `hummingbot/client/hummingbot_application.py`


```python
MARKET_CLASSES = {
    .
    .
    .
    "new_market": NewMarket
}
.
.
.
  def _initialize_markets(self, market_names: List[Tuple[str, List[str]]]):
    ...
    ...
       ...
       elif market_name == "new_market":
         new_market_api_key = global_config_map.get("new_market_api_key").value
         new_market_secret_key = global_config_map.get("new_market_secret_key").value
         new_market_passphrase = global_config_map.get("new_market_passphrase").value

         market = NewMarket(new_market_api_key,
                            new_market_secret_key,
                            new_market_passphrase,
                            symbols=symbols,
                            trading_required=self._trading_required)
```

## settings.py

Directory: `hummingbot/client/settings.py`

```python
EXCHANGES = {
    "bamboo_relay",
    .
    .
    .
    "new_market",
}	}

DEXES = {
    "bamboo_relay",
    .
    .
    .
    "new_market", # if it is a DEX
}

EXAMPLE_PAIRS = {
    "binance": "ZRXETH",
    .
    .
    .
    "new_market": "EXAMPLE_PAIR",
}

EXAMPLE_ASSETS = {
    "binance": "ZRX",
    .
    .
    .
    "new_market": "EXAMPLE_ASSET",
}
```
- `hummingbot/client/command/connect_command.py`
```python
OPTIONS = {
    "binance",
    .
    .
    .
    "new_exchange"
}
```

##  user_balances.py

Directory: `hummingbot/user/user_balances.py`


```python
    @staticmethod
    def connect_market(exchange, *api_details):
        market = None
        if exchange == "binance":
            market = BinanceMarket(api_details[0], api_details[1])
        .
        .
        .
        elif exchange == "new_exchange":
            market = NewExchangeMarket(api_details[0], api_details[1])
        return market
```

## trading_pair_fetcher.py

Directory: `hummingbot/user/hummingbot/core/utils/trading_pair_fetcher.py`

```python
@staticmethod
async def fetch_new_market_trading_pairs() -> List[str]:
    # Returns a List of str, representing each active trading pair on the exchange.
    async with aiohttp.ClientSession() as client:
            async with client.get(NEW_MARKET_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    try:
                        all_trading_pairs: List[Dict[str, any]] = await response.json()
                        return [item["symbol"]
                                for item in all_trading_pairs
                                if item["status"] == "ONLINE"]  # Only returns active trading pairs
                    except Exception:
                        pass
                        # Do nothing if the request fails -- there will be no autocomplete available
                return []
.
.
.

async def fetch_all(self):
    binance_trading_pairs = await self.fetch_binance_trading_pairs()
    .
    .
    .
    new_market_trading_pairs = await self.fetch_new_market_trading_pairs()
    self.trading_pairs = {}
        "binance": binance_trading_pairs,
        .
        .
        .
        "new_market": new_market_trading_pairs,
```
## market_mid_price.py

Directory: `hummingbot/core/utils/market_mid_price.py`


```python
def get_mid_price(exchange: str, trading_pair: str) -> Optional[Decimal]:
    .
    .
    elif exchange == "new_exchange":
        return new_exchange_mid_price(trading_pair)
        
@cachetools.func.ttl_cache(ttl=10)
def new_exchange_mid_price(trading_pair: str) -> Optional[Decimal]:
    resp = requests.get(url=...)
    records = resp.json()
    result = None
    for record in records:
        pair = new_exchange.convert_from_exchange_trading_pair(record["symbol"])
        .
        .
        .
    return result
```
## estimate_fee.py

Directory: `hummingbot/core/utils/estimate_fee.py`

```python
default_cex_estimate = {
        .
        .
        "new_exchange": [maker_fee, taker_fee],
        
```
