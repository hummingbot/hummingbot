
List available commands.

```
>>>  help
usage: {connect,create,import,help,balance,config,start,stop,status,history,exit,paper_trade,export}
..

positional arguments:
  {connect,create,import,help,balance,config,start,stop,status,history,exit,paper_trade,export}
    connect             List available exchanges and add API keys to them
    create              Create a new bot
    import              Import a existing bot by loading the configuration file
    help                List available commands
    balance             Display your asset balances across all connected exchanges
    config              Display the current bot's configuration
    start               Start the current bot
    stop                Stop the current bot
    status              Get the market status of the current bot
    history             See the past performance of the current bot
    exit                Exit and cancel all outstanding orders
    paper_trade         Toggle paper trade mode on and off
    export              Export secure information
     
```

## help [ command_name ]

Displays command usage and function.

```
>>>  help connect

usage:  connect [-h] [{liquid,coinbase_pro,binance,kraken,bittrex,huobi,ethereum,kucoin}]

positional arguments:
  {liquid,coinbase_pro,binance,kraken,bittrex,huobi,ethereum,kucoin}
                        Name of the exchange that you want to connect
```