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

curl -X POST -H "Content-Type: application/json" -d "{\"privateKey\":\"0b8040a6719bc21e2fce075b843e33cc1fab503c105c76bd5375e3f784724bc6\",\"spender\":\"0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D\",\"token\":\"DAI\"}" localhost:5000/eth/approve

# check status of transaction 0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362

curl -X POST -H "Content-Type: application/json" -d "{\"txHash\":\"0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362\"}" localhost:5000/eth/poll

# update config

curl -X POST -H "Content-Type: application/json" -d "{\"LOG_TO_STDOUT\":true}" localhost:5000/config/update
