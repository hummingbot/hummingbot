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
echo
echo "ℹ️  Confirm below if the instance and its folders are correct:"
echo
printf "%30s %5s\n" "Instance name:" "$INSTANCE_NAME"
printf "%30s %5s\n" "Version:" "coinalpha/hummingbot:$TAG"
echo
printf "%30s %5s\n" "Main folder path:" "$FOLDER"
printf "%30s %5s\n" "Config files:" "├── $FOLDER/hummingbot_conf"
printf "%30s %5s\n" "Log files:" "├── $FOLDER/hummingbot_logs"
printf "%30s %5s\n" "Trade and data files:" "├── $FOLDER/hummingbot_data"
printf "%30s %5s\n" "Scripts files:" "├── $FOLDER/hummingbot_scripts"
printf "%30s %5s\n" "Cert files:" "└── $FOLDER/hummingbot_certs"
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
 mkdir $FOLDER/hummingbot_conf
 mkdir $FOLDER/hummingbot_logs
 mkdir $FOLDER/hummingbot_data
 mkdir $FOLDER/hummingbot_scripts
 mkdir $FOLDER/hummingbot_certs
 # 3) Set required permissions to save hummingbot password the first time
 sudo chmod a+rw $FOLDER/hummingbot_conf
 # 4) Launch a new instance of hummingbot
 docker run -it --log-opt max-size=10m --log-opt max-file=5 \
 --name $INSTANCE_NAME \
 --network host \
 --mount "type=bind,source=$FOLDER/hummingbot_conf,destination=/conf/" \
 --mount "type=bind,source=$FOLDER/hummingbot_logs,destination=/logs/" \
 --mount "type=bind,source=$FOLDER/hummingbot_data,destination=/data/" \
 --mount "type=bind,source=$FOLDER/hummingbot_scripts,destination=/scripts/" \
 --mount "type=bind,source=$FOLDER/hummingbot_certs,destination=/certs/" \
 coinalpha/hummingbot:$TAG
}

prompt_proceed
if [[ "$PROCEED" == "Y" || "$PROCEED" == "y" ]]
then
 create_instance
else
 echo "   Aborted"
 echo
fi
