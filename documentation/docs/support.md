# Support

We recognize that running a trading bot for the first time is a big step for many new users, so we maintain 24/7 live support to assist our users.

## Needed support info

Before you reporting bugs or issues, please collect these three items which helps our support team triage your issue promptly.

1. **Screenshot**: In the Hummingbot client, run the `status` command and take a screenshot that includes the full terminal/bash window. Make sure to include both the left pane and the right log pane of Hummingbot.

2. **Strategy config file**: This is the file with the parameters associated with your strategy. It does not contain API keys, wallet private keys, or other confidential data. It is located in the `conf/` (Windows and macOS) or `hummingbot_conf/` (Docker) folder. For example, if you have configured a pure market making strategy for the first time, the file's default name is `conf_pure_market_making_0.yml`.

3. **Log file**: This is the file that contains a detailed log output and error stack trace. It is located in the `logs/` (Windows and macOS) or `hummingbot_logs/` (Docker) folder. If you are sending logs related to your most recent Hummingbot session, sort the folder for the most recently updated file. It should have a name similar to `logs_conf_pure_market_making_0.log`.

## Ways to get support

### Discord

Our official [Discord server](https://discord.hummingbot.io) is the primary gathering spot for announcements, user support, trading strategies, connectors, and other discussion about Hummingbot.

When you sign up for our Discord, please check that the link you are accessing is **https://discord.hummingbot.io**.

!!! warning
    Currently, our Discord server is the only officially-supported online Hummingbot community. We do not maintain any other communities on Telegram, WeChat, Slack, or other applications. Please beware that any such communities (except for the official Hummingbot Discord) may be scams.

### Github

For bugs not yet listed in GitHub, please submit a [Bug Report](https://github.com/CoinAlpha/hummingbot/issues/new?assignees=&labels=bug&template=bug_report.md&title=%5BBUG%5D).

Follow the template and include detailed descriptions of the bug, steps to reproduction, supporting artifacts such as screenshots, logs, configuration settings, and suggested fixes, if any.

We pledge that we will not use your information for trading purposes or share your personal information with third parties.

### E-mail

For support requests via email, you can send us a message at **support@hummingbot.io**.



