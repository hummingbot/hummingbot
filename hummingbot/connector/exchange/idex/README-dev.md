# IDEX Connector - Development

This is a temporal document and will be deleted when development is finished.

Search keys: Mark comments intended as temporal annotations in the code with questions 
with labels/prefixes, one of: TODO, FIXME, DELETE, TEMPORAL.


## Unknowns

* Minimum trade size for IDEX.
  
* Mismatch in testnets: Rinkeby testnet (IDEX) is not well supported in Hummingbot.

* Rate limit for IDEX ?

* Can we introduce new dependency (asynctest) in PR? Needed to mock aiohttp.ClientSession.get 
  (asynchronous context manager). My question in Discord: 
  https://discord.com/channels/530578568154054663/642099307922718730/818501894657933333
  



## IDEX auth

For our internal tests (Do not commit credentials!!!)

```text
# TODO: DO NOT COMMIT CREDENTIALS !!!!!!!!!
idex_api_key = ''
idex_api_secret_key = ''
idex_wallet_private_key = ''
idex_contract_blockchain = 'ETH'
base_url = 'https://api-sandbox-eth.idex.io/'  # rest url for sandbox (rinkeby) ETH chain
```

You can set up environment variables with the same name and they will be read into the `conf` module.



### Questions:

- where used?

- how compare to auth coinbase, kraken, vitrex?
  
- need change?

