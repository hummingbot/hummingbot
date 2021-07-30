---
title: Beaxy
description: About Beaxy connector
---

import Callout from "../../src/components/Callout";

Beaxy is a digital asset exchange that aims to set itself apart from others in the field by offering a feature-rich platform built from the ground up with clients of every experience level in mind.

## Using the Connector

To use [Beaxy](https://beaxy.com/) connector, you will need to generate and provide your API key to trade using Hummingbot.

```
Enter your Beaxy API key >>>
Enter your Beaxy secret key >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

<Callout
  type="tip"
  body="For copying and pasting into Hummingbot, see [this page] for more instructions in our Hummingbot Help Center."
  link={[
    "https://hummingbot.zendesk.com/hc/en-us/articles/900004871203-Copy-and-paste-your-API-keys",
  ]}
/>

### Creating Beaxy API Keys

1. Log in to your account at https://beaxy.com/, then click your account then, from the drop-down, click on API management (If you do not have an account, you will have to create one and enable 2FA.).

<Callout
  type="tip"
  body="You must enable 2FA in your Beaxy account to create the API key. [How to enable 2FA]?"
  link={[
    "https://beaxy.com/faq/how-do-i-enable-disable-2fa-two-factor-authentication/",
  ]}
/>

![](/img/beaxyapi.png)

2. Then click create an API key.

![](/img/beaxyapi-key.png)

3. Give the API a name, then click create.

![](img/beaxycreate.png)

3. Now that you have created an API key, connect it to Hummingbot using the `connect` command.

Make sure you store your Secret Key somewhere secure and do not share it with anyone. Your Secret Key will only be displayed once at the time when you create the API.

<Callout
  type="warning"
  body="If you lose your Secret Key, you can delete the API and create a new one. However, it will be impossible to reuse the same API."
/>

## Miscellaneous Info

### Minimum Order Sizes

See [this page](https://beaxy.com/faq/what-are-the-market-trading-rules/) for the minimum order size per trading pair.

### Transaction Fees

Beaxy has a tiered fee structure that starts at a 0.25% fixed fee per trade on market takers and a 0.15% maker fee.

- [Fees](https://beaxy.com/faq/what-is-the-fee-structure/#:~:text=Trading%20Fees,and%20a%200.15%25%20maker%20fee.)

Users can override the default fees by editing [`conf_fee_overrides.yml`](/operation/override-fees/).
