# Telegram usage

## Setup your Telegram bot

We created this integration to help users who want to run their bots in a cloud environment receive real-time updates
on their mobile phone / desktop.

Below, we show your how to create a telegram bot that reads live status from your deployed hummingbot.

### 1. Create your Telegram bot

Start a chat with the [Telegram BotFather](https://telegram.me/BotFather)

Send the message `/newbot`. 

*BotFather response:*

> Alright, a new bot. How are we going to call it? Please choose a name for your bot.

Choose the public name of your bot (e.x. `hummingbot`)

*BotFather response:*

> Good. Now let's choose a username for your bot. It must end in `bot`. Like this, for example: TetrisBot or tetris_bot.

Choose the name id of your bot and send it to the BotFather (e.g. "`my_hummingbot`")

*BotFather response:*

> Done! Congratulations on your new bot. You will find it at `t.me/yourbots_name_bot`. You can now add a description, about section and profile picture for your bot, see /help for a list of commands. By the way, when you've finished creating your cool bot, ping our Bot Support if you want a better username for it. Just make sure the bot is fully operational before you do this.

> Use this token to access the HTTP API: `12345678:APITOKEN`

> For a description of the Bot API, see this page: https://core.telegram.org/bots/api Father bot will return you the token (API key)

Copy the API Token (`12345678:APITOKEN` in the above example) and keep use it for the config parameter `telegram_token`.

### 2. Get your Telegram chat ID

Talk to the [userinfobot](https://telegram.me/userinfobot)

Get your "Id", you will use it for the config parameter `telegram_chat_id`.

### 2. Configure Hummingbot to send messages to Telegram
Go to your `conf/conf_global.yml` file and enter the following:
```
telegram_enabled: true
telegram_token: <YOUR_TELEGRAM_TOKEN>
telegram_chat_id: <YOUR_TELEGRAM_CHAT_ID>
```

Now you can start hummingbot as you would normally. Telegram will be connected as soon as you enter `start` in 
your hummingbot CLI window.

