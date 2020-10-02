# Liquidity Mining

!!! info "Important Disclaimer"
    <small><ul><li>The content of this Site does not constitute investment, financial, legal, or tax advice, nor does any of the information contained on this Site constitute a recommendation, solicitation, or offer to buy or sell any digital assets, securities, options, or other financial instruments or other assets, or to provide any investment advice or service.<li>There is no guarantee of profit for participating in liquidity mining.<li>Participation is subject to eligibility requirements.</ul></small>
    **Please review the [Liquidity Mining Policy](https://hummingbot.io/liquidity-mining-policy/) for the full disclaimer.**

## What is it?
Liquidity mining is a community-based, data-driven approach to market making, in which a token issuer or exchange can reward a pool of miners to provide liquidity for a specified token.

Liquidity mining sets forth an analytical framework for determining market maker compensation based on (1) time (order book consistency), (2) order spreads, and (3) order sizes, in order to create a fair model for compensation that aligns a miner's risk with rewards.

## Getting Started

### Read me first
- [How it works](https://www.notion.so/hummingbot/What-is-liquidity-mining-c2eb7d68e28b42278e5efead9a247507)
- [Liquidity Mining FAQs](https://docs.hummingbot.io/faq/liquidity-mining/)
- [Liquidity Mining whitepaper](https://hummingbot.io/liquidity-mining.pdf)

### Installation and configuration
- [Hummingbot Quickstart Guide](https://docs.hummingbot.io/quickstart)
- [Hummingbot Miners](https://miners.hummingbot.io/): The **official Liquidity Mining app** where you can see real-time rates of return and track your payouts

### Support
- [Get help on Discord](https://discord.hummingbot.io): Join the **#liquidity-mining** channel for 24/7 support

## Current Campaign Terms

!!! warning "Important information regarding campaign terms"
    **Terms are subject to change**. We will notify participants of changes, if any, on our [Discord](https://discord.hummingbot.io) and [Reddit](https://www.reddit.com/r/Hummingbot/). Participants can also check the latest news in the [Hummingbot Miner](https://miners.hummingbot.io/) app.

**Updated liquidity mining policy on payments**

Qualified participants will be eligible to receive compensation in accordance with each liquidity mining campaign’s schedule of Liquidity Mining Payments, which will be based on each participant’s trading activity (in particular, orders placed and their sizes and spreads) in the tokens subject to the liquidity mining campaign.

==Participants must enter a valid wallet address applicable for the campaign that they are participating in.== CoinAlpha does not take any responsibility and will not reimburse for any loss of funds due to a participant submitting an incorrect or invalid wallet address.


**Orders outstanding for more than 30 minutes not counted for rewards**

Work on removing this limit is in progress, you can read more about it in our [Reddit post](https://www.reddit.com/r/Hummingbot/comments/hz5xv3/tracking_rewards_for_orders_longer_than_30m/).

!!! Tip
    To ensure that orders do not stay outstanding for longer than 30 minutes, Hummingbot users should disable [order refresh tolerance](https://docs.hummingbot.io/strategies/advanced-mm/order-refresh-tolerance/#how-it-works).

**Minimum reward payout amount**

Due to the recent surge in Ethereum gas price, Hummingbot will impose a $50.00 minimum on the weekly payout ==for payments on the Ethereum blockchain (currently USDC and RLC)==, starting with the next scheduled payout on September 18th (UTC).

For miners who earn < $50 within one week, their rewards will be accrued and rolled over to the next period, read more in this [Reddit post](https://www.reddit.com/r/Hummingbot/comments/ip4mc3/announcement_raising_minimum_payment_to_50/).

!!! Note
    XZC payments are not subject to a minimum payout reward; all payouts will be made for each period.


**Native XZC rewards for Zcoin campaign**

Starting September 15, 2020 UTC, we rolled out [XZC native token payments](https://hummingbot.io/blog/2020-09-xzc-native-token-payment/) for the Zcoin liquidity mining campaign! Miners participating in the Zcoin liquidity mining campaign will start earning and be paid in XZC tokens.

Participating miners should enter their XZC wallet address in the miner app.

!!! Note
    You can use your Binance XZC deposit address and enter in the miner app to receive XZC directly into Binance.


## Current Reward Period

**September 29, 2020 12:00am UTC - October 6, 2020 12:00am UTC**

<table>
  <thead>
    <th>Token Issuer</th>
    <th>Trading pair</th>
    <th>Exchange</th>
    <th>Maximum spread</th>
    <th>Spread factor *</th>
    <th>Weekly rewards</th>
  </thead>
  <tbody>
      <tr>
      <td rowspan="3"><a href="#coti">COTI</a><br></td>
      <td>COTI/BTC</td>
      <td>Binance.com</td>
      <td>2%</td>
      <td>8</td>
      <td>USDC 250</td>
    </tr>
    <tr>
      <td>COTI/USDT</td>
      <td>Binance.com</td>
      <td>2%</td>
      <td>8</td>
      <td>USDC 250</td>
    </tr>
    <tr>
      <td>COTI/BNB</td>
      <td>Binance.com</td>
      <td>2%</td>
      <td>8</td>
      <td>USDC 250</td>
    </tr>        
    <tr>
      <td rowspan="3"><a href="#mainframe">Mainframe</a><br></td>
      <td>MFT/USDT</td>
      <td>Binance.com</td>
      <td>2%</td>
      <td>8</td>
      <td>USDC 200</td>
    </tr>
    <tr>
      <td>MFT/ETH</td>
      <td>Binance.com</td>
      <td>2%</td>
      <td>8</td>
      <td>USDC 275</td>
    </tr>
    <tr>
      <td>MFT/BNB</td>
      <td>Binance.com</td>
      <td>2%</td>
      <td>8</td>
      <td>USDC 275</td>
    </tr>
    <tr>
      <td rowspan="3"><a href="#iexec">iExec</a><br></td>
      <td>RLC/BTC</td>
      <td>Binance.com</td>
      <td>2%</td>
      <td>8</td>
      <td>RLC 180</td>
    </tr>
    <tr>
      <td>RLC/USDT</td>
      <td>Binance.com</td>
      <td>2%</td>
      <td>8</td>
      <td>RLC 180</td>
    </tr>
    <tr>
      <td>RLC/ETH</td>
      <td>Binance.com</td>
      <td>2%</td>
      <td>8</td>
      <td>RLC 180</td>
    </tr>
    <tr>
      <td rowspan="2"><a href="#zcoin">Zcoin</a></td>
      <td>XZC/BTC</td>
      <td>Binance.com</td>
      <td>2%</td>
      <td>8</td>
      <td><b>XZC 125</b></td>
    </tr>
    <tr>
      <td>XZC/USDT</td>
      <td>Binance.com</td>
      <td>2%</td>
      <td>8</td>
      <td><b>XZC 125</b></td>
    </tr>
  </tbody>
</table>


\* Spread density function constant is one of the factors that determines the relative weighting of orders by spread, i.e., the amount of additional rewards for orders with tighter spreads vs those with wider spreads. Refer to this [spreadsheet](https://docs.google.com/spreadsheets/d/1mUZsQoiqlMs5HjcL6AXSKIx1oaULsmuQStJaCc2wggQ/edit?ts=5f1e89bd#gid=18167917) for the spread weights and for a visual of the graph that shows the curve.


## Upcoming Changes to Terms 

**Adding support for TRC20 USDT for USD-based liquidity mining payments**
 
In response to rising Ethereum gas prices, we will be giving miners the option to receive USDT-TRON for USD-based liquidity mining rewards. Receiving USDT-TRON mining rewards will not be subject to any minimum amounts, and miners can have rewards paid directly into their exchange accounts.

Miners can also choose to continuing receiving rewards to their Ethereum wallet, but still subject to minimum payment amounts.

https://hummingbot.io/blog/2020-09-migrating-to-trc20-usdt-payment/

Timetable:

- Shortly/next few days: Tron wallet enabled on Hummingbot Miner

- October 6, 2020 12:00am UTC: Campaigns with USDC reward pools will switch to USDT

- October 16, 2020 UTC: First USDT-TRON payout

!!! note
    Users will be required to enter Tron wallet address in the Hummingbot Miners app to enable USDT-TRON payments.

Binance.com (as well as many of the major exchanges) support TRC20-USDT, so you can use a USDT TRC20 deposit address to receive rewards directly into your exchange account.


## Token Issuers

### COTI
[COTI](https://coti.io/) is a fully encompassing “finance on the blockchain” ecosystem that is designed specifically to meet the challenges of traditional finance (fees, latency, global inclusion and risk) by introducing a new type of DAG based base protocol and infrastructure that is scalable, fast, private, inclusive, low cost and is optimized for real time payments. The ecosystem includes a [DAG based Blockchain](https://www.youtube.com/watch?v=kSdRxqHDKe8), a [Proof of Trust Consensus Algorithm](https://coti.io/files/COTI-technical-whitepaper.pdf), a [multiDAG](https://medium.com/cotinetwork%27/coti-is-launching-multidag-a-protocol-to-issue-tokens-on-a-dag-infrastructure-5c6282e5c3d1) a [Global Trust System](https://medium.com/cotinetwork/introducing-cotis-global-trust-system-gts-an-advanced-layer-of-trust-for-any-blockchain-7e44587b8bda), a [Universal Payment Solution](https://medium.com/cotinetwork/coti-universal-payment-system-ups-8614e149ee76), a [Payment Gateway](https://medium.com/cotinetwork/announcing-the-first-release-of-the-coti-payment-gateway-4a9f3e515b86), as well as consumer (COTI Pay) and merchant (COTI Pay Business) applications.

[Whitepaper](https://coti.io/files/COTI-technical-whitepaper.pdf) | [Twitter](https://twitter.com/COTInetwork) | [Telegram](https://t.me/COTInetwork) | [Discord](https://discord.me/coti) | [Github](https://github.com/coti-io) | [CoinMarketCap](https://coinmarketcap.com/currencies/coti/markets/) | [CoinGecko](https://www.coingecko.com/en/coins/coti)

### iExec

[iExec (RLC)](https://iex.ec/) claims to have developed the first decentralized marketplace for cloud computing resources. Blockchain technology is used to organize a market network where users can monetize their computing power, applications, and datasets. By providing on-demand access to cloud computing resources, iExec is reportedly able to support compute-intensive applications in fields such as AI, big data, healthcare, rendering, or FinTech. iExec's RLC token has been listed on Binance, Bittrex, etc.

[Whitepaper](https://iex.ec/wp-content/uploads/pdf/iExec-WPv3.0-English.pdf) | [Twitter](https://twitter.com/iEx_ec) | [Telegram](https://goo.gl/fH3EHT) | [Github](https://github.com/iExecBlockchainComputing) | [Explorer](https://etherscan.io/token/0x607F4C5BB672230e8672085532f7e901544a7375) | [CoinMarketCap](https://coinmarketcap.com/currencies/rlc/markets/) | [CoinGecko](https://www.coingecko.com/en/coins/iexec-rlc)

### Mainframe

The [Mainframe (MFT)](https://mainframe.com/) Lending Protocol allows anyone to borrow against their crypto. Mainframe uses a bond-like instrument, representing an on-chain obligation that settles on a specific future date. Buying and selling the tokenized debt enables fixed-rate lending and borrowing — something much needed in decentralized finance today.

[Blog](https://blog.mainframe.com) | [Twitter](https://twitter.com/Mainframe_HQ) | [Discord](https://discord.gg/mhtSRz6) | [Github](https://github.com/MainframeHQ) | [CoinMarketCap](https://coinmarketcap.com/currencies/mainframe/) | [CoinGecko](https://www.coingecko.com/en/coins/mainframe)

### Zcoin

[ZCoin (XZC)](https://zcoin.io/) is an open-source privacy-focused cryptocurrency token that launched in Sep 2016. Zcoin originally pioneered the use of Zerocoin to enable privacy but has since transitioned to a scheme called Sigma which is based on a paper by Jens Groth and Markulf Kohlweiss that reportedly allows greater scalability and removes the need for trusted setup in Zerocoin. With Zcoin’s Sigma feature, only the sender and receiver would be able to ascertain the exchange of funds in a given transaction, as no transaction histories are linked to the actual coins. Zcoin is also the creator of the Lelantus privacy protocol which improves Sigma's privacy and functionality. Its ZC token has been listed on Binance, Huobi Global, Bittrex, etc. 

[Whitepaper](https://zcoin.io/tech/) | [Twitter](https://twitter.com/zcoinofficial) | [Telegram](https://t.me/zcoinproject) | [Github](https://github.com/zcoinofficial) | [Explorer](https://chainz.cryptoid.info/xzc/) | [CoinMarketCap](https://coinmarketcap.com/currencies/zcoin) | [CoinGecko](https://www.coingecko.com/en/coins/zcoin)

