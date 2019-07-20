#!/bin/bash
# init
function pause() {
  read -p "$*"
}
# =============================================
# SCRIPT COMMANDS
# Ask the user for the name or their instance
echo
echo "** Update Hummingbot instance **"
echo
echo "=> List of stopped docker instances:"
docker ps --filter "status=exited"
echo
echo "Note: if you do not see your docker instance, make sure it is stopped."
echo
echo "=> Enter the name for your Hummingbot instance:"
echo "   (Press enter for default value: hummingbot-instance)"
read INSTANCE_NAME
if [ "$INSTANCE_NAME" == "" ];
then
  INSTANCE_NAME="hummingbot-instance"
  FOLDER="hummingbot_files"
else
  FOLDER="$INSTANCE_NAME"
fi
#
#
#
# =============================================
# EXECUTE SCRIPT# 1) Delete instance and old hummingbot image
docker rm $INSTANCE_NAME
docker image rm coinalpha/hummingbot:latest
# 2) Re-create instance with latest hummingbot release
docker run -it \
--name $INSTANCE_NAME \
--mount "type=bind,source=$(pwd)/$FOLDER/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/$FOLDER/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest