# Hummingbot Source Code

This folder contains the main source code for Hummingbot.

## Project Breakdown
```
hummingbot
├── client                         # CLI related files
├── core 
│   ├── cpp                        # high performance data types written in .cpp
│   ├── data_type                  # key data
│   ├── event                      # defined events and event-tracking related files
│   └── utils                      # helper functions and bot plugins
├── data_feed                      # price feeds such as CoinCap
├── logger                         # handles logging functionality
├── market                         # connectors to individual exchanges
│   └── <market_name>              # folder for specific exchange ("market")
│       ├── *_market               # handles trade execution (buy/sell/cancel)
│       ├── *_data_source          # initializes and maintains a websocket connection
│       ├── *_order_book           # takes order book data and formats it with a standard API
│       ├── *_order_book_tracker   # maintains a copy of the market's real-time order book
│       ├── *_active_order_tracker # for DEXes that require keeping track of
│       └── *_user_stream_tracker  # tracker that process data specific to the user running the bot
├── notifier                       # connectors to services that sends notifications such as Telegram
├── strategy                       # high level strategies that works with every market
├── templates                      # templates for config files: general, strategy, and logging
└── wallet                         # files that read from and submit transactions to blockchains
    └── ethereum                   # files that interact with the ethereum blockchain
```
