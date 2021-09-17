# export GATEWAY_KEY=''
# export GATEWAY_CERT=''

# -k is --insecure, this disables certificate verfication and should only be
# use for development
# test that the gateway-api server is running
curl -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT https://localhost:5000/

curl -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT https://localhost:5000/eth

# get balances for your private key
curl -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "{\"privateKey\":\"$ETH_PRIVATE_KEY\",\"tokenSymbols\":[\"ETH\",\"WETH\",\"DAI\"]}" https://localhost:5000/eth/balances

curl -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "{\"privateKey\":\"$ETH_PRIVATE_KEY\",\"spender\":\"0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D\",\"tokenSymbols\":[\"DAI\",\"WETH\"]}" https://localhost:5000/eth/allowances

curl -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "{\"privateKey\":\"$ETH_PRIVATE_KEY\",\"spender\":\"0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D\",\"tokenSymbols\":[\"DAI\",\"WETH\"]}" https://localhost:5000/eth/allowances

curl -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT  -H "Content-Type: application/json" -d "{\"privateKey\":\"$ETH_PRIVATE_KEY\",\"amount\":\"0\",\"spender\":\"0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D\",\"token\":\"DAI\"}" https://localhost:5000/eth/approve

curl -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT  -H "Content-Type: application/json" -d "{\"privateKey\":\"$ETH_PRIVATE_KEY\",\"spender\":\"0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D\",\"token\":\"DAI\"}" https://localhost:5000/eth/approve


curl -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT  -H "Content-Type: application/json" -d "{\"privateKey\":\"$ETH_PRIVATE_KEY\"}" https://localhost:5000/eth/nonce

curl -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT  -H "Content-Type: application/json" -d "{\"privateKey\":\"$ETH_PRIVATE_KEY\",\"amount\":\"0\",\"spender\":\"0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D\",\"token\":\"DAI\",\"nonce\":83}" https://localhost:5000/eth/approve

curl -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT  -H "Content-Type: application/json" -d "{\"privateKey\":\"$ETH_PRIVATE_KEY\",\"spender\":\"0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D\",\"token\":\"DAI\"}" https://localhost:5000/eth/approve


curl -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "{\"txHash\":\"0x6d068067a5e5a0f08c6395b31938893d1cdad81f54a54456221ecd8c1941294d\"}" https://localhost:5000/eth/poll
