# Telegram Integration

![Telegram](/assets/img/telegram.png)

Integrating Hummingbot with [Telegram Messenger](https://telegram.org/) allows you to get real-time updates and issue commands to your trading bot from any device where you have Telegram installed.

Whether you are running Hummingbot in the cloud or on your local machine, you can use Telegram to monitor and control bots from wherever you are!

!!! note
    Make sure to install Telegram on your system before setting up your Telegram Bot. If not, you can download Telegram for [Windows/MAC/Linux](https://desktop.telegram.org/) and install.

## Set up your Telegram Bot

Below, we show how to create a Telegram bot that integrates with your Hummingbot deployment.

### 1. Create the Bot

* Click this link to launch the official **BotFather** bot, a Telegram bot that helps you create and manage Telegram bots: [https://telegram.me/BotFather](https://telegram.me/BotFather).

* In Telegram, go to the newly-created **BotFather** chat pane, and click `Start` or type `/start`.

* Enter `/newbot` to create a bot.

![](/assets/img/botfather-1.png)

* Enter a name for your bot, the title of the bot in Telegram (e.g. `hummingbot`).

![](/assets/img/botfather-2.png)

* Enter a unique ID that ends with the word `bot` (e.g. `my_awesome_hummingbot`).

![](/assets/img/botfather-3.png)

* Take note of the Telegram token in the response above. You'll need it for Step 3 below.

* Click the link to your new bot in the message above launch it: `t.me/<YOUR BOT NAME>`. Click `Start` or type `/start` to start the bot.

### 2. Get your Telegram ID

* Click this following to launch **userinfobot**, a Telegram bot that helps you retrieve your Telegram ID: [https://telegram.me/userinfobot](https://telegram.me/userinfobot).

* In Telegram, go to the newly-created **userinfobot** chat pane, and click `Start` or type `/start`.

* Take note of the `Id` parameter provided. You'll need it in a minute for the configuration step.

### 3. Configure the Telegram Settings in Hummingbot

* In the directory where you have installed Hummingbot, go to your global configuration file `conf/conf_global.yml` and edit the following parameters inside the file:

```
telegram_enabled: true
telegram_token: <TELEGRAM TOKEN FROM STEP 1>
telegram_chat_id: <TELEGRAM ID FROM STEP 2>
```

* Locating your global configuration:<br />
    * Installed from source: `hummingbot/conf`<br />
    * Installed via Docker: `hummingbot_files/hummingbot_conf`<br />
        `hummingbot_files` is the default name of the parent directory. This can be different depending on the setup
        when the instance was created.<br />
    * Installed via Binary (Windows): `%localappdata%\hummingbot.io\Hummingbot\conf`<br />
    * Installed via Binary (MacOS): `~/Library/Application\ Support/Hummingbot/Conf`<br />

* Alternatively, you can also configure your Telegram bot inside the Hummingbot client by using the following commands:

```
config telegram_enabled
config telegram_token
config telegram_chat_id
```

### 4. Startup Hummingbot

You can now startup Hummingbot and confirm that the integration is properly configured.

If Hummingbot was running when you configured telegram, make sure to `exit` and restart Hummingbot to reload the telegram configurations.

## Use your Telegram Bot

* Before you start Hummingbot, make sure that the Telegram bot is live. If so, you should see a chat pane with your bot's name in Telegram.

* Now you can start hummingbot as you would normally. Telegram will be connected as soon as you enter `start` in
your hummingbot CLI window.

* Messages are synchronized in real-time between the Telegram bot and the actual Hummingbot instance running. For example, you can use commands such as `status` and `history` to monitor the bot's performance, `config` shows bot current configurations and you can use `start` and `stop` to control the bot.

![](/assets/img/telegram-buttons.png)

!!! tip
    If you are running multiple bots with telegram enabled, you can use same [telegram chat id](https://telegram.me/userinfobot) with different telegram tokens from each bot you created to control all of them.  You can also enable [telegram chat folders](tg://settings/folders) to organize your bots.  Visit [telegram blog page](https://telegram.org/blog/folders) for more info. 
