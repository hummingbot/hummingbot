# Adding Transaction Costs to Prices

Transaction costs can now be added to the price calculation. `fee_pct` refers to the percentage maker fees per order (generally common in Centralized exchanges) while `fixed_fees` refers to the flat fees (generally common in Decentralized exchanges).

- The bid order price will be calculated as:

![Bid price with transaction cost](/assets/img/trans_cost_bid.PNG)

- The ask order price will be calculated as:

![Ask price with transaction cost](/assets/img/trans_cost_ask.PNG)

Adding the transaction cost will reduce the bid order price and increase the ask order price i.e. putting your orders further away from the mid price.

We currently display warnings if the adjusted price post adding the transaction costs is 10% away from the original price. If the buy price with the transaction cost is zero or negative, it is not profitable to place orders and orders will not be placed.

## Relevant Parameters

| Parameter | Prompt | Definition |
|-----------|--------|------------|
| **add_transaction_costs** | `Do you want to add transaction costs automatically to order prices? (Yes/No)` | Whether to enable adding transaction costs to order price calculation. |