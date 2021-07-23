Exports secure information.

## export keys

Displays API keys, secret keys and wallet private key in the command output pane.

```
>>>  export keys

Enter your password >>> *****

Warning: Never disclose API keys or private keys. Anyone with your keys can steal any assets held in your account.

API keys:
binance_api_key: 
binance_api_secret: 

Ethereum wallets:
Public address: 
Private key: 
```

## export trades

Exports all trades in the current session to a .csv file.

```
>>>  export trades

Enter a new csv file name >>> trade_list
Successfully exported trades to logs/trade_list.csv
```