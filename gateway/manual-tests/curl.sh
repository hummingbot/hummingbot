# test that the gateway-api server is running
curl -X GET localhost:5000/

# test that the ethereum routes are mounted
curl -X GET localhost:5000/eth/

# the environment variable ETH_PRIVATE_KEY must be set with your private key
# in order for the following tests to work

# get balances for your private key
curl -X POST -H "Content-Type: application/json" -d "{\"privateKey\":\"$ETH_PRIVATE_KEY\",\"tokenSymbols\":[\"ETH\",\"WETH\",\"DAI\"]}" localhost:5000/eth/balances

curl -X POST -H "Content-Type: application/json" -d "{\"privateKey\":\"$ETH_PRIVATE_KEY\",\"tokenSymbols\":[\"DAI\"]}" localhost:5000/eth/balances

# approve Ethereum to spend your WETH

curl -X POST -H "Content-Type: application/json" -d "{\"privateKey\":\"$ETH_PRIVATE_KEY\",\"spender\":\"0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D\",\"token\":\"DAI\"}" localhost:5000/eth/approve

# check status of transaction 0x6d068067a5e5a0f08c6395b31938893d1cdad81f54a54456221ecd8c1941294d

curl -X POST -H "Content-Type: application/json" -d "{\"txHash\":\"0x6d068067a5e5a0f08c6395b31938893d1cdad81f54a54456221ecd8c1941294d\"}" localhost:5000/eth/poll

# update config

curl -X POST -H "Content-Type: application/json" -d "{\"LOG_TO_STDOUT\":true}" localhost:5000/config/update
