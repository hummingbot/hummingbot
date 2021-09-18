---
tags:
- spot exchange connector
---

# `ascend_ex`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/ascend_ex)

## ℹ️ Exchange Info

* Website: https://ascendex.com/
* Transaction fees: https://ascendex.com/en/feerate/transactionfee-traderate
* Minimum order size: https://ascendex.com/en/help-center/articles/360025991074
* Creating API keys: https://ascendex.com/en/help-center/articles/4405542558099

## 👷 Maintainer

CoinAlpha, Inc.

## 🔑 Connect Exchange

Run `connect ascend_ex` in order to enter your API keys:

```
Enter your AscendEx API key >>>
Enter your AscendEx secret API key >>>
```

## 🪙 Fee Assumptions

Hummingbot assumes 0.1% maker fees and 0.1% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/ascend_ex/ascend_ex_utils.py#L15)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).

