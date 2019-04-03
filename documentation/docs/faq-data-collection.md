# Data Collection FAQs

## What data do you collect when I use Hummingbot?

Users have full control over how much data they choose to send us. Depending on what users select, this may include:

- Ethereum wallet address
- Aggregate, anonymized trade and order volume
- Commands entered in the client interface
- Log entries for errors, notifications, and trade events

!!! note
    Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

## Why would I want to send you my usage data?

- **Get better support**: Granting access to your logs and client commands enables us to diagnose your issue more quickly and provide better support.

- **Participate in partner incentive programs**: Some of our exchange partners will compensate us based on aggregate volume. We plan to share this with participating users.

- **Help us improve the product**: We are committed to making Hummingbot the best open source software for crypto algorithmic trading. Understanding how users use the product will help us improve it more rapidly.

We only utilize user data for the purposes listed above. CoinAlpha and our employees are strictly prohibited from utilizing any user data for trading-related purposes.

## Can I opt-out of sharing my usage data?

Absolutely - the logger configuration file is fully editable. In addition, we maintain [templates](https://github.com/coinalpha/hummingbot/blob/master/hummingbot/templates) that users can use to override the default configuration settings, 