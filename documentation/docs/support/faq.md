# Frequently Asked Questions

Here are some of the common questions from our users about running Hummingbot.

### I’m running on pure market making strategy. Why is it only placing buy orders and not sell orders? (or vice-versa)

Check the balance in your inventory. If you don't have enough balance on one side, it will only place orders on the side that it can. This is fine and expected behavior for the strategy.

### Why does my starting inventory value keep changing?

Starting inventory value is calculated based on current market prices at the time you start the bot. Therefore, it will change if there are changes in the price of the asset. But if you look at your actual inventory token balances, those should be consistent after considering any trades that have occurred.

This [blog post](https://hummingbot.io/blog/2019-07-measure-performance-crypto-trading/) explains how we calculate performance. Basically, we calculate the market value of the net change in inventory.
