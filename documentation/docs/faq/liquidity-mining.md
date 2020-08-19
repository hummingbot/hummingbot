# Liquidity Mining FAQs

!!! info "Important Disclaimer"
    <small><ul><li>The content of this Site does not constitute investment, financial, legal, or tax advice, nor does any of the information contained on this Site constitute a recommendation, solicitation, or offer to buy or sell any digital assets, securities, options, or other financial instruments or other assets, or to provide any investment advice or service.<li>There is no guarantee of profit for participating in liquidity mining.<li>Participation is subject to eligibility requirements.</ul></small>
    **Please review the [Liquidity Mining Policy](https://hummingbot.io/liquidity-mining-policy/) for the full disclaimer.**


### Do my earnings in one market affect other markets?
No, reward allocations for each market are calculated independently. Each payment distribution will be based on qualifying activity in the immediately preceding weekly epoch, and not on prior epochs.

### How do you verify the liquidity that I provide?
In order to accurately measure liquidity and allocate rewards, miners need to provide a working read-only API key for each exchange where they want to earn rewards. Our data infrastructure uses read-only API keys to collect and aggregate order data for each miner.

In addition, we run proprietary algorithms in order to attempt any prohibited actions such as wash trading and spoofing. While exploitative practices can be difficult to identify given the adversarial nature of the market, we believe that the combination of our focus on compliance, granular data feeds, and machine learning-based algorithms may deter and detect bad actors.

<!--
### Why do I need an Ethereum wallet to sign up?

The Hummingbot Miners app uses your Ethereum wallet address to:

1. **assign you a unique user ID**.  The Hummingbot miners app associates your configurations (e.g. email address, API configurations), as well as activity.  This allows the miners app to display your user-specific information such as rewards earned and payout history.
2. **send you token payouts**: mining rewards payouts will be sent to this address
-->


### My bot is running but I'm not earning any rewards!

!!! note
    It may takes up to 1 hour for our system to start tracking newly created bots and crediting them with rewards.

Check the following if:

1. You are not running Hummingbot in paper trading mode, which doesn't place real orders.
2. Your bot is actually placing orders on the exchange. You should be able to see them in the exchange website. Make sure you're running token pair on our [active campaigns](https://docs.hummingbot.io/liquidity-mining/#current-campaign-terms).
3. If you are running Hummingbot locally on Mac or Windows computer, your machine didn't go to sleep or lost internet connection which prevents Hummingbot from maintaining orders.

If these 3 reasons are not the cause, you can email a CSV export of your Binance order history for a particular market to accounts@hummingbot.io. Make sure to used or include the email address registered for liquidity mining.

!!! note
    We can only provide you with our system's data and cannot credit users for past rewards.

### When are liquidity mining rewards paid out?
Each weekly epoch runs begins and ends at Tuesday 12am UTC. Rewards are distributed to each participant's registered Ethereum address 3 calendar days after the end of each epoch.

### How do I verify my payouts?
Your weekly payout email receipts contains links to the blockchain transaction confirmations. You can find these transaction confirmation links if you click on the Rewards Paid table in the Activity page.

### I don't see my earnings on my metamask and on etherscan link from my email weekly reward.

Click the etherscan link provided on email and navigate to `Erc20 Token Txns` as shown on image below, Or you may just need to add USDC token to MetaMask so you can view them. Please follow the instructions in this URL: [adding ERC20 Tokens](https://metamask.zendesk.com/hc/en-us/articles/360015489031-How-to-View-Your-Tokens)

![](../assets/img/erc20token.png)


### Do you store data that you collect with my read-only API keys?
At launch, we store individual orders and trades in order to isolate and prevent potential attempts to manipulate or abuse the system by malicious liquidity miners. After the system is more mature, we will adjust the data collection process so that we only store aggregate data and do not store individual orders and trades. We never share individual order and trade data with third parties.

### How is Hummingbot compensated for liquidity mining programs?
In return for administering liquidity mining programs, collecting the data necessary to verify the trading activity of participants, and automating the payout process, we receive compensation from our Liquidity Mining partners and customers.

### Can I earn rewards in multiple markets simultaneously?
Yes, you can run different instances of Hummingbot or your own software in order to earn rewards in multiple markets simultaneously.

### Do I need to use the Hummingbot client to participate in liquidity mining?
No; if you already have your own trading bots and strategies, you can still participate in liquidity mining by registering at [Hummingbot Miner](https://miners.hummingbot.io) and adding your exchange read-only API key.

For the general pool of users who don't have their own trading bots, we created Hummingbot as a way to provide them access to quant/algo strategies and the ability to market make.
