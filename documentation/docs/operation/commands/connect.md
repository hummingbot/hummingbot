
List available exchanges and check whether API keys have been added correctly.

```
>>>  connect

Testing connections, please wait...
         Exchange   Keys Added   Keys Confirmed
          binance          Yes              Yes
          bittrex          Yes              Yes
     coinbase_pro           No               No
         ethereum          Yes              Yes
            huobi           No               No
           kraken           No               No
           kucoin           No               No
           liquid           No               No
```


## connect [ exchange ]

Connect to an exchange by adding API keys.

```
>>>  connect binance

Enter your Binance API key >>>
Enter your Binance secret >>>

You are now connected to binance.
```

Replace existing API keys to an exchange connection.

```
>>>  connect binance

Would you like to replace your existing binance API key ...abc1 (Yes/No)? >>>

Enter your Binance API key >>>
Enter your Binance secret >>>
```

Connect to an Ethereum wallet.

```
>>>  connect ethereum

Enter your wallet private key >>>

Wallet 0x8D10...def2 connected to hummingbot.
```

Replace existing Ethereum wallet.

```
>>>  connect ethereum

Would you like to replace your existing Ethereum wallet ...def2 (Yes/No)? >>>
Enter your wallet private key >>>

Wallet 0xC20...8bFa connected to hummingbot.
```