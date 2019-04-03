# Release Notes - Version 0.3.0

🚀Welcome to `hummingbot` version 0.3.0! This release contains some huge updates and major bug fixes. We highlight some of the most signficant ones below:

## 📈Support for 0x open order book relayers (Radar Relay)
Hummingbot now supports market making on 0x open order book relayers such as Radar Relay. Since it costs gas to cancel orders in open order book relayers, we have revised the **cross-exchange market making strategy** to include 3 new parameters:

* `active_order_canceling`: if TRUE, the bot cancels orders when they are unprofitable based on `min_profitability`; otherwise, it relies on order expirations and renews them after they expire, unless `cancel_order_threshold` is reached.
* `limit_order_min_expiration`: expiration time in seconds per order. This parameter is ignored when market making on exchanges that don't support expirations.
* `cancel_order_threshold`: if `active_order_cancelling` is FALSE, the bot will cancel orders when the spread between maker and taker markets reaches this lower threshold, which can be zero or negative. This allows the bot to cancel orders when they become unprofitable enough that paying gas to do so makes sense.

When this connector has been tuned for Radar Relay, we believe that it should be usable with minor modifications for other 0x open order book relayers that implement the [Standard Relayer API](https://github.com/0xProject/standard-relayer-api). If you are a 0x open order book relayer and would like to discuss integration with Hummingbot, please join our [Discord](https://discord.hummingbot.io) and let us know!

## ⚒ New strategy: Arbitrage
We have added the second strategy mentioned in our whitepaper: arbitrage. Arbitrage allows you to monitor two identical or similar trading pairs on different exchanges and wait for a *crossed market* (when you can buy for a lower price on one exchange and sell for a higher price on another). Note that since the **arbitrage** strategy used different parameters from **cross-exchange market making**, Hummingbot will prompt you to create a separate configuration file for arbitrage.

With two strategies and three exchanges, there are now 6 possible combinations of cross-exchange strategies that Hummingbot users can try.

## ⚙ Configurable data collection
While we only collect data in order to improve Hummingbot and report aggregate volume to exchange partners, we recognize that users attitudes toward data collection vary widely. Therefore, we've made data collection fully modifiable via the configuration file `conf/hummingbot_logs.yml`. We will document how users can customize these settings, as well as publish a few configurations, shortly.

## 💾 Support for multiple configurations per strategy

Since we expect that users will experiment with different combinations of trading pairs, configuration settings, and exchanges, we wanted to allow users to save multiple configurations per strategy. This allows users to load a saved configuration when they start a bot, as well as run multiple bots simultaneously.

## 🐞 Bug fixes and miscellaneous updates
* Fixed another bug related to the Binance co-routine scheduler that prevented Binance API calls from going through after running the bot for a while
* Fixed a bug in which the bot didn't wait for confirmation of cancelled orders before placing new ones, giving rise to insufficient balance errors
* Fixed bugs related to clock difference errors between user's machine and Binance
* Fixed a status pool loop error that affected DDEX and Radar Relay
* Synchronized file names to use the `cross exchange market making` name rather than the old `hedged_market_making` name

## 🙏 Thank you

Last but certainly not least, a big **Thank You!** to the alpha testers who went the extra mile to help improve `hummingbot` by submitting bugs and feature requests, etc.

* Everyone who participated in design feedback, including `psq`, `reverendus`, `mf10r_vc`, `thomas_wyre`, and Shichao/Mingda (DDEX)
* `christopher` (1kx)
* `Joshua | Bamboo Relay`
