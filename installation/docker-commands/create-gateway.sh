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

# Ask the user for balancer network
SUBGRAPH_URL=""
EXCHANGE_PROXY=""
prompt_balancer_network () {
read -p "   Enter Balancer network you want to use [mainnet/kovan] (default = \"mainnet\") >>> " BALANCER_NETWORK
if [[ "$BALANCER_NETWORK" == "" || "$BALANCER_NETWORK" == "mainnet" ]]
then
  BALANCER_NETWORK="mainnet"
  SUBGRAPH_URL="https://api.thegraph.com/subgraphs/name/balancer-labs/balancer"
  EXCHANGE_PROXY="0x3E66B66Fd1d0b02fDa6C811Da9E0547970DB2f21"
elif [ "$BALANCER_NETWORK" == "kovan" ]
then
  BALANCER_NETWORK="kovan"
  SUBGRAPH_URL="https://api.thegraph.com/subgraphs/name/balancer-labs/balancer-kovan"
  EXCHANGE_PROXY="0x4e67bf5bD28Dd4b570FBAFe11D0633eCbA2754Ec"
elif [[ "$BALANCER_NETWORK" != "" && "$BALANCER_NETWORK" != "mainnet" && "$BALANCER_NETWORK" != "kovan" ]]
then
  prompt_balancer_network
fi
}
prompt_balancer_network

# Ask the user for the hummingobt data folder location
prompt_hummingbot_data_path () {
read -p "   Enter the full location path where your Hummingbot cert files are located  >>> " FOLDER
if [ "$FOLDER" == "" ]
then
  prompt_hummingbot_data_path
else
  if [ ! -d "$FOLDER" ]; then
    echo "‼️  Directory not found in ${FOLDER}"
    prompt_hummingbot_data_path
  else
    # check for server_cert.pem, server_key.pem, ca_cert.pem
    if [[ -f "$FOLDER/server_cert.pem" && -f "$FOLDER/server_key.pem" && -f "$FOLDER/ca_cert.pem" ]]; then
      echo
    else
      echo "‼️  SSL Certs missing from path $FOLDER"
      echo "  Required: server_cert.pem, server_key.pem, ca_cert.pem"
      prompt_hummingbot_data_path
    fi
  fi
fi
}
prompt_hummingbot_data_path

# Ask the user for the ethereum rpc url
prompt_ethereum_rpc_url () {
read -p "   Enter the Ethereum RPC URL set in your Hummingbot instance  >>> " RPC_URL
if [ "$RPC_URL" == "" ]
then
  prompt_ethereum_rpc_url
fi
}
prompt_ethereum_rpc_url


# Ask the user for the hummingobt data folder location
prompt_password () {
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
printf "%30s %5s\n" "Balancer Network:" "$BALANCER_NETWORK"
printf "%30s %5s\n" "Balancer Subgraph:" "$SUBGRAPH_URL"
printf "%30s %5s\n" "Balancer Exchange Proxy:" "$EXCHANGE_PROXY"
printf "%30s %5s\n" "Ethereum RPC URL:" "$RPC_URL"
printf "%30s %5s\n" "Gateway Cert Path:" "$FOLDER"
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
echo "BALANCER_NETWORK=$BALANCER_NETWORK" >> $ENV_FILE
echo "ETHEREUM_RPC_URL=$RPC_URL" >> $ENV_FILE
echo "REACT_APP_SUBGRAPH_URL=$SUBGRAPH_URL" >> $ENV_FILE # must used "REACT_APP_SUBGRAPH_URL" for balancer-sor
echo "EXCHANGE_PROXY=$EXCHANGE_PROXY" >> $ENV_FILE
echo "" >> $ENV_FILE

prompt_proceed () {
 read -p "   Do you want to proceed? [Y/N] >>> " PROCEED
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
 --mount "type=bind,source=$FOLDER,destination=/usr/src/app/certs/" \
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
