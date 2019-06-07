# Telegram integration

![Telegram](/assets/img/telegram.png)

Integrating Hummingbot with [Telegram Messenger](https://telegram.org/) allows you to get real-time updates and issue commands to your trading bot from any device where you have Telegram installed. 

Whether you are running Hummingbot in the cloud or on your local machine, you can use Telegram to monitor and  control Hummingbot from wherever you are!

## Set up your Telegram bot

Below, we show how to create a Telegram bot that integrates with your Hummingbot deployment.

### 1. Create the bot

* Click this link to launch the official **BotFather** bot, a Telegram bot that helps you create and manage Telegram bots: [https://telegram.me/BotFather](https://telegram.me/BotFather).

* In Telegram, go to the newly-created **BotFather** chat pane, and click `Start` or type `/start`.

* Enter `/newbot` to create a bot.

![](/assets/img/botfather-1.png)

* Enter a name for your bot, the title of the bot in Telegram (e.g. `hummingbot`).

![](/assets/img/botfather-2.png)

* Enter a unique ID that ends with the word `bot` (e.g. `my_awesome_hummingbot`).

![](/assets/img/botfather-3.png)

* Click the name of the bot to launch it: `t.me/<YOUR BOT NAME>` in the message above.

* Take note of the Telegram token in the the response above. You'll need it in a minute for the configuration step.

### 2. Get your Telegram ID

* Click this link to launch **userinfobot**, a Telegram bot that helps you retrieve your Telegram ID: [https://telegram.me/userinfobot](https://telegram.me/userinfobot).

* In Telegram, go to the newly-created **userinfobot** chat pane, and click `Start` or type `/start`.

* Take note of the `Id` parameter provided. You'll need it in a minute for the configuration step.

### 3. Configure the Telegram settings in Hummingbot

* In the directory where you have installed Hummingbot, go to your global configuration file: `conf/conf_global.yml`.

* Enter the following parameters at the end of the file:

```
telegram_enabled: true
telegram_token: <TELEGRAM TOKEN FROM STEP 1>
telegram_chat_id: <TELEGRAM ID FROM STEP 2>
```

## Use your Telegram bot

* Before you start Hummingbot, make sure that the Telegram bot is live. If so, you should see a chat pane with your bot's name in Telegram.

* Now you can start hummingbot as you would normally. Telegram will be connected as soon as you enter `start` in 
your hummingbot CLI window.

* Messages are synchronized in real-time between the Telegram bot and the actual Hummingbot instance running. For example, you can use commands such as `status` and `history` to monitor the bot's performance, and you can use `start` and `stop` to control the bot.


