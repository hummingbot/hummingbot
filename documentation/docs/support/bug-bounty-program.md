# Bug Bounty Program

Since Hummingbot is experimental, beta software that can be run in many different user configurations and markets, we are leveraging the power of our community to help us identify and properly handle all the edge cases which may arise.

As a small token of our appreciation for users who invest their time and effort to try out Hummingbot and report the issues they encounter, we are excited to announce a bounty program for reward users who help improve Hummingbot's stability and reliability!

## Scope
The public, open source [Hummingbot code base](https://github.com/CoinAlpha/hummingbot).

## Rewards

We will pay bug reporters 0.1 ETH for any bug reported that meets the following criteria:

* It has a different root cause than any other bug reported by other users
* Reporter follows the submission guidelines below (see [Submission](/support/bug-bounty-program/#submission))
* We decide to fix the bug

In addition, we may add a discretionary bonus to bugs that entail security vulnerabilities, depending on the severity of the vulnerability.

## Bounty Rules and Guidelines

* Bounties are awarded on a first-report basis
* We ask that you do not use vulnerabilities or errors you come across for purposes other than your own investigation
* We ask that you do not publicize or disclose to any third parties any details of **security vulnerabilities** until the Hummingbot team removes those issues
* All bounties and rewards will be subject to the sole discretion of the Hummingbot team

## Submission

* **For security vulnerabilities**: Email the description of the issue to us at dev@hummingbot.io
* **For all other bugs**: Submit a [Bug Report](https://github.com/CoinAlpha/hummingbot/issues/new?assignees=&labels=bug&template=bug_report.md&title=%5BBUG%5D) in our Github repo
* Please follow the template and include detailed descriptions of the bug, steps to reproduction, supporting ** artifacts such as screenshots, logs, configuration settings, and suggested fixes, if any
* **Privacy**: We pledge that we will not use your information for trading purposes or share your personal information with third parties

## Evaluation
The Hummingbot team will investigate your report within 24 hours, contact you to discuss the issue, and send 0.1 ETH to your Ethereum wallet once the team decides to fix the bug that you reported.

## Reported bugs

In this section, we will publish a list of reported bugs and their status.

## Bounty distribution (As of 8/31/2019)
ETH Address (First 6 digits) | Bugs Reported | Link | Paid?
---|---|---|---
 0x93cF | Missing logs file | NA | Y
 0xc1fc | Problem installing on Windows | [Issue 94](https://github.com/CoinAlpha/hummingbot/issues/94) | Y
 0xD9B9 | Precision issue in Coinbase | [Issue 106](https://github.com/CoinAlpha/hummingbot/issues/106) | Y
 0xDE1f | Get wallet -e doesn't work | [Issue 96](https://github.com/CoinAlpha/hummingbot/issues/96) | Y 
 0xf452 | Maker order size (0.0) must be greater than 0 | [Issue 118](https://github.com/CoinAlpha/hummingbot/issues/118) | Y 
 0xf452 | Coin flagged erroneously as zero balance on radar_relay | [Issue 101](https://github.com/CoinAlpha/hummingbot/issues/101) | Y
 0x32a5 | DDEX market orders are incorrect | [Issue 147](https://github.com/CoinAlpha/hummingbot/issues/147) | Y 
 0xf452 | Problem in compiling hummingbot 0.5.0 and dev-0.6.0 in windows bash | [Issue 155](https://github.com/CoinAlpha/hummingbot/issues/155) | Y 
 0xB389 | Order still shown as active after being filled | [Issue 341](https://github.com/CoinAlpha/hummingbot/issues/341) | Y 
 0xEEDf | Unexpected error running clock tick - arbitrage in binance | [Issue 401](https://github.com/CoinAlpha/hummingbot/issues/401) | Y 
 0xC39F | RadarRelay - Limit orders require an expiration timestamp 'expiration_ts' | [Issue 568](https://github.com/CoinAlpha/hummingbot/issues/568) | Y 
 0xcF44 | Trade type is always tagged as "Sell" | [Issue 631](https://github.com/CoinAlpha/hummingbot/issues/631) | Y
 0xFcba | Trades for taker market > maker market | [Issue 627](https://github.com/CoinAlpha/hummingbot/issues/627) | Y 
 0x2212 | Bounties "Filled volume" remain constant | [Issue 644](https://github.com/CoinAlpha/hummingbot/issues/644) | Y 
 0xf01E | export_trades command will only export 100 trades | [Issue 677](https://github.com/CoinAlpha/hummingbot/issues/677) | Y 


**Happy 🐞 hunting!**

