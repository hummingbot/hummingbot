Integrating Hummingbot with [Telegram Messenger](https://telegram.org/) allows you to get real-time updates and issue commands to your trading bot from any device where you have Telegram installed.
Whether you are running Hummingbot in the cloud or on your local machine, you can use Telegram to monitor and control bots from wherever you are!

## Creating a Telegram Bot

Click this link to launch the official BotFather bot, a Telegram bot that helps you create and manage Telegram bots: https://telegram.me/BotFather.

1. In Telegram, go to the newly-created BotFather chat pane, and click Start or type `/start`
2. Enter `/newbot` to create a bot
3. Enter a name for your bot, the title of the bot in Telegram e.g. `hummingbot`
4. Enter a unique ID that ends with the word `bot` (e.g. `my_awesome_hummingbot`)
5. Make sure to copy or save the token. This is needed for enabling Telegram on Hummingbot.
6. Click the link to your new bot in the message above launch it: `t.me/<YOUR BOT NAME>`.
7. Click `Start` or type `/start` to start the bot

![](/img/telegram-demo.gif)

## Getting your Telegram ID

Click this following to launch userinfobot, a Telegram bot that helps you retrieve your Telegram ID: https://telegram.me/userinfobot.

![](/img/telegram.png)

In Telegram, go to the newly-created userinfobot chat pane, and click `Start` or type `/start`. Save the ID number.

## Setting up in Hummingbot

You can now startup Hummingbot and confirm that the integration is properly configured. To enable Telegram in Hummingbot do the following:

1. Run `config telegram_enabled` and set to True or answer Yes to enable the Telegram integration
2. Run `config telegram_token` and enter the Telegram token ID from BotFather
3. Run `config telegram_chat_id` and enter the chat ID from [Getting your Telegram ID](#getting-your-telegram-id)

## Using the Telegram Bot

Before you start Hummingbot, make sure that the Telegram bot is live. If so, you should see a chat pane with your bot's name in Telegram.
Start Hummingbot as you would normally. Telegram will be connected as soon as you run `start` in your hummingbot CLI window. Messages are synchronized in real-time between the Telegram bot and the actual Hummingbot instance running. For example, you can use commands such as `status` and `history` to monitor the bot's performance, `config` shows bot current configurations and you can use `start` and `stop` to control the bot.

![](/img/telegram-command.png)

!!! tip
    If you are running multiple bots with Telegram enabled, you can use the same Telegram chat ID with different API tokens from each bot you created to control all of them. You can also use their [chat folders](https://telegram.org/blog/folders) feature to organize your bots.
