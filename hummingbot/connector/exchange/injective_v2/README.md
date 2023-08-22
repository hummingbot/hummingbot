## Injective v2

This is a spot connector created by **[Injective Labs](https://injectivelabs.org/)**.
The difference with `injective` connector is that v2 is a pure Python connector. That means that the user does not need to configure and run a Gateway instance to use the connector.
The connector supports two different account modes:
- Trading with delegate accounts
- Trading through off-chain vault contracts

There is a third account type called `read_only_account`. This mode only allows to request public information from the nodes, but since it does not require credentials it does not allow to perform trading operations.

### Delegate account mode
When configuring the connector with this mode, the account used to send the transactions to the chain for trading is not the account holding the funds.
The user will need to have one portfolio account and at least one trading account. And permissions should be granted with the portfolio account to the trading account for it to operate using the portfolio account's funds.

#### Trading permissions grant
To grant permissions from a portfolio account to a trading account to operate using the portfolio account funds please refer to the script `account_delegation_script.py`

#### Mode parameters
When configuring a new instance of the connector in Hummingbot the following parameters are required:

- **private_key**: the private key of the trading account (grantee account)
- **subaccount_index**: the index (decimal number) of the subaccount from the trading account that the connector will be operating with
- **granter_address**: the public key (injective format address) of the portfolio account
- **granter_subaccount_index**: the index (decimal number) of the subaccount from the portfolio account (the subaccount holding the funds)


### Off-chain vault mode
When configuring the connector with this mode, all the operations are sent to be executed by a vault contract in the chain.
The user will need to have a vault contract deployed on chain, and use the vault's admin account to configure this mode's parameters.

#### Mode parameters
When configuring a new instance of the connector in Hummingbot the following parameters are required:

- **private_key**: the vault's admin account private key
- **subaccount_index**: the index (decimal number) of the subaccount from the vault's admin account
- **vault_contract_address**: the address in the chain for the vault contract
