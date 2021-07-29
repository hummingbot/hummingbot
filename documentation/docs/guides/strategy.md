#Hummingbot
Hummingbot supports 9 different trading strategies to jumpstart you into crypto trading. You can choose any of these strategies to monitor markets and make trading decisions. If you want to continue trading with Hummingbot, this article will get you started with Hummingbot’s strategy module and required parameters.

There are various ways to get hummingbot started on your device. If you do download via Source, you should recompile the bot each time you change the source code to ensure the Cython parts within the bot works properly.
##Install Hummingbot
###Install from source
Follow the **Install from Source** directions for each OS in the [Hummingbot docs](https://docs.hummingbot.io/):

Note: this guide assumes that you have installed Hummingbot in a folder with path **~/hummingbot-instance**.

- [Windows](https://docs.hummingbot.io/installation/windows/#install-from-source)
- [Mac](https://docs.hummingbot.io/installation/mac/#install-from-source)
- [Linux](https://docs.hummingbot.io/installation/mac/#install-from-source)

###Compile and run
After installation, activate the newly created Anaconda/Miniconda environment **hummingbot**. Next, run **./compile** to compile the Cython parts of the codebase. Finally, start Hummingbot.
```
conda activate hummingbot
./compile
bin/hummingbot.py
```
If the installation was successful, you should see the Hummingbot welcome screen.

<!-- ![Hummingbot Welcome Screen](../../assets/img/welcome_screen.png) -->
<img src="../../assets/img/welcome_screen.png" alt="Hummingbot Welcome Screen" width="700"/>

##Create a strategy
Let’s create a new trading strategy for Hummingbot!
###Create a new strategy files and folder
First, navigate to the directory that contains all the strategies. Each sub-folder is a different strategy.
```
cd ~/hummingbot-instance
cd hummingbot/strategy
```
In this directory, create the folder which will have all of the files for our strategy. Run the following commands to create and navigate to the strategy folder.
```
mkdir new_strategy
cd new_strategy
```
Once successful, we will create the following blank files.

- __init__.py  
- new_strategy_config_map.py, 
- new_strategy.py and 
- start.py files 

**Note**: The files should follow {strategy name}.py as a naming convention. 

Run the following command to create these files.
`touch __init__.py new_strategy_config_map.py new_strategy.py start.py`

Each of these files will serve a specific purpose. Visit our [strategy repository in GitHub](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/strategy) to learn more about the file structure and naming conventions for different strategies.

Lastly, we also need to create a template file in humingbot-master/Hummingbot/templates. Like the strategy files and folders, the template file name also follows a convention. Let’s look at these files individually.
###Add functionality to the files
After the files and folders are ready, we will have to add functionalities to the files. Let's visit each of them.

####__init__.py 
This file exposes your strategy. Copy the following code into the file using a code editor.
```
# Initializing the project
from .new_strategy import NewStrategy
__all__ = [NewStrategy]
```

Here, the ***\_\_all\_\_*** field is used to expose the public module i.e. NewStrategy, for use.
####new_strategy_config_map.py
The config map file prompts you to supply config values whenever you call the strategy. It lists the parameters this strategy will require. The naming convention for this file is {*strategy_name*}_config_map.py. Use the following code in your config map file.
```
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
                  ),
    "market": ConfigVar(
        key="market",
        prompt="Enter a market trading_pair :",
        prompt_on_new=True,
       ),
}
```
The parameters in this file are mapped as key-value pairs. Each field uses a [***ConfigVar***](https://github.com/CoinAlpha/hummingbot/blob/18ca19517e2b86d72dbaf50e28f6cd709ca9132c/hummingbot/client/config/config_var.py#L20) method to accept parameters. ConfigVar is a variable that you can use to control the trading behavior of the bot. 

The ***key*** parameter identifies the field, while the ***prompt*** parameter lets you choose the prompt message. Additionally, you can also supply validators as parameters to ensure only accepted values are entered.

In the above example, the ***strategy*** field identifies the trading strategy - *NewStrategy*. Similarly, we have used the ***connector*** field to prompt for the name of the exchange and the ***market*** field to prompt for the pair of coins that you want to exchange.

In addition to the ***key***, ***prompt*** and ***prompt_on_true*** parameters, the method also uses the ***default*** parameter, which can be used to supply a default value to the parameters. ***is_connect_key*** parameter takes a boolean value to check if a config variable is used in connect command. This [GitHub file](https://github.com/CoinAlpha/hummingbot/blob/18ca19517e2b86d72dbaf50e28f6cd709ca9132c/hummingbot/client/config/config_var.py#L20) illustrates all the parameters you can pass through the method. 
####start.py 
The start file holds the main program to initialize the configuration for the strategy. Copy the following code to get started with your start program.
```
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
In the above code, the ***connector*** variable stores the exchange name, whereas the ***market*** variable stores the name of the pairs of coins. These variables fetch the required value from the config map file, which we defined in the previous step.

>If you wish to hardcode the strategy so that it only runs on a certain exchange, you can set the market variable as market = ‘market_name’

Similarly, the ***MarketTradingPairTuple*** object accepts the exchange name, the name of the trading pair, the base asset and the quote asset for your crypto bot as its parameters. 

We have used all this information, lastly, to initialize strategy with the *NewStrategy* object.
####new_strategy.py 
This file contains several functions to define the behavior of strategy. The naming convention for this file is {*strategy_name*.py}. To create your strategy file, copy the following code and paste it into the strategy file.
```
#!/usr/bin/env python

from decimal import Decimal
import logging

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.strategy_py_base import StrategyPyBase

hws_logger = None

class NewStrategy(StrategyPyBase):
    # Here, we use StrategyPyBase to inherit the structure. We also 
    #create a logger object before adding a constructor to the class. 

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


    #After initialing the required variables, we define the tick method. 
    #Tick method is also the entry point for the strategy. 
    def tick(self, timestamp: float):
        if not self._connector_ready:
            self._connector_ready = self._market_info.market.ready
            if not self._connector_ready:
                self.logger().warning(f"{self._market_info.market.name} is not ready. Please wait...")
                return
            else:
                self.logger().warning(f"{self._market_info.market.name} is ready. Trading started")

        if not self._bought_eth:
            mid_price = self._market_info.get_mid_price() 
            #The get_mid_price method gets the mid price of the coin and
            #stores it. This method is derived from the 
            #MarketTradingPairTuple class.
            order_id = self.buy_with_specific_market(self._market_info,
                                                     Decimal("0.005"),
                                                     OrderType.LIMIT,
                                                     mid_price)
            #The buy_with_specific_market executes the trade for you. This     
            #method is derived from the Strategy_base class. 
            self.logger().info(f"Submitted buy order {order_id}")
            self._bought_eth = True


def did_complete_buy_order(self, order_completed_event):
    self.logger().info("Your order has been fulfilled")
    self.logger().info(order_completed_event)
```
You can check out the [MarketTradingPairTuple](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/market_trading_pair_tuple.py) class for more methods to add to your bot.

Both [StrategyPyBase](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/strategy_py_base.pyx) class and buy_with_specific_market method derive from Strategy_base class. To learn more about other methods you can use using the class, visit [Strategy_base](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/strategy_base.pyx). 
####conf_NewStrategy_strategy_TEMPLATE.yml 
We also need an additional file inside the templates folder of the HummingBot directory. This file acts as a placeholder for the parameters you will use in the strategy. First, let’s navigate to the *templates* folder and create the file. Run the following commands.
```
cd "hummingbot/templates" 
touch conf_new_strategy_strategy_TEMPLATE.yml   
```
In the context of this guide, this file will have the following code.
```
template_version: 1
strategy: null
connector: null
market: null
```
**Important**: The template filename convention is conf_{*strategy_name*}_stategy_TEMPLATE.yml.
##Running our strategy
Now that we have created a new trading strategy let’s run it in paper trading mode!

First, let’s recompile the code. It's good practice to recompile the code every time you make changes to rebuild any altered Cython code.
```
cd ~/hummingbot-instance
./compile
```
Start Hummingbot by running the following code.
`bin/hummingbot.py`

##The Hummingbot UI
Your Hummingbot UI comprises three sections - the main section, the logger and the command-line shell.  The command-line shell lets you enter commands to your Hummingbot. The main section shows the output and the logger maintains the log of the run commands.
![Hummingbot UI](../../assets/img/hummingbot_ui.png)

###The Main UI
As soon as you start sending commands through the command line shell in Hummingbot, the main UI reacts. It sends you relevant information, including prompt messages, status messages and help information, allowing you to take necessary actions in getting started. It also acts as a log of all the commands you have entered via the Hummingbot command shell. 
###Using the strategy we created
Follow the steps below to use the strategy we have created.

- Run the Hummingbot application.
- Run the command **create** to start a new bot
- For the option, “What is your market making strategy?”, enter **new_strategy**. 
- For the name of the exchange, we will enter **binance**.
- Give a filename for your configuration. You can use the default one.
- Enter the command **start** to start your bot.
- Paper trading should be enabled by default. If it is not, run the command paper_trade to enable paper trading.

**Note**: You can use paper money (simulation) to test the bot and its strategy before trading real money/crypto. Paper trading should be enabled by default. If it is not, run the **paper_trade** command from the UI.

<!--![Paper Trade Simulation](../../assets/img/hummingbot_papertrade.png)-->
<img src="../../assets/img/hummingbot_papertrade.png" alt="Hummingbot Paper Trade" width="700"/>

To see the progress of your trade run **status** command at any time, a trading session is on and the main UI will display your current trade position.

<!--![Hummingbot Status](../../assets/img/hummingbotstatus_status.png)-->
<img src="../../assets/img/hummingbot_status.png" alt="Hummingbot Status" width="700"/>

###The Logger
As soon as you begin trading, you can see the logger getting populated with trading activity. It shows you  information about the trading strategy, including the conversion rate. To see activity in the logger, create a strategy, choose relevant options and type **start** in the command shell.

<img src="../../assets/img/hummingbot_logger.png" alt="Hummingbot Logger" width="700"/>
<!--![Hummingbot Logger](../../assets/img/hummingbot_logger.png)-->

##Conclusion
Using this guide, you can create your own crypto trading bot and start trading right away. While this example only explains a basic Hummingbot strategy, it will serve as a starting point for creating your own complex trading strategies. To find and learn more about strategies, visit [Hummingbot’s Strategy Repository at GitHub](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/strategy). 

Hummingbot also offers a trading simulator mode to test the bot and its strategies before trading with real assets. This mode can be beneficial if you are a beginner trader or a professional trader trying out the Hummingbot.

So, choose your favorite strategy and start trading with Hummingbot now.
##Various Functions used on Existing Strategies
To sell with a specific market
```
def sell_with_specific_market(self, market_trading_pair_tuple, amount,
                                  order_type=OrderType.MARKET,
                                  price=s_decimal_nan,
                                  expiration_seconds=NaN,
                                  position_action=PositionAction.OPEN):
```
To track orders
```
cdef:
            str order_id = market.c_sell(market_trading_pair_tuple.trading_pair, amount,
                                         order_type=order_type, price=price, kwargs=kwargs)

        # Start order tracking
        if order_type.is_limit_type():
            self.c_start_tracking_limit_order(market_trading_pair_tuple, order_id, False, price, amount)
        elif order_type == OrderType.MARKET:
            self.c_start_tracking_market_order(market_trading_pair_tuple, order_id, False, amount)

        return order_id
```
Any function that starts with ‘did’ checks if the event was successful. For example, the following function checks if the order was successful.
```
 cdef c_did_fail_order_tracker(self, object order_failed_event):
        cdef:
            str order_id = order_failed_event.order_id
            object order_type = order_failed_event.order_type
            object market_pair = self._sb_order_tracker.c_get_market_pair_from_order_id(order_id)

        if order_type.is_limit_type():
            self.c_stop_tracking_limit_order(market_pair, order_id)
        elif order_type == OrderType.MARKET:
            self.c_stop_tracking_market_order(market_pair, order_id)
```
To track limit order
```
  def start_tracking_limit_order(self, market_pair: MarketTradingPairTuple, order_id: str, is_buy: bool, price: Decimal,
                                   quantity: Decimal):

        self.c_start_tracking_limit_order(market_pair, order_id, is_buy, price, quantity)
```
To display message on the Output Panel
```
  def notify_hb_app(self, msg: str):
        """
        Method called to display message on the Output Panel(upper left)
        """
        from hummingbot.client.Hummingbot_application import HummingbotApplication
        HummingbotApplication.main_application()._notify(msg)
```




