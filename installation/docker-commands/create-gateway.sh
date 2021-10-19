#!/bin/bash
# init

echo
echo
echo "===============  CREATE A NEW GATEWAY INSTANCE ==============="
echo
echo
echo "ℹ️  Press [ENTER] for default values:"
echo

echo
read -p "   Enter Gateway version you want to use [latest/development] (default = \"latest\") >>> " GATEWAY_TAG
if [ "$GATEWAY_TAG" == "" ]
then
  GATEWAY_TAG="latest"
fi

# Ask the user for the name of the new Gateway instance
read -p "   Enter a name for your new Gateway instance (default = \"gateway-instance\") >>> " GATEWAY_INSTANCE_NAME
if [ "$GATEWAY_INSTANCE_NAME" == "" ]
then
  GATEWAY_INSTANCE_NAME="gateway-instance"
fi


# Ask the user for the hummingobt data folder location
prompt_hummingbot_data_path () {
read -p "   Enter the location where your Hummingbot files are located (example: /Users/hbot/hummingbot_files) >>> " FOLDER
if [ "$FOLDER" == "" ]
then
  prompt_hummingbot_data_path
else
  if [[ ${FOLDER::1} != "/" ]]; then
    FOLDER=$PWD/$FOLDER
  fi

  if [ ! -d "$FOLDER" ]; then
    echo "‼️  Directory not found in ${FOLDER}"
    prompt_hummingbot_data_path
  else
    if [[ -d "$FOLDER/hummingbot_conf" && -d "$FOLDER/hummingbot_certs" ]]; then
      CERT_PATH=$FOLDER/hummingbot_certs
    else
      echo "‼️  hummingbot_conf & hummingbot_certs directory missing from path $FOLDER"
      prompt_hummingbot_data_path
    fi

    if [[ -f "$FOLDER/hummingbot_certs/server_cert.pem" && -f "$FOLDER/hummingbot_certs/server_key.pem" && -f "$FOLDER/hummingbot_certs/ca_cert.pem" ]]; then
      echo
    else
      echo "‼️  SSL Certs missing from path $FOLDER"
      echo "  Required: server_cert.pem, server_key.pem, ca_cert.pem"
      prompt_hummingbot_data_path
    fi

    # get log folder path
    if [ -d "$FOLDER/hummingbot_logs" ]; then
      LOG_PATH=$FOLDER/hummingbot_logs
    else
      echo "‼️  hummingbot_logs directory missing from path $FOLDER"
      prompt_hummingbot_data_path
    fi
  fi
fi
}
prompt_hummingbot_data_path

read_global_config () {
GLOBAL_CONFIG="$FOLDER/hummingbot_conf/conf_global.yml"
# check for missing config
if [[ ! -f "$GLOBAL_CONFIG" ]]
then
  echo "‼️  conf_global.yml missing from path $GLOBAL_CONFIG"
  echo "Error! Unable to continue setup"
  exit
fi

while IFS=: read key value || [[ -n "$value" ]]
do
  # hummingbot instance id
  if [ "$key" == "instance_id" ]
  then
    HUMMINGBOT_INSTANCE_ID="$(echo -e "${value}" | tr -d '[:space:]')"
  fi
  #
done < "$GLOBAL_CONFIG"
}
read_global_config

# prompt to setup balancer, uniswap
prompt_ethereum_setup () {
  read -p "   Do you want to setup Balancer or Uniswap? [Y/N] (default \"Y\") >>> " PROCEED
  if [[ "$PROCEED" == "Y" || "$PROCEED" == "y"  || "$PROCEED" == ""  ]]
  then
    ETHEREUM_SETUP=true
    echo
    read -p "   Enter Ethereum chain you want to use [mainnet/kovan] (default = \"mainnet\") >>> " ETHEREUM_CHAIN
    # chain selection
    if [ "$ETHEREUM_CHAIN" == "" ]
    then
      ETHEREUM_CHAIN="mainnet"
    fi
    if [[ "$ETHEREUM_CHAIN" != "mainnet" && "$ETHEREUM_CHAIN" != "kovan" ]]
    then
      echo "‼️  ERROR. Unsupported chains (mainnet/kovan). "
      prompt_ethereum_setup
    fi
  fi
}
prompt_ethereum_setup

# prompt to ethereum rpc
prompt_ethereum_rpc_setup () {
  if [ "$ETHEREUM_RPC_URL" == "" ]
  then
    read -p "   Enter the Ethereum RPC node URL to connect to  >>> " ETHEREUM_RPC_URL
    if [ "$ETHEREUM_RPC_URL" == "" ]
    then
      prompt_ethereum_rpc_setup
    fi
  else
    read -p "   Use the this Ethereum RPC node ($ETHEREUM_RPC_URL) setup in Hummingbot client?  [Y/N] (default = \"Y\") >>> " PROCEED
    if [[ "$PROCEED" == "Y" || "$PROCEED" == "y" || "$PROCEED" == "" ]]
    then
      echo
    else
      ETHEREUM_RPC_URL=""
      prompt_ethereum_rpc_setup
    fi
  fi
}
prompt_ethereum_rpc_setup

# prompt to setup ethereum token list
prompt_token_list_source () {
  echo
  echo "   Enter the token list url available at https://tokenlists.org/"
  read -p "      (default = \"https://wispy-bird-88a7.uniswap.workers.dev/?url=http://tokens.1inch.eth.link\") >>> " ETHEREUM_TOKEN_LIST_URL
  if [ "$ETHEREUM_TOKEN_LIST_URL" == "" ]
  then
    echo
    echo "ℹ️  Retrieving config from Hummingbot config file ... "
    ETHEREUM_SETUP=true
    ETHEREUM_TOKEN_LIST_URL=https://wispy-bird-88a7.uniswap.workers.dev/?url=http://tokens.1inch.eth.link
  fi
}
prompt_token_list_source

# prompt to setup eth gas level
prompt_eth_gasstation_gas_level () {
  echo
  read -p "   Enter gas level you want to use for Ethereum transactions (fast, fastest, safeLow, average) (default = \"fast\") >>> " ETH_GAS_STATION_GAS_LEVEL
  if [ "$ETH_GAS_STATION_GAS_LEVEL" == "" ]
  then
    ETH_GAS_STATION_GAS_LEVEL=fast
  else
    if [[ "$ETH_GAS_STATION_GAS_LEVEL" != "fast" && "$ETH_GAS_STATION_GAS_LEVEL" != "fastest" && "$ETH_GAS_STATION_GAS_LEVEL" != "safeLow" && "$ETH_GAS_STATION_GAS_LEVEL" != "safelow" && "$ETH_GAS_STATION_GAS_LEVEL" != "average" ]]
    then
      prompt_eth_gasstation_gas_level
    fi
  fi
}

# prompt to setup eth gas station
prompt_eth_gasstation_setup () {
  echo
  read -p "   Enable dynamic Ethereum gas price lookup? [Y/N] (default = \"Y\") >>> " PROCEED
  if [[ "$PROCEED" == "Y" || "$PROCEED" == "y" || "$PROCEED" == "" ]]
  then
    ETH_GAS_STATION_ENABLE=true
    read -p "   Enter API key for Eth Gas Station (https://ethgasstation.info/) >>> " ETH_GAS_STATION_API_KEY
    if [ "$ETH_GAS_STATION_API_KEY" == "" ]
    then
      prompt_eth_gasstation_setup
    else
      # set gas level
      prompt_eth_gasstation_gas_level

      # set refresh interval
      read -p "   Enter refresh time for Ethereum gas price lookup (in seconds) (default = \"120\") >>> " ETH_GAS_STATION_REFRESH_TIME
      if [ "$ETH_GAS_STATION_REFRESH_TIME" == "" ]
      then
        ETH_GAS_STATION_REFRESH_TIME=120
      fi
    fi
  else
    if [[ "$PROCEED" == "N" || "$PROCEED" == "n" ]]
    then
      ETH_GAS_STATION_ENABLE=false
      ETH_GAS_STATION_API_KEY=null
      ETH_GAS_STATION_GAS_LEVEL=fast
      ETH_GAS_STATION_REFRESH_TIME=60
      ETH_MANUAL_GAS_PRICE=100
    else
      prompt_eth_gasstation_setup
    fi
  fi
  echo
}
prompt_eth_gasstation_setup

prompt_balancer_setup () {
  # Ask the user for the Balancer specific settings
  echo "ℹ️  Balancer setting "
  read -p "   Enter the maximum Balancer swap pool (default = \"4\") >>> " BALANCER_MAX_SWAPS
  if [ "$BALANCER_MAX_SWAPS" == "" ]
  then
    BALANCER_MAX_SWAPS="4"
    echo
  fi
}

prompt_uniswap_setup () {
  # Ask the user for the Uniswap specific settings
  echo "ℹ️  Uniswap setting "
  read -p "   Enter the allowed slippage for swap transactions (default = \"1.5\") >>> " UNISWAP_SLIPPAGE
  if [ "$UNISWAP_SLIPPAGE" == "" ]
  then
    UNISWAP_SLIPPAGE="1.5"
    echo
  fi
}

if [[ "$ETHEREUM_SETUP" == true ]]
then
  prompt_balancer_setup
  prompt_uniswap_setup
fi

prompt_xdai_setup () {
  # Ask the user for the Uniswap specific settings
  echo "ℹ️  XDAI setting "
  read -p "   Enter preferred XDAI rpc provider (default = \"https://rpc.xdaichain.com\") >>> " XDAI_PROVIDER
  if [ "$XDAI_PROVIDER" == "" ]
  then
    XDAI_PROVIDER="https://rpc.xdaichain.com"
    echo
  fi
}
prompt_xdai_setup

# Ask the user for ethereum network
prompt_terra_network () {
  echo
  read -p "   Enter Terra chain you want to use [mainnet/testnet] (default = \"mainnet\") >>> " TERRA
  # chain selection
  if [ "$TERRA" == "" ]
  then
    TERRA="mainnet"
  fi
  if [[ "$TERRA" != "mainnet" && "$TERRA" != "testnet" ]]
  then
    echo "‼️  ERROR. Unsupported chains (mainnet/testnet). "
    prompt_terra_network
  fi
  # setup chain params
  if [[ "$TERRA" == "mainnet" ]]
  then
    TERRA_LCD_URL="https://lcd.terra.dev"
    TERRA_CHAIN="columbus-4"
  elif [ "$TERRA" == "testnet" ]
  then
    TERRA_LCD_URL="https://tequila-lcd.terra.dev"
    TERRA_CHAIN="tequila-0004"
  fi
}

prompt_terra_setup () {
  echo
  read -p "   Do you want to setup Terra? [Y/N] (default \"Y\") >>> " PROCEED
  if [[ "$PROCEED" == "Y" || "$PROCEED" == "y" || "$PROCEED" == "" ]]
  then
    TERRA_SETUP=true
    prompt_terra_network
  fi
}
prompt_terra_setup

# setup uniswap config
UNISWAP_ROUTER="0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
UNISWAP_V3_CORE="0x1F98431c8aD98523631AE4a59f267346ea31F984"
UNISWAP_V3_ROUTER="0xE592427A0AEce92De3Edee1F18E0157C05861564"
UNISWAP_V3_NFT_MANAGER="0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
BALANCER_VAULT="0xBA12222222228d8Ba445958a75a0704d566BF2C8"

# network setup verifications
if [[ "$ETHEREUM_SETUP" != true && "$TERRA_SETUP" != true ]]
then
  echo
  echo "‼️  ERROR. Balancer/Uniswap & Terra Setup are both not selected. "
  echo "   Setup will not continue."
  exit
fi

# Ask the user for the hummingobt data folder location
prompt_password () {
echo
read -s -p "   Enter the your Gateway cert passphrase configured in Hummingbot  >>> " PASSWORD
if [ "$PASSWORD" == "" ]
then
 echo
 echo
 echo "‼️  ERROR. Certificates are not empty string. "
 prompt_password
fi
}
prompt_password

# Get GMT offset from local system time
GMT_OFFSET=$(date +%z)

# Check available open port for Gateway
PORT=5000
LIMIT=$((PORT+1000))
while [[ $PORT -le LIMIT ]]
  do
    if [[ $(netstat -nat | grep "$PORT") ]]; then
      # check another port
      ((PORT = PORT + 1))
    else
      break
    fi
done

echo
echo "ℹ️  Confirm below if the instance and its folders are correct:"
echo

printf "%30s %5s\n" "Gateway instance name:" "$GATEWAY_INSTANCE_NAME"
printf "%30s %5s\n" "Version:" "coinalpha/gateway-api:$GATEWAY_TAG"
echo
printf "%30s %5s\n" "Hummingbot Instance ID:" "$HUMMINGBOT_INSTANCE_ID"
printf "%30s %5s\n" "Ethereum Chain:" "$ETHEREUM_CHAIN"
printf "%30s %5s\n" "Ethereum RPC URL:" "$ETHEREUM_RPC_URL"
printf "%30s %5s\n" "Ethereum Token List URL:" "$ETHEREUM_TOKEN_LIST_URL"
printf "%30s %5s\n" "Manual Gas Price:" "$ETH_MANUAL_GAS_PRICE"
printf "%30s %5s\n" "Enable Eth Gas Station:" "$ETH_GAS_STATION_ENABLE"
printf "%30s %5s\n" "Eth Gas Station API:" "$ETH_GAS_STATION_API_KEY"
printf "%30s %5s\n" "Eth Gas Station Level:" "$ETH_GAS_STATION_GAS_LEVEL"
printf "%30s %5s\n" "Eth Gas Station Refresh Interval:" "$ETH_GAS_STATION_REFRESH_TIME"
printf "%30s %5s\n" "Balancer Vault:" "$BALANCER_VAULT"
printf "%30s %5s\n" "Balancer Max Swaps:" "$BALANCER_MAX_SWAPS"
printf "%30s %5s\n" "Uniswap Router:" "$UNISWAP_ROUTER"
printf "%30s %5s\n" "Uniswap V3 Core:" "$UNISWAP_V3_CORE"
printf "%30s %5s\n" "Uniswap V3 Router:" "$UNISWAP_V3_ROUTER"
printf "%30s %5s\n" "Uniswap V3 NFT Manager:" "$UNISWAP_V3_NFT_MANAGER"
printf "%30s %5s\n" "Uniswap Allowed Slippage:" "$UNISWAP_SLIPPAGE"
printf "%30s %5s\n" "Terra Chain:" "$TERRA"
printf "%30s %5s\n" "Gateway Log Path:" "$LOG_PATH"
printf "%30s %5s\n" "Gateway Cert Path:" "$CERT_PATH"
printf "%30s %5s\n" "Gateway Port:" "$PORT"
echo

ENV_FILE="$FOLDER/hummingbot_conf/global_conf.yml"
echo "  Writing config to environment file"
echo "" > $ENV_FILE # clear existing file data
echo "# gateway-api script generated env" >> $ENV_FILE
echo "" >> $ENV_FILE
echo "CORE:" >> $ENV_FILE
echo "  NODE_ENV: prod" >> $ENV_FILE
echo "  PORT: $PORT" >> $ENV_FILE
echo "" >> $ENV_FILE
echo "HUMMINGBOT_INSTANCE_ID: $HUMMINGBOT_INSTANCE_ID" >> $ENV_FILE

# ethereum config
echo "" >> $ENV_FILE
echo "# Ethereum Settings" >> $ENV_FILE
echo "ETHEREUM_CHAIN: $ETHEREUM_CHAIN" >> $ENV_FILE
echo "ETHEREUM_RPC_URL: $ETHEREUM_RPC_URL" >> $ENV_FILE
echo "ETHEREUM_TOKEN_LIST_URL: $ETHEREUM_TOKEN_LIST_URL" >> $ENV_FILE
echo "" >> $ENV_FILE
echo "ETH_GAS_STATION_ENABLE: $ETH_GAS_STATION_ENABLE" >> $ENV_FILE
echo "ETH_GAS_STATION_API_KEY: $ETH_GAS_STATION_API_KEY" >> $ENV_FILE
echo "ETH_GAS_STATION_GAS_LEVEL: $ETH_GAS_STATION_GAS_LEVEL" >> $ENV_FILE
echo "ETH_GAS_STATION_REFRESH_TIME: $ETH_GAS_STATION_REFRESH_TIME" >> $ENV_FILE
echo "ETH_MANUAL_GAS_PRICE: $ETH_MANUAL_GAS_PRICE" >> $ENV_FILE

# balancer config
echo "" >> $ENV_FILE
echo "# Balancer Settings" >> $ENV_FILE
echo "BALANCER_VAULT: '$BALANCER_VAULT'" >> $ENV_FILE
echo "BALANCER_MAX_SWAPS: $BALANCER_MAX_SWAPS" >> $ENV_FILE

# uniswap config
echo "" >> $ENV_FILE
echo "# Uniswap Settings" >> $ENV_FILE
echo "UNISWAP_ROUTER: '$UNISWAP_ROUTER'" >> $ENV_FILE
echo "UNISWAP_V3_CORE: '$UNISWAP_V3_CORE'" >> $ENV_FILE
echo "UNISWAP_V3_ROUTER: '$UNISWAP_V3_ROUTER'" >> $ENV_FILE
echo "UNISWAP_V3_NFT_MANAGER: '$UNISWAP_V3_NFT_MANAGER'" >> $ENV_FILE
echo "UNISWAP_ALLOWED_SLIPPAGE: $UNISWAP_SLIPPAGE" >> $ENV_FILE
echo "UNISWAP_NO_RESERVE_CHECK_INTERVAL: 300000" >> $ENV_FILE
echo "UNISWAP_PAIRS_CACHE_TIME: 1000" >> $ENV_FILE

# terra config
echo "" >> $ENV_FILE
echo "# Terra Settings" >> $ENV_FILE
echo "TERRA_LCD_URL: $TERRA_LCD_URL" >> $ENV_FILE
echo "TERRA_CHAIN: $TERRA_CHAIN" >> $ENV_FILE

# perpeptual finance config
echo "" >> $ENV_FILE
echo "# Perpeptual Settings" >> $ENV_FILE
echo "XDAI_PROVIDER: $XDAI_PROVIDER" >> $ENV_FILE

# certs
echo "" >> $ENV_FILE
echo "# cert" >> $ENV_FILE
echo "CERT_PATH: ./certs" >> $ENV_FILE
echo "CERT_PASSPHRASE: $PASSWORD" >> $ENV_FILE

echo "GMT_OFFSET: '+0800'" >> $ENV_FILE
echo "" >> $ENV_FILE

prompt_proceed () {
 echo
 read -p "  Do you want to proceed with installation? [Y/N] >>> " PROCEED
 if [ "$PROCEED" == "" ]
 then
 prompt_proceed
 else
  if [[ "$PROCEED" != "Y" && "$PROCEED" != "y" ]]
  then
    PROCEED="N"
  fi
 fi
}

# Execute docker commands
create_instance () {
 echo
 echo "Creating Gateway instance ... "
 echo



 # Launch a new instance of hummingbot
 docker run -d \
 --name $GATEWAY_INSTANCE_NAME \
 -p 127.0.0.1:$PORT:$PORT \
 --mount "type=bind,source=$CERT_PATH,destination=/usr/src/app/certs/" \
 --mount "type=bind,source=$LOG_PATH,destination=/usr/src/app/logs/" \
 --mount "type=bind,source=$FOLDER/hummingbot_conf/,destination=/usr/src/app/conf/" \
 coinalpha/gateway-api:$GATEWAY_TAG
}

prompt_proceed
if [[ "$PROCEED" == "Y" || "$PROCEED" == "y" ]]
then
 create_instance
else
 echo "   Aborted"
 echo
fi
