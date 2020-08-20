
Display your asset balances across all connected exchanges.

```
>>>  balance
Updating balances, please wait...

binance:
     Asset    Amount Limit
       BNB    0.0000     -
       BTC    0.0000     -
       ETH    0.0000     -
     TFUEL    0.0187     -
     THETA    0.5880     -
      USDC    0.0090     -
      USDT  158.8197     -
       XRP    0.8440     -
       XZC    0.0076     -

bittrex:
      Asset     Amount Limit
        BTC     0.0020     -
     BTXCRD  1025.2352     -
        XZC     5.1501     -

coinbase_pro:
    Asset   Amount Limit
      BAT  10.0000     -
      ETH   0.2059     -
     LINK  15.0500     -
     USDC   0.0033     -

ethereum:
    asset  amount
      ETH  0.0453
```

## balance limit [ exchange ] [ asset ] [ amount ]

Set the amount limit on how much assets Hummingbot can use in an exchange or wallet. This can be useful when running multiple bots on different trading pairs with same tokens e.g. running a BTC-USDT pair and another bot on ETH-USDT using the same account.

```
>>>  balance limit binance USDT 100
Limit for USDT on binance exchange set to 100.0
```

Run the `balance` command again to confirm the limit has been applied.

```
>>>  balance
Updating balances, please wait...

binance:
     Asset    Amount     Limit
       BNB    0.0000         -
       BTC    0.0000         -
       ETH    0.0000         -
     TFUEL    0.0187         -
     THETA    0.5880         -
      USDC    0.0090         -
      USDT  158.8197  100.0000
       XRP    0.8440         -
       XZC    0.0076         -
```

## balance paper

Show existing paper account balance setting.

```
>>>  balance paper
Paper account balances:
    Asset    Balance
      DAI  1000.0000
      ETH    10.0000
      ONE  1000.0000
     TUSD  1000.0000
     USDC  1000.0000
     USDQ  1000.0000
     USDT  1000.0000
     WETH    10.0000
      ZRX  1000.0000
```

## balance paper [ asset ] [ amount ]

Set the amount of asset balance for paper trading mode. For example, we want to add 0.5 BTC to our paper account balance.

```
>>>  balance paper BTC 0.5
Paper balance for BTC token set to 0.5

>>>  balance paper
Paper account balances:
    Asset    Balance
      BTC     0.5000
      DAI  1000.0000
      ETH    10.0000
      ONE  1000.0000
     TUSD  1000.0000
     USDC  1000.0000
     USDQ  1000.0000
     USDT  1000.0000
     WETH    10.0000
      ZRX  1000.0000
```