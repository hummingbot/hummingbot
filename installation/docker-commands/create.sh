#!/bin/bash
# init

echo
echo
echo "===============  CREATE A NEW HUMMINGBOT INSTANCE ==============="
echo
echo
echo "ℹ️  Press [ENTER] for default values:"
echo

# Specify hummingbot version
read -p "   Enter Hummingbot version you want to use [latest/development] (default = \"latest\") >>> " TAG
if [ "$TAG" == "" ]
then
  TAG="latest"
fi

# Ask the user for the name of the new instance
read -p "   Enter a name for your new Hummingbot instance (default = \"hummingbot-instance\") >>> " INSTANCE_NAME
if [ "$INSTANCE_NAME" == "" ]
then
  INSTANCE_NAME="hummingbot-instance"
  DEFAULT_FOLDER="hummingbot_files"
else
  DEFAULT_FOLDER="${INSTANCE_NAME}_files"
fi

# Ask the user for the folder location to save files
read -p "   Enter a folder name where your Hummingbot files will be saved (default = \"$DEFAULT_FOLDER\") >>> " FOLDER
if [ "$FOLDER" == "" ]
then
  FOLDER=$PWD/$DEFAULT_FOLDER
elif [[ ${FOLDER::1} != "/" ]]; then
  FOLDER=$PWD/$FOLDER
fi
CONF_FOLDER="$FOLDER/hummingbot_conf"
LOGS_FOLDER="$FOLDER/hummingbot_logs"
DATA_FOLDER="$FOLDER/hummingbot_data"
PMM_SCRIPTS_FOLDER="$FOLDER/hummingbot_pmm_scripts"
SCRIPTS_FOLDER="$FOLDER/hummingbot_scripts"
CERTS_FOLDER="$FOLDER/hummingbot_certs"
GATEWAY_CONF_FOLDER="$FOLDER/gateway_conf"
GATEWAY_LOGS_FOLDER="$FOLDER/gateway_logs"

echo
echo "ℹ️  Confirm below if the instance and its folders are correct:"
echo
printf "%30s %5s\n" "Instance name:" "$INSTANCE_NAME"
printf "%30s %5s\n" "Version:" "hummingbot/hummingbot:$TAG"
echo
printf "%30s %5s\n" "Main folder path:" "$FOLDER"
printf "%30s %5s\n" "Config files:" "├── $CONF_FOLDER"
printf "%30s %5s\n" "Log files:" "├── $LOGS_FOLDER"
printf "%30s %5s\n" "Trade and data files:" "├── $DATA_FOLDER"
printf "%30s %5s\n" "PMM scripts files:" "├── $PMM_SCRIPTS_FOLDER"
printf "%30s %5s\n" "Scripts files:" "├── $SCRIPTS_FOLDER"
printf "%30s %5s\n" "Cert files:" "├── $CERTS_FOLDER"
printf "%30s %5s\n" "Gateway config files:" "└── $GATEWAY_CONF_FOLDER"
printf "%30s %5s\n" "Gateway log files:" "└── $GATEWAY_LOGS_FOLDER"
echo

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
 echo "Creating Hummingbot instance ... Admin password may be required to set the required permissions ..."
 echo
 # 1) Create main folder for your new instance
 mkdir $FOLDER
 # 2) Create subfolders for hummingbot files
 mkdir $CONF_FOLDER
 mkdir $CONF_FOLDER/connectors
 mkdir $CONF_FOLDER/strategies
 mkdir $LOGS_FOLDER
 mkdir $DATA_FOLDER
 mkdir $PMM_SCRIPTS_FOLDER
 mkdir $CERTS_FOLDER
 mkdir $SCRIPTS_FOLDER
 mkdir $GATEWAY_CONF_FOLDER
 mkdir $GATEWAY_LOGS_FOLDER
 # 3) Set required permissions to save hummingbot password the first time
 sudo chmod a+rw $CONF_FOLDER
 # 4) Launch a new instance of hummingbot
 docker run -it --log-opt max-size=10m --log-opt max-file=5 \
 --name $INSTANCE_NAME \
 --network host \
 --mount "type=bind,source=$CONF_FOLDER,destination=/conf/" \
 --mount "type=bind,source=$LOGS_FOLDER,destination=/logs/" \
 --mount "type=bind,source=$DATA_FOLDER,destination=/data/" \
 --mount "type=bind,source=$PMM_SCRIPTS_FOLDER,destination=/pmm_scripts/" \
 --mount "type=bind,source=$SCRIPTS_FOLDER,destination=/scripts/" \
 --mount "type=bind,source=$CERTS_FOLDER,destination=/home/hummingbot/.hummingbot-gateway/certs/" \
 --mount "type=bind,source=$GATEWAY_CONF_FOLDER,destination=/gateway-conf/" \
 --mount "type=bind,source=/var/run/docker.sock,destination=/var/run/docker.sock" \
 -e CONF_FOLDER="$CONF_FOLDER" \
 -e DATA_FOLDER="$DATA_FOLDER" \
 -e PMM_SCRIPTS_FOLDER="$PMM_SCRIPTS_FOLDER" \
 -e SCRIPTS_FOLDER="$SCRIPTS_FOLDER" \
 -e CERTS_FOLDER="$CERTS_FOLDER" \
 -e GATEWAY_LOGS_FOLDER="$GATEWAY_LOGS_FOLDER" \
 -e GATEWAY_CONF_FOLDER="$GATEWAY_CONF_FOLDER" \
 hummingbot/hummingbot:$TAG
}

prompt_proceed
if [[ "$PROCEED" == "Y" || "$PROCEED" == "y" ]]
then
 create_instance
else
 echo "   Aborted"
 echo
fi
