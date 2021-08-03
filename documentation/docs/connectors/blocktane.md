# Blocktane

Launched in 2020, Blocktane was designed and built in partnership with Tritum and operated a high-performance digital asset exchange infrastructure designed with technology and principles from traditional financial markets to serve clients with equal confidence and quality as any other financial institution.

## Using the connector

To use [Blocktane](https://blocktane.io/) connector, you will need to generate and provide your API key to trade using Hummingbot.

```
Enter your Blocktane API key >>>
Enter your Blocktane secret API key >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip
    For copying and pasting into Hummingbot, see [this page](https://hummingbot.zendesk.com/hc/en-us/articles/900004871203-Copy-and-paste-your-API-keys) for more instructions in our Hummingbot Help Center.

### Creating Blocktane API keys

1. Log in to your account at https://blocktane.io/, then click your profile > My API keys (If you do not have an account, you will have to create one and verify your ID.)

!!! tip
    You must enable 2FA in your Blocktane account to create the API key. [How to enable 2FA](https://help.blocktane.io/faq-en/getting-started/)?

![](/assets/img/blocktaneaccount-api.png)

2. Create a new API key

![](/assets/img/account-blocktane-api.png)

3. After clicking create new API key, enter 2FA code, and the key will be generated

![](/assets/img/api-blocktane.png)

Make sure you store your Secret Key somewhere secure and do not share it with anyone. Your Secret Key will only be displayed once at the time when you create the API.

!!! warning
    If you lose your Secret Key, you can delete the API and create a new one. However, it will be impossible to reuse the same API.

## Miscellaneous info

### Minimum order sizes

Each trading pair has a unique minimum order size denominated in the base currency. You can access the minimum order size for a specific token pair using Blocktane's API at the following URL:

```
https://trade.blocktane.io/api/v2/xt/public/markets
```

Sample output:

```
{
  "id": "btcbrl",
  "displayName": "BTC/BRL",
  "base_unit": "btc",
  "quote_unit":"brl",
  "min_price":"0.01",
  "max_price":"1000000000.0",
  "min_amount":"0.0001",
  "amount_precision":8,
  "price_precision":2,
  "state":"enabled"
}
```

In this example, the minimum order size is 0.0001 BTC. For the most part, the smallest order size allowed is about the equivalent of \$4.

### Transaction fees

By default, trading fees are 0.15% for maker fees and 0.20% for takers on Blocktane. See the article below for more details.

- [Fees & limits](https://help.blocktane.io/faq-en/fees-limits/)

Users can override the default fees by editing [`conf_fee_overrides.yml`](/operation/override-fees/).
