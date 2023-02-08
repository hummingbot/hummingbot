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
read -p "   Enter a name for your new Hummingbot instance (default = \"hummingbot\") >>> " INSTANCE_NAME
if [ "$INSTANCE_NAME" == "" ]
then
  INSTANCE_NAME="hummingbot"
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
CONF_FOLDER="$FOLDER/conf"
LOGS_FOLDER="$FOLDER/logs"
DATA_FOLDER="$FOLDER/data"
PMM_SCRIPTS_FOLDER="$FOLDER/pmm-scripts"
SCRIPTS_FOLDER="$FOLDER/scripts"
CERTS_FOLDER="$FOLDER/certs"

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
 # 3) Set required permissions to save hummingbot password the first time
 sudo chmod a+rw $CONF_FOLDER $CERTS_FOLDER
 # 4) Launch a new instance of hummingbot
 docker run -it --log-opt max-size=10m --log-opt max-file=5 \
 --name $INSTANCE_NAME \
 --network host \
 -v $CONF_FOLDER:/conf \
 -v $LOGS_FOLDER:/logs \
 -v $DATA_FOLDER:/data \
 -v $PMM_SCRIPTS_FOLDER:/pmm_scripts \
 -v $SCRIPTS_FOLDER:/scripts \
 -v $CERTS_FOLDER:/certs \
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
