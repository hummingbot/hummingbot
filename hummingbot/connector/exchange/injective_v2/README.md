## Injective v2

This is a spot connector created by **[Injective Labs](https://injectivelabs.org/)**.
The difference with `injective` connector is that v2 is a pure Python connector. That means that the user does not need to configure and run a Gateway instance to use the connector.
Also, `injective_v2` has been implemented to use delegated accounts. That means that the account used to send the transactions to the chain for trading is not the account holding the funds.
The user will need to have one portfolio account and at least one trading account. And permissions should be granted with the portfolio account to the trading account for it to operate using the portfolio account's funds.

### Trading permissions grant
To grant permissions from a portfolio account to a trading account to operate using the portfolio account funds please refer to the script `account_delegation_script.py`

### Connector parameters
When configuring a new instance of the connector in Hummingbot the following parameters are required:

- **injective_private_key**: the private key of the trading account (grantee account)
- **injective_subaccount_index**: the index (decimal number) of the subaccount from the trading account that the connector will be operating with
- **injective_granter_address**: the public key (injective format address) or the portfolio account
- **injective_granter_subaccount_index**: the index (decimal number) of the subaccount from the portfolio account (the subaccount holding the funds)