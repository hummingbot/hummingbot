# How to Create a Hummingbot Strategy
In addition to the trading strategies that come out of the box with Hummingbot, you can also customize them or create your own strategies, since they are written in Python. This guide shows you how to begin creating Hummingbot strategies.

There are various ways to get hummingbot started on your device. If you do download via Source, you should recompile the bot each time you change the source code to ensure the Cython parts within the bot works properly.

## Getting started as a developer

Follow the [Developer Getting Started](/developers/gettingstarted/) guide, which shows you how to install Hummingbot from source on various operating systems, how to set up your development environment, and provides helpful tips about compiling and developing Hummingbot.

If the installation was successful, you should see the Hummingbot welcome screen afterwards:

<!-- ![Hummingbot Welcome Screen](../../assets/img/welcome_screen.png) -->
<img src="../../assets/img/welcome_screen.png" alt="Hummingbot Welcome Screen" width="700"/>

## Create a strategy

Let’s create a simple trading bot that places a limit order!

### Strategy files

For the purposes of this article, we assume that you have installed Hummingbot in a directory `~/hummingbot-instance`. From that directory, navigate to the `strategy` directory that contains all the strategies. Each sub-folder is a different strategy.
```
cd ~/hummingbot-instance
cd hummingbot/strategy
```
In this directory, create the folder which will contain the files for our strategy:
```
mkdir new_strategy
cd new_strategy
```

Next, go into the folder and create the four files that we need for our strategy:
```
touch __init__.py new_strategy_config_map.py new_strategy.py start.py
```

Each of these files has a specific purpose and naming convention. See the [Developer Tutorial](/developers/tutorial/) to learn more about the file structure and naming conventions for different strategies. 

Lastly, we also need to create a strategy configuration template, which defines the user-configurable parameters defined by the strategy. Like the strategy files and folders, the template file name also follows a convention. 

Let’s look at these files individually.

### `__init__.py`

The **init** file exposes your strategy. Copy the following code into the file using a code editor:
```python
# Initializing the project
from .new_strategy import NewStrategy
__all__ = [NewStrategy]
```

Here, the `__all__` field is used to expose the public module `NewStrategy` for use.

### `new_strategy_config_map.py`

The **config map** file sets the user prompts to set the strategy parameters. The naming convention for this file is `{strategy_name}_config_map.py`. 

Use the following code in your config map file:
```python
from hummingbot.client.config.config_var import ConfigVar

NewStrategy_config_map ={
    "strategy":
        ConfigVar(key="strategy",
                  prompt="",
                  default="NewStrategy",
    ),
    "connector":
        ConfigVar(key="connector",
                  prompt="Enter the name of the exchange >>> ",
                  prompt_on_new=True,
    ),
    "market": ConfigVar(
        key="market",
        prompt="Enter a market trading_pair :",
        prompt_on_new=True,
    ),
}
```
The parameters in this file are mapped as key-value pairs. Each field uses a [ConfigVar](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/client/config/config_var.py#L20) method to accept parameters. ConfigVar is a variable that you can use to control the trading behavior of the bot. 

The `key` parameter identifies the field, while the `prompt` parameter lets you choose the prompt message. If you include `prompt_on_new`, the prompt will be asked each time the user creates a new strategy. Otherwise, it will only be displayed when the user configures the parameter with `config`.

In the above example, the `strategy` field identifies the trading strategy: `NewStrategy`. Similarly, we have used the `connector` field to prompt for the name of the exchange, and the `market` field to prompt for trading pair that you want to trade.

Additionally, you can supply validators as parameters to ensure only accepted values are entered, and you can use the `default` parameter to supply a default value to the parameters. See the [ConfigVar](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/client/config/config_var.py#L20) file for all the ways that you can set strategy parameters.

### `start.py `

The **start** file initializes the configuration for a strategy. Copy the following code to get started:

```python
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.new_strategy import NewStrategy
from hummingbot.strategy.new_startegy.new_strategy_config_map import new_strategy_config_map as c_map

def start(self):
    connector = c_map.get("connector").value.lower()
    market = c_map.get("market").value

    self._initialize_markets([(connector, [market])])
    base, quote = market.split("-")
    market_info = MarketTradingPairTuple(self.markets[connector], market, base, quote)
    self.market_trading_pair_tuples = [market_info]

    self.strategy = NewStrategy(market_info)
```

In the above code, the `connector` variable stores the exchange name, whereas the `market` variable stores the trading pair. These variables fetch the required values from the config map file, which we defined in the previous step. 

Similarly, the `MarketTradingPairTuple` object accepts the exchange name, trading pair, base asset and quote asset for as its parameters.

This information allows us to initialize the `NewStrategy` object.

!!! tip
    To hard-code the strategy so that it only runs on a certain exchange, add a line such as `connector = 'binance'`

### `new_strategy.py`

The **strategy** file defines its behavior. To create your strategy file, copy the following code and paste it into the strategy file:

```python
#!/usr/bin/env python

from decimal import Decimal
import logging

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.strategy_py_base import StrategyPyBase

hws_logger = None

class NewStrategy(StrategyPyBase):
    # We use StrategyPyBase to inherit the structure. We also 
    # create a logger object before adding a constructor to the class. 
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global hws_logger
        if hws_logger is None:
            hws_logger = logging.getLogger(__name__)
        return hws_logger

    def __init__(self,
                 market_info: MarketTradingPairTuple,
                 ):

        super().__init__()
        self._market_info = market_info
        self._connector_ready = False
        self._bought_eth = False
        self.add_markets([market_info.market])

    # After initializing the required variables, we define the tick method. 
    # The tick method is the entry point for the strategy. 
    def tick(self, timestamp: float):
        if not self._connector_ready:
            self._connector_ready = self._market_info.market.ready
            if not self._connector_ready:
                self.logger().warning(f"{self._market_info.market.name} is not ready. Please wait...")
                return
            else:
                self.logger().warning(f"{self._market_info.market.name} is ready. Trading started")

        if not self._bought_eth:
            # The get_mid_price method gets the mid price of the coin and
            # stores it. This method is derived from the MarketTradingPairTuple class.
            mid_price = self._market_info.get_mid_price() 

            #The buy_with_specific_market method executes the trade for you. This     
            #method is derived from the Strategy_base class. 
            order_id = self.buy_with_specific_market(self._market_info,
                                                     Decimal("0.005"),
                                                     OrderType.LIMIT,
                                                     mid_price)
            self.logger().info(f"Submitted buy order {order_id}")
            self._bought_eth = True

def did_complete_buy_order(self, order_completed_event):
    self.logger().info("Your order has been fulfilled")
    self.logger().info(order_completed_event)
```

Check out the [MarketTradingPairTuple](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/market_trading_pair_tuple.py) class for more methods to add to your bot.

Both [StrategyPyBase](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/strategy_py_base.pyx) class and `buy_with_specific_market` method derive from the strategy base class. To learn more about other methods you can use using the class, visit [Strategy_base](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/strategy_base.pyx).

### `conf_NewStrategy_strategy_TEMPLATE.yml`

Lastly, we also need an additional file inside the templates folder of the HummingBot directory. This file acts as a placeholder for the parameters you will use in the strategy. First, let’s navigate to the `templates` folder and create the file. Run the following commands.
```
cd ~/hummingbot instance
cd hummingbot/templates
touch conf_new_strategy_strategy_TEMPLATE.yml   
```

Add the following code to this file:
```yaml
template_version: 1
strategy: null
connector: null
market: null
```

**Important**: The template filename convention is `conf_{strategy_name}_strategy_TEMPLATE.yml`.

## Running our strategy
Now that we have created a new trading strategy let’s run it in paper trading mode!

First, let’s recompile the code. It's good practice to recompile the code every time you make changes to rebuild any altered Cython code.
```
cd ~/hummingbot-instance
./compile
```
Now, start Hummingbot:
```
bin/hummingbot.py
```

### The Hummingbot UI

Your Hummingbot UI comprises three sections:

1. the main interface
2. logger
3. the input interface

![Hummingbot UI](../../assets/img/hummingbot_ui.png)

### Create the strategy
Follow the steps below to use the strategy we have created.

1. Run the command `create` to start a new bot
2. For the option, “What is your market making strategy?”, enter `new_strategy`. 
3. For the name of the exchange, enter `binance`
4. Save the configuration file

### Apply paper trading mode

Run the `paper_trade` command to enter paper trading mode. Paper trading mode lets you simulate placing orders and trades using live, real-time exchange order book data, and you don't need to add API keys to use it. You should see `paper_trading: ON` in the top navbar if you are in paper trading mode.

<!--![Paper Trade Simulation](../../assets/img/hummingbot_papertrade.png)-->
<img src="../../assets/img/hummingbot_papertrade.png" alt="Hummingbot Paper Trade" width="700"/>

### Run the strategy

Run `start` to run your bot in paper trading mode.

As soon as you begin trading, you can see the logger getting populated with trading activity. It shows you  information about the trading strategy, including the conversion rate. To see activity in the logger, create a strategy, choose relevant options and type **start** in the command shell.

<img src="../../assets/img/hummingbot_logger.png" alt="Hummingbot Logger" width="700"/>
<!--![Hummingbot Logger](../../assets/img/hummingbot_logger.png)-->

## Conclusion

Using this guide, you can create your own crypto trading bot and start trading right away. While this example only explains a basic Hummingbot strategy, it will serve as a starting point for creating your own complex trading strategies. To learn more about creating Hummingbot strategies, check out our [Developer Tutorial](/developers/tutorial/).