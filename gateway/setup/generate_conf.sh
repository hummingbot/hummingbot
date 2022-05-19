#!/bin/bash
# init

echo
echo
echo "===============  GENERATE GATEWAY CONFIGURATION FILES ==============="
echo
echo


HOST_CONF_PATH="${1:=(pwd -P)/conf}"
INFURA_API_KEY="${2:=null}"

echo "HOST_CONF_PATH=$HOST_CONF_PATH"
echo "INFURA_API_KEY=$INFURA_API_KEY"

mkdir -p $HOST_CONF_PATH

# generate ethereum file
cp "$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )/../src/templates/ethereum.yml" "$HOST_CONF_PATH/ethereum.yml"
sed -i'.bak' -e "/nodeAPIKey:/ s/[^ ][^ ]*$/$INFURA_API_KEY/" "$HOST_CONF_PATH/ethereum.yml"
echo "created $HOST_CONF_PATH/ethereum.yml"

# generate ssl file
cp "$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )/../src/templates/ssl.yml" "$HOST_CONF_PATH/ssl.yml"
echo "created $HOST_CONF_PATH/ssl.yml"
# apiKey must be prompted

# generate ethereum-gas-station file
cp "$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )/../src/templates/ethereum-gas-station.yml" "$HOST_CONF_PATH/ethereum-gas-station.yml"
echo "created $HOST_CONF_PATH/ethereum-gas-station.yml"

# copy the following files

cp "$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )/../src/templates/avalanche.yml" "$HOST_CONF_PATH/avalanche.yml"
echo "created $HOST_CONF_PATH/avalanche.yml"

cp "$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )/../src/templates/logging.yml" "$HOST_CONF_PATH/logging.yml"
echo "created $HOST_CONF_PATH/logging.yml"

cp "$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )/../src/templates/pangolin.yml" "$HOST_CONF_PATH/pangolin.yml"
echo "created $HOST_CONF_PATH/pangolin.yml"

cp "$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )/../src/templates/root.yml" "$HOST_CONF_PATH/root.yml"
echo "created $HOST_CONF_PATH/root.yml"

cp "$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )/../src/templates/server.yml" "$HOST_CONF_PATH/server.yml"
echo "created $HOST_CONF_PATH/server.yml"

cp "$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )/../src/templates/uniswap.yml" "$HOST_CONF_PATH/uniswap.yml"
echo "created $HOST_CONF_PATH/uniswap.yml"

# generate the telemetry file
echo "enabled: false" > "$HOST_CONF_PATH/telemetry.yml"  # enabled must be prompted
echo "created $HOST_CONF_PATH/telemetry.yml"
