# Pure market making

## How it works

In a Nutshell, Pure market making can be described as the user posting limit bid and ask offers on a market and expecting other users to fill their orders. 
You have control over how far away from the mid price your posted bid and asks are, whats the order quantity and how often you want to cancel and replace them.  

!!! note
    Please exercise caution while running this strategy and set appropriate stop loss limits

### Schematic

The diagram below illustrates how market making works.  Hummingbot makes a market by placing buy and sell orders on a single exchange, specifying prices and sizes.

<small><center>***Figure 1: Hummingbot makes a market on an exchange***</center></small>

![Figure 1: Hummingbot makes a market on an exchange](/assets/img/pure-mm.png)

## Prerequisites: Inventory

1. You will need to hold inventory of quote and base currencies on the exchange.
2. You will also need some Ethereum to pay gas for transactions on a DEX (if applicable).

## Configuration walkthrough

To come...

## Configuration parameters

To come...