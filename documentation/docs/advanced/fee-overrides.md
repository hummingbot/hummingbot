# Fee override

This feature overrides trading fees (maker and taker) from corresponding market connector. This applies to users that has discounted rates or VIP account with specific fees.

### How to configure fee override?

Edit `conf_fee_overrides.yml` file using a text editor which is located in the `/conf` directory. Specific path or location may vary depending on the environment and how Hummingbot was installed.

- Installed from source: `hummingbot/conf`
- Installed via Docker: `hummingbot_files/hummingbot_conf`
    - `hummingbot_files` is the default name of the parent directory. This can be different depending on the setup 
    when the instance was created.
- Installed via Binary (Windows): `%localappdata%\hummingbot.io\Hummingbot\conf`
- Installed via Binary (MacOS): `~/Library/Application\ Support/Hummingbot/Conf`

### Fee override configuration by default

```
# Exchange trading fees, the values are in precise decimal, e.g. 0.1 for 0.1%.
# If the value is left blank, the default value (from corresponding market connector) will be used.

binance_maker_fee:
binance_taker_fee:

coinbase_pro_maker_fee:
coinbase_pro_taker_fee:

huobi_maker_fee:
huobi_taker_fee:

liquid_maker_fee:
liquid_taker_fee:

bittrex_maker_fee:
bittrex_taker_fee:

kucoin_maker_fee:
kucoin_taker_fee:

kraken_maker_fee:
kraken_taker_fee:
```

!!! note
    Make sure Hummingbot is not running on background or exit Hummingbot first before editing `conf/conf_fee_overrides.yml`.
