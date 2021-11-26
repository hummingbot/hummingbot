#!/bin/bash

CONFIG_PATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )/../conf"
cp "$CONFIG_PATH/samples/avalanche.yml" "$CONFIG_PATH/avalanche.yml"

cp "$CONFIG_PATH/samples/ethereum-gas-station.yml" "$CONFIG_PATH/ethereum-gas-station.yml"
sed -i '/apiKey: .*/d;/^ *$/d' "$CONFIG_PATH/ethereum-gas-station.yml"
echo "apiKey: 'blahblah'" >> "$CONFIG_PATH/ethereum-gas-station.yml"
