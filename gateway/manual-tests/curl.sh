# you need to install to programs: curl and envsubst

# You must the following values in your command line
# export ETH_ADDRESS='<put-your-public-key-here>'
# export AVALANCHE_ADDRESS='<put-your-public-key-here>'
# export NEAR_ADDRESS='<put-your-public-key-here'
# export BSC_ADDRESS='put-your-binance-smart-chain-key-here'

# -k is --insecure, this disables certificate verification and should only be
# used for local development and testing

# Config

curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT https://localhost:15888/ | jq

curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT https://localhost:15888/connectors | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/config_update.json)" https://localhost:15888/config/update | jq

# Network

curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT https://localhost:15888/network/status | jq

curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT "https://localhost:15888/network/status?chain=ethereum&network=kovan" | jq

curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT "https://localhost:15888/network/status?chain=avalanche&network=avalanche" | jq

curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT "https://localhost:15888/network/status?chain=harmony&network=harmony" | jq

curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT "https://localhost:15888/network/status?chain=cronos&network=mainnet" | jq

curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT https://localhost:15888/network/config | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/network_poll.json)" https://localhost:15888/network/poll | jq

curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT "https://localhost:15888/network/tokens?chain=ethereum&network=kovan" | jq

curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT "https://localhost:15888/network/tokens?chain=polygon&network=mumbai" | jq

curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT "https://localhost:15888/network/tokens?chain=cronos&network=mainnet" | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/network_balances.json)" https://localhost:15888/network/balances | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/bsc_balances.json)" https://localhost:15888/network/balances | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/cronos_balances.json)" https://localhost:15888/network/balances | jq

# Wallet

## add private keys
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/add_ethereum_key.json)" https://localhost:15888/wallet/add | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/add_avalanche_key.json)" https://localhost:15888/wallet/add | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/add_cronos_key.json)" https://localhost:15888/wallet/add | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/add_near_key.json)" https://localhost:15888/wallet/add | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/add_bsc_key.json)" https://localhost:15888/wallet/add | jq

## read public keys
curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT https://localhost:15888/wallet | jq

## remove keys
curl -s -X DELETE -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/remove_ethereum_key.json)" https://localhost:15888/wallet/remove | jq

curl -s -X DELETE -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/remove_avalanche_key.json)" https://localhost:15888/wallet/remove | jq

curl -s -X DELETE -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/remove_cronos_key.json)" https://localhost:15888/wallet/remove | jq

curl -s -X DELETE -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/remove_near_key.json)" https://localhost:15888/wallet/remove | jq

curl -s -X DELETE -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/remove_bsc_key.json)" https://localhost:15888/wallet/remove | jq

# AMM

## price

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/price_uniswap.json)" https://localhost:15888/amm/price | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/price_traderjoe.json)" https://localhost:15888/amm/price | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/price_dfk.json)" https://localhost:15888/amm/price

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/price_defira.json)" https://localhost:15888/amm/price | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/price_mad_meerkat.json)" https://localhost:15888/amm/price | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/price_vvs.json)" https://localhost:15888/amm/price | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/price_ref.json)" https://localhost:15888/amm/price | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/price_bsc_pancakeswap.json)" https://localhost:15888/amm/price | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/price_bsc_sushiswap.json)" https://localhost:15888/amm/price | jq


## trade

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/eth_uniswap_trade.json)" https://localhost:15888/amm/trade | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/avalanche_traderjoe_trade.json)" https://localhost:15888/amm/trade | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/harmony_dfk_trade.json)" https://localhost:15888/amm/trade | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/harmony_testnet_defira_trade.json)" https://localhost:15888/amm/trade | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/cronos_mmf_trade.json)" https://localhost:15888/amm/trade | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/cronos_vvs_trade.json)" https://localhost:15888/amm/trade | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/near_mainnet_ref_trade.json)" https://localhost:15888/amm/trade | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/bsc_pancakeswap_trade.json)" https://localhost:15888/amm/trade | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/bsc_sushiswap_trade.json)" https://localhost:15888/amm/trade | jq


## Perp - curie

### Market prices

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/perp_prices.json)" https://localhost:15888/amm/perp/market-prices | jq

### Marker Status
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/perp_prices.json)" https://localhost:15888/amm/perp/market-status | jq

### Marker pairs
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/perp_prices.json)" https://localhost:15888/amm/perp/pairs | jq

### Positon status

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/perp_position.json)" https://localhost:15888/amm/perp/position | jq

### Acct balance

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/perp_position.json)" https://localhost:15888/amm/perp/balance | jq

### Open position

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/perp_trade_open.json)" https://localhost:15888/amm/perp/open | jq

### Close position

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/perp_position.json)" https://localhost:15888/amm/perp/close | jq

## Lping

### add liquidity

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/eth_uniswap_add_liquidity.json)" https://localhost:15888/amm/liquidity/add | jq

### remove liquidity

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/eth_uniswap_position.json)" https://localhost:15888/amm/liquidity/remove | jq

### collect fees

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/eth_uniswap_position.json)" https://localhost:15888/amm/liquidity/collect_fees | jq

### get position

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/eth_uniswap_position.json)" https://localhost:15888/amm/liquidity/position | jq

### get pool price

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/eth_uniswap_pool_price.json)" https://localhost:15888/amm/liquidity/price | jq

# EVM

## nonce
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/eth_nonce.json)" https://localhost:15888/evm/nonce | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/avalanche_nonce.json)" https://localhost:15888/evm/nonce | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/cronos_nonce.json)" https://localhost:15888/evm/nonce | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/bsc_nonce.json)" https://localhost:15888/evm/nonce | jq

## allowances

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/eth_allowances.json)" https://localhost:15888/evm/allowances | jq

## approve

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/eth_approve.json)" https://localhost:15888/evm/approve | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/eth_perp_approve.json)" https://localhost:15888/evm/approve | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/avalanche_approve.json)" https://localhost:15888/evm/approve | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/cronos_approve.json)" https://localhost:15888/evm/approve | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/bsc_approve.json)" https://localhost:15888/evm/approve | jq

# Solana

## config
curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT https://localhost:15888/solana | jq

## get config
curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/solana_get_root.json)" https://localhost:15888/solana | jq

## get balances
curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/solana_get_balances.json)" https://localhost:15888/solana/balances | jq

## get token
curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/solana_get_token.json)" https://localhost:15888/solana/token | jq

## post token
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/solana_post_token.json)" https://localhost:15888/solana/token | jq

## post poll
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/solana_post_poll.json)" https://localhost:15888/solana/poll | jq


# NEAR

## get balances
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/near_network_balances.json)" https://localhost:15888/near/balances | jq

## get token
curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT "https://localhost:15888/near/tokens?chain=near&network=testnet" | jq

## post poll
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/near_post_poll.json)" https://localhost:15888/near/poll | jq


# CLOB

## get config
curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/clob_get_root.json)" https://localhost:15888/clob | jq

## get markets
curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/clob_get_markets.json)" https://localhost:15888/clob/markets | jq

## get order books
curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/clob_get_order_books.json)" https://localhost:15888/clob/orderBooks | jq

## get tickers
curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/clob_get_tickers.json)" https://localhost:15888/clob/tickers | jq

## get orders
curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/clob_get_orders.json)" https://localhost:15888/clob/orders | jq

## post orders
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/clob_post_orders.json)" https://localhost:15888/clob/orders | jq

## delete orders
curl -s -X DELETE -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/clob_delete_orders.json)" https://localhost:15888/clob/orders | jq

## get open orders
curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/clob_get_open_orders.json)" https://localhost:15888/clob/orders/open | jq

## get filled orders
curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/clob_get_filled_orders.json)" https://localhost:15888/clob/orders/filled | jq

## post settle funds
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/clob_post_settle_funds.json)" https://localhost:15888/clob/settleFunds | jq

# Serum

## get config
curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/serum_get_root.json)" https://localhost:15888/serum | jq

## get markets
curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/serum_get_markets.json)" https://localhost:15888/serum/markets | jq

## get order books
curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/serum_get_order_books.json)" https://localhost:15888/serum/orderBooks | jq

## get tickers
curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/serum_get_tickers.json)" https://localhost:15888/serum/tickers | jq

## get orders
curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/serum_get_orders.json)" https://localhost:15888/serum/orders | jq

## post orders
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/serum_post_orders.json)" https://localhost:15888/serum/orders | jq

## delete orders
curl -s -X DELETE -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/serum_delete_orders.json)" https://localhost:15888/serum/orders | jq

## get open orders
curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/serum_get_open_orders.json)" https://localhost:15888/serum/orders/open | jq

## get filled orders
curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/serum_get_filled_orders.json)" https://localhost:15888/serum/orders/filled | jq

## post settle funds
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/serum_post_settle_funds.json)" https://localhost:15888/serum/settleFunds | jq
