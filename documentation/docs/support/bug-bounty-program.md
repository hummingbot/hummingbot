# Bug Bounty Program

Since Hummingbot is experimental, beta software that can be run in many different user configurations and markets, we are leveraging the power of our community to help us identify and properly handle all the edge cases which may arise.

As a small token of our appreciation for users who invest their time and effort to try out Hummingbot and report the issues they encounter, we are excited to announce a bounty program for reward users who help improve Hummingbot's stability and reliability!

## Scope

The bounty program applies to issues found within the public, open source [Hummingbot code base](https://github.com/CoinAlpha/hummingbot).

## Rewards

We will pay bug reporters 0.1 ETH for any bug reported that meets the following criteria:

* It has a different root cause than any other bug reported by other users or discovered by the Hummingbot team
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
* Please follow the template and include detailed descriptions of the bug, steps to reproduction, supporting artifacts such as screenshots, logs, configuration settings, and suggested fixes, if any
* **Privacy**: We pledge that we will not use your information for trading purposes or share your personal information with third parties

## Evaluation
The Hummingbot team will investigate your report within 24 hours, contact you to discuss the issue, and send 0.1 ETH to your Ethereum wallet once the team decides to fix the bug that you reported.

## Reported bugs

In this section, we will publish a list of reported bugs and their status.

## Bounty distribution (As of 11/05/2019)
ETH Address (First 6 digits) | Bugs Reported | Github Issue | Paid?
---|---|---|---
 0x93cF | Missing logs file | NA | Y
 0xc1fc | Problem installing on Windows | [#94](https://github.com/CoinAlpha/hummingbot/issues/94) | Y
 0xD9B9 | Precision issue in Coinbase | [#106](https://github.com/CoinAlpha/hummingbot/issues/106) | Y
 0xDE1f | Get wallet -e doesn't work | [#96](https://github.com/CoinAlpha/hummingbot/issues/96) | Y 
 0xf452 | Maker order size (0.0) must be greater than 0 | [#118](https://github.com/CoinAlpha/hummingbot/issues/118) | Y 
 0xf452 | Coin flagged erroneously as zero balance on radar_relay | [#101](https://github.com/CoinAlpha/hummingbot/issues/101) | Y
 0x32a5 | DDEX market orders are incorrect | [#147](https://github.com/CoinAlpha/hummingbot/issues/147) | Y 
 0xf452 | Problem in compiling hummingbot 0.5.0 and dev-0.6.0 in windows bash | [#155](https://github.com/CoinAlpha/hummingbot/issues/155) | Y 
 0xB389 | Order still shown as active after being filled | [#341](https://github.com/CoinAlpha/hummingbot/issues/341) | Y 
 0xEEDf | Unexpected error running clock tick - arbitrage in binance | [#401](https://github.com/CoinAlpha/hummingbot/issues/401) | Y 
 0xC39F | RadarRelay - Limit orders require an expiration timestamp 'expiration_ts' | [#568](https://github.com/CoinAlpha/hummingbot/issues/568) | Y 
 0xcF44 | Trade type is always tagged as "Sell" | [#631](https://github.com/CoinAlpha/hummingbot/issues/631) | Y
 0xFcba | Trades for taker market > maker market | [#627](https://github.com/CoinAlpha/hummingbot/issues/627) | Y 
 0x2212 | Bounties "Filled volume" remain constant | [#644](https://github.com/CoinAlpha/hummingbot/issues/644) | Y 
 0xf01E | export_trades command will only export 100 trades | [#677](https://github.com/CoinAlpha/hummingbot/issues/677) | Y 
 0x1309 | Discovery fails when processing market pair | [#721](https://github.com/CoinAlpha/hummingbot/issues/721) | Y 
 0x2A60 | Stop command causes "cancelled order" | [#723](https://github.com/CoinAlpha/hummingbot/issues/723) | Y 
 0x8950 | Token symbol format for Discovery configuration | [#724](https://github.com/CoinAlpha/hummingbot/issues/724) | Y 
 0xd8fb | Bounty Status server error | [#754](https://github.com/CoinAlpha/hummingbot/issues/754) | Y 
 0x1D95 | 0 day remote command execution | [#555](https://github.com/CoinAlpha/hummingbot/issues/555) | Y 
 0x09B4 | Huobi assets are not displayed when using cross exchange MM | [#826](https://github.com/CoinAlpha/hummingbot/issues/826) | Y  
 0xe363 | XEMM not placing orders in empty maker market | [#854](https://github.com/CoinAlpha/hummingbot/issues/854) | Y  
 0x75e8 | Volume traded from Oct 10 - 13 are missing | [#918](https://github.com/CoinAlpha/hummingbot/issues/918) | Y 
 0x21a0 | code bug in ddex_market.pyx | [#923](https://github.com/CoinAlpha/hummingbot/issues/923) | Y  
 0x5a83 | Error running performance analysis while in paper trade arbitrage strategy | [#974](https://github.com/CoinAlpha/hummingbot/issues/974) | Y   
 0x8b5d | Inventory skew enabled causes order size becomes less than allowed on Bittrex | [#1092](https://github.com/CoinAlpha/hummingbot/issues/1092) | Y   
 0x887c | Cross-exchange MM strategy has incorrect price calculation with BUSD as base token | [#1120](https://github.com/CoinAlpha/hummingbot/issues/1120) | Y   
 0x8264 | Liquid connector on non-fiat quote asset | [#1331](https://github.com/CoinAlpha/hummingbot/issues/1331) | Y   
 0x5447 | Liquid, bot stuck when using pure market making for trading pair TRX-BTC | [#1375](https://github.com/CoinAlpha/hummingbot/issues/1375) | Y  

**Happy 🐞 hunting!**
