#!/bin/bash
# init
function pause() {
  read -p "$*"
}
# =============================================
# SCRIPT COMMANDS
echo
echo "** Update Hummingbot instance **"
echo
echo "=> List of stopped docker instances:"
docker ps --filter "status=exited"
echo
echo "Note: if you do not see your docker instance, connect to your instance and run \"exit\" to shut down."
echo
# Ask the user for the name of the instance to update
echo "Enter the name of the Hummingbot instance to update:"
echo "(Press [enter] for default value: hummingbot-instance)"
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
# List all directories in the current folder
echo "List of folders in your directory:"
ls -d */
echo
# Ask the user for the folder location of the instance
echo "Enter a folder for your config and log files:"
echo "(Press [enter] for default value: $DEFAULT_FOLDER)"
read FOLDER
if [ "$FOLDER" == "" ]
then
  FOLDER=$DEFAULT_FOLDER
fi
#
#
#
# =============================================
# EXECUTE SCRIPT
# 1) Delete instance and old hummingbot image
docker rm $INSTANCE_NAME
docker image rm coinalpha/hummingbot:latest
# 2) Re-create instance with latest hummingbot release
docker run -it \
--name $INSTANCE_NAME \
--mount "type=bind,source=$(pwd)/$FOLDER/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/$FOLDER/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest