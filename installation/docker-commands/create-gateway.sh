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
read -p "   Enter the full location path where your Hummingbot files are located (example: /Users/hbot/hummingbot_files) >>> " FOLDER
if [ "$FOLDER" == "" ]
then
  prompt_hummingbot_data_path
else
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
  # chain
  if [ "$key" == "ethereum_chain_name" ]
  then
    ETHEREUM_CHAIN="$(echo -e "${value}" | tr -d '[:space:]')"
    # subgraph url
    if [[ "$ETHEREUM_CHAIN" == "MAIN_NET" || "$ETHEREUM_CHAIN" == "main_net"  || "$ETHEREUM_CHAIN" == "MAINNET"  || "$ETHEREUM_CHAIN" == "mainnet" ]]
    then
      ETHEREUM_CHAIN="mainnet"
      REACT_APP_SUBGRAPH_URL="https://api.thegraph.com/subgraphs/name/balancer-labs/balancer"
      EXCHANGE_PROXY="0x3E66B66Fd1d0b02fDa6C811Da9E0547970DB2f21"
    else
      ETHEREUM_CHAIN="kovan"
      REACT_APP_SUBGRAPH_URL="https://api.thegraph.com/subgraphs/name/balancer-labs/balancer-kovan"
      EXCHANGE_PROXY="0x4e67bf5bD28Dd4b570FBAFe11D0633eCbA2754Ec"
    fi
  fi
  # ethereum rpc url
  if [ "$key" == "ethereum_rpc_url" ]
  then
    ETHEREUM_RPC_URL="$(echo -e "${value}" | tr -d '[:space:]')"
  fi
done < "$GLOBAL_CONFIG"
}
read_global_config

# prompt to setup balancer, uniswap
prompt_ethereum_setup () {
  read -p "   Do you want to setup Balancer/Uniswap/Perpetual Finance? [Y/N] >>> " PROCEED
  if [[ "$PROCEED" == "Y" || "$PROCEED" == "y" ]]
  then
    echo "ℹ️  Retrieving config from Hummingbot config file ... "
    ETHEREUM_SETUP=true
    echo
  fi
}
prompt_ethereum_setup

# Ask the user for ethereum network
prompt_terra_network () {
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
  read -p "   Do you want to setup Terra? [Y/N] >>> " PROCEED
  if [[ "$PROCEED" == "Y" || "$PROCEED" == "y" ]]
  then
    TERRA_SETUP=true
    prompt_terra_network
  fi
}
prompt_terra_setup

# setup uniswap config
UNISWAP_ROUTER=0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D

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
printf "%30s %5s\n" "Balancer Subgraph:" "$REACT_APP_SUBGRAPH_URL"
printf "%30s %5s\n" "Balancer Exchange Proxy:" "$EXCHANGE_PROXY"
printf "%30s %5s\n" "Uniswap Router:" "$UNISWAP_ROUTER"
printf "%30s %5s\n" "Terra Chain:" "$TERRA"
printf "%30s %5s\n" "Gateway Log Path:" "$LOG_PATH"
printf "%30s %5s\n" "Gateway Cert Path:" "$CERT_PATH"
printf "%30s %5s\n" "Gateway Port:" "$PORT"
echo

ENV_FILE="./gateway.env"
echo "  Writing config to environment file"
echo "" > $ENV_FILE # clear existing file data
echo "# gateway-api script generated env" >> $ENV_FILE
echo "" >> $ENV_FILE
echo "NODE_ENV=prod" >> $ENV_FILE
echo "PORT=$PORT" >> $ENV_FILE
echo "" >> $ENV_FILE
echo "HUMMINGBOT_INSTANCE_ID=$HUMMINGBOT_INSTANCE_ID" >> $ENV_FILE
echo "ETHEREUM_CHAIN=$ETHEREUM_CHAIN" >> $ENV_FILE
echo "ETHEREUM_RPC_URL=$ETHEREUM_RPC_URL" >> $ENV_FILE
echo "REACT_APP_SUBGRAPH_URL=$REACT_APP_SUBGRAPH_URL" >> $ENV_FILE # must used "REACT_APP_SUBGRAPH_URL" for balancer-sor
echo "EXCHANGE_PROXY=$EXCHANGE_PROXY" >> $ENV_FILE
echo "UNISWAP_ROUTER=$UNISWAP_ROUTER" >> $ENV_FILE
echo "TERRA_LCD_URL=$TERRA_LCD_URL" >> $ENV_FILE
echo "TERRA_CHAIN=$TERRA_CHAIN" >> $ENV_FILE
echo "" >> $ENV_FILE

prompt_proceed () {
 echo
 read -p "  Do you want to proceed with installation? [Y/N] >>> " PROCEED
 if [ "$PROCEED" == "" ]
 then
 PROCEED="Y"
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
 --env-file $ENV_FILE \
 -e CERT_PASSPHRASE="$PASSWORD" \
 -e GMT_OFFSET="$GMT_OFFSET" \
 --mount "type=bind,source=$CERT_PATH,destination=/usr/src/app/certs/" \
 --mount "type=bind,source=$LOG_PATH,destination=/usr/src/app/logs/" \
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
