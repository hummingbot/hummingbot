# export GATEWAY_KEY=''
# export GATEWAY_CERT=''

# -k is --insecure, this disables certificate verfication and should only be
# use for development
# test that the gateway-api server is running
curl -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT https://localhost:5000/

curl -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT https://localhost:5000/eth

# get balances for your private key
curl -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "{\"privateKey\":\"$ETH_PRIVATE_KEY\",\"tokenSymbols\":[\"ETH\",\"WETH\",\"DAI\"]}" https://localhost:5000/eth/balances
