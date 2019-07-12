# [Quickstart] Configure Your First Trading Bot

!!! note "Paper trading mode [in progress]"
    We are currently working on a paper trading mode that will allow you to test out Hummingbot without risking real crypto. For now, you still need to run a live trading bot.

If you have successfully installed Hummingbot using our install scripts, you should see the command line-based Hummingbot interface below.

## Navigating the Client Interface

![](/assets/img/hummingbot-cli.png)

* Left bottom pane: input [commands](https://docs.hummingbot.io/operation/client/#client-commands)
* Left top pane: output of your commands go
* Right pane: logs of live trading bot activity

The left bottom pane is  The upper left pane  and the right pane logs messages in real time.

## Register for Bounties

Enter `bounty --register` to start the registration process:

1. Agree to the Terms & Conditions
2. Allow us to collect your trading data for verification purposes
3. Enter your Ethereum wallet address
4. Enter your email address
5. Confirm information and finalize

Note that in order to accumulate rewards, you need to maintain at least 0.05 ETH in your Ethereum wallet. This prevents spam attacks and ensures that everyone has a fair chance to earn bounties.

## Bounty-Related Commands

| Command | Description |
|-------- | ----------- |
| `bounty --register` | Register to participate in for liquidity bounties
| `bounty --status` | See your accumulated rewards
| `bounty --terms` | See the terms & conditions

---
# Next: [Run a market making bot](/bounties/tutorial/bot)
