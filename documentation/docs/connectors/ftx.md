# FTX

FTX is a cryptocurrency exchange launched in 2019. It allows users to trade contracts on crypto assets, or buy tokens representing other assets. Its team comes from Wall Street quant firms and tech companies.

The [FTX Foundation](https://ftx.com/foundation) donates 1% of all net fees to charity, and has earmarked more than \$7 million for "the world's most effective charities" so far.

## Using the connector

> The connector is for [FTX](https://ftx.com). The connector will not work with [FTX US](https://ftx.us). Because it is a centralized exchange, you will need to generate and provide your API key in order to trade using Hummingbot.

To use the connector, run the `connect ftx` command in the Hummingbot client.

![](/assets/img/ftx-api.png)

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip
    For copying and pasting into Hummingbot, see [this page](https://hummingbot.zendesk.com/hc/en-us/articles/900004871203-Copy-and-paste-your-API-keys) for more instructions in our Support guide.

### Creating FTX API keys

You can create API keys from your FTX profile page. Under the API tab will be a `CREATE` button.

![](/assets/img/ftx-create-api.png)

Consult the FTX [API Documentation](https://help.ftx.com/hc/en-us/articles/360028807171-api-docs) for more information.

!!! warning
    For API key permissions, we recommend using only #orders# enabled (read and write) API keys; enabling #withdraw, transfer, or the equivalent# is unnecessary for current Hummingbot strategies.

### Exchange status

Users can go to https://ftx.com/status to check the status of the exchange and review past or ongoing incidents.

### Minimum order sizes

When creating a strategy with Hummingbot, the prompt will include a minimum order size.

![](/assets/img/ftx-min-order.png)

### Transaction fees

FTX has a tiered fee structure.

![](/assets/img/ftx-fees.png)

Information on trading fees can be found [here](https://help.ftx.com/hc/en-us/articles/360024479432-Fees)

> **Note**: there is also a [VIP program](https://help.ftx.com/hc/en-us/articles/360032890872-VIP-program), as well as a [Backstop Liquidity Provider program](https://help.ftx.com/hc/en-us/articles/360024479392)
