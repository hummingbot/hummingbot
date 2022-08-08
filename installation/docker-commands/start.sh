#!/bin/bash
# init
# =============================================
# SCRIPT COMMANDS
echo
echo "===============  START HUMMINGBOT INSTANCE ==============="
echo
echo "List of all docker instances:"
echo
docker ps -a
echo
echo
if [ -f .last_instance ]; then 
  INSTANCE_NAME=`cat .last_instance` 
else
  INSTANCE_NAME="hummingbot-instance"
fi
# Ask the user for the name of the new instance
read -p "   Enter the NAME of the Hummingbot instance to start or connect to (default = \"$INSTANCE_NAME\") >>> " TMP_NAME
if [ "$TMP_NAME" != "" ]
then
  INSTANCE_NAME="$TMP_NAME"
fi
echo
# =============================================
# EXECUTE SCRIPT
echo "$INSTANCE_NAME" > .last_instance
docker start $INSTANCE_NAME && docker attach $INSTANCE_NAME
