#!/bin/bash
# init
function pause() {
  read -p "$*"
}
# =============================================
# SCRIPT COMMANDS
# Ask the user for the name or their instance
echo
echo "** Creating a new Hummingbot instance **"
echo
echo "Enter a name for your new Hummingbot instance:"
echo "(Press enter for default value: hummingbot-instance)"
read INSTANCE_NAME
if [ "$INSTANCE_NAME" == "" ];
then
  INSTANCE_NAME="hummingbot-instance"
  FOLDER="hummingbot_files"
else
  FOLDER="$INSTANCE_NAME"
fi
echo
echo "Creating your hummingbot instance: \"$INSTANCE_NAME\""
echo
echo "Your files will be saved to:"
echo "=> instance folder:    $PWD/$FOLDER"
echo "=> config files:       ├── $PWD/$FOLDER/hummingbot_conf"
echo "=> log files:          └── $PWD/$FOLDER/hummingbot_logs"
echo
pause Press [Enter] to continue
# =============================================
# EXECUTE SCRIPT
# 1) Create folder for your new instance
mkdir $FOLDER
# 2) Create folders for log and config files
mkdir $FOLDER/hummingbot_conf && mkdir $FOLDER/hummingbot_logs
# 3) Launch a new instance of hummingbot
docker run -it \
--name $INSTANCE_NAME \
--mount "type=bind,source=$(pwd)/$FOLDER/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/$FOLDER/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest