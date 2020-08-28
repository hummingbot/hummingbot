#!/bin/bash
# init
function pause() {
  read -p "$*"
}
# =============================================
# SCRIPT COMMANDS
echo
echo "** ✏️  Creating a new Hummingbot instance **"
echo
# Specify hummingbot version
echo "ℹ️  Press [enter] for default values."
echo
echo "➡️  Enter Hummingbot version: [latest|development] (default = \"latest\")"
read TAG
if [ "$TAG" == "" ]
then
  TAG="latest"
fi
echo
# Ask the user for the name of the new instance
echo "➡️  Enter a name for your new Hummingbot instance: (default = \"hummingbot-instance\")"
read INSTANCE_NAME
if [ "$INSTANCE_NAME" == "" ];
then
  INSTANCE_NAME="hummingbot-instance"
  DEFAULT_FOLDER="hummingbot_files"
else
  DEFAULT_FOLDER="${INSTANCE_NAME}_files"
fi
echo
echo "=> Instance name: $INSTANCE_NAME"
echo
# Ask the user for the folder location to save files
echo "➡️  Enter a folder name for your config and log files: (default = \"$DEFAULT_FOLDER\")"
read FOLDER
if [ "$FOLDER" == "" ]
then
  FOLDER=$DEFAULT_FOLDER
fi
echo
echo "Creating your hummingbot instance: \"$INSTANCE_NAME\" (coinalpha/hummingbot:$TAG)"
echo
echo "Your files will be saved to:"
echo "=> instance folder:    $PWD/$FOLDER"
echo "=> config files:       ├── $PWD/$FOLDER/hummingbot_conf"
echo "=> log files:          ├── $PWD/$FOLDER/hummingbot_logs"
echo "=> data file:          ├── $PWD/$FOLDER/hummingbot_data"
echo "=> scripts files:      └── $PWD/$FOLDER/hummingbot_scripts"
echo
pause Press [Enter] to continue
#
#
#
# =============================================
# EXECUTE SCRIPT
# 1) Create folder for your new instance
mkdir $FOLDER
# 2) Create folders for log and config files
mkdir $FOLDER/hummingbot_conf
mkdir $FOLDER/hummingbot_logs
mkdir $FOLDER/hummingbot_data
mkdir $FOLDER/hummingbot_scripts
# 3) Launch a new instance of hummingbot
docker run -it \
--network host \
--name $INSTANCE_NAME \
--mount "type=bind,source=$(pwd)/$FOLDER/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/$FOLDER/hummingbot_logs,destination=/logs/" \
--mount "type=bind,source=$(pwd)/$FOLDER/hummingbot_data,destination=/data/" \
--mount "type=bind,source=$(pwd)/$FOLDER/hummingbot_scripts,destination=/scripts/" \
coinalpha/hummingbot:$TAG
