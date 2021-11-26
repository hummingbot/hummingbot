#!/bin/bash
# init

echo
echo
echo "===============  GENERATE GATEWAY CONFIGURATION FILES ==============="
echo
echo

prompt_cert_path () {
read -p "Enter the directory path for you SSL certificates (example = \"/home/user/hummingbot/certs\")>>> " CERT_PATH
if [ -d "$CERT_PATH" ]; then
    echo "SSL certificate path set as $CERT_PATH."
else 
    echo "Invalid file path, try again"
    prompt_cert_path
fi    
}
prompt_cert_path

prompt_infura_api_key () {
read -p "Enter Infura API Key (required for Ethereum node, if you do not have one, make an account at infura.io): " INFURA_KEY
echo "Infura API Key is $INFURA_KEY."
}
prompt_infura_api_key

prompt_eth_gas_station_api_key () {
read -p "Enter Eth Gas Station API Key (required for Ethereum, if you do not have one, one at https://ethgasstation.info): " ETH_GAS_STATION_KEY
echo "Infura API Key is $ETH_GAS_STATION_KEY."
}
prompt_eth_gas_station_api_key

prompt_to_allow_telemetry () {
read -p "Do you want to enable telemetry?  [yes/no] (default = \"no\")>>> " TELEMETRY
if [[ "$TELEMETRY" == "" || "$TELEMETRY" == "No" || "$TELEMETRY" == "no" ]]
then
  echo "Telemetry disabled."
  TELEMETRY=false
elif [[ "$TELEMETRY" == "Yes" || "$TELEMETRY" == "yes" ]]
then
  echo "Telemetry enabled."
  TELEMETRY=true
else
  echo "Invalid input, try again."
  prompt_to_allow_telemetry
fi
}
prompt_to_allow_telemetry

CONFIG_PATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )/../conf"


# generate ethereum file
echo "networks:" > "$CONFIG_PATH/ethereum.yml"
echo "  mainnet:" >> "$CONFIG_PATH/ethereum.yml"
echo "    chainID: 1" >> "$CONFIG_PATH/ethereum.yml"
echo "    nodeURL: https://kovan.infura.io/v3/" >> "$CONFIG_PATH/ethereum.yml"
echo "    nodeApiKey: $INFURA_KEY" >> "$CONFIG_PATH/ethereum.yml"
echo "  kovan:" >> "$CONFIG_PATH/ethereum.yml"
echo "    chainID: 42" >> "$CONFIG_PATH/ethereum.yml"
echo "    nodeURL: https://kovan.infura.io/v3/" >> "$CONFIG_PATH/ethereum.yml"
echo "    nodeApiKey: $INFURA_KEY" >> "$CONFIG_PATH/ethereum.yml"
echo "created $CONFIG_PATH/ethereum.yml"

# generate ssl file
echo "caCertificatePath: $CERT_PATH/ca_cert.pem"   > "$CONFIG_PATH/ssl.yml"
echo "certificatePath: $CERT_PATH/server_cert.pem" >> "$CONFIG_PATH/ssl.yml"
echo "keyPath: $CERT_PATH/server_key.pem"          >> "$CONFIG_PATH/ssl.yml"
echo "passPhrasePath: $CONFIG_PATH/gateway-passphrase.yml" >> "$CONFIG_PATH/ssl.yml"
echo "created $CONFIG_PATH/ssl.yml"

# update apiKey in the ethereum-gas-station file
cp "$CONFIG_PATH/samples/ethereum-gas-station.yml" "$CONFIG_PATH/ethereum-gas-station.yml"
sed -i '/apiKey: .*/d;/^ *$/d' "$CONFIG_PATH/ethereum-gas-station.yml"
echo "apiKey: '$ETH_GAS_STATION_KEY'" >> "$CONFIG_PATH/ethereum-gas-station.yml"
echo "created $CONFIG_PATH/ethereum-gas-station.yml"

# copy the following files

cp "$CONFIG_PATH/samples/avalanche.yml" "$CONFIG_PATH/avalanche.yml"
echo "created $CONFIG_PATH/avalanche.yml"

cp "$CONFIG_PATH/samples/logging.yml" "$CONFIG_PATH/logging.yml"
echo "created $CONFIG_PATH/logging.yml"

cp "$CONFIG_PATH/samples/pangolin.yml" "$CONFIG_PATH/pangolin.yml"
echo "created $CONFIG_PATH/pangolin.yml"

cp "$CONFIG_PATH/samples/root.yml" "$CONFIG_PATH/root.yml"
echo "created $CONFIG_PATH/root.yml"

cp "$CONFIG_PATH/samples/server.yml" "$CONFIG_PATH/server.yml"
echo "created $CONFIG_PATH/server.yml"

cp "$CONFIG_PATH/samples/uniswap.yml" "$CONFIG_PATH/uniswap.yml"
echo "created $CONFIG_PATH/uniswap.yml"

# generate the telemetry file
echo "enabled: $TELEMETRY" > "$CONFIG_PATH/telemetry.yml"
echo "created $CONFIG_PATH/telemetry.yml"
