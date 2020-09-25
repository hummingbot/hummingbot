# Minimum Order Size

<style>
    .div-1 {
        background-color: #000000;
    }
</style>

During pure market making/cross-exchange market making strategy creation, you be prompted with one of the following parameters for order amount:

<div class="div-1"> <font color="#20a26a">What is the amount of ETH per order? (minimum 0.0703) >>></font></div>

The minimum order size is calculated as `min_quote_order_amount/current mid price`

The `min_quote_order_amount` is defined in the  **conf_global.yml**

```
min_quote_order_amount:
- - BTC
  - 0.0011
- - ETH
  - 0.05
- - USD
  - 11
- - BNB
  - 0.5
```

However, the minimum order size fluctuates accordingly to market volatility(determined by the order price and volume). If the order size falls below the exchange's minimum order size, the orders will not be created.

**Example:**

If a trading pair mid-price is $2 and min trade amount is $10; minimum order size is 5. When the trading pair falls down to $1, the minimum order size is 10;thus,no order is created and "no active market orders" is displayed.

If you wish to set the bot to trade at your desired quote value for better risk management, the `min_quote_order_amount` section in the **conf_global.yml** needs to be edited. 

For example, the minimum order size(on the exchange) for LINK/ETH is 0.01 ETH and you wish to set a lower ETH value instead of the default of 0.05. To do so:

1. Download and open the **conf_global.yml** file.
2. Scroll down to the **Minimum default order amount** section.
3. Enter or edit the values accordingly.


